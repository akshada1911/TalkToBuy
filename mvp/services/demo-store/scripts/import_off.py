"""Import the catalogue snapshot from Open Food Facts (T016).

For every barcode in `data/seed_barcodes.json`:

- **Fetch** `GET /api/v2/product/{code}` (throttled, see off_client.py). Stage-1 barcodes are always
  fetched live; stage-2 barcodes reuse the Search-a-licious hit cached in `data/candidates.json`
  (same fields) unless `--fetch-all` is given, which keeps a 300-500 item import inside the OFF
  time budget.
- **Normalise** `quantity` into `unit_qty` + `unit` and map `categories_tags` to our categories.
- **Include-list / denylist** (FR-031): keep only our 10 grocery categories, reject supplement,
  vitamin, protein-powder, infant-formula and non-food tags (and health-positioned names). Every
  reject is logged with its reason in `data/import_rejects.json`.
- **Merge** `data/overrides.json` (Hindi names, synonyms, listings, demo prices, hand-added items).
- **Validate** each product against the generated domain `Product` model and write
  `data/catalog.json`. Fails if a demo item lacks `local_name`, `listing.description` or `image`.

Stage-2 items get a generated Hindi name, Hinglish synonyms, a pack-facts listing and a demo
price from the lexicon below; they are marked in `source_categories` with `talktobuy:auto-hindi`
for review.

Usage (from mvp/):
  python -m uv run python services/demo-store/scripts/import_off.py [--offline] [--fetch-all]
  python -m uv run python services/demo-store/scripts/import_off.py --select-stage2 400
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from off_client import DATA_DIR, OffClient  # noqa: E402

from demo_store.models.domain import Product  # noqa: E402

STATIC_DIR = DATA_DIR.parent / "static" / "products"

INCLUDE = ["dairy", "flours", "biscuits", "baking", "beverages", "spices", "staples", "snacks",
           "produce", "home"]
DENY_TAGS = {
    "en:dietary-supplements", "en:food-supplements", "en:vitamins", "en:protein-powders",
    "en:baby-milks", "en:infant-formulas", "en:non-food-products", "en:bodybuilding-supplements",
    "en:baby-foods", "en:alcoholic-beverages", "en:energy-drinks", "en:sweeteners-tabletop",
}
DENY_NAME = re.compile(
    r"protein|vitamin|supplement|immun|chyawan|bourn ?vita|horlicks|complan|boost|glucon|"
    r"glucose[- ]?d\b|glucose c|sugar[- ]?free|diabet|ayurved|medic|balm|tablet|capsule|syrup|"
    r"baby|infant|cerelac|lactogen|nan pro|whey|health|keto|weight|slim|detox|herbal",
    re.I,
)

# OFF category tag -> our category, checked in order (most specific first).
CATEGORY_RULES: list[tuple[str, str]] = [
    (r"en:(baking-powders?|cocoa-powders|bicarbonates-of-soda|custard-powders|baking-aids|"
     r"baking-decorations|cake-mixes|yeasts)", "baking"),
    (r"en:(biscuits|cookies|rusks|crackers|wafers|biscuits-and-cakes)", "biscuits"),
    (r"en:(dairies|milks|butters|cheeses|paneer|yogurts|milk-curds|ghee|clarified-butter|"
     r"condensed-milks|creams|milkfat)", "dairy"),
    (r"en:(flours|wheat-flours|cereal-flours|semolinas?|legume-flours|whole-wheat-flours)", "flours"),
    (r"en:(spices|salts|spice-mixes|turmeric|chili-powders|cumin|condiments|masalas|"
     r"garam-masala|seasonings)", "spices"),
    (r"en:(teas|coffees|tea-bags|instant-coffees|carbonated-drinks|fruit-juices|juices|"
     r"waters|beverages)", "beverages"),
    (r"en:(rices|pulses|legumes|lentils|sugars|vegetable-oils|oils|noodles|pastas|"
     r"rice-flakes|breakfast-cereals|jaggery|honeys|jams|pickles|sauces|ketchup|vermicelli|"
     r"oat-flakes|rolled-flakes|cereals-and-their-products|cereal-grains|seeds|dried-fruits|"
     r"nuts|spreads|chickpeas|beans)", "staples"),
    (r"en:(snacks|salty-snacks|chips|crisps|namkeen|appetizers|popcorn|bhujia|papads?)", "snacks"),
    (r"en:(fresh-vegetables|vegetables|fresh-fruits|fruits)", "produce"),
]

# Product-type lexicon for stage-2 items: name regex -> (Hindi noun, Hinglish synonyms,
# category hint, usage line, demo rupees per kg/L or per piece). Checked in order.
LEXICON: list[tuple[str, str, list[str], str, str, int]] = [
    (r"condensed", "कंडेंस्ड मिल्क", ["condensed milk"], "dairy", "For sweets and desserts.", 380),
    (r"\bghee\b", "घी", ["ghee", "desi ghee"], "dairy", "For cooking and tadka.", 650),
    (r"paneer", "पनीर", ["paneer"], "dairy", "Keep refrigerated. For sabzi and snacks.", 420),
    (r"\bcurd|dahi|yogh?urt", "दही", ["dahi", "curd"], "dairy", "Keep refrigerated.", 90),
    (r"cheese", "चीज़", ["cheese", "chees"], "dairy", "Keep refrigerated. For sandwiches and pizza.", 550),
    (r"peanut butter|peanut spread", "पीनट बटर", ["peanut butter"], "staples", "A spread for bread.", 450),
    (r"butter(?! ?cookie| ?biscuit|scotch|fly)", "मक्खन", ["butter", "makhan"], "dairy", "Keep refrigerated.", 560),
    (r"milk powder", "मिल्क पाउडर", ["milk powder", "doodh powder"], "dairy", "Mix with water.", 450),
    (r"^(?!.*(choc|cookie|biscuit|bread|shake|candy|toffee|bikis|shakti|\bbar\b)).*\bmilk\b", "दूध", ["doodh", "milk"], "dairy",
     "Keep refrigerated after opening. For tea and cooking.", 64),
    (r"maida|refined wheat flour|all purpose flour", "मैदा", ["maida"], "flours", "For baking and naan.", 60),
    (r"besan|gram flour|chickpea flour", "बेसन", ["besan"], "flours", "For pakoras and cheela.", 110),
    (r"suji|sooji|semolina|rava", "सूजी", ["suji", "rava"], "flours", "For upma and halwa.", 60),
    (r"\batta\b|whole wheat flour|chakki", "आटा", ["atta", "aata"], "flours", "For rotis and parathas.", 52),
    (r"rice flour", "चावल का आटा", ["chawal ka atta"], "flours", "For dosa and snacks.", 80),
    (r"biscuit|cookie|marie|bourbon|crackers?\b|cream biscuit", "बिस्किट", ["biscuit", "biskut"], "biscuits",
     "A tea-time biscuit.", 160),
    (r"\brusk|toast\b", "रस्क", ["rusk", "toast"], "biscuits", "A tea-time rusk.", 160),
    (r"cocoa", "कोको पाउडर", ["cocoa"], "baking", "For cakes and drinks.", 900),
    (r"custard", "कस्टर्ड पाउडर", ["custard"], "baking", "For desserts.", 400),
    (r"baking powder", "बेकिंग पाउडर", ["baking powder"], "baking", "A raising agent for cakes.", 400),
    (r"baking soda|bicarbonate", "बेकिंग सोडा", ["baking soda", "meetha soda"], "baking", "A raising agent.", 250),
    (r"basmati", "बासमती चावल", ["basmati", "chawal"], "staples", "Rinse before cooking.", 140),
    (r"\bpoha\b|rice flakes", "पोहा", ["poha"], "staples", "For breakfast poha.", 80),
    (r"\brice\b", "चावल", ["chawal", "rice"], "staples", "Rinse before cooking.", 85),
    (r"toor|tur dal|arhar", "अरहर दाल", ["toor dal", "arhar dal", "dal"], "staples", "Rinse and soak before cooking.", 170),
    (r"moong", "मूंग दाल", ["moong dal", "dal"], "staples", "Rinse before cooking.", 150),
    (r"masoor", "मसूर दाल", ["masoor dal", "dal"], "staples", "Rinse before cooking.", 120),
    (r"urad", "उड़द दाल", ["urad dal", "dal"], "staples", "Rinse and soak before cooking.", 150),
    (r"chana dal", "चना दाल", ["chana dal", "dal"], "staples", "Rinse and soak before cooking.", 110),
    (r"rajma|kidney bean", "राजमा", ["rajma"], "staples", "Soak overnight before cooking.", 170),
    (r"kabuli|chickpea|chole|\bchana\b", "चना", ["chana", "chole"], "staples", "Soak overnight before cooking.", 120),
    (r"\bdal\b|\bdhal\b|lentil", "दाल", ["dal"], "staples", "Rinse before cooking.", 140),
    (r"jaggery|\bgur\b|\bgud\b", "गुड़", ["gud", "gur", "jaggery"], "staples", "For sweets and tea.", 90),
    (r"\bsugar\b", "चीनी", ["chini", "cheeni", "sugar"], "staples", "For tea and sweets.", 50),
    (r"mustard oil", "सरसों का तेल", ["sarson tel", "mustard oil"], "staples", "For cooking.", 190),
    (r"sunflower", "सूरजमुखी तेल", ["sunflower oil", "tel"], "staples", "For cooking and frying.", 170),
    (r"rice bran", "राइस ब्रान तेल", ["rice bran oil", "tel"], "staples", "For cooking and frying.", 170),
    (r"soya|soybean", "सोयाबीन तेल", ["soyabean oil", "tel"], "staples", "For cooking and frying.", 150),
    (r"groundnut oil|peanut oil", "मूंगफली का तेल", ["mungfali tel"], "staples", "For cooking.", 220),
    (r"\boil\b", "तेल", ["tel", "oil"], "staples", "For cooking.", 180),
    (r"honey", "शहद", ["shahad", "honey"], "staples", "A sweetener for drinks and desserts.", 500),
    (r"\bjam\b", "जैम", ["jam"], "staples", "A spread for bread.", 300),
    (r"pickle|achar", "अचार", ["achaar", "achar", "pickle"], "staples", "Keep the lid closed.", 300),
    (r"ketchup|tomato sauce", "टमाटर सॉस", ["ketchup", "sauce"], "staples", "Refrigerate after opening.", 150),
    (r"vermicelli|sevai|seviyan", "सेवई", ["sevai", "vermicelli"], "staples", "For kheer and upma.", 120),
    (r"noodle", "नूडल्स", ["noodles", "maggi"], "staples", "Cook in boiling water.", 260),
    (r"\boats\b", "ओट्स", ["oats"], "staples", "For breakfast porridge.", 200),
    (r"corn ?flakes", "कॉर्नफ़्लेक्स", ["cornflakes"], "staples", "Serve with milk.", 350),
    (r"almond|badam", "बादाम", ["badam", "almonds"], "staples", "Store in an airtight jar.", 1000),
    (r"cashew|kaju", "काजू", ["kaju", "cashew"], "staples", "Store in an airtight jar.", 1100),
    (r"raisin|kishmish", "किशमिश", ["kishmish", "raisins"], "staples", "Store in an airtight jar.", 600),
    (r"\bsalt\b", "नमक", ["namak", "salt"], "spices", "For everyday cooking.", 28),
    (r"turmeric|haldi", "हल्दी", ["haldi", "turmeric"], "spices", "For everyday cooking.", 350),
    (r"chilli|chili|mirch", "लाल मिर्च पाउडर", ["mirch", "lal mirch"], "spices", "For everyday cooking.", 400),
    (r"garam masala", "गरम मसाला", ["garam masala"], "spices", "For curries.", 700),
    (r"jeera|cumin", "जीरा", ["jeera", "zeera"], "spices", "For tadka.", 500),
    (r"coriander|dhania", "धनिया पाउडर", ["dhaniya"], "spices", "For everyday cooking.", 300),
    (r"masala", "मसाला", ["masala"], "spices", "For everyday cooking.", 600),
    (r"\btea\b|chai", "चाय पत्ती", ["chai", "chai patti", "tea"], "beverages", "Brew in hot water or milk.", 500),
    (r"coffee", "कॉफ़ी", ["coffee", "kafi"], "beverages", "Mix with hot water or milk.", 1200),
    (r"bhujia|namkeen|mixture|sev\b|chivda|chiwda", "नमकीन", ["namkeen", "bhujia"], "snacks", "A tea-time snack.", 300),
    (r"chips|crisps|wafers", "चिप्स", ["chips"], "snacks", "A snack.", 400),
    (r"papad", "पापड़", ["papad"], "snacks", "Roast or fry before serving.", 300),
]

BRANDS_HI = {
    "amul": "अमूल", "fortune": "फ़ॉर्च्यून", "aashirvaad": "आशीर्वाद", "parle": "पारले",
    "britannia": "ब्रिटानिया", "tata": "टाटा", "sunfeast": "सनफ़ीस्ट", "haldiram": "हल्दीराम",
    "mother dairy": "मदर डेयरी", "nestle": "नेस्ले", "nestlé": "नेस्ले", "patanjali": "पतंजलि",
    "everest": "एवरेस्ट", "mdh": "एमडीएच", "catch": "कैच", "kissan": "किसान", "maggi": "मैगी",
    "nandini": "नंदिनी", "pillsbury": "पिल्सबरी", "india gate": "इंडिया गेट", "daawat": "दावत",
    "saffola": "सफ़ोला", "dhara": "धारा", "bikaji": "बीकाजी", "lays": "लेज़", "lay's": "लेज़",
    "kurkure": "कुरकुरे", "brooke bond": "ब्रुक बॉन्ड", "red label": "रेड लेबल", "taj mahal": "ताज महल",
    "bru": "ब्रू", "nescafe": "नेस्कैफ़े", "dabur": "डाबर", "mtr": "एमटीआर", "cadbury": "कैडबरी",
    "unibic": "यूनिबिक", "priyagold": "प्रियागोल्ड", "bisk farm": "बिस्क फ़ार्म", "cremica": "क्रेमिका",
    "madhur": "मधुर", "weikfield": "वीकफ़ील्ड", "rajdhani": "राजधानी", "heritage": "हेरिटेज",
    "dodla": "डोडला", "milky mist": "मिल्की मिस्ट", "gowardhan": "गोवर्धन", "keya": "केया",
    "goodlife": "गुडलाइफ़", "good life": "गुडलाइफ़", "ganesh": "गणेश", "id": "आईडी",
    "bambino": "बैम्बिनो", "kellogg's": "केलॉग्स", "quaker": "क्वेकर", "saffron": "सैफ़्रन",
    "aachi": "आची", "eastern": "ईस्टर्न", "ching's": "चिंग्स", "yippee": "यिप्पी", "knorr": "नॉर",
    "mccain": "मैक्केन", "milkymist": "मिल्की मिस्ट", "jabsons": "जैबसन्स", "tetley": "टेटली",
    "wagh bakri": "वाघ बकरी", "society": "सोसाइटी", "ashirvaad": "आशीर्वाद", "itc": "आईटीसी", "veeba": "वीबा", "del monte": "डेल मोंटे", "hershey's": "हर्शीज़",
}

UNIT_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kgs?|kilo(?:gram)?s?|g|gm|gms|gr|grams?|gram|ml|millilit(?:re|er)s?|"
    r"l|lt|ltr|lit(?:re|er)s?)\b",
    re.I,
)


def parse_quantity(text: str | None) -> tuple[float, str, str] | None:
    """'5 kg' -> (5000, 'g', '5 kg'); '1litre' -> (1000, 'ml', '1 L'). None when unparseable."""
    if not text:
        return None
    match = UNIT_RE.search(text)
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    if value <= 0:
        return None
    if unit.startswith("k"):
        qty, base = value * 1000, "g"
    elif unit in {"g", "gm", "gms", "gr"} or unit.startswith("gram"):
        qty, base = value, "g"
    elif unit == "ml" or unit.startswith("milli"):
        qty, base = value, "ml"
    else:
        qty, base = value * 1000, "ml"
    qty = round(qty, 1)
    if qty < 5 or qty > 30000:
        return None
    if base == "g":
        label = f"{_num(qty / 1000)} kg" if qty >= 1000 else f"{_num(qty)} g"
    else:
        label = f"{_num(qty / 1000)} L" if qty >= 1000 else f"{_num(qty)} ml"
    return qty, base, label


def _num(value: float) -> str:
    return str(int(value)) if value == int(value) else f"{value:g}"


def map_category(tags: list[str]) -> str | None:
    joined = " ".join(tags)
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern + r"(\s|$)", joined):
            return category
    return None


def reject_reason(name: str, tags: list[str], brand: str | None = None) -> str | None:
    denied = sorted(DENY_TAGS.intersection(tags))
    if denied:
        return f"denylisted tag {denied[0]}"
    match = DENY_NAME.search(f"{name} {brand or ''}")
    if match:
        return f"health/medicine keyword in name or brand ({match.group(0)})"
    return None


def brand_of(raw: dict) -> str | None:
    brands = raw.get("brands")
    if isinstance(brands, list):
        brands = brands[0] if brands else None
    if isinstance(brands, str):
        brands = brands.split(",")[0].strip()
    return brands or None


def lexicon_entry(name: str, category: str) -> tuple | None:
    """First lexicon entry whose pattern matches and whose category agrees with OFF's."""
    lower = name.lower()
    for entry in LEXICON:
        if re.search(entry[0], lower) and entry[3] == category:
            return entry
    return None


