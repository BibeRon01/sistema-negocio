import base64
import io
import unicodedata
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd
import streamlit as st
from supabase import Client, create_client

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
st.set_page_config(page_title="Sistema de Negocio PRO", layout="wide")

st.markdown("""
<style>
:root {
    --azul-claro:#e8f7ff;
    --azul:#bde8ff;
    --azul-fuerte:#66c7ff;
    --rojo:#d94c64;
    --rojo-claro:#ffe5ea;
    --texto:#17384d;
}
html, body, [class*="css"] { color: var(--texto); }
.block-container { padding-top: .9rem; }
h1, h2, h3 { color:#154664; }
.stButton>button { border-radius: 10px; }
.pos-card {
    background: linear-gradient(180deg,var(--azul-claro),white);
    border: 1px solid #d4edf9;
    border-radius: 18px;
    padding: 14px;
    box-shadow: 0 5px 15px rgba(20,50,70,.08);
    min-height: 170px;
}
.soft-box {
    background:#f9fdff; border:1px solid #d8eef8; border-radius:16px; padding:14px;
}
.red-box {
    background:#fff5f7; border:1px solid #ffd6de; border-radius:16px; padding:14px;
}
div[data-testid="stMetric"] {
    background:white; border:1px solid #e6f1f8; border-radius:12px; padding:10px;
    box-shadow:0 2px 8px rgba(0,0,0,.04);
}
</style>
""", unsafe_allow_html=True)


# =========================================================
# SECRETS / CONEXIÓN
# =========================================================
def obtener_secreto(nombre: str, default: str = "") -> str:
    try:
        return st.secrets.get(nombre, default)
    except Exception:
        return default


SUPABASE_URL = obtener_secreto("SUPABASE_URL", "")
SUPABASE_KEY = obtener_secreto("SUPABASE_KEY", "")
APP_PASSWORD = obtener_secreto("APP_PASSWORD", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Faltan SUPABASE_URL y/o SUPABASE_KEY en .streamlit/secrets.toml")
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as exc:
    st.error(f"No se pudo conectar con Supabase: {exc}")
    st.stop()




# =========================================================
# UTILIDADES BÁSICAS TEMPRANAS (PARA LOGIN)
# =========================================================
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


# =========================================================
# LOGIN POR USUARIO / CONTRASEÑA
# =========================================================
def usuario_sesion() -> dict:
    return st.session_state.get("usuario_data", {}) or {}



def nombre_usuario_actual() -> str:
    user = usuario_sesion()
    return str(user.get("usuario") or user.get("nombre") or "sistema")



def es_admin() -> bool:
    return normalizar_texto(usuario_sesion().get("rol", "")) == "admin"



def tiene_permiso(flag: str) -> bool:
    user = usuario_sesion()
    if not user:
        return False
    if es_admin():
        return True
    return bool(user.get(flag, False))



def cerrar_sesion():
    st.session_state.pop("usuario_data", None)
    st.rerun()



def login_simple() -> bool:
    if st.session_state.get("usuario_data"):
        return True

    st.title("🔐 Acceso al sistema")
    st.caption("Entra con tu usuario y clave del sistema.")
    usuario_in = st.text_input("Usuario", key="login_usuario")
    clave_in = st.text_input("Clave", type="password", key="login_clave")

    if st.button("Entrar", key="btn_login_usuario"):
        encontrado = None
        error_login = None
        try:
            resp = supabase.table("usuarios").select("*").execute()
            filas = resp.data or []
            usuario_n = normalizar_texto(usuario_in)
            for fila in filas:
                fila_usuario = normalizar_texto(fila.get("usuario") or fila.get("email") or "")
                fila_clave = str(fila.get("clave") or fila.get("password") or "")
                activo = bool(fila.get("activo", True))
                if activo and fila_usuario == usuario_n and fila_clave == str(clave_in):
                    encontrado = fila
                    break
        except Exception as exc:
            error_login = exc

        if encontrado is not None:
            st.session_state["usuario_data"] = encontrado
            st.rerun()

        if APP_PASSWORD and usuario_in == "admin" and clave_in == APP_PASSWORD:
            st.session_state["usuario_data"] = {
                "usuario": "admin",
                "nombre": "Administrador",
                "rol": "admin",
                "puede_vender": True,
                "puede_editar_ventas": True,
                "puede_eliminar": True,
                "puede_anular": True,
                "puede_ver_reportes": True,
                "puede_registrar_compras": True,
                "puede_registrar_gastos": True,
                "puede_configurar": True,
                "activo": True,
            }
            st.rerun()

        if error_login is not None:
            st.error(f"No se pudo validar el usuario: {error_login}")
        else:
            st.error("Usuario o clave incorrectos.")

    return False


if not login_simple():
    st.stop()


# =========================================================
# UTILIDADES
# =========================================================
def ahora_str() -> str:
    return date.today().isoformat()



def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    columnas = []
    for c in df.columns:
        c2 = normalizar_texto(c).replace(" ", "_")
        columnas.append(c2)
    df.columns = columnas
    df = df.loc[:, ~df.columns.str.contains("^unnamed", case=False)]
    return df



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
    if isinstance(valor, pd.Timestamp):
        return valor.date().isoformat()
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()

    txt = str(valor).strip()
    formatos = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(txt, fmt).date().isoformat()
        except Exception:
            pass

    try:
        fecha = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        if pd.isna(fecha):
            return None
        return fecha.date().isoformat()
    except Exception:
        return None





def mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    mapa = {
        "nombre": ["producto", "nombre", "item", "descripcion", "descripción"],
        "codigo": ["codigo", "código", "codigo_barra", "barcode", "sku", "referencia"],
        "costo": ["costo", "cost", "precio_compra", "precio compra"],
        "precio": ["precio", "venta", "precio_venta", "precio venta"],
        "cantidad": ["cantidad", "stock", "existencia", "existencia_sistema"],
        "fecha": ["fecha", "date"],
        "proveedor": ["proveedor", "suplidor"],
        "descripcion": ["descripcion", "descripción", "detalle"],
        "numero": ["numero", "número", "factura", "documento"],
        "metodo": ["metodo", "método", "metodo_pago", "forma_pago"],
    }
    ren = {}
    for col in df.columns:
        norm = normalizar_texto(col)
        for destino, aliases in mapa.items():
            if norm in [normalizar_texto(a) for a in aliases]:
                ren[col] = destino
                break
    return df.rename(columns=ren)



def get_producto_por_codigo(codigo: str):
    codigo_n = normalizar_texto(codigo)
    if not codigo_n:
        return None
    df = leer_tabla("productos")
    if df.empty or "codigo" not in df.columns:
        return None
    tmp = df.copy()
    tmp["_c"] = tmp["codigo"].astype(str).apply(normalizar_texto)
    match = tmp[tmp["_c"] == codigo_n]
    if match.empty:
        return None
    return match.iloc[0]



def obtener_configuracion() -> dict:
    try:
        resp = supabase.table("configuracion_sistema").select("*").limit(1).execute()
        filas = resp.data or []
        return filas[0] if filas else {}
    except Exception:
        return {}



def logo_actual() -> str:
    cfg = obtener_configuracion()
    return str(cfg.get("logo_url") or "")



def construir_data_uri(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"



def guardar_logo_en_configuracion(file_bytes: bytes, mime: str) -> bool:
    cfg = obtener_configuracion()
    if not cfg:
        return False
    uri = construir_data_uri(file_bytes, mime)
    try:
        supabase.table("configuracion_sistema").update({"logo_url": uri}).eq("id", cfg["id"]).execute()
        registrar_auditoria("actualizar_logo", "configuracion_sistema", "Logo actualizado")
        return True
    except Exception as exc:
        st.error(f"No se pudo guardar el logo: {exc}")
        return False



def obtener_nombre_producto(row: pd.Series) -> str:
    return limpiar_texto(row.get("nombre") or row.get("producto"))



def producto_tiene_inventario(row: pd.Series) -> bool:
    return bool(row.get("usa_inventario", True))



def obtener_existencia_producto(row: pd.Series) -> float:
    producto_id = row.get("id") or row.get("producto_id")
    producto_nombre = obtener_nombre_producto(row)
    invent = leer_tabla("inventario_actual")
    if not invent.empty:
        if producto_id is not None and "producto_id" in invent.columns:
            m = invent[invent["producto_id"].astype(str) == str(producto_id)]
            if not m.empty:
                return float(limpiar_numero(m.iloc[0].get("cantidad")) or limpiar_numero(m.iloc[0].get("existencia_sistema")) or 0)
        if producto_nombre and "producto" in invent.columns:
            tmp = invent.copy()
            tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
            m = tmp[tmp["_n"] == normalizar_texto(producto_nombre)]
            if not m.empty:
                return float(limpiar_numero(m.iloc[0].get("cantidad")) or limpiar_numero(m.iloc[0].get("existencia_sistema")) or 0)
    return limpiar_numero(row.get("cantidad")) or limpiar_numero(row.get("stock")) or 0.0



def actualizar_existencia_producto(producto_row: pd.Series, nueva_cantidad: float) -> bool:
    payload = {"cantidad": float(nueva_cantidad)}
    if "stock" in producto_row.index:
        payload["stock"] = float(nueva_cantidad)
    ok = actualizar("productos", producto_row["id"], payload)
    try:
        upsert_inventario_actual(obtener_nombre_producto(producto_row), float(limpiar_numero(producto_row.get("costo")) or 0), float(limpiar_numero(producto_row.get("precio")) or 0), float(nueva_cantidad), ahora_str(), "Sync desde producto")
    except Exception:
        pass
    return ok



def registrar_movimiento_inventario(producto_id, producto, tipo_movimiento, referencia_tabla, referencia_id, cantidad, costo_unitario, observacion=""):
    datos = {
        "producto_id": producto_id,
        "producto": producto,
        "tipo_movimiento": tipo_movimiento,
        "referencia_tabla": referencia_tabla,
        "referencia_id": str(referencia_id) if referencia_id is not None else None,
        "cantidad": float(cantidad),
        "costo_unitario": float(costo_unitario or 0),
        "observacion": observacion,
        "usuario": nombre_usuario_actual(),
    }
    try:
        supabase.table("movimientos").insert(datos).execute()
    except Exception:
        pass



def registrar_compra_producto(producto_row: pd.Series, cantidad: float, costo_unitario: float, fecha_compra: str, proveedor: str = "", numero: str = "", descripcion: str = "", metodo: str = "") -> bool:
    producto_id = producto_row["id"]
    producto_nombre = obtener_nombre_producto(producto_row)
    total = float(cantidad) * float(costo_unitario)
    try:
        resp = supabase.table("compras").insert({
            "fecha": fecha_compra,
            "numero": numero,
            "proveedor": proveedor,
            "descripcion": descripcion or f"Compra de {producto_nombre}",
            "monto": total,
            "metodo": metodo,
            "producto_id": str(producto_id),
            "producto": producto_nombre,
            "cantidad": float(cantidad),
            "costo_unitario": float(costo_unitario),
            "total": total,
            "usuario": nombre_usuario_actual(),
        }).execute()
        compra_id = (resp.data or [{}])[0].get("id") if hasattr(resp, "data") else None
        nueva_existencia = obtener_existencia_producto(producto_row) + float(cantidad)
        payload = {"costo": float(costo_unitario), "cantidad": float(nueva_existencia)}
        if "stock" in producto_row.index:
            payload["stock"] = float(nueva_existencia)
        if "costo_promedio" in producto_row.index:
            payload["costo_promedio"] = float(costo_unitario)
        supabase.table("productos").update(payload).eq("id", producto_id).execute()
        try:
            supabase.table("inventario_lotes").insert({
                "producto_id": str(producto_id),
                "producto": producto_nombre,
                "compra_id": str(compra_id) if compra_id else None,
                "cantidad_inicial": float(cantidad),
                "cantidad_restante": float(cantidad),
                "costo_unitario": float(costo_unitario),
                "fecha_compra": fecha_compra,
                "activo": True,
            }).execute()
        except Exception:
            pass
        registrar_movimiento_inventario(producto_id, producto_nombre, "entrada_compra", "compras", compra_id, cantidad, costo_unitario, descripcion)
        registrar_auditoria("compra_producto", "compras", f"producto={producto_nombre} cantidad={cantidad} costo={costo_unitario}")
        return True
    except Exception as exc:
        st.error(f"No se pudo registrar la compra: {exc}")
        return False



def obtener_costo_fifo(producto_row: pd.Series, cantidad: float) -> tuple[float, list[dict]]:
    producto_id = str(producto_row["id"])
    producto_nombre = obtener_nombre_producto(producto_row)
    lotes = leer_tabla("inventario_lotes")
    movimientos = []
    if lotes.empty:
        costo = limpiar_numero(producto_row.get("costo")) or 0.0
        return costo, movimientos
    tmp = lotes.copy()
    if "producto_id" in tmp.columns:
        tmp = tmp[tmp["producto_id"].astype(str) == producto_id]
    if "cantidad_restante" in tmp.columns:
        tmp = tmp[pd.to_numeric(tmp["cantidad_restante"], errors="coerce").fillna(0) > 0]
    if "fecha_compra" in tmp.columns:
        tmp["fecha_compra"] = pd.to_datetime(tmp["fecha_compra"], errors="coerce")
        tmp = tmp.sort_values(["fecha_compra", "fecha"], na_position="last")
    restante = float(cantidad)
    costo_total = 0.0
    for _, lote in tmp.iterrows():
        if restante <= 0:
            break
        disponible = limpiar_numero(lote.get("cantidad_restante")) or 0
        if disponible <= 0:
            continue
        tomar = min(disponible, restante)
        costo = limpiar_numero(lote.get("costo_unitario")) or 0
        costo_total += tomar * costo
        movimientos.append({"lote_id": lote["id"], "tomar": tomar, "costo": costo, "restante_final": disponible - tomar})
        restante -= tomar
    if cantidad <= 0:
        return 0.0, movimientos
    if costo_total <= 0:
        costo_total = (limpiar_numero(producto_row.get("costo")) or 0.0) * float(cantidad)
    return costo_total / float(cantidad), movimientos



def aplicar_consumo_fifo(movimientos: list[dict]):
    for mov in movimientos:
        payload = {
            "cantidad_restante": float(mov["restante_final"]),
            "activo": float(mov["restante_final"]) > 0,
        }
        try:
            supabase.table("inventario_lotes").update(payload).eq("id", mov["lote_id"]).execute()
        except Exception:
            pass

def leer_archivo_subido(archivo) -> pd.DataFrame:
    try:
        nombre = archivo.name.lower()
        if nombre.endswith(".csv"):
            try:
                df = pd.read_csv(archivo)
            except Exception:
                archivo.seek(0)
                df = pd.read_csv(archivo, encoding="latin-1")
        else:
            df = pd.read_excel(archivo)
        df = normalizar_columnas(df)
        df = mapear_columnas(df)
        return df
    except Exception as exc:
        st.error(f"No se pudo leer el archivo: {exc}")
        return pd.DataFrame()



def filtrar_por_fechas(df: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns:
        return df.copy()
    out = df.copy()
    out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
    desde_dt = pd.to_datetime(desde)
    hasta_dt = pd.to_datetime(hasta)
    return out[(out["fecha"] >= desde_dt) & (out["fecha"] <= hasta_dt)]



def buscar_df(df: pd.DataFrame, texto: str) -> pd.DataFrame:
    if df.empty or not texto:
        return df
    mask = df.astype(str).apply(lambda col: col.str.contains(texto, case=False, na=False)).any(axis=1)
    return df[mask]



def suma_col(df: pd.DataFrame, columna: str) -> float:
    if df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())



def agrupar_mensual(df: pd.DataFrame, columna_valor: str) -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns or columna_valor not in df.columns:
        return pd.DataFrame(columns=["mes", "valor"])
    temp = df.copy()
    temp["fecha"] = pd.to_datetime(temp["fecha"], errors="coerce")
    temp[columna_valor] = pd.to_numeric(temp[columna_valor], errors="coerce").fillna(0)
    temp = temp.dropna(subset=["fecha"])
    if temp.empty:
        return pd.DataFrame(columns=["mes", "valor"])
    temp["mes"] = temp["fecha"].dt.to_period("M").astype(str)
    out = temp.groupby("mes", as_index=False)[columna_valor].sum()
    out.columns = ["mes", "valor"]
    return out



def rango_fechas_ui(key_base: str):
    c1, c2 = st.columns(2)
    with c1:
        desde = st.date_input("Desde", value=date.today().replace(day=1), key=f"{key_base}_desde")
    with c2:
        hasta = st.date_input("Hasta", value=date.today(), key=f"{key_base}_hasta")
    return desde, hasta



def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="datos")
    buffer.seek(0)
    return buffer.getvalue()



def descargar_archivos(df: pd.DataFrame, base_name: str):
    if df.empty:
        st.info("No hay datos para descargar.")
        return

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    xlsx_bytes = df_to_excel_bytes(df)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Descargar CSV",
            data=csv_bytes,
            file_name=f"{base_name}.csv",
            mime="text/csv",
            key=f"dl_csv_{base_name}",
        )
    with c2:
        st.download_button(
            "⬇️ Descargar Excel",
            data=xlsx_bytes,
            file_name=f"{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_xlsx_{base_name}",
        )


