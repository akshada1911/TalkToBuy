"""Structured JSON logging with secret redaction (T026, FR-037, FR-040).

Audio and video bytes are never logged. Any 4–8 digit run (OTP/PIN-like) in string values is
masked before a log line is written.
"""

import logging
import re
from typing import Any

import structlog

_DIGITS = re.compile(r"(?<!\d)[0-9०-९]{4,8}(?!\d)")


def redact_text(text: str) -> str:
    return _DIGITS.sub(lambda m: "•" * len(m.group()), text)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return f"<{len(value)} bytes>"
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_redact(v) for v in value]
    return value


def redaction_processor(_logger: Any, _method: str, event_dict: dict) -> dict:
    return {k: _redact(v) for k, v in event_dict.items()}


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            redaction_processor,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def get_logger(name: str = "session_server") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
