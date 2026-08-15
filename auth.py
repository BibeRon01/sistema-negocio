import streamlit as st
from db import (
    usuario_sesion, nombre_usuario_actual, obtener_tenant_actual,
    es_superadmin_plataforma, supabase, renovar_cliente_sesion,
    limpiar_cache_datos,
)
from utils import normalizar_texto


_SESSION_KEYS = (
    "usuario_data",
    "access_token",
    "refresh_token",
    "sesion_token",
    "tenant_actual",
    "tenant_seleccionado",
    "mfa_pendiente",
    "login_pending_mfa",
    "superadmin_tenant_seleccionado",
    "last_activity",
    "ultimo_check_usuario",
    "_last_session_validation",
    "_supabase_session_client",
    "_supabase_session_fingerprint",
    "session_cache_tablas",
)

def es_admin() -> bool:
    if es_superadmin_plataforma():
        return True
    return normalizar_texto(usuario_sesion().get("rol", "")) == "admin"

def es_cajera() -> bool:
    return normalizar_texto(usuario_sesion().get("rol", "")) in ["cajera", "cajero"]

def tiene_permiso(flag: str) -> bool:
    user = usuario_sesion()
    if not user:
        return False
    if es_admin():
        return True
    return bool(user.get(flag, False))

def limpiar_estado_sesion(*, cerrar_auth: bool = False) -> None:
    """Invalida todo estado local; ningún error conserva una sesión utilizable."""
    if cerrar_auth:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    for key in _SESSION_KEYS:
        st.session_state.pop(key, None)
    limpiar_cache_datos()
    try:
        renovar_cliente_sesion()
    except Exception:
        pass
    try:
        st.cache_data.clear()
    except Exception:
        pass


def cerrar_sesion():
    limpiar_estado_sesion(cerrar_auth=True)
    st.rerun()

# =========================================================
# PERMISOS GRANULARES POR MÓDULO Y ACCIÓN
# =========================================================
def puede_editar_global() -> bool:
    return es_admin() or tiene_permiso("puede_editar_todo")

def puede_ver_utilidad_global() -> bool:
    return es_admin() or tiene_permiso("puede_ver_utilidad")

# --- POS / Ventas ---
def puede_vender() -> bool:
    return es_admin() or tiene_permiso("puede_vender")

def puede_abrir_caja() -> bool:
    return es_admin() or tiene_permiso("puede_abrir_caja") or tiene_permiso("puede_vender")

def puede_cerrar_caja() -> bool:
    return es_admin() or tiene_permiso("puede_cerrar_caja")

def puede_ver_ventas_propias() -> bool:
    return es_admin() or tiene_permiso("puede_ver_ventas_propias")

def puede_ver_todas_ventas() -> bool:
    return es_admin() or tiene_permiso("puede_ver_todas_ventas") or tiene_permiso("puede_ver_reportes")

def puede_editar_ventas() -> bool:
    return es_admin() or tiene_permiso("puede_editar_ventas") or tiene_permiso("puede_editar_todo")

def puede_anular_ventas() -> bool:
    return es_admin() or tiene_permiso("puede_anular") or tiene_permiso("puede_editar_todo")

def puede_eliminar_ventas() -> bool:
    return es_admin() or tiene_permiso("puede_eliminar") or tiene_permiso("puede_editar_todo")

# --- Compras ---
def puede_registrar_compras() -> bool:
    return es_admin() or tiene_permiso("puede_registrar_compras")

def puede_ver_compras() -> bool:
    return es_admin() or tiene_permiso("puede_ver_compras") or tiene_permiso("puede_registrar_compras") or tiene_permiso("puede_ver_reportes")

def puede_editar_compras() -> bool:
    return es_admin() or tiene_permiso("puede_editar_compras") or tiene_permiso("puede_editar_todo")

def puede_eliminar_compras() -> bool:
    return es_admin() or tiene_permiso("puede_eliminar_compras") or tiene_permiso("puede_eliminar")

def puede_aprobar_compras() -> bool:
    return es_admin() or tiene_permiso("puede_aprobar_compras") or tiene_permiso("puede_editar_todo")

# --- Gastos ---
def puede_registrar_gastos() -> bool:
    return es_admin() or tiene_permiso("puede_registrar_gastos")

def puede_ver_gastos() -> bool:
    return es_admin() or tiene_permiso("puede_ver_gastos") or tiene_permiso("puede_registrar_gastos") or tiene_permiso("puede_ver_reportes")

def puede_editar_gastos() -> bool:
    return es_admin() or tiene_permiso("puede_editar_gastos") or tiene_permiso("puede_editar_todo")

def puede_eliminar_gastos() -> bool:
    return es_admin() or tiene_permiso("puede_eliminar_gastos") or tiene_permiso("puede_eliminar")

# --- Inventario ---
def puede_ver_inventario() -> bool:
    return es_admin() or tiene_permiso("puede_ver_inventario") or tiene_permiso("puede_ver_reportes")

def puede_registrar_conteo() -> bool:
    return es_admin() or tiene_permiso("puede_registrar_conteo")

