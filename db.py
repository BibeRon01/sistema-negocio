import base64
import hashlib
import json
import os
import re
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Any
try:
    from supabase import Client, create_client
except Exception:
    Client = Any
    create_client = None

VERSION_SISTEMA = "v3.0.0-secure"

# =========================================================
# SECRETS / CONEXIÓN
# =========================================================
def obtener_secreto(nombre: str, default: str = "") -> str:
    try:
        if hasattr(st, "secrets") and nombre in st.secrets:
            return str(st.secrets[nombre])
        return os.environ.get(nombre, default)
    except Exception:
        return os.environ.get(nombre, default)

SUPABASE_URL = obtener_secreto("SUPABASE_URL", "")
SUPABASE_KEY = obtener_secreto("SUPABASE_KEY", "")

def _token_fingerprint(token: str) -> str:
    if not token:
        return "anon"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _crear_cliente_sesion() -> Client | None:
    """Crea un cliente exclusivo para la sesión Streamlit actual.

    Nunca se reutiliza un cliente mutable entre navegadores o usuarios.
    """
    if not SUPABASE_URL or not SUPABASE_KEY or create_client is None:
        return None

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    access_token = str(st.session_state.get("access_token") or "")
    refresh_token = str(st.session_state.get("refresh_token") or "")
    if access_token:
        try:
            if refresh_token:
                auth_response = client.auth.set_session(access_token, refresh_token)
                if getattr(auth_response, "session", None):
                    st.session_state["access_token"] = auth_response.session.access_token
                    st.session_state["refresh_token"] = auth_response.session.refresh_token
            else:
                client.postgrest.auth(access_token)
        except Exception:
            client.postgrest.auth(access_token)
    return client


def obtener_cliente_sesion(forzar_nuevo: bool = False) -> Client | None:
    """Retorna el cliente aislado de la sesión, renovándolo si cambia el token."""
    token = str(st.session_state.get("access_token") or "")
    fingerprint = _token_fingerprint(token)
    cached = st.session_state.get("_supabase_session_client")
    cached_fingerprint = st.session_state.get("_supabase_session_fingerprint")

    if forzar_nuevo or cached is None or cached_fingerprint != fingerprint:
        cached = _crear_cliente_sesion()
        st.session_state["_supabase_session_client"] = cached
        st.session_state["_supabase_session_fingerprint"] = fingerprint
    return cached


def renovar_cliente_sesion() -> Client | None:
    st.session_state.pop("_supabase_session_client", None)
    st.session_state.pop("_supabase_session_fingerprint", None)
    return obtener_cliente_sesion(forzar_nuevo=True)


class SessionSupabaseProxy:
    """Proxy compatible con el código existente y aislado por sesión."""

    def __bool__(self):
        return bool(SUPABASE_URL and SUPABASE_KEY and create_client is not None)

    def __getattr__(self, name):
        client = obtener_cliente_sesion()
        if client is None:
            raise RuntimeError("Supabase no está configurado.")
        return getattr(client, name)

    def table(self, table_name: str):
        client = obtener_cliente_sesion()
        if client is None:
            raise RuntimeError("Supabase no está configurado.")
        return client.table(table_name)

    def rpc(self, function_name: str, params: dict | None = None):
        client = obtener_cliente_sesion()
        if client is None:
            raise RuntimeError("Supabase no está configurado.")
        return client.rpc(function_name, params or {})


supabase: Any = SessionSupabaseProxy() if SUPABASE_URL and SUPABASE_KEY and create_client is not None else None


def aplicar_auth_token():
    """Compatibilidad: garantiza que exista el cliente correcto de esta sesión."""
    obtener_cliente_sesion()


# =========================================================
# TENANT / SESION HELPERS
# =========================================================
def usuario_sesion() -> dict:
    return st.session_state.get("usuario_data", {}) or {}

def nombre_usuario_actual() -> str:
    user = usuario_sesion()
    return str(user.get("usuario") or user.get("nombre") or "sistema")

