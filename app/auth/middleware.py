"""
Session auth helpers + request middleware.

Public paths: login/signup/static assets. Everything else requires a session.

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) so it shares the
same Request/session scope as SessionMiddleware.
"""
from __future__ import annotations

from typing import Optional, Set
from urllib.parse import quote

from fastapi import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.auth.users import User, apply_user_credentials_to_config, get_user_by_id
from app.auth.security import create_access_token, decode_access_token

SESSION_USER_KEY = "user_id"
JWT_COOKIE_NAME = "crashout_jwt"
JWT_HEADER_PREFIX = "bearer "

PUBLIC_EXACT: Set[str] = {
    "/login",
    "/signup",
    "/logout",
    "/favicon.ico",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/system/health",
}

PUBLIC_PREFIXES = (
    "/static/",
    "/characters/",
    "/outputs/",
)


def is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def current_user_id(request: Request) -> Optional[int]:
    # 1. Check Authorization: Bearer <JWT>
    auth_header = request.headers.get("authorization") or ""
    if auth_header.lower().startswith(JWT_HEADER_PREFIX):
        token = auth_header[len(JWT_HEADER_PREFIX):].strip()
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            try:
                return int(payload["sub"])
            except (ValueError, TypeError):
                pass

    # 2. Check JWT cookie
    jwt_cookie = request.cookies.get(JWT_COOKIE_NAME)
    if jwt_cookie:
        payload = decode_access_token(jwt_cookie)
        if payload and payload.get("sub"):
            try:
                return int(payload["sub"])
            except (ValueError, TypeError):
                pass

    # 3. Fallback to session cookie
    raw = request.session.get(SESSION_USER_KEY)
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def get_current_user(request: Request) -> Optional[User]:
    cached = getattr(request.state, "user", None)
    if cached is not None:
        return cached
    uid = current_user_id(request)
    if uid is None:
        return None
    user = get_user_by_id(uid)
    request.state.user = user
    return user


def login_user(request: Request, user: User) -> str:
    """Logs in user, sets session, configures user creds, and returns signed JWT access token."""
    request.session.clear()
    request.session[SESSION_USER_KEY] = int(user.id)
    request.state.user = user
    apply_user_credentials_to_config(user.id)
    token = create_access_token(user_id=user.id, email=user.email)
    request.state.jwt_token = token
    return token


def logout_user(request: Request) -> None:
    request.session.clear()
    request.state.user = None
    request.state.jwt_token = None


def _wants_html(scope: Scope) -> bool:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    accept = (headers.get("accept") or "").lower()
    if headers.get("hx-request"):
        return True
    return "text/html" in accept or accept == "*/*" or not accept


class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if is_public_path(path):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        user = get_current_user(request)
        if user is not None:
            try:
                apply_user_credentials_to_config(user.id)
            except Exception:
                pass
            request.state.user = user
            await self.app(scope, receive, send)
            return

        query = scope.get("query_string", b"").decode("latin-1")
        next_url = path + (f"?{query}" if query else "")
        login_url = f"/login?next={quote(next_url, safe='')}"

        if _wants_html(scope):
            response: RedirectResponse | JSONResponse = RedirectResponse(
                url=login_url, status_code=303
            )
        else:
            response = JSONResponse(
                {"detail": "Authentication required", "login": "/login"},
                status_code=401,
            )
        await response(scope, receive, send)
