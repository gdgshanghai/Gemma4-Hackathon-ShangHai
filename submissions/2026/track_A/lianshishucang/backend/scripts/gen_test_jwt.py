#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import time

JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-key-change-in-production").encode()
USER_ID = int(os.getenv("TEST_USER_ID", "2"))
WALLET_ADDRESS = os.getenv("TEST_WALLET_ADDRESS", "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266")
EXPIRES_IN_SECONDS = int(os.getenv("TEST_TOKEN_TTL", str(3600 * 24 * 365)))

header = {
    "alg": "HS256",
    "typ": "JWT",
}

payload = {
    "user_id": USER_ID,
    "wallet_address": WALLET_ADDRESS,
    "exp": int(time.time()) + EXPIRES_IN_SECONDS,
    "iat": int(time.time()),
}


def b64(obj):
    raw = json.dumps(obj, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=")

segments = [b64(header), b64(payload)]
signing_input = b".".join(segments)
sig = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
segments.append(base64.urlsafe_b64encode(sig).rstrip(b"="))

print(b".".join(segments).decode())
