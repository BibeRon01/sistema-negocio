"""Cliente único para las operaciones críticas del sistema A&M.

Las operaciones de dinero se ejecutan en funciones SQL transaccionales. La
creación de usuarios se delega a una Edge Function para que la service-role
nunca llegue al navegador ni al servidor Streamlit.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
import streamlit as st

from db import SUPABASE_KEY, SUPABASE_URL, obtener_tenant_actual, supabase


LOGGER = logging.getLogger("ais")

_API_ERROR_MESSAGES = {
    "AUTH_REQUIRED": "La sesión expiró. Inicie sesión nuevamente.",
    "MFA_AAL2_REQUIRED": "Esta operación requiere confirmar el segundo factor.",
    "PURCHASE_PERMISSION_DENIED": "No tiene permiso para registrar compras en esta empresa.",
    "PRODUCT_NOT_FOUND_OR_FORBIDDEN": "Uno de los productos no existe o no pertenece a la empresa activa.",
    "INVALID_PURCHASE_ITEM": "Revise las cantidades y costos de los productos.",
    "INVALID_PURCHASE_QUANTITY": "Todas las cantidades deben ser mayores que cero.",
    "INVALID_PURCHASE_COST": "Los costos de compra no pueden ser negativos.",
    "DUPLICATE_PURCHASE_PRODUCT": "Cada producto debe aparecer una sola vez en la factura.",
    "IDEMPOTENCY_PAYLOAD_MISMATCH": "La factura cambió después de un intento previo; recargue el formulario.",
    "PERIODO_CERRADO": "No se permiten movimientos en un período contable cerrado.",
    "BIBERON_IMPORT_FORBIDDEN": "La cuenta no puede importar datos de BIBE RON 01.",
    "BIBERON_TENANT_MISMATCH": "El paquete no pertenece a la empresa activa.",
    "BIBERON_TARGET_NOT_EMPTY": "La empresa ya contiene movimientos que deben revisarse antes de importar.",
    "IMPORT_IDEMPOTENCY_MISMATCH": "Una fila ya importada cambió; use el paquete original.",
    "DUPLICATE_HISTORICAL_INVOICE": "El número de una factura histórica ya existe.",
    "HISTORICAL_SALE_NOT_FOUND": "No se encontró la venta histórica relacionada.",
    "HISTORICAL_EMPLOYEE_NOT_FOUND": "No se encontró el empleado histórico relacionado.",
}


class ApiError(RuntimeError):
    pass


def _mensaje_api_seguro(error: Any, fallback: str = "No se pudo completar la operación.") -> str:
    raw = str(error or "")
    for code, message in _API_ERROR_MESSAGES.items():
        if code in raw:
            return message
    return fallback


def _rpc(name: str, **params) -> dict:
    payload = params.get("p")
    if isinstance(payload, dict):
        payload = dict(payload)
        tenant_id = obtener_tenant_actual()
        if not tenant_id:
            raise ApiError("No hay una empresa autorizada activa.")
        # La empresa verificada por api_my_session prevalece sobre cualquier
        # identificador enviado por una vista o un cliente manipulado.
        payload["tenant_id"] = tenant_id
        payload["empresa_id"] = tenant_id
        params["p"] = payload
    try:
        response = supabase.rpc(name, params).execute()
    except Exception as exc:
        LOGGER.error("RPC %s rechazada (%s)", name, type(exc).__name__, exc_info=exc)
        raise ApiError(_mensaje_api_seguro(exc)) from exc

    data = response.data
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        LOGGER.error("RPC %s devolvió un tipo inesperado: %s", name, type(data).__name__)
        raise ApiError("El servidor devolvió una respuesta inválida.")
    if data.get("success") is False:
        raise ApiError(_mensaje_api_seguro(data.get("error"), "La operación fue rechazada."))
    return data


def prevalidar_migracion_biberon() -> dict:
    return _rpc("api_prevalidar_migracion_biberon")


def importar_historial_biberon(payload: dict) -> dict:
    return _rpc("api_importar_historial_biberon", p=payload)


def validar_importacion_biberon(package_id: str) -> dict:
    return _rpc(
        "api_validar_importacion_biberon",
        p_package_id=str(package_id),
    )


def registrar_venta(payload: dict) -> dict:
    # Una venta se envía una sola vez a la API canónica. Intentar una segunda
    # RPC tras un error de red puede duplicar una operación que sí alcanzó a
    # confirmarse en PostgreSQL.
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


def registrar_factura_compra(payload: dict) -> dict:
    return _rpc("api_registrar_factura_compra", p=payload)


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
        LOGGER.error("Servicio de invitaciones no disponible (%s)", type(exc).__name__, exc_info=exc)
        raise ApiError("No se pudo contactar el servicio de usuarios.") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or body.get("success") is False:
        raise ApiError(_mensaje_api_seguro(body.get("error"), "El servicio rechazó la invitación."))
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
        LOGGER.error("Servicio de usuarios no disponible (%s)", type(exc).__name__, exc_info=exc)
        raise ApiError("No se pudo contactar el servicio de usuarios.") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or body.get("success") is False:
        raise ApiError(_mensaje_api_seguro(body.get("error"), "El servicio rechazó el cambio de usuario."))
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
        LOGGER.error("Servicio de empresas no disponible (%s)", type(exc).__name__, exc_info=exc)
        raise ApiError("No se pudo contactar el servicio de empresas.") from exc

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or body.get("success") is False:
        raise ApiError(_mensaje_api_seguro(body.get("error"), "El servicio rechazó el cambio de empresa."))
    return body
