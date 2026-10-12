"""ClassifierPort via a fast Gemini text model with structured output (T087, R8)."""

import json

from google import genai
from google.genai import types

from session_server.config import Settings
from session_server.logging import get_logger
from session_server.ports.classifier import SafetyVerdict

log = get_logger(__name__)

PROMPT = """You screen messages to a grocery shopping assistant for medical WARNING SIGNS.
Warning signs are only: a recent fall; numbness or weakness; sudden or severe pain; fever;
bladder or urination problems. Ordinary aches with no warning sign, food talk, or things that
fell (not a person) are NOT warning signs.
Message (Hindi/Hinglish/English): {text}"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "warning_sign": {"type": "BOOLEAN"},
        "sign": {
            "type": "STRING",
            "nullable": True,
            "enum": ["recent_fall", "numbness_or_weakness", "severe_pain", "fever", "bladder"],
        },
    },
    "required": ["warning_sign"],
}


class FlashClassifier:
    def __init__(self, settings: Settings):
        self.model = settings.flash_model
        self.client = genai.Client(
            vertexai=True, project=settings.require_gcp(), location=settings.gcp_location
        )

    async def classify(self, text: str) -> SafetyVerdict | None:
        try:
            resp = await self.client.aio.models.generate_content(
                model=self.model,
                contents=PROMPT.format(text=text),
                config=types.GenerateContentConfig(
                    temperature=0, response_mime_type="application/json", response_schema=SCHEMA
                ),
            )
            data = json.loads(resp.text or "{}")
            return SafetyVerdict(bool(data.get("warning_sign")), data.get("sign"))
        except Exception:
            log.warning("classifier_failed")
            return None
