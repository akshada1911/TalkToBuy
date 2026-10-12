"""Warning-sign lexicon in Hindi (Devanagari + Latin) and English (T086, FR-032).

Signs: a recent fall, numbness or weakness, sudden severe pain, fever, bladder problems.
The lexicon is deliberately broad; benign look-alikes are filtered by context rules in the
detector (e.g. "चीनी गिर गई" = the sugar fell, "fell in love").
"""

import re


def _rx(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


# A fall only counts as a warning sign with a self/body/dizziness context (see detector).
FALL = _rx(
    r"गिर\s*(गया|गई|गयी|पड़ा|पड़ी|पड़ा\s*था|गया\s*था|गई\s*थी)",
    r"\bgir\s*(gaya|gayi|gai|gaye|pada|padi|padaa)\b",
    r"\bfell\b",
    r"\b(i|he|she)\s+(had\s+a\s+)?fall\b",
    r"\bfall(en)?\s+down\b",
    r"\bslipped\b",
    r"फिसल\s*(गया|गई|गयी)",
    r"\bphisal\s*(gaya|gayi|gai)\b",
)
SELF_OR_BODY = _rx(
    r"\b(main|mai|mein|mujhe|mera|meri|mere|hum|i|me|my|myself)\b",
    r"मैं|मै\s|मुझे|मेरा|मेरी|मेरे",
    r"पैर|पाँव|पांव|हाथ|सिर|कमर|घुटन|कूल्हे|पीठ",
    r"\b(pair|paon|paanv|haath|hath|sir|kamar|ghutna|ghutne|peeth|leg|legs|arm|head|hip|knee|back)\b",
    r"चक्कर|\bchakkar\b|\bdizzy\b|\bdizziness\b",
)
BENIGN_FALL = _rx(
    r"\bfell\s+in\s+love\b",
    r"\bprices?\s+fell\b",
    r"(चीनी|दूध|सामान|पैकेट|डिब्बा|बिस्कुट|आटा|अंडा|गिलास|बोतल)\s*(\S+\s*){0,2}गिर",
    r"\b(cheeni|chini|doodh|dudh|saaman|samaan|packet|dabba|biscuit|aata|atta|anda|glass|bottle)\s*(\S+\s*){0,2}gir",
)

NUMB_WEAK = _rx(
    r"सुन्न|सुन\s*हो\s*गया|झुनझुनी|कमज़ोरी|कमजोरी|जान\s*नहीं|ताकत\s*नहीं|ताक़त\s*नहीं",
    r"\bsunn\b|\bsun\s+ho\s+gaya\b|\bjhunjhuni\b|\bkamzori\b|\bkamjori\b|\bjaan\s+nahi\b|\btaakat\s+nahi\b|\btakat\s+nahi\b",
    r"\bnumb(ness)?\b|\btingling\b|\bweak(ness)?\b|\bcan'?t\s+feel\b|\bno\s+strength\b|\bparaly",
)
SEVERE_PAIN = _rx(
    r"(बहुत\s*)?तेज़?\s*दर्द|अचानक\s*(से\s*)?दर्द|असहनीय\s*दर्द|सीने\s*में\s*दर्द|छाती\s*में\s*दर्द",
    r"\b(bahut\s+)?tez\s+dard\b|\bachanak\s+(se\s+)?dard\b|\bseene\s+(mein|me)\s+dard\b|\bchhati\s+(mein|me)\s+dard\b",
    r"\bsevere\s+pain\b|\bsudden(ly)?\s+(severe\s+)?pain\b|\bunbearable\s+pain\b|\bchest\s+pain\b|\bterrible\s+pain\b",
)
FEVER = _rx(r"बुखार|बुख़ार|तेज़?\s*तापमान", r"\bbukhar\b|\bbukhaar\b|\bfever\b|\bhigh\s+temperature\b")
BLADDER = _rx(
    r"पेशाब|मूत्र|पेशाब\s*में\s*जलन",
    r"\bpeshab\b|\bpeshaab\b|\bpesab\b|\burine\b|\burinat|\bbladder\b|\bpee(ing)?\s+(problem|pain|burn)",
)

# Health words that warrant a classifier second opinion even without a lexicon hit.
HEALTH_WORDS = _rx(
    r"दर्द|दवा|दवाई|डॉक्टर|बीमार|चोट|सूजन|सांस|साँस|ब्लड\s*प्रेशर|शुगर\s*की\s*(दवा|बीमारी)",
    r"\bdard\b|\bdawa\b|\bdawai\b|\bdavai\b|\bbeemar\b|\bbimar\b|\bchot\b|\bsoojan\b|\bsujan\b|\bsaans\b",
    r"\bpain\b|\bmedicine\b|\bmedication\b|\btablet\b|\bpill\b|\bhurt\b|\bsick\b|\binjur|\bswelling\b|\bbreath",
    r"\bbalm\b|\bspray\b|\bvitamin\b|\bsupplement\b",
)

SIGNS: dict[str, re.Pattern[str]] = {
    "numbness_or_weakness": NUMB_WEAK,
    "severe_pain": SEVERE_PAIN,
    "fever": FEVER,
    "bladder": BLADDER,
}
