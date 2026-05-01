import base64
import io
import re
import uuid
import unicodedata
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import Client, create_client

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
st.set_page_config(page_title="Sistema de Negocio PRO", layout="wide")


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



def es_cajera() -> bool:
    return normalizar_texto(usuario_sesion().get("rol", "")) in ["cajera", "cajero"]


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


def puede_editar_global() -> bool:
    return es_admin() or tiene_permiso("puede_editar_todo")


def puede_ver_utilidad_global() -> bool:
    return es_admin() or tiene_permiso("puede_ver_utilidad")


def valor_simple(valor: Any):
    if isinstance(valor, pd.Series):
        if valor.empty:
            return None
        return valor.iloc[0]
    if isinstance(valor, (list, tuple)):
        return valor[0] if valor else None
    return valor


def render_crud_generico(nombre_tabla: str, df: pd.DataFrame, titulo: str | None = None, excluir: list[str] | None = None):
    if not puede_editar_global():
        return
    if df is None or df.empty:
        return
    excluir = set((excluir or []) + ["id"])
    if "identificación" in df.columns:
        excluir.add("identificación")
    titulo = titulo or f"🛠️ Editar / eliminar en {nombre_tabla}"
    with st.expander(titulo, expanded=False):
        df_local = df.copy()
        if "fecha" in df_local.columns:
            try:
                df_local = df_local.sort_values("fecha", ascending=False)
            except Exception:
                pass
        opciones = []
        mapa = {}
        for _, row in df_local.iterrows():
            row_id = valor_simple(row.get("id") or row.get("identificación"))
            etiqueta_partes = [str(row_id)]
            for campo in ["nombre", "producto", "cliente_nombre", "proveedor", "concepto", "usuario", "metodo_pago", "metodo", "fecha", "total", "monto"]:
                if campo in row.index and limpiar_texto(row.get(campo)):
                    etiqueta_partes.append(limpiar_texto(row.get(campo)))
                    if len(etiqueta_partes) >= 4:
                        break
            etiqueta = " | ".join(etiqueta_partes)
            opciones.append(etiqueta)
            mapa[etiqueta] = row
        if not opciones:
            st.info("No hay filas para gestionar.")
            return
        elegido = st.selectbox("Selecciona un registro", opciones, key=f"crud_sel_{nombre_tabla}")
        fila = mapa[elegido]
        fila_id = valor_simple(fila.get("id") or fila.get("identificación"))

        editable_cols = [c for c in df_local.columns if c not in excluir]
        nuevos_datos = {}
        cols = st.columns(2)
        campos_numericos_forzados = {
            "sueldo", "dia_pago_1", "dia_pago_2", "monto", "cantidad", "costo", "precio",
            "total", "subtotal", "descuento", "recargo", "limite_credito", "balance_pendiente",
            "impuesto", "costo_unitario", "precio_unitario", "valor", "existencia_sistema",
            "existencia_fisica", "diferencia"
        }
        for i, col in enumerate(editable_cols):
            valor = valor_simple(fila.get(col))
            cont = cols[i % 2]
            with cont:
                if isinstance(valor, (bool,)) or str(valor).lower() in ["true", "false"]:
                    nuevos_datos[col] = st.checkbox(col, value=bool(valor), key=f"crud_{nombre_tabla}_{col}_{fila_id}")
                else:
                    num = limpiar_numero(valor)
                    es_numerico = (
                        (num is not None and col not in ["telefono", "rnc", "cedula_rnc", "codigo", "ncf"])
                        or col in campos_numericos_forzados
                    )
                    if es_numerico:
                        valor_num = float(num) if num is not None else 0.0
                        nuevos_datos[col] = st.number_input(
                            col,
                            value=valor_num,
                            step=1.0,
                            key=f"crud_{nombre_tabla}_{col}_{fila_id}"
                        )
                    else:
                        if "fecha" in col.lower():
                            fecha_val = pd.to_datetime(valor, errors="coerce")
                            if pd.isna(fecha_val):
                                nuevos_datos[col] = st.text_input(col, value=limpiar_texto(valor), key=f"crud_{nombre_tabla}_{col}_{fila_id}")
                            else:
                                nuevos_datos[col] = str(st.date_input(col, value=fecha_val.date(), key=f"crud_{nombre_tabla}_{col}_{fila_id}"))
                        elif len(limpiar_texto(valor)) > 60:
                            nuevos_datos[col] = st.text_area(col, value=limpiar_texto(valor), key=f"crud_{nombre_tabla}_{col}_{fila_id}")
                        else:
                            nuevos_datos[col] = st.text_input(col, value=limpiar_texto(valor), key=f"crud_{nombre_tabla}_{col}_{fila_id}")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Guardar cambios", key=f"crud_save_{nombre_tabla}_{fila_id}"):
                if actualizar(nombre_tabla, fila_id, nuevos_datos):
                    st.success("Registro actualizado.")
                    st.rerun()
        with c2:
            if st.button("🗑️ Eliminar registro", key=f"crud_delete_{nombre_tabla}_{fila_id}"):
                if eliminar(nombre_tabla, fila_id):
                    st.success("Registro eliminado.")
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
    df = DATA.get("productos", pd.DataFrame()).copy()
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
    return (
        limpiar_numero(row.get("cantidad"))
        or limpiar_numero(row.get("stock"))
        or limpiar_numero(row.get("existencias"))
        or 0.0
    )



def actualizar_existencia_producto(producto_row: pd.Series, nueva_cantidad: float) -> bool:
    payload = {"cantidad": float(nueva_cantidad)}
    if "stock" in producto_row.index:
        payload["stock"] = float(nueva_cantidad)
    return actualizar("productos", producto_row["id"], payload)


def obtener_detalle_venta(venta_id):
    return supabase.table("detalle_venta").select("*").eq("venta_id", venta_id).execute().data


def eliminar_linea_detalle(id_linea):
    supabase.table("detalle_venta").delete().eq("id", id_linea).execute()


def actualizar_linea_detalle(id_linea, cantidad):
    supabase.table("detalle_venta").update({"cantidad": cantidad}).eq("id", id_linea).execute()


def insertar_linea_detalle(venta_id, producto, cantidad, precio, costo):
    supabase.table("detalle_venta").insert({
        "venta_id": venta_id,
        "producto": producto,
        "cantidad": cantidad,
        "precio_unitario": precio,
        "costo_unitario": costo,
        "total_linea": cantidad * precio,
        "ganancia_linea": (precio - costo) * cantidad
    }).execute()



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
    hasta_dt = pd.to_datetime(hasta) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
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


def obtener_utilidad_bruta_periodo(ventas_df: pd.DataFrame) -> float:
    if ventas_df.empty:
        return 0.0
    utilidad = 0.0
    if "ganancia_bruta" in ventas_df.columns:
        utilidad += float(pd.to_numeric(ventas_df["ganancia_bruta"], errors="coerce").fillna(0).sum())
    if utilidad == 0.0 and "ganancia_bruta_manual" in ventas_df.columns:
        utilidad += float(pd.to_numeric(ventas_df["ganancia_bruta_manual"], errors="coerce").fillna(0).sum())
    return float(utilidad)


