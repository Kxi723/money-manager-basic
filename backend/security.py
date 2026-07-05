"""
Security helpers that behave differently per mode: password hashing,
session tokens, field encryption, and login rate limiting
"""
import base64
import hashlib
import os
import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import config
from config import (
    AES_KEY,
    JWT_ALG,
    JWT_SECRET,
    JWT_TTL_SECONDS,
    LOCKOUT_SECONDS,
    MAX_FAILED_LOGINS,
)

# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
_ph = PasswordHasher()  # Called Argon2id

def hash_password(plain: str) -> str:
    if config.is_secure():
        # Argon2id, per-user salt + tunable cost
        # E.g. "$argon2id$v=19$m=65536,t=3,p=4$1ouOY0+OhtRfNQgwmLN4wg$G0PD9DhGOBYeGzKNT77B6rz4ixo0j+Jp6iWTJS01i4g"
        return _ph.hash(plain)

    # Bare unsalted SHA-1. Trivially reversible via rainbow tables
    # and identical for identical passwords.
    # E.g. "sha1$7c4a8d09ca3762af61e59520943dc26494f8941b"
    return "sha1$" + hashlib.sha1(plain.encode()).hexdigest()


def verify_password(plain: str, stored: str) -> bool:
    if config.is_secure():
        try:
            # Argon2 verify
            return _ph.verify(stored, plain)
        except VerifyMismatchError:
            return False
        except Exception:
            return False

    # Recompute the same weak hash and compare
    return stored == "sha1$" + hashlib.sha1(plain.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Session tokens
# ---------------------------------------------------------------------------
def issue_token(user_id: int, username: str) -> str:
    if config.is_secure():
        # Signed with Json Web Token
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "username": username,
            "iat": now, 
            "exp": now + JWT_TTL_SECONDS,
        }
        # E.g. "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzIiwidXNlcm5hbWUiOiJhcHUiLCJpYXQiOjE3ODI2NTk3MzYsImV4cCI6MTc4MjY2MzMzNn0.wtPycK6ApGSAs0UmxNhMIgalTp1Hk1s3PkxUmrYolbQ"
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

    # Return user id in base64, which is unsigned and forgeable
    # E.g. "Mw=="
    return base64.urlsafe_b64encode(str(user_id).encode()).decode()


def read_token(token: str) -> int | None:
    """Return the authenticated user id, or None if the token is invalid."""
    if not token:
        return None

    if config.is_secure():
        # Verify signature + expiry before trusting any claim
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
            # "sub" claim is user_id
            return int(payload["sub"])
        except Exception:
            return None

    # Trust whatever the client sends
    try:
        return int(base64.urlsafe_b64decode(token.encode()).decode())
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Data Encryption 
# ---------------------------------------------------------------------------
def _get_aes_key() -> bytes:
    raw = AES_KEY.strip()
    try:
        if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
            # Return 32 bytes key for AES-256-GCM
            return bytes.fromhex(raw)
        return base64.b64decode(raw)
    except Exception as exc:
        raise SystemExit(f"AES_KEY is not valid hex or base64: {exc}")


def encrypt_field(plaintext: str) -> str:
    """Encrypt a sensitive field for storage"""
    if not config.is_secure():
        # Stored every data in plain text.
        return plaintext

    key = _get_aes_key()
    if len(key) != 32:
        raise SystemExit("AES_KEY must decode to exactly 32 bytes for AES-256.")

    # "Nonce" is a random value that must never be reused with the same key. "Number used once"
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)

    # E.g. "7gDu1Zx2LZro6KSXS3enQnnvQF3KgS4la0YwOe3/RF2R"
    return base64.b64encode(nonce + ct).decode()


def decrypt_field(stored: str) -> str:
    """Inverse of encrypt_field for display"""
    if not config.is_secure():
        # never encrypted, return original
        return stored

    key = _get_aes_key()
    blob = base64.b64decode(stored.encode())
    
    # Split nonce off the front, authenticate + decrypt.
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()


# ---------------------------------------------------------------------------
# Login rate limiting
# ---------------------------------------------------------------------------
_failures: dict[str, list] = {}  # username -> [count, locked_until_epoch]

def is_locked(username: str) -> int:
    """Return remaining lockout seconds (0 if not locked)"""
    if not config.is_secure():
        return 0

    record = _failures.get(username)
    if not record:
        return 0
    remaining = int(record[1] - time.time())
    return remaining if remaining > 0 else 0


def record_failure(username: str) -> None:
    if not config.is_secure():
        return
    
    record = _failures.setdefault(username, [0, 0])
    record[0] += 1
    if record[0] >= MAX_FAILED_LOGINS:
        record[1] = time.time() + LOCKOUT_SECONDS
        record[0] = 0


def record_success(username: str) -> None:
    _failures.pop(username, None)
