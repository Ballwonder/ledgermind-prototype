from __future__ import annotations

import base64
import hashlib
import hmac
import html
import os
import secrets
import time

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from .data_model import AppUser, SessionLocal
from .personal_service import ensure_demo_household

router = APIRouter(tags=["Authentication"])
SESSION_COOKIE = "ledgermind_session"
SESSION_LIFETIME = 60 * 60 * 12


def _secret() -> bytes:
    value = os.getenv("SESSION_SECRET", "")
    if not value:
        if os.getenv("RENDER"):
            raise RuntimeError("SESSION_SECRET is required on Render")
        value = "local-development-only-change-me"
    return value.encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return f"pbkdf2_sha256$600000${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt_text, expected = stored.split("$", 3)
        salt = base64.urlsafe_b64decode(salt_text + "==")
        actual = _b64(hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds)))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_session(user_id: int) -> tuple[str, str]:
    expires = int(time.time()) + SESSION_LIFETIME
    csrf = secrets.token_urlsafe(24)
    payload = f"{user_id}.{expires}.{csrf}"
    signature = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}", csrf


def read_session(token: str | None) -> tuple[int, str] | None:
    if not token:
        return None
    try:
        user_id, expires, csrf, signature = token.split(".", 3)
        payload = f"{user_id}.{expires}.{csrf}"
        expected = _b64(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected) or int(expires) < int(time.time()):
            return None
        return int(user_id), csrf
    except (ValueError, TypeError):
        return None


def authenticate_request(request: Request) -> tuple[AppUser, str] | None:
    session = read_session(request.cookies.get(SESSION_COOKIE))
    if not session:
        return None
    user_id, csrf = session
    with SessionLocal() as db:
        user = db.get(AppUser, user_id)
        if not user or not user.active:
            return None
        db.expunge(user)
        return user, csrf


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>
<style>body{{font-family:Inter,Arial,sans-serif;background:#f4f6f8;color:#17202a;margin:0;display:grid;place-items:center;min-height:100vh}}main{{background:white;width:min(420px,calc(100% - 32px));padding:28px;border-radius:16px;box-shadow:0 3px 20px #0001}}label{{display:block;margin:14px 0 5px;font-weight:650}}input{{width:100%;box-sizing:border-box;padding:11px;border:1px solid #cfd4dc;border-radius:9px}}button{{margin-top:18px;width:100%;padding:11px;border:0;border-radius:9px;background:#111827;color:white;font-weight:700}}.muted{{color:#667085;font-size:13px}}.error{{color:#b91c1c}}</style></head><body><main><h1>LedgerMind</h1>{body}</main></body></html>""")


def _set_cookie(response: RedirectResponse, token: str):
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_LIFETIME, httponly=True,
        secure=bool(os.getenv("RENDER")), samesite="lax", path="/"
    )


@router.get("/setup", response_class=HTMLResponse)
def setup_page():
    with SessionLocal() as db:
        if db.scalar(select(func.count(AppUser.id))):
            return RedirectResponse("/login", status_code=303)
    return _page("Set up LedgerMind", """<h2>Create the owner account</h2><p class='muted'>This one-time step locks the prototype to you.</p><form method='post'><label>Email</label><input type='email' name='email' autocomplete='email' required><label>Password</label><input type='password' name='password' minlength='12' autocomplete='new-password' required><p class='muted'>Use at least 12 characters.</p><button>Create account</button></form>""")


@router.post("/setup")
def setup(email: str = Form(...), password: str = Form(...)):
    normalized = email.strip().lower()
    try:
        password_hash = hash_password(password)
    except ValueError as exc:
        return _page("Set up LedgerMind", f"<p class='error'>{html.escape(str(exc))}</p><p><a href='/setup'>Try again</a></p>")
    with SessionLocal() as db:
        if db.scalar(select(func.count(AppUser.id))):
            return RedirectResponse("/login", status_code=303)
        household_id = ensure_demo_household()
        user = AppUser(household_id=household_id, email=normalized, password_hash=password_hash)
        db.add(user); db.commit(); db.refresh(user)
        token, _ = create_session(user.id)
    response = RedirectResponse("/prototype", status_code=303)
    _set_cookie(response, token)
    return response


@router.get("/login", response_class=HTMLResponse)
def login_page():
    with SessionLocal() as db:
        if not db.scalar(select(func.count(AppUser.id))):
            return RedirectResponse("/setup", status_code=303)
    return _page("Sign in to LedgerMind", """<h2>Sign in</h2><form method='post'><label>Email</label><input type='email' name='email' autocomplete='email' required><label>Password</label><input type='password' name='password' autocomplete='current-password' required><button>Sign in</button></form>""")


@router.post("/login")
def login(email: str = Form(...), password: str = Form(...)):
    with SessionLocal() as db:
        user = db.scalar(select(AppUser).where(AppUser.email == email.strip().lower()))
        if not user or not user.active or not verify_password(password, user.password_hash):
            return _page("Sign in to LedgerMind", "<p class='error'>Email or password was incorrect.</p><p><a href='/login'>Try again</a></p>")
        token, _ = create_session(user.id)
    response = RedirectResponse("/prototype", status_code=303)
    _set_cookie(response, token)
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


def enforce_csrf(request: Request, csrf: str):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(supplied, csrf):
            raise HTTPException(403, "Invalid security token; refresh and try again")
