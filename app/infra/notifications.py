"""
Real-time mobile push notifications and Telegram Bot integration for Crash Out.
Dispatches instant alerts for HITL approval gates, system errors/SLA alerts, and live publishing confirmations.
Includes persistent storage in PostgreSQL and offline graceful fallbacks.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple

from app.db import get_conn

logger = logging.getLogger("app.notifications")

# Base URL for deep links back to the admin portal
DEFAULT_ADMIN_BASE = "https://admin.crashout.tv"


def get_admin_base_url() -> str:
    """Return the base URL used for deep-links in mobile push notifications."""
    raw = (os.getenv("ADMIN_BASE_URL") or os.getenv("CRASHOUT_BASE_URL") or DEFAULT_ADMIN_BASE).strip()
    return raw.rstrip("/")


def build_full_deep_link(relative_path: str) -> str:
    """Format an absolute deep-link to the target admin screen."""
    path = relative_path.strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return f"{get_admin_base_url()}{path}"


# ---------------------------------------------------------------------------
# Telegram Bot API Dispatcher
# ---------------------------------------------------------------------------

def send_telegram_message_sync(
    bot_token: str,
    chat_id: str,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    timeout_sec: float = 5.0,
) -> Tuple[bool, str]:
    """
    Send an HTML-formatted message to Telegram Bot API synchronously.
    Returns (success: bool, detail_message: str).
    """
    token = (bot_token or "").strip()
    cid = (chat_id or "").strip()

    if not token or not cid:
        return False, "Telegram bot token or chat ID is missing."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": cid,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            resp_body = resp.read().decode("utf-8")
            res = json.loads(resp_body)
            if res.get("ok"):
                return True, "Telegram message delivered successfully."
            else:
                desc = res.get("description", "Unknown Telegram error")
                return False, f"Telegram API error: {desc}"
    except urllib.error.HTTPError as exc:
        err_msg = f"HTTP {exc.code}: {exc.reason}"
        try:
            body = exc.read().decode("utf-8")
            data = json.loads(body)
            if "description" in data:
                err_msg = data["description"]
        except Exception:
            pass
        logger.warning("Telegram HTTP error: %s", err_msg)
        return False, f"Telegram error: {err_msg}"
    except urllib.error.URLError as exc:
        logger.warning("Telegram network failure (offline fallback): %s", exc.reason)
        return False, f"Network connection failed: {exc.reason}"
    except Exception as exc:
        logger.warning("Telegram dispatch unexpected error: %s", exc)
        return False, f"Unexpected error: {exc}"


def test_telegram_connection(bot_token: str, chat_id: str) -> Tuple[bool, str]:
    """Send an immediate test alert to verify Telegram bot setup."""
    admin_url = get_admin_base_url()
    test_text = (
        "🤖 <b>Crash Out Studio — Telegram Push Test</b>\n\n"
        "✅ <b>Connection Verified!</b>\n"
        "Your Telegram Bot integration is successfully linked to <b>admin.crashout.tv</b>.\n\n"
        "You will receive instant alerts for:\n"
        "• ✋ <b>HITL Approval Gates</b> (Pitches, Scripts, Video QA)\n"
        "• 🚨 <b>Critical Errors & SLA Breaches</b>\n"
        "• 🚀 <b>Live Episode Publishing</b> (YouTube, TikTok, IG)\n\n"
        f"🔗 <a href=\"{admin_url}/settings\">Open Settings</a>"
    )
    markup = {
        "inline_keyboard": [
            [{"text": "🖥️ Open Admin Dashboard", "url": admin_url}],
            [{"text": "🔔 View Notifications", "url": f"{admin_url}/notifications"}],
        ]
    }
    return send_telegram_message_sync(bot_token, chat_id, test_text, reply_markup=markup, timeout_sec=6.0)


def detect_telegram_chat_id(bot_token: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Query getUpdates from Telegram Bot API to automatically detect the user's Chat ID.
    Returns (chat_id, sender_name, error_message).
    """
    token = (bot_token or "").strip()
    if not token:
        return None, None, "Telegram Bot Token is missing."

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CrashOut/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                return None, None, f"Telegram API error: {data.get('description', 'Unknown error')}"

            results = data.get("result") or []
            if not results:
                return None, None, "No messages found yet. Please open t.me/CrashhOut_bot on your phone/desktop and tap 'Start' or send any message."

            # Find the most recent message with a valid chat object
            for update in reversed(results):
                msg = update.get("message") or update.get("channel_post") or update.get("my_chat_member")
                if msg and "chat" in msg:
                    cid = str(msg["chat"]["id"])
                    sender = (
                        msg.get("from", {}).get("username")
                        or msg.get("from", {}).get("first_name")
                        or msg["chat"].get("title")
                        or "Telegram User"
                    )
                    return cid, sender, None

            return None, None, "Could not locate chat details in Telegram updates. Send a message to the bot and try again."
    except urllib.error.HTTPError as exc:
        return None, None, f"Telegram HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        return None, None, f"Network error connecting to Telegram: {exc.reason}"
    except Exception as exc:
        return None, None, f"Error detecting chat ID: {exc}"


