"""
User accounts + per-user settings (encrypted Vidu credentials).
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.db import get_conn, init_db
from app.auth.security import (
    decrypt_secret,
    encrypt_secret,
    hash_password,
    mask_secret,
    verify_password,
)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class User:
    id: int
    email: str
    display_name: str
    created_at: float
    updated_at: float

    @property
    def name(self) -> str:
        return (self.display_name or "").strip() or self.email.split("@")[0]


@dataclass
class UserSettings:
    user_id: int
    vidu_api_key_enc: str = ""
    vidu_email: str = ""
    vidu_model: str = ""
    vidu_reference_model: str = ""
    vidu_resolution: str = ""
    telegram_bot_token_enc: str = ""
    telegram_chat_id: str = ""
    telegram_enabled: bool = False
    notify_hitl: bool = True
    notify_errors: bool = True
    notify_published: bool = True
    openai_api_key_enc: str = ""
    openai_model: str = ""
    updated_at: float = 0.0

    @property
    def has_vidu_key(self) -> bool:
        return bool(self.vidu_api_key_enc)

    def decrypted_vidu_key(self) -> str:
        return decrypt_secret(self.vidu_api_key_enc)

    @property
    def has_telegram_bot_token(self) -> bool:
        return bool(self.telegram_bot_token_enc)

    def decrypted_telegram_bot_token(self) -> str:
        return decrypt_secret(self.telegram_bot_token_enc)

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key_enc)

    def decrypted_openai_key(self) -> str:
        return decrypt_secret(self.openai_api_key_enc)


def ensure_auth_ready() -> None:
    init_db()


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_signup(email: str, password: str, display_name: str = "") -> Optional[str]:
    email_n = normalize_email(email)
    if not email_n or not _EMAIL_RE.match(email_n):
        return "Enter a valid email address."
    if len((password or "").strip()) < 8:
        return "Password must be at least 8 characters."
    if len((display_name or "").strip()) > 80:
        return "Display name is too long."
    return None


def _row_user(row: Any) -> User:
    return User(
        id=int(row["id"]),
        email=str(row["email"]),
        display_name=str(row["display_name"] or ""),
        created_at=float(row["created_at"] or 0),
        updated_at=float(row["updated_at"] or 0),
    )


def get_user_by_id(user_id: int) -> Optional[User]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
    return _row_user(row) if row else None


def get_user_by_email(email: str) -> Optional[User]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (normalize_email(email),),
        ).fetchone()
    return _row_user(row) if row else None


def _insert_user(email: str, password: str, display_name: str = "") -> User:
    email_n = normalize_email(email)
    now = time.time()
    name = (display_name or "").strip() or email_n.split("@")[0]
    pw_hash = hash_password(password)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO users (email, password_hash, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (email_n, pw_hash, name, now, now),
        )
        user_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO user_settings (user_id, updated_at)
            VALUES (?, ?)
            """,
            (user_id, now),
        )
    user = get_user_by_id(user_id)
    if not user:
        raise RuntimeError("Failed to create user.")
    return user


def create_user(email: str, password: str, display_name: str = "") -> User:
    ensure_auth_ready()
    err = validate_signup(email, password, display_name)
    if err:
        raise ValueError(err)
    email_n = normalize_email(email)
    if get_user_by_email(email_n):
        raise ValueError("An account with that email already exists.")
    return _insert_user(email_n, password, display_name)


def authenticate(email: str, password: str) -> Optional[User]:
    ensure_auth_ready()
    email_n = normalize_email(email)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email_n,),
        ).fetchone()
    if not row:
        return None
    if not verify_password(password, str(row["password_hash"])):
        return None
    return _row_user(row)


def update_profile(user_id: int, *, display_name: Optional[str] = None, email: Optional[str] = None) -> User:
    user = get_user_by_id(user_id)
    if not user:
        raise ValueError("User not found.")
    new_name = user.display_name
    new_email = user.email
    if display_name is not None:
        cleaned = display_name.strip()
        if not cleaned:
            raise ValueError("Display name cannot be empty.")
        if len(cleaned) > 80:
            raise ValueError("Display name is too long.")
        new_name = cleaned
    if email is not None:
        cleaned = normalize_email(email)
        if not _EMAIL_RE.match(cleaned):
            raise ValueError("Enter a valid email address.")
        existing = get_user_by_email(cleaned)
        if existing and existing.id != user_id:
            raise ValueError("That email is already in use.")
        new_email = cleaned
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE users
            SET display_name = ?, email = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_name, new_email, now, int(user_id)),
        )
    updated = get_user_by_id(user_id)
    if not updated:
        raise RuntimeError("Failed to update profile.")
    return updated