def auto_fields(raw: dict, category: str, qty: tuple[float, str, str]) -> dict | None:
    """Generated Hindi name, synonyms, listing and demo price for a stage-2 item."""
    name = (raw.get("product_name") or "").strip()
    entry = lexicon_entry(name, category)
    if not entry:
        return None
    _pattern, hindi, synonyms, _hint, usage, rate = entry
    brand = brand_of(raw)
    brand_hi = BRANDS_HI.get((brand or "").lower())
    unit_qty, unit, size = qty
    local_name = f"{brand_hi} {hindi}" if brand_hi else hindi
    rupees = max(10, round(rate * unit_qty / 1000))
    title = name if size.replace(" ", "").lower() in name.replace(" ", "").lower() else f"{name} {size}"
    if brand and brand.lower() not in title.lower():
        title = f"{brand} {title}"
    # Qualify generic words ("doodh") with the brand so auto items never claim a bare generic
    # synonym that a curated demo item owns.
    qualifier = (brand or name.split()[0]).lower()
    syns = list(dict.fromkeys(f"{qualifier} {s}" for s in synonyms))
    return {
        "name": re.sub(r"\s+", " ", title).strip()[:80],
        "local_name": f"{local_name} {size_hi(size)}",
        "brand": brand,
        "synonyms": syns,
        "listing": {"description": f"{title.strip()}, {size} pack.", "usage": usage},
        "price_minor": rupees * 100,
        "category": category,
    }


