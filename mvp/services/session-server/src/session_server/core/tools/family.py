"""notify_family (T090): in-app only, only after the shopper agreed (FR-033, FR-036)."""

from typing import Any

from session_server.core import confirm
from session_server.core.runtime import Runtime
from session_server.core.tool_router import ToolError
from session_server.models.messages import FamilyNotifiedMsg


async def notify_family(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    contact = await rt.commerce.family(rt.session.shopper_id)
    if contact is None:
        raise ToolError("No family member is linked in the app.", retryable=False)
    name = await rt.commerce.notify_family(rt.session.shopper_id, args["message"][:280])
    confirm.consume(rt)
    await rt.ui.send_json(FamilyNotifiedMsg(type="family_notified", contact_name=name))
    return {"delivered": True, "contact_name": name, "channel": "in_app"}
