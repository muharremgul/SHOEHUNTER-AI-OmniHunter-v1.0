import asyncio
import hashlib
import hmac
import ipaddress
import os
import secrets
import socket
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_argon2 = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


SESSION_COOKIE = "shoehunter_session"
CSRF_COOKIE = "shoehunter_csrf"
SESSION_HOURS = max(1, int(os.environ.get("SESSION_HOURS", "24")))
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
PUBLIC_PATHS = {
    "/api",
    "/api/health",
    "/api/auth/status",
    "/api/auth/setup",
    "/api/auth/login",
}


class URLValidationError(ValueError):
    pass


def utcnow():
    return datetime.now(timezone.utc)


def token_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def hash_password(password):
    return _argon2.hash(password)


def verify_password(password, password_hash):
    if not password_hash:
        return False
    try:
        if password_hash.startswith("$argon2"):
            return _argon2.verify(password_hash, password)
        if password_hash.startswith("scrypt$"):
            _, salt_hex, expected_hex = password_hash.split("$", 2)
            derived = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
            return hmac.compare_digest(derived.hex(), expected_hex)
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except (ValueError, InvalidHashError, VerifyMismatchError):
        return False


def validate_password_strength(password):
    if len(password or "") < 12:
        raise ValueError("Parola en az 12 karakter olmalidir")
    if password.lower() == password or password.upper() == password:
        raise ValueError("Parola buyuk ve kucuk harf icermelidir")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Parola en az bir rakam icermelidir")


async def ensure_admin(db):
    existing = await db.admin_users.find_one({"id": "main"}, {"_id": 0, "id": 1})
    if existing:
        return False
    configured_password = os.environ.get("ADMIN_PASSWORD", "").strip() or "Admin12345678"
    validate_password_strength(configured_password)
    await db.admin_users.insert_one(
        {
            "id": "main",
            "username": os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin",
            "password_hash": hash_password(configured_password),
            "created_at": utcnow(),
        }
    )
    return True


async def create_session(db, request):
    session_token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    now = utcnow()
    await db.auth_sessions.insert_one(
        {
            "id": secrets.token_hex(16),
            "token_hash": token_hash(session_token),
            "csrf_hash": token_hash(csrf_token),
            "client_ip": request.client.host if request.client else None,
            "user_agent": (request.headers.get("user-agent") or "")[:300],
            "created_at": now,
            "last_seen_at": now,
            "expires_at": now + timedelta(hours=SESSION_HOURS),
        }
    )
    return session_token, csrf_token


def set_session_cookies(response, session_token, csrf_token, secure=False):
    max_age = SESSION_HOURS * 3600
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def clear_session_cookies(response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _domain_allowed(hostname, allowed_domains):
    host = (hostname or "").rstrip(".").lower()
    for domain in allowed_domains:
        allowed = str(domain).rstrip(".").lower()
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


def _ip_is_public(value):
    ip = ipaddress.ip_address(value)
    return bool(ip.is_global and not ip.is_multicast and not ip.is_unspecified)


async def validate_remote_url(url, allowed_domains, resolve_dns=True):
    try:
        parsed = urlparse(str(url).strip())
    except Exception as exc:
        raise URLValidationError("Gecersiz URL") from exc
    if parsed.scheme.lower() != "https":
        raise URLValidationError("Yalnizca HTTPS urun linkleri kabul edilir")
    if not parsed.hostname or parsed.username or parsed.password:
        raise URLValidationError("Gecersiz veya guvenli olmayan URL")
    if parsed.port not in (None, 443):
        raise URLValidationError("Standart disi portlara izin verilmez")
    if not _domain_allowed(parsed.hostname, allowed_domains):
        raise URLValidationError("Bu magaza desteklenen alan adlari listesinde degil")

    try:
        direct_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        direct_ip = None
    if direct_ip is not None and not _ip_is_public(direct_ip):
        raise URLValidationError("Yerel veya ozel IP adreslerine erisim engellendi")

    if resolve_dns:
        try:
            records = await asyncio.to_thread(
                socket.getaddrinfo,
                parsed.hostname,
                parsed.port or 443,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise URLValidationError("Magaza alan adi cozumlenemedi") from exc
        addresses = {item[4][0] for item in records}
        if not addresses or any(not _ip_is_public(address) for address in addresses):
            raise URLValidationError("Alan adi guvenli olmayan bir IP adresine cozumleniyor")
    return parsed.geturl()


class SlidingWindowLimiter:
    def __init__(self):
        self.events = defaultdict(deque)

    def allow(self, key, limit, window_seconds):
        now = utcnow().timestamp()
        bucket = self.events[key]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True


request_limiter = SlidingWindowLimiter()
login_limiter = SlidingWindowLimiter()


def _request_limit(path):
    if path.endswith("/search"):
        return 10, 60
    if "/check" in path or "/track" in path:
        return 8, 60
    if path.startswith("/api/ai/"):
        return 20, 60
    return 180, 60


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, db):
        super().__init__(app)
        self.db = db

    async def dispatch(self, request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if request.method == "OPTIONS" or not path.startswith("/api"):
            return await self._call_with_headers(request, call_next)

        client_ip = request.client.host if request.client else "unknown"
        if not request_limiter.allow((client_ip, "global"), 300, 60):
            return JSONResponse({"detail": "Cok fazla istek. Lutfen biraz bekleyin."}, status_code=429)

        if path in {"/api/auth/setup", "/api/auth/login"}:
            if not request_limiter.allow((client_ip, path), 10, 60):
                return JSONResponse({"detail": "Cok fazla giris istegi. Lutfen bekleyin."}, status_code=429)
        if path in PUBLIC_PATHS:
            return await self._call_with_headers(request, call_next)

        limit, window = _request_limit(path)
        if not request_limiter.allow((client_ip, path, request.method), limit, window):
            return JSONResponse({"detail": "Cok fazla istek. Lutfen biraz bekleyin."}, status_code=429)

        admin = await self.db.admin_users.find_one({"id": "main"}, {"_id": 0})
        if not admin:
            return JSONResponse({"detail": "Ilk yonetici kurulumu gerekli", "setup_required": True}, status_code=428)

        raw_token = request.cookies.get(SESSION_COOKIE)
        session = None
        if raw_token:
            session = await self.db.auth_sessions.find_one(
                {"token_hash": token_hash(raw_token), "expires_at": {"$gt": utcnow()}},
                {"_id": 0},
            )
        if not session:
            return JSONResponse({"detail": "Oturum gerekli"}, status_code=401)

        if request.method not in SAFE_METHODS:
            csrf_cookie = request.cookies.get(CSRF_COOKIE) or ""
            csrf_header = request.headers.get("x-csrf-token") or ""
            valid_csrf = csrf_cookie and hmac.compare_digest(csrf_cookie, csrf_header)
            valid_csrf = valid_csrf and hmac.compare_digest(token_hash(csrf_cookie), session.get("csrf_hash", ""))
            if not valid_csrf:
                return JSONResponse({"detail": "CSRF dogrulamasi basarisiz"}, status_code=403)

        request.state.admin = admin
        await self.db.auth_sessions.update_one(
            {"id": session["id"]},
            {"$set": {"last_seen_at": utcnow()}},
        )
        return await self._call_with_headers(request, call_next)

    async def _call_with_headers(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
