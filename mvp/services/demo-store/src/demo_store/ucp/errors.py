#   Copyright 2026 UCP Authors
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
#   Adapted for TalkToBuy from Universal-Commerce-Protocol/samples
#   rest/python/server/{exceptions,enums}.py @ cdb291c (see UPSTREAM.md):
#   merged into one module, restyled, AP2 mandate errors added.

"""UCP error envelope, error classes and status enums."""

import enum

from pydantic import BaseModel

UCP_VERSION = "2026-08-25"


class CheckoutStatus(enum.StrEnum):
    INCOMPLETE = "incomplete"
    REQUIRES_ESCALATION = "requires_escalation"
    READY_FOR_COMPLETE = "ready_for_complete"
    COMPLETE_IN_PROGRESS = "complete_in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"


TERMINAL_STATUSES = {CheckoutStatus.COMPLETED, CheckoutStatus.CANCELED}


class MessageType(enum.StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorSeverity(enum.StrEnum):
    RECOVERABLE = "recoverable"
    REQUIRES_BUYER_INPUT = "requires_buyer_input"
    REQUIRES_BUYER_REVIEW = "requires_buyer_review"
    UNRECOVERABLE = "unrecoverable"


class UcpMessageError(BaseModel):
    type: MessageType = MessageType.ERROR
    code: str
    content: str
    severity: ErrorSeverity


class UcpErrorResponse(BaseModel):
    ucp: dict
    messages: list[UcpMessageError]


class UcpError(Exception):
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        severity: ErrorSeverity = ErrorSeverity.UNRECOVERABLE,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.severity = severity
        super().__init__(message)

    def to_response(self) -> UcpErrorResponse:
        return UcpErrorResponse(
            ucp={"version": UCP_VERSION, "status": "error"},
            messages=[
                UcpMessageError(code=self.code, content=self.message, severity=self.severity)
            ],
        )


class ResourceNotFoundError(UcpError):
    def __init__(self, message: str):
        super().__init__(message, code="RESOURCE_NOT_FOUND", status_code=404)


class IdempotencyConflictError(UcpError):
    def __init__(self, message: str):
        super().__init__(message, code="IDEMPOTENCY_CONFLICT", status_code=409)


class CheckoutNotModifiableError(UcpError):
    def __init__(self, message: str):
        super().__init__(message, code="CHECKOUT_NOT_MODIFIABLE", status_code=409)


class OutOfStockError(UcpError):
    def __init__(self, message: str):
        super().__init__(message, code="OUT_OF_STOCK", status_code=400)


class InvalidRequestError(UcpError):
    def __init__(self, message: str, code: str = "INVALID_REQUEST"):
        super().__init__(message, code=code, status_code=400)


class MandateError(UcpError):
    """AP2 mandate verification failure (codes from the AP2 extension spec)."""

    CODES = {
        "mandate_required",
        "mandate_invalid_signature",
        "mandate_expired",
        "mandate_scope_mismatch",
        "merchant_authorization_invalid",
    }

    def __init__(self, code: str, message: str):
        assert code in self.CODES, code
        super().__init__(
            message, code=code, status_code=402, severity=ErrorSeverity.REQUIRES_BUYER_INPUT
        )