def puede_aplicar_ajuste_inventario() -> bool:
    return es_admin() or tiene_permiso("puede_aplicar_ajuste_inventario") or tiene_permiso("puede_editar_todo")

def puede_editar_inventario() -> bool:
    return es_admin() or tiene_permiso("puede_editar_inventario") or tiene_permiso("puede_editar_todo")

# --- Pérdidas ---
def puede_reportar_perdidas() -> bool:
    return es_admin() or tiene_permiso("puede_reportar_perdidas")

def puede_ver_perdidas() -> bool:
    return es_admin() or tiene_permiso("puede_ver_perdidas") or tiene_permiso("puede_reportar_perdidas") or tiene_permiso("puede_ver_reportes")

def puede_aprobar_perdidas() -> bool:
    return es_admin() or tiene_permiso("puede_aprobar_perdidas") or tiene_permiso("puede_editar_todo")

def puede_debitar_perdidas() -> bool:
    return es_admin() or tiene_permiso("puede_debitar_perdidas") or tiene_permiso("puede_editar_todo")

def puede_editar_perdidas() -> bool:
    return es_admin() or tiene_permiso("puede_editar_perdidas") or tiene_permiso("puede_editar_todo")

def puede_eliminar_perdidas() -> bool:
    return es_admin() or tiene_permiso("puede_eliminar_perdidas") or tiene_permiso("puede_eliminar")

# --- Productos ---
def puede_ver_productos() -> bool:
    return es_admin() or tiene_permiso("puede_ver_productos")

def puede_crear_productos() -> bool:
    return es_admin() or tiene_permiso("puede_crear_productos") or tiene_permiso("puede_editar_todo")

def puede_editar_productos() -> bool:
    return es_admin() or tiene_permiso("puede_editar_productos") or tiene_permiso("puede_editar_todo")

def puede_eliminar_productos() -> bool:
    return es_admin() or tiene_permiso("puede_eliminar_productos") or tiene_permiso("puede_eliminar")


