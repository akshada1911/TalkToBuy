"""set_pace tool (T094)."""

from typing import Any

from session_server.core import pace
from session_server.core.runtime import Runtime


async def set_pace(rt: Runtime, args: dict[str, Any]) -> dict[str, Any]:
    await pace.set_pace(rt, args["mode"], args.get("reason", "shopper_asked"))
    return {"pace": rt.session.pace}
