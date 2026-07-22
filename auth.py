import base64
import hashlib
import hmac
import struct
import time
import streamlit as st
try:
    try:
        from core.db import usuario_sesion, nombre_usuario_actual, obtener_tenant_actual, es_superadmin_plataforma
    except ModuleNotFoundError:
        from db import usuario_sesion, nombre_usuario_actual, obtener_tenant_actual, es_superadmin_plataforma
    try:
        from core.utils import normalizar_texto
    except ModuleNotFoundError:
        from utils import normalizar_texto
except ModuleNotFoundError:
    from db import usuario_sesion, nombre_usuario_actual, obtener_tenant_actual, es_superadmin_plataforma
    from utils import normalizar_texto

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

def cerrar_sesion():
    for k in ["usuario_data", "access_token", "refresh_token", "sesion_token", "tenant_actual", "mfa_pendiente"]:
        st.session_state.pop(k, None)
    if "session_cache_tablas" in st.session_state:
        st.session_state["session_cache_tablas"].clear()
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    try:
        st.cache_data.clear()
    except Exception:
        pass
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
        
    permisos = {}
    
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


# =========================================================
# S-02 · BLOQUEO PERSISTENTE + BACKOFF EXPONENCIAL
# Los intentos fallidos se guardan en la tabla `login_intentos`
# en Supabase (usando service_role key), sobreviviendo recargas.
# Backoff: 1 fallo→0s | 3→30s | 5→2min | 7→15min | 10+→1h
# =========================================================
_BACKOFF_TABLA = [
    (10, 3600),   # 10+ intentos → 1 hora
    (7,  900),    # 7+  intentos → 15 minutos
    (5,  120),    # 5+  intentos → 2 minutos
    (3,  30),     # 3+  intentos → 30 segundos
]

def _supabase_admin():
    """Retorna cliente Supabase con service_role para operaciones de auth sin RLS."""
    try:
        try:
            from core.db import obtener_secreto, SUPABASE_URL
        except ModuleNotFoundError:
            from db import obtener_secreto, SUPABASE_URL
        from supabase import create_client
        svc_key = obtener_secreto("SUPABASE_SERVICE_KEY", "")
        if svc_key:
            return create_client(SUPABASE_URL, svc_key)
    except Exception:
        pass
    return None

def registrar_intento_fallido(username: str):
    """Registra intento fallido en BD (persistente) y en session_state (caché local)."""
    # --- Persistencia en Supabase ---
    try:
        adm = _supabase_admin()
        if adm:
            existing = adm.table("login_intentos").select("*").eq("username", username).execute()
            ahora = datetime.now().isoformat()
            if existing.data:
                row = existing.data[0]
                count = (row.get("intentos") or 0) + 1
                duracion = 0
                for min_count, secs in _BACKOFF_TABLA:
                    if count >= min_count:
                        duracion = secs
                        break
                locked_until = (datetime.now() + timedelta(seconds=duracion)).isoformat() if duracion else None
                adm.table("login_intentos").update({
                    "intentos": count,
                    "ultimo_intento": ahora,
                    "bloqueado_hasta": locked_until
                }).eq("username", username).execute()
            else:
                adm.table("login_intentos").insert({
                    "username": username,
                    "intentos": 1,
                    "ultimo_intento": ahora,
                    "bloqueado_hasta": None
                }).execute()
    except Exception:
        pass
    # --- Caché local en session_state (fallback si BD no disponible) ---
    if "login_attempts" not in st.session_state:
        st.session_state["login_attempts"] = {}
    attempts = st.session_state["login_attempts"].get(username, {"count": 0, "locked_until": 0.0})
    attempts["count"] += 1
    duracion_local = 0
    for min_count, secs in _BACKOFF_TABLA:
        if attempts["count"] >= min_count:
            duracion_local = secs
            break
    if duracion_local:
        attempts["locked_until"] = time.time() + duracion_local
    st.session_state["login_attempts"][username] = attempts