# =========================================================
# S-03 · SEPARACIÓN DE PRIVILEGIOS SUPERADMIN
# El privilegio de superadmin de PLATAFORMA se verifica desde
# el claim 'role' del JWT de Supabase Auth, NO del username.
# Esto previene escalada horizontal por coincidencia de nombre.
# =========================================================
def es_superadmin_plataforma() -> bool:
    """Usa únicamente el resultado entregado por la función SQL verificada."""
    return bool(usuario_sesion().get("es_superadmin") is True)

def obtener_tenant_actual() -> str:
    usuario_data = usuario_sesion()
    if not usuario_data:
        return ""

    tenant_sesion = str(usuario_data.get("tenant_id") or usuario_data.get("empresa_id") or "").strip()
    if es_superadmin_plataforma():
        seleccionado = str(st.session_state.get("superadmin_tenant_seleccionado") or tenant_sesion).strip()
        permitidos = {
            str(item.get("tenant_id") or "").strip()
            for item in (usuario_data.get("tenants") or [])
            if isinstance(item, dict)
        }
        if seleccionado == "global" or seleccionado in permitidos:
            return seleccionado
    return tenant_sesion


def obtener_configuracion() -> dict:
    tenant = obtener_tenant_actual()
    return _obtener_configuracion_interna(tenant)

@st.cache_data(ttl=60, show_spinner=False)
def _obtener_configuracion_interna(tenant: str) -> dict:
    if not supabase or not tenant:
        return {}
    try:
        resp = (
            supabase.table("configuracion_sistema")
            .select("*")
            .eq("empresa_id", tenant)
            .limit(1)
            .execute()
        )
        filas = resp.data or []
        if filas:
            return filas[0]
        # Compatibilidad de lectura para instalaciones aún no armonizadas.
        resp = (
            supabase.table("configuracion_sistema")
            .select("*")
            .eq("propietario", tenant)
            .limit(1)
            .execute()
        )
        filas = resp.data or []
        return filas[0] if filas else {}
    except Exception:
        return {}

# =========================================================
# FASE 4 — TABLAS MULTI-TENANT & MONKEY PATCHING
# =========================================================
TABLAS_MULTI_TENANT = {
    "ventas", "detalle_venta", "caja", "productos", "clientes", "proveedores",
    "compras", "gastos", "empleados", "pagos_empleados", "perdidas",
    "gastos_dueno", "activos_fijos", "capital_base", "creditos",
    "auditoria_eventos", "usuarios", "ajustes_inventario", "conteo_inventario",
    "distribuciones", "notas_credito", "suscripciones_empresas", "secuencia_ncf",
    "inventario_actual", "cuentas_por_cobrar", "abonos_credito", "distribucion_beneficios", "ventas_pagos", "pagos_proveedores"
}

class WrappedQueryBuilder:
    def __init__(self, original_builder, table_name):
        self.original_builder = original_builder
        self.table_name = table_name

    def select(self, *args, **kwargs):
        builder = self.original_builder.select(*args, **kwargs)
        tenant = obtener_tenant_actual()
        if tenant and self.table_name in TABLAS_MULTI_TENANT:
            if self.table_name == "usuarios":
                if tenant != "global":
                    return builder.eq("email", tenant)
            else:
                if tenant == "global":
                    return builder.or_("empresa_id.eq.global,empresa_id.is.null")
                else:
                    return builder.eq("empresa_id", tenant)
        return builder

    def update(self, datos, *args, **kwargs):
        tenant = obtener_tenant_actual()
        if tenant and tenant != "global" and self.table_name in TABLAS_MULTI_TENANT:
            if self.table_name != "usuarios" and "empresa_id" not in datos:
                datos["empresa_id"] = tenant
            elif self.table_name == "usuarios" and "email" not in datos:
                datos["email"] = tenant
        
        builder = self.original_builder.update(datos, *args, **kwargs)
        if tenant and tenant != "global" and self.table_name in TABLAS_MULTI_TENANT:
            if self.table_name == "usuarios":
                return builder.eq("email", tenant)
            else:
                return builder.eq("empresa_id", tenant)
        return builder

    def delete(self, *args, **kwargs):
        builder = self.original_builder.delete(*args, **kwargs)
        tenant = obtener_tenant_actual()
        if tenant and tenant != "global" and self.table_name in TABLAS_MULTI_TENANT:
            if self.table_name == "usuarios":
                return builder.eq("email", tenant)
            else:
                return builder.eq("empresa_id", tenant)
        return builder

    def insert(self, datos, *args, **kwargs):
        tenant = obtener_tenant_actual()
        if isinstance(datos, list):
            for d in datos:
                if tenant and tenant != "global" and self.table_name in TABLAS_MULTI_TENANT:
                    if self.table_name == "usuarios":
                        if "email" not in d or not d["email"]:
                            d["email"] = tenant
                    else:
                        if "empresa_id" not in d or not d["empresa_id"]:
                            d["empresa_id"] = tenant
        elif isinstance(datos, dict):
            if tenant and tenant != "global" and self.table_name in TABLAS_MULTI_TENANT:
                if self.table_name == "usuarios":
                    if "email" not in datos or not datos["email"]:
                        datos["email"] = tenant
                else:
                    if "empresa_id" not in datos or not datos["empresa_id"]:
                        datos["empresa_id"] = tenant
                        
        return self.original_builder.insert(datos, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.original_builder, name)

