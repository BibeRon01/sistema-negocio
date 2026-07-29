"""Cliente único para las operaciones críticas del sistema A&M.

Las operaciones de dinero se ejecutan en funciones SQL transaccionales. La
creación de usuarios se delega a una Edge Function para que la service-role
nunca llegue al navegador ni al servidor Streamlit.
"""

from __future__ import annotations

from typing import Any

import requests
import streamlit as st

from db import SUPABASE_KEY, SUPABASE_URL, supabase


class ApiError(RuntimeError):
    pass


def _rpc(name: str, **params) -> dict:
    try:
        response = supabase.rpc(name, params).execute()
    except Exception as exc:
        raise ApiError(str(exc)) from exc

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise ApiError(f"{name} no devolvió una respuesta válida.")
    if data.get("success") is False:
        raise ApiError(str(data.get("error") or "Operación rechazada."))
    return data


def registrar_venta(payload: dict) -> dict:
    try:
        return _rpc(
            "guardar_venta_rpc",
            p_empresa_id=str(payload.get("empresa_id") or ""),
            p_numero_factura=str(payload.get("numero_factura") or ""),
            p_cliente_nombre=str(payload.get("cliente_nombre") or "Cliente General"),
            p_rnc_cliente=str(payload.get("rnc_cliente") or ""),
            p_metodo_pago=str(payload.get("metodo_pago") or "Efectivo"),
            p_items=payload.get("items") or [],
            p_descuento_global=float(payload.get("descuento") or 0.0),
            p_caja_id=payload.get("caja_id"),
            p_usuario_id=payload.get("usuario_id"),
            p_idempotency_key=payload.get("idempotency_key"),
        )
    except Exception:
        return _rpc("api_registrar_venta", p=payload)


def editar_venta(venta_id: Any, items: list[dict], metodo_pago: str) -> dict:
    return _rpc(
        "api_editar_venta",
        p_venta_id=str(venta_id),
        p_items=items,
        p_metodo_pago=str(metodo_pago),
    )


def reemplazar_cuenta_abierta(venta_id: Any, payload: dict) -> dict:
    return _rpc(
        "api_reemplazar_cuenta_abierta",
        p_venta_id=str(venta_id),
        p_payload=payload,
    )


def registrar_compra_producto(payload: dict) -> dict:
    return _rpc("api_registrar_compra_producto", p=payload)


def anular_venta(venta_id: Any, motivo: str) -> dict:
    return _rpc("api_anular_venta", p_venta_id=str(venta_id), p_motivo=str(motivo))


def registrar_abono(
    *,
    monto: float,
    metodo_pago: str,
    caja_id: Any,
    cuenta_id: Any | None = None,
    cliente_id: Any | None = None,
    observacion: str = "",
) -> dict:
    return _rpc(
        "api_registrar_abono",
        p_cuenta_id=int(cuenta_id) if cuenta_id not in (None, "") else None,
        p_cliente_id=int(cliente_id) if cliente_id not in (None, "") else None,
        p_monto=float(monto),
        p_metodo_pago=str(metodo_pago),
        p_caja_id=str(caja_id),
        p_observacion=str(observacion or ""),
    )


def cerrar_caja(caja_id: Any, efectivo_contado: float, observacion: str) -> dict:
    return _rpc(
        "api_cerrar_caja",
        p_caja_id=str(caja_id),
        p_efectivo_contado=float(efectivo_contado),
        p_observacion=str(observacion or ""),
    )


def abrir_caja(monto_inicial: float, observacion: str = "") -> dict:
    return _rpc(
        "api_abrir_caja",
        p_monto_inicial=float(monto_inicial),
        p_observacion=str(observacion or ""),
    )


def cerrar_periodo(ano: int, mes: int, observacion: str = "") -> dict:
    return _rpc(
        "api_cerrar_periodo",
        p_ano=int(ano),
        p_mes=int(mes),
        p_observacion=str(observacion or ""),
    )


def registrar_nomina(
    *,
    empleado_id: Any,
    periodo: str,
    fecha: str,
    metodo_pago: str,
    observacion: str = "",
) -> dict:
    return _rpc(
        "api_registrar_nomina",
        p_empleado_id=str(empleado_id),
        p_periodo=str(periodo),
        p_fecha=str(fecha),
        p_metodo_pago=str(metodo_pago),
        p_observacion=str(observacion or ""),
    )


def invitar_usuario_seguro(
    *,
    email: str,
    password: str,
    nombre: str,
    rol: str,
    tenant_id: str,
    permisos: dict | None = None,
) -> dict:
    access_token = str(st.session_state.get("access_token") or "")
    if not access_token:
        raise ApiError("La sesión administrativa expiró.")
    if "@" not in str(email):
        raise ApiError("El acceso del usuario debe ser un correo electrónico completo.")
    if len(str(password)) < 12:
        raise ApiError("La contraseña inicial debe tener al menos 12 caracteres.")

    url = f"{SUPABASE_URL.rstrip('/')}/functions/v1/invite-user"
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": SUPABASE_KEY,
                "Content-Type": "application/json",
            },
            json={
                "email": str(email).strip().lower(),
                "password": str(password),
                "nombre": str(nombre).strip(),
                "rol": str(rol).strip().lower(),
                "tenant_id": str(tenant_id).strip(),
                "permissions": permisos or {},
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ApiError(f"No se pudo contactar el servicio de usuarios: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or body.get("success") is False:
        raise ApiError(str(body.get("error") or f"Error HTTP {response.status_code}"))
    return body


def gestionar_usuario_seguro(
    *,
    profile_id: Any,
    tenant_id: str,
    nombre: str,
    rol: str,
    activo: bool,
    permisos: dict,
    nueva_password: str = "",
) -> dict:
    access_token = str(st.session_state.get("access_token") or "")
    if not access_token:
        raise ApiError("La sesión administrativa expiró.")
    if nueva_password and len(nueva_password) < 12:
        raise ApiError("La nueva contraseña debe tener al menos 12 caracteres.")

    url = f"{SUPABASE_URL.rstrip('/')}/functions/v1/manage-user"
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": SUPABASE_KEY,
                "Content-Type": "application/json",
            },
            json={
                "profile_id": str(profile_id),
                "tenant_id": str(tenant_id),
                "nombre": str(nombre).strip(),
                "rol": str(rol).strip().lower(),
                "activo": bool(activo),
                "permissions": permisos or {},
                "new_password": nueva_password or None,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ApiError(f"No se pudo contactar el servicio de usuarios: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or body.get("success") is False:
        raise ApiError(str(body.get("error") or f"Error HTTP {response.status_code}"))
    return body


def gestionar_empresa_seguro(
    *,
    action: str,
    tenant_id: str,
    nombre: str = "",
    activo: bool = True,
    configuracion: dict | None = None,
) -> dict:
    access_token = str(st.session_state.get("access_token") or "")
    if not access_token:
        raise ApiError("La sesión de superadministrador expiró.")

    url = f"{SUPABASE_URL.rstrip('/')}/functions/v1/manage-company"
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": SUPABASE_KEY,
                "Content-Type": "application/json",
            },
            json={
                "action": str(action),
                "tenant_id": str(tenant_id).strip(),
                "nombre": str(nombre).strip(),
                "activo": bool(activo),
                "configuracion": configuracion or {},
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise ApiError(f"No se pudo contactar el servicio de empresas: {exc}") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or body.get("success") is False:
        raise ApiError(str(body.get("error") or f"Error HTTP {response.status_code}"))
    return body
