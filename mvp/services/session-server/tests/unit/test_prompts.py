"""T033: the system instruction assembles fully, with gendered address rules and pace block."""

from session_server.core.prompts import build_system_instruction
from session_server.models.domain import Shopper


def _shopper(form: str) -> Shopper:
    return Shopper(id="u", display_name="Vaibhav", language="hi", address_form=form)


def test_all_placeholders_are_filled() -> None:
    text = build_system_instruction(_shopper("respectful_male"), "guided")
    assert "{" not in text and "}" not in text
    assert "Vaibhav" in text and "GUIDED" in text
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
    assert "Speak only simple, polite Indian English" in en and "What would you like today" in en
    assert "masculine forms for them" not in en and "{" not in en
    assert "Speak only simple, respectful, natural Hindi" in hi and "आज क्या मँगवाना है" in hi


def test_opening_note_asks_the_model_to_greet_first_by_name() -> None:
    from session_server.core.prompts import opening_note

    assert "नमस्ते Vaibhav" in opening_note(_shopper("neutral"), "hi")
    assert "Hello Vaibhav" in opening_note(_shopper("neutral"), "en")


def test_natural_yes_answers_confirm_a_proposed_list() -> None:
    from session_server.core.confirm import is_affirmative

    for said in ("चलेगा", "हाँ चलेगा", "ठीक है", "go ahead", "chalega"):
        assert is_affirmative(said), said
    assert not is_affirmative("नहीं चलेगा")


def test_a_goal_item_cannot_ask_for_dozens_of_packs() -> None:
    from session_server.core.tool_router import load_tool_specs
    from jsonschema import Draft202012Validator

    spec = next(s for s in load_tool_specs() if s["name"] == "show_products")
    item = {"need": "rice", "product_id": "p-1", "qty": 50, "struck": False}
    errors = list(Draft202012Validator(spec["parameters"]).iter_errors(
        {"goal_list": {"goal_text": "veg biryani for 50", "items": [item]}}))
    assert errors and "50" in errors[0].message