# =========================================================
# SUPABASE CRUD
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



def leer_tabla(nombre_tabla: str, order_by: str = "id") -> pd.DataFrame:
    try:
        resp = supabase.table(nombre_tabla).select("*").order(order_by).execute()
        data = resp.data if resp.data else []
        return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()



def insertar(nombre_tabla: str, datos: dict, usuario: str | None = None) -> bool:
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        registrar_auditoria("insertar", nombre_tabla, f"usuario={usuario or nombre_usuario_actual()} | {str(datos)[:500]}")
        return True
    except Exception as exc:
        st.error(f"Error al insertar en {nombre_tabla}: {exc}")
        return False



def actualizar(nombre_tabla: str, fila_id: Any, datos: dict, usuario: str | None = None) -> bool:
    try:
        supabase.table(nombre_tabla).update(datos).eq("id", fila_id).execute()
        registrar_auditoria("actualizar", nombre_tabla, f"usuario={usuario or nombre_usuario_actual()} | id={fila_id} | {str(datos)[:500]}")
        return True
    except Exception as exc:
        st.error(f"Error al actualizar en {nombre_tabla}: {exc}")
        return False



def eliminar(nombre_tabla: str, fila_id: Any, usuario: str | None = None) -> bool:
    try:
        supabase.table(nombre_tabla).delete().eq("id", fila_id).execute()
        registrar_auditoria("eliminar", nombre_tabla, f"usuario={usuario or nombre_usuario_actual()} | id={fila_id}")
        return True
    except Exception as exc:
        st.error(f"Error al eliminar en {nombre_tabla}: {exc}")
        return False



def anular(nombre_tabla: str, fila_id: Any, motivo: str = "", usuario: str | None = None) -> bool:
    try:
        supabase.table(nombre_tabla).update({"anulado": True, "motivo_anulacion": motivo}).eq("id", fila_id).execute()
        registrar_auditoria("anular", nombre_tabla, f"usuario={usuario or nombre_usuario_actual()} | id={fila_id} motivo={motivo}")
        return True
    except Exception as exc:
        st.error(f"Error al anular en {nombre_tabla}: {exc}")
        return False

# =========================================================
# CARGA GLOBAL
# =========================================================
def cargar_datos() -> dict[str, pd.DataFrame]:
    tablas = [
        "productos",
        "ventas",
        "compras",
        "gastos",
        "catalogo_gastos",
        "empleados",
        "adelantos_empleados",
        "perdidas",
        "inventario_actual",
        "conteo_inventario",
        "ajustes_inventario",
        "gastos_dueno",
        "cierre_caja",
        "estado_resultados",
        "auditoria",
        "usuarios",
        "clientes",
        "proveedores",
        "detalle_venta",
        "ventas_pagos",
        "cuentas_por_cobrar",
        "abonos_credito",
        "inventario_lotes",
        "movimientos",
        "movimientos_caja",
        "configuracion_sistema",
    ]

    data: dict[str, pd.DataFrame] = {}
    for tabla in tablas:
        df = leer_tabla(tabla)
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        data[tabla] = df
    return data


DATA = cargar_datos()


# =========================================================
# HELPERS DE NEGOCIO
# =========================================================
def get_producto_por_nombre(nombre: str):
    df = leer_tabla("productos")
    if df.empty or "nombre" not in df.columns:
        return None
    nombre_n = normalizar_texto(nombre)
    tmp = df.copy()
    tmp["_n"] = tmp["nombre"].astype(str).apply(normalizar_texto)
    match = tmp[tmp["_n"] == nombre_n]
    if match.empty:
        return None
    return match.iloc[0]



def actualizar_stock_producto(nombre: str, nueva_cantidad: float, fecha_mov=None):
    fila = get_producto_por_nombre(nombre)
    if fila is None:
        return False
    payload = {"cantidad": float(nueva_cantidad)}
    if fecha_mov is not None:
        payload["fecha"] = str(fecha_mov)
    return actualizar("productos", fila["id"], payload)



def upsert_inventario_actual(producto: str, costo: float, precio: float, existencia: float, fecha_mov, observacion: str = "") -> bool:
    invent = DATA["inventario_actual"]
    producto_n = normalizar_texto(producto)
    if not invent.empty and "producto" in invent.columns:
        tmp = invent.copy()
        tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
        match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            fila_id = match.iloc[0]["id"]
            return actualizar(
                "inventario_actual",
                fila_id,
                {
                    "fecha": str(fecha_mov),
                    "producto": limpiar_texto(producto),
                    "costo": float(costo),
                    "precio": float(precio),
                    "existencia_sistema": float(existencia),
                    "observacion": observacion,
                },
            )

    return insertar(
        "inventario_actual",
        {
            "fecha": str(fecha_mov),
            "producto": limpiar_texto(producto),
            "costo": float(costo),
            "precio": float(precio),
            "existencia_sistema": float(existencia),
            "observacion": observacion,
        },
    )



def registrar_perdida(fecha_mov, producto, cantidad, costo_unitario, tipo_perdida, observacion="") -> bool:
    cantidad = float(cantidad)
    costo_unitario = float(costo_unitario)
    valor = cantidad * costo_unitario
    return insertar(
        "perdidas",
        {
            "fecha": str(fecha_mov),
            "producto": limpiar_texto(producto),
            "cantidad": cantidad,
            "costo_unitario": costo_unitario,
            "valor": valor,
            "tipo_perdida": tipo_perdida,
            "observacion": observacion,
        },
    )



def obtener_empleados_fijos_periodo(empleados_df: pd.DataFrame, desde, hasta) -> float:
    if empleados_df.empty:
        return 0.0

    total = 0.0
    meses = pd.period_range(pd.to_datetime(desde), pd.to_datetime(hasta), freq="M")

    for _, row in empleados_df.iterrows():
        activo = str(row.get("activo", True)).lower() not in ["false", "0", "no"]
        if not activo:
            continue

        tipo_salario = normalizar_texto(row.get("tipo_salario", "fijo"))
        if tipo_salario != "fijo":
            continue

        sueldo = limpiar_numero(row.get("sueldo")) or 0
        frecuencia = normalizar_texto(row.get("frecuencia_pago", "mensual"))

        for _ in meses:
            if frecuencia == "quincenal":
                total += sueldo * 2
            elif frecuencia == "semanal":
                total += sueldo * 4
            else:
                total += sueldo

    adelantos = DATA["adelantos_empleados"]
    adel_f = filtrar_por_fechas(adelantos, desde, hasta)
    total_adelantos = suma_col(adel_f, "monto")
    return float(max(total - total_adelantos, 0))



def obtener_empleados_variables_periodo(gastos_df: pd.DataFrame, desde, hasta) -> float:
    if gastos_df.empty or "categoria" not in gastos_df.columns:
        return 0.0
    temp = filtrar_por_fechas(gastos_df, desde, hasta).copy()
    if temp.empty:
        return 0.0
    temp["categoria"] = temp["categoria"].astype(str).apply(normalizar_texto)
    temp = temp[temp["categoria"] == "nomina variable"]
    return suma_col(temp, "monto")



def obtener_gastos_fijos_variables(gastos_df: pd.DataFrame, desde, hasta):
    temp = filtrar_por_fechas(gastos_df, desde, hasta).copy()
    if temp.empty or "tipo" not in temp.columns:
        return 0.0, 0.0
    temp["tipo"] = temp["tipo"].astype(str).apply(normalizar_texto)
    fijos = suma_col(temp[temp["tipo"] == "fijo"], "monto")
    variables = suma_col(temp[temp["tipo"] == "variable"], "monto")
    return fijos, variables



def analisis_negocio(ventas, compras, gastos_fijos, gastos_variables, empleados_fijos, empleados_variables, perdidas, utilidad_neta):
    mensajes: list[str] = []

    if utilidad_neta > 0:
        mensajes.append("🟢 El negocio está dejando utilidad neta positiva.")
    elif utilidad_neta == 0:
        mensajes.append("🟡 El negocio quedó en equilibrio, sin ganancia neta.")
    else:
        mensajes.append("🔴 El negocio está quedando con pérdida neta.")

    if ventas > 0:
        porcentaje_perdidas = (perdidas / ventas) * 100
        if porcentaje_perdidas >= 8:
            mensajes.append(f"🔴 Las pérdidas representan {porcentaje_perdidas:.2f}% de las ventas. Está alto.")
        elif porcentaje_perdidas >= 3:
            mensajes.append(f"🟡 Las pérdidas representan {porcentaje_perdidas:.2f}% de las ventas.")
        else:
            mensajes.append(f"🟢 Las pérdidas representan {porcentaje_perdidas:.2f}% de las ventas.")
    else:
        mensajes.append("⚪ No hay ventas en el período seleccionado.")

    gasto_total = gastos_fijos + gastos_variables + empleados_fijos + empleados_variables
    if ventas > 0 and (gasto_total / ventas) > 0.7:
        mensajes.append("🟡 Tus gastos están consumiendo más del 70% de las ventas.")

    if compras > ventas and ventas > 0:
        mensajes.append("🟡 Las compras superan las ventas en el período. Revísalo.")

    return mensajes



def guardar_snapshot_estado_resultados(
    fecha,
    desde,
    hasta,
    ventas,
    compras,
    costo_ventas,
    utilidad_bruta,
    gastos_fijos,
    gastos_variables,
    empleados_fijos,
    empleados_variables,
    perdidas,
    retiros_dueno,
    utilidad_neta,
):
    return insertar(
        "estado_resultados",
        {
            "fecha": str(fecha),
            "desde": str(desde),
            "hasta": str(hasta),
            "ventas": float(ventas),
            "compras": float(compras),
            "costo_ventas": float(costo_ventas),
            "utilidad_bruta": float(utilidad_bruta),
            "gastos_fijos": float(gastos_fijos),
            "gastos_variables": float(gastos_variables),
            "empleados_fijos": float(empleados_fijos),
            "empleados_variables": float(empleados_variables),
            "perdidas": float(perdidas),
            "retiros_dueno": float(retiros_dueno),
            "utilidad_neta": float(utilidad_neta),
        },
    )



def columnas_disponibles(df: pd.DataFrame, candidatas: Iterable[str]) -> list[str]:
    return [c for c in candidatas if c in df.columns]



def rango_periodo(tipo_periodo: str):
    hoy = date.today()
    if tipo_periodo == "Día":
        return hoy, hoy
    if tipo_periodo == "Mes actual":
        return hoy.replace(day=1), hoy
    if tipo_periodo == "Año actual":
        return date(hoy.year, 1, 1), hoy
    return hoy.replace(day=1), hoy


def resumen_financiero_periodo(desde, hasta, utilidad_bruta_manual: float = 0.0) -> dict[str, float]:
    ventas_df = filtrar_por_fechas(DATA["ventas"], desde, hasta)
    compras_df = filtrar_por_fechas(DATA["compras"], desde, hasta)
    gastos_df = filtrar_por_fechas(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)
    adelantos_df = filtrar_por_fechas(DATA["adelantos_empleados"], desde, hasta)

    ventas_tot = suma_col(ventas_df, "total")
    compras_tot = suma_col(compras_df, "monto")
    gastos_fijos, gastos_variables = obtener_gastos_fijos_variables(DATA["gastos"], desde, hasta)
    empleados_fijos = obtener_empleados_fijos_periodo(DATA["empleados"], desde, hasta)
    empleados_variables = obtener_empleados_variables_periodo(DATA["gastos"], desde, hasta)
    perdidas_tot = suma_col(perdidas_df, "valor")
    retiros_tot = suma_col(dueno_df, "monto")
    adelantos_tot = suma_col(adelantos_df, "monto")

    utilidad_neta = (
        float(utilidad_bruta_manual)
        - gastos_fijos
        - gastos_variables
        - empleados_fijos
        - empleados_variables
        - perdidas_tot
    )
    return {
        "ventas": ventas_tot,
        "compras": compras_tot,
        "gastos_fijos": gastos_fijos,
        "gastos_variables": gastos_variables,
        "empleados_fijos": empleados_fijos,
        "empleados_variables": empleados_variables,
        "adelantos": adelantos_tot,
        "perdidas": perdidas_tot,
        "retiros_dueno": retiros_tot,
        "utilidad_bruta": float(utilidad_bruta_manual),
        "utilidad_neta": utilidad_neta,
        "dueno_65": utilidad_neta * 0.65,
        "gerente_35": utilidad_neta * 0.35,
    }


def serie_periodica(df: pd.DataFrame, columna: str, frecuencia: str = "M") -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns or columna not in df.columns:
        etiqueta = "periodo"
        return pd.DataFrame(columns=[etiqueta, "valor"])
    temp = df.copy()
    temp["fecha"] = pd.to_datetime(temp["fecha"], errors="coerce")
    temp[columna] = pd.to_numeric(temp[columna], errors="coerce").fillna(0)
    etiqueta = "periodo"
    temp[etiqueta] = temp["fecha"].dt.to_period(frecuencia).astype(str)
    out = temp.groupby(etiqueta, as_index=False)[columna].sum()
    out.columns = [etiqueta, "valor"]
    return out


def guardar_logo_configuracion(archivo_logo) -> tuple[bool, str]:
    try:
        contenido = archivo_logo.read()
        b64 = base64.b64encode(contenido).decode("utf-8")
        cfg = obtener_configuracion()
        if not cfg:
            return False, "No se encontró configuración"
        supabase.table("configuracion_sistema").update({
            "logo_base64": b64,
            "logo_filename": archivo_logo.name,
        }).eq("id", cfg["id"]).execute()
        registrar_auditoria("subir_logo", "configuracion_sistema", archivo_logo.name)
        return True, "Logo guardado"
    except Exception as exc:
        return False, str(exc)