# ---------------------------------------------------------------------------
# Database Storage & Query Helpers
# ---------------------------------------------------------------------------

def create_notification(
    category: str,
    title: str,
    message: str,
    *,
    deep_link: str = "",
    user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    telegram_sent: bool = False,
) -> Optional[int]:
    """Insert a notification entry into PostgreSQL."""
    try:
        meta_json = json.dumps(metadata or {})
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO notifications (
                    user_id, category, title, message, deep_link, metadata,
                    is_read, telegram_sent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?::jsonb, FALSE, ?, NOW())
                RETURNING id
                """,
                (user_id, category, title, message, deep_link, meta_json, bool(telegram_sent)),
            )
            row = cursor.fetchone()
            return int(row["id"]) if row else None
    except Exception as exc:
        logger.warning("Could not persist notification in PostgreSQL: %s", exc)
        return None


def get_unread_notifications_count(user_id: Optional[int] = None) -> int:
    """Return count of unread notifications for a user (or system-wide if user_id is None)."""
    try:
        with get_conn() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM notifications WHERE (user_id = ? OR user_id IS NULL) AND is_read = FALSE",
                    (int(user_id),),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM notifications WHERE is_read = FALSE"
                ).fetchone()
            return int(row["cnt"]) if row else 0
    except Exception as exc:
        logger.warning("Could not count unread notifications: %s", exc)
        return 0


def list_notifications(
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Retrieve paginated notifications with category filtering and unread count."""
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 20)))
    offset = (page - 1) * page_size

    filters = []
    params: List[Any] = []

    if user_id:
        filters.append("(user_id = ? OR user_id IS NULL)")
        params.append(int(user_id))

    if category and category.lower() != "all":
        filters.append("LOWER(category) = ?")
        params.append(category.lower().strip())

    if unread_only:
        filters.append("is_read = FALSE")

    where_clause = ("WHERE " + " AND ".join(filters)) if filters else ""

    try:
        with get_conn() as conn:
            # Total matching count
            count_query = f"SELECT COUNT(*) as cnt FROM notifications {where_clause}"
            c_row = conn.execute(count_query, tuple(params)).fetchone()
            total_items = int(c_row["cnt"]) if c_row else 0

            # Fetch page items
            query = f"""
                SELECT id, user_id, category, title, message, deep_link,
                       metadata, is_read, telegram_sent, created_at
                FROM notifications
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            item_params = list(params) + [page_size, offset]
            rows = conn.execute(query, tuple(item_params)).fetchall()

            items = []
            now = time.time()
            for r in rows:
                item = dict(r)
                # Parse created_at display
                ts = item.get("created_at")
                if hasattr(ts, "timestamp"):
                    created_sec = ts.timestamp()
                else:
                    created_sec = now
                diff = max(0, int(now - created_sec))
                if diff < 60:
                    time_ago = f"{diff}s ago"
                elif diff < 3600:
                    time_ago = f"{diff // 60}m ago"
                elif diff < 86400:
                    time_ago = f"{diff // 3600}h ago"
                else:
                    time_ago = f"{diff // 86400}d ago"
                item["time_ago"] = time_ago
                item["created_at_str"] = str(ts)[:19] if ts else time.strftime("%Y-%m-%d %H:%M:%S")
                items.append(item)

            total_pages = max(1, (total_items + page_size - 1) // page_size)
            unread_count = get_unread_notifications_count(user_id=user_id)

            return {
                "items": items,
                "total_items": total_items,
                "current_page": page,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
                "prev_page": page - 1,
                "next_page": page + 1,
                "unread_count": unread_count,
            }
    except Exception as exc:
        logger.warning("Error listing notifications: %s", exc)
        return {
            "items": [],
            "total_items": 0,
            "current_page": 1,
            "total_pages": 1,
            "has_prev": False,
            "has_next": False,
            "unread_count": 0,
        }


def mark_notification_read(notification_id: int, user_id: Optional[int] = None) -> bool:
    """Mark a specific notification as read."""
    try:
        with get_conn() as conn:
            if user_id:
                conn.execute(
                    "UPDATE notifications SET is_read = TRUE WHERE id = ? AND (user_id = ? OR user_id IS NULL)",
                    (int(notification_id), int(user_id)),
                )
            else:
                conn.execute(
                    "UPDATE notifications SET is_read = TRUE WHERE id = ?",
                    (int(notification_id),),
                )
        return True
    except Exception as exc:
        logger.warning("Failed to mark notification %s read: %s", notification_id, exc)
        return False


def mark_all_notifications_read(user_id: Optional[int] = None) -> bool:
    """Mark all notifications as read."""
    try:
        with get_conn() as conn:
            if user_id:
                conn.execute(
                    "UPDATE notifications SET is_read = TRUE WHERE (user_id = ? OR user_id IS NULL)",
                    (int(user_id),),
                )
            else:
                conn.execute("UPDATE notifications SET is_read = TRUE")
        return True
    except Exception as exc:
        logger.warning("Failed to mark all notifications read: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Notification Dispatcher with User Preferences & Async Telegram Trigger
# ---------------------------------------------------------------------------

def _resolve_telegram_recipients(
    category: str,
    explicit_user_id: Optional[int] = None,
) -> List[Tuple[int, str, str]]:
    """
    Find users who have Telegram enabled and have opted into this category.
    Returns list of (user_id, bot_token, chat_id).
    """
    from app.auth.users import get_settings

    recipients: List[Tuple[int, str, str]] = []

    # If specific user target
    if explicit_user_id:
        try:
            settings = get_settings(explicit_user_id)
            if settings.telegram_enabled and settings.telegram_chat_id:
                token = settings.decrypted_telegram_bot_token() or os.getenv("TELEGRAM_BOT_TOKEN", "")
                if token:
                    allowed = False
                    if category == "hitl" and settings.notify_hitl:
                        allowed = True
                    elif category == "error" and settings.notify_errors:
                        allowed = True
                    elif category == "published" and settings.notify_published:
                        allowed = True
                    elif category == "system":
                        allowed = True
                    if allowed:
                        recipients.append((explicit_user_id, token, settings.telegram_chat_id))
        except Exception as exc:
            logger.warning("Error resolving user %s settings: %s", explicit_user_id, exc)
        return recipients

    # Check database for all users with telegram_enabled
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT user_id, telegram_bot_token_enc, telegram_chat_id,
                       notify_hitl, notify_errors, notify_published
                FROM user_settings
                WHERE telegram_enabled = TRUE AND telegram_chat_id != ''
                """
            ).fetchall()

            for row in rows:
                uid = int(row["user_id"])
                settings = get_settings(uid)
                token = settings.decrypted_telegram_bot_token() or os.getenv("TELEGRAM_BOT_TOKEN", "")
                cid = str(row["telegram_chat_id"] or "").strip()
                if not token or not cid:
                    continue

                allowed = False
                if category == "hitl" and row["notify_hitl"]:
                    allowed = True
                elif category == "error" and row["notify_errors"]:
                    allowed = True
                elif category == "published" and row["notify_published"]:
                    allowed = True
                elif category == "system":
                    allowed = True

                if allowed:
                    recipients.append((uid, token, cid))
    except Exception as exc:
        logger.warning("Error fetching telegram enabled users: %s", exc)

    # Fallback: Environment variable TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID
    if not recipients:
        env_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        env_cid = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if env_token and env_cid:
            recipients.append((0, env_token, env_cid))

    return recipients


