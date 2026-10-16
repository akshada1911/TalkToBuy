"""Smoke test of a deployed TalkToBuy (UI address as the only argument).

Checks, through the UI address exactly as a browser would: the shop page, the catalogue, a voice session
(the greeting arrives at once), the dish flow (names a dish, gives the headcount, the list appears), adding to
the cart after a yes, and clearing the cart by voice. Uses real Gemini for a minute or two.
Run with the project's Python (httpx and websockets installed):  python smoke_test.py https://<ui-url>
"""

import asyncio
import json
import sys
import time

import httpx
import websockets

sys.stdout.reconfigure(encoding="utf-8")
BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:5173"
WS = BASE.replace("https://", "wss://").replace("http://", "ws://")
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    return ok


async def collect(ws, seconds: float, until=None) -> dict:
    """Read server messages for up to `seconds` (or until `until(state)` is true)."""
    state = {"audio": 0, "captions": [], "goal": None, "cart": None, "t": time.monotonic(), "first_audio_s": None}
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
        except TimeoutError:
            if until and until(state):
                return state
            continue
        if isinstance(msg, bytes):
            state["audio"] += 1
            state["first_audio_s"] = state["first_audio_s"] or round(time.monotonic() - state["t"], 1)
        else:
            m = json.loads(msg)
            if m["type"] == "caption" and m.get("final"):
                state["captions"].append((m["who"], m["text_hi"]))
            elif m["type"] == "goal_list":
                state["goal"] = m
            elif m["type"] == "cart":
                state["cart"] = m
            elif m["type"] == "error":
                state["captions"].append(("error", json.dumps(m)))
        if until and until(state):
            return state
    return state


async def main() -> int:
    print(f"Smoke test: {BASE}")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
        page = await http.get(BASE + "/")
        check("shop page loads", page.status_code == 200 and 'id="root"' in page.text, f"HTTP {page.status_code}")
        cat = await http.get(BASE + "/demo/catalog?limit=3")
        items = cat.json().get("items", []) if cat.status_code == 200 else []
        check("catalogue answers through the UI", len(items) == 3, f"HTTP {cat.status_code}")
        img = await http.get(BASE + "/static/products/p-0601.svg")
        check("product images load through the UI", img.status_code == 200, f"HTTP {img.status_code}")
        slots = await http.get(BASE + "/demo/slots")
        check("delivery slots answer", slots.status_code == 200, f"HTTP {slots.status_code}")
        tk = await http.post(BASE + "/v1/demo-ticket", headers={"Origin": BASE})
        check("voice ticket is issued", tk.status_code == 200 and "ticket" in tk.text, f"HTTP {tk.status_code} {tk.text[:80] if tk.status_code != 200 else ''}")
        if tk.status_code != 200:
            return 1
        ticket = tk.json()["ticket"]

    url = f"{WS}/v1/session?ticket={ticket}&media_mode=audio_only&language=en"
    async with websockets.connect(url, max_size=None, origin=BASE) as ws:
        hello = await collect(ws, 25, until=lambda s: s["audio"] > 3 and s["captions"])
        greeting = next((t for who, t in hello["captions"] if who == "assistant"), "")
        check("greets by name", "Vaibhav" in greeting, greeting[:60])
        check("greeting arrives fast", hello["first_audio_s"] is not None and hello["first_audio_s"] < 6, f"first audio {hello['first_audio_s']}s")

        await ws.send(json.dumps({"type": "text", "text": "I want to make dal tadka"}))
        ask = await collect(ws, 30, until=lambda s: any("people" in t.lower() for who, t in s["captions"] if who == "assistant"))
        check("asks how many people", any("people" in t.lower() for who, t in ask["captions"] if who == "assistant"))

        t0 = time.monotonic()
        await ws.send(json.dumps({"type": "text", "text": "4 people"}))
        plan = await collect(ws, 45, until=lambda s: s["goal"] is not None)
        n = len(plan["goal"]["items"]) if plan["goal"] else 0
        check("ingredient list appears", n >= 5, f"{n} items in {time.monotonic() - t0:.1f}s")
        await collect(ws, 40, until=lambda s: any("?" in t for who, t in s["captions"] if who == "assistant"))

        # The natural answer to "do you have any at home?": a "no" with an instruction to add. It must still add.
        await ws.send(json.dumps({"type": "text", "text": "No, I do not have any of these at home. Please add everything."}))
        added = await collect(ws, 40, until=lambda s: s["cart"] is not None and s["cart"]["cart"]["item_count"] > 0)
        count = added["cart"]["cart"]["item_count"] if added["cart"] else 0
        check("a \"no, add everything\" answer adds the items", count >= 5, f"{count} lines")
        await collect(ws, 12)

        await ws.send(json.dumps({"type": "text", "text": "clear the cart"}))
        cleared = await collect(ws, 30, until=lambda s: s["cart"] is not None and s["cart"]["cart"]["item_count"] == 0)
        check("clear the cart empties it", bool(cleared["cart"]) and cleared["cart"]["cart"]["item_count"] == 0)

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    return 1 if failed else 0


sys.exit(asyncio.run(main()))
