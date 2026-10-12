"""Seeded search (FR-044): fixed results for the quickstart.md rehearsal phrases.

Used when `SEARCH_MODE=seeded`. A query is matched first as a whole phrase (casefolded, NFC),
then by its normalised token key (so "doodh", "दूध" and "दो लीटर दूध" share one entry). Queries
not in the table fall through to normal search. Results are never ambiguous.
"""

import unicodedata

from demo_store.catalog import normalize

MILK = ["p-0001", "p-0014", "p-0013"]
TOMATOES = ["p-0002", "p-0016", "p-0017"]
ATTA = ["p-0003", "p-0019", "p-0018"]
BISCUIT = ["p-0004", "p-0021", "p-0023"]
MAIDA = ["p-0005", "p-0024", "p-0025"]
COCOA = ["p-0006", "p-0026", "p-0027"]
BUTTER = ["p-0007", "p-0028", "p-0029"]
CONDENSED = ["p-0008", "p-0030"]
BAKING_POWDER = ["p-0009", "p-0031", "p-0032"]
CAKE_TIN = ["p-0010", "p-0033", "p-0034"]
SUGAR = ["p-0011", "p-0035", "p-0036"]
BAKING_SODA = ["p-0012", "p-0037"]
CAKE_GOAL = ["p-0005", "p-0006", "p-0007", "p-0008", "p-0009", "p-0010"]

PHRASES: dict[str, list[str]] = {
    # row 1: "दो लीटर दूध, पाव किलो टमाटर, और मेरा हमेशा वाला आटा"
    **dict.fromkeys(["दूध", "doodh", "dudh", "milk", "toned milk", "टोंड दूध", "दो लीटर दूध"], MILK),
    **dict.fromkeys(["टमाटर", "tamatar", "tomato", "tomatoes", "पाव किलो टमाटर"], TOMATOES),
    **dict.fromkeys(["आटा", "aata", "atta", "chakki atta", "चक्की आटा", "मेरा हमेशा वाला आटा",
                     "aashirvaad atta", "आशीर्वाद आटा", "gehun ka atta"], ATTA),
    # row 3: the empty biscuit packet ("यह ख़त्म हो गया")
    **dict.fromkeys(["यह ख़त्म हो गया", "यह खत्म हो गया", "ye khatam ho gaya", "parle-g", "parle g",
                     "पारले जी", "पारले-जी", "glucose biscuit", "glucose biscuits", "biscuit",
                     "बिस्किट", "parle-g biscuit", "ग्लूकोज़ बिस्किट"], BISCUIT),
    # row 4: "मुझे छोटा eggless चॉकलेट केक बनाना है, चीनी और बेकिंग सोडा है"
    **dict.fromkeys(["मैदा", "maida", "refined flour", "all purpose flour"], MAIDA),
    **dict.fromkeys(["कोको पाउडर", "कोको", "cocoa powder", "cocoa", "koko powder"], COCOA),
    **dict.fromkeys(["मक्खन", "बटर", "butter", "makhan", "makkhan"], BUTTER),
    **dict.fromkeys(["कंडेंस्ड मिल्क", "मिल्कमेड", "condensed milk", "milkmaid",
                     "sweetened condensed milk"], CONDENSED),
    **dict.fromkeys(["बेकिंग पाउडर", "baking powder"], BAKING_POWDER),
    **dict.fromkeys(["केक टिन", "7 इंच केक टिन", "cake tin", "7 inch cake tin", "7-inch cake tin",
                     "cake mould", "केक का बर्तन"], CAKE_TIN),
    **dict.fromkeys(["चीनी", "chini", "cheeni", "sugar", "शक्कर"], SUGAR),
    **dict.fromkeys(["बेकिंग सोडा", "baking soda", "meetha soda", "मीठा सोडा"], BAKING_SODA),
    **dict.fromkeys(["eggless chocolate cake", "chocolate cake", "चॉकलेट केक",
                     "छोटा eggless चॉकलेट केक", "eggless चॉकलेट केक"], CAKE_GOAL),
    # row 7 and medicine requests: never any products
    **dict.fromkeys(["दवाई", "दवा", "dawai", "dawa", "medicine", "pain balm", "balm", "vitamin",
                     "protein powder", "sugar ki dawai"], []),
}


def _phrase(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


_BY_PHRASE = {_phrase(k): v for k, v in PHRASES.items()}
_BY_KEY = {normalize.key(k): v for k, v in PHRASES.items() if normalize.key(k)}


def lookup(query: str) -> list[str] | None:
    """Fixed product ids for a rehearsal phrase, or None when the phrase is not seeded."""
    hit = _BY_PHRASE.get(_phrase(query))
    if hit is not None:
        return hit
    return _BY_KEY.get(normalize.key(query))
