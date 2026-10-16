"""Assemble the provider-neutral system instruction from mvp/prompts/*.md (T033)."""

import re
from pathlib import Path

from session_server.config import MVP_ROOT
from session_server.models.domain import Shopper

PROMPTS = MVP_ROOT / "prompts"

LANGUAGE_RULES = {
    "hi": "Speak only simple, respectful, natural Hindi (Hindustani, not Sanskritised) in short "
          "sentences, even if the shopper mixes in English words.",
    "en": "Speak only simple, polite Indian English in short sentences. The Hindi phrases quoted in "
          "these instructions show the meaning and tone; say them in English. The shopper may use "
          "Hindi words for items (doodh, atta, paav kilo) and you must understand them.",
}

OPENING_QUESTION = {
    "hi": '"नमस्ते {name}! आज क्या मँगवाना है?"',
    "en": '"Namaste {name}! What would you like today?"',
}

OPENING_LIVE = (
    'Opening: greet briefly using their name ("नमस्ते {display_name}।" or "Hello {display_name}"), then ask once '
    "{opening_question} Never ask about pace (step by step or quickly) and never ask their age."
)
OPENING_DONE = (
    'Opening: the app has ALREADY greeted the shopper aloud by name and asked what they would like ("{greeting}"). '
    "Do NOT greet again and do NOT ask it again. Wait for the shopper to speak, then help with what they ask. "
    "Never ask about pace (step by step or quickly) and never ask their age."
)

ENGLISH_ADDRESS = (
    "Address them respectfully as '{name}'. In English, use polite forms (please, would you like)."
)

ADDRESS_RULES = {
    "respectful_male": (
        "Address them respectfully as '{name}' with 'आप'. They are male: use masculine forms for "
        "them (e.g. 'आप चाहेंगे', 'आपने लिया था'). You (the shopkeeper) speak in masculine first "
        "person ('मैं देखता हूँ')."
    ),
    "respectful_female": (
        "Address them respectfully as '{name}' with 'आप'. They are female: use feminine forms for "
        "them (e.g. 'आप चाहेंगी', 'आपने ली थी'). You speak in masculine first person."
    ),
    "neutral": (
        "Address them respectfully as '{name}' with 'आप', and prefer constructions that avoid "
        "gendered verb forms for them."
    ),
}


def _read(name: str, root: Path) -> str:
    text = (root / name).read_text(encoding="utf-8")
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def opening_text(shopper: Shopper, language: str = "hi") -> str:
    """The greeting plus the opening question, as it is spoken."""
    return OPENING_QUESTION[language].format(name=shopper.display_name).strip('"')


def opening_note(shopper: Shopper, language: str = "hi") -> str:
    """The model only speaks when spoken to, so the server asks it to open the conversation."""
    greeting = f"Hello {shopper.display_name}" if language == "en" else f"नमस्ते {shopper.display_name}"
    return (
        "[SERVER NOTE] The session has just started and the shopper has not spoken yet. Speak first: "
        f'greet them by name in one short sentence ("{greeting}!"), then ask what they would like, once. '
        "Do not wait for them to say something first."
    )


def cart_note(lines: list[tuple[str, str, int]], total: int) -> str:
    """Tell the model about items the shopper already put in the cart by tapping (id, name, qty)."""
    items = "; ".join(f"{qty} × {name} ({pid})" for pid, name, qty in lines)
    return (
        "The shopper has already put these in the cart on screen, so do not add them again and do not "
        f"announce them unless it helps: {items}. Cart total so far: ₹{total}. The cart can also change on "
        "screen while you talk; the cart in a tool result is always the current one."
    )


def build_system_instruction(shopper: Shopper, pace: str, root: Path = PROMPTS, language: str = "hi",
                             cart: str | None = None, greeted: str | None = None) -> str:
    pace_file = "pace_guided.md" if pace == "guided" else "pace_quick.md"
    template = _read("system.hi.md", root)
    name = shopper.display_name
    address = ENGLISH_ADDRESS if language == "en" else ADDRESS_RULES[shopper.address_form]
    parts = {
        "language_rules": LANGUAGE_RULES[language],
        "opening": (OPENING_DONE.format(greeting=greeted) if greeted else
                    OPENING_LIVE.format(display_name=name, opening_question=OPENING_QUESTION[language].format(name=name))),
        "display_name": name,
        "address_rules": address.format(name=name),
        "pace_block": _read(pace_file, root),
        "goal_planning": _read("goal_planning.md", root),
        "camera": _read("camera.md", root),
        "problem_help": _read("problem_help.md", root),
        "safety_rules": _read("safety_rules.md", root),
    }
    for key, value in parts.items():
        template = template.replace("{" + key + "}", value)
    return f"{template}\n\n{cart}" if cart else template
