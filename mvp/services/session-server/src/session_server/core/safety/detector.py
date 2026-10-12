"""Warning-sign detector (T088): lexicon first, classifier second opinion (R8).

The lexicon runs on every partial and final shopper transcript, so the hold is set before the
model can call a product tool. The classifier (if configured) runs on final text that has a
lexicon hit or a health word; it can add a sign the lexicon missed, but it can never clear a
lexicon hit (fail safe).
"""

from session_server.core.safety.lexicon import (
    BENIGN_FALL,
    FALL,
    HEALTH_WORDS,
    SELF_OR_BODY,
    SIGNS,
)
from session_server.ports.classifier import ClassifierPort, SafetyVerdict


def lexicon_verdict(text: str) -> SafetyVerdict:
    if FALL.search(text) and SELF_OR_BODY.search(text) and not BENIGN_FALL.search(text):
        return SafetyVerdict(True, "recent_fall")
    for sign, pattern in SIGNS.items():
        if pattern.search(text):
            return SafetyVerdict(True, sign)
    return SafetyVerdict(False, None)


def mentions_health(text: str) -> bool:
    return bool(HEALTH_WORDS.search(text))


async def evaluate(text: str, classifier: ClassifierPort | None) -> SafetyVerdict:
    lexical = lexicon_verdict(text)
    if lexical.warning_sign:
        return lexical
    if classifier is not None and mentions_health(text):
        verdict = await classifier.classify(text)
        if verdict is not None and verdict.warning_sign:
            return verdict
    return lexical