def obtener_ventas_periodo_actualizadas(desde, hasta) -> pd.DataFrame:
    try:
        resp = supabase.table("ventas").select("*").order("fecha", desc=True).execute()
        df = pd.DataFrame(resp.data or [])
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return filtrar_por_fechas(df, desde, hasta)
    except Exception:
        return filtrar_por_fechas(DATA["ventas"], desde, hasta)



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
            key=f"dl_csv_{base_name}_{uuid.uuid4().hex}",
        )
    with c2:
        st.download_button(
            "⬇️ Descargar Excel",
            data=xlsx_bytes,
            file_name=f"{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_xlsx_{base_name}_{uuid.uuid4().hex}",
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



def total_contable_sin_recargo(row) -> float:
    """
    Total real para contabilidad/caja/dashboard.
    El recargo de tarjeta NO se toma como ingreso real.
    """
    try:
        total = float(limpiar_numero(row.get("total")) or 0)
        recargo = float(limpiar_numero(row.get("recargo")) or limpiar_numero(row.get("recargo_tarjeta")) or 0)
        return max(total - recargo, 0)
    except Exception:
        try:
            return float(limpiar_numero(row.get("subtotal")) or limpiar_numero(row.get("total")) or 0)
        except Exception:
            return 0.0


def aplicar_total_contable_df(df):
    """
    Crea una columna total_contable = total - recargo.
    Debe estar definida antes de cargar_datos().
    """
    try:
        if df is None or df.empty:
            return df
        out = df.copy()
        out["total_contable"] = out.apply(total_contable_sin_recargo, axis=1)
        return out
    except Exception:
        return df


def leer_tabla(nombre_tabla: str, order_by: str = "id") -> pd.DataFrame:
    try:
        resp = supabase.table(nombre_tabla).select("*").order(order_by).execute()
        data = resp.data if resp.data else []
        df = pd.DataFrame(data)
    except Exception:
        try:
            resp = supabase.table(nombre_tabla).select("*").execute()
            data = resp.data if resp.data else []
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
    return aplicar_total_contable_df(df)



def insertar(nombre_tabla: str, datos: dict) -> bool:
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        registrar_auditoria("insertar", nombre_tabla, str(datos)[:500])
        return True
    except Exception as exc:
        st.error(f"Error al insertar en {nombre_tabla}: {exc}")
        return False



def _campos_pk(nombre_tabla: str) -> list[str]:
    if nombre_tabla == "ventas":
        return ["id", "identificación"]
    return ["id"]


def actualizar(nombre_tabla: str, fila_id: Any, datos: dict) -> bool:
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    for campo in campos:
        try:
            supabase.table(nombre_tabla).update(datos).eq(campo, fila_id).execute()
            registrar_auditoria("actualizar", nombre_tabla, f"{campo}={fila_id} | {str(datos)[:500]}")
            return True
        except Exception as exc:
            ultimo_error = exc
    st.error(f"Error al actualizar en {nombre_tabla}: {ultimo_error}")
    return False



def eliminar(nombre_tabla: str, fila_id: Any) -> bool:
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    for campo in campos:
        try:
            supabase.table(nombre_tabla).delete().eq(campo, fila_id).execute()
            registrar_auditoria("eliminar", nombre_tabla, f"{campo}={fila_id}")
            return True
        except Exception as exc:
            ultimo_error = exc
    st.error(f"Error al eliminar en {nombre_tabla}: {ultimo_error}")
    return False



def anular(nombre_tabla: str, fila_id: Any, motivo: str = "") -> bool:
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    for campo in campos:
        try:
            supabase.table(nombre_tabla).update({"anulado": True, "motivo_anulacion": motivo}).eq(campo, fila_id).execute()
            registrar_auditoria("anular", nombre_tabla, f"{campo}={fila_id} motivo={motivo}")
            return True
        except Exception as exc:
            ultimo_error = exc
    st.error(f"Error al anular en {nombre_tabla}: {ultimo_error}")
    return False


def ajustar_pagos_sin_recargo_tarjeta(pagos_df: pd.DataFrame, ventas_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if pagos_df is None or pagos_df.empty:
        return pagos_df
    pagos = pagos_df.copy()
    if "monto" not in pagos.columns:
        return pagos
    pagos["monto"] = pd.to_numeric(pagos["monto"], errors="coerce").fillna(0)
    metodo_col = "metodo" if "metodo" in pagos.columns else ("metodo_pago" if "metodo_pago" in pagos.columns else None)
    if not metodo_col or ventas_df is None or ventas_df.empty:
        return pagos
    ventas = ventas_df.copy()
    ventas = aplicar_total_contable_df(ventas) if "aplicar_total_contable_df" in globals() else ventas

    def descontar(indices, exceso):
        for metodo_prioridad in ["tarjeta", "efectivo", "transferencia", "credito"]:
            for idx in indices:
                if exceso <= 0:
                    return
                if normalizar_texto(pagos.at[idx, metodo_col]) != metodo_prioridad:
                    continue
                monto = float(pagos.at[idx, "monto"])
                quitar = min(monto, exceso)
                pagos.at[idx, "monto"] = monto - quitar
                exceso -= quitar

    id_col = next((c for c in ["id", "identificación", "identificacion"] if c in ventas.columns), None)
    if id_col and "venta_id" in pagos.columns:
        for _, venta in ventas.iterrows():
            venta_id = str(venta.get(id_col))
            idxs = list(pagos[pagos["venta_id"].astype(str) == venta_id].index)
            if not idxs:
                continue
            total_real = float(limpiar_numero(venta.get("total_contable")) or limpiar_numero(venta.get("subtotal")) or limpiar_numero(venta.get("total")) or 0)
            total_pagado = float(pagos.loc[idxs, "monto"].sum())
            exceso = max(total_pagado - total_real, 0.0)
            if exceso > 0:
                descontar(idxs, exceso)
    return pagos

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

if "pos_post_venta" not in st.session_state:
    st.session_state["pos_post_venta"] = None

# =========================================================
# HELPERS DE NEGOCIO
# =========================================================
def get_producto_por_nombre(nombre: str):
    df = DATA["productos"]
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
    if "stock" in fila.index:
        payload["stock"] = float(nueva_cantidad)
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





def upsert_conteo_base(producto: str, existencia: float, fecha_mov, observacion: str = "") -> bool:
    conteo = DATA.get("conteo_inventario", pd.DataFrame()).copy()
    producto_n = normalizar_texto(producto)
    fecha_txt = str(fecha_mov)
    if not conteo.empty and "producto" in conteo.columns:
        tmp = conteo.copy()
        tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
        if "fecha" in tmp.columns:
            tmp["_f"] = pd.to_datetime(tmp["fecha"], errors="coerce").dt.date.astype(str)
            match = tmp[(tmp["_n"] == producto_n) & (tmp["_f"] == fecha_txt)]
        else:
            match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            fila = match.iloc[0]
            existencia_fisica = limpiar_numero(fila.get("existencia_fisica"))
            if existencia_fisica is None:
                existencia_fisica = float(existencia)
            diferencia = float(existencia_fisica) - float(existencia)
            estado = "cuadrado" if abs(diferencia) < 0.0001 else ("faltante" if diferencia < 0 else "sobrante")
            return actualizar(
                "conteo_inventario",
                fila["id"],
                {
                    "fecha": fecha_txt,
                    "producto": limpiar_texto(producto),
                    "existencia_sistema": float(existencia),
                    "existencia_fisica": float(existencia_fisica),
                    "diferencia": float(diferencia),
                    "estado": estado,
                    "observacion": observacion or fila.get("observacion") or "Sincronizado desde productos",
                },
            )
    return insertar(
        "conteo_inventario",
        {
            "fecha": fecha_txt,
            "producto": limpiar_texto(producto),
            "existencia_sistema": float(existencia),
            "existencia_fisica": float(existencia),
            "diferencia": 0.0,
            "estado": "cuadrado",
            "observacion": observacion or "Sincronizado desde productos",
        },
    )


def sincronizar_producto_inventario(producto_row: pd.Series | dict, fecha_mov=None, observacion: str = "") -> bool:
    if fecha_mov is None:
        fecha_mov = ahora_str()
    nombre = obtener_nombre_producto(producto_row)
    costo = float(limpiar_numero(producto_row.get("costo")) or 0)
    precio = float(limpiar_numero(producto_row.get("precio")) or 0)
    existencia = float(obtener_existencia_producto(producto_row))
    ok1 = upsert_inventario_actual(nombre, costo, precio, existencia, fecha_mov, observacion or "Sincronizado desde productos")
    ok2 = upsert_conteo_base(nombre, existencia, fecha_mov, observacion or "Sincronizado desde productos")
    return bool(ok1 and ok2)


def refrescar_producto_por_id(producto_id: Any):
    try:
        resp = supabase.table("productos").select("*").eq("id", producto_id).limit(1).execute()
        filas = resp.data or []
        if filas:
            return pd.Series(filas[0])
    except Exception:
        pass
    return None


def revertir_inventario_de_venta(venta_id: Any, marcar_detalle_anulado: bool = False) -> bool:
    try:
        resp = supabase.table("detalle_venta").select("*").eq("venta_id", str(venta_id)).execute()
        detalles = resp.data or []
    except Exception as exc:
        st.error(f"No se pudo leer el detalle de venta: {exc}")
        return False
    for det in detalles:
        producto_id = det.get("producto_id")
        cantidad = float(limpiar_numero(det.get("cantidad")) or 0)
        if not producto_id or cantidad <= 0:
            continue
        prod = refrescar_producto_por_id(producto_id)
        if prod is None:
            continue
        nueva_cant = float(obtener_existencia_producto(prod)) + cantidad
        actualizar_existencia_producto(prod, nueva_cant)
        prod2 = refrescar_producto_por_id(producto_id)
        if prod2 is None:
            prod2 = prod
        sincronizar_producto_inventario(prod2, ahora_str(), f"Reintegro por venta {venta_id}")
        registrar_movimiento_inventario(producto_id, obtener_nombre_producto(prod2), "reversa_venta", "ventas", venta_id, cantidad, float(limpiar_numero(det.get("costo_unitario")) or 0), "Reversa por anulación/eliminación de venta")
        if marcar_detalle_anulado and det.get("id"):
            try:
                supabase.table("detalle_venta").update({"anulado": True}).eq("id", det.get("id")).execute()
            except Exception:
                pass
    return True


def eliminar_venta_completa_app(venta_id: Any) -> bool:
    if not revertir_inventario_de_venta(venta_id, marcar_detalle_anulado=False):
        return False
    try:
        try:
            cxc = supabase.table("cuentas_por_cobrar").select("id").eq("venta_id", str(venta_id)).execute().data or []
            for row in cxc:
                supabase.table("abonos_credito").delete().eq("cuenta_id", str(row.get("id"))).execute()
            supabase.table("cuentas_por_cobrar").delete().eq("venta_id", str(venta_id)).execute()
        except Exception:
            pass
        for tabla in ["ventas_pagos", "detalle_venta"]:
            try:
                supabase.table(tabla).delete().eq("venta_id", str(venta_id)).execute()
            except Exception:
                pass
        ok = eliminar("ventas", venta_id)
        if ok:
            registrar_auditoria("eliminar_venta_completa", "ventas", f"venta_id={venta_id}")
        return ok
    except Exception as exc:
        st.error(f"No se pudo eliminar la venta completa: {exc}")
        return False


def anular_venta_completa_app(venta_id: Any, motivo: str = "") -> bool:
    if not revertir_inventario_de_venta(venta_id, marcar_detalle_anulado=True):
        return False
    try:
        try:
            supabase.table("ventas_pagos").update({"anulado": True}).eq("venta_id", str(venta_id)).execute()
        except Exception:
            pass
        ok = actualizar("ventas", venta_id, {
            "anulado": True,
            "motivo_anulacion": motivo or "Anulada manualmente",
            "estado": "anulada",
            "total": 0.0,
            "subtotal": 0.0,
            "descuento": 0.0,
            "recargo": 0.0,
            "ganancia_bruta": 0.0,
            "ganancia_bruta_manual": 0.0,
        })
        if ok:
            registrar_auditoria("anular_venta_completa", "ventas", f"venta_id={venta_id}")
        return ok
    except Exception as exc:
        st.error(f"No se pudo anular la venta completa: {exc}")
        return False


def obtener_costo_desde_inventario(producto: str) -> float:
    """
    Para pérdidas, toma el costo en vivo desde Supabase.
    Prioridad:
    1) inventario_actual: costo / costo_unitario / costo_promedio / precio_compra
    2) productos: costo / costo_unitario / costo_promedio / precio_compra
    """
    producto_n = normalizar_texto(producto)
    if not producto_n:
        return 0.0

    # 1) Buscar en inventario_actual en vivo
    try:
        resp = supabase.table("inventario_actual").select("*").execute()
        invent = pd.DataFrame(resp.data or [])
    except Exception:
        invent = DATA.get("inventario_actual", pd.DataFrame()).copy()

    if not invent.empty and "producto" in invent.columns:
        tmp = invent.copy()
        tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
        match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            if "fecha" in match.columns:
                match = match.copy()
                match["fecha"] = pd.to_datetime(match["fecha"], errors="coerce")
                match = match.sort_values("fecha", ascending=False)
            fila_inv = match.iloc[0]
            for campo in ["costo", "costo_unitario", "costo_promedio", "precio_compra", "ultimo_costo"]:
                if campo in fila_inv.index:
                    costo = limpiar_numero(fila_inv.get(campo))
                    if costo is not None and costo > 0:
                        return float(costo)

    # 2) Buscar en productos en vivo
    try:
        resp = supabase.table("productos").select("*").execute()
        productos = pd.DataFrame(resp.data or [])
    except Exception:
        productos = DATA.get("productos", pd.DataFrame()).copy()

    if not productos.empty and "nombre" in productos.columns:
        tmp = productos.copy()
        tmp["_n"] = tmp["nombre"].astype(str).apply(normalizar_texto)
        match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            fila_prod = match.iloc[0]
            for campo in ["costo", "costo_unitario", "costo_promedio", "precio_compra", "ultimo_costo"]:
                if campo in fila_prod.index:
                    costo = limpiar_numero(fila_prod.get(campo))
                    if costo is not None and costo > 0:
                        return float(costo)

    return 0.0


def obtener_existencia_desde_inventario(producto: str) -> float:
    """
    Toma la existencia en vivo desde inventario_actual.
    Si no aparece, usa productos como respaldo.
    """
    producto_n = normalizar_texto(producto)
    if not producto_n:
        return 0.0

    try:
        resp = supabase.table("inventario_actual").select("*").execute()
        invent = pd.DataFrame(resp.data or [])
    except Exception:
        invent = DATA.get("inventario_actual", pd.DataFrame()).copy()

    if not invent.empty and "producto" in invent.columns:
        tmp = invent.copy()
        tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
        match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            if "fecha" in match.columns:
                match = match.copy()
                match["fecha"] = pd.to_datetime(match["fecha"], errors="coerce")
                match = match.sort_values("fecha", ascending=False)
            fila_inv = match.iloc[0]
            for campo in ["existencia_sistema", "cantidad", "stock", "existencias"]:
                if campo in fila_inv.index:
                    existencia = limpiar_numero(fila_inv.get(campo))
                    if existencia is not None:
                        return float(existencia)

    prod = get_producto_por_nombre(producto)
    if prod is not None:
        return float(obtener_existencia_producto(prod))

    return 0.0

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




def leer_pagos_empleados_actualizados() -> pd.DataFrame:
    """Lee los pagos de empleados directamente desde Supabase para que el Dashboard se actualice en vivo."""
    try:
        resp = supabase.table("adelantos_empleados").select("*").execute()
        df = pd.DataFrame(resp.data or [])
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return df
    except Exception:
        return DATA.get("adelantos_empleados", pd.DataFrame()).copy()


def obtener_texto_clasificacion_pago(df: pd.DataFrame) -> pd.Series:
    texto = pd.Series([""] * len(df), index=df.index)
    for col in ["tipo_pago", "concepto", "detalle", "observacion", "descripción", "descripcion", "tipo", "categoria"]:
        if col in df.columns:
            texto = texto + " " + df[col].astype(str)
    return texto.apply(normalizar_texto)


def obtener_empleados_fijos_periodo(empleados_df: pd.DataFrame, desde, hasta) -> float:
    """
    El sueldo del empleado NO se descuenta automático.
    Solo se suma lo pagado realmente en la tabla adelantos_empleados.
    Todo pago que no sea comisión/bono/variable se trata como empleado fijo.
    """
    pagos = leer_pagos_empleados_actualizados()
    if pagos.empty:
        return 0.0

    pagos_f = filtrar_por_fechas(pagos, desde, hasta).copy()
    if pagos_f.empty or "monto" not in pagos_f.columns:
        return 0.0

    pagos_f["monto"] = pd.to_numeric(pagos_f["monto"], errors="coerce").fillna(0)
    texto = obtener_texto_clasificacion_pago(pagos_f)

    mask_variable = texto.str.contains("variable|comision|comisión|bono|incentivo", na=False)
    return float(pagos_f.loc[~mask_variable, "monto"].sum())



def obtener_empleados_variables_periodo(gastos_df: pd.DataFrame, desde, hasta) -> float:
    """
    Solo se suman pagos variables reales: comisión, bono, incentivo o variable.
    """
    total = 0.0

    pagos = leer_pagos_empleados_actualizados()
    if not pagos.empty:
        pagos_f = filtrar_por_fechas(pagos, desde, hasta).copy()
        if not pagos_f.empty and "monto" in pagos_f.columns:
            pagos_f["monto"] = pd.to_numeric(pagos_f["monto"], errors="coerce").fillna(0)
            texto = obtener_texto_clasificacion_pago(pagos_f)
            mask_var = texto.str.contains("variable|comision|comisión|bono|incentivo", na=False)
            total += float(pagos_f.loc[mask_var, "monto"].sum())

    if not gastos_df.empty and "categoria" in gastos_df.columns:
        temp = filtrar_por_fechas(gastos_df, desde, hasta).copy()
        if not temp.empty:
            temp["categoria"] = temp["categoria"].astype(str).apply(normalizar_texto)
            temp = temp[temp["categoria"] == "nomina variable"]
            total += suma_col(temp, "monto")

    return float(total)



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



def calcular_total_dinero_inventario() -> float:
    """
    Calcula el valor total del inventario:
    existencia actual x costo.
    Usa inventario_actual como fuente principal.
    """
    try:
        inv = DATA.get("inventario_actual", pd.DataFrame()).copy()
        if inv.empty:
            return 0.0

        col_exist = None
        for c in ["existencia_sistema", "cantidad", "stock", "existencias"]:
            if c in inv.columns:
                col_exist = c
                break

        col_costo = None
        for c in ["costo", "costo_unitario", "costo_promedio", "precio_compra", "ultimo_costo"]:
            if c in inv.columns:
                col_costo = c
                break

        if not col_exist or not col_costo:
            return 0.0

        inv[col_exist] = pd.to_numeric(inv[col_exist], errors="coerce").fillna(0)
        inv[col_costo] = pd.to_numeric(inv[col_costo], errors="coerce").fillna(0)

        return float((inv[col_exist] * inv[col_costo]).sum())
    except Exception:
        return 0.0


def resumen_financiero_periodo(desde, hasta, utilidad_bruta_manual: float = 0.0) -> dict[str, float]:
    ventas_df = obtener_ventas_periodo_actualizadas(desde, hasta)
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
    utilidad_bruta_ventas = obtener_utilidad_bruta_periodo(ventas_df)
    utilidad_bruta = float(utilidad_bruta_ventas) + float(utilidad_bruta_manual)

    utilidad_neta = (
        float(utilidad_bruta)
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
        "utilidad_bruta_ventas": float(utilidad_bruta_ventas),
        "utilidad_bruta_manual": float(utilidad_bruta_manual),
        "utilidad_bruta": float(utilidad_bruta),
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




def usuario_id_actual():
    user = usuario_sesion()
    return user.get("id")


def obtener_caja_abierta():
    usuario_id = usuario_id_actual()
    if not usuario_id:
        return None
    try:
        resp = (
            supabase.table("caja")
            .select("*")
            .eq("usuario_id", str(usuario_id))
            .eq("estado", "abierta")
            .order("fecha_apertura", desc=True)
            .limit(1)
            .execute()
        )
        filas = resp.data or []
        return filas[0] if filas else None
    except Exception:
        return None


def abrir_caja(monto_inicial: float, observacion: str = "") -> tuple[bool, str]:
    if obtener_caja_abierta() is not None:
        return False, "Ya tienes una caja abierta."
    usuario_id = usuario_id_actual()
    if not usuario_id:
        return False, "No se encontró el usuario actual."
    try:
        supabase.table("caja").insert({
            "usuario_id": str(usuario_id),
            "fecha_apertura": datetime.now().isoformat(),
            "monto_inicial": float(monto_inicial),
            "estado": "abierta",
            "dia_operativo": ahora_str(),
            "observacion": observacion,
            "anulado": False,
        }).execute()
        registrar_auditoria("abrir_caja", "caja", f"monto_inicial={monto_inicial}")
        return True, "Caja abierta correctamente."
    except Exception as exc:
        return False, f"No se pudo abrir caja: {exc}"


def cerrar_caja(caja_row: dict, monto_cierre: float, observacion: str = "") -> tuple[bool, str]:
    try:
        monto_inicial = float(limpiar_numero(caja_row.get("monto_inicial")) or 0)
        diferencia = float(monto_cierre) - monto_inicial
        supabase.table("caja").update({
            "fecha_cierre": datetime.now().isoformat(),
            "monto_cierre": float(monto_cierre),
            "diferencia": float(diferencia),
            "observacion": observacion or caja_row.get("observacion") or "",
            "estado": "cerrada",
        }).eq("id", caja_row["id"]).execute()
        insertar("cierre_caja", {
            "fecha": datetime.now().isoformat(),
            "apertura": monto_inicial,
            "efectivo_sistema": monto_inicial,
            "efectivo_fisico": float(monto_cierre),
            "diferencia": float(diferencia),
            "detalle": observacion,
        })
        registrar_auditoria("cerrar_caja", "caja", f"id={caja_row['id']} monto_cierre={monto_cierre}")
        return True, "Caja cerrada correctamente."
    except Exception as exc:
        return False, f"No se pudo cerrar caja: {exc}"



def html_escape(valor: Any) -> str:
    txt = limpiar_texto(valor)
    return (
        txt.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def construir_html_impresion(post_venta: dict, tipo: str = "factura") -> str:
    negocio = obtener_configuracion().get("negocio_nombre") or "Sistema de Negocio PRO"
    titulo = "TICKET" if tipo == "ticket" else "FACTURA"
    items = post_venta.get("items") or []
    filas = ""
    for item in items:
        filas += f"""
        <tr>
            <td>{html_escape(item.get('producto'))}</td>
            <td style='text-align:center'>{float(item.get('cantidad', 0)):.0f}</td>
            <td style='text-align:right'>RD$ {float(item.get('precio_unitario', 0)):,.2f}</td>
            <td style='text-align:right'>RD$ {float(item.get('total_linea', 0)):,.2f}</td>
        </tr>
        """
    if not filas:
        filas = "<tr><td colspan='4' style='text-align:center'>Sin detalle</td></tr>"

    ncf = html_escape(post_venta.get("numero_factura") or post_venta.get("ncf") or post_venta.get("venta_id") or "")
    cliente = html_escape(post_venta.get("cliente_nombre") or "Venta general")
    metodo = html_escape(post_venta.get("metodo_pago") or "")
    fecha_txt = html_escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total = float(post_venta.get("total", 0) or 0)
    cambio = float(post_venta.get("cambio", 0) or 0)

    return f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>{titulo} - {html_escape(negocio)}</title>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; color: #111; }}
        .wrap {{ max-width: 800px; margin: 0 auto; }}
        h1,h2,h3,p {{ margin: 0 0 8px 0; }}
        .top {{ text-align: center; margin-bottom: 16px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ border-bottom: 1px solid #ddd; padding: 8px; font-size: 14px; }}
        th {{ background: #f7f7f7; text-align: left; }}
        .totales {{ margin-top: 18px; width: 100%; }}
        .totales td {{ border: none; padding: 6px 0; }}
        .right {{ text-align: right; }}
        .strong {{ font-weight: bold; }}
        @media print {{
          body {{ padding: 0; }}
          .no-print {{ display: none; }}
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="top">
          <h2>{html_escape(negocio)}</h2>
          <h1>{titulo}</h1>
          <p><strong>No./NCF:</strong> {ncf}</p>
          <p><strong>Fecha:</strong> {fecha_txt}</p>
          <p><strong>Cliente:</strong> {cliente}</p>
          <p><strong>Método:</strong> {metodo}</p>
        </div>

        <table>
          <thead>
            <tr>
              <th>Producto</th>
              <th>Cant.</th>
              <th>Precio</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {filas}
          </tbody>
        </table>

        <table class="totales">
          <tr><td class="strong">Total</td><td class="right strong">RD$ {total:,.2f}</td></tr>
          <tr><td class="strong">Cambio</td><td class="right">RD$ {cambio:,.2f}</td></tr>
        </table>
      </div>
    </body>
    </html>
    """


def lanzar_impresion_navegador(html_doc: str):
    """
    Abre una ventana imprimible. Si el navegador bloquea el pop-up,
    el usuario podrá imprimir desde la vista previa con el botón interno.
    """
    html_js = f"""
    <html>
    <body>
    <script>
      const contenido = {html_doc!r};
      const w = window.open('', '_blank');
      if (w) {{
        w.document.open();
        w.document.write(contenido);
        w.document.close();
        w.focus();
        setTimeout(() => {{
          w.print();
        }}, 500);
      }} else {{
        alert('El navegador bloqueó la ventana de impresión. Usa el botón Imprimir dentro de la vista previa.');
      }}
    </script>
    </body>
    </html>
    """
    components.html(html_js, height=80, width=300)

def generar_numero_factura_pos() -> str:
    """
    Genera una secuencia limpia de factura:
    00001, 00002, 00003...
    Ignora números raros anteriores que salieron de UUID/ID.
    """
    try:
        resp = supabase.table("ventas").select("numero_factura").execute()
        ventas = pd.DataFrame(resp.data or [])
    except Exception:
        ventas = DATA.get("ventas", pd.DataFrame()).copy()

    max_num = 0

    if not ventas.empty and "numero_factura" in ventas.columns:
        for val in ventas["numero_factura"].dropna().astype(str):
            txt = val.strip()
            # Solo acepta secuencias limpias de 1 a 5 dígitos.
            # Ej: 1, 01, 00001, 00025
            if re.fullmatch(r"\d{1,5}", txt):
                try:
                    max_num = max(max_num, int(txt))
                except Exception:
                    pass

    return str(max_num + 1).zfill(5)

def mostrar_factura_pos(post_venta: dict):
    """
    Muestra factura/ticket visible y descargable para cajera y admin.
    Incluye botón de impresión dentro de la vista previa para evitar bloqueo de pop-ups.
    """
    if not post_venta:
        return

    html_factura = construir_html_impresion(post_venta, "factura")
    html_ticket = construir_html_impresion(post_venta, "ticket")
    venta_ref = post_venta.get("numero_factura") or post_venta.get("venta_id") or "factura"

    st.markdown("### 🧾 Factura / Ticket")
    st.caption("Permitido para cajera y administradora. Si el navegador bloquea la impresión automática, usa el botón dentro de la vista previa.")

    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("🖨️ Imprimir factura", key=f"btn_pos_imprimir_factura_{post_venta.get('venta_id')}"):
            lanzar_impresion_navegador(html_factura)
            st.success("Factura enviada al navegador para imprimir. Si no se abrió, usa el botón dentro de la vista previa.")
    with p2:
        if st.button("🖨️ Imprimir ticket", key=f"btn_pos_imprimir_ticket_{post_venta.get('venta_id')}"):
            lanzar_impresion_navegador(html_ticket)
            st.success("Ticket enviado al navegador para imprimir. Si no se abrió, usa el botón dentro de la vista previa.")
    with p3:
        st.download_button(
            "⬇️ Descargar factura",
            data=html_factura.encode("utf-8"),
            file_name=f"factura_{venta_ref}.html",
            mime="text/html",
            key=f"descargar_factura_html_{post_venta.get('venta_id')}",
        )

    html_preview = f"""
    <html>
    <head>
      <meta charset='utf-8'>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 12px; }}
        .toolbar {{
          position: sticky;
          top: 0;
          background: #ffffff;
          padding: 10px;
          border-bottom: 1px solid #ddd;
          z-index: 999;
          text-align: center;
        }}
        .btn {{
          padding: 10px 18px;
          border: none;
          border-radius: 6px;
          background: #0f766e;
          color: white;
          font-weight: bold;
          cursor: pointer;
          margin: 4px;
        }}
        @media print {{
          .toolbar {{ display: none; }}
          body {{ padding: 0; }}
        }}
      </style>
    </head>
    <body>
      <div class='toolbar'>
        <button class='btn' onclick='window.print()'>🖨️ Imprimir esta factura</button>
        <button class='btn' onclick='document.body.style.zoom="85%"'>Ajustar vista</button>
      </div>
      {html_factura}
    </body>
    </html>
    """

    with st.expander("👁️ Ver factura antes de imprimir", expanded=True):
        components.html(html_preview, height=760, scrolling=True)
        st.info("Para imprimir: usa el botón verde dentro de la factura. También puedes descargarla y abrirla en Chrome.")



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
    "Pagos Empleados",
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
    menu_opciones = ["Dashboard", "Caja"] + [m for m in menu_base if m not in ["Dashboard", "Cierre de Caja"]]
else:
    menu_opciones = []
    if tiene_permiso("puede_vender"):
        menu_opciones += ["Caja", "POS", "Ventas"]
    if tiene_permiso("puede_ver_reportes"):
        menu_opciones += ["Clientes", "Créditos"]
    menu_opciones = list(dict.fromkeys(menu_opciones)) or ["Caja", "POS"]

menu = st.sidebar.selectbox("Menú", menu_opciones)

if st.sidebar.button("🔄 Recargar nube"):
    st.rerun()

# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Dashboard PRO")

    desde, hasta = rango_fechas_ui("dash")

    ventas_df = obtener_ventas_periodo_actualizadas(desde, hasta)
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
    total_inventario_dinero = calcular_total_dinero_inventario()

    pagos_empleados_debug = filtrar_por_fechas(leer_pagos_empleados_actualizados(), desde, hasta) if "leer_pagos_empleados_actualizados" in globals() else DATA.get("adelantos_empleados", pd.DataFrame()).copy()
    pagos_empleados_tot = suma_col(pagos_empleados_debug, "monto")

    utilidad_bruta_ventas = obtener_utilidad_bruta_periodo(ventas_df)
    utilidad_bruta_manual = st.number_input("Utilidad bruta manual / ajuste", min_value=0.0, step=1.0, key="dash_utilidad_bruta_manual")
    utilidad_bruta = float(utilidad_bruta_ventas) + float(utilidad_bruta_manual)

    utilidad_neta = utilidad_bruta - gastos_fijos - gastos_variables - empleados_fijos - empleados_variables - perdidas_tot
    dueno_65 = utilidad_neta * 0.65
    gerente_35 = utilidad_neta * 0.35

    # El retiro del dueño NO afecta al gerente ni baja la utilidad neta.
    # Solo se descuenta del 65% correspondiente al dueño.
    saldo_dueno_final = dueno_65 - retiros_tot
    saldo_gerente_final = gerente_35

    st.markdown("### 💼 Resumen general")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Ventas", f"RD$ {ventas_tot:,.2f}")
    a2.metric("Compras", f"RD$ {compras_tot:,.2f}")
    a3.metric("Pérdidas", f"RD$ {perdidas_tot:,.2f}")
    a4.metric("Total dinero en inventario", f"RD$ {total_inventario_dinero:,.2f}")

    st.markdown("### 💸 Gastos y pagos")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Gastos fijos", f"RD$ {gastos_fijos:,.2f}")
    b2.metric("Gastos variables", f"RD$ {gastos_variables:,.2f}")
    b3.metric("Empleados fijos pagados", f"RD$ {empleados_fijos:,.2f}")
    b4.metric("Empleados variables pagados", f"RD$ {empleados_variables:,.2f}")

    with st.expander("🔎 Ver pagos de empleados tomados para Dashboard", expanded=False):
        if pagos_empleados_debug.empty:
            st.info("No hay pagos de empleados en este rango.")
        else:
            st.dataframe(pagos_empleados_debug, use_container_width=True)

    st.markdown("### 📊 Utilidad y reparto")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Utilidad bruta ventas", f"RD$ {utilidad_bruta_ventas:,.2f}")
    c2.metric("Utilidad bruta total", f"RD$ {utilidad_bruta:,.2f}")
    c3.metric("Utilidad neta", f"RD$ {utilidad_neta:,.2f}")
    c4.metric("Ajuste manual utilidad", f"RD$ {utilidad_bruta_manual:,.2f}")

    st.markdown("### 👥 Reparto dueño / gerente")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("65% dueño", f"RD$ {dueno_65:,.2f}")
    d2.metric("Retiros del dueño", f"RD$ {retiros_tot:,.2f}")
    d3.metric("Saldo final dueño", f"RD$ {saldo_dueno_final:,.2f}")
    d4.metric("35% gerente", f"RD$ {saldo_gerente_final:,.2f}")

    st.caption("Los retiros del dueño solo se descuentan del 65% del dueño. No afectan el 35% del gerente.")

    st.markdown("### 📈 Gráficos")
    charts = [
        ("Ventas por mes", ventas_df, "total"),
        ("Compras por mes", compras_df, "monto"),
        ("Gastos por mes", gastos_df, "monto"),
        ("Pérdidas por mes", perdidas_df, "valor"),
    ]

    for titulo, df_chart, col_val in charts:
        if not df_chart.empty and col_val in df_chart.columns and "fecha" in df_chart.columns:
            graf = agrupar_mensual(df_chart, col_val)
            if not graf.empty:
                st.write(titulo)
                st.bar_chart(graf.set_index("mes")["valor"])

# =========================================================
# PRODUCTOS
# =========================================================

elif menu == "Productos":
    st.title("📦 Productos")
    st.caption("Catálogo maestro de productos con código, precios múltiples y control de inventario.")

    with st.expander("📥 Subir Excel / CSV de productos", expanded=False):
        st.write("Acepta columnas como producto/nombre, código, costo, precio, cantidad, fecha. No duplica productos existentes.")
        modo_carga = st.selectbox("Cómo tratar productos existentes", ["Actualizar costo/precio y sumar cantidad", "Actualizar costo/precio y reemplazar cantidad", "Solo actualizar datos sin mover cantidad"], key="prod_modo_carga")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_productos")
        if archivo is not None and st.button("Cargar productos", key="btn_cargar_productos_pro"):
            df = leer_archivo_subido(archivo)
            if "nombre" not in df.columns:
                st.error("El archivo debe traer al menos una columna nombre o producto.")
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
                    fecha_row = parsear_fecha(row.get("fecha")) or ahora_str()
                    existente = get_producto_por_codigo(codigo) if codigo else None
                    if existente is None:
                        existente = get_producto_por_nombre(nombre)
                    if existente is not None:
                        actual = obtener_existencia_producto(existente)
                        nueva_cant = actual
                        if modo_carga == "Actualizar costo/precio y sumar cantidad":
                            nueva_cant = actual + cantidad
                        elif modo_carga == "Actualizar costo/precio y reemplazar cantidad":
                            nueva_cant = cantidad
                        payload = {
                            "fecha": fecha_row,
                            "codigo": codigo or existente.get("codigo"),
                            "nombre": nombre,
                            "costo": float(costo or limpiar_numero(existente.get("costo")) or 0),
                            "precio": float(precio or limpiar_numero(existente.get("precio")) or 0),
                            "precio_descuento": float(limpiar_numero(row.get("precio_descuento")) or limpiar_numero(existente.get("precio_descuento")) or 0),
                            "precio_especial": float(limpiar_numero(row.get("precio_especial")) or limpiar_numero(existente.get("precio_especial")) or 0),
                            "activo": bool(row.get("activo", existente.get("activo", True))),
                            "usa_inventario": bool(row.get("usa_inventario", existente.get("usa_inventario", True))),
                        }
                        if modo_carga != "Solo actualizar datos sin mover cantidad":
                            payload["cantidad"] = float(nueva_cant)
                            if "stock" in existente.index:
                                payload["stock"] = float(nueva_cant)
                        actualizar("productos", existente["id"], payload)
                        prod_sync = refrescar_producto_por_id(existente["id"])
                        if prod_sync is None:
                            prod_sync = existente
                        sincronizar_producto_inventario(prod_sync, fecha_row, "Sincronizado desde carga de productos")
                    else:
                        payload = {
                            "fecha": fecha_row,
                            "codigo": codigo,
                            "nombre": nombre,
                            "costo": float(costo),
                            "precio": float(precio),
                            "precio_descuento": float(limpiar_numero(row.get("precio_descuento")) or 0),
                            "precio_especial": float(limpiar_numero(row.get("precio_especial")) or 0),
                            "cantidad": float(cantidad),
                            "activo": True if pd.isna(row.get("activo")) else bool(row.get("activo")),
                            "usa_inventario": True if pd.isna(row.get("usa_inventario")) else bool(row.get("usa_inventario")),
                        }
                        if "stock" in DATA["productos"].columns:
                            payload["stock"] = float(cantidad)
                        insertar("productos", payload)
                        prod_sync = get_producto_por_codigo(codigo) if codigo else get_producto_por_nombre(nombre)
                        if prod_sync is not None:
                            sincronizar_producto_inventario(prod_sync, fecha_row, "Sincronizado desde carga de productos")
                    procesados += 1
                st.success(f"Se procesaron {procesados} productos.")
                st.rerun()

    with st.expander("➕ Agregar / actualizar producto manual", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="prod_fecha")
            codigo = st.text_input("Código (lector o manual)", key="prod_codigo")
            nombre = st.text_input("Nombre", key="prod_nombre")
            categoria = st.text_input("Categoría", key="prod_categoria")
        with c2:
            costo = st.number_input("Costo", min_value=0.0, step=1.0, key="prod_costo")
            precio = st.number_input("Precio normal", min_value=0.0, step=1.0, key="prod_precio")
            precio_descuento = st.number_input("Precio descuento", min_value=0.0, step=1.0, key="prod_precio_desc")
            precio_especial = st.number_input("Precio especial", min_value=0.0, step=1.0, key="prod_precio_esp")
        with c3:
            usa_inventario = st.checkbox("Usa inventario", value=True, key="prod_usa_inv")
            activo = st.checkbox("Activo", value=True, key="prod_activo")
            cantidad = st.number_input("Cantidad inicial", min_value=0.0, step=1.0, key="prod_cantidad")
            observacion = st.text_area("Observación", key="prod_obs")

        if st.button("Guardar producto", key="btn_guardar_producto_pro"):
            if not limpiar_texto(nombre):
                st.error("Debes escribir el nombre del producto.")
            else:
                existente = get_producto_por_codigo(codigo) if codigo else None
                if existente is None:
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
                    "observacion": observacion,
                }
                if "stock" in DATA["productos"].columns:
                    payload["stock"] = float(cantidad) if usa_inventario else 0.0
                if existente is not None:
                    ok = actualizar("productos", existente["id"], payload)
                    if ok:
                        prod_sync = refrescar_producto_por_id(existente["id"])
                        if prod_sync is None:
                            prod_sync = existente
                        sincronizar_producto_inventario(prod_sync, fecha, "Sincronizado desde producto manual")
                        st.success("Producto actualizado sin duplicarse.")
                        st.rerun()
                else:
                    ok = insertar("productos", payload)
                    if ok:
                        prod_sync = get_producto_por_codigo(limpiar_texto(codigo)) if limpiar_texto(codigo) else get_producto_por_nombre(limpiar_texto(nombre))
                        if prod_sync is not None:
                            sincronizar_producto_inventario(prod_sync, fecha, "Sincronizado desde producto manual")
                        st.success("Producto creado.")
                        st.rerun()

    st.subheader("📋 Listado")
    df = DATA["productos"].copy()
    if not df.empty:
        txt = st.text_input("Buscar producto por nombre o código", key="buscar_prod")
        solo_activos = st.checkbox("Solo activos", value=True, key="solo_activos_prod")
        if solo_activos and "activo" in df.columns:
            df = df[df["activo"] == True]
        if txt:
            mask = df.astype(str).apply(lambda col: col.str.contains(txt, case=False, na=False)).any(axis=1)
            df = df[mask]
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "productos")
        render_crud_generico("productos", df, "🛠️ Editar / eliminar productos")
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
        render_crud_generico("inventario_actual", invent, "🛠️ Editar / eliminar inventario actual")
    else:
        st.info("No hay inventario actual registrado.")


# =========================================================
# CONTEO INVENTARIO
# =========================================================
elif menu == "Conteo Inventario":
    st.title("🧮 Conteo de Inventario")

    productos_df = DATA["productos"].copy()
    productos_lista = productos_df["nombre"].astype(str).tolist() if not productos_df.empty and "nombre" in productos_df.columns else []

    # =====================================================
    # CONTEO MANUAL
    # =====================================================
    with st.expander("✍️ Conteo manual", expanded=True):
        if not productos_lista:
            st.info("No hay productos para contar.")
        else:
            c1, c2, c3 = st.columns(3)

            with c1:
                fecha_manual = st.date_input("Fecha", value=date.today(), key="conteo_manual_fecha")
                producto_manual = st.selectbox("Producto", productos_lista, key="conteo_manual_producto")

            fila_prod_manual = get_producto_por_nombre(producto_manual) if producto_manual else None
            existencia_sistema_manual = obtener_existencia_producto(fila_prod_manual) if fila_prod_manual is not None else 0.0

            with c2:
                st.number_input(
                    "Existencia sistema",
                    min_value=0.0,
                    step=1.0,
                    value=float(existencia_sistema_manual),
                    disabled=True,
                    key="conteo_manual_existencia_sistema",
                )
                existencia_fisica_manual = st.number_input(
                    "Existencia física real",
                    min_value=0.0,
                    step=1.0,
                    value=float(existencia_sistema_manual),
                    key="conteo_manual_existencia_fisica",
                )

            diferencia_manual = float(existencia_fisica_manual) - float(existencia_sistema_manual)
            if diferencia_manual == 0:
                estado_manual = "cuadrado"
            elif diferencia_manual < 0:
                estado_manual = "faltante"
            else:
                estado_manual = "sobrante"

            with c3:
                st.metric("Diferencia", f"{diferencia_manual:,.2f}")
                st.text_input("Estado", value=estado_manual, disabled=True, key="conteo_manual_estado")
                observacion_manual = st.text_area("Observación", key="conteo_manual_obs")

            if st.button("Guardar conteo manual", key="btn_guardar_conteo_manual"):
                ok = insertar(
                    "conteo_inventario",
                    {
                        "fecha": str(fecha_manual),
                        "producto": producto_manual,
                        "existencia_sistema": float(existencia_sistema_manual),
                        "existencia_fisica": float(existencia_fisica_manual),
                        "diferencia": float(diferencia_manual),
                        "estado": estado_manual,
                        "observacion": observacion_manual,
                    },
                )
                if ok:
                    st.success("Conteo manual guardado.")
                    st.rerun()

    # =====================================================
    # CARGA MASIVA POR EXCEL / CSV
    # =====================================================
    with st.expander("📥 Subir conteo físico por Excel / CSV", expanded=False):
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
                    existencia_sistema = obtener_existencia_producto(fila_prod) if fila_prod is not None else 0.0
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
                            "existencia_sistema": float(existencia_sistema),
                            "existencia_fisica": float(existencia_fisica),
                            "diferencia": float(diferencia),
                            "estado": estado,
                            "observacion": "",
                        },
                    )
                    procesados += 1
                st.success(f"Se procesaron {procesados} filas de conteo.")
                st.rerun()

    # =====================================================
    # LISTADO + ACCIONES
    # =====================================================
    conteo = DATA["conteo_inventario"].copy()
    if not conteo.empty:
        st.subheader("📋 Conteos guardados")
        d1, d2 = rango_fechas_ui("conteo_inv")
        conteo_f = filtrar_por_fechas(conteo, d1, d2)
        estado_filtro = st.selectbox(
            "Filtrar por estado",
            ["Todos", "cuadrado", "faltante", "sobrante"],
            key="filtro_estado_conteo",
        )
        if estado_filtro != "Todos" and "estado" in conteo_f.columns:
            conteo_f = conteo_f[conteo_f["estado"].astype(str).str.lower() == estado_filtro]

        st.dataframe(conteo_f, use_container_width=True)
        descargar_archivos(conteo_f, "conteo_inventario")

        st.subheader("⚙️ Procesar faltantes y sobrantes")
        pendientes = (
            conteo_f[conteo_f["estado"].astype(str).str.lower().isin(["faltante", "sobrante"])]
            if not conteo_f.empty else pd.DataFrame()
        )

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
                if diferencia < 0 and st.button("Enviar este faltante a pérdidas", key="btn_faltante_individual"):
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
                if diferencia > 0 and st.button("Aplicar ajuste positivo", key="btn_ajuste_positivo_individual"):
                    ok2 = actualizar_stock_producto(producto, existencia_fisica, fecha_mov)
                    ok3 = upsert_inventario_actual(producto, costo, precio, existencia_fisica, fecha_mov, "Ajuste positivo por conteo")
                    if ok2 and ok3:
                        st.success("Ajuste positivo aplicado.")
                        st.rerun()

            with col3:
                if st.button("Marcar pendiente / dejar como está", key="btn_pendiente_individual"):
                    st.info("No se hizo cambio en inventario. Queda el registro para revisión.")

            faltantes_df = pendientes[pendientes["estado"].astype(str).str.lower() == "faltante"]
            if not faltantes_df.empty and st.button("Enviar TODOS los faltantes del filtro a pérdidas", key="btn_faltantes_masivo"):
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
        render_crud_generico("ajustes_inventario", df, "🛠️ Editar / eliminar ajustes de inventario")
    else:
        st.info("No hay ajustes registrados.")


# =========================================================
# VENTAS
# =========================================================
elif menu == "Ventas":
    st.title("💰 Ventas")

    puede_gestionar_ventas = (es_admin() or tiene_permiso("puede_editar_todo") or tiene_permiso("puede_editar_ventas") or tiene_permiso("puede_eliminar") or tiene_permiso("puede_anular")) and not es_cajera()
    puede_ver_utilidad = puede_ver_utilidad_global()

    if not es_cajera():
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
                            insertar(
                                "ventas",
                                {
                                    "fecha": fecha,
                                    "total": float(total),
                                    "metodo": metodo,
                                    "metodo_pago": metodo,
                                    "observacion": observacion,
                                    "usuario": nombre_usuario_actual(),
                                    "cliente_nombre": "Venta general",
                                    "anulado": False,
                                },
                            )
                            count += 1
                    st.success(f"Se cargaron {count} ventas.")
                    st.rerun()

    if not es_cajera():
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
                if insertar(
                    "ventas",
                    {
                        "fecha": str(fecha),
                        "total": float(total),
                        "metodo": metodo,
                        "metodo_pago": metodo,
                        "observacion": observacion,
                        "usuario": nombre_usuario_actual(),
                        "cliente_nombre": "Venta general",
                        "anulado": False,
                    },
                ):
                    st.success("Venta guardada.")
                    st.rerun()


    # Lectura robusta: sin filtros cerrados para no ocultar ventas registradas
    try:
        resp_v = supabase.table("ventas").select("*").order("fecha", desc=True).execute()
        df = pd.DataFrame(resp_v.data or [])
    except Exception:
        df = leer_tabla("ventas")

    if not df.empty:
        if "id" not in df.columns and "identificación" in df.columns:
            df["id"] = df["identificación"]
        if "identificacion" not in df.columns and "identificación" in df.columns:
            df["identificacion"] = df["identificación"]
        if "identificación" not in df.columns and "identificacion" in df.columns:
            df["identificación"] = df["identificacion"]
        if "metodo" not in df.columns and "metodo_pago" in df.columns:
            df["metodo"] = df["metodo_pago"]
        if "metodo_pago" not in df.columns and "metodo" in df.columns:
            df["metodo_pago"] = df["metodo"]
        if "cliente_nombre" not in df.columns:
            df["cliente_nombre"] = "Venta general"
        if "usuario" not in df.columns:
            df["usuario"] = ""
        if "anulado" not in df.columns:
            df["anulado"] = False
        if "motivo_anulacion" not in df.columns:
            df["motivo_anulacion"] = ""
        if "ganancia_bruta" not in df.columns:
            df["ganancia_bruta"] = 0.0
        if "ganancia_bruta_manual" not in df.columns:
            df["ganancia_bruta_manual"] = 0.0

        d1, d2 = rango_fechas_ui("ventas")
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df[(df["fecha"] >= pd.to_datetime(d1)) & (df["fecha"] <= pd.to_datetime(d2) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]

        txt = st.text_input("Buscar venta", key="buscar_ventas")
        metodo_filtro = st.selectbox(
            "Filtrar por método",
            ["Todos", "efectivo", "transferencia", "tarjeta", "credito", "mixto"],
            key="ventas_filtro_metodo",
        )

        if txt:
            df = buscar_df(df, txt)
        col_metodo = "metodo_pago" if "metodo_pago" in df.columns else "metodo" if "metodo" in df.columns else None
        if metodo_filtro != "Todos" and col_metodo:
            df = df[df[col_metodo].astype(str).str.lower() == metodo_filtro.lower()]

        if es_cajera():
            usuario_actual = normalizar_texto(nombre_usuario_actual())
            if "usuario" in df.columns:
                df = df[df["usuario"].astype(str).apply(normalizar_texto) == usuario_actual]
            elif "cajera" in df.columns:
                df = df[df["cajera"].astype(str).apply(normalizar_texto) == usuario_actual]
            else:
                df = df.iloc[0:0]
            st.caption("Vista cajera: solo puedes ver tus ventas. No puedes editar, eliminar, anular, descargar ni registrar ventas manuales.")

        total_vendido = float(pd.to_numeric(df.get("total", 0), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
        utilidad_visible = float(pd.to_numeric(df.get("ganancia_bruta", 0), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
        metric_cols = st.columns(3) if puede_ver_utilidad else st.columns(2)
        metric_cols[0].metric("Ventas registradas", int(len(df.index)))
        metric_cols[1].metric("Total vendido", f"RD$ {total_vendido:,.2f}")
        if puede_ver_utilidad:
            metric_cols[2].metric("Utilidad bruta visible", f"RD$ {utilidad_visible:,.2f}")

        df_show = df.copy().sort_values("fecha", ascending=False)
        if not df_show.empty:
            df_show["factura"] = df_show.apply(numero_factura_visible, axis=1)
        columnas_preferidas = [
            c
            for c in [
                "numero_factura",
                "factura",
                "id",
                "identificación",
                "fecha",
                "total",
                "subtotal",
                "descuento",
                "recargo",
                "metodo_pago",
                "metodo",
                "cliente_nombre",
                "usuario",
                "anulado",
                "motivo_anulacion",
                "ganancia_bruta",
                "ganancia_bruta_manual",
            ]
            if c in df_show.columns
        ]
        if not puede_ver_utilidad:
            columnas_preferidas = [c for c in columnas_preferidas if c not in ["ganancia_bruta", "ganancia_bruta_manual"]]
        st.dataframe(df_show[columnas_preferidas] if columnas_preferidas else df_show, use_container_width=True)
        if not es_cajera():
            descargar_archivos(df_show[columnas_preferidas] if columnas_preferidas else df_show, "ventas")

        # =========================================================
        # BLOQUE NUEVO: EDITAR VENTA COMPLETA
        # PÉGALO DEBAJO DE:
        # st.dataframe(df[columnas_preferidas] if columnas_preferidas else df, use_container_width=True)
        # descargar_archivos(df, "ventas")
        # DENTRO DEL MÓDULO: elif menu == "Ventas":
        # =========================================================

        if puede_gestionar_ventas:
            st.subheader("✏️ Editar venta completa")

            ventas_visibles = df.copy()
            if not ventas_visibles.empty:
                opciones_venta = []
                mapa_ventas = {}

                for _, row in ventas_visibles.iterrows():
                    venta_id = row.get("id") or row.get("identificación")
                    etiqueta = f"{venta_id} | {row.get('fecha')} | Total RD$ {float(limpiar_numero(row.get('total')) or 0):,.2f}"
                    opciones_venta.append(etiqueta)
                    mapa_ventas[etiqueta] = row

                venta_sel = st.selectbox("Selecciona la venta a editar", opciones_venta, key="venta_editar_sel")
                venta_row = mapa_ventas[venta_sel]
                venta_id = venta_row.get("id") or venta_row.get("identificación")

                detalle_resp = supabase.table("detalle_venta").select("*").eq("venta_id", str(venta_id)).execute()
                detalle_data = detalle_resp.data or []
                detalle_df = pd.DataFrame(detalle_data)

                if detalle_df.empty:
                    st.warning("Esta venta no tiene detalle para editar.")
                else:
                    productos_df = DATA["productos"].copy()
                    productos_lista = productos_df["nombre"].astype(str).tolist() if not productos_df.empty and "nombre" in productos_df.columns else []

                    st.write("### Detalle actual de la venta")
                    nuevos_items = []

                    for i, item in detalle_df.iterrows():
                        st.markdown(f"**Línea {i + 1}**")
                        c1, c2, c3, c4, c5, c6 = st.columns([3, 1, 1, 1, 1, 1])

                        with c1:
                            producto_actual = st.text_input(
                                f"Producto {i}",
                                value=str(item.get("producto", "")),
                                key=f"edit_producto_{i}"
                            )
                        with c2:
                            cantidad_nueva = st.number_input(
                                f"Cantidad {i}",
                                min_value=0.0,
                                step=1.0,
                                value=float(limpiar_numero(item.get("cantidad")) or 0),
                                key=f"edit_cantidad_{i}"
                            )
                        with c3:
                            precio_nuevo = st.number_input(
                                f"Precio {i}",
                                min_value=0.0,
                                step=1.0,
                                value=float(limpiar_numero(item.get("precio_unitario") or item.get("precio")) or 0),
                                key=f"edit_precio_{i}"
                            )
                        with c4:
                            costo_nuevo = st.number_input(
                                f"Costo {i}",
                                min_value=0.0,
                                step=1.0,
                                value=float(limpiar_numero(item.get("costo_unitario") or item.get("costo")) or 0),
                                key=f"edit_costo_{i}"
                            )
                        with c5:
                            descuento_nuevo = st.number_input(
                                f"Desc. {i}",
                                min_value=0.0,
                                step=1.0,
                                value=float(limpiar_numero(item.get("descuento")) or 0),
                                key=f"edit_desc_{i}"
                            )
                        with c6:
                            eliminar_linea = st.checkbox("❌", value=False, key=f"edit_eliminar_{i}")

                        if not eliminar_linea and cantidad_nueva > 0:
                            linea_total = (cantidad_nueva * precio_nuevo) - descuento_nuevo
                            ganancia_linea = (precio_nuevo - costo_nuevo) * cantidad_nueva - descuento_nuevo

                            nuevos_items.append({
                                "producto_id": item.get("producto_id"),
                                "producto": producto_actual,
                                "codigo": item.get("código") or item.get("codigo"),
                                "cantidad": float(cantidad_nueva),
                                "precio_unitario": float(precio_nuevo),
                                "costo_unitario": float(costo_nuevo),
                                "descuento": float(descuento_nuevo),
                                "recargo": float(limpiar_numero(item.get("recargo")) or 0),
                                "linea_total": float(linea_total),
                                "ganancia_linea": float(ganancia_linea),
                                "usuario": nombre_usuario_actual(),
                                "fecha": ahora_str(),
                                "anulado": False,
                                "motivo_anulacion": "",
                            })

                    st.write("### ➕ Agregar producto nuevo a esta venta")
                    if productos_lista:
                        cna1, cna2, cna3 = st.columns(3)
                        with cna1:
                            prod_nuevo_nombre = st.selectbox("Producto nuevo", [""] + productos_lista, key="venta_nuevo_producto")
                        with cna2:
                            prod_nueva_cantidad = st.number_input("Cantidad nueva", min_value=0.0, step=1.0, value=0.0, key="venta_nueva_cantidad")
                        with cna3:
                            agregar_nuevo = st.checkbox("Agregar a la venta", key="venta_agregar_nuevo")

                        if agregar_nuevo and prod_nuevo_nombre and prod_nueva_cantidad > 0:
                            prod_row = get_producto_por_nombre(prod_nuevo_nombre)
                            if prod_row is not None:
                                precio_nuevo = float(limpiar_numero(prod_row.get("precio")) or 0)
                                costo_nuevo = float(limpiar_numero(prod_row.get("costo")) or 0)
                                linea_total = prod_nueva_cantidad * precio_nuevo
                                ganancia_linea = (precio_nuevo - costo_nuevo) * prod_nueva_cantidad

                                nuevos_items.append({
                                    "producto_id": prod_row.get("id"),
                                    "producto": prod_nuevo_nombre,
                                    "codigo": prod_row.get("codigo"),
                                    "cantidad": float(prod_nueva_cantidad),
                                    "precio_unitario": float(precio_nuevo),
                                    "costo_unitario": float(costo_nuevo),
                                    "descuento": 0.0,
                                    "recargo": 0.0,
                                    "linea_total": float(linea_total),
                                    "ganancia_linea": float(ganancia_linea),
                                    "usuario": nombre_usuario_actual(),
                                    "fecha": ahora_str(),
                                    "anulado": False,
                                    "motivo_anulacion": "",
                                })

                    st.write("### Método de pago")
                    metodo_pago_nuevo = st.selectbox(
                        "Método de pago nuevo",
                        ["efectivo", "transferencia", "tarjeta", "credito", "mixto"],
                        index=["efectivo", "transferencia", "tarjeta", "credito", "mixto"].index(
                            str(venta_row.get("metodo_pago") or "efectivo").lower()
                        ) if str(venta_row.get("metodo_pago") or "efectivo").lower() in ["efectivo", "transferencia", "tarjeta", "credito", "mixto"] else 0,
                        key="venta_edit_metodo_pago"
                    )

                    if st.button("💾 Guardar edición completa", key="btn_guardar_edicion_completa"):
                        try:
                            detalle_original = detalle_df.to_dict("records")

                            # 1. devolver inventario viejo
                            for item in detalle_original:
                                prod_id = item.get("producto_id")
                                cant_old = float(limpiar_numero(item.get("cantidad")) or 0)
                                if prod_id:
                                    prod_match = productos_df[productos_df["id"].astype(str) == str(prod_id)] if not productos_df.empty and "id" in productos_df.columns else pd.DataFrame()
                                    if not prod_match.empty:
                                        prod_row = prod_match.iloc[0]
                                        stock_actual = obtener_existencia_producto(prod_row)
                                        actualizar_existencia_producto(prod_row, stock_actual + cant_old)

                            # 2. borrar detalle viejo
                            supabase.table("detalle_venta").delete().eq("venta_id", str(venta_id)).execute()

                            # 3. insertar detalle nuevo y descontar inventario nuevo
                            nuevo_total = 0.0
                            nueva_ganancia = 0.0

                            for item in nuevos_items:
                                item_insert = item.copy()
                                item_insert["venta_id"] = str(venta_id)
                                supabase.table("detalle_venta").insert(item_insert).execute()

                                prod_id = item.get("producto_id")
                                cant_new = float(item.get("cantidad") or 0)
                                nuevo_total += float(item.get("linea_total") or 0)
                                nueva_ganancia += float(item.get("ganancia_linea") or 0)

                                if prod_id:
                                    prod_match = productos_df[productos_df["id"].astype(str) == str(prod_id)] if not productos_df.empty and "id" in productos_df.columns else pd.DataFrame()
                                    if not prod_match.empty:
                                        prod_row = prod_match.iloc[0]
                                        stock_actual = obtener_existencia_producto(prod_row)
                                        actualizar_existencia_producto(prod_row, stock_actual - cant_new)

                            # 4. actualizar venta
                            supabase.table("ventas").update({
                                "total": float(nuevo_total),
                                "subtotal": float(nuevo_total),
                                "metodo_pago": metodo_pago_nuevo,
                                "ganancia_bruta": float(nueva_ganancia),
                            }).eq("id", str(venta_id)).execute()

                            # 5. actualizar pagos si existe registro
                            try:
                                supabase.table("ventas_pagos").update({
                                    "metodo_pago": metodo_pago_nuevo,
                                    "monto": float(nuevo_total),
                                }).eq("venta_id", str(venta_id)).execute()
                            except Exception:
                                pass

                            st.success("Venta editada completamente.")
                            st.rerun()

                        except Exception as exc:
                            st.error(f"No se pudo guardar la edición completa: {exc}")



        if puede_gestionar_ventas:
            with st.expander("🛠️ Editar / eliminar ventas", expanded=False):
                opciones = []
                mapa_ids = {}
                for _, row in df_show.iterrows():
                    row_id = row.get("id") or row.get("identificación")
                    etiqueta = f"{row_id} | {row.get('fecha')} | RD$ {float(limpiar_numero(row.get('total')) or 0):,.2f} | {row.get('metodo_pago') or row.get('metodo') or ''}"
                    opciones.append(etiqueta)
                    mapa_ids[etiqueta] = row
                if opciones:
                    venta_sel = st.selectbox("Selecciona una venta", opciones, key="ventas_sel_edit")
                    venta_row = mapa_ids[venta_sel]
                    venta_id = venta_row.get("id") or venta_row.get("identificación")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        fecha_edit = st.date_input("Fecha edición", value=pd.to_datetime(venta_row.get("fecha")).date() if pd.notna(pd.to_datetime(venta_row.get("fecha"), errors="coerce")) else date.today(), key="venta_edit_fecha")
                    with ce2:
                        total_edit = st.number_input("Total edición", min_value=0.0, step=1.0, value=float(limpiar_numero(venta_row.get("total")) or 0), key="venta_edit_total")
                    with ce3:
                        metodo_edit = st.selectbox("Método edición", ["efectivo", "transferencia", "tarjeta", "credito", "mixto"], index=["efectivo", "transferencia", "tarjeta", "credito", "mixto"].index(str((venta_row.get("metodo_pago") or venta_row.get("metodo") or "efectivo")).lower()) if str((venta_row.get("metodo_pago") or venta_row.get("metodo") or "efectivo")).lower() in ["efectivo", "transferencia", "tarjeta", "credito", "mixto"] else 0, key="venta_edit_metodo")
                    obs_edit = st.text_input("Observación edición", value=limpiar_texto(venta_row.get("observacion")), key="venta_edit_obs")
                    cl1, cl2, cl3 = st.columns(3)
                    with cl1:
                        if (es_admin() or tiene_permiso("puede_editar_ventas")) and st.button("💾 Guardar cambios", key="btn_guardar_cambios_venta"):
                            ok = actualizar("ventas", venta_id, {
                                "fecha": str(fecha_edit),
                                "total": float(total_edit),
                                "metodo": metodo_edit,
                                "metodo_pago": metodo_edit,
                                "observacion": obs_edit,
                            })
                            if ok:
                                st.success("Venta actualizada.")
                                st.rerun()
                    with cl2:
                        if (es_admin() or tiene_permiso("puede_anular")) and st.button("🚫 Anular venta", key="btn_anular_venta_admin"):
                            ok = anular_venta_completa_app(venta_id, "Anulada manualmente desde módulo Ventas")
                            if ok:
                                st.success("Venta anulada.")
                                st.rerun()
                    with cl3:
                        if (es_admin() or tiene_permiso("puede_eliminar")) and st.button("🗑️ Eliminar venta", key="btn_eliminar_venta_admin"):
                            ok = eliminar_venta_completa_app(venta_id)
                            if ok:
                                st.success("Venta eliminada.")
                                st.rerun()
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
            c1, c2 = st.columns(2)
            with c1:
                nuevo_codigo = st.text_input("Código nuevo", key="comp_nuevo_codigo")
                nuevo_nombre = st.text_input("Nombre producto nuevo", key="comp_nuevo_nombre")
            with c2:
                nuevo_precio = st.number_input("Precio de venta sugerido", min_value=0.0, step=1.0, key="comp_nuevo_precio")
                nuevo_categoria = st.text_input("Categoría", key="comp_nuevo_categoria")
        else:
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
        render_crud_generico("compras", df, "🛠️ Editar / eliminar compras")
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
        render_crud_generico("catalogo_gastos", df, "🛠️ Editar / eliminar catálogo de gastos")
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
        render_crud_generico("gastos", df, "🛠️ Editar / eliminar gastos")
    else:
        st.info("No hay gastos registrados.")


# =========================================================
# EMPLEADOS
# =========================================================
elif menu == "Empleados":
    st.title("👥 Empleados")
    st.caption("Este módulo es solo para registrar datos del empleado. Para pagar quincenas, comisiones o bonos usa el menú Pagos Empleados.")

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
            metodo_pago = st.selectbox("Método de pago", ["", "efectivo", "transferencia", "tarjeta"], key="emp_metodo_pago")
        with c2:
            tipo_salario = st.selectbox("Tipo salario", ["fijo", "variable"], key="emp_tipo_salario")
            frecuencia_pago = st.selectbox("Frecuencia pago", ["mensual", "quincenal", "semanal"], key="emp_frec")
            dia_pago_1 = st.number_input("Día pago 1", min_value=0.0, step=1.0, value=0.0, key="emp_dia_pago_1")
            dia_pago_2 = st.number_input("Día pago 2", min_value=0.0, step=1.0, value=0.0, key="emp_dia_pago_2")
            activo = st.checkbox("Activo", value=True, key="emp_activo")
            observacion = st.text_area("Observación", key="emp_obs")

        if st.button("Guardar empleado"):
            payload_empleado = {
                "fecha": str(fecha),
                "nombre": nombre,
                "puesto": puesto,
                "sueldo": float(sueldo),
                "tipo_salario": tipo_salario,
                "frecuencia_pago": frecuencia_pago,
                "metodo_pago": metodo_pago or None,
                "dia_pago_1": None if float(dia_pago_1) == 0 else float(dia_pago_1),
                "dia_pago_2": None if float(dia_pago_2) == 0 else float(dia_pago_2),
                "activo": activo,
                "observacion": observacion,
            }
            if insertar("empleados", payload_empleado):
                st.success("Empleado guardado.")
                st.rerun()

    df = DATA["empleados"].copy()
    if not df.empty:
        txt = st.text_input("Buscar empleado", key="buscar_emp")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "empleados")
        render_crud_generico("empleados", df, "🛠️ Editar / eliminar empleados")
    else:
        st.info("No hay empleados registrados.")


# =========================================================
# ADELANTOS EMPLEADOS
# =========================================================
elif menu == "Pagos Empleados":
    st.title("💵 Pagos a Empleados")
    st.caption("Aquí es donde se aplica el pago real. El módulo Empleados solo guarda los datos del empleado y su sueldo acordado.")

    empleados_df = DATA.get("empleados", pd.DataFrame()).copy()
    nombres_empleados = empleados_df["nombre"].astype(str).tolist() if not empleados_df.empty and "nombre" in empleados_df.columns else []
    columnas_pagos = DATA["adelantos_empleados"].columns.tolist() if not DATA["adelantos_empleados"].empty else []

    with st.expander("➕ Aplicar pago a empleado", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            fecha_pago = st.date_input("Fecha de pago", value=date.today(), key="pago_emp_fecha")
            empleado = st.selectbox("Empleado", nombres_empleados, key="pago_emp_nombre") if nombres_empleados else st.text_input("Empleado", key="pago_emp_nombre_txt")

        with c2:
            tipo_pago = st.selectbox(
                "Tipo de pago",
                ["quincena", "salario", "comisión", "bono", "adelanto", "otro"],
                key="pago_emp_tipo"
            )
            monto_pago = st.number_input("Monto pagado", min_value=0.0, step=1.0, key="pago_emp_monto")

        with c3:
            metodo_pago = st.selectbox(
                "Método de pago",
                ["efectivo", "transferencia", "tarjeta"],
                key="pago_emp_metodo"
            )
            observacion_pago = st.text_area("Observación", key="pago_emp_obs")

        if st.button("Guardar pago de empleado", key="btn_guardar_pago_empleado_real"):
            if not limpiar_texto(empleado):
                st.error("Debes seleccionar o escribir el empleado.")
            elif monto_pago <= 0:
                st.error("El monto pagado debe ser mayor que cero.")
            else:
                detalle_final = f"tipo_pago: {tipo_pago} | metodo_pago: {metodo_pago}"
                if observacion_pago:
                    detalle_final += f" | {observacion_pago}"

                payload_pago = {
                    "fecha": str(fecha_pago),
                    "empleado": empleado,
                    "monto": float(monto_pago),
                    "detalle": detalle_final,
                }

                if "tipo_pago" in columnas_pagos:
                    payload_pago["tipo_pago"] = tipo_pago
                if "metodo_pago" in columnas_pagos:
                    payload_pago["metodo_pago"] = metodo_pago
                if "concepto" in columnas_pagos:
                    payload_pago["concepto"] = tipo_pago

                if insertar("adelantos_empleados", payload_pago):
                    st.success("Pago aplicado correctamente. Ya debe reflejarse en el Dashboard.")
                    st.rerun()

    st.subheader("📋 Historial de pagos aplicados")
    df = DATA["adelantos_empleados"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("pagos_empleados")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar pago", key="buscar_pagos_empleados")
        df = buscar_df(df, txt)

        total_pagos = suma_col(df, "monto")
        st.metric("Total pagado en el período", f"RD$ {total_pagos:,.2f}")

        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "pagos_empleados")
        render_crud_generico("adelantos_empleados", df, "🛠️ Editar / eliminar pagos aplicados")
    else:
        st.info("No hay pagos registrados todavía.")



# =========================================================
# PÉRDIDAS
# =========================================================
elif menu == "Pérdidas":
    st.title("📉 Pérdidas")
    st.caption("Puedes guardar la pérdida sola o guardarla y descontarla del inventario. Si la guardaste sola, luego puedes aplicarla al inventario desde el historial.")

    productos_lista = DATA["productos"]["nombre"].astype(str).tolist() if not DATA["productos"].empty and "nombre" in DATA["productos"].columns else []

    with st.expander("➕ Registrar pérdida de mercancía", expanded=True):
        c1, c2 = st.columns(2)

        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="perd_fecha")
            producto = st.selectbox("Producto", productos_lista, key="perd_prod") if productos_lista else st.text_input("Producto", key="perd_prod_txt")
            existencia_actual = obtener_existencia_desde_inventario(producto) if producto else 0.0
            st.number_input(
                "Existencia actual en inventario",
                value=float(existencia_actual),
                step=1.0,
                disabled=True,
                key=f"perd_existencia_actual_{normalizar_texto(producto)}"
            )
            cantidad = st.number_input("Cantidad perdida", min_value=0.0, step=1.0, key="perd_cant")

        with c2:
            costo_auto = obtener_costo_desde_inventario(producto) if producto else 0.0
            costo_unitario = st.number_input(
                "Costo unitario según inventario",
                min_value=0.0,
                step=1.0,
                value=float(costo_auto),
                key=f"perd_costo_auto_{normalizar_texto(producto)}"
            )
            if costo_auto <= 0:
                st.warning("No encontré costo para este producto en Inventario Actual ni en Productos. Revisa que el costo esté guardado.")

            tipo_perdida = st.selectbox("Tipo de pérdida", ["mercancia", "vencimiento", "rotura", "ajuste_mercancia", "otro"], key="perd_tipo")
            valor_perdida = float(cantidad) * float(costo_unitario)
            st.metric("Valor de la pérdida", f"RD$ {valor_perdida:,.2f}")
            observacion = st.text_area("Observación", key="perd_obs")

        nueva_existencia = max(float(existencia_actual) - float(cantidad), 0.0)
        st.info(f"Si aplicas al inventario, la existencia bajará de {existencia_actual:,.0f} a {nueva_existencia:,.0f}.")

        b1, b2 = st.columns(2)

        with b1:
            if st.button("💾 Guardar pérdida solamente", key="btn_guardar_perdida_sola"):
                if not limpiar_texto(producto):
                    st.error("Debes seleccionar un producto.")
                elif cantidad <= 0:
                    st.error("La cantidad perdida debe ser mayor que cero.")
                elif costo_unitario <= 0:
                    st.error("El costo unitario no puede ser cero. Revisa el costo en Inventario Actual o Productos.")
                else:
                    obs_final = (observacion or "") + " | Pendiente de descontar inventario"
                    if registrar_perdida(fecha, producto, cantidad, costo_unitario, tipo_perdida, obs_final):
                        st.success("Pérdida guardada. Queda pendiente de descontar inventario.")
                        st.rerun()

        with b2:
            if st.button("📉 Guardar pérdida y descontar inventario", key="btn_guardar_perdida_descontar"):
                if not limpiar_texto(producto):
                    st.error("Debes seleccionar un producto.")
                elif cantidad <= 0:
                    st.error("La cantidad perdida debe ser mayor que cero.")
                elif costo_unitario <= 0:
                    st.error("El costo unitario no puede ser cero. Revisa el costo en Inventario Actual o Productos.")
                elif cantidad > existencia_actual:
                    st.error("La cantidad perdida no puede ser mayor que la existencia actual.")
                else:
                    obs_final = (observacion or "") + f" | Inventario descontado. Cantidad perdida: {cantidad}"
                    ok_perdida = registrar_perdida(fecha, producto, cantidad, costo_unitario, tipo_perdida, obs_final)

                    fila_prod = get_producto_por_nombre(producto)
                    costo = float(costo_unitario)
                    precio = float(limpiar_numero(fila_prod.get("precio")) or 0) if fila_prod is not None else 0.0

                    ok_stock = True
                    ok_inv = True
                    if fila_prod is not None:
                        ok_stock = actualizar_stock_producto(producto, nueva_existencia, fecha)
                        ok_inv = upsert_inventario_actual(
                            producto,
                            costo,
                            precio,
                            nueva_existencia,
                            fecha,
                            f"Descontado por pérdida de mercancía. Cantidad perdida: {cantidad}"
                        )

                    if ok_perdida and ok_stock and ok_inv:
                        st.success("Pérdida guardada y descontada del inventario correctamente.")
                        st.rerun()

    df = DATA["perdidas"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("perdidas")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar pérdida", key="buscar_perd")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "perdidas")

        st.subheader("📉 Descontar del inventario una pérdida ya guardada")
        pendientes = df.copy()
        if "observacion" in pendientes.columns:
            obs_norm = pendientes["observacion"].astype(str).apply(normalizar_texto)
            pendientes = pendientes[~obs_norm.str.contains("inventario descontado", na=False)]

        if pendientes.empty:
            st.info("No hay pérdidas pendientes de descontar en el inventario dentro del filtro seleccionado.")
        else:
            opciones = []
            mapa_perdidas = {}
            for _, r in pendientes.iterrows():
                perdida_id = r.get("id") or r.get("identificación") or r.get("identificacion")
                prod = r.get("producto", "")
                cant = float(limpiar_numero(r.get("cantidad")) or 0)
                costo = float(limpiar_numero(r.get("costo_unitario")) or limpiar_numero(r.get("costo")) or 0)
                fecha_r = r.get("fecha", "")
                etiqueta = f"{perdida_id} | {prod} | cant: {cant:,.0f} | costo: {costo:,.2f} | fecha: {fecha_r}"
                opciones.append(etiqueta)
                mapa_perdidas[etiqueta] = r

            sel_perdida = st.selectbox("Selecciona pérdida pendiente", opciones, key="perdida_pendiente_descuento")
            fila_p = mapa_perdidas[sel_perdida]

            perdida_id = fila_p.get("id") or fila_p.get("identificación") or fila_p.get("identificacion")
            producto_p = limpiar_texto(fila_p.get("producto"))
            cantidad_p = float(limpiar_numero(fila_p.get("cantidad")) or 0)
            costo_p = float(limpiar_numero(fila_p.get("costo_unitario")) or limpiar_numero(fila_p.get("costo")) or obtener_costo_desde_inventario(producto_p) or 0)
            existencia_p = obtener_existencia_desde_inventario(producto_p)
            nueva_existencia_p = max(float(existencia_p) - float(cantidad_p), 0.0)

            cpa, cpb, cpc = st.columns(3)
            cpa.metric("Existencia actual", f"{existencia_p:,.0f}")
            cpb.metric("Cantidad a descontar", f"{cantidad_p:,.0f}")
            cpc.metric("Nueva existencia", f"{nueva_existencia_p:,.0f}")

            if st.button("📉 Aplicar descuento al inventario", key="btn_aplicar_descuento_perdida_pendiente"):
                if cantidad_p <= 0:
                    st.error("La pérdida seleccionada no tiene cantidad válida.")
                elif cantidad_p > existencia_p:
                    st.error("La cantidad perdida no puede ser mayor que la existencia actual.")
                else:
                    fila_prod = get_producto_por_nombre(producto_p)
                    precio = float(limpiar_numero(fila_prod.get("precio")) or 0) if fila_prod is not None else 0.0

                    ok_stock = True
                    ok_inv = True
                    if fila_prod is not None:
                        ok_stock = actualizar_stock_producto(producto_p, nueva_existencia_p, date.today())
                        ok_inv = upsert_inventario_actual(
                            producto_p,
                            costo_p,
                            precio,
                            nueva_existencia_p,
                            date.today(),
                            f"Descontado desde pérdida ya guardada. Pérdida ID: {perdida_id}"
                        )

                    ok_update = True
                    if perdida_id:
                        obs_anterior = limpiar_texto(fila_p.get("observacion"))
                        obs_nueva = (obs_anterior + " | " if obs_anterior else "") + "Inventario descontado"
                        ok_update = actualizar("perdidas", perdida_id, {"observacion": obs_nueva})

                    if ok_stock and ok_inv and ok_update:
                        st.success("Pérdida aplicada al inventario correctamente.")
                        st.rerun()

        render_crud_generico("perdidas", df, "🛠️ Editar / eliminar pérdidas")
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
        render_crud_generico("gastos_dueno", df, "🛠️ Editar / eliminar gastos del dueño")
    else:
        st.info("No hay gastos del dueño registrados.")


# =========================================================
# CIERRE DE CAJA
# =========================================================
elif menu == "Caja":
    st.title("💵 Caja PRO")
    st.caption("La cajera abre caja con fondo inicial. Al cerrar, solo coloca el efectivo contado; el sistema calcula todo lo demás.")

    usuario_act = nombre_usuario_actual() if "nombre_usuario_actual" in globals() else usuario_sesion().get("usuario", "")
    hoy = date.today()

    def _leer_cajas():
        try:
            resp = supabase.table("caja").select("*").order("fecha_apertura", desc=True).execute()
            return pd.DataFrame(resp.data or [])
        except Exception:
            return DATA.get("caja", pd.DataFrame()).copy()

    def _leer_ventas_pagos_actualizadas():
        try:
            resp = supabase.table("ventas_pagos").select("*").execute()
            return pd.DataFrame(resp.data or [])
        except Exception:
            return DATA.get("ventas_pagos", pd.DataFrame()).copy()

    def _leer_ventas_actualizadas():
        try:
            resp = supabase.table("ventas").select("*").execute()
            df = pd.DataFrame(resp.data or [])
            if not df.empty:
                df = aplicar_total_contable_df(df) if "aplicar_total_contable_df" in globals() else df
            return df
        except Exception:
            ventas = DATA.get("ventas", pd.DataFrame()).copy()
            return aplicar_total_contable_df(ventas) if "aplicar_total_contable_df" in globals() else ventas

    def _obtener_caja_abierta_usuario(usuario_nombre=None):
        usuario_nombre = usuario_nombre or usuario_act
        try:
            resp = (
                supabase.table("caja")
                .select("*")
                .eq("estado", "abierta")
                .eq("usuario", usuario_nombre)
                .order("fecha_apertura", desc=True)
                .limit(1)
                .execute()
            )
            data = resp.data or []
            return data[0] if data else None
        except Exception:
            cajas = _leer_cajas()
            if cajas.empty:
                return None
            if "estado" in cajas.columns:
                cajas = cajas[cajas["estado"].astype(str).apply(normalizar_texto) == "abierta"]
            if "usuario" in cajas.columns:
                cajas = cajas[cajas["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_nombre)]
            if cajas.empty:
                return None
            return cajas.iloc[0].to_dict()

    def _ventas_de_caja(caja):
        ventas = _leer_ventas_actualizadas()
        if ventas.empty:
            return ventas

        caja_id = caja.get("id")
        fecha_apertura = caja.get("fecha_apertura")
        fecha_cierre = caja.get("fecha_cierre")
        usuario_caja = caja.get("usuario") or usuario_act

        # 1) Si la venta tiene caja_id, esa es la fuente principal
        if "caja_id" in ventas.columns and caja_id:
            ventas_caja = ventas[ventas["caja_id"].astype(str) == str(caja_id)].copy()
            if not ventas_caja.empty:
                return ventas_caja

        # 2) Respaldo para ventas viejas sin caja_id: usuario + rango apertura/cierre
        if "fecha" in ventas.columns and fecha_apertura:
            ventas["_fecha_dt"] = pd.to_datetime(ventas["fecha"], errors="coerce")
            apertura_dt = pd.to_datetime(fecha_apertura, errors="coerce")
            ventas = ventas[ventas["_fecha_dt"] >= apertura_dt]
            if fecha_cierre:
                cierre_dt = pd.to_datetime(fecha_cierre, errors="coerce")
                ventas = ventas[ventas["_fecha_dt"] <= cierre_dt]

        if "usuario" in ventas.columns:
            ventas = ventas[ventas["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_caja)]

        return ventas

    def _pagos_de_caja(caja, ventas_caja=None):
        pagos = _leer_ventas_pagos_actualizadas()
        if pagos.empty:
            return pagos

        caja_id = caja.get("id")
        fecha_apertura = caja.get("fecha_apertura")
        fecha_cierre = caja.get("fecha_cierre")
        usuario_caja = caja.get("usuario") or usuario_act

        # 1) Si pagos tiene caja_id, usarlo
        if "caja_id" in pagos.columns and caja_id:
            pagos_caja = pagos[pagos["caja_id"].astype(str) == str(caja_id)].copy()
            if not pagos_caja.empty:
                return pagos_caja

        # 2) Si pagos tiene venta_id, cruzar con ventas de esa caja
        if ventas_caja is not None and not ventas_caja.empty and "venta_id" in pagos.columns:
            venta_ids = set()
            for col in ["id", "identificación", "identificacion"]:
                if col in ventas_caja.columns:
                    venta_ids.update(ventas_caja[col].dropna().astype(str).tolist())
            if venta_ids:
                pagos_match = pagos[pagos["venta_id"].astype(str).isin(venta_ids)].copy()
                if not pagos_match.empty:
                    return pagos_match

        # 3) Respaldo por usuario y rango de fechas
        if "usuario" in pagos.columns:
            pagos = pagos[pagos["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_caja)]

        if "fecha" in pagos.columns and fecha_apertura:
            pagos["_fecha_dt"] = pd.to_datetime(pagos["fecha"], errors="coerce")
            apertura_dt = pd.to_datetime(fecha_apertura, errors="coerce")
            pagos = pagos[pagos["_fecha_dt"] >= apertura_dt]
            if fecha_cierre:
                cierre_dt = pd.to_datetime(fecha_cierre, errors="coerce")
                pagos = pagos[pagos["_fecha_dt"] <= cierre_dt]

        return pagos

    def _sumar_pago_metodo(pagos, metodo_buscar):
        if pagos.empty:
            return 0.0
        metodo_col = "metodo" if "metodo" in pagos.columns else ("metodo_pago" if "metodo_pago" in pagos.columns else None)
        if not metodo_col or "monto" not in pagos.columns:
            return 0.0
        temp = pagos[pagos[metodo_col].astype(str).apply(normalizar_texto) == metodo_buscar]
        return float(pd.to_numeric(temp["monto"], errors="coerce").fillna(0).sum())

    def _sumar_ventas_por_metodo_respaldo(ventas_caja, metodo_buscar):
        if ventas_caja.empty:
            return 0.0
        metodo_col = "metodo_pago" if "metodo_pago" in ventas_caja.columns else ("metodo" if "metodo" in ventas_caja.columns else None)
        total_col = "total_contable" if "total_contable" in ventas_caja.columns else "total"
        if not metodo_col or total_col not in ventas_caja.columns:
            return 0.0
        temp = ventas_caja[ventas_caja[metodo_col].astype(str).apply(normalizar_texto) == metodo_buscar]
        return float(pd.to_numeric(temp[total_col], errors="coerce").fillna(0).sum())

    def _calcular_resumen_caja(caja):
        ventas_caja = _ventas_de_caja(caja)
        pagos_caja = _pagos_de_caja(caja, ventas_caja)
        pagos_caja = ajustar_pagos_sin_recargo_tarjeta(pagos_caja, ventas_caja)

        fondo_inicial = float(limpiar_numero(caja.get("monto_inicial")) or 0)

        # Fuente principal: ventas_pagos, porque separa los pagos mixtos
        venta_efectivo = _sumar_pago_metodo(pagos_caja, "efectivo")
        venta_transferencia = _sumar_pago_metodo(pagos_caja, "transferencia")
        venta_tarjeta = _sumar_pago_metodo(pagos_caja, "tarjeta")
        venta_credito = _sumar_pago_metodo(pagos_caja, "credito")

        # Respaldo por ventas para cuando ventas_pagos esté incompleto
        if venta_efectivo == 0:
            venta_efectivo = _sumar_ventas_por_metodo_respaldo(ventas_caja, "efectivo")
        if venta_transferencia == 0:
            venta_transferencia = _sumar_ventas_por_metodo_respaldo(ventas_caja, "transferencia")
        if venta_tarjeta == 0:
            venta_tarjeta = _sumar_ventas_por_metodo_respaldo(ventas_caja, "tarjeta")
        if venta_credito == 0:
            venta_credito = _sumar_ventas_por_metodo_respaldo(ventas_caja, "credito")

        total_col = "total_contable" if "total_contable" in ventas_caja.columns else "total"
        total_ventas = suma_col(ventas_caja, total_col) if not ventas_caja.empty else (venta_efectivo + venta_transferencia + venta_tarjeta + venta_credito)

        efectivo_esperado = fondo_inicial + venta_efectivo

        return {
            "ventas_df": ventas_caja,
            "pagos_df": pagos_caja,
            "fondo_inicial": fondo_inicial,
            "venta_efectivo": venta_efectivo,
            "venta_transferencia": venta_transferencia,
            "venta_tarjeta": venta_tarjeta,
            "venta_credito": venta_credito,
            "total_ventas": total_ventas,
            "efectivo_esperado": efectivo_esperado,
        }

    def _cerrar_caja(caja, efectivo_contado, obs_cierre, usuario_cierre=None):
        usuario_cierre = usuario_cierre or usuario_act
        resumen = _calcular_resumen_caja(caja)

        diferencia = float(efectivo_contado) - float(resumen["efectivo_esperado"])
        faltante = abs(diferencia) if diferencia < 0 else 0.0
        sobrante = diferencia if diferencia > 0 else 0.0

        cierre_payload = {
            "fecha_cierre": datetime.now().isoformat(),
            "estado": "cerrada",
            "efectivo_contado": float(efectivo_contado),
            "efectivo_esperado": float(resumen["efectivo_esperado"]),
            "total_efectivo": float(resumen["venta_efectivo"]),
            "total_transferencia": float(resumen["venta_transferencia"]),
            "total_tarjeta": float(resumen["venta_tarjeta"]),
            "total_credito": float(resumen["venta_credito"]),
            "total_ventas": float(resumen["total_ventas"]),
            "faltante": float(faltante),
            "sobrante": float(sobrante),
            "diferencia": float(diferencia),
            "observacion": obs_cierre,
        }

        ok_update = actualizar("caja", caja.get("id"), cierre_payload)

        cierre_reg = {
            "caja_id": str(caja.get("id")),
            "usuario": caja.get("usuario") or usuario_cierre,
            "usuario_id": str(caja.get("usuario_id") or usuario_sesion().get("id", "")),
            "fecha": datetime.now().isoformat(),
            "monto_inicial": float(resumen["fondo_inicial"]),
            "efectivo_contado": float(efectivo_contado),
            "efectivo_esperado": float(resumen["efectivo_esperado"]),
            "total_efectivo": float(resumen["venta_efectivo"]),
            "total_transferencia": float(resumen["venta_transferencia"]),
            "total_tarjeta": float(resumen["venta_tarjeta"]),
            "total_credito": float(resumen["venta_credito"]),
            "total_ventas": float(resumen["total_ventas"]),
            "faltante": float(faltante),
            "sobrante": float(sobrante),
            "diferencia": float(diferencia),
            "observacion": obs_cierre,
        }
        insertar("cierre_caja", cierre_reg)
        return ok_update

    def _tabla_cajas_limpia(cajas_df):
        if cajas_df.empty:
            return cajas_df
        out = cajas_df.copy()
        columnas = [c for c in [
            "usuario", "fecha_apertura", "fecha_cierre", "estado", "monto_inicial",
            "efectivo_esperado", "efectivo_contado", "diferencia", "faltante", "sobrante",
            "total_ventas", "total_efectivo", "total_transferencia", "total_tarjeta", "total_credito", "observacion"
        ] if c in out.columns]
        out = out[columnas].copy()
        nombres = {
            "usuario": "Usuario",
            "fecha_apertura": "Apertura",
            "fecha_cierre": "Cierre",
            "estado": "Estado",
            "monto_inicial": "Caja inicial",
            "efectivo_esperado": "Efectivo esperado",
            "efectivo_contado": "Efectivo contado",
            "diferencia": "Diferencia",
            "faltante": "Faltante",
            "sobrante": "Sobrante",
            "total_ventas": "Total ventas",
            "total_efectivo": "Ventas efectivo",
            "total_transferencia": "Transferencia",
            "total_tarjeta": "Tarjeta",
            "total_credito": "Crédito",
            "observacion": "Observación",
        }
        return out.rename(columns=nombres)

    def _html_cuadre_caja(caja, resumen, efectivo_contado=None):
        efectivo_contado = resumen["efectivo_esperado"] if efectivo_contado is None else float(efectivo_contado)
        diferencia = efectivo_contado - resumen["efectivo_esperado"]
        faltante = abs(diferencia) if diferencia < 0 else 0
        sobrante = diferencia if diferencia > 0 else 0
        negocio = obtener_configuracion().get("negocio_nombre") or "Sistema de Negocio PRO"
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 18px; color: #111; }}
                .box {{ max-width: 520px; margin: 0 auto; border: 1px solid #ddd; padding: 18px; }}
                h2, h3 {{ text-align:center; margin: 4px 0; }}
                table {{ width:100%; border-collapse: collapse; margin-top: 14px; }}
                td {{ padding: 7px; border-bottom:1px solid #eee; }}
                td:last-child {{ text-align:right; font-weight:bold; }}
                .print {{ text-align:center; margin-bottom: 12px; }}
                button {{ padding:10px 16px; font-weight:bold; }}
                @media print {{ .print {{ display:none; }} .box {{ border:none; }} }}
            </style>
        </head>
        <body>
            <div class="print"><button onclick="window.print()">🖨️ Imprimir cuadre de caja</button></div>
            <div class="box">
                <h2>{negocio}</h2>
                <h3>CUADRE DE CAJA</h3>
                <p><b>Usuario:</b> {caja.get("usuario","")}<br>
                <b>Apertura:</b> {caja.get("fecha_apertura","")}<br>
                <b>Estado:</b> {caja.get("estado","")}</p>
                <table>
                    <tr><td>Caja inicial</td><td>RD$ {resumen["fondo_inicial"]:,.2f}</td></tr>
                    <tr><td>Ventas efectivo</td><td>RD$ {resumen["venta_efectivo"]:,.2f}</td></tr>
                    <tr><td>Transferencia</td><td>RD$ {resumen["venta_transferencia"]:,.2f}</td></tr>
                    <tr><td>Tarjeta</td><td>RD$ {resumen["venta_tarjeta"]:,.2f}</td></tr>
                    <tr><td>Crédito</td><td>RD$ {resumen["venta_credito"]:,.2f}</td></tr>
                    <tr><td>Total ventas</td><td>RD$ {resumen["total_ventas"]:,.2f}</td></tr>
                    <tr><td>Efectivo esperado</td><td>RD$ {resumen["efectivo_esperado"]:,.2f}</td></tr>
                    <tr><td>Efectivo contado</td><td>RD$ {efectivo_contado:,.2f}</td></tr>
                    <tr><td>Diferencia</td><td>RD$ {diferencia:,.2f}</td></tr>
                    <tr><td>Faltante</td><td>RD$ {faltante:,.2f}</td></tr>
                    <tr><td>Sobrante</td><td>RD$ {sobrante:,.2f}</td></tr>
                </table>
                <br><br>
                <p>Firma cajera: __________________________</p>
                <p>Firma supervisora: ______________________</p>
            </div>
        </body>
        </html>
        """

    caja_abierta = _obtener_caja_abierta_usuario(usuario_act)

    if not caja_abierta:
        st.subheader("🔓 Abrir caja")
        c1, c2 = st.columns(2)
        with c1:
            monto_inicial = st.number_input("Caja inicial / fondo inicial", min_value=0.0, step=1.0, value=0.0, key="caja_apertura_monto")
        with c2:
            obs_apertura = st.text_input("Observación apertura", key="caja_apertura_obs")

        if st.button("Abrir caja", key="btn_abrir_caja_pro"):
            payload = {
                "usuario": usuario_act,
                "usuario_id": str(usuario_sesion().get("id", "")),
                "fecha_apertura": datetime.now().isoformat(),
                "dia_operativo": str(hoy),
                "monto_inicial": float(monto_inicial),
                "estado": "abierta",
                "observacion": obs_apertura,
            }
            ok = insertar("caja", payload)
            if ok:
                st.success("Caja abierta correctamente.")
                st.rerun()
    else:
        st.success("Tienes una caja abierta.")
        resumen = _calcular_resumen_caja(caja_abierta)
        ventas_caja = resumen["ventas_df"]
        pagos_caja = resumen["pagos_df"]

        st.markdown("### 📌 Resumen de caja")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Caja inicial", f"RD$ {resumen['fondo_inicial']:,.2f}")
        r2.metric("Ventas efectivo", f"RD$ {resumen['venta_efectivo']:,.2f}")
        r3.metric("Efectivo esperado", f"RD$ {resumen['efectivo_esperado']:,.2f}")
        r4.metric("Total ventas", f"RD$ {resumen['total_ventas']:,.2f}")

        r5, r6, r7 = st.columns(3)
        r5.metric("Transferencia", f"RD$ {resumen['venta_transferencia']:,.2f}")
        r6.metric("Tarjeta", f"RD$ {resumen['venta_tarjeta']:,.2f}")
        r7.metric("Crédito", f"RD$ {resumen['venta_credito']:,.2f}")

        html_cuadre_pre = _html_cuadre_caja(caja_abierta, resumen)
        with st.expander("🖨️ Imprimir cuadre de caja para contar", expanded=False):
            components.html(html_cuadre_pre, height=780, scrolling=True)
            st.download_button(
                "⬇️ Descargar cuadre de caja",
                data=html_cuadre_pre.encode("utf-8"),
                file_name=f"cuadre_caja_{caja_abierta.get('usuario','')}.html",
                mime="text/html",
                key=f"desc_cuadre_caja_{caja_abierta.get('id')}",
            )

        with st.expander("🔎 Ver ventas y pagos tomados para este cierre", expanded=False):
            st.write("Ventas tomadas:")
            if ventas_caja.empty:
                st.info("No hay ventas registradas para esta caja.")
            else:
                cols = [c for c in ["numero_factura", "fecha", "total", "total_contable", "recargo", "metodo_pago", "metodo", "usuario", "caja_id"] if c in ventas_caja.columns]
                st.dataframe(ventas_caja[cols] if cols else ventas_caja, use_container_width=True)
            st.write("Pagos tomados:")
            if pagos_caja.empty:
                st.info("No hay pagos separados para esta caja.")
            else:
                cols_p = [c for c in ["venta_id", "metodo", "metodo_pago", "monto", "usuario", "caja_id", "dia_operativo"] if c in pagos_caja.columns]
                st.dataframe(pagos_caja[cols_p] if cols_p else pagos_caja, use_container_width=True)

        st.markdown("---")
        st.subheader("🔐 Cierre de caja")
        st.caption("La cajera solo escribe el efectivo físico contado. El sistema calcula si hay sobrante o faltante.")

        efectivo_contado = st.number_input(
            "Efectivo físico contado",
            min_value=0.0,
            step=1.0,
            value=float(resumen["efectivo_esperado"]),
            key="caja_efectivo_fisico_contado",
        )

        diferencia = float(efectivo_contado) - float(resumen["efectivo_esperado"])
        faltante = abs(diferencia) if diferencia < 0 else 0.0
        sobrante = diferencia if diferencia > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Efectivo esperado", f"RD$ {resumen['efectivo_esperado']:,.2f}")
        c2.metric("Efectivo contado", f"RD$ {efectivo_contado:,.2f}")
        if diferencia < 0:
            c3.metric("Faltante", f"RD$ {faltante:,.2f}")
        elif diferencia > 0:
            c3.metric("Sobrante", f"RD$ {sobrante:,.2f}")
        else:
            c3.metric("Diferencia", "RD$ 0.00")

        obs_cierre = st.text_area("Observación de cierre", key="caja_obs_cierre")

        html_cuadre_final = _html_cuadre_caja(caja_abierta, resumen, efectivo_contado)
        with st.expander("👁️ Vista previa del cuadre final", expanded=False):
            components.html(html_cuadre_final, height=780, scrolling=True)

        if st.button("Cerrar caja", key="btn_cerrar_caja_pro"):
            ok_update = _cerrar_caja(caja_abierta, efectivo_contado, obs_cierre, usuario_act)
            if ok_update:
                st.success("Caja cerrada correctamente.")
                st.rerun()

    st.markdown("---")
    st.subheader("📚 Historial de cierres")
    cierres = DATA.get("cierre_caja", pd.DataFrame()).copy()
    if cierres.empty:
        st.info("No hay cierres de caja registrados.")
    else:
        if es_cajera() and "usuario" in cierres.columns:
            cierres = cierres[cierres["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_act)]
        st.dataframe(_tabla_cajas_limpia(cierres), use_container_width=True)
        if not es_cajera():
            descargar_archivos(_tabla_cajas_limpia(cierres), "cierres_caja")

    if es_admin():
        st.markdown("---")
        st.subheader("🧑‍💼 Control administrativo de cajas")
        cajas_admin = _leer_cajas()
        if cajas_admin.empty:
            st.info("No hay cajas registradas.")
        else:
            cfa, cfb, cfc = st.columns(3)
            usuarios = ["Todos"]
            if "usuario" in cajas_admin.columns:
                usuarios += sorted([u for u in cajas_admin["usuario"].dropna().astype(str).unique().tolist() if u])
            usuario_filtro = cfa.selectbox("Filtrar por usuario", usuarios, key="admin_caja_usuario")
            estado_filtro = cfb.selectbox("Filtrar por estado", ["Todos", "abierta", "cerrada"], key="admin_caja_estado")
            texto_filtro = cfc.text_input("Buscar", key="admin_caja_buscar")

            cajas_vista = cajas_admin.copy()
            if usuario_filtro != "Todos" and "usuario" in cajas_vista.columns:
                cajas_vista = cajas_vista[cajas_vista["usuario"].astype(str) == usuario_filtro]
            if estado_filtro != "Todos" and "estado" in cajas_vista.columns:
                cajas_vista = cajas_vista[cajas_vista["estado"].astype(str).apply(normalizar_texto) == estado_filtro]
            cajas_vista = buscar_df(cajas_vista, texto_filtro)

            st.dataframe(_tabla_cajas_limpia(cajas_vista), use_container_width=True)

            cajas_abiertas = cajas_admin.copy()
            if "estado" in cajas_abiertas.columns:
                cajas_abiertas = cajas_abiertas[cajas_abiertas["estado"].astype(str).apply(normalizar_texto) == "abierta"]

            with st.expander("🔐 Cerrar caja abierta como administradora", expanded=False):
                if cajas_abiertas.empty:
                    st.info("No hay cajas abiertas.")
                else:
                    opciones = []
                    mapa = {}
                    for _, r in cajas_abiertas.iterrows():
                        etiqueta = f"{r.get('usuario','')} | apertura: {r.get('fecha_apertura','')} | fondo RD$ {float(limpiar_numero(r.get('monto_inicial')) or 0):,.2f}"
                        opciones.append(etiqueta)
                        mapa[etiqueta] = r.to_dict()

                    sel = st.selectbox("Selecciona caja abierta", opciones, key="admin_caja_abierta_sel")
                    caja_sel = mapa[sel]
                    resumen_sel = _calcular_resumen_caja(caja_sel)

                    aa, ab, ac, ad = st.columns(4)
                    aa.metric("Usuario", caja_sel.get("usuario", ""))
                    ab.metric("Caja inicial", f"RD$ {resumen_sel['fondo_inicial']:,.2f}")
                    ac.metric("Efectivo esperado", f"RD$ {resumen_sel['efectivo_esperado']:,.2f}")
                    ad.metric("Total ventas", f"RD$ {resumen_sel['total_ventas']:,.2f}")

                    efectivo_admin = st.number_input(
                        "Efectivo contado por administración",
                        min_value=0.0,
                        step=1.0,
                        value=float(resumen_sel["efectivo_esperado"]),
                        key="admin_caja_efectivo_contado",
                    )
                    diferencia_admin = float(efectivo_admin) - float(resumen_sel["efectivo_esperado"])
                    if diferencia_admin < 0:
                        st.warning(f"Faltante: RD$ {abs(diferencia_admin):,.2f}")
                    elif diferencia_admin > 0:
                        st.success(f"Sobrante: RD$ {diferencia_admin:,.2f}")
                    else:
                        st.info("Caja cuadrada. Diferencia RD$ 0.00")

                    obs_admin = st.text_area("Observación cierre administrativo", key="admin_caja_obs")
                    html_admin = _html_cuadre_caja(caja_sel, resumen_sel, efectivo_admin)
                    components.html(html_admin, height=420, scrolling=True)

                    if st.button("Cerrar esta caja como ADMIN", key="admin_btn_cerrar_caja"):
                        ok = _cerrar_caja(caja_sel, efectivo_admin, f"Cierre administrativo. {obs_admin}", usuario_act)
                        if ok:
                            st.success("Caja cerrada por administración.")
                            st.rerun()


            with st.expander("🔄 Recalcular caja cerrada", expanded=False):
                cajas_cerradas_recalc = cajas_admin.copy()
                if "estado" in cajas_cerradas_recalc.columns:
                    cajas_cerradas_recalc = cajas_cerradas_recalc[cajas_cerradas_recalc["estado"].astype(str).apply(normalizar_texto) == "cerrada"]

                if cajas_cerradas_recalc.empty:
                    st.info("No hay cajas cerradas para recalcular.")
                else:
                    opciones_recalc = []
                    mapa_recalc = {}
                    for _, r in cajas_cerradas_recalc.iterrows():
                        etiqueta = f"{r.get('usuario','')} | apertura: {r.get('fecha_apertura','')} | cierre: {r.get('fecha_cierre','')} | esperado actual RD$ {float(limpiar_numero(r.get('efectivo_esperado')) or 0):,.2f}"
                        opciones_recalc.append(etiqueta)
                        mapa_recalc[etiqueta] = r.to_dict()

                    sel_recalc = st.selectbox("Selecciona caja para recalcular", opciones_recalc, key="admin_caja_recalcular_sel")
                    caja_recalc = mapa_recalc[sel_recalc]
                    resumen_recalc = _calcular_resumen_caja(caja_recalc)

                    efectivo_original = float(limpiar_numero(caja_recalc.get("efectivo_contado")) or 0)
                    nuevo_esperado = float(resumen_recalc["efectivo_esperado"])
                    nueva_diferencia = efectivo_original - nuevo_esperado
                    nuevo_faltante = abs(nueva_diferencia) if nueva_diferencia < 0 else 0.0
                    nuevo_sobrante = nueva_diferencia if nueva_diferencia > 0 else 0.0

                    rr1, rr2, rr3, rr4 = st.columns(4)
                    rr1.metric("Caja inicial", f"RD$ {resumen_recalc['fondo_inicial']:,.2f}")
                    rr2.metric("Ventas efectivo recalculadas", f"RD$ {resumen_recalc['venta_efectivo']:,.2f}")
                    rr3.metric("Nuevo efectivo esperado", f"RD$ {nuevo_esperado:,.2f}")
                    rr4.metric("Efectivo contado guardado", f"RD$ {efectivo_original:,.2f}")

                    rr5, rr6, rr7 = st.columns(3)
                    rr5.metric("Nueva diferencia", f"RD$ {nueva_diferencia:,.2f}")
                    rr6.metric("Nuevo faltante", f"RD$ {nuevo_faltante:,.2f}")
                    rr7.metric("Nuevo sobrante", f"RD$ {nuevo_sobrante:,.2f}")

                    with st.expander("Ver ventas/pagos usados en recálculo", expanded=False):
                        st.write("Ventas")
                        vdf = resumen_recalc.get("ventas_df", pd.DataFrame())
                        st.dataframe(vdf, use_container_width=True)
                        st.write("Pagos ajustados sin recargo")
                        pdf = resumen_recalc.get("pagos_df", pd.DataFrame())
                        st.dataframe(pdf, use_container_width=True)

                    if st.button("Aplicar recálculo a esta caja", key="admin_aplicar_recalculo_caja"):
                        payload_recalc = {
                            "efectivo_esperado": float(nuevo_esperado),
                            "total_efectivo": float(resumen_recalc["venta_efectivo"]),
                            "total_transferencia": float(resumen_recalc["venta_transferencia"]),
                            "total_tarjeta": float(resumen_recalc["venta_tarjeta"]),
                            "total_credito": float(resumen_recalc["venta_credito"]),
                            "total_ventas": float(resumen_recalc["total_ventas"]),
                            "diferencia": float(nueva_diferencia),
                            "faltante": float(nuevo_faltante),
                            "sobrante": float(nuevo_sobrante),
                            "observacion": limpiar_texto(caja_recalc.get("observacion")) + " | Caja recalculada sin recargo financiero",
                        }
                        ok = actualizar("caja", caja_recalc.get("id"), payload_recalc)
                        if ok:
                            st.success("Caja recalculada correctamente.")
                            st.rerun()


            with st.expander("✏️ Editar datos de una caja cerrada", expanded=False):
                cajas_cerradas = cajas_admin.copy()
                if "estado" in cajas_cerradas.columns:
                    cajas_cerradas = cajas_cerradas[cajas_cerradas["estado"].astype(str).apply(normalizar_texto) == "cerrada"]

                if cajas_cerradas.empty:
                    st.info("No hay cajas cerradas para editar.")
                else:
                    opciones2 = []
                    mapa2 = {}
                    for _, r in cajas_cerradas.iterrows():
                        etiqueta = f"{r.get('usuario','')} | cierre: {r.get('fecha_cierre','')} | dif RD$ {float(limpiar_numero(r.get('diferencia')) or 0):,.2f}"
                        opciones2.append(etiqueta)
                        mapa2[etiqueta] = r.to_dict()

                    sel2 = st.selectbox("Selecciona caja cerrada", opciones2, key="admin_caja_cerrada_sel")
                    caja_cerrada = mapa2[sel2]

                    efectivo_edit = st.number_input(
                        "Efectivo contado corregido",
                        min_value=0.0,
                        step=1.0,
                        value=float(limpiar_numero(caja_cerrada.get("efectivo_contado")) or 0),
                        key="admin_edit_efectivo_contado",
                    )
                    esperado_edit = float(limpiar_numero(caja_cerrada.get("efectivo_esperado")) or 0)
                    diff_edit = float(efectivo_edit) - esperado_edit
                    falt_edit = abs(diff_edit) if diff_edit < 0 else 0.0
                    sobr_edit = diff_edit if diff_edit > 0 else 0.0
                    obs_edit = st.text_area(
                        "Observación corregida",
                        value=limpiar_texto(caja_cerrada.get("observacion")),
                        key="admin_edit_obs_caja",
                    )

                    st.metric("Nueva diferencia", f"RD$ {diff_edit:,.2f}")

                    if st.button("Guardar corrección de caja", key="admin_guardar_correccion_caja"):
                        payload_edit = {
                            "efectivo_contado": float(efectivo_edit),
                            "diferencia": float(diff_edit),
                            "faltante": float(falt_edit),
                            "sobrante": float(sobr_edit),
                            "observacion": obs_edit,
                        }
                        ok = actualizar("caja", caja_cerrada.get("id"), payload_edit)
                        if ok:
                            st.success("Caja corregida.")
                            st.rerun()

# =========================================================
# ESTADO DE RESULTADOS

# =========================================================
elif menu == "Estado de Resultados":
    st.title("📊 Estado de Resultados")

    desde, hasta = rango_fechas_ui("er")

    ventas_df = obtener_ventas_periodo_actualizadas(desde, hasta)
    compras_df = filtrar_por_fechas(DATA["compras"], desde, hasta)
    gastos_df = filtrar_por_fechas(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)

    ventas_tot = suma_col(ventas_df, "total")
    compras_tot = suma_col(compras_df, "monto")
    utilidad_bruta_ventas = obtener_utilidad_bruta_periodo(ventas_df)
    utilidad_bruta_manual = st.number_input("Utilidad bruta manual / ajuste", min_value=0.0, step=1.0, key="er_utilidad_bruta_manual")
    utilidad_bruta = float(utilidad_bruta_ventas) + float(utilidad_bruta_manual)
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
            ["Utilidad bruta desde ventas", utilidad_bruta_ventas],
            ["Utilidad bruta manual", utilidad_bruta_manual],
            ["Utilidad bruta total", utilidad_bruta],
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
    st.title("🛒 POS")
    caja_activa = obtener_caja_abierta()
    if caja_activa is None:
        st.warning("Debes abrir la caja antes de vender.")
        st.stop()
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
                "total_linea": float(cantidad) * float(precio_base),
            })

        c1, c2 = st.columns([1, 2])
        with c1:
            codigo_scan = st.text_input("Escanear / escribir código", key="pos_codigo")
            if st.button("Agregar por código", key="btn_pos_codigo"):
                prod = get_producto_por_codigo(codigo_scan)
                if prod is None:
                    st.error("Producto no encontrado con ese código.")
                else:
                    if producto_tiene_inventario(prod) and obtener_existencia_producto(prod) <= 0:
                        st.warning("Ese producto no tiene stock disponible.")
                    else:
                        agregar_item_carrito(prod, 1.0)
                        st.rerun()
        with c2:
            busqueda = st.text_input("Buscar por nombre", key="pos_busqueda")
            temp = productos_df.copy()
            if busqueda:
                temp = temp[temp.astype(str).apply(lambda col: col.str.contains(busqueda, case=False, na=False)).any(axis=1)]
            opciones = []
            mapa = {}
            for _, row in temp.iterrows():
                etiqueta = f"{obtener_nombre_producto(row)} | {limpiar_texto(row.get('codigo'))} | Stock {obtener_existencia_producto(row):,.0f}"
                opciones.append(etiqueta)
                mapa[etiqueta] = row
            if opciones:
                prod_label = st.selectbox("Producto", opciones, key="pos_producto_sel")
                prod = mapa[prod_label]
                c21, c22, c23 = st.columns(3)
                with c21:
                    cantidad_add = st.number_input("Cantidad", min_value=1.0, step=1.0, value=1.0, key="pos_cantidad_add")
                with c22:
                    tipo_precio = st.selectbox("Tipo de precio", ["normal", "descuento", "especial"], key="pos_tipo_precio")
                with c23:
                    precio_ref = limpiar_numero(prod.get("precio")) or 0.0
                    if tipo_precio == "descuento":
                        precio_ref = limpiar_numero(prod.get("precio_descuento")) or precio_ref
                    elif tipo_precio == "especial":
                        precio_ref = limpiar_numero(prod.get("precio_especial")) or precio_ref
                    st.metric("Precio usado", f"RD$ {precio_ref:,.2f}")
                if st.button("➕ Agregar al carrito", key="btn_pos_agregar"):
                    if producto_tiene_inventario(prod) and cantidad_add > obtener_existencia_producto(prod):
                        st.error("No hay stock suficiente.")
                    else:
                        agregar_item_carrito(prod, cantidad_add, precio_ref)
                        st.rerun()

        st.subheader("🧾 Carrito")

        post_venta = st.session_state.get("pos_post_venta")
        if post_venta:
            st.success(f"Venta registrada correctamente. Factura No.: {post_venta.get('numero_factura') or post_venta.get('venta_id', '')}")
            p1, p2, p3 = st.columns(3)
            p1.metric("Total", f"RD$ {float(post_venta.get('total', 0)):,.2f}")
            p2.metric("Cambio", f"RD$ {float(post_venta.get('cambio', 0)):,.2f}")
            p3.metric("Método", str(post_venta.get('metodo_pago', '')))

            mostrar_factura_pos(post_venta)

            if st.button("✅ Terminar", key=f"btn_pos_post_venta_terminar_{post_venta.get('venta_id')}"):
                st.session_state["pos_post_venta"] = None
                st.rerun()
            st.markdown("---")

        if carrito:
            df_carrito = pd.DataFrame(carrito)
            st.data_editor(df_carrito, use_container_width=True, disabled=["producto_id", "codigo", "producto"], key="editor_carrito")

            st.caption("Si te equivocas antes de cobrar, quita el producto aquí mismo.")
            for i, item in enumerate(list(carrito)):
                col_q1, col_q2, col_q3, col_q4 = st.columns([4, 2, 2, 1])
                with col_q1:
                    st.write(item["producto"])
                with col_q2:
                    st.write(f"Cant. {float(item['cantidad']):,.0f}")
                with col_q3:
                    st.write(f"RD$ {float(item['total_linea']):,.2f}")
                with col_q4:
                    if st.button("❌", key=f"quitar_pos_{i}"):
                        carrito.pop(i)
                        st.rerun()

            subtotal = float(df_carrito["total_linea"].sum())

            descuento_global = st.number_input("Descuento global", min_value=0.0, step=1.0, key="pos_desc_global")
            cliente_df = DATA.get("clientes", pd.DataFrame()).copy()
            cliente_nombre = "Venta general"
            cliente_id = None
            usar_cliente = st.checkbox("Asignar cliente", value=False, key="pos_usar_cliente")
            if usar_cliente and not cliente_df.empty:
                cli_opt = ["Venta general"] + cliente_df["nombre"].astype(str).tolist()
                cliente_nombre = st.selectbox("Cliente", cli_opt, key="pos_cliente_sel")
                if cliente_nombre != "Venta general":
                    cli_row = cliente_df[cliente_df["nombre"].astype(str) == cliente_nombre].iloc[0]
                    cliente_id = cli_row["id"]
            cpa1, cpa2, cpa3, cpa4 = st.columns(4)
            with cpa1:
                pago_efectivo = st.number_input("Efectivo", min_value=0.0, step=1.0, key="pos_pag_ef")
            with cpa2:
                pago_transferencia = st.number_input("Transferencia", min_value=0.0, step=1.0, key="pos_pag_tr")
            with cpa3:
                pago_tarjeta = st.number_input("Tarjeta", min_value=0.0, step=1.0, key="pos_pag_tj")
            with cpa4:
                pago_credito = st.number_input("Crédito / fiado", min_value=0.0, step=1.0, key="pos_pag_cr")
            recargo_pct = limpiar_numero(cfg.get("recargo_tarjeta_pct")) or 0.0
            recargo = float(pago_tarjeta) * (recargo_pct / 100.0)
            total_final = max(subtotal - descuento_global + recargo, 0.0)
            pagos_total = pago_efectivo + pago_transferencia + pago_tarjeta + pago_credito
            cambio = max(pagos_total - total_final, 0.0)
            faltante = max(total_final - pagos_total, 0.0)
            csum1, csum2, csum3, csum4 = st.columns(4)
            csum1.metric("Subtotal", f"RD$ {subtotal:,.2f}")
            csum2.metric("Recargo tarjeta", f"RD$ {recargo:,.2f}")
            csum3.metric("Total final", f"RD$ {total_final:,.2f}")
            csum4.metric("Cambio / faltante", f"RD$ {cambio:,.2f}" if cambio > 0 else f"Faltan RD$ {faltante:,.2f}")

            tarjeta_info = float(locals().get("tarjeta", 0) or locals().get("pago_tarjeta", 0) or 0)
            recargo_info = float(locals().get("recargo", 0) or locals().get("recargo_tarjeta", 0) or 0)
            st.markdown("### 💳 Recargo de tarjeta")
            st.info(
                f"Tarjeta registrada para contabilidad: RD$ {tarjeta_info:,.2f} | "
                f"Recargo informativo 4%: RD$ {recargo_info:,.2f} | "
                f"Total que debes cobrar por tarjeta: RD$ {tarjeta_info + recargo_info:,.2f}"
            )
            st.caption("Ese recargo no se escribe en efectivo, transferencia ni crédito. Solo informa cuánto cobrar por tarjeta.")

            ncf = st.text_input("NCF (opcional)", key="pos_ncf")
            numero_factura_pos = generar_numero_factura_pos()
            st.caption(f"Factura No. {numero_factura_pos}")
            if st.button("💳 Cobrar", key="btn_pos_cobrar"):
                if faltante > 0.001:
                    st.error("Los pagos no cubren el total final.")
                elif pago_credito > 0 and cliente_nombre == "Venta general":
                    st.error("Para vender a crédito debes asignar un cliente.")
                else:
                    try:
                        venta_resp = supabase.table("ventas").insert({
                            "fecha": datetime.now().isoformat(),
                            "subtotal": float(subtotal),
                            "descuento": float(descuento_global),
                            "recargo": float(recargo),
                            "total": float(subtotal),
                            "metodo_pago": "mixto" if sum(v > 0 for v in [pago_efectivo, pago_transferencia, pago_tarjeta, pago_credito]) > 1 else ("efectivo" if pago_efectivo > 0 else "transferencia" if pago_transferencia > 0 else "tarjeta" if pago_tarjeta > 0 else "credito"),
                            "cliente_id": cliente_id,
                            "cliente_nombre": cliente_nombre,
                            "usuario": nombre_usuario_actual(),
                            "dia_operativo": ahora_str(),
                            "caja_id": str(caja_activa.get("id")),
                            "ncf": ncf,
                            "numero_factura": numero_factura_pos,
"tipo_venta": "POS",
                            "estado": "completada",
                            "anulado": False,
                        }).execute()
                        venta = (venta_resp.data or [{}])[0]
                        venta_id = venta.get("id")
                        for item in carrito:
                            prod = productos_df[productos_df["id"].astype(str) == str(item["producto_id"])].iloc[0]
                            costo_unit, movimientos_fifo = obtener_costo_fifo(prod, float(item["cantidad"]))
                            total_linea = float(item["cantidad"]) * float(item["precio_unitario"])
                            supabase.table("detalle_venta").insert({
                                "venta_id": str(venta_id),
"producto_id": str(prod["id"]),
                                "codigo": item["codigo"],
                                "producto": item["producto"],
                                "cantidad": float(item["cantidad"]),
                                "precio_unitario": float(item["precio_unitario"]),
                                "costo_unitario": float(costo_unit),
                                "descuento": 0,
                                "recargo": 0,
                                "total_linea": total_linea,
                                "ganancia_linea": total_linea - (float(item["cantidad"]) * float(costo_unit)),
                                "usuario": nombre_usuario_actual(),
                                "anulado": False,
                            }).execute()
                            if producto_tiene_inventario(prod):
                                nueva_cant = max(obtener_existencia_producto(prod) - float(item["cantidad"]), 0.0)
                                actualizar_existencia_producto(prod, nueva_cant)
                                prod_sync = refrescar_producto_por_id(prod["id"])
                                if prod_sync is None:
                                    prod_sync = prod
                                sincronizar_producto_inventario(prod_sync, ahora_str(), f"Salida por venta {venta_id}")
                                aplicar_consumo_fifo(movimientos_fifo)
                                registrar_movimiento_inventario(prod["id"], obtener_nombre_producto(prod), "salida_venta", "ventas", venta_id, -float(item["cantidad"]), costo_unit, "Salida por venta POS")
                        pagos = {"efectivo": pago_efectivo, "transferencia": pago_transferencia, "tarjeta": pago_tarjeta, "credito": pago_credito}
                        for metodo, monto in pagos.items():
                            if monto > 0:
                                monto_contable_pago = float(monto)
                                supabase.table("ventas_pagos").insert({
                                    "venta_id": str(venta_id),
                                    "metodo": metodo,
                                    "monto": float(monto),
                                    "usuario": nombre_usuario_actual(),
                                    "caja_id": str(caja_activa.get("id")),
                                    "dia_operativo": ahora_str(),
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
                                            "monto": float(monto),
                                            "descripcion": f"Venta POS {venta_id}",
                                            "usuario": nombre_usuario_actual(),
                                        }).execute()
                                    except Exception:
                                        pass
                        if pago_credito > 0:
                            supabase.table("cuentas_por_cobrar").insert({
                                "cliente_id": cliente_id,
                                "cliente_nombre": cliente_nombre,
                                "venta_id": str(venta_id),
                                "monto_original": float(pago_credito),
                                "monto_abonado": 0,
                                "saldo_pendiente": float(pago_credito),
                                "estado": "pendiente",
                                "usuario": nombre_usuario_actual(),
                            }).execute()
                        registrar_auditoria("venta_pos", "ventas", f"venta_id={venta_id} total={total_final}")
                        DATA.update(cargar_datos())
                        st.session_state["pos_post_venta"] = {
                            "venta_id": str(venta_id),
                            "numero_factura": numero_factura_pos,
                            "total": float(subtotal),
                            "total_real": float(subtotal),
                            "cambio": float(cambio),
                            "cliente_nombre": cliente_nombre,
                            "metodo_pago": "mixto" if sum(v > 0 for v in [pago_efectivo, pago_transferencia, pago_tarjeta, pago_credito]) > 1 else ("efectivo" if pago_efectivo > 0 else "transferencia" if pago_transferencia > 0 else "tarjeta" if pago_tarjeta > 0 else "credito"),
                            "ncf": ncf,
                            "items": [dict(x) for x in carrito],
                        }
                        st.session_state["pos_carrito"] = []
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se pudo registrar la venta: {exc}")
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
        render_crud_generico("clientes", df, "🛠️ Editar / eliminar clientes")
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
        render_crud_generico("proveedores", df, "🛠️ Editar / eliminar proveedores")
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
                puede_editar_todo = st.checkbox("Puede editar todo", key="usr_pet")
                puede_ver_utilidad = st.checkbox("Puede ver utilidad", key="usr_pvu")
            if st.button("Guardar usuario", key="btn_guardar_usuario"):
                existentes = DATA.get("usuarios", pd.DataFrame()).copy()
                if not limpiar_texto(usuario):
                    st.error("Debes poner usuario.")
                elif not limpiar_texto(clave):
                    st.error("Debes poner clave.")
                else:
                    if not existentes.empty and "usuario" in existentes.columns and normalizar_texto(usuario) in existentes["usuario"].astype(str).apply(normalizar_texto).tolist():
                        fila = existentes[existentes["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario)].iloc[0]
                        actualizar("usuarios", fila["id"], {"nombre": nombre, "usuario": usuario, "clave": clave, "rol": rol, "activo": activo, "puede_vender": puede_vender, "puede_editar_ventas": puede_editar_ventas, "puede_eliminar": puede_eliminar, "puede_anular": puede_anular, "puede_ver_reportes": puede_ver_reportes, "puede_registrar_compras": puede_registrar_compras, "puede_registrar_gastos": puede_registrar_gastos, "puede_configurar": puede_configurar, "puede_editar_todo": puede_editar_todo, "puede_ver_utilidad": puede_ver_utilidad})
                        st.success("Usuario actualizado.")
                    else:
                        insertar("usuarios", {"nombre": nombre, "usuario": usuario, "clave": clave, "rol": rol, "activo": activo, "puede_vender": puede_vender, "puede_editar_ventas": puede_editar_ventas, "puede_eliminar": puede_eliminar, "puede_anular": puede_anular, "puede_ver_reportes": puede_ver_reportes, "puede_registrar_compras": puede_registrar_compras, "puede_registrar_gastos": puede_registrar_gastos, "puede_configurar": puede_configurar, "puede_editar_todo": puede_editar_todo, "puede_ver_utilidad": puede_ver_utilidad})
                        st.success("Usuario creado.")
                    st.rerun()
        df = DATA.get("usuarios", pd.DataFrame()).copy()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            render_crud_generico("usuarios", df, "🛠️ Editar / eliminar usuarios", excluir=["clave"])

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
