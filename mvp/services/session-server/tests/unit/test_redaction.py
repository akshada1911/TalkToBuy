"""T102: OTP/PIN-like digits are masked in logs; audio bytes are never logged (FR-037, FR-040)."""

from session_server.logging import redact_text, redaction_processor


def test_otp_and_pin_are_masked() -> None:
    assert "123456" not in redact_text("मेरा OTP 123456 है")
    assert "4321" not in redact_text("PIN 4321")
    assert "१२३४५६" not in redact_text("ओटीपी १२३४५६")


def test_short_numbers_and_prices_survive() -> None:
    assert redact_text("₹1016 total, 2 litre") == "₹•••• total, 2 litre"
    assert redact_text("2 litre doodh, 250 g") == "2 litre doodh, 250 g"


def test_processor_redacts_nested_values_and_hides_bytes() -> None:
    out = redaction_processor(None, "info", {"event": "x", "text": "pin 9876", "audio": b"\x00" * 64,
                                             "nested": {"t": ["otp 55555"]}})
    assert "9876" not in out["text"] and out["audio"] == "<64 bytes>"
    assert "55555" not in out["nested"]["t"][0]
