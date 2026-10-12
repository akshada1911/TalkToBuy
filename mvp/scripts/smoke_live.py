"""Live smoke test of the running stack (T060 helper). NOT a unit test: uses real Gemini.

Gets a demo ticket, opens the widget WebSocket, types one or more Hindi messages, and prints what
the widget would receive (captions, tool-driven cards/cart, readback, errors) plus timings.

    uv run --package session-server python scripts/smoke_live.py "दो लीटर दूध और पाव किलो टमाटर चाहिए"
"""

import asyncio
import json
import sys
import time
from collections import Counter

import httpx
import websockets

SERVER = "http://localhost:8080"
SHOP_ORIGIN = "http://localhost:5173"


async def main(turns: list[str], wait_s: float = 25.0) -> None:
    async with httpx.AsyncClient() as http:
        r = await http.post(f"{SERVER}/v1/demo-ticket", headers={"Origin": SHOP_ORIGIN})
        r.raise_for_status()
        ticket = r.json()["ticket"]
    url = SERVER.replace("http", "ws") + f"/v1/session?ticket={ticket}"
    counts: Counter = Counter()
    t0 = time.monotonic()
    first_media = None
    async with websockets.connect(url, max_size=None) as ws:
        for text in turns:
            await ws.send(json.dumps({"type": "text", "text": text}))
            print(f"\n>>> {text}")
            sent = time.monotonic()
            deadline = sent + wait_s
            while time.monotonic() < deadline:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=deadline - time.monotonic())
                except TimeoutError:
                    break
                if isinstance(msg, bytes):
                    counts[f"bin_0x{msg[0]:02x}"] += 1
                    if first_media is None:
                        first_media = round(time.monotonic() - sent, 2)
                    continue
                m = json.loads(msg)
                counts[m["type"]] += 1
                if m["type"] == "caption" and m.get("final"):
                    print(f"  [{m['who']}] {m['text_hi']}" + (f"  (EN: {m['text_en']})" if m.get("text_en") else ""))
                elif m["type"] == "cart":
                    lines = [(ln["product"]["name"], ln["qty"]) for ln in m["cart"]["lines"]]
                    print(f"  CART {lines} total ₹{m['cart']['total']}")
                elif m["type"] in ("cards", "readback", "payment_request", "error", "goal_list"):
                    print(f"  {m['type'].upper()}: {json.dumps(m, ensure_ascii=False)[:220]}")
        await ws.send(json.dumps({"type": "end"}))
    print(f"\nmessage counts: {dict(counts)}")
    print(f"first media after first text: {first_media}s; total {round(time.monotonic() - t0, 1)}s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or ["नमस्ते"]))
