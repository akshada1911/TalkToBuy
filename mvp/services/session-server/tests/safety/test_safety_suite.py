"""T085: the safety suite. For every warning-sign prompt, zero products are shown, added or bought
and the model is told to suggest a doctor; benign prompts never trigger a hold (SC-006).

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
async def test_warning_sign_stops_the_sale(case) -> None:
    rt = make_runtime()
    await add_to_cart(rt, {"product_id": "p-0112", "qty": 1})  # an existing cart must not be bought
    cards_before = len(rt.ui.of("cards"))
    verdict = await detector.evaluate(case["text"], classifier=None)
    assert verdict.warning_sign, case["text"]
    await hold.apply(rt, verdict)

    router = ToolRouter(rt, HANDLERS)
    for cid, name, args in [
        ("s", "search_catalog", {"query": "pain spray"}),
        ("p", "show_products", {"ids": ["p-0112"]}),
        ("a", "add_to_cart", {"product_id": "p-0007", "qty": 1}),
        ("c", "start_checkout", {"delivery_slot": "earliest"}),
    ]:
        await router.handle(ToolCall(cid, name, args))
        assert rt.live.response_for(cid)["status"] == "refused", name

    assert len(rt.ui.of("cards")) == cards_before  # zero products shown
    assert rt.commerce.carts[rt.session.cart_ref]["lines"] == {"p-0112": 1}  # nothing added
    note = " ".join(text for role, text in rt.live.texts if role == "system_note")
    assert "doctor" in note and "Do NOT show" in note
    assert rt.ui.of("state")[-1]["safety_hold"] is True


@pytest.mark.parametrize("case", NON_SIGNS, ids=lambda c: c["text"][:40])
async def test_benign_and_medicine_requests_do_not_trigger_hold(case) -> None:
    verdict = await detector.evaluate(case["text"], classifier=None)
    assert not verdict.warning_sign, case["text"]


async def test_hold_clears_only_after_doctor_suggestion_and_new_non_health_request() -> None:
    rt = make_runtime()
    await hold.apply(rt, await detector.evaluate(SIGNS[0]["text"], None))
    await hold.maybe_clear(rt, "atta chahiye")
    assert rt.session.safety_hold  # doctor not yet suggested
    hold.on_assistant_text(rt, "मुझे लगता है आपको जल्दी डॉक्टर को दिखाना चाहिए।")
    await hold.maybe_clear(rt, "haan")  # answer to the family question, not a new request
    assert rt.session.safety_hold
    await hold.maybe_clear(rt, "mera pair abhi bhi dard kar raha hai")  # still health
    assert rt.session.safety_hold
    await hold.maybe_clear(rt, "theek hai, ab do litre doodh de do")
    assert not rt.session.safety_hold


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
