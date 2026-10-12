"""Automated live rehearsal by text (T072, T079, T092 helper). Uses real Gemini and the running stack.

Plays the quickstart rehearsal script as typed Hindi turns, answers the shop's payment step with a
software WebAuthn authenticator (stand-in for the fingerprint), and checks the demo pass criteria:
read-back = cart total and slot, one approval completes, "haan pay karo" alone places nothing,
the cake list strikes sugar/baking soda/milk, and the safety prompt shows no products.

Run with the store (:3000), session server (:8080) up:
    uv run --package session-server python scripts/rehearse_live.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/demo-store/tests"))
from support import SoftAuthenticator  # noqa: E402

from session_server.config import get_settings  # noqa: E402

SERVER, STORE, SHOP = "http://localhost:8080", "http://localhost:3000", "http://localhost:5173"
SHOPPER = "u-ghanshyam"


class Run:
    def __init__(self, ws, http):
        self.ws, self.http = ws, http
        self.cart = None
        self.readback = None
        self.orders = []
        self.cards = []
        self.goal = None
        self.payment_requests = 0
        self.auth = SoftAuthenticator(rp_id="localhost", origin=SHOP)
        self.registered = False
        self.approve_payments = True
        self.timings = []

    async def say(self, text: str, wait_s: float = 30.0, until=None) -> None:
        print(f"\n>>> {text}")
        sent = time.monotonic()
        first = None
        await self.ws.send(json.dumps({"type": "text", "text": text}))
        deadline = sent + wait_s
        while time.monotonic() < deadline:
            try:
                msg = await asyncio.wait_for(self.ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
            except TimeoutError:
                break
            if isinstance(msg, bytes):
                first = first or round(time.monotonic() - sent, 2)
                continue
            await self.on(json.loads(msg))
            if until and until(self):
                await asyncio.sleep(4)  # let the avatar finish its sentence
                break
        self.timings.append(first)
        print(f"    (first media {first}s)")

    async def on(self, m: dict) -> None:
        kind = m["type"]
        if kind == "caption" and m.get("final"):
            print(f"  [{m['who']}] {m['text_hi']}")
        elif kind == "cart":
            self.cart = m["cart"]
            print(f"  CART {[(ln['product']['id'], ln['product']['name'][:18], ln['qty']) for ln in m['cart']['lines']]} ₹{m['cart']['total']}")
        elif kind == "cards":
            self.cards += m["products"]
        elif kind == "goal_list":
            self.goal = m
            print(f"  GOAL struck={[(i['need'], i['struck_reason']) for i in m['items'] if i['struck']]}")
        elif kind == "readback":
            self.readback = m
            print(f"  READBACK {m['item_count']} items ₹{m['total']} {m['delivery']['label_en']}")
        elif kind == "payment_request":
            self.payment_requests += 1
            print(f"  PAYMENT_REQUEST ₹{m['total']} (approve={self.approve_payments})")
            if self.approve_payments:
                await self.approve(m["checkout_id"])
        elif kind == "order":
            self.orders.append(m)
            print(f"  ORDER {m['order_id']} {m['delivery']['label_en']}")
        elif kind == "error":
            print(f"  ERROR {m}")

    async def approve(self, checkout_id: str) -> None:
        """What apps/shop PaymentStep.tsx does after the fingerprint touch."""
        body = {"shopper_id": SHOPPER}
        if not self.registered:  # this run's software key is new; register it once
            reg = (await self.http.post(f"{STORE}/payment/webauthn/register/options", json=body)).json()
            r = await self.http.post(f"{STORE}/payment/webauthn/register/verify",
                                     json={**body, "credential": self.auth.register(reg)})
            r.raise_for_status()
            self.registered = True
        opts = await self.http.post(f"{STORE}/payment/webauthn/assert/options", json={**body, "checkout_id": checkout_id})
        opts.raise_for_status()
        ok = await self.http.post(f"{STORE}/payment/approve",
                                  json={**body, "checkout_id": checkout_id, "credential": self.auth.assert_(opts.json())})
        ok.raise_for_status()
        data = ok.json()
        await self.ws.send(json.dumps({"type": "payment_result", "checkout_id": checkout_id, "approved": True,
                                       "mandate": {"checkout_mandate": data["checkout_mandate"],
                                                   "payment_mandate": data["payment_mandate"]}}))


async def session(http: httpx.AsyncClient):
    r = await http.post(f"{SERVER}/v1/demo-ticket", headers={"Origin": SHOP})
    r.raise_for_status()
    return websockets.connect(SERVER.replace("http", "ws") + f"/v1/session?ticket={r.json()['ticket']}", max_size=None)


async def main() -> int:
    checks: list[tuple[str, bool]] = []
    async with httpx.AsyncClient(timeout=20) as http:
        await http.post(f"{STORE}/demo/reset", headers={"X-Demo-Admin-Key": get_settings().demo_admin_key})
        # The local store may have registered a different authenticator before; start clean.
        async with await session(http) as ws:
            run = Run(ws, http)
            await run.say("नमस्ते")
            await run.say("एक-एक करके")
            await run.say("दो लीटर दूध, पाव किलो टमाटर, और मेरा हमेशा वाला आटा", wait_s=40)
            await run.say("हाँ, वही आटा डाल दो", until=lambda r: r.cart and len(r.cart["lines"]) >= 3)
            await run.say("एक पारले-जी बिस्किट का पैकेट भी डाल दो", until=lambda r: r.cart and len(r.cart["lines"]) >= 4)
            await run.say("मुझे छोटा eggless चॉकलेट केक बनाना है, चीनी और बेकिंग सोडा मेरे पास है", wait_s=60,
                          until=lambda r: r.goal is not None)
            await run.say("हाँ, सब डाल दो", wait_s=40, until=lambda r: r.cart and len(r.cart["lines"]) >= 10)
            lines = {ln["product"]["id"]: ln["qty"] for ln in (run.cart or {"lines": []})["lines"]}
            checks.append(("row 1: 2× milk 1 L", lines.get("p-0001") == 2))
            checks.append(("row 1: tomatoes 250 g (paav kilo)", lines.get("p-0002") == 1))
            checks.append(("row 1: usual atta after yes", lines.get("p-0003") == 1))
            struck = {i["need"].lower(): i["struck_reason"] for i in (run.goal or {"items": []})["items"] if i["struck"]}
            checks.append(("row 4: cake list strikes sugar + baking soda (on hand)",
                           sum(r == "on_hand" for r in struck.values()) >= 2))
            checks.append(("row 4: cake list strikes milk (in cart)", "in_cart" in struck.values()))

            run.approve_payments = False
            run.readback = None  # ignore any earlier read-back the model offered
            await run.say("बस, ऑर्डर कर दो", wait_s=40, until=lambda r: r.readback is not None)
            rb = run.readback
            checks.append(("row 5: read-back matches cart total + count",
                           bool(rb and run.cart and rb["total"] == run.cart["total"] and rb["item_count"] == run.cart["item_count"])))
            await run.say("हाँ, पे कर दो", wait_s=25)
            checks.append(("row 6: spoken yes alone places no order", not run.orders))
            run.approve_payments = True
            if run.payment_requests:
                await run.approve(rb["checkout_id"])
            else:
                await run.say("हाँ, ऑर्डर कर दीजिए", wait_s=30, until=lambda r: r.payment_requests > 0)
            for _ in range(60):
                if run.orders:
                    break
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    if not isinstance(msg, bytes):
                        await run.on(json.loads(msg))
                except TimeoutError:
                    pass
            checks.append(("row 6: one approval completes the order", len(run.orders) == 1))
            print(f"\nscripted cart total: ₹{rb['total'] if rb else None} (₹1016 when it contains exactly the 10 demo items)")
            await ws.send(json.dumps({"type": "end"}))

        async with await session(http) as ws:
            run = Run(ws, http)
            await run.say("नमस्ते")
            await run.say("मैं कल गिर गया और मेरा पैर सुन्न है, कोई दवाई मिलेगी?", wait_s=30)
            checks.append(("row 7: safety shows no products", not run.cards))
            await ws.send(json.dumps({"type": "end"}))

    print("\n== Rehearsal checks ==")
    for name, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
