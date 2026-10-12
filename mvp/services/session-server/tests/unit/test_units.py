"""T041: local units and pack planning must be exact (FR-012, FR-025, SC-002)."""

import pytest

from session_server.units import Amount, PackOption, parse, plan


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("paav kilo", Amount(250, "g")),
        ("पाव किलो", Amount(250, "g")),
        ("pav kg", Amount(250, "g")),
        ("aadha kilo", Amount(500, "g")),
        ("आधा किलो", Amount(500, "g")),
        ("sava kilo", Amount(1250, "g")),
        ("dedh kilo", Amount(1500, "g")),
        ("डेढ़ किलो", Amount(1500, "g")),
        ("dhai kilo", Amount(2500, "g")),
        ("paune do kilo", Amount(1750, "g")),
        ("aadha litre", Amount(500, "ml")),
        ("do litre", Amount(2000, "ml")),
        ("दो लीटर", Amount(2000, "ml")),
        ("two litres", Amount(2000, "ml")),
        ("2 litre", Amount(2000, "ml")),
        ("५०० ग्राम", Amount(500, "g")),
        ("500 gm", Amount(500, "g")),
        ("darjan", Amount(12, "piece")),
        ("ek darjan", Amount(12, "piece")),
        ("do packet", Amount(2, "pack")),
        ("ek", Amount(1, "pack")),
        ("teen", Amount(3, "pack")),
    ],
)
def test_parse(phrase: str, expected: Amount) -> None:
    assert parse(phrase) == expected


def test_parse_unknown_returns_none() -> None:
    assert parse("thoda sa") is None
    assert parse("") is None


MILK = [PackOption("p-0112", 1000, "ml"), PackOption("p-0113", 500, "ml")]
TOMATO = [PackOption("p-0007", 250, "g"), PackOption("p-0008", 1000, "g")]


def test_do_litre_is_two_one_litre_packs() -> None:
    assert plan(Amount(2000, "ml"), MILK)[0] == ("p-0112", 2)


def test_paav_kilo_tomato_is_one_250g_pack() -> None:
    assert plan(Amount(250, "g"), TOMATO)[0] == ("p-0007", 1)


def test_fewest_packs_at_least_amount() -> None:
    # 1.5 L: 2×1 L (2 packs) beats 3×500 ml (3 packs).
    assert plan(Amount(1500, "ml"), MILK)[0] == ("p-0112", 2)


def test_below_smallest_pack_chooses_smallest_pack() -> None:
    cocoa = [PackOption("p-2051", 50, "g"), PackOption("p-2052", 200, "g")]
    assert plan(Amount(20, "g"), cocoa)[0] == ("p-2051", 1)


def test_pack_count_applies_to_each_option() -> None:
    biscuits = [PackOption("p-0300", 1, "piece")]
    assert plan(Amount(2, "pack"), biscuits)[0] == ("p-0300", 2)


def test_incompatible_units_are_skipped() -> None:
    assert plan(Amount(500, "g"), MILK) == []