def dispatch_push_notification(
    category: str,
    title: str,
    message: str,
    *,
    deep_link: str = "",
    user_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
    telegram_html: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """
    Main dispatch entry point:
    1. Persists notification to PostgreSQL.
    2. Resolves eligible Telegram users according to their notification toggles.
    3. Asynchronously sends push notification to Telegram so it never blocks the caller.
    """
    full_deep_link = build_full_deep_link(deep_link) if deep_link else ""
    meta = metadata or {}
    meta["full_deep_link"] = full_deep_link

    # 1. Persist notification to DB first
    notif_id = create_notification(
        category=category,
        title=title,
        message=message,
        deep_link=deep_link,
        user_id=user_id,
        metadata=meta,
        telegram_sent=False,
    )

    # 2. Check if Telegram recipients exist
    recipients = _resolve_telegram_recipients(category, explicit_user_id=user_id)
    if not recipients:
        return notif_id

    # 3. Format Telegram text
    if not telegram_html:
        cat_tag = "🔔 <b>NOTIFICATION</b>"
        if category == "hitl":
            cat_tag = "✋ <b>HITL APPROVAL GATE</b>"
        elif category == "error":
            cat_tag = "🚨 <b>CRITICAL ERROR & SLA ALERT</b>"
        elif category == "published":
            cat_tag = "🚀 <b>EPISODE PUBLISHED LIVE</b>"

        telegram_html = (
            f"{cat_tag}\n\n"
            f"<b>{title}</b>\n\n"
            f"{message}\n\n"
        )
        if full_deep_link:
            telegram_html += f"🔗 <a href=\"{full_deep_link}\">Open in Crash Out Studio</a>"

    # Default button if not provided and deep link exists
    if not reply_markup and full_deep_link:
        btn_label = "Open Screen 👉"
        if category == "hitl":
            btn_label = "Review Approval Gate 👉"
        elif category == "error":
            btn_label = "Inspect Error Board 👉"
        elif category == "published":
            btn_label = "View Episode Live 👉"

        reply_markup = {
            "inline_keyboard": [
                [{"text": btn_label, "url": full_deep_link}]
            ]
        }

    # 4. Dispatch asynchronously in background thread
    def _async_send():
        sent_any = False
        for uid, tok, cid in recipients:
            ok, err = send_telegram_message_sync(tok, cid, telegram_html, reply_markup=reply_markup)
            if ok:
                sent_any = True
            else:
                logger.warning("Telegram failed for user %s: %s", uid, err)

        if sent_any and notif_id:
            try:
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE notifications SET telegram_sent = TRUE WHERE id = ?",
                        (int(notif_id),),
                    )
            except Exception:
                pass

    thread = threading.Thread(target=_async_send, daemon=True, name="telegram-push-worker")
    thread.start()

    return notif_id


