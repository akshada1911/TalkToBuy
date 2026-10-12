"""Tool router (T031): validate → guard → execute → respond, with no dead air.

Handlers push UI messages (cards, cart) themselves *before* returning, so a card is on screen
before the model hears the result (SC-007). A handler may return `Deferred` to keep the call
open (non-blocking) and respond later — used by confirm_checkout while the shopper approves
in the payment step (research R2).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from session_server.config import MVP_ROOT
from session_server.core.cart import duplicate_add
from session_server.core.guards import GUARDS, Guard
from session_server.core.runtime import Runtime
from session_server.logging import get_logger
from session_server.models.messages import WorkingMsg
from session_server.ports.live import Scheduling, ToolCall

log = get_logger(__name__)

TOOLS_SCHEMA = MVP_ROOT / "contracts" / "tools.schema.json"
HOLDING_AFTER_S = 2.0


class ToolError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, status: str = "error"):
        self.message = message
        self.retryable = retryable
        self.status = status
        super().__init__(message)


@dataclass
class Deferred:
    awaitable: Awaitable[dict[str, Any]]
    scheduling: Scheduling = "INTERRUPT"


Handler = Callable[[Runtime, dict[str, Any]], Awaitable[dict[str, Any] | Deferred]]


def load_tool_specs(path: Path = TOOLS_SCHEMA) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["tools"]


class ToolRouter:
    def __init__(
        self,
        rt: Runtime,
        handlers: dict[str, Handler],
        specs: list[dict[str, Any]] | None = None,
        guards: list[Guard] | None = None,
    ):
        self.rt = rt
        self.handlers = handlers
        self.specs = {s["name"]: s for s in (specs or load_tool_specs())}
        self.validators = {n: Draft202012Validator(s["parameters"]) for n, s in self.specs.items()}
        self.guards = GUARDS if guards is None else guards
        self.deferred: dict[str, asyncio.Task] = {}

    async def handle(self, call: ToolCall) -> None:
        response, scheduling = await self._run(call)
        if response is not None:
            await self.rt.live.send_tool_response(call.id, call.name, response, scheduling)

    async def _run(self, call: ToolCall) -> tuple[dict[str, Any] | None, Scheduling]:
        name, args = call.name, dict(call.args or {})
        if name not in self.handlers or name not in self.specs:
            return _error(f"Unknown tool {name}", retryable=False), "WHEN_IDLE"
        errors = sorted(self.validators[name].iter_errors(args), key=str)
        if errors:
            return _error(f"Invalid arguments: {errors[0].message}"), "WHEN_IDLE"
        if name == "add_to_cart" and not self.rt.session.safety_hold:
            duplicate = duplicate_add(self.rt, args)  # a pure repeat adds nothing: skip approval
            if duplicate is not None:
                return {"status": "ok", "retryable": False, "result": duplicate}, "WHEN_IDLE"
        for guard in self.guards:
            refusal = guard(self.rt, name, args)
            if refusal is not None:
                log.info("tool_refused", tool=name, reason=refusal.message)
                return {"status": "refused", "retryable": refusal.retryable,
                        "message": refusal.message}, "WHEN_IDLE"

        holding = self.rt.spawn(self._holding(name))
        try:
            result = await self.handlers[name](self.rt, args)
        except ToolError as exc:
            return {"status": exc.status, "retryable": exc.retryable, "message": exc.message}, "WHEN_IDLE"
        except Exception as exc:  # never leave the model without a response
            log.exception("tool_failed", tool=name)
            return _error(f"{name} failed: {exc}"), "WHEN_IDLE"
        finally:
            shown = holding.done() and not holding.cancelled()
            holding.cancel()
            if shown:
                await self.rt.ui.send_json(WorkingMsg(type="working", on=False))

        if isinstance(result, Deferred):
            self.deferred[call.id] = self.rt.spawn(self._finish_deferred(call, result))
            return None, result.scheduling
        return {"status": "ok", "retryable": False, "result": result}, "WHEN_IDLE"

    async def _finish_deferred(self, call: ToolCall, deferred: Deferred) -> None:
        try:
            result = await deferred.awaitable
            response = {"status": "ok", "retryable": False, "result": result}
        except ToolError as exc:
            response = {"status": exc.status, "retryable": exc.retryable, "message": exc.message}
        except Exception as exc:
            log.exception("deferred_tool_failed", tool=call.name)
            response = _error(f"{call.name} failed: {exc}")
        finally:
            self.deferred.pop(call.id, None)
        await self.rt.live.send_tool_response(call.id, call.name, response, deferred.scheduling)

    async def _holding(self, name: str) -> None:
        await asyncio.sleep(HOLDING_AFTER_S)
        await self.rt.ui.send_json(
            WorkingMsg(type="working", on=True, label_hi="एक पल…", label_en="One moment…")
        )


def _error(message: str, retryable: bool = True) -> dict[str, Any]:
    return {"status": "error", "retryable": retryable, "message": message}
