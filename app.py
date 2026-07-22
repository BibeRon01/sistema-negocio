# VERSION CONFIGURADA PARA PRODUCCIÓN Y MODULARIZADA
import streamlit as st
import pandas as pd
from datetime import date
import streamlit.components.v1 as components

# Configuración de página
st.set_page_config(page_title="Sistema de Negocio PRO", layout="wide")

# Ocultar la barra y botones por defecto de Streamlit (White-Label Puro)
st.markdown("""
<style>
/* Hacemos la cabecera transparente pero visible para que el botón de expandir/contraer funcione */
[data-testid="stHeader"] {
    background-color: transparent !important;
    background: transparent !important;
}
footer {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
.viewerBadge_container__1QS1G {display: none !important;}
button[title="View source code"] {display: none !important;}
/* Ocultar menú superior y botón de despliegue */
[data-testid="stMainMenu"], #MainMenu {display: none !important;}
[data-testid="stDeployButton"] {display: none !important;}
</style>
""", unsafe_allow_html=True)

# Importar núcleo con resolución de ruta
import os
import sys

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

try:
    from db import *
    from auth import *
    from utils import *
    from helpers import *
except Exception as _e_root:
    try:
        try:
            from core.db import *
        except ModuleNotFoundError:
            from db import *
        try:
            from core.auth import *
        except ModuleNotFoundError:
            from auth import *
        try:
            from core.utils import *
        except ModuleNotFoundError:
            from utils import *
        try:
            from core.helpers import *
        except ModuleNotFoundError:
            from helpers import *
    except Exception as _e_core:
        st.error(f"⚠️ **Error cargando módulos iniciales:**\n- Raíz: `{_e_root}`\n- Subcarpeta: `{_e_core}`")
        st.stop()

# Validar instalación de dependencias en Streamlit Cloud
if create_client is None:
    st.error("⚠️ **Falta la librería `supabase` en el servidor de Streamlit Cloud**")
    st.info("Por favor asegúrate de incluir el archivo `requirements.txt` en la raíz de tu repositorio en GitHub para que Streamlit Cloud instale automáticamente las dependencias.")
    st.stop()

# Validar que los secretos de Supabase están configurados
if not supabase:
    st.error("⚠️ **Faltan las credenciales de Supabase en Streamlit Cloud**")
    st.info("Por favor ingresa a **Manage app -> Settings -> Secrets** en el panel de Streamlit Cloud y añade:")
    st.code("""
SUPABASE_URL = "https://tu-proyecto.supabase.co"
SUPABASE_KEY = "tu-anon-key-de-supabase"
""", language="toml")
    st.stop()

# Importar vistas modulares (Soporta archivos en la raíz o en subcarpeta modules/)
try:
    from pos_view import *
    from inventario_view import *
    from gastos_view import *
    from ia_view import *
    from contabilidad_view import *
    from nomina_view import *
    from auditoria_view import *
    from central_am_view import *
    from admin_view import *
    from academia_view import *
    from notas_credito_view import *
    from sucursales_view import *
    from facturacion_electronica_view import *
    from cxp_view import *
except Exception:
    from modules.pos_view import *
    from modules.inventario_view import *
    from modules.gastos_view import *
    from modules.ia_view import *
    from modules.contabilidad_view import *
    from modules.nomina_view import *
    from modules.auditoria_view import *
    from modules.central_am_view import *
    from modules.admin_view import *
    from modules.academia_view import *
    from modules.notas_credito_view import *
    from modules.sucursales_view import *
    from modules.facturacion_electronica_view import *
    from modules.cxp_view import *

# 1. Login simple y autenticación
if not login_simple():
    st.stop()

# Forzar visibilidad del Sidebar y del Header
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        display: flex !important;
    }
    [data-testid="stHeader"] {
        display: flex !important;
    }
</style>
""", unsafe_allow_html=True)

verificar_licencia_y_alertas()

# =========================================================
# SIDEBAR
# =========================================================
cfg = obtener_configuracion()
logo_cfg = str(cfg.get("logo_url") or "")
_sidebar_logo = logo_cfg or AM_LOGO_B64
if _sidebar_logo:
    st.sidebar.markdown(f"""