# ---------------------------------------------------------------------------
# High-Level Automatic Pipeline Triggers
# ---------------------------------------------------------------------------

def notify_hitl_gate(
    episode_id: str,
    gateway_num: int,
    title: str,
    *,
    summary: str = "",
    user_id: Optional[int] = None,
) -> Optional[int]:
    """
    Trigger 1: HITL Approval Gate alert when an episode is waiting for manual approval.
    (Pitch Card batch, Script/Audio, Video QA, Merch, Publishing Sign-Off).
    """
    gw_names = {
        1: "Gate 1: Trend Pitch Selection",
        2: "Gate 2: Script & Audio Review",
        3: "Gate 3: Master 9:16 Video Review",
        4: "Gate 4: Merch & Distribution Package",
        5: "Gate 5: Guerrilla Seeding Sign-Off",
    }
    stage_map = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    gw_title = gw_names.get(gateway_num, f"Gateway {gateway_num}")
    stage = stage_map.get(gateway_num, 1)

    heading = f"✋ {gw_title} Waiting for Approval"
    msg_body = (
        f"Episode: <b>\"{title}\"</b> (ID: <code>{episode_id}</code>)\n"
        f"Stage: <b>Stage {stage}</b>\n"
        f"Details: {summary or 'New assets generated and waiting for your manual review and approval.'}"
    )

    deep_link = f"/studio?stage={stage}&episode={episode_id}"
    full_url = build_full_deep_link(deep_link)

    tg_html = (
        f"✋ <b>HITL APPROVAL GATE REQUIRED</b>\n\n"
        f"<b>{gw_title}</b>\n"
        f"🎬 Episode: <b>\"{title}\"</b>\n\n"
        f"📝 <i>{summary or 'Assets are ready for your review.'}</i>\n\n"
        f"⏱️ SLA timer running. Tap below to review & approve:"
    )

    markup = {
        "inline_keyboard": [
            [{"text": f"Review {gw_title} 👉", "url": full_url}],
            [{"text": "Agent M Overview", "url": build_full_deep_link("/agent-m")}],
        ]
    }

    return dispatch_push_notification(
        category="hitl",
        title=heading,
        message=f"Episode '{title}' is waiting for sign-off at {gw_title}. {summary}",
        deep_link=deep_link,
        user_id=user_id,
        metadata={"episode_id": episode_id, "gateway_num": gateway_num, "stage": stage},
        telegram_html=tg_html,
        reply_markup=markup,
    )