def verificar_bloqueo_login(username: str):
    """Verifica bloqueo en BD primero, luego en session_state como fallback."""
    # --- Verificar en Supabase (fuente de verdad) ---
    try:
        adm = _supabase_admin()
        if adm:
            existing = adm.table("login_intentos").select("*").eq("username", username).execute()
            if existing.data:
                row = existing.data[0]
                bloqueado_hasta = row.get("bloqueado_hasta")
                if bloqueado_hasta:
                    from datetime import timezone
                    try:
                        dt_bloqueo = datetime.fromisoformat(bloqueado_hasta.replace("Z", "+00:00"))
                        dt_now = datetime.now(timezone.utc)
                        if dt_bloqueo > dt_now:
                            remaining = int((dt_bloqueo - dt_now).total_seconds())
                            minutes = remaining // 60
                            seconds = remaining % 60
                            st.error(f"🔒 Cuenta bloqueada por intentos fallidos. Intente de nuevo en {minutes}m {seconds}s.")
                            st.stop()
                    except Exception:
                        pass
    except Exception:
        pass
    # --- Fallback: verificar en session_state ---
    if "login_attempts" in st.session_state:
        attempts = st.session_state["login_attempts"].get(username)
        if attempts and attempts.get("locked_until", 0) > time.time():
            remaining = int(attempts["locked_until"] - time.time())
            minutes = remaining // 60
            seconds = remaining % 60
            st.error(f"🔒 Cuenta temporalmente bloqueada. Intente de nuevo en {minutes}m {seconds}s.")
            st.stop()

def limpiar_intentos_fallidos(username: str):
    """Limpia el contador de intentos en BD y session_state tras login exitoso."""
    try:
        adm = _supabase_admin()
        if adm:
            adm.table("login_intentos").delete().eq("username", username).execute()
    except Exception:
        pass
    if "login_attempts" in st.session_state and username in st.session_state["login_attempts"]:
        st.session_state["login_attempts"].pop(username, None)

def mfa_requerido_para_admin(usuario_data: dict) -> bool:
    """
    Retorna True si el usuario es admin/superadmin y NO tiene MFA configurado.
    En ese caso muestra un aviso bloqueante: el admin debe configurar TOTP antes de usar el sistema.
    """
    rol = str(usuario_data.get("rol") or "").lower()
    if rol not in ("admin", "superadmin"):
        return False
    tiene_mfa = bool(usuario_data.get("mfa_enabled")) and bool(usuario_data.get("totp_secret"))
    if not tiene_mfa:
        st.error(
            "🔐 **MFA Requerido:** Su cuenta de administrador debe tener autenticación de dos factores (TOTP) "
            "activada antes de acceder al sistema. Contacte al superadministrador para configurarla."
        )
        return True
    return False

def hashear_clave(password: str) -> str:
    if not password:
        return ""
    p_str = str(password).strip()
    if p_str.startswith("pbkdf2_sha256$600000$"):
        return p_str
    import uuid
    salt = uuid.uuid4().hex
    iterations = 600000
    dk = hashlib.pbkdf2_hmac("sha256", p_str.encode("utf-8"), salt.encode("utf-8"), iterations)
    hash_hex = dk.hex()
    return f"pbkdf2_sha256${iterations}${salt}${hash_hex}"

def verificar_clave_usuario(stored_val: str, input_pwd: str) -> bool:
    try:
        if not stored_val or not input_pwd:
            return False
        stored_clean = str(stored_val).strip()
        pwd_clean = str(input_pwd).strip()
        if not stored_clean.startswith("pbkdf2_sha256$600000$"):
            # Deniega claves heredadas para forzar restablecimiento obligatorio
            return False
        parts = stored_clean.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        stored_hash = parts[3]
        dk = hashlib.pbkdf2_hmac("sha256", pwd_clean.encode("utf-8"), salt.encode("utf-8"), iterations)
        return dk.hex() == stored_hash
    except Exception:
        return False


def verificar_codigo_totp(secret: str, code: str) -> bool:
    try:
        secret = secret.replace(" ", "").upper()
        missing_padding = len(secret) % 8
        if missing_padding:
            secret += "=" * (8 - missing_padding)
        key = base64.b32decode(secret)
        now_interval = int(time.time() // 30)
        # Tolerar clock drift de +/- 30 segundos
        for interval in [now_interval - 1, now_interval, now_interval + 1]:
            msg = struct.pack(">Q", interval)
            h = hmac.new(key, msg, hashlib.sha1).digest()
            o = h[19] & 15
            token = (struct.unpack(">I", h[o:o+4])[0] & 0x7fffffff) % 1000000
            if f"{token:06d}" == str(code).strip():
                return True
    except Exception:
        pass
    return False
