"""Discover Open Food Facts candidate barcodes for the catalogue (T014).

Queries Search-a-licious (`q=<term> countries_tags:"en:india"`) for each staple term and writes
`data/candidates.json`: `{barcode: {term, product_name, brands, quantity, categories_tags,
image_front_url}}`. The full search hit is kept so `import_off.py` can reuse it for stage-2 items
without a second request per barcode.

Usage (from mvp/): python -m uv run python services/demo-store/scripts/discover_off.py [--page-size 50]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from off_client import DATA_DIR, OffClient  # noqa: E402

TERMS = [
    # demo items first, so a budget stop still covers them
    "toned milk", "chakki atta", "glucose biscuits", "parle-g", "maida", "cocoa powder",
    "butter", "condensed milk", "baking powder", "sugar", "baking soda",
    # staples for stage 2
    "milk", "atta", "whole wheat flour", "besan", "rice", "basmati rice", "poha", "suji", "dal",
    "toor dal", "moong dal", "chana", "rajma", "sunflower oil", "mustard oil", "ghee", "paneer",
    "curd", "cheese", "tea", "coffee", "salt", "turmeric", "chilli powder", "garam masala",
    "jeera", "biscuits", "cookies", "namkeen", "bhujia", "chips", "noodles", "jam", "honey",
    "pickle", "ketchup", "vermicelli", "oats", "cornflakes", "jaggery", "custard powder",
    "rusk", "dry fruits", "papad",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--budget-min", type=float, default=10.0)
    args = parser.parse_args()

    out = DATA_DIR / "candidates.json"
    candidates: dict[str, dict] = json.loads(out.read_text("utf-8")) if out.exists() else {}
    client = OffClient(budget_s=args.budget_min * 60)
    for term in TERMS:
        if client.over_budget():
            print("budget reached; stopping")
            break
        hits = client.search(term, args.page_size)
        new = 0
        for hit in hits:
            code = str(hit.get("code") or "")
            if not code.isdigit() or code in candidates:
                continue
            if "en:india" not in (hit.get("countries_tags") or []):
                continue
            candidates[code] = {"term": term, **{k: v for k, v in hit.items() if k != "code"}}
            new += 1
        print(f"{term!r}: {len(hits)} hits, {new} new (total {len(candidates)})")
        out.write_text(json.dumps(candidates, ensure_ascii=False, indent=1), "utf-8")
    print(f"wrote {len(candidates)} candidates to {out}")


if __name__ == "__main__":
    main()