def size_hi(size: str) -> str:
    value, unit = size.split(" ")
    return f"{value} " + {"kg": "किलो", "g": "ग्राम", "L": "लीटर", "ml": "मिली"}[unit]


def placeholder_svg(product: dict) -> str:
    colours = {"produce": "#3f7d3a", "home": "#6b5b95", "dairy": "#2d6a9f", "baking": "#8a5a2b",
               "flours": "#a0782c", "staples": "#7a6a3a"}
    colour = colours.get(product["category"], "#555")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400" viewBox="0 0 400 400">'
        f'<rect width="400" height="400" rx="24" fill="{colour}"/>'
        '<rect x="24" y="24" width="352" height="352" rx="16" fill="#fff" opacity="0.12"/>'
        f'<text x="200" y="185" font-family="sans-serif" font-size="38" fill="#fff" '
        f'text-anchor="middle">{product["local_name"]}</text>'
        f'<text x="200" y="240" font-family="sans-serif" font-size="26" fill="#fff" '
        f'text-anchor="middle">{product["name"]}</text>'
        '<text x="200" y="360" font-family="sans-serif" font-size="16" fill="#fff" opacity="0.8" '
        'text-anchor="middle">TalkToBuy placeholder</text></svg>'
    )


def load_json(path: Path, default):
    return json.loads(path.read_text("utf-8")) if path.exists() else default


