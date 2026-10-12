"""Convert provider-neutral tool specs (JSON Schema) to Live API FunctionDeclarations (T028).

The Live API takes an OpenAPI-style subset of JSON Schema, so this:
- maps `type: [X, "null"]` and `enum: [..., null]` to `type: X, nullable: true`;
- maps `const` to a one-value enum (booleans become plain BOOLEAN with the rule in the description);
- drops `x-*`, `default`, `additionalProperties`, `$schema`;
- refuses `oneOf`/`anyOf`, so a contract that the provider can't represent fails loudly.
"""

from typing import Any

from google.genai import types

_KEYMAP = {
    "maxItems": "max_items", "minItems": "min_items", "maxLength": "max_length",
    "minLength": "min_length", "minimum": "minimum", "maximum": "maximum",
    "description": "description", "pattern": "pattern", "format": "format",
}
_DROP = {"default", "additionalProperties", "$schema", "$id", "title", "exclusiveMinimum"}


class UnsupportedSchema(ValueError):
    pass


def convert_schema(schema: dict[str, Any], path: str = "$") -> dict[str, Any]:
    if "oneOf" in schema or "anyOf" in schema:
        raise UnsupportedSchema(f"oneOf/anyOf is not supported by the Live API at {path}")
    out: dict[str, Any] = {}
    nullable = False

    typ = schema.get("type")
    if isinstance(typ, list):
        non_null = [t for t in typ if t != "null"]
        nullable = "null" in typ
        if len(non_null) != 1:
            raise UnsupportedSchema(f"multi-type {typ} at {path}")
        typ = non_null[0]

    if "const" in schema:
        const = schema["const"]
        if isinstance(const, bool):
            typ = "boolean"
            out["description"] = (schema.get("description", "") + f" Must be {str(const).lower()}.").strip()
        else:
            typ = typ or "string"
            out["enum"] = [str(const)]

    if "enum" in schema:
        values = schema["enum"]
        nullable = nullable or None in values
        out["enum"] = [str(v) for v in values if v is not None]
        typ = typ or "string"

    if typ:
        out["type"] = typ.upper()
    if nullable:
        out["nullable"] = True

    for key, value in schema.items():
        if key.startswith("x-") or key in _DROP or key in {"type", "enum", "const"}:
            continue
        if key == "properties":
            out["properties"] = {k: convert_schema(v, f"{path}.{k}") for k, v in value.items()}
        elif key == "items":
            out["items"] = convert_schema(value, f"{path}[]")
        elif key == "required":
            out["required"] = list(value)
        elif key in _KEYMAP:
            if key == "description" and "description" in out:
                continue
            out[_KEYMAP[key]] = value
        else:
            raise UnsupportedSchema(f"unsupported keyword {key!r} at {path}")
    return out


def to_function_declarations(specs: list[dict[str, Any]]) -> list[types.FunctionDeclaration]:
    decls = []
    for spec in specs:
        params = convert_schema(spec["parameters"], spec["name"])
        if not params.get("properties"):
            params = None  # zero-arg tools (get_usual_order)
        decls.append(
            types.FunctionDeclaration(
                name=spec["name"],
                description=spec["description"],
                parameters=types.Schema.model_validate(params) if params else None,
                behavior=types.Behavior.BLOCKING if spec.get("x-blocking") else types.Behavior.NON_BLOCKING,
            )
        )
    return decls
