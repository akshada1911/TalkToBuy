"""T085: the safety suite. For every warning-sign prompt the model is told to suggest a doctor and
offer the family alert, and shopping keeps working; benign prompts never trigger it (SC-006).

Runs offline (lexicon + guards). Marked `safety`; deploy scripts refuse to deploy if it fails.
"""

from pathlib import Path

import pytest
import yaml

from session_server.core.safety import detector, hold
from session_server.core.tool_router import ToolRouter
from session_server.core.tools import HANDLERS
from session_server.core.tools.cart import add_to_cart
from session_server.ports.live import ToolCall
from session_server.testing.fakes import make_runtime

pytestmark = pytest.mark.safety

PROMPTS = yaml.safe_load((Path(__file__).parent / "prompts.yaml").read_text(encoding="utf-8"))
SIGNS = [p for p in PROMPTS if p["warning_sign"]]
NON_SIGNS = [p for p in PROMPTS if not p["warning_sign"]]


def test_suite_has_at_least_20_prompts() -> None:
    assert len(PROMPTS) >= 20 and len(SIGNS) >= 10


@pytest.mark.parametrize("case", SIGNS, ids=lambda c: c["text"][:40])
async def test_warning_sign_suggests_a_doctor_but_does_not_stop_shopping(case) -> None:
    rt = make_runtime()
    await add_to_cart(rt, {"product_id": "p-0112", "qty": 1})
    verdict = await detector.evaluate(case["text"], classifier=None)
    assert verdict.warning_sign, case["text"]
    await hold.apply(rt, verdict)

    router = ToolRouter(rt, HANDLERS)
    for cid, name, args in [
        ("s", "search_catalog", {"query": "milk"}),
        ("p", "show_products", {"ids": ["p-0112"]}),
        ("a", "add_to_cart", {"product_id": "p-0007", "qty": 1}),
        ("c", "start_checkout", {"delivery_slot": "earliest", "address_id": "addr-home"}),
    ]:
        await router.handle(ToolCall(cid, name, args))
        assert rt.live.response_for(cid)["status"] == "ok", name

    assert rt.commerce.carts[rt.session.cart_ref]["lines"] == {"p-0112": 1, "p-0007": 1}  # added
    note = " ".join(text for role, text in rt.live.texts if role == "system_note")
    assert "doctor" in note and "NOT paused" in note and "Do NOT show" not in note
    assert not rt.session.safety_hold  # no "shopping paused" banner


@pytest.mark.parametrize("case", NON_SIGNS, ids=lambda c: c["text"][:40])
async def test_benign_and_medicine_requests_do_not_trigger_hold(case) -> None:
    verdict = await detector.evaluate(case["text"], classifier=None)
    assert not verdict.warning_sign, case["text"]


async def test_doctor_note_and_family_offer_are_given_once_per_session() -> None:
    rt = make_runtime()
    verdict = await detector.evaluate(SIGNS[0]["text"], None)
    await hold.apply(rt, verdict)
    await hold.apply(rt, verdict)
    notes = [t for role, t in rt.live.texts if role == "system_note"]
    assert len(notes) == 1 and "doctor" in notes[0]


async def test_classifier_can_add_but_never_clear_a_sign() -> None:
    from session_server.ports.classifier import SafetyVerdict

    class SaysNo:
        async def classify(self, text):
            return SafetyVerdict(False, None)

    class SaysYes:
        async def classify(self, text):
            return SafetyVerdict(True, "severe_pain")

    assert (await detector.evaluate(SIGNS[0]["text"], SaysNo())).warning_sign
    assert (await detector.evaluate("mere ghutne mein dard hai", SaysYes())).warning_sign
