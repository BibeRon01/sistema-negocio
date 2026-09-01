"""Persistencia cifrada y breve de una sesión real de Supabase en el navegador.

La cookie no concede acceso por sí sola: solo permite reconstruir la pareja de
tokens para que Supabase Auth y ``api_my_session`` vuelvan a validarla. Ante un
error de firma, vencimiento o validación remota, la aplicación la elimina.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import streamlit as st
from cryptography.fernet import Fernet, InvalidToken

try:
    import extra_streamlit_components as stx
except Exception:  # La aplicación seguirá cerrando de forma segura.
    stx = None


LOGGER = logging.getLogger("ais")
COOKIE_NAME = "ais_supabase_session_v1"
COOKIE_VERSION = 1
COOKIE_SECRET_NAME = "SESSION_COOKIE_SECRET"
COOKIE_SECRET_MIN_LENGTH = 32
EMPLOYEE_SESSION_SECONDS = 60 * 60
PRIVILEGED_SESSION_SECONDS = 24 * 60 * 60


def _secret_value() -> str:
    try:
        if hasattr(st, "secrets") and COOKIE_SECRET_NAME in st.secrets:
            return str(st.secrets[COOKIE_SECRET_NAME]).strip()
    except Exception:
        pass
    return str(os.environ.get(COOKIE_SECRET_NAME, "") or "").strip()


def persistencia_navegador_configurada() -> bool:
    """Indica si existe componente y un secreto privado suficientemente largo."""
    return stx is not None and len(_secret_value()) >= COOKIE_SECRET_MIN_LENGTH


def _cipher() -> Fernet:
    secret = _secret_value()
    if stx is None or len(secret) < COOKIE_SECRET_MIN_LENGTH:
        raise RuntimeError("BROWSER_SESSION_NOT_CONFIGURED")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _cookie_manager():
    manager = st.session_state.get("_ais_cookie_manager")
    if manager is None:
        manager = stx.CookieManager(key="ais_session_cookie_manager")
        st.session_state["_ais_cookie_manager"] = manager
    return manager


def _component_key(prefix: str) -> str:
    event = int(st.session_state.get("_session_cookie_event") or 0) + 1
    st.session_state["_session_cookie_event"] = event
    return f"ais_session_{prefix}_{event}"


def _context_cookies() -> dict[str, str]:
    try:
        return {str(key): str(value) for key, value in dict(st.context.cookies).items()}
    except Exception:
        return {}


def _request_cookies() -> dict[str, str]:
    """Lee cookies del request y, si hace falta, del componente del navegador.

    ``st.context.cookies`` representa el request que abrió la sesión. Una cookie
    escrita por JavaScript después de ese momento puede no aparecer allí hasta
    otra conexión. El lector del componente evita perderla durante un rerun o un
    reinicio de la aplicación.
    """
    cookies = _context_cookies()
    if COOKIE_NAME in cookies or stx is None:
        return cookies
    try:
        manager = _cookie_manager()
        component_cookies = manager.get_all(key="ais_session_cookie_reader")
        if isinstance(component_cookies, dict):
            cookies.update(
                {str(key): str(value) for key, value in component_cookies.items()}
            )
    except Exception as exc:
        LOGGER.warning(
            "No se pudieron consultar las cookies del navegador (%s).",
            type(exc).__name__,
        )
    return cookies


def _request_is_https() -> bool:
    try:
        return str(st.context.url or "").lower().startswith("https://")
    except Exception:
        return True


def guardar_sesion_navegador(
    *,
    access_token: str,
    refresh_token: str,
    tenant_id: str,
    privileged: bool,
    mfa_verified_at: float = 0.0,
    last_activity: float | None = None,
) -> bool:
    """Cifra la sesión y limita su vida a 1 h o al AAL2 diario vigente."""
    if not persistencia_navegador_configurada():
        return False

    access = str(access_token or "")
    refresh = str(refresh_token or "")
    tenant = str(tenant_id or "").strip()
    now = float(time.time())
    activity = float(last_activity or now)
    verified_at = float(mfa_verified_at or 0.0)
    if not access or not refresh or not tenant:
        return False

    if privileged:
        expires_at = verified_at + PRIVILEGED_SESSION_SECONDS
        if verified_at <= 0 or expires_at <= now:
            return False
    else:
        expires_at = activity + EMPLOYEE_SESSION_SECONDS

    max_age = max(1, int(expires_at - now))
    payload = {
        "v": COOKIE_VERSION,
        "access_token": access,
        "refresh_token": refresh,
        "tenant_id": tenant,
        "privileged": bool(privileged),
        "mfa_verified_at": verified_at,
        "last_activity": activity,
        "expires_at": expires_at,
    }
    encrypted = _cipher().encrypt(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).decode("ascii")
    manager = _cookie_manager()
    manager.set(
        COOKIE_NAME,
        encrypted,
        key=_component_key("set"),
        path="/",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=max_age),
        max_age=max_age,
        secure=_request_is_https(),
        same_site="strict",
    )
    return True


def leer_sesion_navegador() -> dict[str, Any] | None:
    """Descifra una cookie vigente; nunca acepta datos sin firma del servidor."""
    if not persistencia_navegador_configurada():
        return None
    encoded = _request_cookies().get(COOKIE_NAME, "")
    if not encoded:
        return None
    try:
        raw = _cipher().decrypt(
            encoded.encode("ascii"),
            ttl=PRIVILEGED_SESSION_SECONDS + 60,
        )
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("v") != COOKIE_VERSION:
            raise ValueError("BROWSER_SESSION_VERSION_INVALID")
        if float(payload.get("expires_at") or 0.0) <= time.time():
            raise ValueError("BROWSER_SESSION_EXPIRED")
        if not str(payload.get("access_token") or ""):
            raise ValueError("BROWSER_SESSION_ACCESS_REQUIRED")
        if not str(payload.get("refresh_token") or ""):
            raise ValueError("BROWSER_SESSION_REFRESH_REQUIRED")
        if not str(payload.get("tenant_id") or "").strip():
            raise ValueError("BROWSER_SESSION_TENANT_REQUIRED")
        return payload
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError):
        LOGGER.warning("La sesión cifrada del navegador fue rechazada.")
        borrar_sesion_navegador()
        return None


def borrar_sesion_navegador() -> None:
    """Retira la cookie sin fallar cuando ya no existe."""
    if stx is None:
        return
    cookies = _request_cookies()
    manager = st.session_state.get("_ais_cookie_manager")
    if COOKIE_NAME not in cookies and (
        manager is None or COOKIE_NAME not in (getattr(manager, "cookies", {}) or {})
    ):
        return
    try:
        manager = manager or _cookie_manager()
        current = dict(getattr(manager, "cookies", {}) or {})
        current.update(cookies)
        manager.cookies = current
        manager.delete(COOKIE_NAME, key=_component_key("delete"))
    except Exception as exc:
        LOGGER.warning("No se pudo retirar la cookie de sesión (%s).", type(exc).__name__)
