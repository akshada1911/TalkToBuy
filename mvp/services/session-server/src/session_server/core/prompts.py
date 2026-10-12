"""Assemble the provider-neutral system instruction from mvp/prompts/*.md (T033)."""

import re
from pathlib import Path

from session_server.config import MVP_ROOT
from session_server.models.domain import Shopper

PROMPTS = MVP_ROOT / "prompts"

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


def build_system_instruction(shopper: Shopper, pace: str, root: Path = PROMPTS) -> str:
    pace_file = "pace_guided.md" if pace == "guided" else "pace_quick.md"
    template = _read("system.hi.md", root)
    parts = {
        "display_name": shopper.display_name,
        "address_rules": ADDRESS_RULES[shopper.address_form].format(name=shopper.display_name),
        "pace_block": _read(pace_file, root),
        "goal_planning": _read("goal_planning.md", root),
        "camera": _read("camera.md", root),
        "problem_help": _read("problem_help.md", root),
        "safety_rules": _read("safety_rules.md", root),
    }
    for key, value in parts.items():
        template = template.replace("{" + key + "}", value)
    return template
