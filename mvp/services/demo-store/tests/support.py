"""Test helpers: a UCP client wrapper, the scripted cart and a software WebAuthn authenticator."""

import base64
import hashlib
import json
import os
import struct
import uuid

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

UCP_HEADERS = {"UCP-Agent": 'profile="http://session.test/agent-profile.json"'}

# The scripted 10-product cart (quickstart rows 1, 3, 4): Rs 1,016.
SCRIPTED_CART = [
    ("p-0001", 2), ("p-0002", 1), ("p-0003", 1), ("p-0004", 1), ("p-0005", 1),
    ("p-0006", 1), ("p-0007", 1), ("p-0008", 1), ("p-0009", 1), ("p-0010", 1),
]


class UcpClient:
    """TestClient wrapper that adds UCP-Agent, Request-Id and Idempotency-Key."""

    def __init__(self, client: TestClient) -> None:
        self.raw = client

    def _headers(self, key: str | None, method: str) -> dict:
        headers = {**UCP_HEADERS, "Request-Id": str(uuid.uuid4())}
        if method in {"POST", "PUT"}:
            headers["Idempotency-Key"] = key or str(uuid.uuid4())
        return headers

    def get(self, path: str):
        return self.raw.get(path, headers=self._headers(None, "GET"))

    def post(self, path: str, json: dict | None = None, key: str | None = None):
        return self.raw.post(path, json=json or {}, headers=self._headers(key, "POST"))

    def put(self, path: str, json: dict, key: str | None = None):
        return self.raw.put(path, json=json, headers=self._headers(key, "PUT"))

    # --- helpers ---

    def search(self, query: str, **extra) -> dict:
        resp = self.post("/ucp/v1/catalog/search", {"query": query, **extra})
        assert resp.status_code == 200, resp.text
        return resp.json()

    def create(self, lines=()) -> dict:
        resp = self.post("/ucp/v1/checkout-sessions", lines_body(lines))
        assert resp.status_code == 201, resp.text
        return resp.json()

    def replace(self, checkout_id: str, lines, slot: str | None = None):
        return self.put(f"/ucp/v1/checkout-sessions/{checkout_id}", lines_body(lines, slot))

    def ready_cart(self, lines=SCRIPTED_CART, slot: str = "slot-1800") -> dict:
        checkout = self.create(lines)
        resp = self.replace(checkout["id"], lines, slot)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "ready_for_complete"
        return resp.json()


def lines_body(lines, slot: str | None = None) -> dict:
    return {
        "currency": "INR",
        "line_items": [{"item": {"id": pid}, "quantity": qty} for pid, qty in lines],
        "fulfillment": {"selected_option_id": slot} if slot else None,
    }


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class SoftAuthenticator:
    def __init__(self, rp_id: str = "localhost", origin: str = "http://localhost:5173") -> None:
        self.rp_id, self.origin = rp_id, origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.sign_count = 0

    def _client_data(self, kind: str, challenge_b64: str) -> bytes:
        return json.dumps({"type": kind, "challenge": challenge_b64, "origin": self.origin,
                           "crossOrigin": False}).encode()

    def _auth_data(self, flags: int, attested: bytes = b"") -> bytes:
        self.sign_count += 1
        rp_hash = hashlib.sha256(self.rp_id.encode()).digest()
        return rp_hash + bytes([flags]) + struct.pack(">I", self.sign_count) + attested

    def register(self, options: dict) -> dict:
        numbers = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"),
                            -3: numbers.y.to_bytes(32, "big")})
        attested = bytes(16) + struct.pack(">H", len(self.credential_id)) + self.credential_id + cose
        auth_data = self._auth_data(0x45, attested)  # UP | UV | AT
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        client_data = self._client_data("webauthn.create", options["challenge"])
        cred_id = b64url(self.credential_id)
        return {"id": cred_id, "rawId": cred_id, "type": "public-key",
                "response": {"clientDataJSON": b64url(client_data),
                             "attestationObject": b64url(attestation)}}

    def assert_(self, options: dict) -> dict:
        auth_data = self._auth_data(0x05)  # UP | UV (fingerprint)
        client_data = self._client_data("webauthn.get", options["challenge"])
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(),
                                  ec.ECDSA(hashes.SHA256()))
        cred_id = b64url(self.credential_id)
        return {"id": cred_id, "rawId": cred_id, "type": "public-key",
                "response": {"clientDataJSON": b64url(client_data),
                             "authenticatorData": b64url(auth_data),
                             "signature": b64url(signature), "userHandle": b64url(b"u-ghanshyam")}}
