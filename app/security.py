"""
Password hashing + reversible encryption for API secrets.

- Passwords: bcrypt (one-way hash; never reversible)
- Vidu API keys: Fernet (AES) so they can be decrypted for live API calls
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from dotenv import set_key

from app.config import ENV_PATH


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            (password_hash or "").encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def _persist_env(key: str, value: str) -> None:
    try:
        set_key(ENV_PATH, key, value)
    except Exception:
        pass
    os.environ[key] = value


def session_secret() -> str:
    """Signed cookie secret for SessionMiddleware."""
    existing = (os.getenv("AUTH_SECRET_KEY") or "").strip()
    if existing:
        return existing
    generated = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    _persist_env("AUTH_SECRET_KEY", generated)
    return generated


def _fernet_key() -> bytes:
    raw = (os.getenv("SECRET_ENCRYPTION_KEY") or "").strip()
    if raw:
        try:
            # Accept either a Fernet key or any passphrase (derive).
            if len(raw) == 44 and raw.endswith("="):
                return raw.encode("ascii")
            digest = hashlib.sha256(raw.encode("utf-8")).digest()
            return base64.urlsafe_b64encode(digest)
        except Exception:
            pass
    generated = Fernet.generate_key().decode("ascii")
    _persist_env("SECRET_ENCRYPTION_KEY", generated)
    return generated.encode("ascii")


def _fernet() -> Fernet:
    return Fernet(_fernet_key())


def encrypt_secret(plaintext: str) -> str:
    value = (plaintext or "").strip()
    if not value:
        return ""
    token = _fernet().encrypt(value.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        return ""
    try:
        return _fernet().decrypt(raw.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


def mask_secret(value: Optional[str], keep: int = 4) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= keep:
        return "•" * len(text)
    return ("•" * max(8, len(text) - keep)) + text[-keep:]