def notify_critical_error(
    task_name: str,
    error_message: str,
    *,
    episode_id: Optional[str] = None,
    category: str = "System Incident",
    retry_count: int = 0,
    user_id: Optional[int] = None,
) -> Optional[int]:
    """
    Trigger 2: Critical Errors & SLA Alerts when an agent fails, API outage occurs,
    or a task exceeds retry limits.
    """
    heading = f"🚨 Critical Error: {task_name}"
    msg_body = (
        f"Task: <b>{task_name}</b>\n"
        f"Component: <b>{category}</b>\n"
        f"Retries: <b>{retry_count}/3</b>\n"
        f"Error: <code>{error_message}</code>"
    )

    deep_link = "/agent-m#system-log-board"
    full_url = build_full_deep_link(deep_link)

    tg_html = (
        f"🚨 <b>CRITICAL SYSTEM ALERT / SLA BREACH</b>\n\n"
        f"⚠️ <b>{task_name}</b>\n"
        f"Component: <b>{category}</b>\n"
        f"Retries Exceeded: <b>{retry_count} attempt(s)</b>\n\n"
        f"❌ <b>Error:</b> <code>{error_message}</code>\n\n"
        f"Action required immediately to restore automated workflow."
    )

    markup = {
        "inline_keyboard": [
            [{"text": "🛠️ Open Incident Log & Retry 👉", "url": full_url}],
            [{"text": "📋 Per-Agent Tasks & Schedule", "url": build_full_deep_link("/tasks")}],
        ]
    }

    return dispatch_push_notification(
        category="error",
        title=heading,
        message=f"{task_name} failed: {error_message} (Retries: {retry_count})",
        deep_link=deep_link,
        user_id=user_id,
        metadata={
            "task_name": task_name,
            "error_message": error_message,
            "category": category,
            "retry_count": retry_count,
            "episode_id": episode_id,
        },
        telegram_html=tg_html,
        reply_markup=markup,
    )


def notify_episode_published(
    episode_id: str,
    title: str,
    *,
    youtube_url: str = "",
    tiktok_url: str = "",
    instagram_url: str = "",
    user_id: Optional[int] = None,
) -> Optional[int]:
    """
    Trigger 3: Confirmation alert with live links once an episode goes live on
    YouTube Shorts, TikTok, and Instagram Reels.
    """
    heading = f"🚀 Episode Published: \"{title}\""
    deep_link = f"/studio?stage=5&episode={episode_id}"

    tg_html = (
        f"🚀 <b>EPISODE PUBLISHED LIVE!</b>\n\n"
        f"🎉 <b>\"{title}\"</b> is now live across all platforms!\n\n"
        f"📺 <b>Live Distribution Links:</b>\n"
        f"• YouTube Shorts: {youtube_url or 'Live in Studio'}\n"
        f"• TikTok: {tiktok_url or 'Live in Studio'}\n"
        f"• Instagram Reels: {instagram_url or 'Live in Studio'}\n\n"
        f"Check engagement metrics and comments in the Studio."
    )

    buttons = []
    if youtube_url:
        buttons.append([{"text": "🔴 Watch on YouTube Shorts", "url": youtube_url}])
    if tiktok_url:
        buttons.append([{"text": "🎵 Watch on TikTok", "url": tiktok_url}])
    if instagram_url:
        buttons.append([{"text": "📸 Watch on Instagram Reels", "url": instagram_url}])
    buttons.append([{"text": "🎬 Open in Studio", "url": build_full_deep_link(deep_link)}])

    markup = {"inline_keyboard": buttons}

    return dispatch_push_notification(
        category="published",
        title=heading,
        message=f"Episode '{title}' was successfully published to YouTube Shorts, TikTok, and Instagram Reels.",
        deep_link=deep_link,
        user_id=user_id,
        metadata={
            "episode_id": episode_id,
            "title": title,
            "youtube_url": youtube_url,
            "tiktok_url": tiktok_url,
            "instagram_url": instagram_url,
        },
        telegram_html=tg_html,
        reply_markup=markup,
    )