def change_password(user_id: int, current_password: str, new_password: str) -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
    if not row:
        raise ValueError("User not found.")
    if not verify_password(current_password, str(row["password_hash"])):
        raise ValueError("Current password is incorrect.")
    if len((new_password or "").strip()) < 8:
        raise ValueError("New password must be at least 8 characters.")
    now = time.time()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?
            """,
            (hash_password(new_password), now, int(user_id)),
        )


def get_settings(user_id: int) -> UserSettings:
    ensure_auth_ready()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?",
            (int(user_id),),
        ).fetchone()
        if not row:
            now = time.time()
            conn.execute(
                "INSERT INTO user_settings (user_id, updated_at) VALUES (?, ?)",
                (int(user_id), now),
            )
            return UserSettings(user_id=int(user_id), updated_at=now)
    return UserSettings(
        user_id=int(row["user_id"]),
        vidu_api_key_enc=str(row.get("vidu_api_key_enc") or ""),
        vidu_email=str(row.get("vidu_email") or ""),
        vidu_model=str(row.get("vidu_model") or ""),
        vidu_reference_model=str(row.get("vidu_reference_model") or ""),
        vidu_resolution=str(row.get("vidu_resolution") or ""),
        telegram_bot_token_enc=str(row.get("telegram_bot_token_enc") or ""),
        telegram_chat_id=str(row.get("telegram_chat_id") or ""),
        telegram_enabled=bool(row.get("telegram_enabled")),
        notify_hitl=True if row.get("notify_hitl") is None else bool(row.get("notify_hitl")),
        notify_errors=True if row.get("notify_errors") is None else bool(row.get("notify_errors")),
        notify_published=True if row.get("notify_published") is None else bool(row.get("notify_published")),
        openai_api_key_enc=str(row.get("openai_api_key_enc") or ""),
        openai_model=str(row.get("openai_model") or ""),
        updated_at=float(row.get("updated_at") or 0),
    )


def update_vidu_settings(
    user_id: int,
    *,
    api_key: Optional[str] = None,
    clear_api_key: bool = False,
    vidu_email: Optional[str] = None,
    model: Optional[str] = None,
    reference_model: Optional[str] = None,
    resolution: Optional[str] = None,
) -> UserSettings:
    settings = get_settings(user_id)
    now = time.time()
    enc = settings.vidu_api_key_enc
    email = settings.vidu_email
    vidu_model = settings.vidu_model
    ref_model = settings.vidu_reference_model
    res = settings.vidu_resolution

    if clear_api_key:
        enc = ""
    elif api_key is not None:
        cleaned = api_key.strip()
        if cleaned:
            enc = encrypt_secret(cleaned)

    if vidu_email is not None:
        email = vidu_email.strip()
    if model is not None:
        vidu_model = model.strip()
    if reference_model is not None:
        ref_model = reference_model.strip()
    if resolution is not None:
        res = resolution.strip()

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE user_settings
            SET vidu_api_key_enc = ?,
                vidu_email = ?,
                vidu_model = ?,
                vidu_reference_model = ?,
                vidu_resolution = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (enc, email, vidu_model, ref_model, res, now, int(user_id)),
        )
    return get_settings(user_id)


def update_notification_settings(
    user_id: int,
    *,
    bot_token: Optional[str] = None,
    clear_bot_token: bool = False,
    chat_id: Optional[str] = None,
    telegram_enabled: Optional[bool] = None,
    notify_hitl: Optional[bool] = None,
    notify_errors: Optional[bool] = None,
    notify_published: Optional[bool] = None,
) -> UserSettings:
    settings = get_settings(user_id)
    now = time.time()
    token_enc = settings.telegram_bot_token_enc
    cid = settings.telegram_chat_id
    tg_enabled = settings.telegram_enabled
    n_hitl = settings.notify_hitl
    n_err = settings.notify_errors
    n_pub = settings.notify_published

    if clear_bot_token:
        token_enc = ""
    elif bot_token is not None:
        cleaned = bot_token.strip()
        if cleaned:
            token_enc = encrypt_secret(cleaned)

    if chat_id is not None:
        cid = chat_id.strip()
    if telegram_enabled is not None:
        tg_enabled = bool(telegram_enabled)
    if notify_hitl is not None:
        n_hitl = bool(notify_hitl)
    if notify_errors is not None:
        n_err = bool(notify_errors)
    if notify_published is not None:
        n_pub = bool(notify_published)

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE user_settings
            SET telegram_bot_token_enc = ?,
                telegram_chat_id = ?,
                telegram_enabled = ?,
                notify_hitl = ?,
                notify_errors = ?,
                notify_published = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (token_enc, cid, tg_enabled, n_hitl, n_err, n_pub, now, int(user_id)),
        )
    return get_settings(user_id)


def update_openai_settings(
    user_id: int,
    *,
    api_key: Optional[str] = None,
    clear_api_key: bool = False,
    model: Optional[str] = None,
) -> UserSettings:
    settings = get_settings(user_id)
    now = time.time()
    enc = settings.openai_api_key_enc
    openai_model = settings.openai_model

    if clear_api_key:
        enc = ""
    elif api_key is not None:
        cleaned = api_key.strip()
        if cleaned:
            enc = encrypt_secret(cleaned)

    if model is not None:
        openai_model = model.strip()

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE user_settings
            SET openai_api_key_enc = ?,
                openai_model = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (enc, openai_model, now, int(user_id)),
        )
    return get_settings(user_id)


def settings_public_view(settings: UserSettings) -> Dict[str, Any]:
    plaintext = settings.decrypted_vidu_key()
    plaintext_tg = settings.decrypted_telegram_bot_token()
    plaintext_openai = settings.decrypted_openai_key()
    return {
        "has_vidu_key": settings.has_vidu_key,
        "vidu_key_masked": mask_secret(plaintext) if plaintext else "",
        "vidu_email": settings.vidu_email,
        "vidu_model": settings.vidu_model,
        "vidu_reference_model": settings.vidu_reference_model,
        "vidu_resolution": settings.vidu_resolution,
        "has_telegram_bot_token": settings.has_telegram_bot_token,
        "telegram_bot_token_masked": mask_secret(plaintext_tg) if plaintext_tg else "",
        "telegram_chat_id": settings.telegram_chat_id,
        "telegram_enabled": settings.telegram_enabled,
        "notify_hitl": settings.notify_hitl,
        "notify_errors": settings.notify_errors,
        "notify_published": settings.notify_published,
        "has_openai_key": settings.has_openai_key,
        "openai_key_masked": mask_secret(plaintext_openai) if plaintext_openai else "",
        "openai_model": settings.openai_model,
    }


def apply_user_credentials_to_config(user_id: int) -> None:
    """Load this user's encrypted Vidu & OpenAI keys into the live process config."""
    from app.config import config

    settings = get_settings(user_id)
    key = settings.decrypted_vidu_key()
    if key:
        config.vidu_api_key = key
    if settings.vidu_email:
        config.vidu_email = settings.vidu_email
    if settings.vidu_model:
        config.vidu_model = settings.vidu_model
    if settings.vidu_reference_model:
        config.vidu_reference_model = settings.vidu_reference_model
    if settings.vidu_resolution:
        config.vidu_resolution = settings.vidu_resolution

    key_openai = settings.decrypted_openai_key()
    if key_openai:
        config.openai_api_key = key_openai
        os.environ["OPENAI_API_KEY"] = key_openai
    else:
        env_key = os.getenv("OPENAI_API_KEY", "")
        if env_key:
            config.openai_api_key = env_key
            os.environ["OPENAI_API_KEY"] = env_key

    if settings.openai_model:
        config.openai_model = settings.openai_model
        os.environ["OPENAI_MODEL"] = settings.openai_model
    else:
        env_model = os.getenv("OPENAI_MODEL", "gpt-6-luna")
        config.openai_model = env_model
        os.environ["OPENAI_MODEL"] = env_model