def render_checkboxes_permisos(key_prefix: str, defaults_dict: dict = None) -> dict[str, bool]:
    if defaults_dict is None:
        defaults_dict = {}
        
    # Conserve permisos que todavía no tengan un control visual para evitar
    # borrarlos accidentalmente al editar una cuenta existente.
    permisos = dict(defaults_dict)

    with st.expander("🧭 Acceso general", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_ver_dashboard"] = st.checkbox(
                "Puede ver el dashboard",
                value=bool(defaults_dict.get("puede_ver_dashboard", False)),
                key=f"{key_prefix}_pvd",
            )
            permisos["puede_ver_reportes"] = st.checkbox(
                "Puede ver reportes financieros",
                value=bool(defaults_dict.get("puede_ver_reportes", False)),
                key=f"{key_prefix}_pvr",
            )
        with c2:
            permisos["puede_ver_utilidad"] = st.checkbox(
                "Puede ver utilidad y márgenes",
                value=bool(defaults_dict.get("puede_ver_utilidad", False)),
                key=f"{key_prefix}_pvu",
            )
            permisos["puede_configurar"] = st.checkbox(
                "Puede administrar configuración y nómina",
                value=bool(defaults_dict.get("puede_configurar", False)),
                key=f"{key_prefix}_pcfg",
            )
    
    with st.expander("📦 POS / Ventas", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_vender"] = st.checkbox("Puede vender (POS)", value=bool(defaults_dict.get("puede_vender", True)), key=f"{key_prefix}_pv")
            permisos["puede_abrir_caja"] = st.checkbox("Puede abrir caja", value=bool(defaults_dict.get("puede_abrir_caja", True)), key=f"{key_prefix}_pab")
            permisos["puede_cerrar_caja"] = st.checkbox("Puede cerrar caja", value=bool(defaults_dict.get("puede_cerrar_caja", True)), key=f"{key_prefix}_pce")
            permisos["puede_ver_ventas_propias"] = st.checkbox("Puede ver ventas propias", value=bool(defaults_dict.get("puede_ver_ventas_propias", True)), key=f"{key_prefix}_pvp")
            permisos["ver_clientes"] = st.checkbox("Puede ver/gestionar clientes", value=bool(defaults_dict.get("ver_clientes", False)), key=f"{key_prefix}_vcl")
        with c2:
            permisos["puede_ver_todas_ventas"] = st.checkbox("Puede ver todas las ventas", value=bool(defaults_dict.get("puede_ver_todas_ventas", False)), key=f"{key_prefix}_pvt")
            permisos["puede_editar_ventas"] = st.checkbox("Puede editar ventas/facturas", value=bool(defaults_dict.get("puede_editar_ventas", False)), key=f"{key_prefix}_pev")
            permisos["puede_anular"] = st.checkbox("Puede anular ventas/facturas", value=bool(defaults_dict.get("puede_anular", False)), key=f"{key_prefix}_pan")
            permisos["puede_eliminar"] = st.checkbox("Puede eliminar ventas/facturas", value=bool(defaults_dict.get("puede_eliminar", False)), key=f"{key_prefix}_pel")
            permisos["ver_credito"] = st.checkbox("Puede ver/gestionar créditos", value=bool(defaults_dict.get("ver_credito", False)), key=f"{key_prefix}_vcr")
            
    with st.expander("🛒 Compras", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_registrar_compras"] = st.checkbox("Puede registrar compras", value=bool(defaults_dict.get("puede_registrar_compras", False)), key=f"{key_prefix}_prc")
            permisos["puede_ver_compras"] = st.checkbox("Puede ver compras", value=bool(defaults_dict.get("puede_ver_compras", False)), key=f"{key_prefix}_pvc")
            permisos["puede_editar_compras"] = st.checkbox("Puede editar compras", value=bool(defaults_dict.get("puede_editar_compras", False)), key=f"{key_prefix}_pec")
        with c2:
            permisos["puede_eliminar_compras"] = st.checkbox("Puede eliminar compras", value=bool(defaults_dict.get("puede_eliminar_compras", False)), key=f"{key_prefix}_pelc")
            permisos["puede_aprobar_compras"] = st.checkbox("Puede aprobar compras", value=bool(defaults_dict.get("puede_aprobar_compras", False)), key=f"{key_prefix}_pac")
            
    with st.expander("💰 Gastos", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_registrar_gastos"] = st.checkbox("Puede registrar gastos", value=bool(defaults_dict.get("puede_registrar_gastos", False)), key=f"{key_prefix}_prg")
            permisos["puede_ver_gastos"] = st.checkbox("Puede ver gastos", value=bool(defaults_dict.get("puede_ver_gastos", False)), key=f"{key_prefix}_pvg")
        with c2:
            permisos["puede_editar_gastos"] = st.checkbox("Puede editar gastos", value=bool(defaults_dict.get("puede_editar_gastos", False)), key=f"{key_prefix}_peg")
            permisos["puede_eliminar_gastos"] = st.checkbox("Puede eliminar gastos", value=bool(defaults_dict.get("puede_eliminar_gastos", False)), key=f"{key_prefix}_pelg")
            
    with st.expander("📊 Inventario", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_ver_inventario"] = st.checkbox("Puede ver inventario", value=bool(defaults_dict.get("puede_ver_inventario", False)), key=f"{key_prefix}_pvi")
            permisos["puede_registrar_conteo"] = st.checkbox("Puede registrar conteo de inventario", value=bool(defaults_dict.get("puede_registrar_conteo", False)), key=f"{key_prefix}_prco")
        with c2:
            permisos["puede_aplicar_ajuste_inventario"] = st.checkbox("Puede aplicar ajustes de inventario", value=bool(defaults_dict.get("puede_aplicar_ajuste_inventario", False)), key=f"{key_prefix}_paai")
            permisos["puede_editar_inventario"] = st.checkbox("Puede editar inventario", value=bool(defaults_dict.get("puede_editar_inventario", False)), key=f"{key_prefix}_pein")
            
    with st.expander("📉 Pérdidas", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_reportar_perdidas"] = st.checkbox("Puede reportar pérdidas", value=bool(defaults_dict.get("puede_reportar_perdidas", False)), key=f"{key_prefix}_prp")
            permisos["puede_ver_perdidas"] = st.checkbox("Puede ver historial de pérdidas", value=bool(defaults_dict.get("puede_ver_perdidas", False)), key=f"{key_prefix}_pvp_l")
            permisos["puede_editar_perdidas"] = st.checkbox("Puede editar pérdidas", value=bool(defaults_dict.get("puede_editar_perdidas", False)), key=f"{key_prefix}_pepl")
        with c2:
            permisos["puede_aprobar_perdidas"] = st.checkbox("Puede aprobar pérdidas", value=bool(defaults_dict.get("puede_aprobar_perdidas", False)), key=f"{key_prefix}_papl")
            permisos["puede_debitar_perdidas"] = st.checkbox("Puede descontar pérdidas de inventario", value=bool(defaults_dict.get("puede_debitar_perdidas", False)), key=f"{key_prefix}_pdpl")
            permisos["puede_eliminar_perdidas"] = st.checkbox("Puede eliminar pérdidas", value=bool(defaults_dict.get("puede_eliminar_perdidas", False)), key=f"{key_prefix}_peel")
            
    with st.expander("🏷️ Productos", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            permisos["puede_ver_productos"] = st.checkbox("Puede ver catálogo de productos", value=bool(defaults_dict.get("puede_ver_productos", False)), key=f"{key_prefix}_pvpr")
            permisos["puede_crear_productos"] = st.checkbox("Puede crear productos", value=bool(defaults_dict.get("puede_crear_productos", False)), key=f"{key_prefix}_pcpr")
            permisos["puede_editar_productos"] = st.checkbox("Puede editar productos", value=bool(defaults_dict.get("puede_editar_productos", False)), key=f"{key_prefix}_pepr")
        with c2:
            permisos["puede_eliminar_productos"] = st.checkbox("Puede eliminar productos", value=bool(defaults_dict.get("puede_eliminar_productos", False)), key=f"{key_prefix}_pelpr")
            
    return permisos