def custom_table(table_name):
    """Compatibilidad con vistas antiguas; RLS es la autoridad de aislamiento."""
    client = obtener_cliente_sesion()
    return client.table(table_name) if client is not None else None

# =========================================================
# LOGO A&M
# =========================================================
def get_am_logo_b64() -> str:
    rute_candidates = [
        os.path.join(os.path.dirname(__file__), "am_logo.png"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "am_logo.png"),
        os.path.join(os.getcwd(), "am_logo.png"),
        "am_logo.png"
    ]
    for p in rute_candidates:
        try:
            if os.path.isfile(p):
                with open(p, "rb") as _f:
                    _data_bytes = _f.read()
                    _data = base64.b64encode(_data_bytes).decode()
                    mime = "image/png"
                    if _data_bytes.startswith(b"\xff\xd8\xff"):
                        mime = "image/jpeg"
                    elif _data_bytes.startswith(b"\x89PNG"):
                        mime = "image/png"
                    elif _data_bytes.startswith(b"GIF8"):
                        mime = "image/gif"
                    return f"data:{mime};base64,{_data}"
        except Exception:
            pass
    return ""

AM_LOGO_B64 = get_am_logo_b64()

# =========================================================
# CACHE MANAGEMENT
# =========================================================
def invalidar_cache_tabla(nombre_tabla: str):
    if "session_cache_tablas" in st.session_state:
        cache = st.session_state["session_cache_tablas"]
        claves_a_borrar = [k for k in list(cache.keys()) if k == nombre_tabla or k.startswith(f"{nombre_tabla}::")]
        for k in claves_a_borrar:
            del cache[k]
        deps = []
        nombre_lower = nombre_tabla.lower()
        if nombre_lower == "ventas":
            deps = ["detalle_venta", "caja", "cuentas_por_cobrar"]
        elif nombre_lower == "productos":
            deps = ["detalle_venta"]
        elif nombre_lower == "caja":
            deps = ["ventas"]
        elif nombre_lower == "detalle_venta":
            deps = ["ventas"]
        for dep in deps:
            dep_claves = [k for k in list(cache.keys()) if k == dep or k.startswith(f"{dep}::")]
            for k in dep_claves:
                del cache[k]

def limpiar_cache_datos():
    if "session_cache_tablas" in st.session_state:
        st.session_state["session_cache_tablas"].clear()
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass

# =========================================================
# BASE CRUD OPERATIONS
# =========================================================

# C-02 · PRECISIÓN MONETARIA — Decimal en lugar de float
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