def select_stage2(seed: dict, candidates: dict, overrides: dict, target: int) -> list[dict]:
    """Pick up to `target` stage-2 barcodes from candidates that will pass every import rule.

    Returns the screened-out candidates with their reasons (merged into import_rejects.json).
    """
    taken = {e["barcode"] for e in seed["stage1"]}
    screened: list[dict] = []
    seen_names: set[tuple[str, float]] = set()
    by_term: dict[str, list[str]] = {}
    for code, raw in candidates.items():
        if code in taken or code in overrides or not raw.get("image_front_url"):
            continue
        name = (raw.get("product_name") or "").strip()
        tags = raw.get("categories_tags") or []
        qty = parse_quantity(raw.get("quantity")) or parse_quantity(name)
        category = map_category(tags)
        reason = (reject_reason(name, tags, brand_of(raw)) or (None if category else "no category in the include-list")
                  or (None if qty else "unparseable quantity")
                  or (None if auto_fields(raw, category, qty) else "no Hindi lexicon entry"))
        if not name or reason:
            screened.append({"barcode": code, "name": name, "reason": reason or "no product name"})
            continue
        dedupe = (re.sub(r"[^a-z]", "", name.lower()) + (brand_of(raw) or "").lower(), qty[0])
        if dedupe in seen_names:
            continue
        seen_names.add(dedupe)
        by_term.setdefault(raw.get("term", ""), []).append(code)
    picked: list[str] = []
    while len(picked) < target and any(by_term.values()):
        for codes in by_term.values():
            if codes and len(picked) < target:
                picked.append(codes.pop(0))
    seed["stage2"] = [{"id": f"p-{101 + i:04d}", "barcode": code} for i, code in enumerate(picked)]
    print(f"selected {len(picked)} stage-2 barcodes; screened out {len(screened)}")
    return screened


