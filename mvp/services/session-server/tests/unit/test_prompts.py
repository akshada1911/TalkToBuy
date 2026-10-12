"""T033: the system instruction assembles fully, with gendered address rules and pace block."""

from session_server.core.prompts import build_system_instruction
from session_server.models.domain import Shopper


def _shopper(form: str) -> Shopper:
    return Shopper(id="u", display_name="Ghanshyam ji", language="hi", address_form=form)


def test_all_placeholders_are_filled() -> None:
    text = build_system_instruction(_shopper("respectful_male"), "guided")
    assert "{" not in text and "}" not in text
    assert "Ghanshyam ji" in text and "GUIDED" in text
    for must in ("OTP", "`readback`", "notify_family", "amount_phrase", "goal_id", "camera"):
        assert must in text


def test_address_form_and_pace_change_the_prompt() -> None:
    male = build_system_instruction(_shopper("respectful_male"), "quick")
    female = build_system_instruction(_shopper("respectful_female"), "quick")
    assert "masculine forms for them" in male and "feminine forms for them" in female
    assert "QUICK" in male


def test_prompt_never_asks_age() -> None:
    text = build_system_instruction(_shopper("neutral"), "guided").lower()
    assert "never ask their age" in text


def test_english_session_speaks_english_without_hindi_grammar_rules() -> None:
    en = build_system_instruction(_shopper("respectful_male"), "guided", language="en")
    hi = build_system_instruction(_shopper("respectful_male"), "guided", language="hi")
    assert "Speak only simple, polite Indian English" in en and "Shall we go step by step" in en
    assert "masculine forms for them" not in en and "{" not in en
    assert "Speak only simple, respectful, natural Hindi" in hi and "हम एक-एक करके चलें" in hi
