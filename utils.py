import base64
import html as _html_mod
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any
import pandas as pd
import streamlit as st

# =========================================================
# S-03 · SANITIZACIÓN XSS — usar en todo HTML dinámico
# =========================================================
def html_escape(valor: Any) -> str:
    """Escapa caracteres HTML peligrosos en valores dinámicos.
    Usar siempre que se interpole una variable en un f-string
    que luego se pasa a st.markdown(..., unsafe_allow_html=True).
    Ejemplo: st.markdown(f"<div>{html_escape(nombre)}</div>", unsafe_allow_html=True)
    """
    if valor is None:
        return ""
    return _html_mod.escape(str(valor), quote=True)


def limpiar_texto(valor: Any) -> str:
    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass
    return str(valor).strip()


def quitar_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )


def normalizar_texto(valor: Any) -> str:
    txt = limpiar_texto(valor).lower()
    txt = quitar_acentos(txt)
    txt = txt.replace("-", " ").replace("_", " ")
    txt = " ".join(txt.split())
    return txt


def limpiar_numero(valor: Any) -> float | None:
    if pd.isna(valor) or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    txt = str(valor).strip()
    txt = txt.replace("RD$", "").replace("rd$", "").replace("$", "")
    txt = txt.replace(",", "")
    txt = txt.replace(" ", "")
    try:
        return float(txt)
    except Exception:
        return None


def parsear_fecha(valor: Any) -> str | None:
    if pd.isna(valor) or valor == "":
        return None
    try:
        dt = pd.to_datetime(valor)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def selector_fechas_universal(key_base: str) -> tuple:
    opciones = ["Hoy", "Ayer", "Últimos 7 días", "Últimos 30 días", "Este mes", "Mes anterior", "Personalizado"]
    seleccion = st.selectbox("Rango de Fecha", opciones, index=4, key=f"{key_base}_rango_preset")
    
    hoy = date.today()
    if seleccion == "Hoy":
        desde, hasta = hoy, hoy
    elif seleccion == "Ayer":
        ayer = hoy - timedelta(days=1)
        desde, hasta = ayer, ayer
    elif seleccion == "Últimos 7 días":
        desde, hasta = hoy - timedelta(days=6), hoy
    elif seleccion == "Últimos 30 días":
        desde, hasta = hoy - timedelta(days=29), hoy
    elif seleccion == "Este mes":
        desde = date(hoy.year, hoy.month, 1)
        hasta = hoy
    elif seleccion == "Mes anterior":
        primer_dia_este_mes = date(hoy.year, hoy.month, 1)
        ultimo_dia_mes_anterior = primer_dia_este_mes - timedelta(days=1)
        desde = date(ultimo_dia_mes_anterior.year, ultimo_dia_mes_anterior.month, 1)
        hasta = ultimo_dia_mes_anterior
    else:
        col1, col2 = st.columns(2)
        with col1:
            desde = st.date_input("Desde", value=hoy - timedelta(days=30), key=f"{key_base}_custom_desde")
        with col2:
            hasta = st.date_input("Hasta", value=hoy, key=f"{key_base}_custom_hasta")
            
    return desde, hasta


def normalizar_item_carrito(item: dict) -> dict:
    """Asegura que cada item del carrito tenga nombre/producto visibles."""
    if not isinstance(item, dict):
        return {}
    nom = buscar_nombre_producto_por_item(item)
    if nom:
        item["producto"] = nom
        item["nombre"] = nom
    else:
        item["producto"] = item.get("producto") or item.get("nombre") or ""
        item["nombre"] = item.get("nombre") or item.get("producto") or ""
    return item


def recalcular_item_carrito(item: dict) -> dict:
    item = normalizar_item_carrito(dict(item))
    cantidad = float(limpiar_numero(item.get("cantidad")) or 0)
    precio = float(limpiar_numero(item.get("precio_unitario")) or limpiar_numero(item.get("precio")) or 0)
    item["cantidad"] = cantidad
    item["precio_unitario"] = precio
    item["total_linea"] = cantidad * precio
    return item


def carrito_limpio() -> list:
    """Devuelve el carrito normalizado para mostrar/facturar."""
    car = st.session_state.get("pos_carrito", [])
    return [normalizar_item_carrito(dict(x)) for x in car if isinstance(x, dict)]


