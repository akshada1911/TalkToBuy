"""Lexicon for spoken quantities in Hindi, Hinglish and English (research R7)."""

NUMBERS: dict[str, float] = {
    # Hinglish
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6,
    "chhah": 6, "che": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    # Devanagari
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10,
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10,
}

FRACTIONS: dict[str, float] = {
    "paav": 0.25, "pav": 0.25, "pau": 0.25, "pao": 0.25, "पाव": 0.25, "quarter": 0.25,
    "aadha": 0.5, "adha": 0.5, "aadhi": 0.5, "adhi": 0.5, "आधा": 0.5, "आधी": 0.5, "half": 0.5,
    "dedh": 1.5, "derh": 1.5, "dedhh": 1.5, "डेढ़": 1.5, "डेढ": 1.5,
    "dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5,
}

# Modifiers applied to the following number: sava X = X + 1/4, paune X = X − 1/4.
SAVA = {"sava", "sawa", "सवा"}
PAUNE = {"paune", "pone", "paone", "पौने"}

# word → (multiplier into base unit, base unit). "pack" means a count of packs.
UNITS: dict[str, tuple[float, str]] = {
    **dict.fromkeys(["kilo", "kg", "kgs", "kilogram", "kilograms", "किलो", "केजी"], (1000, "g")),
    **dict.fromkeys(["gram", "grams", "gm", "gms", "g", "ग्राम"], (1, "g")),
    **dict.fromkeys(
        ["litre", "liter", "litres", "liters", "l", "ltr", "लीटर", "लिटर"], (1000, "ml")
    ),
    **dict.fromkeys(["ml", "millilitre", "milliliter", "मिली", "एमएल"], (1, "ml")),
    **dict.fromkeys(["darjan", "dozen", "दर्जन"], (12, "piece")),
    **dict.fromkeys(
        ["packet", "packets", "pack", "packs", "pkt", "पैकेट", "piece", "pieces", "नग", "डिब्बा",
         "dabba"],
        (1, "pack"),
    ),
}

DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
