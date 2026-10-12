"""Per-session cost estimate (T107, FR-043). Rates from research R11; reconcile with billing."""

from session_server.models.domain import Usage

AUDIO_IN_USD_PER_MIN = 0.005   # Google developer post, gemini-3.8-live
AUDIO_OUT_USD_PER_MIN = 0.018  # same source (marked with an asterisk there)
VIDEO_IN_USD_PER_M_TOKENS = 1.00
TEXT_OUT_USD_PER_M_TOKENS = 4.50
AVATAR_USD_PER_MIN: float | None = None  # unpublished; logged as unknown


def estimate_usd(usage: Usage) -> float:
    cost = usage.audio_in_s / 60 * AUDIO_IN_USD_PER_MIN + usage.audio_out_s / 60 * AUDIO_OUT_USD_PER_MIN
    return round(cost, 5)