def buscar_nombre_producto_por_item(item: dict) -> str:
    """Busca el nombre del producto desde el item del carrito usando nombre, producto, producto_id o código."""
    if not isinstance(item, dict):
        return ""
    nombre = item.get("producto") or item.get("nombre") or item.get("descripcion")
    if nombre:
        return str(nombre)

    prod_id = item.get("producto_id") or item.get("id")
    codigo = item.get("codigo") or item.get("codigo_barra")

    try:
        from core.db import DATA
        prods = DATA.get("productos", pd.DataFrame()).copy()
    except Exception:
        prods = pd.DataFrame()

    if not prods.empty:
        if prod_id and "id" in prods.columns:
            fila = prods[prods["id"].astype(str) == str(prod_id)]
            if not fila.empty:
                return str(fila.iloc[0].get("nombre") or fila.iloc[0].get("producto") or "")
        if codigo:
            for col in ["codigo", "codigo_barra", "sku"]:
                if col in prods.columns:
                    fila = prods[prods[col].astype(str) == str(codigo)]
                    if not fila.empty:
                        return str(fila.iloc[0].get("nombre") or fila.iloc[0].get("producto") or "")

    return ""


def nombre_item(item):
    """Devuelve el nombre visible del producto."""
    try:
        return buscar_nombre_producto_por_item(item) or item.get("nombre") or item.get("producto") or ""
    except Exception:
        return ""


def numero_factura_visible(row: Any) -> str:
    try:
        for campo in ["numero_factura", "factura", "n_factura"]:
            val = row.get(campo)
            txt = limpiar_texto(val)
            if txt:
                if re.fullmatch(r"\d{1,5}", txt):
                    return txt.zfill(5)
                return txt
        val_id = row.get("id") or row.get("identificación") or row.get("identificacion")
        if limpiar_texto(val_id):
            return limpiar_texto(val_id)
    except Exception:
        pass
    return ""


def predecir_categoria_y_tipo_gasto(nombre: str) -> tuple:
    if not nombre:
        return "Otros Gastos", "variable"
        
    nombre_lower = nombre.lower()
    
    # 1. Intentar aprender del histórico de la empresa (IA Supervisada)
    try:
        from core.db import _df_actual
        gastos_hist = _df_actual("gastos")
        if not gastos_hist.empty and "nombre" in gastos_hist.columns:
            coincidencias = gastos_hist[gastos_hist["nombre"].astype(str).str.lower() == nombre_lower]
            if not coincidencias.empty:
                ultima_coincidencia = coincidencias.iloc[-1]
                categoria_sug = ultima_coincidencia.get("categoria") or ""
                tipo_sug = ultima_coincidencia.get("tipo") or "fijo"
                if categoria_sug:
                    return categoria_sug, tipo_sug
    except Exception:
        pass
        
    # 2. Diccionario de fallbacks semánticos inteligentes
    mapeos = {
        ("luz", "energia", "energía", "electricidad", "edeeste", "edenorte", "edesur"): ("Servicios Públicos / Electricidad", "fijo"),
        ("alquiler", "renta", "local"): ("Alquiler / Arrendamiento", "fijo"),
        ("agua", "caasd", "botellon", "botellones"): ("Servicios Públicos / Agua", "fijo"),
        ("internet", "telefono", "teléfono", "claro", "altice", "telecomunicaciones"): ("Telecomunicaciones", "fijo"),
        ("basura", "ayuntamiento", "alcaldia", "alcaldía"): ("Servicios Públicos / Basura", "fijo"),
        ("sueldo", "salario", "quincena", "nomina", "nómina", "pago empleado", "pagos empleados"): ("Gastos de Personal", "fijo"),
        ("tss", "seguro medico", "seguridad social", "sfs", "afp", "infotep"): ("Cargas Sociales / TSS", "fijo"),
        ("gasolina", "gasoil", "combustible", "transporte", "pasaje", "peaje", "flete"): ("Transporte y Movilidad", "variable"),
        ("harina", "azucar", "azúcar", "huevo", "leche", "mantequilla", "materia prima", "ingredientes", "pan", "queso"): ("Materia Prima", "variable"),
        ("publicidad", "anuncio", "instagram", "facebook", "marketing", "volantes", "letrero"): ("Publicidad y Marketing", "variable"),
        ("reparacion", "mantenimiento", "pintura", "plomero", "reparación", "reparar", "aire acondicionado"): ("Mantenimiento y Reparaciones", "variable"),
        ("limpieza", "cloro", "detergente", "desinfectante", "escoba", "papel higienico", "papel higiénico"): ("Limpieza e Higiene", "variable"),
        ("desechables", "vasos", "platos", "servilletas", "fundas", "cajas"): ("Materiales Desechables", "variable"),
        ("comision", "comisión", "interes", "interés", "banco", "bancario", "comisiones"): ("Gastos Financieros", "variable"),
    }
    
    for claves, (cat, tipo) in mapeos.items():
        if any(k in nombre_lower for k in claves):
            return cat, tipo
            
    return "Otros Gastos", "variable"