<div style='padding: 8px; background: linear-gradient(135deg,#0d0d0d,#1a1a2e); border-radius:14px; text-align:center; margin-bottom:8px; box-shadow:0 4px 20px rgba(212,175,55,0.2); border:1px solid rgba(212,175,55,0.2);'>
<img src='{_sidebar_logo}' style='width:100%; max-width:180px; border-radius:10px;' />
</div>
""", unsafe_allow_html=True)

_tenant_actual = obtener_tenant_actual()
st.sidebar.markdown(f"""
<div style='padding: 10px 0px 15px 0px; border-bottom: 1px solid rgba(0,0,0,0.1); margin-bottom: 10px;'>
<h3 style='margin: 0; font-size: 18px; font-weight: 800; color: #13783b;'>{cfg.get("nombre_sistema") or "Sistema contable A&M"}</h3>
<p style='margin: 2px 0 0 0; font-size: 13px; font-weight: 600; color: #4b5563; text-transform: uppercase; letter-spacing: 0.5px;'>💼 {cfg.get("negocio_nombre") or "Sistema de Negocio PRO"}</p>
<p style='margin: 4px 0 0 0; font-size: 11px; font-weight: 700; color: #6b7280; font-family: monospace; background: #e5e7eb; padding: 2px 6px; border-radius: 4px; display: inline-block;'>🔴 Versión {VERSION_SISTEMA}</p>
</div>
""", unsafe_allow_html=True)

usuario_data_map = st.session_state.get("usuario_data", {})
es_superadmin_usr = es_superadmin_plataforma()

if es_superadmin_usr:
    try:
        cfgs = supabase.table("configuracion_sistema").select("propietario, negocio_nombre").execute().data or []
    except Exception:
        cfgs = []
    
    opciones = {"global": "👑 Super-Admin (Todas)"}
    for c in cfgs:
        prop = c.get("propietario")
        nombre = c.get("negocio_nombre")
        if prop and prop != "global":
            opciones[prop] = f"🏢 {nombre or prop.upper()}"
            
    sel_idx = 0
    keys_list = list(opciones.keys())
    current_sel = st.session_state.get("superadmin_tenant_seleccionado", "global")
    if current_sel in keys_list:
        sel_idx = keys_list.index(current_sel)
        
    empresa_seleccionada = st.sidebar.selectbox(
        "🏢 Empresa Activa",
        options=keys_list,
        format_func=lambda x: opciones[x],
        index=sel_idx,
        key="superadmin_tenant_selectbox"
    )
    
    if empresa_seleccionada != current_sel:
        st.session_state["superadmin_tenant_seleccionado"] = empresa_seleccionada
        st.session_state.pop("session_cache_tablas", None)
        st.rerun()
else:
    _badge_color = "#13783b"
    _badge_label = f"🏢 {(_tenant_actual or 'N/A').upper()}"
    st.sidebar.markdown(f"""
    <div style='background:rgba(0,0,0,0.08); border-radius:8px; padding:4px 10px; margin-bottom:4px; text-align:center; border:1px solid {_badge_color}33;'>
    <span style='font-size:11px; font-weight:700; color:{_badge_color}; letter-spacing:1px;'>{_badge_label}</span>
    </div>
    """, unsafe_allow_html=True)

st.sidebar.caption(f"👤 Usuario: {nombre_usuario_actual()} | Rol: {str(usuario_sesion().get('rol', '')).upper()}")
if st.sidebar.button("🚪 Cerrar sesión"):
    cerrar_sesion()

menu_base = [
    "Dashboard",
    "Caja",
    "Dinero Real",
    "POS",
    "Productos",
    "Clientes",
    "Proveedores",
    "Inventario Actual",
    "Historial de Inventario",
    "Conteo Inventario",
    "Ajustes Inventario",
    "Ventas",
    "Compras",
    "Catálogo de Gastos",
    "Gastos",
    "Empleados",
    "Nómina",
    "Pagos Empleados",
    "Pérdidas",
    "Gastos Dueño",
    "Cierre de Caja",
    "Estado de Resultados",
    "Reportes DGII",
    "Distribución Beneficios",
    "Activos Fijos",
    "Capital Base",
    "Libro Mayor",
    "Cierre de Período",
    "Informes",
    "Créditos",
    "Sucursales",
    "Facturación Electrónica e-CF",
    "Cuentas por Pagar (CxP)",
    "Usuarios",
    "Configuración",
    "Auditoría PRO",
    "Mejoras del sistema",
    "🔮 Predicciones IA",
]

if obtener_tenant_actual() == "global":
    menu_base.append("🏢 Gestión de Empresas")

if es_admin():
    menu_opciones = ["Dashboard", "Caja", "Dinero Real"] + [m for m in menu_base if m not in ["Dashboard", "Caja", "Dinero Real", "Cierre de Caja"]]
else:
    menu_opciones = []
    if puede_vender():
        menu_opciones += ["Caja", "POS"]
    if tiene_permiso("ver_clientes"):
        menu_opciones += ["Clientes"]
    if tiene_permiso("ver_credito"):
        menu_opciones += ["Créditos"]
    if tiene_permiso("puede_ver_ventas_propias") or tiene_permiso("puede_ver_todas_ventas"):
        menu_opciones += ["Ventas"]
    if tiene_permiso("puede_cerrar_caja"):
        menu_opciones += ["Cierre de Caja"]
    if tiene_permiso("puede_ver_productos"):
        menu_opciones += ["Productos"]
    if puede_ver_compras() or puede_registrar_compras():
        menu_opciones += ["Compras", "Proveedores"]
    if puede_ver_gastos() or puede_registrar_gastos():
        menu_opciones += ["Gastos", "Catálogo de Gastos"]
    if puede_ver_inventario():
        menu_opciones += ["Inventario Actual", "Historial de Inventario"]
    if puede_registrar_conteo():
        menu_opciones += ["Conteo Inventario"]
    if puede_aplicar_ajuste_inventario() or puede_editar_inventario():
        menu_opciones += ["Ajustes Inventario"]
    if puede_reportar_perdidas() or puede_ver_perdidas() or puede_aprobar_perdidas():
        menu_opciones += ["Pérdidas"]
    if tiene_permiso("puede_ver_dashboard"):
        menu_opciones += ["Dashboard"]
    if tiene_permiso("puede_ver_reportes"):
        menu_opciones += ["Informes", "Estado de Resultados"]
    if tiene_permiso("puede_configurar"):
        menu_opciones += ["Configuración", "Usuarios", "Empleados", "Nómina", "Pagos Empleados", "Activos Fijos", "Capital Base"]
    if tiene_permiso("puede_ver_reportes"):
        menu_opciones += ["Reportes DGII", "🔮 Predicciones IA"]

    menu_opciones = [m for m in menu_base if m in menu_opciones]
    menu_opciones = list(dict.fromkeys(menu_opciones)) or ["Caja", "POS"]
    menu_opciones = [m for m in menu_opciones if m in ["🏢 Gestión de Empresas", "🔒 Mi Perfil"] or verificar_plan_permite(m)]

if not es_admin() and "Dinero Real" in menu_opciones:
    menu_opciones = [m for m in menu_opciones if m != "Dinero Real"]

if usuario_sesion():
    menu_opciones.append("🔒 Mi Perfil")

# Definir la estructura de navegación de doble nivel (Categorías y Sub-menús)
CATEGORIAS = {
    "📊 Operaciones y POS": ["POS", "Caja", "Dashboard", "Dinero Real"],
    "📦 Inventario y Pérdidas": ["Productos", "Inventario Actual", "Historial de Inventario", "Conteo Inventario", "Ajustes Inventario", "Pérdidas"],
    "💼 Ventas y Compras": ["Ventas", "Clientes", "Créditos", "Compras", "Proveedores", "Cuentas por Pagar (CxP)", "Notas de Crédito"],
    "🏛️ Finanzas y DGII": ["Estado de Resultados", "Reportes DGII", "Facturación Electrónica e-CF", "Libro Mayor", "Cierre de Período", "Informes", "Capital Base", "Activos Fijos", "Distribución Beneficios", "Academia DGII"],
    "⚙️ Administración y Nómina": ["Configuración", "Usuarios", "Sucursales", "Empleados", "Nómina", "Pagos Empleados", "Catálogo de Gastos", "Gastos", "Gastos Dueño", "Auditoría PRO", "🔮 Predicciones IA", "Mejoras del sistema", "🏢 Gestión de Empresas", "🔒 Mi Perfil"]
}

categorias_usuario = {}
for cat, sub_items in CATEGORIAS.items():
    items_hab = [i for i in sub_items if i in menu_opciones]
    if items_hab:
        categorias_usuario[cat] = items_hab

if categorias_usuario:
    # Preservar o restaurar la última categoría seleccionada si es posible
    cat_keys = list(categorias_usuario.keys())
    cat_elegida = st.sidebar.selectbox("📂 Módulo Principal", cat_keys, key="pos_sb_categoria_principal")
    menu = st.sidebar.selectbox("📄 Opción", categorias_usuario[cat_elegida], key="pos_sb_opcion")
else:
    menu = "POS"

# 🤖 Asistente Fiscal Ayuda AIM integrado en la barra lateral
st.sidebar.markdown("---")
with st.sidebar.expander("🤖 Ayuda AIM (Asistente Fiscal)", expanded=False):
    st.write("Pregúntame sobre comprobantes (ej. ¿Qué es un E34? o ¿Qué es el ITBIS?):")
    pregunta_ai = st.text_input("Escribe tu duda...", key="pos_sidebar_ayuda_aim_q")
    if pregunta_ai:
        p_norm = normalizar_texto(pregunta_ai)
        if "e34" in p_norm or "nota de credito" in p_norm:
            st.info("📊 **Nota de Crédito (E34):** Sirve para anular o modificar facturas ya emitidas (por devoluciones o errores). Devuelve el stock al inventario automáticamente.")
        elif "e31" in p_norm or "credito fiscal" in p_norm:
            st.info("🏢 **Crédito Fiscal (E31):** Utilizado por empresas para deducir gastos e ITBIS. Requiere obligatoriamente registrar RNC y Razón Social.")
        elif "e32" in p_norm or "consumo" in p_norm:
            st.info("👤 **Factura de Consumo (E32):** Para consumidores finales. No exige RNC obligatoriamente en ventas normales.")
        elif "e45" in p_norm or "gubernamental" in p_norm or "gobierno" in p_norm:
            st.info("🏛️ **Factura Gubernamental (E45):** Exclusivo para vender a instituciones del Estado. Requiere RNC del Estado, Dependencia y Orden de Compra.")
        elif "itbis" in p_norm or "impuesto" in p_norm:
            st.info("💰 **ITBIS:** Impuesto al consumo del 18% en República Dominicana. Se desglosa en comprobantes fiscales válidos.")
        elif "isc" in p_norm or "selectivo" in p_norm:
            st.info("🥃 **Impuesto Selectivo al Consumo (ISC):** Grava bebidas alcohólicas y tabaco. Viene incorporado en el costo del distribuidor, no se calcula en la caja.")
        elif "607" in p_norm:
            st.info("📁 **Formato 607:** Reporte mensual de ventas con NCF que se envía a la DGII antes del día 15 de cada mes.")
        elif "606" in p_norm:
            st.info("📁 **Formato 606:** Reporte mensual de compras y gastos de la empresa enviado a la DGII.")
        else:
            st.info("💡 **Consejo:** Intenta preguntar con palabras clave como 'E34', 'ITBIS', 'E31', 'E45' o 'ISC' para obtener respuestas.")

if st.sidebar.button("🔄 Recargar nube"):
    st.session_state.pop("session_cache_tablas", None)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 Personalizar Marca")
temas_disponibles = list(TEMAS_CSS.keys())
tema_actual_db = obtener_tema_guardado()
if "tema_actual" not in st.session_state:
    st.session_state["tema_actual"] = tema_actual_db if tema_actual_db in temas_disponibles else temas_disponibles[0]

tema_elegido = st.sidebar.selectbox("Seleccione el Tema", temas_disponibles, index=temas_disponibles.index(st.session_state["tema_actual"]), key="select_tema_sb")
if tema_elegido != st.session_state["tema_actual"]:
    st.session_state["tema_actual"] = tema_elegido
    guardar_tema_en_db(tema_elegido)
    st.rerun()

st.markdown(TEMAS_CSS[st.session_state["tema_actual"]], unsafe_allow_html=True)

# GESTOR GLOBAL DE IMPRESIÓN
if "imprimir_apertura_gaveta" in st.session_state:
    components.html(st.session_state["imprimir_apertura_gaveta"], height=0)
    st.session_state.pop("imprimir_apertura_gaveta")

if st.session_state.get("imprimir_cierre_z"):
    st.success("🎉 ¡Caja cerrada exitosamente! Imprime el comprobante de Cierre Z a continuación.")
    html_z = st.session_state["imprimir_cierre_z"]
    script_auto = """
    <script>
      window.onload = function() {
        window.print();
        setTimeout(function() {
          window.close();
        }, 1500);
      };
    </script>
    """
    html_z_descarga = html_z.replace("</body>", f"{script_auto}</body>") if "</body>" in html_z else html_z + script_auto
    
    st.download_button(
        "📥 Descargar e Imprimir Cierre Z (Térmico)",
        data=html_z_descarga.encode("utf-8"),
        file_name="cierre_z.html",
        mime="text/html",
        key="descargar_cierre_z_auto_print",
        help="Descarga el Cierre Z y ábrelo en tu navegador local para mandarlo a imprimir automáticamente.",
        use_container_width=True
    )
    components.html(st.session_state["imprimir_cierre_z"], height=800, scrolling=True)
    if st.button("✅ Confirmar y terminar turno", key="btn_clear_cierre_z", use_container_width=True):
        st.session_state.pop("imprimir_cierre_z")
        st.rerun()
    st.stop()

# =========================================================
# RUTEO DE VISTAS MODULARES
# =========================================================
if menu == "Dashboard":
    render_dashboard()
elif menu == "Productos":
    render_productos()
elif menu == "Inventario Actual":
    render_inventario_actual()
elif menu == "Historial de Inventario":
    render_historial_inventario()
elif menu == "Conteo Inventario":
    render_conteo_inventario()
elif menu == "Ajustes Inventario":
    render_ajustes_inventario()
elif menu == "Ventas":
    render_ventas()
elif menu == "Compras":
    render_compras()
elif menu == "Catálogo de Gastos":
    render_catalogo_gastos()
elif menu == "Gastos":
    render_gastos()
elif menu == "Empleados":
    render_empleados()
elif menu == "Nómina":
    render_nomina()
elif menu == "Pagos Empleados":
    render_pagos_empleados()
elif menu == "Pérdidas":
    render_perdidas()
elif menu == "Gastos Dueño":
    render_gastos_dueno()
elif menu == "Caja":
    render_caja()
elif menu == "Estado de Resultados":
    render_estado_resultados()
elif menu == "Reportes DGII":
    render_reportes_dgii()
elif menu == "Informes":
    render_informes()
elif menu == "Academia DGII":
    render_academia_dgii()
elif menu == "Notas de Crédito":
    render_notas_credito()
elif menu == "Auditoría PRO":
    render_auditoria_pro()
elif menu == "🔮 Predicciones IA":
    render_predicciones_ia()
elif menu == "Mejoras del sistema":
    render_mejoras_sistema()
elif menu == "POS":
    render_pos()
elif menu == "Dinero Real":
    render_dinero_real()
elif menu == "Clientes":
    render_clientes()
elif menu == "Proveedores":
    render_proveedores()
elif menu == "Créditos":
    render_creditos()
elif menu == "Distribución Beneficios":
    render_distribucion_beneficios()
elif menu == "Capital Base":
    render_capital_base()
elif menu == "Activos Fijos":
    render_activos_fijos()
elif menu == "Usuarios":
    render_usuarios()
elif menu == "Configuración":
    render_configuracion()
elif menu == "🏢 Gestión de Empresas":
    render_gestion_empresas()
elif menu == "🔒 Mi Perfil":
    render_mi_perfil()
elif menu == "Cierre de Caja":
    st.info("Para realizar el cierre de caja, diríjase a la sección 'Caja' y seleccione la opción correspondiente.")
elif menu == "Libro Mayor":
    render_libro_mayor()
elif menu == "Cierre de Período":
    render_cierre_periodo()
elif menu == "Sucursales":
    render_sucursales()
elif menu == "Facturación Electrónica e-CF":
    render_facturacion_electronica()
elif menu == "Cuentas por Pagar (CxP)":
    render_cxp()