def build(args: argparse.Namespace) -> None:
    seed = load_json(DATA_DIR / "seed_barcodes.json", {})
    overrides = {k: v for k, v in load_json(DATA_DIR / "overrides.json", {}).items() if not k.startswith("_")}
    candidates = load_json(DATA_DIR / "candidates.json", {})
    cache = load_json(DATA_DIR / "off_cache.json", {})
    client = None if args.offline else OffClient(budget_s=args.budget_min * 60)

    products: list[dict] = []
    rejects: list[dict] = []
    demo_ids = {e["id"] for e in seed["stage1"] if e.get("demo")}
    demo_ids |= {pid for pid, demo in seed.get("hand_added", {}).items() if demo}

    entries = [(e, True) for e in seed["stage1"]] + [(e, False) for e in seed.get("stage2", [])]
    for entry, stage1 in entries:
        code, pid = entry["barcode"], entry["id"]
        raw = None
        if client and (stage1 or args.fetch_all) and not client.over_budget():
            raw = client.product(code)
            if raw:
                cache[code] = raw
        raw = raw or cache.get(code) or candidates.get(code)
        if not raw:
            rejects.append({"barcode": code, "id": pid, "reason": "not found on Open Food Facts"})
            continue
        name = (raw.get("product_name") or "").strip()
        tags = list(raw.get("categories_tags") or [])
        over = overrides.get(code, {})
        reason = reject_reason(name, tags, brand_of(raw)) if not over else None
        if reason:
            rejects.append({"barcode": code, "id": pid, "name": name, "reason": reason})
            continue
        category = over.get("category") or map_category(tags)
        if category not in INCLUDE:
            rejects.append({"barcode": code, "id": pid, "name": name,
                            "reason": "no category in the include-list"})
            continue
        qty = parse_quantity(raw.get("quantity")) or parse_quantity(name)
        fields = {}
        if not over:
            if not qty:
                rejects.append({"barcode": code, "id": pid, "name": name, "reason": "unparseable quantity"})
                continue
            fields = auto_fields(raw, category, qty) or {}
            if not fields:
                rejects.append({"barcode": code, "id": pid, "name": name,
                                "reason": "no Hindi lexicon entry for this product type"})
                continue
            fields["source_categories"] = [*tags, "talktobuy:auto-hindi"]
        image = raw.get("image_front_url")
        product = {
            "id": pid,
            "barcode": code,
            "brand": brand_of(raw),
            "size": qty[2] if qty else None,
            "unit_qty": qty[0] if qty else None,
            "unit": qty[1] if qty else None,
            "currency": "INR",
            "image": image,
            "image_credit": f"Open Food Facts contributors, CC BY-SA (openfoodfacts.org/product/{code})",
            "category": category,
            "source_categories": tags,
            "in_stock": True,
            **fields,
            **over,
        }
        if not product.get("image"):
            product["image"] = f"/static/products/{pid}.svg"
            product["image_credit"] = "TalkToBuy placeholder illustration"
        products.append(product)

    for pid in seed.get("hand_added", {}):
        over = dict(overrides[pid])
        products.append({
            "id": pid, "currency": "INR", "image": f"/static/products/{pid}.svg",
            "image_credit": "TalkToBuy placeholder illustration",
            "source_categories": ["talktobuy:hand-added"], "in_stock": True, **over,
        })

    validated: list[dict] = []
    for product in products:
        try:
            validated.append(Product.model_validate(product).model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001 - report every invalid record
            rejects.append({"barcode": product.get("barcode"), "id": product["id"],
                            "name": product.get("name"), "reason": f"invalid: {exc}"[:300]})
    validated.sort(key=lambda p: p["id"])

    by_id = {p["id"]: p for p in validated}
    missing = [pid for pid in sorted(demo_ids)
               if pid not in by_id or not by_id[pid]["local_name"] or not by_id[pid]["listing"]["description"]
               or not by_id[pid]["image"]]
    if missing:
        raise SystemExit(f"demo items missing or incomplete: {missing}")
    if any(p["category"] not in INCLUDE for p in validated):
        raise SystemExit("a product outside the include-list slipped through")

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    for product in validated:
        if product["image"].startswith("/static/products/"):
            (STATIC_DIR / f"{product['id']}.svg").write_text(placeholder_svg(product), "utf-8")

    meta = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Open Food Facts (ODbL; images CC BY-SA) + TalkToBuy hand-added items",
        "count": len(validated),
    }
    (DATA_DIR / "catalog.json").write_text(
        json.dumps({**meta, "products": validated}, ensure_ascii=False, indent=1), "utf-8")
    screening = load_json(DATA_DIR / "candidate_rejects.json", [])
    (DATA_DIR / "import_rejects.json").write_text(json.dumps(
        {"import": rejects, "candidate_screening": screening}, ensure_ascii=False, indent=1), "utf-8")
    (DATA_DIR / "off_cache.json").write_text(json.dumps(cache, ensure_ascii=False, indent=1), "utf-8")
    hand = sum(1 for p in validated if p["barcode"] is None)
    print(f"catalog: {len(validated)} products ({len(validated) - hand} OFF, {hand} hand-added); "
          f"{len(rejects)} rejects; OFF failures: {client.failures if client else 0}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="use cached OFF data only")
    parser.add_argument("--fetch-all", action="store_true", help="fetch stage-2 barcodes live too")
    parser.add_argument("--budget-min", type=float, default=15.0)
    parser.add_argument("--select-stage2", type=int, metavar="N",
                        help="choose N stage-2 barcodes from candidates.json, then exit")
    args = parser.parse_args()
    if args.select_stage2:
        seed_path = DATA_DIR / "seed_barcodes.json"
        seed = load_json(seed_path, {})
        overrides = load_json(DATA_DIR / "overrides.json", {})
        screened = select_stage2(seed, load_json(DATA_DIR / "candidates.json", {}), overrides,
                                 args.select_stage2)
        seed_path.write_text(json.dumps(seed, ensure_ascii=False, indent=1), "utf-8")
        (DATA_DIR / "candidate_rejects.json").write_text(
            json.dumps(screened, ensure_ascii=False, indent=1), "utf-8")
        return
    build(args)


if __name__ == "__main__":
    main()
