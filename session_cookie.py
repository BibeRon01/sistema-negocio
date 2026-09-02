"""Persistencia cifrada y breve de una sesión real de Supabase en el navegador.

El valor se guarda en ``localStorage`` mediante un componente Streamlit v2 que
se ejecuta en la propia página, no dentro del iframe usado por los antiguos
administradores de cookies. Esto evita que la vista compartida de Streamlit
bloquee la persistencia como una cookie de terceros.

El dato del navegador no concede acceso por sí solo: únicamente reconstruye la
pareja de tokens para que Supabase Auth y ``api_my_session`` vuelvan a validarla.
Ante un error de firma, vencimiento o validación remota, la aplicación lo borra.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from typing import Any

import streamlit as st
from cryptography.fernet import Fernet, InvalidToken


LOGGER = logging.getLogger("ais")
COOKIE_NAME = "ais_supabase_session_v1"
COOKIE_VERSION = 1
COOKIE_SECRET_NAME = "SESSION_COOKIE_SECRET"
COOKIE_SECRET_MIN_LENGTH = 32
EMPLOYEE_SESSION_SECONDS = 60 * 60
PRIVILEGED_SESSION_SECONDS = 24 * 60 * 60

_BROWSER_STORAGE_JS = """
export default function(component) {
    const { data, setStateValue } = component;
    let value = "";
    let status = "ok";
    try {
        if (data.operation === "write") {
            window.localStorage.setItem(data.name, data.value);
        } else if (data.operation === "delete") {
            window.localStorage.removeItem(data.name);
        }
        value = window.localStorage.getItem(data.name) || "";
    } catch (_error) {
        value = "";
        status = "unavailable";
    }
    setStateValue("value", value);
    setStateValue("status", status);
}
"""

try:
    _browser_storage = st.components.v2.component(
        "ais_secure_browser_session_storage",
        js=_BROWSER_STORAGE_JS,
    )
except Exception:  # La aplicación seguirá cerrando de forma segura.
    _browser_storage = None


def _secret_value() -> str:
    try:
        if hasattr(st, "secrets") and COOKIE_SECRET_NAME in st.secrets:
            return str(st.secrets[COOKIE_SECRET_NAME]).strip()
    except Exception:
        pass
    return str(os.environ.get(COOKIE_SECRET_NAME, "") or "").strip()


def persistencia_navegador_configurada() -> bool:
    """Indica si existe componente y un secreto privado suficientemente largo."""
    return _browser_storage is not None and len(_secret_value()) >= COOKIE_SECRET_MIN_LENGTH


def _cipher() -> Fernet:
    secret = _secret_value()
    if _browser_storage is None or len(secret) < COOKIE_SECRET_MIN_LENGTH:
        raise RuntimeError("BROWSER_SESSION_NOT_CONFIGURED")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _component_key(prefix: str) -> str:
    event = int(st.session_state.get("_session_cookie_event") or 0) + 1
    st.session_state["_session_cookie_event"] = event
    return f"ais_session_{prefix}_{event}"


def _storage_operation(operation: str, value: str = "", *, key: str) -> tuple[str, str]:
    """Monta el almacén integrado y retorna únicamente valor y estado.

    El valor procedente del navegador nunca se considera confiable. La firma
    Fernet se valida después en Python antes de reconstruir una sesión.
    """
    if _browser_storage is None:
        return "", "unavailable"
    result = _browser_storage(
        data={
            "operation": str(operation),
            "name": COOKIE_NAME,
            "value": str(value or ""),
        },
        default={"value": "", "status": "pending"},
        on_value_change=lambda: None,
        on_status_change=lambda: None,
        key=key,
    )
    stored = str(getattr(result, "value", "") or "")
    status = str(getattr(result, "status", "pending") or "pending")
    return stored, status


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
    _storage_operation("write", encrypted, key=_component_key("write"))
    return True


def leer_sesion_navegador() -> dict[str, Any] | None:
    """Descifra una sesión vigente; nunca acepta datos sin firma del servidor."""
    if not persistencia_navegador_configurada():
        return None
    encoded, status = _storage_operation(
        "read",
        key="ais_session_storage_reader",
    )
    if status == "unavailable":
        LOGGER.warning("El navegador no permitió guardar la sesión cifrada.")
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
    """Retira la sesión cifrada sin fallar cuando ya no existe."""
    if _browser_storage is None:
        return
    try:
        _storage_operation("delete", key=_component_key("delete"))
    except Exception as exc:
        LOGGER.warning("No se pudo retirar la sesión del navegador (%s).", type(exc).__name__)