def agregar_columna_codigo_secuencial(df: pd.DataFrame, nombre_tabla: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
        
    df = df.copy()
    PREFIJOS = {
        "productos": "PO",
        "compras": "CP",
        "ventas": "VT",
        "clientes": "CL",
        "proveedores": "PR",
        "empleados": "EM",
        "gastos": "GS",
        "adelantos_empleados": "AE",
        "perdidas": "PE",
        "ajustes_inventario": "AI",
        "conteo_inventario": "CI",
        "cuentas_por_cobrar": "CC",
        "caja": "CJ",
        "movimientos_caja": "MC",
        "cotizaciones": "CT",
        "bancos": "BN"
    }
    prefijo = PREFIJOS.get(nombre_tabla)
    if not prefijo:
        return df

    if "Código" in df.columns:
        return df

    sort_cols = []
    for c in ["fecha", "created_at", "fecha_apertura", "id", "identificación"]:
        if c in df.columns:
            sort_cols.append(c)
            
    indices = {}
    if sort_cols:
        try:
            df_sorted = df.sort_values(by=sort_cols, ascending=True)
            col_id = "id" if "id" in df.columns else "identificación"
            for idx, row_id in enumerate(df_sorted[col_id].tolist()):
                indices[str(row_id)] = idx + 1
        except Exception:
            pass

    codigos = []
    col_id = "id" if "id" in df.columns else "identificación" if "identificación" in df.columns else None
    
    for _, row in df.iterrows():
        row_id = str(row.get(col_id)) if col_id and row.get(col_id) is not None else ""
        
        codigo_existente = None
        if nombre_tabla == "productos" and "codigo" in row.index:
            codigo_existente = row.get("codigo")
        elif nombre_tabla == "compras" and "numero" in row.index:
            codigo_existente = row.get("numero")
        elif nombre_tabla == "ventas" and "numero_factura" in row.index:
            codigo_existente = row.get("numero_factura")
            
        if codigo_existente and str(codigo_existente).strip():
            c_str = str(codigo_existente).strip().upper()
            if c_str.startswith(prefijo):
                codigos.append(c_str)
            else:
                codigos.append(f"{prefijo}{c_str}")
        else:
            try:
                if row_id.isdigit():
                    codigos.append(f"{prefijo}{int(row_id):03d}")
                else:
                    idx_num = indices.get(row_id)
                    if idx_num is not None:
                        codigos.append(f"{prefijo}{idx_num:03d}")
                    else:
                        codigos.append(f"{prefijo}000")
            except Exception:
                codigos.append(f"{prefijo}000")
                
    df.insert(0, "Código", codigos)
    return df


def generar_codigo_secuencial(nombre_tabla: str) -> str:
    PREFIJOS = {
        "productos": "PO",
        "compras": "CP",
        "ventas": "VT",
        "clientes": "CL",
        "proveedores": "PR",
        "empleados": "EM",
        "gastos": "GS",
        "adelantos_empleados": "AE",
        "perdidas": "PE",
        "ajustes_inventario": "AI",
        "conteo_inventario": "CI",
        "cuentas_por_cobrar": "CC",
        "caja": "CJ",
        "movimientos_caja": "MC",
        "cotizaciones": "CT",
        "bancos": "BN"
    }
    prefijo = PREFIJOS.get(nombre_tabla, "XX")
    
    try:
        from core.db import leer_tabla, DATA
        df = leer_tabla(nombre_tabla)
    except Exception:
        df = DATA.get(nombre_tabla, pd.DataFrame()).copy()

    if df.empty:
        return f"{prefijo}001"

    if nombre_tabla == "productos" and "codigo" in df.columns:
        max_num = 0
        for val in df["codigo"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("PO"):
                num_part = txt.replace("PO", "")
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"PO{(max_num + 1):03d}"

    if nombre_tabla == "compras" and "numero" in df.columns:
        max_num = 0
        for val in df["numero"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("CP"):
                num_part = txt.replace("CP", "")
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"CP{(max_num + 1):03d}"

    if nombre_tabla == "ventas" and "numero_factura" in df.columns:
        max_num = 0
        for val in df["numero_factura"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("VT"):
                num_part = txt.replace("VT", "")
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"VT{(max_num + 1):03d}"

    col_id = "id" if "id" in df.columns else "identificación" if "identificación" in df.columns else None
    if col_id:
        ids = df[col_id].dropna().tolist()
        numeric_ids = []
        for x in ids:
            try:
                numeric_ids.append(int(x))
            except Exception:
                pass
        if numeric_ids:
            return f"{prefijo}{(max(numeric_ids) + 1):03d}"
        
    return f"{prefijo}{(len(df) + 1):03d}"


def generar_codigo_producto() -> str:
    return generar_codigo_secuencial("productos")

