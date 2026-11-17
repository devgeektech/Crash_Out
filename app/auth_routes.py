"""
Login / signup / settings UI routes.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth_middleware import JWT_COOKIE_NAME, get_current_user, login_user, logout_user
from app.auth_users import (
    apply_user_credentials_to_config,
    authenticate,
    change_password,
    get_settings,
    settings_public_view,
    update_profile,
    update_vidu_settings,
)
from app.config import config
from app.engines.factory import engine_display_name, video_engine_mode
from app.engines.vidu_models import (
    VIDU_REFERENCE_MODELS,
    VIDU_RESOLUTIONS,
    VIDU_VIDEO_MODELS,
    options_with_current,
)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_CSS_PATH = os.path.join(os.path.dirname(__file__), "static", "css", "app.css")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def _static_cache_bust() -> str:
    try:
        return str(int(os.path.getmtime(STATIC_CSS_PATH)))
    except OSError:
        return "1"


def _get_total_credits_used() -> float:
    try:
        from app.state import state_manager
        from app.studio.generation import cost_summary

        total = 0.0
        for ep in state_manager.episodes.values():
            total += float(cost_summary(ep).get("total_credits") or 0.0)
        return round(total, 1)
    except Exception:
        return 0.0


templates.env.globals["static_cache_bust"] = _static_cache_bust
templates.env.globals["get_total_credits_used"] = _get_total_credits_used

router = APIRouter(tags=["auth"])


def _safe_next(raw: Optional[str]) -> str:
    value = unquote((raw or "").strip()) or "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    if value.startswith("/login") or value.startswith("/signup"):
        return "/"
    return value


def _auth_ctx(request: Request, page: str, **extra: Any) -> Dict[str, Any]:
    ctx = {
        "request": request,
        "page": page,
        "error": extra.pop("error", None),
        "toast": extra.pop("toast", None),
        "toast_kind": extra.pop("toast_kind", "info"),
        "next": extra.pop("next", "/"),
        "viewing_stage": 0,
    }
    ctx.update(extra)
    return ctx


def _settings_ctx(request: Request, **extra: Any) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user:
        return {}
    settings = get_settings(user.id)
    public = settings_public_view(settings)
    selected_model = public.get("vidu_model") or config.vidu_model or "viduq4-preview"
    selected_ref = (
        public.get("vidu_reference_model")
        or config.vidu_reference_model
        or selected_model
    )
    selected_res = public.get("vidu_resolution") or config.vidu_resolution or "720p"
    return {
        "request": request,
        "page": "settings",
        "user": user,
        "settings": public,
        "vidu_model_options": options_with_current(VIDU_VIDEO_MODELS, selected_model),
        "vidu_reference_model_options": options_with_current(
            VIDU_REFERENCE_MODELS, selected_ref
        ),
        "vidu_resolution_options": options_with_current(VIDU_RESOLUTIONS, selected_res),
        "selected_vidu_model": selected_model,
        "selected_vidu_reference_model": selected_ref,
        "selected_vidu_resolution": selected_res,
        "platform": {
            "video_engine": video_engine_mode(),
            "engine_name": engine_display_name(),
            "vidu_model": config.vidu_model,
            "vidu_has_key": bool(config.vidu_api_key) or public["has_vidu_key"],
        },
        "toast": extra.pop("toast", None),
        "toast_kind": extra.pop("toast_kind", "info"),
        "error": extra.pop("error", None),
        "viewing_stage": 0,
        "revision_notes": [],
        "production_statuses": [],
        "library_characters": [],
        "episode_list": [],
        **extra,
    }


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: Optional[str] = None):
    if get_current_user(request):
        return RedirectResponse(_safe_next(next), status_code=303)
    return templates.TemplateResponse(
        request,
        "auth_login.html",
        _auth_ctx(request, "login", next=_safe_next(next)),
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    user = authenticate(email, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "auth_login.html",
            _auth_ctx(
                request,
                "login",
                error="Invalid email or password.",
                next=_safe_next(next),
                email=email,
            ),
            status_code=400,
        )
    token = login_user(request, user)
    response = RedirectResponse(_safe_next(next), status_code=303)
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400 * 7,  # 7 days
    )
    return response


@router.post("/api/auth/token")
def api_auth_token(
    email: str = Form(...),
    password: str = Form(...),
):
    """API endpoint to obtain a JWT access token programmatically."""
    from fastapi import HTTPException

    user = authenticate(email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    from app.security import create_access_token

    token = create_access_token(user_id=user.id, email=user.email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name},
    }


@router.get("/signup")
@router.post("/signup")
def signup_removed(next: Optional[str] = None):
    """Signup is disabled — redirect to sign in."""
    target = _safe_next(next)
    q = f"?next={target}" if target and target != "/" else ""
    return RedirectResponse(f"/login{q}", status_code=303)


@router.get("/logout")
@router.post("/logout")
def logout(request: Request):
    logout_user(request)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(key=JWT_COOKIE_NAME)
    return response


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, welcome: Optional[int] = None):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/settings", status_code=303)
    toast = "Welcome — set your profile and Vidu API key." if welcome else None
    return templates.TemplateResponse(
        request,
        "settings.html",
        _settings_ctx(request, toast=toast, toast_kind="ok"),
    )


@router.post("/settings/profile", response_class=HTMLResponse)
def settings_profile(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/settings", status_code=303)
    try:
        updated = update_profile(user.id, display_name=display_name, email=email)
        request.state.user = updated
        return templates.TemplateResponse(
            request,
            "settings.html",
            _settings_ctx(request, toast="Profile updated.", toast_kind="ok", user=updated),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "settings.html",
            _settings_ctx(request, error=str(exc)),
            status_code=400,
        )


@router.post("/settings/password", response_class=HTMLResponse)
def settings_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/settings", status_code=303)
    if new_password != new_password_confirm:
        return templates.TemplateResponse(
            request,
            "settings.html",
            _settings_ctx(request, error="New passwords do not match."),
            status_code=400,
        )
    try:
        change_password(user.id, current_password, new_password)
        return templates.TemplateResponse(
            request,
            "settings.html",
            _settings_ctx(request, toast="Password changed.", toast_kind="ok"),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "settings.html",
            _settings_ctx(request, error=str(exc)),
            status_code=400,
        )


@router.post("/settings/vidu", response_class=HTMLResponse)
def settings_vidu(
    request: Request,
    vidu_api_key: str = Form(""),
    clear_vidu_key: Optional[str] = Form(None),
    vidu_email: str = Form(""),
    vidu_model: str = Form(""),
    vidu_reference_model: str = Form(""),
    vidu_resolution: str = Form(""),
):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/login?next=/settings", status_code=303)

    clear = bool(clear_vidu_key)
    key_arg = None if (not vidu_api_key.strip() and not clear) else vidu_api_key
    update_vidu_settings(
        user.id,
        api_key=key_arg,
        clear_api_key=clear,
        vidu_email=vidu_email,
        model=vidu_model or None,
        reference_model=vidu_reference_model or None,
        resolution=vidu_resolution or None,
    )
    apply_user_credentials_to_config(user.id)
    msg = "Vidu API key cleared." if clear else "Vidu settings saved securely."
    return templates.TemplateResponse(
        request,
        "settings.html",
        _settings_ctx(request, toast=msg, toast_kind="ok"),
    )
