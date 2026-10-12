"""Transliteration-lite normalisation shared by catalogue search and seeded search.

Devanagari is romanised (with final-schwa deletion), then both scripts are folded into one
phonetic key so that "दूध", "doodh" and "dudh" all become `dudh`, and "चीनी"/"cheeni" become
`chini`. Quantity words (paav, kilo, litre, do, ek, aadha, …) and Hindi filler words are dropped;
`size_hint()` keeps the amount as a ranking hint.
"""

import re
import unicodedata

_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j",
    "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t",
    "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh",
    "म": "m", "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s",
    "ह": "h", "ळ": "l",
}
_NUKTA_FORMS = {"ज": "z", "फ": "f", "ड": "r", "ढ": "rh", "क": "k", "ख": "kh", "ग": "g"}
_VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri", "ए": "e",
    "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o",
}
_MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "ृ": "ri", "े": "e", "ै": "ai",
    "ो": "o", "ौ": "au", "ॉ": "o",
}
_VIRAMA, _NUKTA = "्", "़"
_NASALS = {"ं": "n", "ँ": "n", "ः": "h"}
_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def devanagari_to_latin(text: str) -> str:
    """Romanise Devanagari (other characters pass through unchanged)."""
    text = unicodedata.normalize("NFD", text).translate(_DIGITS)
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in _CONSONANTS:
            roman = _CONSONANTS[ch]
            if i + 1 < len(text) and text[i + 1] == _NUKTA:
                roman = _NUKTA_FORMS.get(ch, roman)
                i += 1
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt in _MATRAS:
                roman += _MATRAS[nxt]
                i += 1
            elif nxt == _VIRAMA:
                i += 1
            elif "ऀ" <= nxt <= "ॿ" and nxt not in _NASALS:
                roman += "a"  # inherent vowel inside a word
            elif nxt in _NASALS:
                roman += "a"
            # else: word-final consonant, schwa deleted
            out.append(roman)
        elif ch in _VOWELS:
            out.append(_VOWELS[ch])
        elif ch in _NASALS:
            out.append(_NASALS[ch])
        elif ch in _MATRAS or ch in (_VIRAMA, _NUKTA):
            out.append(_MATRAS.get(ch, ""))
        else:
            out.append(ch)
        i += 1
    return "".join(out)


_LATIN_RULES = [
    (r"chh", "ch"), (r"ph", "f"), (r"ck", "k"), (r"ch", "\x00"), (r"c", "k"), (r"\x00", "ch"),
    (r"ow", "au"), (r"er$", "ar"), (r"q", "k"), (r"w", "v"), (r"z", "j"), (r"x", "ks"),
    (r"([kgtdbj])h", r"\1"),  # drop aspiration (dh/d, th/t, bh/b …)
    (r"ee|ii|ie", "i"), (r"oo|uu", "u"), (r"aa", "a"),
    (r"(.)\1+", r"\1"),  # collapse doubled letters (atta → ata)
]


def phonetic(token: str) -> str:
    """Fold a lowercase Latin token into its phonetic key."""
    for pattern, repl in _LATIN_RULES:
        token = re.sub(pattern, repl, token)
    return token


_QUANTITY_WORDS = """
paav pav pao kilo kilogram kilograms kg kgs gram grams gm gms g gr litre liter litres liters ltr
lit litar l ml millilitre mililitre do ek char panch chhe das aadha adha dedh dhai sava
darjan dozen packet packets pack packs piece pieces pcs pc nos unit units bottle box
पाव किलो ग्राम लीटर एक दो चार पाँच आधा डेढ़ ढाई सवा दर्जन पैकेट पीस
""".split()  # noqa: SIM905 - one word list per line reads better
_FILLER_WORDS = """
aur mera meri mere hamesha vala wala wali vali chahiye chaiye de dena dijiye dedo karo kar
ka ki ke ko se me mein main mujhe hai hain ho gaya gya gayi yah ye yeh vo woh khatm khatam
kuch thoda bhi wahi vahi please the a an of for and with my usual some want need
और मेरा मेरी मेरे हमेशा वाला वाली चाहिए दे देना दीजिए करो का की के को से में मुझे है हैं
हो गया गई यह ये वो ख़त्म खत्म कुछ थोड़ा भी वही
""".split()  # noqa: SIM905 - one word list per line reads better


def _raw_tokens(text: str) -> list[str]:
    text = devanagari_to_latin(text.lower())
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"(?<=[a-z])[-'’.](?=[a-z])", "", text)  # parle-g → parleg
    text = re.sub(r"(?<=\d)(?=[a-z])|(?<=[a-z])(?=\d)", " ", text)  # 250g → 250 g
    return re.findall(r"[a-z]+|\d+(?:\.\d+)?", text)


def _keys(words: list[str]) -> set[str]:
    return {phonetic(t) for w in words for t in _raw_tokens(w)}


STOP_KEYS = _keys(_QUANTITY_WORDS) | _keys(_FILLER_WORDS)


def tokens(text: str) -> list[str]:
    """Content tokens (phonetic keys) with numbers, quantity and filler words removed."""
    out: list[str] = []
    for raw in _raw_tokens(text):
        if raw[0].isdigit():
            continue
        key = phonetic(raw)
        if len(key) > 1 and key not in STOP_KEYS and key not in out:
            out.append(key)
    return out


def key(text: str) -> str:
    """Single normalised key for a phrase (used for seeded lookups and exact matching)."""
    return " ".join(tokens(text))


_HINTS = [
    (r"\b(pav|pao)\s*kilo\b", (250, "g")),
    (r"\bada\s*kilo\b", (500, "g")),
    (r"\bsava\s*kilo\b", (1250, "g")),
    (r"\bded\s*kilo\b", (1500, "g")),
    (r"\bdai\s*kilo\b", (2500, "g")),
    (r"\bada\s*l(itr|itar|itre|iter|tr)?e?\b", (500, "ml")),
    (r"\b(do|2)\s*l(itr|itar|itre|iter|tr)?e?\b", (2000, "ml")),
    (r"\bdarjan|dojen\b", (12, "piece")),
]
_UNIT_FACTORS = {
    "g": (1, "g"), "gm": (1, "g"), "gram": (1, "g"), "gr": (1, "g"), "kg": (1000, "g"),
    "kilo": (1000, "g"), "ml": (1, "ml"), "l": (1000, "ml"), "litre": (1000, "ml"),
    "liter": (1000, "ml"), "litar": (1000, "ml"), "ltr": (1000, "ml"),
}


def size_hint(text: str) -> tuple[float, str] | None:
    """Best-effort amount in the query ("paav kilo" → (250, "g"), "5 kg" → (5000, "g"))."""
    folded = " ".join(phonetic(t) if not t[0].isdigit() else t for t in _raw_tokens(text))
    for pattern, amount in _HINTS:
        if re.search(pattern, folded):
            return amount
    match = re.search(r"(\d+(?:\.\d+)?)\s+([a-z]+)", folded)
    if match and match.group(2) in _UNIT_FACTORS:
        factor, unit = _UNIT_FACTORS[match.group(2)]
        return float(match.group(1)) * factor, unit
    return None


def numbers(text: str) -> set[str]:
    return {t for t in _raw_tokens(text) if t[0].isdigit()}