def to_decimal(valor, decimales: int = 2) -> Decimal:
    """Convierte un valor numérico a Decimal redondeado con ROUND_HALF_UP.
    Evita errores de representación binaria de float (0.1+0.2 ≠ 0.3 en float).
    """
    try:
        if isinstance(valor, Decimal):
            d = valor
        elif isinstance(valor, str):
            # Limpiar separadores de miles y normalizar coma decimal
            valor_clean = valor.replace(",", "").strip()
            d = Decimal(valor_clean)
        elif valor is None or (isinstance(valor, float) and not pd.notna(valor)):
            return Decimal("0")
        else:
            d = Decimal(str(valor))
        factor = Decimal(10) ** decimales
        return d.quantize(Decimal(1) / factor, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")

def total_contable_sin_recargo(row) -> float:
    """Total real para contabilidad. Usa Decimal para precisión exacta.
    C-01: recargo por tarjeta siempre es 0 (eliminado).
    C-02: cálculo en Decimal, retorna float para compatibilidad pandas.
    """
    try:
        total = to_decimal(row.get("total", 0))
        return float(total)
    except Exception:
        return 0.0

def aplicar_total_contable_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return df
        out = df.copy()
        out["total_contable"] = out.apply(total_contable_sin_recargo, axis=1)
        return out
    except Exception:
        return df


def _leer_tabla_de_supabase(nombre_tabla: str, order_by: str = "id", tenant: str = "global") -> pd.DataFrame:
    aplicar_auth_token()
    try:
        query = supabase.table(nombre_tabla).select("*")
        if tenant and nombre_tabla in TABLAS_MULTI_TENANT:
            if nombre_tabla == "usuarios":
                if tenant != "global":
                    query = query.eq("empresa_id", tenant)
            else:
                if tenant == "global":
                    query = query.or_("empresa_id.eq.global,empresa_id.is.null")
                else:
                    query = query.eq("empresa_id", tenant)
        try:
            ordered_query = query.order(order_by)
        except Exception:
            ordered_query = query

        data = []
        start = 0
        chunk_size = 1000
        while True:
            resp = ordered_query.range(start, start + chunk_size - 1).execute()
            chunk_data = resp.data or []
            data.extend(chunk_data)
            if len(chunk_data) < chunk_size:
                break
            start += chunk_size
        df = pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

    if not df.empty:
        if "identificación" in df.columns and "id" not in df.columns:
            df["id"] = df["identificación"]
        if "metodo_pago" not in df.columns and "método_pago" in df.columns:
            df["metodo_pago"] = df["método_pago"]
        if "metodo" not in df.columns and "método" in df.columns:
            df["metodo"] = df["método"]
        if "cliente_nombre" not in df.columns and "cliente_nombr" in df.columns:
            df["cliente_nombre"] = df["cliente_nombr"]
    if nombre_tabla == "productos" and not df.empty and "nombre" in df.columns:
        try:
            df = df.sort_values(by="nombre", key=lambda col: col.str.lower(), ascending=True).reset_index(drop=True)
        except Exception:
            pass
    if nombre_tabla == "ventas":
        return aplicar_total_contable_df(df)
    return df

def leer_tabla(nombre_tabla: str, order_by: str = "id") -> pd.DataFrame:
    tenant = obtener_tenant_actual()
    cache_key = f"{nombre_tabla}::{tenant}"

    if "session_cache_tablas" not in st.session_state:
        st.session_state["session_cache_tablas"] = {}

    ahora = datetime.now()
    cache = st.session_state["session_cache_tablas"].get(cache_key)

    if cache is not None:
        df, timestamp = cache
        if (ahora - timestamp).total_seconds() < 300.0:
            return df.copy()

    df = _leer_tabla_de_supabase(nombre_tabla, order_by, tenant=tenant)
    from utils import agregar_columna_codigo_secuencial
    df = agregar_columna_codigo_secuencial(df, nombre_tabla)
    if not df.empty and "fecha" in df.columns:
        try:
            df["fecha"] = pd.to_datetime(df["fecha"], format="ISO8601", errors="coerce")
        except Exception:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    st.session_state["session_cache_tablas"][cache_key] = (df, ahora)
    return df.copy()

def es_periodo_cerrado(fecha) -> bool:
    """Retorna True si la fecha cae dentro de un período contable cerrado (C-08)."""
    try:
        if not fecha:
            return False

        fecha_dt = None
        if isinstance(fecha, (date, datetime)):
            fecha_dt = fecha
        elif isinstance(fecha, str):
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    fecha_dt = datetime.strptime(fecha.split(" ")[0].split("T")[0], "%Y-%m-%d").date()
                    break
                except Exception:
                    pass

        if not fecha_dt:
            return False

        ano = fecha_dt.year
        mes = fecha_dt.month
        ref_cierre = f"cierre:{ano}{mes:02d}"
        periodo_str = f"{ano}-{mes:02d}"

        tenant = obtener_tenant_actual()

        # 1. Consultar tabla periodos_contables si existe
        try:
            p_res = supabase.table("periodos_contables").select("id").eq("periodo", periodo_str).eq("estado", "cerrado")
            if tenant and tenant != "global":
                p_res = p_res.eq("empresa_id", tenant)
            p_data = p_res.execute().data
            if p_data:
                return True
        except Exception:
            pass

        # 2. Consultar movimientos_contables con referencia de cierre
        q = supabase.table("movimientos_contables").select("id").eq("referencia", ref_cierre)
        if tenant and tenant != "global":
            q = q.eq("empresa_id", tenant)
        res = q.execute()
        return bool(res.data)
    except Exception:
        return False

def validar_periodo_abierto(nombre_tabla: str, datos: dict) -> bool:
    if nombre_tabla not in {"ventas", "detalle_venta", "compras", "gastos", "pagos_empleados", "adelantos_empleados", "movimientos_caja", "movimientos_contables", "ventas_pagos", "cuentas_por_cobrar"}:
        return True
    if nombre_tabla == "movimientos_contables" and datos.get("referencia", "").startswith("cierre:"):
        return True
    for key in ("fecha", "dia_operativo", "created_at"):
        if key in datos and datos[key]:
            if es_periodo_cerrado(datos[key]):
                st.error("🔒 **Período Cerrado:** No se permiten registrar o modificar transacciones en un mes contable cerrado.")
                return False
    return True

def validar_periodo_abierto_existente(nombre_tabla: str, antes_json: dict) -> bool:
    if not antes_json or nombre_tabla not in {"ventas", "detalle_venta", "compras", "gastos", "pagos_empleados", "adelantos_empleados", "movimientos_caja", "movimientos_contables", "ventas_pagos", "cuentas_por_cobrar"}:
        return True
    for key in ("fecha", "dia_operativo", "created_at"):
        if key in antes_json and antes_json[key]:
            if es_periodo_cerrado(antes_json[key]):
                st.error("🔒 **Período Cerrado:** No se permiten registrar o modificar transacciones en un mes contable cerrado.")
                return False
    return True

def validar_inmutabilidad_ncf(nombre_tabla: str, antes_json: dict | None) -> bool:
    """
    Conserva inmutables las referencias NCF históricas.

    A&M no emite la corrección fiscal; cualquier procedimiento oficial se
    realiza fuera del sistema siguiendo las instrucciones vigentes de la DGII.
    """
    if nombre_tabla != "ventas":
        return True  # Solo aplica a ventas
    if not antes_json:
        return True  # Sin datos previos, no podemos verificar — dejamos pasar
    ncf_val = str(antes_json.get("ncf") or "").strip()
    if not ncf_val:
        return True  # Sin NCF: la venta puede modificarse normalmente
    # Tiene NCF: bloquear modificación directa
    st.error(
        f"🛡️ **Referencia NCF histórica inmutable ({ncf_val}):** "
        "no se puede modificar ni eliminar directamente. Registre la anulación "
        "interna con su evidencia y tramite cualquier documento fiscal fuera de "
        "A&M mediante el procedimiento oficial aplicable."
    )
    return False

def insertar(nombre_tabla: str, datos: dict) -> bool:
    aplicar_auth_token()
    if not validar_periodo_abierto(nombre_tabla, datos):
        return False
    if nombre_tabla in TABLAS_MULTI_TENANT:
        _tenant = obtener_tenant_actual()
        if _tenant and _tenant != "global":
            if nombre_tabla == "usuarios":
                datos.setdefault("empresa_id", _tenant)
            else:
                if "empresa_id" not in datos:
                    datos["empresa_id"] = _tenant
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        registrar_auditoria_pro(
            accion="insertar",
            modulo=nombre_tabla.capitalize(),
            tabla_afectada=nombre_tabla,
            despues_json=datos,
            descripcion=f"Registro creado en {nombre_tabla}."
        )
        invalidar_cache_tabla(nombre_tabla)
        return True
    except Exception as exc:
        exc_str = str(exc)
        if "23505" in exc_str or "unique constraint" in exc_str.lower():
            st.error("⚠️ **Error de Código Duplicado:** Ya existe un registro con este mismo código en la base de datos de esta empresa.")
        else:
            st.error(f"Error al insertar en {nombre_tabla}: {exc}")
        return False

def _campos_pk(nombre_tabla: str) -> list[str]:
    if nombre_tabla == "ventas":
        return ["id", "identificación"]
    return ["id"]

def actualizar(nombre_tabla: str, fila_id: Any, datos: dict) -> bool:
    aplicar_auth_token()
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    antes_json = None
    try:
        df = DATA[nombre_tabla]
        if not df.empty and "id" in df.columns:
            match = df[df["id"].astype(str) == str(fila_id)]
            if not match.empty:
                antes_json = match.iloc[0].to_dict()
    except Exception:
        pass
        
    if not antes_json:
        try:
            resp = supabase.table(nombre_tabla).select("*").eq("id", fila_id).execute()
            if resp.data:
                antes_json = resp.data[0]
        except Exception:
            pass

    if not validar_periodo_abierto_existente(nombre_tabla, antes_json):
        return False
    # C-03: Bloquear modificación de facturas con NCF emitido
    if not validar_inmutabilidad_ncf(nombre_tabla, antes_json):
        return False

    for campo in campos:
        try:
            supabase.table(nombre_tabla).update(datos).eq(campo, fila_id).execute()
            despues_json = antes_json.copy() if antes_json else {}
            despues_json.update(datos)
            registrar_auditoria_pro(
                accion="actualizar",
                modulo=nombre_tabla.capitalize(),
                tabla_afectada=nombre_tabla,
                registro_id=fila_id,
                antes_json=antes_json,
                despues_json=despues_json,
                descripcion=f"Registro actualizado en {nombre_tabla}."
            )
            invalidar_cache_tabla(nombre_tabla)
            return True
        except Exception as exc:
            ultimo_error = exc
    exc_str = str(ultimo_error) if ultimo_error else ""
    if "23505" in exc_str or "unique constraint" in exc_str.lower():
        st.error(f"⚠️ **Error de Código Duplicado:** Ya existe un registro con este mismo código en la base de datos de esta empresa.")
    else:
        st.error(f"Error al actualizar en {nombre_tabla}: {ultimo_error}")
    return False

def eliminar(nombre_tabla: str, fila_id: Any) -> bool:
    aplicar_auth_token()
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    antes_json = None
    try:
        df = DATA[nombre_tabla]
        if not df.empty and "id" in df.columns:
            match = df[df["id"].astype(str) == str(fila_id)]
            if not match.empty:
                antes_json = match.iloc[0].to_dict()
    except Exception:
        pass

    if not antes_json:
        try:
            resp = supabase.table(nombre_tabla).select("*").eq("id", fila_id).execute()
            if resp.data:
                antes_json = resp.data[0]
        except Exception:
            pass

    if not validar_periodo_abierto_existente(nombre_tabla, antes_json):
        return False
    # C-03: Bloquear eliminación de facturas con NCF emitido
    if not validar_inmutabilidad_ncf(nombre_tabla, antes_json):
        return False

    for campo in campos:
        try:
            supabase.table(nombre_tabla).delete().eq(campo, fila_id).execute()
            registrar_auditoria_pro(
                accion="eliminar",
                modulo=nombre_tabla.capitalize(),
                tabla_afectada=nombre_tabla,
                registro_id=fila_id,
                antes_json=antes_json,
                descripcion=f"Registro eliminado de {nombre_tabla}."
            )
            if nombre_tabla == "productos" and antes_json:
                prod_nombre = antes_json.get("nombre")
                if prod_nombre:
                    try:
                        tenant = obtener_tenant_actual()
                        q = supabase.table("inventario_actual").delete().eq("producto", prod_nombre)
                        if tenant and tenant != "global":
                            q = q.eq("empresa_id", tenant)
                        q.execute()
                        invalidar_cache_tabla("inventario_actual")
                    except Exception:
                        pass
            invalidar_cache_tabla(nombre_tabla)
            return True
        except Exception as exc:
            ultimo_error = exc
    st.error(f"Error al eliminar en {nombre_tabla}: {ultimo_error}")
    return False

def anular(nombre_tabla: str, fila_id: Any, motivo: str = "") -> bool:
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    antes_json = None
    try:
        df = DATA[nombre_tabla]
        if not df.empty and "id" in df.columns:
            match = df[df["id"].astype(str) == str(fila_id)]
            if not match.empty:
                antes_json = match.iloc[0].to_dict()
    except Exception:
        pass

    for campo in campos:
        try:
            supabase.table(nombre_tabla).update({"anulado": True, "motivo_anulacion": motivo}).eq(campo, fila_id).execute()
            despues_json = antes_json.copy() if antes_json else {}
            despues_json["anulado"] = True
            despues_json["motivo_anulacion"] = motivo
            registrar_auditoria_pro(
                accion="anular",
                modulo=nombre_tabla.capitalize(),
                tabla_afectada=nombre_tabla,
                registro_id=fila_id,
                antes_json=antes_json,
                despues_json=despues_json,
                descripcion=f"Registro anulado en {nombre_tabla}. Motivo: {motivo}"
            )
            invalidar_cache_tabla(nombre_tabla)
            return True
        except Exception as exc:
            ultimo_error = exc
    st.error(f"Error al anular en {nombre_tabla}: {ultimo_error}")
    return False

def rpc(func_name: str, params: dict) -> Any:
    aplicar_auth_token()
    return supabase.rpc(func_name, params).execute()

def guardar_venta_rpc(params: dict) -> dict:
    try:
        res = rpc("api_registrar_venta", {"p": params})
        data = res.data[0] if isinstance(res.data, list) and res.data else res.data
        if isinstance(data, dict) and data.get("success"):
            return data
        return {"success": False, "error": data.get("error") if isinstance(data, dict) else "Sin respuesta del servidor"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# =========================================================
# AUDITORÍA / LOGGING
# =========================================================
def registrar_auditoria(accion: str, tabla: str, detalle: str = ""):
    try:
        supabase.table("auditoria").insert(
            {
                "accion": accion,
                "tabla": tabla,
                "usuario": nombre_usuario_actual(),
                "fecha": datetime.now().isoformat(),
                "detalle": detalle,
            }
        ).execute()
    except Exception:
        pass

def json_safe_value(valor):
    try:
        import numpy as np
        if isinstance(valor, (np.integer,)):
            return int(valor)
        if isinstance(valor, (np.floating,)):
            return float(valor)
        if isinstance(valor, (np.bool_,)):
            return bool(valor)
    except Exception:
        pass
    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass
    if isinstance(valor, dict):
        return {str(k): json_safe_value(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [json_safe_value(v) for v in valor]
    if isinstance(valor, tuple):
        return [json_safe_value(v) for v in valor]
    return valor

def json_safe_payload(payload: dict) -> dict:
    return {str(k): json_safe_value(v) for k, v in payload.items()}

# =========================================================
# S-07 · PII MASKING — Enmascarar datos personales en logs
# =========================================================
def _pii_mask(valor: Any) -> Any:
    """Enmascara cédulas, teléfonos y emails en strings antes de persistir en auditoría."""
    if valor is None:
        return None
    if isinstance(valor, dict):
        sensitive = {
            "password", "clave", "token", "access_token", "refresh_token",
            "secret", "totp_secret", "hash", "service_role",
        }
        return {
            k: "[REDACTADO]" if str(k).lower() in sensitive else _pii_mask(v)
            for k, v in valor.items()
        }
    if isinstance(valor, list):
        return [_pii_mask(v) for v in valor]
    if not isinstance(valor, str):
        return valor
    # Cédula dominicana: ###-#######-# o ###########
    valor = re.sub(r'\b(\d{3})-(\d{7})-(\d)\b', r'\1-*******-\3', valor)
    valor = re.sub(r'\b(\d{3})(\d{7})(\d)\b', r'\1*******\3', valor)
    # Teléfono: ###-###-#### o (###) ###-####
    valor = re.sub(r'\b(\d{3})[-.\s](\d{3})[-.\s](\d{4})\b', r'\1-***-\3', valor)
    # Email: mantiene dominio, enmascara usuario
    valor = re.sub(r'\b([A-Za-z0-9._%+\-]{1,3})[A-Za-z0-9._%+\-]*@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b',
                   r'\1***@\2', valor)
    return valor


def registrar_auditoria_pro(
    accion: str,
    modulo: str = "General",
    tabla_afectada: str = "general",
    registro_id: Any = None,
    antes_json: Any = None,
    despues_json: Any = None,
    impacto_economico: float = 0.0,
    nivel_riesgo: str = "bajo",
    riesgo_score: float = 0.0,
    descripcion: str = "",
    revertible: bool = False
) -> None:
    """Inserta un registro de auditoría armonizado y libre de PII."""
    if nivel_riesgo == "bajo" and riesgo_score == 0.0:
        accion_lower = accion.lower()
        if any(k in accion_lower for k in ["eliminar", "borrar", "delete"]):
            nivel_riesgo = "critico"
            riesgo_score = 90.0
        elif any(k in accion_lower for k in ["anular", "anulacion", "void"]):
            nivel_riesgo = "alto"
            riesgo_score = 75.0
        elif any(k in accion_lower for k in ["descuento", "precio", "permisos", "seguridad", "cambio_precio"]):
            nivel_riesgo = "medio"
            riesgo_score = 50.0
        else:
            nivel_riesgo = "bajo"
            riesgo_score = 10.0

    metadata = {
        "antes": _pii_mask(
            json_safe_payload(antes_json)
            if isinstance(antes_json, dict) else antes_json
        ),
        "despues": _pii_mask(
            json_safe_payload(despues_json)
            if isinstance(despues_json, dict) else despues_json
        ),
        "impacto_economico": float(impacto_economico),
        "nivel_riesgo": nivel_riesgo,
        "riesgo_score": float(riesgo_score),
        "revertible": bool(revertible),
        "tenant_id": obtener_tenant_actual(),
    }
    try:
        supabase.rpc("api_audit_event", {
            "p_accion": accion,
            "p_modulo": modulo,
            "p_tabla": tabla_afectada,
            "p_registro_id": str(registro_id) if registro_id is not None else None,
            "p_detalle": _pii_mask(descripcion),
            "p_metadata": metadata,
        }).execute()
    except Exception as exc:
        st.warning(f"No se pudo registrar la evidencia de auditoría: {exc}")

# =========================================================
# LAZY DATA LOAD
# =========================================================
class LazyDataDict(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = leer_tabla(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except Exception:
            return default

    def copy(self):
        return self

    def update(self, other=None, **kwargs):
        self.clear()
        if other:
            if isinstance(other, dict):
                for k, v in other.items():
                    self[k] = v
            elif hasattr(other, "keys"):
                for k in other.keys():
                    self[k] = other[k]

def cargar_datos() -> LazyDataDict:
    return LazyDataDict()

DATA = cargar_datos()

def leer_actualizado(tabla: str) -> pd.DataFrame:
    try:
        tenant = obtener_tenant_actual()
        return _leer_tabla_de_supabase(tabla, tenant=tenant)
    except Exception:
        return DATA.get(tabla, pd.DataFrame()).copy()

def _df_actual(tabla: str) -> pd.DataFrame:
    try:
        return leer_actualizado(tabla)
    except Exception:
        return DATA.get(tabla, pd.DataFrame()).copy()

def buscar_producto_por_codigo(codigo: str):
    if not codigo:
        return None
    from utils import normalizar_texto
    codigo_n = normalizar_texto(codigo)
    if not codigo_n:
        return None
    df = DATA.get("productos", pd.DataFrame()).copy()
    if df.empty or "codigo" not in df.columns:
        return None
    tmp = df.copy()
    tmp["_c"] = tmp["codigo"].astype(str).apply(normalizar_texto)
    match = tmp[tmp["_c"] == codigo_n]
    if match.empty:
        return None
    return match.iloc[0]
