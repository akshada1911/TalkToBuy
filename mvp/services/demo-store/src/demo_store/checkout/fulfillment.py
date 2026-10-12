"""Fulfillment extension (T063): one free delivery method whose options are delivery slots.

Options are today's remaining slots (a slot is open until 60 minutes before it starts) followed
by tomorrow's. `"earliest"` resolves to the first open slot. The option list is snapshotted on
the checkout whenever it is created or replaced, so the canonical (signed) checkout does not
change while the shopper approves it.
"""

from datetime import datetime, timedelta, timezone

from demo_store.config import get_settings

IST = timezone(timedelta(hours=5, minutes=30))
LEAD_TIME = timedelta(minutes=60)
EARLIEST = "earliest"
METHOD_ID = "m_delivery"
GROUP_ID = "g1"

# (start hour, Hindi label, English label); each slot lasts one hour.
SLOTS = [
    (10, "सुबह 10 से 11 बजे", "10–11 am"),
    (12, "दोपहर 12 से 1 बजे", "12–1 pm"),
    (16, "शाम 4 से 5 बजे", "4–5 pm"),
    (18, "शाम 6 से 7 बजे", "6–7 pm"),
    (20, "रात 8 से 9 बजे", "8–9 pm"),
]


def now() -> datetime:
    clock = get_settings().demo_clock
    if clock:
        fixed = datetime.fromisoformat(clock)
        return fixed if fixed.tzinfo else fixed.replace(tzinfo=IST)
    return datetime.now(IST)


def slot_options(at: datetime | None = None) -> list[dict]:
    """Open slots as `DeliverySlot` dicts: `{id, label_hi, label_en, start, end}`."""
    at = (at or now()).astimezone(IST)
    options = []
    for day in (0, 1):
        date = (at + timedelta(days=day)).date()
        for hour, label_hi, label_en in SLOTS:
            start = datetime(date.year, date.month, date.day, hour, tzinfo=IST)
            if start - LEAD_TIME < at:
                continue
            options.append({
                "id": f"slot-{hour:02d}00" if day == 0 else f"slot-d1-{hour:02d}00",
                "label_hi": label_hi if day == 0 else f"कल {label_hi}",
                "label_en": label_en if day == 0 else f"tomorrow {label_en}",
                "start": start.isoformat(),
                "end": (start + timedelta(hours=1)).isoformat(),
            })
    return options


def resolve(option_id: str | None, options: list[dict]) -> dict | None:
    """The selected slot, `"earliest"` → first open slot. Raises KeyError for unknown ids."""
    if option_id is None:
        return None
    if option_id == EARLIEST:
        if not options:
            raise KeyError(option_id)
        return options[0]
    for option in options:
        if option["id"] == option_id:
            return option
    raise KeyError(option_id)


def to_ucp(options: list[dict], selected_id: str | None, line_item_ids: list[str]) -> dict:
    return {
        "methods": [{
            "id": METHOD_ID,
            "type": "shipping",
            "line_item_ids": line_item_ids,
            "groups": [{
                "id": GROUP_ID,
                "selected_option_id": selected_id,
                "options": [
                    {
                        "id": o["id"],
                        "title": o["label_en"],
                        "metadata": {k: o[k] for k in ("label_hi", "label_en", "start", "end")},
                        "totals": [{"type": "total", "amount": 0}],
                    }
                    for o in options
                ],
            }],
        }]
    }
