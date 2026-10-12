"""GET /agent-profile.json: the UCP-Agent profile this session server presents to stores."""

from fastapi import APIRouter, Depends

from session_server.config import Settings, get_settings

router = APIRouter()


@router.get("/agent-profile.json")
async def agent_profile(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "name": "TalkToBuy shopping assistant",
        "version": "0.1.0",
        "ucp": {"version": "2026-08-25"},
        "capabilities": ["dev.ucp.shopping.checkout", "dev.ucp.shopping.catalog.search",
                         "dev.ucp.shopping.catalog.lookup", "dev.ucp.common.payment.ap2_mandate"],
        "contact": settings.session_server_url,
        "human_present": True,
    }