def render_logo_y_encabezado():
    cfg = obtener_configuracion()
    if not cfg:
        return
    c1, c2 = st.columns([1, 4])
    with c1:
        logo_b64 = limpiar_texto(cfg.get("logo_base64"))
        if logo_b64:
            st.image(base64.b64decode(logo_b64), width=120)
    with c2:
        st.markdown(f"## {limpiar_texto(cfg.get('negocio_nombre')) or 'Negocio'}")
        nombre_sistema = limpiar_texto(cfg.get("nombre_sistema"))
        propietario = limpiar_texto(cfg.get("propietario"))
        slogan = limpiar_texto(cfg.get("slogan"))
        if nombre_sistema:
            st.caption(nombre_sistema)
        if propietario:
            st.caption(f"Responsable: {propietario}")
        if slogan:
            st.caption(slogan)


def generar_texto_factura(venta_id, cliente_nombre, carrito, subtotal_real, descuento_global, recargo_visual, total_cobrar, pagos_cliente, recibido_efectivo, cambio):
    lineas = []
    cfg = obtener_configuracion()
    lineas.append(limpiar_texto((cfg or {}).get("negocio_nombre")) or "NEGOCIO")
    lineas.append(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lineas.append(f"Venta: {venta_id}")
    lineas.append(f"Cliente: {cliente_nombre}")
    lineas.append("-" * 40)
    for item in carrito:
        total_linea = float(item["cantidad"]) * float(item["precio_unitario"])
        lineas.append(f"{item['producto']} | {item['cantidad']:,.2f} x {item['precio_unitario']:,.2f} = {total_linea:,.2f}")
    lineas.append("-" * 40)
    lineas.append(f"Subtotal real: RD$ {subtotal_real:,.2f}")
    lineas.append(f"Descuento: RD$ {descuento_global:,.2f}")
    lineas.append(f"Recargo visual: RD$ {recargo_visual:,.2f}")
    lineas.append(f"Total a cobrar: RD$ {total_cobrar:,.2f}")
    lineas.append("Pagos cliente:")
    for metodo, monto in pagos_cliente.items():
        if monto > 0:
            lineas.append(f"- {metodo}: RD$ {monto:,.2f}")
    if recibido_efectivo > 0:
        lineas.append(f"Recibido efectivo: RD$ {recibido_efectivo:,.2f}")
    lineas.append(f"Cambio: RD$ {cambio:,.2f}")
    return "\n".join(lineas)



# =========================================================
# SIDEBAR
# =========================================================
cfg = obtener_configuracion()
logo_cfg = str(cfg.get("logo_url") or "")
if logo_cfg:
    try:
        st.sidebar.image(logo_cfg, use_container_width=True)
    except Exception:
        pass
st.sidebar.title(f"💼 {cfg.get('negocio_nombre') or 'Sistema de Negocio PRO'}")
if cfg.get("nombre_sistema"):
    st.sidebar.caption(str(cfg.get("nombre_sistema")))
st.sidebar.caption(f"Usuario: {nombre_usuario_actual()}")
if st.sidebar.button("🚪 Cerrar sesión"):
    cerrar_sesion()

menu_base = [
    "Dashboard",
    "POS",
    "Productos",
    "Clientes",
    "Proveedores",
    "Inventario Actual",
    "Conteo Inventario",
    "Ajustes Inventario",
    "Ventas",
    "Compras",
    "Catálogo de Gastos",
    "Gastos",
    "Empleados",
    "Adelantos Empleados",
    "Pérdidas",
    "Gastos Dueño",
    "Cierre de Caja",
    "Estado de Resultados",
    "Reportes",
    "Créditos",
    "Usuarios",
    "Configuración",
    "Auditoría",
]

if es_admin() or tiene_permiso("puede_configurar"):
    menu_opciones = menu_base
else:
    rol_actual = normalizar_texto((st.session_state.get("usuario_data") or {}).get("rol", ""))
    if rol_actual == "cajera":
        menu_opciones = ["Apertura de Caja", "POS", "Cierre de Caja", "Reportes"]
    else:
        menu_opciones = ["Dashboard"]
        if tiene_permiso("puede_vender"):
            menu_opciones += ["Apertura de Caja", "POS", "Ventas", "Cierre de Caja", "Reportes"]
        if tiene_permiso("puede_registrar_compras"):
            menu_opciones += ["Compras", "Proveedores", "Productos", "Inventario Actual", "Conteo Inventario", "Ajustes Inventario"]
        if tiene_permiso("puede_registrar_gastos"):
            menu_opciones += ["Gastos", "Catálogo de Gastos", "Gastos Dueño", "Pérdidas"]
        if tiene_permiso("puede_ver_reportes"):
            menu_opciones += ["Reportes", "Estado de Resultados", "Auditoría", "Clientes", "Créditos"]
        if tiene_permiso("puede_configurar"):
            menu_opciones += ["Usuarios", "Edición Total", "Configuración"]
        menu_opciones = list(dict.fromkeys(menu_opciones))

menu = st.sidebar.selectbox("Menú", menu_opciones)

if st.sidebar.button("🔄 Recargar nube"):
    st.rerun()

# =========================================================
# APERTURA DE CAJA
# =========================================================
if menu == "Apertura de Caja":
    st.title("💵 Apertura de Caja")
    render_logo_y_encabezado()
    fecha = st.date_input("Fecha operativa", value=date.today(), key="apertura_fecha")
    fondo = st.number_input("Fondo inicial", min_value=0.0, step=1.0, key="apertura_fondo")
    observacion = st.text_input("Observación", key="apertura_obs")
    aperturas_hoy = DATA.get("movimientos_caja", pd.DataFrame()).copy()
    if not aperturas_hoy.empty and "descripcion" in aperturas_hoy.columns:
        aperturas_hoy = aperturas_hoy[aperturas_hoy["descripcion"].astype(str).str.contains("Apertura de caja", case=False, na=False)]
    if st.button("Registrar apertura", key="btn_apertura_caja"):
        try:
            supabase.table("movimientos_caja").insert({
                "fecha": datetime.now().isoformat(),
                "dia_operativo": str(fecha),
                "tipo_movimiento": "apertura",
                "metodo_pago": "efectivo",
                "monto": float(fondo),
                "descripcion": f"Apertura de caja. {observacion}".strip(),
                "usuario": nombre_usuario_actual(),
                "tipo": "apertura",
                "referencia": "apertura_caja",
            }).execute()
            registrar_auditoria("apertura_caja", "movimientos_caja", f"fondo={fondo}")
            st.success("Apertura registrada")
            st.rerun()
        except Exception as exc:
            st.error(f"No se pudo registrar la apertura: {exc}")
    if not aperturas_hoy.empty:
        st.subheader("Aperturas registradas")
        st.dataframe(aperturas_hoy, use_container_width=True)

# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Dashboard PRO")
    render_logo_y_encabezado()

    desde, hasta = rango_fechas_ui("dash")

    ventas_df = filtrar_por_fechas(DATA["ventas"], desde, hasta)
    compras_df = filtrar_por_fechas(DATA["compras"], desde, hasta)
    gastos_df = filtrar_por_fechas(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)

    ventas_tot = suma_col(ventas_df, "total")
    compras_tot = suma_col(compras_df, "monto")
    gastos_fijos, gastos_variables = obtener_gastos_fijos_variables(DATA["gastos"], desde, hasta)
    empleados_fijos = obtener_empleados_fijos_periodo(DATA["empleados"], desde, hasta)
    empleados_variables = obtener_empleados_variables_periodo(DATA["gastos"], desde, hasta)
    perdidas_tot = suma_col(perdidas_df, "valor")
    retiros_tot = suma_col(dueno_df, "monto")

    utilidad_bruta = st.number_input("Utilidad bruta manual", min_value=0.0, step=1.0, key="dash_utilidad_bruta")
    utilidad_neta = utilidad_bruta - gastos_fijos - gastos_variables - empleados_fijos - empleados_variables - perdidas_tot

    dueno_65 = utilidad_neta * 0.65
    gerente_35 = utilidad_neta * 0.35

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas", f"RD$ {ventas_tot:,.2f}")
    c2.metric("Compras", f"RD$ {compras_tot:,.2f}")
    c3.metric("Pérdidas", f"RD$ {perdidas_tot:,.2f}")

    adelantos_tot = suma_col(filtrar_por_fechas(DATA["adelantos_empleados"], desde, hasta), "monto")
    c4, c5, c6 = st.columns(3)
    c4.metric("Gastos fijos", f"RD$ {gastos_fijos:,.2f}")
    c5.metric("Gastos variables", f"RD$ {gastos_variables:,.2f}")
    c6.metric("Retiros dueño", f"RD$ {retiros_tot:,.2f}")

    c7, c8, c9 = st.columns(3)
    c7.metric("Empleados fijos", f"RD$ {empleados_fijos:,.2f}")
    c8.metric("Empleados variables", f"RD$ {empleados_variables:,.2f}")
    c9.metric("Adelantos", f"RD$ {adelantos_tot:,.2f}")

    c10, c11, c12 = st.columns(3)
    c10.metric("Utilidad neta", f"RD$ {utilidad_neta:,.2f}")
    c11.metric("65% dueño", f"RD$ {dueno_65:,.2f}")
    c12.metric("35% gerente", f"RD$ {gerente_35:,.2f}")

    st.subheader("📈 Gráficos")
    v_mes = agrupar_mensual(ventas_df, "total")
    g_mes = agrupar_mensual(gastos_df, "monto")
    p_mes = agrupar_mensual(perdidas_df, "valor")
    c_mes = agrupar_mensual(compras_df, "monto")

    if not v_mes.empty:
        st.write("Ventas por mes")
        st.line_chart(v_mes.set_index("mes"))

    if not c_mes.empty:
        st.write("Compras por mes")
        st.bar_chart(c_mes.set_index("mes"))

    if not g_mes.empty:
        st.write("Gastos por mes")
        st.bar_chart(g_mes.set_index("mes"))

    if not p_mes.empty:
        st.write("Pérdidas por mes")
        st.line_chart(p_mes.set_index("mes"))

    st.subheader("🧠 Análisis del negocio")
    for mensaje in analisis_negocio(
        ventas_tot,
        compras_tot,
        gastos_fijos,
        gastos_variables,
        empleados_fijos,
        empleados_variables,
        perdidas_tot,
        utilidad_neta,
    ):
        st.write(mensaje)

    st.subheader("🧾 Pérdidas por producto")
    if not perdidas_df.empty and "producto" in perdidas_df.columns:
        cols = columnas_disponibles(perdidas_df, ["cantidad", "valor"])
        rep = perdidas_df.groupby("producto", as_index=False)[cols].sum().sort_values(cols[-1], ascending=False)
        st.dataframe(rep, use_container_width=True)
        descargar_archivos(rep, "perdidas_por_producto")
    else:
        st.info("No hay pérdidas en el rango seleccionado.")


# =========================================================
# PRODUCTOS
# =========================================================

elif menu == "Productos":
    st.title("📦 Productos")
    render_logo_y_encabezado()

    with st.expander("📥 Subir Excel / CSV de productos"):
        st.write("Columnas esperadas: nombre, costo, precio, cantidad. Fecha opcional. Si el producto ya existe, se alimenta y no se duplica.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_productos")
        if archivo is not None and st.button("Cargar productos"):
            df = leer_archivo_subido(archivo)
            df = df.rename(columns={"producto": "nombre"})
            faltan = [c for c in ["nombre"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                procesados = 0
                for _, row in df.iterrows():
                    nombre = limpiar_texto(row.get("nombre"))
                    if not nombre:
                        continue
                    codigo = limpiar_texto(row.get("codigo"))
                    costo = limpiar_numero(row.get("costo")) or 0
                    precio = limpiar_numero(row.get("precio")) or 0
                    cantidad = limpiar_numero(row.get("cantidad")) or 0
                    fecha_row = parsear_fecha(row.get("fecha")) if "fecha" in df.columns else ahora_str()
                    existente = get_producto_por_nombre(nombre)
                    payload = {
                        "fecha": fecha_row,
                        "codigo": codigo,
                        "nombre": nombre,
                        "costo": float(costo),
                        "precio": float(precio),
                        "precio_descuento": limpiar_numero(row.get("precio_descuento")) or 0,
                        "precio_especial": limpiar_numero(row.get("precio_especial")) or 0,
                        "cantidad": float(cantidad),
                        "activo": True,
                    }
                    if existente is not None:
                        actualizar("productos", existente["id"], payload, usuario=nombre_usuario_actual())
                        upsert_inventario_actual(nombre, costo, precio, cantidad, fecha_row, "Producto actualizado desde Excel")
                    else:
                        insertar("productos", payload, usuario=nombre_usuario_actual())
                        upsert_inventario_actual(nombre, costo, precio, cantidad, fecha_row, "Producto creado desde Excel")
                    procesados += 1
                st.success(f"Se procesaron {procesados} productos.")
                st.rerun()

    with st.expander("➕ Agregar producto manual", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="prod_fecha")
            codigo = st.text_input("Código", key="prod_codigo")
            nombre = st.text_input("Nombre", key="prod_nombre")
            categoria = st.text_input("Categoría", key="prod_categoria")
        with c2:
            costo = st.number_input("Costo", min_value=0.0, step=1.0, key="prod_costo")
            precio = st.number_input("Precio normal", min_value=0.0, step=1.0, key="prod_precio")
            precio_descuento = st.number_input("Precio descuento", min_value=0.0, step=1.0, key="prod_precio_desc")
            precio_especial = st.number_input("Precio especial", min_value=0.0, step=1.0, key="prod_precio_esp")
        with c3:
            usa_inventario = st.checkbox("Usa inventario", value=True, key="prod_usa_inv")
            cantidad = st.number_input("Cantidad inicial", min_value=0.0, step=1.0, key="prod_cantidad") if usa_inventario else 0.0
            activo = st.checkbox("Activo", value=True, key="prod_activo")
            observacion = st.text_area("Observación", key="prod_obs")

        if st.button("Guardar producto", key="btn_guardar_producto"):
            if not limpiar_texto(nombre):
                st.error("Debes escribir el nombre del producto.")
            else:
                existente = get_producto_por_nombre(nombre)
                payload = {
                    "fecha": str(fecha),
                    "codigo": limpiar_texto(codigo),
                    "nombre": limpiar_texto(nombre),
                    "categoria": limpiar_texto(categoria),
                    "costo": float(costo),
                    "precio": float(precio),
                    "precio_descuento": float(precio_descuento),
                    "precio_especial": float(precio_especial),
                    "cantidad": float(cantidad) if usa_inventario else 0.0,
                    "activo": activo,
                    "usa_inventario": usa_inventario,
                    "observacion": limpiar_texto(observacion),
                }
                if existente is not None:
                    ok = actualizar("productos", existente["id"], payload, usuario=nombre_usuario_actual())
                    if ok:
                        upsert_inventario_actual(limpiar_texto(nombre), float(costo), float(precio), float(cantidad) if usa_inventario else 0.0, fecha, "Producto actualizado manual")
                        st.success("Producto actualizado.")
                        st.rerun()
                else:
                    ok = insertar("productos", payload, usuario=nombre_usuario_actual())
                    if ok:
                        upsert_inventario_actual(limpiar_texto(nombre), float(costo), float(precio), float(cantidad) if usa_inventario else 0.0, fecha, "Producto creado manual")
                        st.success("Producto creado.")
                        st.rerun()

    st.subheader("📋 Listado")
    df_prod = DATA["productos"].copy()
    if not df_prod.empty:
        txt = st.text_input("Buscar producto", key="buscar_prod")
        df_prod = buscar_df(df_prod, txt)
        st.dataframe(df_prod, use_container_width=True)
        descargar_archivos(df_prod, "productos")

        if es_admin() or tiene_permiso("puede_configurar"):
            with st.expander("✏️ Editar producto por ID", expanded=False):
                opciones = [f"{row['id']} | {row.get('nombre','')}" for _, row in df_prod.iterrows()]
                if opciones:
                    seleccionado = st.selectbox("Producto a editar", opciones, key="prod_edit_sel")
                    prod_id = seleccionado.split(" | ")[0]
                    fila = df_prod[df_prod["id"].astype(str) == str(prod_id)].iloc[0]
                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        e_codigo = st.text_input("Código", value=limpiar_texto(fila.get("codigo")), key="e_prod_codigo")
                        e_nombre = st.text_input("Nombre", value=limpiar_texto(fila.get("nombre")), key="e_prod_nombre")
                        e_categoria = st.text_input("Categoría", value=limpiar_texto(fila.get("categoria")), key="e_prod_cat")
                    with ec2:
                        e_costo = st.number_input("Costo", min_value=0.0, step=1.0, value=float(limpiar_numero(fila.get("costo")) or 0), key="e_prod_costo")
                        e_precio = st.number_input("Precio normal", min_value=0.0, step=1.0, value=float(limpiar_numero(fila.get("precio")) or 0), key="e_prod_precio")
                        e_precio_desc = st.number_input("Precio descuento", min_value=0.0, step=1.0, value=float(limpiar_numero(fila.get("precio_descuento")) or 0), key="e_prod_precio_desc")
                        e_precio_esp = st.number_input("Precio especial", min_value=0.0, step=1.0, value=float(limpiar_numero(fila.get("precio_especial")) or 0), key="e_prod_precio_esp")
                    with ec3:
                        e_usa_inv = st.checkbox("Usa inventario", value=str(fila.get("usa_inventario", True)).lower() not in ["false","0","no"], key="e_prod_usa_inv")
                        e_cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, value=float(limpiar_numero(fila.get("cantidad")) or 0), key="e_prod_cantidad")
                        e_activo = st.checkbox("Activo", value=str(fila.get("activo", True)).lower() not in ["false","0","no"], key="e_prod_activo")
                        e_obs = st.text_area("Observación", value=limpiar_texto(fila.get("observacion")), key="e_prod_obs")
                    if st.button("Guardar edición producto", key="btn_edit_producto"):
                        ok = actualizar("productos", prod_id, {
                            "codigo": e_codigo,
                            "nombre": e_nombre,
                            "categoria": e_categoria,
                            "costo": float(e_costo),
                            "precio": float(e_precio),
                            "precio_descuento": float(e_precio_desc),
                            "precio_especial": float(e_precio_esp),
                            "usa_inventario": e_usa_inv,
                            "cantidad": float(e_cantidad),
                            "activo": e_activo,
                            "observacion": e_obs,
                        }, usuario=nombre_usuario_actual())
                        if ok:
                            st.success("Producto editado.")
                            st.rerun()
    else:
        st.info("No hay productos registrados.")

# =========================================================
# INVENTARIO ACTUAL
# =========================================================
elif menu == "Inventario Actual":
    st.title("📊 Inventario Actual")

    with st.expander("📥 Subir Excel / CSV de inventario actual", expanded=True):
        st.write("Columnas esperadas: nombre o producto, cantidad o existencia_sistema. Costo y precio opcionales.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_inventario")
        fecha_inv = st.date_input("Fecha del inventario", value=date.today(), key="fecha_inv_actual")

        if archivo is not None and st.button("Cargar inventario actual"):
            df = leer_archivo_subido(archivo)
            df = df.rename(columns={"nombre": "producto", "cantidad": "existencia_sistema"})
            faltan = [c for c in ["producto", "existencia_sistema"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                procesados = 0
                for _, row in df.iterrows():
                    producto = limpiar_texto(row["producto"])
                    if not producto:
                        continue
                    existencia = limpiar_numero(row["existencia_sistema"]) or 0
                    fila_prod = get_producto_por_nombre(producto)

                    if fila_prod is not None:
                        costo = limpiar_numero(row["costo"]) if "costo" in df.columns else limpiar_numero(fila_prod.get("costo")) or 0
                        precio = limpiar_numero(row["precio"]) if "precio" in df.columns else limpiar_numero(fila_prod.get("precio")) or 0
                        actualizar(
                            "productos",
                            fila_prod["id"],
                            {
                                "fecha": str(fecha_inv),
                                "cantidad": float(existencia),
                                "costo": float(costo),
                                "precio": float(precio),
                            },
                        )
                        upsert_inventario_actual(producto, costo, precio, existencia, fecha_inv, "Carga inventario actual")
                    else:
                        costo = limpiar_numero(row["costo"]) if "costo" in df.columns else 0
                        precio = limpiar_numero(row["precio"]) if "precio" in df.columns else 0
                        insertar(
                            "productos",
                            {
                                "fecha": str(fecha_inv),
                                "nombre": producto,
                                "costo": float(costo),
                                "precio": float(precio),
                                "cantidad": float(existencia),
                            },
                        )
                        upsert_inventario_actual(producto, costo, precio, existencia, fecha_inv, "Creado desde inventario actual")
                    procesados += 1
                st.success(f"Inventario actualizado: {procesados} productos.")
                st.rerun()

    invent = DATA["inventario_actual"].copy()
    if not invent.empty:
        st.subheader("📋 Inventario guardado")
        d1, d2 = rango_fechas_ui("inventario_actual")
        invent = filtrar_por_fechas(invent, d1, d2)
        txt = st.text_input("Buscar en inventario actual", key="buscar_inv_actual")
        invent = buscar_df(invent, txt)
        st.dataframe(invent, use_container_width=True)
        descargar_archivos(invent, "inventario_actual")
    else:
        st.info("No hay inventario actual registrado.")


# =========================================================
# CONTEO INVENTARIO
# =========================================================
elif menu == "Conteo Inventario":
    st.title("🧮 Conteo de Inventario")

    with st.expander("📥 Subir conteo físico por Excel / CSV", expanded=True):
        st.write("Columnas esperadas: producto o nombre, existencia_fisica o cantidad.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_conteo")
        fecha_conteo = st.date_input("Fecha del conteo", value=date.today(), key="fecha_conteo")

        if archivo is not None and st.button("Procesar conteo"):
            df = leer_archivo_subido(archivo)
            df = df.rename(columns={"nombre": "producto", "cantidad": "existencia_fisica"})
            faltan = [c for c in ["producto", "existencia_fisica"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                procesados = 0
                for _, row in df.iterrows():
                    producto = limpiar_texto(row["producto"])
                    if not producto:
                        continue
                    fila_prod = get_producto_por_nombre(producto)
                    existencia_sistema = float(limpiar_numero(fila_prod.get("cantidad")) or 0) if fila_prod is not None else 0.0
                    existencia_fisica = float(limpiar_numero(row["existencia_fisica"]) or 0)
                    diferencia = existencia_fisica - existencia_sistema

                    if diferencia == 0:
                        estado = "cuadrado"
                    elif diferencia < 0:
                        estado = "faltante"
                    else:
                        estado = "sobrante"

                    insertar(
                        "conteo_inventario",
                        {
                            "fecha": str(fecha_conteo),
                            "producto": producto,
                            "existencia_sistema": existencia_sistema,
                            "existencia_fisica": existencia_fisica,
                            "diferencia": diferencia,
                            "estado": estado,
                            "observacion": "",
                        },
                    )
                    procesados += 1
                st.success(f"Se procesaron {procesados} filas de conteo.")
                st.rerun()

    conteo = DATA["conteo_inventario"].copy()
    if not conteo.empty:
        st.subheader("📋 Conteos guardados")
        d1, d2 = rango_fechas_ui("conteo_inv")
        conteo_f = filtrar_por_fechas(conteo, d1, d2)
        estado_filtro = st.selectbox("Filtrar por estado", ["Todos", "cuadrado", "faltante", "sobrante"], key="filtro_estado_conteo")
        if estado_filtro != "Todos" and "estado" in conteo_f.columns:
            conteo_f = conteo_f[conteo_f["estado"].astype(str).str.lower() == estado_filtro]

        st.dataframe(conteo_f, use_container_width=True)
        descargar_archivos(conteo_f, "conteo_inventario")

        st.subheader("⚙️ Procesar faltantes y sobrantes")
        pendientes = conteo_f[conteo_f["estado"].astype(str).str.lower().isin(["faltante", "sobrante"])] if not conteo_f.empty else pd.DataFrame()
        if not pendientes.empty:
            opciones = pendientes.apply(
                lambda r: f"{r['producto']} | sistema: {r['existencia_sistema']} | físico: {r['existencia_fisica']} | estado: {r['estado']}",
                axis=1,
            ).tolist()
            sel = st.selectbox("Selecciona una fila", opciones, key="conteo_sel")
            fila = pendientes.iloc[opciones.index(sel)]

            producto = fila["producto"]
            existencia_sistema = float(fila["existencia_sistema"])
            existencia_fisica = float(fila["existencia_fisica"])
            diferencia = float(fila["diferencia"])
            fecha_mov = pd.to_datetime(fila["fecha"]).date()

            fila_prod = get_producto_por_nombre(producto)
            costo = float(limpiar_numero(fila_prod.get("costo")) or 0) if fila_prod is not None else 0.0
            precio = float(limpiar_numero(fila_prod.get("precio")) or 0) if fila_prod is not None else 0.0

            col1, col2, col3 = st.columns(3)
            with col1:
                if diferencia < 0 and st.button("Enviar este faltante a pérdidas"):
                    cant_perdida = abs(diferencia)
                    ok1 = registrar_perdida(
                        fecha_mov,
                        producto,
                        cant_perdida,
                        costo,
                        "mercancia",
                        f"Generado desde conteo. Sistema: {existencia_sistema}, físico: {existencia_fisica}",
                    )
                    ok2 = actualizar_stock_producto(producto, existencia_fisica, fecha_mov)
                    ok3 = upsert_inventario_actual(producto, costo, precio, existencia_fisica, fecha_mov, "Ajustado por conteo a pérdida")
                    if ok1 and ok2 and ok3:
                        st.success("Faltante enviado a pérdidas y stock ajustado.")
                        st.rerun()

            with col2:
                if diferencia > 0 and st.button("Aplicar ajuste positivo"):
                    ok2 = actualizar_stock_producto(producto, existencia_fisica, fecha_mov)
                    ok3 = upsert_inventario_actual(producto, costo, precio, existencia_fisica, fecha_mov, "Ajuste positivo por conteo")
                    if ok2 and ok3:
                        st.success("Ajuste positivo aplicado.")
                        st.rerun()

            with col3:
                if st.button("Marcar pendiente / dejar como está"):
                    st.info("No se hizo cambio en inventario. Queda el registro para revisión.")

            faltantes_df = pendientes[pendientes["estado"].astype(str).str.lower() == "faltante"]
            if not faltantes_df.empty and st.button("Enviar TODOS los faltantes del filtro a pérdidas"):
                count = 0
                for _, r in faltantes_df.iterrows():
                    prod = r["producto"]
                    fis = float(r["existencia_fisica"])
                    sist = float(r["existencia_sistema"])
                    dif = abs(float(r["diferencia"]))
                    ff = pd.to_datetime(r["fecha"]).date()
                    p = get_producto_por_nombre(prod)
                    c = float(limpiar_numero(p.get("costo")) or 0) if p is not None else 0.0
                    pr = float(limpiar_numero(p.get("precio")) or 0) if p is not None else 0.0
                    registrar_perdida(ff, prod, dif, c, "mercancia", f"Generado masivamente desde conteo. Sistema: {sist}, físico: {fis}")
                    actualizar_stock_producto(prod, fis, ff)
                    upsert_inventario_actual(prod, c, pr, fis, ff, "Ajustado por envío masivo a pérdidas")
                    count += 1
                st.success(f"Se enviaron {count} faltantes a pérdidas.")
                st.rerun()
        else:
            st.info("No hay faltantes ni sobrantes en el filtro seleccionado.")
    else:
        st.info("No hay conteos registrados.")


# =========================================================
# AJUSTES INVENTARIO
# =========================================================
elif menu == "Ajustes Inventario":
    st.title("🔄 Ajustes de Inventario")

    productos_lista = DATA["productos"]["nombre"].astype(str).tolist() if not DATA["productos"].empty and "nombre" in DATA["productos"].columns else []

    with st.expander("➕ Registrar ajuste", expanded=True):
        fecha = st.date_input("Fecha", value=date.today(), key="aj_fecha")
        c1, c2 = st.columns(2)
        with c1:
            producto_origen = st.selectbox("Producto origen (faltante / correcto)", productos_lista, key="aj_origen") if productos_lista else ""
            cantidad = st.number_input("Cantidad", min_value=1.0, step=1.0, key="aj_cantidad")
            tipo_ajuste = st.selectbox("Tipo de ajuste", ["ajuste_cruzado", "ajuste_positivo", "ajuste_negativo"], key="aj_tipo")
        with c2:
            producto_destino = st.selectbox("Producto destino (sobrante / cruzado)", productos_lista, key="aj_destino") if productos_lista else ""
            observacion = st.text_area("Observación", key="aj_obs")

        if st.button("Guardar ajuste"):
            po = get_producto_por_nombre(producto_origen)
            pdst = get_producto_por_nombre(producto_destino)
            if po is None or pdst is None:
                st.error("No se encontraron productos para ajustar.")
            else:
                costo_origen = float(limpiar_numero(po.get("costo")) or 0)
                costo_destino = float(limpiar_numero(pdst.get("costo")) or 0)
                diferencia_costo = abs((costo_origen - costo_destino) * float(cantidad))
                if costo_origen > costo_destino:
                    impacto = "perdida"
                elif costo_origen < costo_destino:
                    impacto = "ganancia"
                else:
                    impacto = "neutral"

                ok = insertar(
                    "ajustes_inventario",
                    {
                        "fecha": str(fecha),
                        "producto_origen": producto_origen,
                        "producto_destino": producto_destino,
                        "cantidad": float(cantidad),
                        "tipo_ajuste": tipo_ajuste,
                        "costo_origen": costo_origen,
                        "costo_destino": costo_destino,
                        "diferencia_costo": diferencia_costo,
                        "impacto": impacto,
                        "observacion": observacion,
                    },
                )

                if ok:
                    cant_origen = float(limpiar_numero(po.get("cantidad")) or 0) + float(cantidad)
                    cant_destino = float(limpiar_numero(pdst.get("cantidad")) or 0) - float(cantidad)
                    actualizar_stock_producto(producto_origen, cant_origen, fecha)
                    actualizar_stock_producto(producto_destino, cant_destino, fecha)
                    upsert_inventario_actual(producto_origen, costo_origen, float(limpiar_numero(po.get("precio")) or 0), cant_origen, fecha, "Ajuste inventario")
                    upsert_inventario_actual(producto_destino, costo_destino, float(limpiar_numero(pdst.get("precio")) or 0), cant_destino, fecha, "Ajuste inventario")
                    if impacto == "perdida":
                        registrar_perdida(
                            fecha,
                            producto_origen,
                            float(cantidad),
                            abs(costo_origen - costo_destino),
                            "ajuste_mercancia",
                            f"Ajuste contra {producto_destino}. Diferencia de costo total: {diferencia_costo}",
                        )
                    st.success("Ajuste guardado y stock actualizado.")
                    st.rerun()

    df = DATA["ajustes_inventario"].copy()
    if not df.empty:
        st.subheader("📋 Historial de ajustes")
        d1, d2 = rango_fechas_ui("ajustes")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar ajuste", key="buscar_ajustes")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "ajustes_inventario")
    else:
        st.info("No hay ajustes registrados.")


# =========================================================
# VENTAS
# =========================================================
elif menu == "Ventas":
    st.title("💰 Ventas")

    with st.expander("📥 Subir Excel / CSV de ventas"):
        st.write("Columnas esperadas: fecha, total, metodo. Observación opcional.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_ventas")
        if archivo is not None and st.button("Cargar ventas"):
            df = leer_archivo_subido(archivo)
            faltan = [c for c in ["fecha", "total", "metodo"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                count = 0
                for _, row in df.iterrows():
                    fecha = parsear_fecha(row["fecha"])
                    total = limpiar_numero(row["total"]) or 0
                    metodo = limpiar_texto(row["metodo"])
                    observacion = limpiar_texto(row["observacion"]) if "observacion" in df.columns else ""
                    if fecha:
                        insertar("ventas", {"fecha": fecha, "total": float(total), "metodo": metodo, "observacion": observacion})
                        count += 1
                st.success(f"Se cargaron {count} ventas.")
                st.rerun()

    with st.expander("➕ Agregar venta manual", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="venta_fecha")
        with c2:
            total = st.number_input("Total", min_value=0.0, step=1.0, key="venta_total")
        with c3:
            metodo = st.selectbox("Método", ["efectivo", "transferencia", "tarjeta"], key="venta_metodo")
        observacion = st.text_input("Observación", key="venta_obs")

        if st.button("Guardar venta"):
            if insertar("ventas", {"fecha": str(fecha), "total": float(total), "metodo": metodo, "observacion": observacion}):
                st.success("Venta guardada.")
                st.rerun()

    df = DATA["ventas"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("ventas")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar venta", key="buscar_ventas")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "ventas")
    else:
        st.info("No hay ventas registradas.")


# =========================================================
# COMPRAS
# =========================================================

elif menu == "Compras":
    st.title("🧾 Compras")
    st.caption("Las compras se registran por producto y alimentan automáticamente el inventario y los lotes FIFO.")

    productos_df = DATA["productos"].copy()
    proveedores_df = DATA.get("proveedores", pd.DataFrame()).copy()

    with st.expander("📥 Subir Excel / CSV de compras", expanded=False):
        st.write("Acepta columnas como fecha, producto/nombre, código, cantidad, costo, proveedor, número, descripción y método.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_compras_pro")
        if archivo is not None and st.button("Cargar compras", key="btn_cargar_compras_pro"):
            df = leer_archivo_subido(archivo)
            if "nombre" not in df.columns and "producto" not in df.columns:
                st.error("El archivo debe traer producto o nombre.")
            else:
                procesadas = 0
                for _, row in df.iterrows():
                    nombre = limpiar_texto(row.get("nombre") or row.get("producto"))
                    codigo = limpiar_texto(row.get("codigo"))
                    cantidad = limpiar_numero(row.get("cantidad")) or 0
                    costo_unitario = limpiar_numero(row.get("costo") or row.get("costo_unitario")) or 0
                    if not nombre or cantidad <= 0:
                        continue
                    prod = get_producto_por_codigo(codigo) if codigo else None
                    if prod is None:
                        prod = get_producto_por_nombre(nombre)
                    if prod is None:
                        payload = {
                            "fecha": parsear_fecha(row.get("fecha")) or ahora_str(),
                            "codigo": codigo,
                            "nombre": nombre,
                            "costo": float(costo_unitario),
                            "precio": float(limpiar_numero(row.get("precio")) or 0),
                            "cantidad": 0.0,
                            "activo": True,
                            "usa_inventario": True,
                        }
                        if "stock" in productos_df.columns:
                            payload["stock"] = 0.0
                        supabase.table("productos").insert(payload).execute()
                        DATA.update(cargar_datos())
                        prod = get_producto_por_codigo(codigo) if codigo else get_producto_por_nombre(nombre)
                    fecha_compra = parsear_fecha(row.get("fecha")) or ahora_str()
                    ok = registrar_compra_producto(
                        prod,
                        cantidad=float(cantidad),
                        costo_unitario=float(costo_unitario),
                        fecha_compra=fecha_compra,
                        proveedor=limpiar_texto(row.get("proveedor")),
                        numero=limpiar_texto(row.get("numero")),
                        descripcion=limpiar_texto(row.get("descripcion")),
                        metodo=limpiar_texto(row.get("metodo")),
                    )
                    if ok:
                        procesadas += 1
                st.success(f"Se cargaron {procesadas} compras.")
                st.rerun()

    with st.expander("➕ Registrar compra manual", expanded=True):
        crear_nuevo = st.checkbox("Crear producto nuevo desde compra", value=False, key="comp_crear_nuevo")
        if crear_nuevo:
            render_logo_y_encabezado()
            c1, c2 = st.columns(2)
            with c1:
                nuevo_codigo = st.text_input("Código nuevo", key="comp_nuevo_codigo")
                nuevo_nombre = st.text_input("Nombre producto nuevo", key="comp_nuevo_nombre")
            with c2:
                nuevo_precio = st.number_input("Precio de venta sugerido", min_value=0.0, step=1.0, key="comp_nuevo_precio")
                nuevo_categoria = st.text_input("Categoría", key="comp_nuevo_categoria")
        else:
            st.write("### Buscar producto")
            bus_compra = st.text_input("Buscar por nombre o código", key="compra_buscar_tarjetas")
            vista_compra = productos_df.copy()
            if not vista_compra.empty and bus_compra:
                vista_compra = buscar_df(vista_compra, bus_compra)
            cols_comp = st.columns(4)
            for i, (_, r) in enumerate(vista_compra.head(20).iterrows()):
                with cols_comp[i % 4]:
                    st.markdown("<div class='pos-card'>", unsafe_allow_html=True)
                    st.markdown(f"**{obtener_nombre_producto(r)}**")
                    st.caption(f"Código: {limpiar_texto(r.get('codigo'))}")
                    st.write(f"Costo: RD$ {(limpiar_numero(r.get('costo')) or 0):,.2f}")
                    st.write(f"Stock: {obtener_existencia_producto(r):,.0f}")
                    if st.button("Elegir", key=f"comp_card_{r['id']}"):
                        st.session_state['compra_producto_sel_manual'] = f"{obtener_nombre_producto(r)} | {limpiar_texto(r.get('codigo'))}"
                    st.markdown("</div>", unsafe_allow_html=True)
            opciones = []
            mapa_productos = {}
            if not productos_df.empty:
                for _, row in productos_df.iterrows():
                    etiqueta = f"{obtener_nombre_producto(row)} | {limpiar_texto(row.get('codigo'))}"
                    opciones.append(etiqueta)
                    mapa_productos[etiqueta] = row
            producto_sel = st.selectbox("Producto", opciones, key="comp_producto_sel") if opciones else None

        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="comp_fecha")
            numero = st.text_input("Número", key="comp_num")
            proveedor = st.text_input("Proveedor", key="comp_prov") if proveedores_df.empty else st.selectbox("Proveedor", [""] + proveedores_df["nombre"].astype(str).tolist(), key="comp_prov_sel")
        with c2:
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, key="comp_cantidad_new")
            costo_unitario = st.number_input("Costo unitario", min_value=0.0, step=1.0, key="comp_costo_unit")
            metodo = st.selectbox("Método", ["efectivo", "transferencia", "tarjeta", "credito"], key="comp_met")
        with c3:
            descripcion = st.text_area("Descripción / observación", key="comp_desc")

        if st.button("Guardar compra", key="btn_guardar_compra_pro"):
            prod = None
            if crear_nuevo:
                if not limpiar_texto(nuevo_nombre):
                    st.error("Debes poner nombre al producto nuevo.")
                    st.stop()
                existente = get_producto_por_codigo(nuevo_codigo) if nuevo_codigo else None
                if existente is None:
                    existente = get_producto_por_nombre(nuevo_nombre)
                if existente is None:
                    payload = {
                        "fecha": str(fecha),
                        "codigo": limpiar_texto(nuevo_codigo),
                        "nombre": limpiar_texto(nuevo_nombre),
                        "categoria": limpiar_texto(nuevo_categoria),
                        "costo": float(costo_unitario),
                        "precio": float(nuevo_precio),
                        "cantidad": 0.0,
                        "activo": True,
                        "usa_inventario": True,
                    }
                    if "stock" in DATA["productos"].columns:
                        payload["stock"] = 0.0
                    supabase.table("productos").insert(payload).execute()
                    DATA.update(cargar_datos())
                prod = get_producto_por_codigo(nuevo_codigo) if nuevo_codigo else get_producto_por_nombre(nuevo_nombre)
            else:
                prod = mapa_productos.get(producto_sel) if producto_sel else None
            if prod is None:
                st.error("No se encontró el producto para registrar la compra.")
            elif cantidad <= 0 or costo_unitario <= 0:
                st.error("Cantidad y costo deben ser mayores que cero.")
            else:
                ok = registrar_compra_producto(prod, float(cantidad), float(costo_unitario), str(fecha), proveedor, numero, descripcion, metodo)
                if ok:
                    st.success("Compra guardada y stock actualizado.")
                    st.rerun()

    df = DATA["compras"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("compras")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar compra", key="buscar_compras")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "compras")
    else:
        st.info("No hay compras registradas.")

# =========================================================
# CATÁLOGO DE GASTOS
# =========================================================
elif menu == "Catálogo de Gastos":
    st.title("🗂️ Catálogo de Gastos")

    with st.expander("➕ Agregar al catálogo", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="cat_nom")
            tipo = st.selectbox("Tipo", ["fijo", "variable"], key="cat_tipo")
            categoria = st.text_input("Categoría", key="cat_cat")
            activo = st.checkbox("Activo", value=True, key="cat_activo")
        with c2:
            metodo_pago_default = st.selectbox("Método de pago default", ["efectivo", "transferencia", "tarjeta"], key="cat_met")
            impuesto_default = st.number_input("Impuesto default", min_value=0.0, step=1.0, key="cat_imp")
            descripcion_default = st.text_area("Descripción default", key="cat_desc")

        if st.button("Guardar en catálogo"):
            if insertar(
                "catalogo_gastos",
                {
                    "nombre": nombre,
                    "tipo": tipo,
                    "categoria": categoria,
                    "activo": activo,
                    "metodo_pago_default": metodo_pago_default,
                    "impuesto_default": float(impuesto_default),
                    "descripcion_default": descripcion_default,
                },
            ):
                st.success("Gasto guardado en catálogo.")
                st.rerun()

    df = DATA["catalogo_gastos"].copy()
    if not df.empty:
        txt = st.text_input("Buscar en catálogo", key="buscar_catalogo")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "catalogo_gastos")
    else:
        st.info("No hay catálogo de gastos.")


# =========================================================
# GASTOS
# =========================================================
elif menu == "Gastos":
    st.title("💸 Gastos")

    catalogo = DATA["catalogo_gastos"].copy()
    if not catalogo.empty and "activo" in catalogo.columns:
        catalogo_activo = catalogo[catalogo["activo"] == True]
    else:
        catalogo_activo = catalogo

    with st.expander("➕ Registrar gasto", expanded=True):
        usar_catalogo = st.checkbox("Usar catálogo de gastos", value=True, key="usar_catalogo")
        gasto_catalogo = None
        if usar_catalogo and not catalogo_activo.empty and "nombre" in catalogo_activo.columns:
            nombres_cat = catalogo_activo["nombre"].astype(str).tolist()
            nombre_sel = st.selectbox("Selecciona gasto del catálogo", nombres_cat, key="gasto_cat_sel")
            gasto_catalogo = catalogo_activo[catalogo_activo["nombre"].astype(str) == nombre_sel].iloc[0]

        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="g_fecha")
            nombre = st.text_input("Nombre del gasto", value=str(gasto_catalogo["nombre"]) if gasto_catalogo is not None else "", key="g_nombre")
            tipo = st.selectbox(
                "Tipo",
                ["fijo", "variable"],
                index=0 if gasto_catalogo is not None and str(gasto_catalogo.get("tipo", "fijo")).lower() == "fijo" else 1 if gasto_catalogo is not None else 0,
                key="g_tipo",
            )
            categoria = st.text_input("Categoría", value=str(gasto_catalogo["categoria"]) if gasto_catalogo is not None and "categoria" in gasto_catalogo.index else "", key="g_categoria")
            responsable = st.text_input("Quién creó el gasto", key="g_responsable")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="g_monto")
            default_metodo = "efectivo"
            if gasto_catalogo is not None:
                metodo_cat = str(gasto_catalogo.get("metodo_pago_default", "efectivo")).lower()
                if metodo_cat in ["efectivo", "transferencia", "tarjeta"]:
                    default_metodo = metodo_cat
            metodo_pago = st.selectbox("Método de pago", ["efectivo", "transferencia", "tarjeta"], index=["efectivo", "transferencia", "tarjeta"].index(default_metodo), key="g_metodo")
            impuesto = st.number_input("Impuesto", min_value=0.0, step=1.0, value=float(limpiar_numero(gasto_catalogo.get("impuesto_default")) or 0) if gasto_catalogo is not None else 0.0, key="g_impuesto")
            detalle = st.text_area("Detalle", value=str(gasto_catalogo.get("descripcion_default", "")) if gasto_catalogo is not None else "", key="g_detalle")

        guardar_catalogo_nuevo = st.checkbox("Guardar este gasto nuevo también en el catálogo", value=False, key="g_guardar_cat")

        if st.button("Guardar gasto"):
            ok = insertar(
                "gastos",
                {
                    "fecha": str(fecha),
                    "nombre": nombre,
                    "tipo": tipo,
                    "categoria": categoria,
                    "monto": float(monto),
                    "metodo_pago": metodo_pago,
                    "impuesto": float(impuesto),
                    "detalle": detalle,
                    "responsable": responsable,
                },
            )
            if ok and guardar_catalogo_nuevo and nombre:
                existe = False
                if not DATA["catalogo_gastos"].empty and "nombre" in DATA["catalogo_gastos"].columns:
                    existe = normalizar_texto(nombre) in DATA["catalogo_gastos"]["nombre"].astype(str).apply(normalizar_texto).tolist()
                if not existe:
                    insertar(
                        "catalogo_gastos",
                        {
                            "nombre": nombre,
                            "tipo": tipo,
                            "categoria": categoria,
                            "activo": True,
                            "metodo_pago_default": metodo_pago,
                            "impuesto_default": float(impuesto),
                            "descripcion_default": detalle,
                        },
                    )
            if ok:
                st.success("Gasto guardado.")
                st.rerun()

    df = DATA["gastos"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("gastos")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar gasto", key="buscar_gastos")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "gastos")
    else:
        st.info("No hay gastos registrados.")


# =========================================================
# EMPLEADOS
# =========================================================
elif menu == "Empleados":
    st.title("👥 Empleados")

    with st.expander("📥 Subir Excel / CSV de empleados"):
        st.write("Columnas esperadas: nombre, puesto, sueldo, tipo_salario, frecuencia_pago. Activo opcional.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_empleados")
        if archivo is not None and st.button("Cargar empleados"):
            df = leer_archivo_subido(archivo)
            faltan = [c for c in ["nombre", "puesto", "sueldo", "tipo_salario", "frecuencia_pago"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                count = 0
                for _, row in df.iterrows():
                    insertar(
                        "empleados",
                        {
                            "fecha": parsear_fecha(row["fecha"]) if "fecha" in df.columns else ahora_str(),
                            "nombre": limpiar_texto(row["nombre"]),
                            "puesto": limpiar_texto(row["puesto"]),
                            "sueldo": float(limpiar_numero(row["sueldo"]) or 0),
                            "tipo_salario": limpiar_texto(row["tipo_salario"]),
                            "frecuencia_pago": limpiar_texto(row["frecuencia_pago"]),
                            "activo": bool(row["activo"]) if "activo" in df.columns else True,
                            "observacion": limpiar_texto(row["observacion"]) if "observacion" in df.columns else "",
                        },
                    )
                    count += 1
                st.success(f"Se cargaron {count} empleados.")
                st.rerun()

    with st.expander("➕ Agregar empleado manual", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="emp_fecha")
            nombre = st.text_input("Nombre", key="emp_nombre")
            puesto = st.text_input("Puesto", key="emp_puesto")
            sueldo = st.number_input("Sueldo", min_value=0.0, step=1.0, key="emp_sueldo")
        with c2:
            tipo_salario = st.selectbox("Tipo salario", ["fijo", "variable"], key="emp_tipo_salario")
            frecuencia_pago = st.selectbox("Frecuencia pago", ["mensual", "quincenal", "semanal"], key="emp_frec")
            activo = st.checkbox("Activo", value=True, key="emp_activo")
            observacion = st.text_area("Observación", key="emp_obs")

        if st.button("Guardar empleado"):
            if insertar(
                "empleados",
                {
                    "fecha": str(fecha),
                    "nombre": nombre,
                    "puesto": puesto,
                    "sueldo": float(sueldo),
                    "tipo_salario": tipo_salario,
                    "frecuencia_pago": frecuencia_pago,
                    "activo": activo,
                    "observacion": observacion,
                },
            ):
                st.success("Empleado guardado.")
                st.rerun()

    df = DATA["empleados"].copy()
    if not df.empty:
        txt = st.text_input("Buscar empleado", key="buscar_emp")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "empleados")
    else:
        st.info("No hay empleados registrados.")


# =========================================================
# ADELANTOS EMPLEADOS
# =========================================================
elif menu == "Adelantos Empleados":
    st.title("💵 Adelantos a Empleados")

    nombres_empleados = DATA["empleados"]["nombre"].astype(str).tolist() if not DATA["empleados"].empty and "nombre" in DATA["empleados"].columns else []

    with st.expander("➕ Registrar adelanto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="adel_fecha")
            empleado = st.selectbox("Empleado", nombres_empleados, key="adel_emp") if nombres_empleados else st.text_input("Empleado", key="adel_emp_txt")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="adel_monto")
            detalle = st.text_area("Detalle", key="adel_detalle")

        if st.button("Guardar adelanto"):
            if insertar(
                "adelantos_empleados",
                {"fecha": str(fecha), "empleado": empleado, "monto": float(monto), "detalle": detalle},
            ):
                st.success("Adelanto guardado.")
                st.rerun()

    df = DATA["adelantos_empleados"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("adelantos")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar adelanto", key="buscar_adel")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "adelantos_empleados")
    else:
        st.info("No hay adelantos registrados.")


# =========================================================
# PÉRDIDAS
# =========================================================
elif menu == "Pérdidas":
    st.title("📉 Pérdidas")

    productos_lista = DATA["productos"]["nombre"].astype(str).tolist() if not DATA["productos"].empty and "nombre" in DATA["productos"].columns else []

    with st.expander("➕ Registrar pérdida", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="perd_fecha")
            producto = st.selectbox("Producto", productos_lista, key="perd_prod") if productos_lista else st.text_input("Producto", key="perd_prod_txt")
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, key="perd_cant")
        with c2:
            costo_unitario = st.number_input("Costo unitario", min_value=0.0, step=1.0, key="perd_costo")
            tipo_perdida = st.selectbox("Tipo de pérdida", ["mercancia", "vencimiento", "rotura", "ajuste_mercancia", "otro"], key="perd_tipo")
            observacion = st.text_area("Observación", key="perd_obs")

        if st.button("Guardar pérdida"):
            if registrar_perdida(fecha, producto, cantidad, costo_unitario, tipo_perdida, observacion):
                st.success("Pérdida guardada.")
                st.rerun()

    df = DATA["perdidas"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("perdidas")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar pérdida", key="buscar_perd")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "perdidas")
    else:
        st.info("No hay pérdidas registradas.")


# =========================================================
# GASTOS DUEÑO
# =========================================================
elif menu == "Gastos Dueño":
    st.title("👤 Gastos / Retiros del Dueño")

    with st.expander("➕ Registrar gasto del dueño", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="dueno_fecha")
            concepto = st.text_input("Concepto", key="dueno_concepto")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="dueno_monto")
            detalle = st.text_area("Detalle", key="dueno_detalle")

        if st.button("Guardar gasto dueño"):
            if insertar(
                "gastos_dueno",
                {"fecha": str(fecha), "concepto": concepto, "monto": float(monto), "detalle": detalle},
            ):
                st.success("Gasto del dueño guardado.")
                st.rerun()

    df = DATA["gastos_dueno"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("dueno")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar gasto dueño", key="buscar_dueno")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "gastos_dueno")
    else:
        st.info("No hay gastos del dueño registrados.")


# =========================================================
# CIERRE DE CAJA
# =========================================================
elif menu == "Cierre de Caja":
    st.title("🧾 Cierre de Caja")
    render_logo_y_encabezado()

    with st.expander("➕ Registrar cierre de caja", expanded=True):
        fecha = st.date_input("Fecha de cierre", value=date.today(), key="caja_fecha")
        apertura = st.number_input("Fondo / apertura", min_value=0.0, step=1.0, key="caja_apertura")

        ventas_hoy = filtrar_por_fechas(DATA["ventas"], fecha, fecha)
        compras_hoy = filtrar_por_fechas(DATA["compras"], fecha, fecha)
        gastos_hoy = filtrar_por_fechas(DATA["gastos"], fecha, fecha)
        adelantos_hoy = filtrar_por_fechas(DATA["adelantos_empleados"], fecha, fecha)
        dueno_hoy = filtrar_por_fechas(DATA["gastos_dueno"], fecha, fecha)

        ventas_efectivo = suma_col(ventas_hoy[ventas_hoy["metodo"].astype(str).str.lower() == "efectivo"], "total") if not ventas_hoy.empty and "metodo" in ventas_hoy.columns else 0.0
        compras_efectivo = suma_col(compras_hoy[compras_hoy["metodo"].astype(str).str.lower() == "efectivo"], "monto") if not compras_hoy.empty and "metodo" in compras_hoy.columns else 0.0
        gastos_efectivo = suma_col(gastos_hoy[gastos_hoy["metodo_pago"].astype(str).str.lower() == "efectivo"], "monto") if not gastos_hoy.empty and "metodo_pago" in gastos_hoy.columns else 0.0
        adelantos_total = suma_col(adelantos_hoy, "monto")
        dueno_total = suma_col(dueno_hoy, "monto")

        efectivo_sistema = apertura + ventas_efectivo - compras_efectivo - gastos_efectivo - adelantos_total - dueno_total
        st.info(f"Efectivo esperado en sistema: RD$ {efectivo_sistema:,.2f}")

        efectivo_fisico = st.number_input("Efectivo físico contado", min_value=0.0, step=1.0, key="caja_fisico")
        detalle = st.text_area("Detalle / observación", key="caja_detalle")
        diferencia = float(efectivo_fisico) - float(efectivo_sistema)
        st.write(f"Diferencia: RD$ {diferencia:,.2f}")

        if st.button("Guardar cierre de caja"):
            if insertar(
                "cierre_caja",
                {
                    "fecha": str(fecha),
                    "apertura": float(apertura),
                    "efectivo_sistema": float(efectivo_sistema),
                    "efectivo_fisico": float(efectivo_fisico),
                    "diferencia": float(diferencia),
                    "detalle": detalle,
                },
            ):
                st.success("Cierre de caja guardado.")
                st.rerun()

    df = DATA["cierre_caja"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("caja")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar cierre de caja", key="buscar_caja")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "cierre_caja")
    else:
        st.info("No hay cierres de caja registrados.")


# =========================================================
# ESTADO DE RESULTADOS
# =========================================================
elif menu == "Estado de Resultados":
    st.title("📊 Estado de Resultados")

    desde, hasta = rango_fechas_ui("er")

    ventas_df = filtrar_por_fechas(DATA["ventas"], desde, hasta)
    compras_df = filtrar_por_fechas(DATA["compras"], desde, hasta)
    gastos_df = filtrar_por_fechas(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)

    ventas_tot = suma_col(ventas_df, "total")
    compras_tot = suma_col(compras_df, "monto")
    utilidad_bruta = st.number_input("Utilidad bruta manual", min_value=0.0, step=1.0, key="er_utilidad_bruta")
    costo_ventas = 0.0
    gastos_fijos, gastos_variables = obtener_gastos_fijos_variables(DATA["gastos"], desde, hasta)
    empleados_fijos = obtener_empleados_fijos_periodo(DATA["empleados"], desde, hasta)
    empleados_variables = obtener_empleados_variables_periodo(DATA["gastos"], desde, hasta)
    perdidas_tot = suma_col(perdidas_df, "valor")
    retiros_tot = suma_col(dueno_df, "monto")

    adelantos_tot = suma_col(filtrar_por_fechas(DATA["adelantos_empleados"], desde, hasta), "monto")
    utilidad_neta = utilidad_bruta - gastos_fijos - gastos_variables - empleados_fijos - empleados_variables - perdidas_tot

    resumen = pd.DataFrame(
        [
            ["Ventas", ventas_tot],
            ["Compras", compras_tot],
            ["Costo de ventas", costo_ventas],
            ["Utilidad bruta", utilidad_bruta],
            ["Gastos fijos", gastos_fijos],
            ["Gastos variables", gastos_variables],
            ["Empleados fijos", empleados_fijos],
            ["Empleados variables", empleados_variables],
            ["Adelantos", adelantos_tot],
            ["Pérdidas", perdidas_tot],
            ["Retiros del dueño", retiros_tot],
            ["65% dueño", utilidad_neta * 0.65],
            ["35% gerente", utilidad_neta * 0.35],
            ["Utilidad neta", utilidad_neta],
        ],
        columns=["concepto", "monto"],
    )

    st.dataframe(resumen, use_container_width=True)
    descargar_archivos(resumen, "estado_resultados_resumen")

    if st.button("💾 Guardar snapshot de este estado de resultados"):
        ok = guardar_snapshot_estado_resultados(
            fecha=date.today(),
            desde=desde,
            hasta=hasta,
            ventas=ventas_tot,
            compras=compras_tot,
            costo_ventas=costo_ventas,
            utilidad_bruta=utilidad_bruta,
            gastos_fijos=gastos_fijos,
            gastos_variables=gastos_variables,
            empleados_fijos=empleados_fijos,
            empleados_variables=empleados_variables,
            perdidas=perdidas_tot,
            retiros_dueno=retiros_tot,
            utilidad_neta=utilidad_neta,
        )
        if ok:
            st.success("Snapshot guardado.")
            st.rerun()

    hist = DATA["estado_resultados"].copy()
    if not hist.empty:
        st.subheader("📚 Historial guardado")
        st.dataframe(hist, use_container_width=True)
        descargar_archivos(hist, "estado_resultados_historial")



# =========================================================
# REPORTES
# =========================================================
elif menu == "Reportes":
    st.title("📑 Reportes y Comparaciones")

    tipo_reporte = st.selectbox("Tipo de reporte", ["Día", "Mes actual", "Año actual", "Rango personalizado"], key="rep_tipo")
    if tipo_reporte == "Rango personalizado":
        desde, hasta = rango_fechas_ui("rep")
    else:
        desde, hasta = rango_periodo(tipo_reporte)
        st.caption(f"Período seleccionado: {desde} a {hasta}")

    utilidad_bruta_manual = st.number_input("Utilidad bruta manual del período", min_value=0.0, step=1.0, key="rep_utilidad_bruta")
    resumen = resumen_financiero_periodo(desde, hasta, utilidad_bruta_manual)

    tabla_resumen = pd.DataFrame(
        [[k, v] for k, v in resumen.items()],
        columns=["concepto", "monto"],
    )
    ventas_rep = filtrar_por_fechas(DATA["ventas"], desde, hasta)
    if not ventas_rep.empty:
        cfr1, cfr2 = st.columns(2)
        with cfr1:
            metodo_f = st.selectbox("Filtrar ventas por método", ["Todos"] + sorted(ventas_rep["metodo_pago"].dropna().astype(str).unique().tolist()) if "metodo_pago" in ventas_rep.columns else ["Todos"], key="rep_metodo_pago")
        with cfr2:
            ncf_f = st.text_input("Buscar por NCF / factura", key="rep_ncf")
        if metodo_f != "Todos" and "metodo_pago" in ventas_rep.columns:
            ventas_rep = ventas_rep[ventas_rep["metodo_pago"].astype(str) == metodo_f]
        if ncf_f and "ncf" in ventas_rep.columns:
            ventas_rep = ventas_rep[ventas_rep["ncf"].astype(str).str.contains(ncf_f, case=False, na=False)]
        st.write("### Ventas filtradas")
        st.dataframe(ventas_rep, use_container_width=True)
        descargar_archivos(ventas_rep, "ventas_filtradas_reportes")

    st.subheader("Resumen del período")
    st.dataframe(tabla_resumen, use_container_width=True)
    descargar_archivos(tabla_resumen, f"reporte_{tipo_reporte.lower().replace(' ', '_')}")

    st.subheader("Comparación de períodos")
    modo_comp = st.selectbox("Comparar", ["Mes vs mes", "Período vs período"], key="rep_comp")
    if modo_comp == "Mes vs mes":
        mes_actual = date.today().replace(day=1)
        mes_anterior = (pd.Timestamp(mes_actual) - pd.offsets.MonthBegin(1)).date().replace(day=1)
        fin_mes_anterior = (pd.Timestamp(mes_actual) - pd.Timedelta(days=1)).date()
        res_actual = resumen_financiero_periodo(mes_actual, date.today(), utilidad_bruta_manual)
        res_anterior = resumen_financiero_periodo(mes_anterior, fin_mes_anterior, utilidad_bruta_manual)
        comp = pd.DataFrame(
            {
                "concepto": list(res_actual.keys()),
                "mes_actual": list(res_actual.values()),
                "mes_anterior": [res_anterior.get(k, 0.0) for k in res_actual.keys()],
            }
        )
        comp["diferencia"] = comp["mes_actual"] - comp["mes_anterior"]
        st.dataframe(comp, use_container_width=True)
        descargar_archivos(comp, "comparacion_mes_vs_mes")
    else:
        st.write("Selecciona dos rangos para comparar.")
        c1, c2 = st.columns(2)
        with c1:
            d1a, d1b = rango_fechas_ui("rep_a")
        with c2:
            d2a, d2b = rango_fechas_ui("rep_b")
        res_a = resumen_financiero_periodo(d1a, d1b, utilidad_bruta_manual)
        res_b = resumen_financiero_periodo(d2a, d2b, utilidad_bruta_manual)
        comp = pd.DataFrame(
            {
                "concepto": list(res_a.keys()),
                "periodo_a": list(res_a.values()),
                "periodo_b": [res_b.get(k, 0.0) for k in res_a.keys()],
            }
        )
        comp["diferencia"] = comp["periodo_a"] - comp["periodo_b"]
        st.dataframe(comp, use_container_width=True)
        descargar_archivos(comp, "comparacion_periodo_vs_periodo")

    st.subheader("Series para análisis")
    frecuencia = st.selectbox("Agrupación", ["Mensual", "Anual"], key="rep_freq")
    freq = "M" if frecuencia == "Mensual" else "Y"
    ventas_s = serie_periodica(filtrar_por_fechas(DATA["ventas"], desde, hasta), "total", freq)
    compras_s = serie_periodica(filtrar_por_fechas(DATA["compras"], desde, hasta), "monto", freq)
    gastos_s = serie_periodica(filtrar_por_fechas(DATA["gastos"], desde, hasta), "monto", freq)
    perdidas_s = serie_periodica(filtrar_por_fechas(DATA["perdidas"], desde, hasta), "valor", freq)

    if not ventas_s.empty:
        st.write("Ventas")
        st.line_chart(ventas_s.set_index("periodo"))
    if not compras_s.empty:
        st.write("Compras")
        st.bar_chart(compras_s.set_index("periodo"))
    if not gastos_s.empty:
        st.write("Gastos")
        st.bar_chart(gastos_s.set_index("periodo"))
    if not perdidas_s.empty:
        st.write("Pérdidas")
        st.line_chart(perdidas_s.set_index("periodo"))

# =========================================================
# AUDITORÍA
# =========================================================
elif menu == "Auditoría":
    st.title("📝 Auditoría")
    df = DATA["auditoria"].copy()
    if not df.empty:
        txt = st.text_input("Buscar en auditoría", key="buscar_aud")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "auditoria")
    else:
        st.info("No hay datos de auditoría o la tabla no existe todavía.")



# =========================================================
# POS
# =========================================================
elif menu == "POS":
    st.title("🛒 POS PRO")
    render_logo_y_encabezado()
    cfg = obtener_configuracion()
    productos_df = DATA["productos"].copy()
    if not productos_df.empty and "activo" in productos_df.columns:
        productos_df = productos_df[productos_df["activo"] == True]
    if productos_df.empty:
        st.warning("No hay productos activos para vender.")
    else:
        if "pos_carrito" not in st.session_state:
            st.session_state["pos_carrito"] = []
        carrito = st.session_state["pos_carrito"]

        def agregar_item_carrito(prod_row, cantidad=1.0, precio_usar=None):
            nombre = obtener_nombre_producto(prod_row)
            precio_base = precio_usar if precio_usar is not None else (limpiar_numero(prod_row.get("precio")) or 0)
            for item in carrito:
                if str(item["producto_id"]) == str(prod_row["id"]):
                    item["cantidad"] += float(cantidad)
                    item["total_linea"] = item["cantidad"] * item["precio_unitario"]
                    return
            carrito.append({
                "producto_id": str(prod_row["id"]),
                "codigo": limpiar_texto(prod_row.get("codigo")),
                "producto": nombre,
                "cantidad": float(cantidad),
                "precio_unitario": float(precio_base),
                "descuento_pct": 0.0,
                "total_linea": float(cantidad) * float(precio_base),
            })

        top1, top2, top3 = st.columns([1.2, 1.3, 1])
        with top1:
            cantidad_pre = st.number_input("Cant", min_value=1.0, step=1.0, value=1.0, key="pos_cant_pre")
        with top2:
            codigo_scan = st.text_input("Código / lector", key="pos_codigo")
        with top3:
            if st.button("Agregar por código", key="btn_pos_codigo"):
                prod = get_producto_por_codigo(codigo_scan)
                if prod is None:
                    st.error("Producto no encontrado con ese código.")
                elif producto_tiene_inventario(prod) and cantidad_pre > obtener_existencia_producto(prod):
                    st.error("No hay stock suficiente.")
                else:
                    agregar_item_carrito(prod, cantidad_pre)
                    st.rerun()

        busqueda = st.text_input("Buscar producto por nombre o código", key="pos_busqueda")
        temp = productos_df.copy()
        if busqueda:
            temp = temp[temp.astype(str).apply(lambda col: col.str.contains(busqueda, case=False, na=False)).any(axis=1)]
        st.write("### Productos")
        cols_cards = st.columns(4)
        for j, (_, prow) in enumerate(temp.head(24).iterrows()):
            with cols_cards[j % 4]:
                st.markdown("<div class='pos-card'>", unsafe_allow_html=True)
                st.markdown(f"**{obtener_nombre_producto(prow)}**")
                st.caption(f"Código: {limpiar_texto(prow.get('codigo'))}")
                st.write(f"Precio: RD$ {(limpiar_numero(prow.get('precio')) or 0):,.2f}")
                st.write(f"Stock: {obtener_existencia_producto(prow):,.0f}")
                if st.button("Agregar tarjeta", key=f"pos_card_{prow['id']}"):
                    if producto_tiene_inventario(prow) and cantidad_pre > obtener_existencia_producto(prow):
                        st.error("No hay stock suficiente.")
                    else:
                        agregar_item_carrito(prow, cantidad_pre)
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
        opciones = []
        mapa = {}
        for _, row in temp.iterrows():
            etiqueta = f"{obtener_nombre_producto(row)} | {limpiar_texto(row.get('codigo'))} | Stock {obtener_existencia_producto(row):,.0f}"
            opciones.append(etiqueta)
            mapa[etiqueta] = row
        csel1, csel2, csel3 = st.columns([2,1,1])
        with csel1:
            prod_label = st.selectbox("Producto", [""] + opciones, key="pos_producto_sel")
        with csel2:
            tipo_precio = st.selectbox("Precio", ["normal", "descuento", "especial"], key="pos_tipo_precio")
        with csel3:
            if st.button("➕ Agregar", key="btn_pos_agregar"):
                if not prod_label:
                    st.warning("Selecciona un producto.")
                else:
                    prod = mapa[prod_label]
                    precio_ref = limpiar_numero(prod.get("precio")) or 0.0
                    if tipo_precio == "descuento":
                        precio_ref = limpiar_numero(prod.get("precio_descuento")) or precio_ref
                    elif tipo_precio == "especial":
                        precio_ref = limpiar_numero(prod.get("precio_especial")) or precio_ref
                    if producto_tiene_inventario(prod) and cantidad_pre > obtener_existencia_producto(prod):
                        st.error("No hay stock suficiente.")
                    else:
                        agregar_item_carrito(prod, cantidad_pre, precio_ref)
                        st.rerun()

        st.subheader("🧾 Carrito")
        if carrito:
            total_bruto = 0.0
            quitar_idx = None
            for i, item in enumerate(carrito):
                cc1, cc2, cc3, cc4, cc5, cc6, cc7 = st.columns([1.2, 0.9, 2.4, 1, 1, 1, 0.7])
                cc1.text_input("Código", value=item["codigo"], key=f"pos_cod_{i}", disabled=True)
                nueva_cant = cc2.number_input("Cant", min_value=0.0, step=1.0, value=float(item["cantidad"]), key=f"pos_item_cant_{i}")
                cc3.text_input("Producto", value=item["producto"], key=f"pos_prod_{i}", disabled=True)
                puede_editar_precio = es_admin() or tiene_permiso("puede_editar_ventas")
                nuevo_precio = cc4.number_input("Precio", min_value=0.0, step=1.0, value=float(item["precio_unitario"]), key=f"pos_item_precio_{i}", disabled=not puede_editar_precio)
                desc_pct = cc5.number_input("Desc %", min_value=0.0, max_value=100.0, step=1.0, value=float(item.get("descuento_pct", 0.0)), key=f"pos_item_desc_{i}")
                subtotal_linea = max((float(nueva_cant) * float(nuevo_precio)) * (1 - desc_pct/100.0), 0.0)
                cc6.write(f"RD$ {subtotal_linea:,.2f}")
                if cc7.button("❌", key=f"pos_quitar_{i}"):
                    quitar_idx = i
                item["cantidad"] = float(nueva_cant)
                item["precio_unitario"] = float(nuevo_precio)
                item["descuento_pct"] = float(desc_pct)
                item["total_linea"] = float(subtotal_linea)
                total_bruto += subtotal_linea
            if quitar_idx is not None:
                carrito.pop(quitar_idx)
                st.rerun()
            carrito[:] = [it for it in carrito if float(it["cantidad"]) > 0]

            st.divider()
            cli_df = DATA.get("clientes", pd.DataFrame()).copy()
            usar_cliente = st.checkbox("Asignar cliente", value=False, key="pos_usar_cliente")
            cliente_nombre = "Venta general"
            cliente_id = None
            if usar_cliente and not cli_df.empty:
                cli_opt = ["Venta general"] + cli_df["nombre"].astype(str).tolist()
                cliente_nombre = st.selectbox("Cliente", cli_opt, key="pos_cliente_sel")
                if cliente_nombre != "Venta general":
                    cli_row = cli_df[cli_df["nombre"].astype(str) == cliente_nombre].iloc[0]
                    cliente_id = cli_row.get("id")

            descuento_global = st.number_input("Descuento global", min_value=0.0, step=1.0, key="pos_desc_global")
            subtotal_real = max(total_bruto - descuento_global, 0.0)

            usar_recargo = st.checkbox("Aplicar recargo visual (solo tarjeta)", value=False, key="pos_usar_recargo")
            recargo_pct = st.number_input("% recargo visual", min_value=0.0, step=0.5, value=float(cfg.get("recargo_tarjeta_pct") or 4), key="pos_recargo_pct") if usar_recargo else 0.0
            recargo_visual = subtotal_real * (recargo_pct / 100.0) if usar_recargo else 0.0
            total_cobrar = subtotal_real + recargo_visual
            if usar_recargo and cobro_tarjeta <= 0:
                st.warning("El recargo visual solo debe usarse cuando haya cobro con tarjeta.")

            st.subheader("Cobro")
            cp1, cp2, cp3, cp4 = st.columns(4)
            with cp1:
                recibido_efectivo = st.number_input("Recibido efectivo", min_value=0.0, step=1.0, key="pos_recib_ef")
                aplicado_efectivo = st.number_input("Aplicado venta efectivo", min_value=0.0, step=1.0, key="pos_apl_ef")
            with cp2:
                cobro_transferencia = st.number_input("Cobrado transferencia", min_value=0.0, step=1.0, key="pos_pag_tr")
                aplicado_transferencia = st.number_input("Aplicado venta transferencia", min_value=0.0, step=1.0, key="pos_apl_tr")
            with cp3:
                cobro_tarjeta = st.number_input("Cobrado tarjeta", min_value=0.0, step=1.0, key="pos_pag_tj")
                aplicado_tarjeta = st.number_input("Aplicado venta tarjeta", min_value=0.0, step=1.0, key="pos_apl_tj")
            with cp4:
                aplicado_credito = st.number_input("Crédito / fiado aplicado", min_value=0.0, step=1.0, key="pos_apl_cr")

            cobro_cliente_total = recibido_efectivo + cobro_transferencia + cobro_tarjeta + aplicado_credito
            aplicado_total_real = aplicado_efectivo + aplicado_transferencia + aplicado_tarjeta + aplicado_credito
            cambio = max(cobro_cliente_total - total_cobrar, 0.0)
            faltante_cliente = max(total_cobrar - cobro_cliente_total, 0.0)
            faltante_real = max(subtotal_real - aplicado_total_real, 0.0)

            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Subtotal real", f"RD$ {subtotal_real:,.2f}")
            s2.metric("Recargo visual", f"RD$ {recargo_visual:,.2f}")
            s3.metric("Total a cobrar", f"RD$ {total_cobrar:,.2f}")
            s4.metric("Cambio", f"RD$ {cambio:,.2f}" if cambio > 0 else f"Faltan RD$ {faltante_cliente:,.2f}")

            ncf = st.text_input("NCF (opcional)", key="pos_ncf")
            imprimir = st.checkbox("Generar factura para imprimir", value=True, key="pos_print")
            pagos_cliente = {
                "efectivo": float(recibido_efectivo),
                "transferencia": float(cobro_transferencia),
                "tarjeta": float(cobro_tarjeta),
                "credito": float(aplicado_credito),
            }

            if st.button("💳 Cobrar / guardar", key="btn_pos_cobrar"):
                if faltante_cliente > 0.001:
                    st.error("El cobro al cliente no cubre el total a cobrar.")
                elif faltante_real > 0.001:
                    st.error("Los montos aplicados a la venta real no cubren el subtotal real.")
                elif aplicado_credito > 0 and cliente_nombre == "Venta general":
                    st.error("Para vender a crédito debes asignar un cliente.")
                else:
                    try:
                        metodo_resumen = []
                        if aplicado_efectivo > 0: metodo_resumen.append("efectivo")
                        if aplicado_transferencia > 0: metodo_resumen.append("transferencia")
                        if aplicado_tarjeta > 0: metodo_resumen.append("tarjeta")
                        if aplicado_credito > 0: metodo_resumen.append("credito")
                        venta_resp = supabase.table("ventas").insert({
                            "fecha": datetime.now().isoformat(),
                            "subtotal": float(total_bruto),
                            "descuento": float(descuento_global),
                            "recargo": float(recargo_visual),
                            "total": float(subtotal_real),
                            "metodo_pago": "mixto" if len(metodo_resumen) > 1 else (metodo_resumen[0] if metodo_resumen else "efectivo"),
                            "cliente_id": cliente_id,
                            "cliente_nombre": cliente_nombre,
                            "usuario": nombre_usuario_actual(),
                            "dia_operativo": ahora_str(),
                            "ncf": ncf,
                            "tipo_venta": "POS",
                            "estado": "completada",
                            "anulado": False,
                        }).execute()
                        venta = (venta_resp.data or [{}])[0]
                        venta_id = venta.get("id")
                        for item in carrito:
                            prod = productos_df[productos_df["id"].astype(str) == str(item["producto_id"])].iloc[0]
                            costo_unit, movimientos_fifo = obtener_costo_fifo(prod, float(item["cantidad"]))
                            total_linea_real = float(item["total_linea"])
                            supabase.table("detalle_venta").insert({
                                "venta_id": str(venta_id),
                                "producto_id": str(prod["id"]),
                                "codigo": item["codigo"],
                                "producto": item["producto"],
                                "cantidad": float(item["cantidad"]),
                                "precio_unitario": float(item["precio_unitario"]),
                                "costo_unitario": float(costo_unit),
                                "descuento": float(item.get("descuento_pct", 0.0)),
                                "recargo": 0,
                                "total_linea": total_linea_real,
                                "ganancia_linea": total_linea_real - (float(item["cantidad"]) * float(costo_unit)),
                                "usuario": nombre_usuario_actual(),
                                "anulado": False,
                            }).execute()
                            if producto_tiene_inventario(prod):
                                nueva_cant = max(obtener_existencia_producto(prod) - float(item["cantidad"]), 0.0)
                                actualizar_existencia_producto(prod, nueva_cant)
                                aplicar_consumo_fifo(movimientos_fifo)
                                registrar_movimiento_inventario(prod["id"], obtener_nombre_producto(prod), "salida_venta", "ventas", venta_id, -float(item["cantidad"]), costo_unit, "Salida por venta POS")

                        pagos_aplicados = {
                            "efectivo": float(aplicado_efectivo),
                            "transferencia": float(aplicado_transferencia),
                            "tarjeta": float(aplicado_tarjeta),
                            "credito": float(aplicado_credito),
                        }
                        for metodo, monto in pagos_aplicados.items():
                            if monto > 0:
                                detalle = f"aplicado_real={monto}"
                                cobrado_cliente = pagos_cliente.get(metodo, 0.0)
                                if metodo == "efectivo":
                                    cobrado_cliente = float(recibido_efectivo)
                                supabase.table("ventas_pagos").insert({
                                    "venta_id": str(venta_id),
                                    "metodo": metodo,
                                    "monto": float(cobrado_cliente if metodo in ["efectivo", "transferencia", "tarjeta"] else monto),
                                    "referencia": detalle,
                                    "usuario": nombre_usuario_actual(),
                                }).execute()
                                if metodo != "credito":
                                    try:
                                        supabase.table("movimientos_caja").insert({
                                            "fecha": datetime.now().isoformat(),
                                            "dia_operativo": ahora_str(),
                                            "tipo_movimiento": "entrada",
                                            "origen": "venta",
                                            "referencia_id": str(venta_id),
                                            "metodo_pago": metodo,
                                            "monto": float(cobrado_cliente if metodo != "efectivo" else (recibido_efectivo - cambio)),
                                            "descripcion": f"Venta POS {venta_id}",
                                            "usuario": nombre_usuario_actual(),
                                            "tipo": "venta",
                                            "referencia": f"venta:{venta_id}",
                                        }).execute()
                                    except Exception:
                                        pass
                        if aplicado_credito > 0:
                            supabase.table("cuentas_por_cobrar").insert({
                                "cliente_id": cliente_id,
                                "cliente_nombre": cliente_nombre,
                                "venta_id": str(venta_id),
                                "monto_original": float(aplicado_credito),
                                "monto_abonado": 0,
                                "saldo_pendiente": float(aplicado_credito),
                                "estado": "pendiente",
                                "usuario": nombre_usuario_actual(),
                            }).execute()
                        registrar_auditoria("venta_pos", "ventas", f"venta_id={venta_id} total_real={subtotal_real} cobrado={total_cobrar}")
                        if imprimir:
                            st.session_state["ultima_factura_texto"] = generar_texto_factura(venta_id, cliente_nombre, carrito, subtotal_real, descuento_global, recargo_visual, total_cobrar, pagos_cliente, recibido_efectivo, cambio)
                        st.success(f"Venta registrada. Total real RD$ {subtotal_real:,.2f}. Total cobrado RD$ {total_cobrar:,.2f}. Cambio RD$ {cambio:,.2f}")
                        st.session_state["pos_carrito"] = []
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo registrar la venta: {exc}")

            factura_texto = st.session_state.get("ultima_factura_texto", "")
            if factura_texto:
                st.subheader("🧾 Factura / recibo")
                st.text(factura_texto)
                st.download_button(
                    "⬇️ Descargar factura TXT",
                    data=factura_texto.encode("utf-8"),
                    file_name=f"factura_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain",
                    key="dl_factura_pos",
                )
        else:
            st.info("Carrito vacío.")

# =========================================================
# CLIENTES
# =========================================================
elif menu == "Clientes":
    st.title("👥 Clientes")
    with st.expander("➕ Agregar cliente", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="cli_nombre")
            telefono = st.text_input("Teléfono", key="cli_tel")
            cedula_rnc = st.text_input("Cédula / RNC", key="cli_doc")
        with c2:
            direccion = st.text_input("Dirección", key="cli_dir")
            limite_credito = st.number_input("Límite de crédito", min_value=0.0, step=1.0, key="cli_lim")
            observacion = st.text_area("Observación", key="cli_obs")
        if st.button("Guardar cliente", key="btn_guardar_cliente"):
            if insertar("clientes", {"nombre": nombre, "telefono": telefono, "cedula_rnc": cedula_rnc, "direccion": direccion, "limite_credito": float(limite_credito), "balance_pendiente": 0.0, "activo": True, "observacion": observacion}):
                st.success("Cliente guardado.")
                st.rerun()
    df = DATA.get("clientes", pd.DataFrame()).copy()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "clientes")
    else:
        st.info("No hay clientes.")

# =========================================================
# PROVEEDORES
# =========================================================
elif menu == "Proveedores":
    st.title("🚚 Proveedores")
    with st.expander("➕ Agregar proveedor", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="prov_nombre")
            telefono = st.text_input("Teléfono", key="prov_tel")
            rnc = st.text_input("RNC", key="prov_rnc")
        with c2:
            direccion = st.text_input("Dirección", key="prov_dir")
            contacto = st.text_input("Contacto", key="prov_contacto")
            observacion = st.text_area("Observación", key="prov_obs")
        if st.button("Guardar proveedor", key="btn_guardar_prov"):
            if insertar("proveedores", {"nombre": nombre, "telefono": telefono, "rnc": rnc, "direccion": direccion, "contacto": contacto, "activo": True, "observacion": observacion}):
                st.success("Proveedor guardado.")
                st.rerun()
    df = DATA.get("proveedores", pd.DataFrame()).copy()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "proveedores")
    else:
        st.info("No hay proveedores.")

# =========================================================
# CREDITOS
# =========================================================
elif menu == "Créditos":
    st.title("💳 Créditos y cuentas por cobrar")
    cxc = DATA.get("cuentas_por_cobrar", pd.DataFrame()).copy()
    if not cxc.empty:
        st.dataframe(cxc, use_container_width=True)
        descargar_archivos(cxc, "cuentas_por_cobrar")
        cuentas = cxc[cxc["estado"].astype(str).str.lower() != "saldada"] if "estado" in cxc.columns else cxc
        if not cuentas.empty:
            st.subheader("Registrar abono")
            opciones = [f"{row['id']} | {row.get('cliente_nombre','')} | Saldo {limpiar_numero(row.get('saldo_pendiente')) or 0:,.2f}" for _, row in cuentas.iterrows()]
            elegido = st.selectbox("Cuenta", opciones, key="abono_cuenta")
            cuenta_id = elegido.split("|")[0].strip()
            monto = st.number_input("Monto abonado", min_value=0.0, step=1.0, key="abono_monto")
            metodo = st.selectbox("Método de pago", ["efectivo", "transferencia", "tarjeta"], key="abono_metodo")
            if st.button("Guardar abono", key="btn_guardar_abono"):
                fila = cuentas[cuentas["id"].astype(str) == cuenta_id].iloc[0]
                abonado = (limpiar_numero(fila.get("monto_abonado")) or 0) + float(monto)
                saldo = max((limpiar_numero(fila.get("monto_original")) or 0) - abonado, 0.0)
                insertar("abonos_credito", {"cuenta_id": int(fila["id"]), "cliente_id": fila.get("cliente_id"), "cliente_nombre": fila.get("cliente_nombre"), "monto": float(monto), "metodo_pago": metodo, "usuario": nombre_usuario_actual()})
                actualizar("cuentas_por_cobrar", fila["id"], {"monto_abonado": abonado, "saldo_pendiente": saldo, "estado": "saldada" if saldo <= 0 else "pendiente"})
                try:
                    supabase.table("movimientos_caja").insert({"fecha": datetime.now().isoformat(), "dia_operativo": ahora_str(), "tipo_movimiento": "entrada", "origen": "abono_credito", "referencia_id": str(fila["id"]), "metodo_pago": metodo, "monto": float(monto), "descripcion": f"Abono crédito {fila['cliente_nombre']}", "usuario": nombre_usuario_actual()}).execute()
                except Exception:
                    pass
                st.success("Abono guardado.")
                st.rerun()
    else:
        st.info("No hay cuentas por cobrar registradas.")

# =========================================================
# EDICIÓN TOTAL
# =========================================================
elif menu == "Edición Total":
    st.title("🛠️ Edición Total")
    if not es_admin() and not tiene_permiso("puede_configurar"):
        st.error("No tienes permiso para entrar aquí.")
    else:
        tablas_editables = [
            "productos", "compras", "ventas", "clientes", "proveedores", "gastos",
            "empleados", "adelantos_empleados", "perdidas", "gastos_dueno", "cierre_caja", "usuarios"
        ]
        tabla_sel = st.selectbox("Tabla", tablas_editables, key="ed_total_tabla")
        df_edit = leer_tabla(tabla_sel)
        if df_edit.empty:
            st.info("No hay registros en esa tabla.")
        elif "id" not in df_edit.columns:
            st.error("Esa tabla no tiene columna id para edición segura.")
        else:
            st.dataframe(df_edit, use_container_width=True)
            opciones = [f"{row['id']}" for _, row in df_edit.iterrows()]
            reg_id = st.selectbox("ID a editar", opciones, key="ed_total_id")
            fila = df_edit[df_edit["id"].astype(str) == str(reg_id)].iloc[0]
            payload = {}
            for col in df_edit.columns:
                if col == "id":
                    continue
                valor = fila.get(col)
                if isinstance(valor, (int, float)) and not pd.isna(valor):
                    payload[col] = st.text_input(col, value=str(valor), key=f"edit_{tabla_sel}_{col}")
                else:
                    payload[col] = st.text_input(col, value="" if pd.isna(valor) else str(valor), key=f"edit_{tabla_sel}_{col}")
            if st.button("Guardar edición total", key="btn_ed_total"):
                datos_final = {}
                for k, v in payload.items():
                    num = limpiar_numero(v)
                    datos_final[k] = num if num is not None and v != "" and not any(ch.isalpha() for ch in str(v)) else v
                ok = actualizar(tabla_sel, reg_id, datos_final, usuario=nombre_usuario_actual())
                if ok:
                    st.success("Registro actualizado.")
                    st.rerun()

# =========================================================
# USUARIOS
# =========================================================
elif menu == "Usuarios":
    st.title("👤 Usuarios")
    if not es_admin() and not tiene_permiso("puede_configurar"):
        st.error("No tienes permiso para entrar aquí.")
    else:
        with st.expander("➕ Crear / actualizar usuario", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                nombre = st.text_input("Nombre", key="usr_nombre")
                usuario = st.text_input("Usuario", key="usr_usuario")
                clave = st.text_input("Clave", key="usr_clave")
                rol = st.selectbox("Rol", ["admin", "gerente", "cajera"], key="usr_rol")
            with c2:
                activo = st.checkbox("Activo", value=True, key="usr_activo")
                puede_vender = st.checkbox("Puede vender", value=True, key="usr_pv")
                puede_editar_ventas = st.checkbox("Puede editar ventas", key="usr_pev")
                puede_eliminar = st.checkbox("Puede eliminar", key="usr_pel")
                puede_anular = st.checkbox("Puede anular", key="usr_pan")
                puede_ver_reportes = st.checkbox("Puede ver reportes", key="usr_pvr")
                puede_registrar_compras = st.checkbox("Puede registrar compras", key="usr_prc")
                puede_registrar_gastos = st.checkbox("Puede registrar gastos", key="usr_prg")
                puede_configurar = st.checkbox("Puede configurar", key="usr_pcf")
            if st.button("Guardar usuario", key="btn_guardar_usuario"):
                existentes = DATA.get("usuarios", pd.DataFrame()).copy()
                if not limpiar_texto(usuario):
                    st.error("Debes poner usuario.")
                elif not limpiar_texto(clave):
                    st.error("Debes poner clave.")
                else:
                    if not existentes.empty and "usuario" in existentes.columns and normalizar_texto(usuario) in existentes["usuario"].astype(str).apply(normalizar_texto).tolist():
                        fila = existentes[existentes["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario)].iloc[0]
                        actualizar("usuarios", fila["id"], {"nombre": nombre, "usuario": usuario, "clave": clave, "rol": rol, "activo": activo, "puede_vender": puede_vender, "puede_editar_ventas": puede_editar_ventas, "puede_eliminar": puede_eliminar, "puede_anular": puede_anular, "puede_ver_reportes": puede_ver_reportes, "puede_registrar_compras": puede_registrar_compras, "puede_registrar_gastos": puede_registrar_gastos, "puede_configurar": puede_configurar})
                        st.success("Usuario actualizado.")
                    else:
                        insertar("usuarios", {"nombre": nombre, "usuario": usuario, "clave": clave, "rol": rol, "activo": activo, "puede_vender": puede_vender, "puede_editar_ventas": puede_editar_ventas, "puede_eliminar": puede_eliminar, "puede_anular": puede_anular, "puede_ver_reportes": puede_ver_reportes, "puede_registrar_compras": puede_registrar_compras, "puede_registrar_gastos": puede_registrar_gastos, "puede_configurar": puede_configurar})
                        st.success("Usuario creado.")
                    st.rerun()
        df = DATA.get("usuarios", pd.DataFrame()).copy()
        if not df.empty:
            st.dataframe(df, use_container_width=True)

# =========================================================
# CONFIGURACION
# =========================================================
elif menu == "Configuración":
    st.title("⚙️ Configuración del sistema")
    if not es_admin() and not tiene_permiso("puede_configurar"):
        st.error("No tienes permiso para entrar aquí.")
    else:
        cfg = obtener_configuracion()
        if not cfg:
            st.error("No se encontró la configuración del sistema.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                negocio_nombre = st.text_input("Nombre del negocio", value=str(cfg.get("negocio_nombre") or ""))
                nombre_sistema = st.text_input("Nombre del sistema", value=str(cfg.get("nombre_sistema") or ""))
                propietario = st.text_input("Propietaria / responsable", value=str(cfg.get("propietario") or ""))
                slogan = st.text_input("Slogan", value=str(cfg.get("slogan") or ""))
            with c2:
                telefono = st.text_input("Teléfono", value=str(cfg.get("telefono") or ""))
                direccion = st.text_input("Dirección", value=str(cfg.get("direccion") or ""))
                recargo_tarjeta_pct = st.number_input("Recargo tarjeta %", min_value=0.0, step=0.5, value=float(limpiar_numero(cfg.get("recargo_tarjeta_pct")) or 4.0))
                cierre_dia_operativo_hora = st.text_input("Hora cierre día operativo", value=str(cfg.get("cierre_dia_operativo_hora") or "03:00"))
            logo_archivo = st.file_uploader("Subir / cambiar logo", type=["png", "jpg", "jpeg"], key="cfg_logo")
            if logo_archivo is not None:
                ok_logo, msg_logo = guardar_logo_configuracion(logo_archivo)
                if ok_logo:
                    st.success(msg_logo)
                    st.rerun()
                else:
                    st.error(msg_logo)

            if st.button("Guardar configuración", key="btn_guardar_cfg"):
                actualizar("configuracion_sistema", cfg["id"], {"negocio_nombre": negocio_nombre, "nombre_sistema": nombre_sistema, "propietario": propietario, "slogan": slogan, "telefono": telefono, "direccion": direccion, "recargo_tarjeta_pct": float(recargo_tarjeta_pct), "cierre_dia_operativo_hora": cierre_dia_operativo_hora})
                st.success("Configuración guardada.")
                st.rerun()
            st.subheader("Logo")
            logo_file = st.file_uploader("Sube logo", type=["png", "jpg", "jpeg", "webp"], key="cfg_logo")
            if logo_file is not None and st.button("Guardar logo", key="btn_guardar_logo"):
                if guardar_logo_en_configuracion(logo_file.getvalue(), logo_file.type or "image/png"):
                    st.success("Logo guardado.")
                    st.rerun()
            if cfg.get("logo_url"):
                st.image(cfg.get("logo_url"), width=220)
