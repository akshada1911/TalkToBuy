"""TranslatePort via a fast Gemini text model (T053, R10). Display-only; never fed back to Live."""

from google import genai
from google.genai import types

from session_server.config import Settings
from session_server.logging import get_logger

log = get_logger(__name__)

PROMPT = (
    "Translate this Hindi line from a grocery shopping conversation into plain, natural English. "
    "Keep product names, numbers and ₹ amounts exactly. Reply with the translation only.\n\n{text}"
)


class FlashTranslate:
    def __init__(self, settings: Settings):
        self.model = settings.flash_model
        self.client = genai.Client(
            vertexai=True, project=settings.require_gcp(), location=settings.gcp_location
        )

    async def to_english(self, text_hi: str) -> str | None:
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model,
                contents=PROMPT.format(text=text_hi),
                config=types.GenerateContentConfig(
                    temperature=0, max_output_tokens=400,
                    # 2.5 Flash "thinks" by default and that eats the output budget (captions were cut off).
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            return (resp.text or "").strip() or None
        except Exception:
            log.warning("translate_failed")
            return None
