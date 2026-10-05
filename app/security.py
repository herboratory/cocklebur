from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from pathlib import Path

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)



RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def new_recovery_code(groups: int = 4, group_len: int = 5) -> str:
    return "-".join("".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(group_len)) for _ in range(groups))

def host_session_token(secret_key: str) -> str:
    return hmac.new(secret_key.encode("utf-8"), b"cocklebur-host-session-v1", hashlib.sha256).hexdigest()

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(token: str, expected_hash: str) -> bool:
    return hmac.compare_digest(token_hash(token), expected_hash or "")


def hash_pin(pin: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), 120_000)
    return f"pbkdf2_sha256$120000${salt}${dk.hex()}"


def verify_pin(pin: str, encoded: str | None) -> bool:
    if not encoded:
        return True
    try:
        algo, rounds, salt, digest = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


def safe_id(value: str, label: str = "id") -> str:
    if not SAFE_ID_RE.fullmatch(value or ""):
        raise ValueError(f"Invalid {label}")
    return value


def safe_filename(name: str) -> str:
    name = Path(name or "file").name.replace("\x00", "")
    name = re.sub(r"[^A-Za-z0-9._()\- ]+", "_", name).strip(" .")
    return (name[:180] or "file")
