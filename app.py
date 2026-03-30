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
# LOGIN SIMPLE
# =========================================================
def login_simple() -> bool:
    if not APP_PASSWORD:
        return True

    if st.session_state.get("autorizado", False):
        return True

    st.title("🔐 Acceso al sistema")
    clave = st.text_input("Clave del sistema", type="password")

    if st.button("Entrar", key="btn_login"):
        if clave == APP_PASSWORD:
            st.session_state["autorizado"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")

    return False


if not login_simple():
    st.stop()


# =========================================================
# UTILIDADES
# =========================================================
def ahora_str() -> str:
    return date.today().isoformat()



def limpiar_texto(valor: Any) -> str:
    if pd.isna(valor):
        return ""
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
        return normalizar_columnas(df)
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
# CRUD PRO COMPLETO (CREAR - EDITAR - ELIMINAR - ANULAR)
# =========================================================

def insertar(tabla, datos, usuario="admin"):
    try:
        supabase.table(tabla).insert(datos).execute()

        supabase.table("auditoria").insert({
            "accion": "crear",
            "tabla": tabla,
            "usuario": usuario,
            "detalle": str(datos)
        }).execute()

        return True

    except Exception as e:
        st.error(f"Error al insertar en {tabla}: {e}")
        return False


def actualizar(tabla, fila_id, datos, usuario="admin"):
    try:
        supabase.table(tabla).update(datos).eq("id", fila_id).execute()

        supabase.table("auditoria").insert({
            "accion": "editar",
            "tabla": tabla,
            "usuario": usuario,
            "detalle": f"id={fila_id} | {datos}"
        }).execute()

        return True

    except Exception as e:
        st.error(f"Error al actualizar en {tabla}: {e}")
        return False


def eliminar(tabla, fila_id, usuario="admin"):
    try:
        supabase.table(tabla).delete().eq("id", fila_id).execute()

        supabase.table("auditoria").insert({
            "accion": "eliminar",
            "tabla": tabla,
            "usuario": usuario,
            "detalle": f"id eliminado: {fila_id}"
        }).execute()

        return True

    except Exception as e:
        st.error(f"Error al eliminar en {tabla}: {e}")
        return False


def anular(tabla, fila_id, motivo="", usuario="admin"):
    try:
        supabase.table(tabla).update({
            "anulado": True,
            "motivo_anulacion": motivo
        }).eq("id", fila_id).execute()

        supabase.table("auditoria").insert({
            "accion": "anular",
            "tabla": tabla,
            "usuario": usuario,
            "detalle": f"id={fila_id} | motivo={motivo}"
        }).execute()

        return True

    except Exception as e:
        st.error(f"Error al anular en {tabla}: {e}")
        return False


def leer_tabla(tabla):
    try:
        resp = supabase.table(tabla).select("*").execute()
        return pd.DataFrame(resp.data or [])
    except Exception as e:
        st.error(f"Error al leer {tabla}: {e}")
        return pd.DataFrame()

# =========================================================
def registrar_auditoria(accion: str, tabla: str, detalle: str = ""):
    try:
        supabase.table("auditoria").insert(
            {
                "accion": accion,
                "tabla": tabla,
                "usuario": "sistema",
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



def insertar(nombre_tabla: str, datos: dict) -> bool:
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        registrar_auditoria("insertar", nombre_tabla, str(datos)[:500])
        return True
    except Exception as exc:
        st.error(f"Error al insertar en {nombre_tabla}: {exc}")
        return False



def actualizar(nombre_tabla: str, fila_id: Any, datos: dict) -> bool:
    try:
        supabase.table(nombre_tabla).update(datos).eq("id", fila_id).execute()
        registrar_auditoria("actualizar", nombre_tabla, f"id={fila_id} | {str(datos)[:500]}")
        return True
    except Exception as exc:
        st.error(f"Error al actualizar en {nombre_tabla}: {exc}")
        return False



def eliminar(nombre_tabla: str, fila_id: Any) -> bool:
    try:
        supabase.table(nombre_tabla).delete().eq("id", fila_id).execute()
        registrar_auditoria("eliminar", nombre_tabla, f"id={fila_id}")
        return True
    except Exception as exc:
        st.error(f"Error al eliminar en {nombre_tabla}: {exc}")
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




def valor_bool_ui(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    txt = normalizar_texto(valor)
    return txt in ["true", "1", "si", "sí", "yes", "activo"]


def columnas_sistema_no_editables() -> set[str]:
    return {"id", "created_at", "updated_at"}


def construir_payload_desde_fila(df: pd.DataFrame, fila: pd.Series, key_base: str) -> dict:
    payload: dict[str, Any] = {}
    excluir = columnas_sistema_no_editables()

    for col in df.columns:
        if col in excluir:
            continue

        valor = fila.get(col, None)
        etiqueta = col.replace("_", " ").title()

        if col == "anulado":
            payload[col] = st.checkbox(etiqueta, value=valor_bool_ui(valor), key=f"{key_base}_{col}")
            continue

        if "fecha" in col:
            fecha_default = date.today()
            try:
                fecha_parsed = pd.to_datetime(valor, errors="coerce")
                if not pd.isna(fecha_parsed):
                    fecha_default = fecha_parsed.date()
            except Exception:
                pass
            payload[col] = str(st.date_input(etiqueta, value=fecha_default, key=f"{key_base}_{col}"))
            continue

        if pd.api.types.is_bool_dtype(df[col]) or isinstance(valor, bool):
            payload[col] = st.checkbox(etiqueta, value=valor_bool_ui(valor), key=f"{key_base}_{col}")
            continue

        if pd.api.types.is_numeric_dtype(df[col]) or isinstance(valor, (int, float)):
            num = limpiar_numero(valor) or 0.0
            payload[col] = float(st.number_input(etiqueta, value=float(num), step=1.0, key=f"{key_base}_{col}"))
            continue

        txt = "" if pd.isna(valor) else str(valor)
        if len(txt) > 80:
            payload[col] = st.text_area(etiqueta, value=txt, key=f"{key_base}_{col}")
        else:
            payload[col] = st.text_input(etiqueta, value=txt, key=f"{key_base}_{col}")

    return payload


def crud_pro_tabla(tabla: str, permitir_anular: bool = True, permitir_eliminar: bool = True):
    st.title(f"🛠️ CRUD PRO · {tabla}")
    df = leer_tabla(tabla)

    if df.empty:
        st.info("No hay registros en esta tabla.")
        return

    txt = st.text_input("Buscar", key=f"crud_buscar_{tabla}")
    if txt:
        df = buscar_df(df, txt)

    st.subheader("📋 Registros")
    st.dataframe(df, use_container_width=True)

    if "id" not in df.columns:
        st.warning("Esta tabla no tiene columna id. No se puede editar ni eliminar desde aquí.")
        return

    opciones = df["id"].tolist()
    fila_id = st.selectbox("Selecciona el ID a trabajar", opciones, key=f"crud_id_{tabla}")
    fila = df[df["id"] == fila_id].iloc[0]

    st.subheader("✏️ Editar registro")
    with st.form(f"form_editar_{tabla}"):
        payload = construir_payload_desde_fila(df, fila, f"edit_{tabla}_{fila_id}")
        guardar = st.form_submit_button("💾 Guardar cambios")
        if guardar:
            if actualizar(tabla, fila_id, payload):
                st.success("Registro actualizado correctamente.")
                st.rerun()

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🗑️ Eliminar")
        confirmar_eliminar = st.checkbox(
            "Confirmo que quiero eliminar físicamente este registro",
            key=f"confirmar_eliminar_{tabla}_{fila_id}",
        )
        if st.button("Eliminar definitivo", key=f"btn_eliminar_{tabla}_{fila_id}", disabled=not permitir_eliminar):
            if not permitir_eliminar:
                st.warning("En esta tabla se recomienda anular en vez de eliminar.")
            elif not confirmar_eliminar:
                st.warning("Debes confirmar antes de eliminar.")
            elif eliminar(tabla, fila_id):
                st.success("Registro eliminado correctamente.")
                st.rerun()

    with c2:
        st.subheader("🚫 Anular")
        motivo = st.text_area("Motivo de anulación", key=f"motivo_anular_{tabla}_{fila_id}")
        if st.button("Anular registro", key=f"btn_anular_{tabla}_{fila_id}", disabled=not permitir_anular):
            if not permitir_anular:
                st.warning("Esta tabla normalmente se maneja con eliminar, no con anular.")
            elif anular(tabla, fila_id, motivo):
                st.success("Registro anulado correctamente.")
                st.rerun()


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("💼 Sistema de Negocio PRO")
menu = st.sidebar.selectbox(
    "Menú",
    [
        "Dashboard",
        "Productos",
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
        "CRUD PRO",
        "Auditoría",
    ],
)

if st.sidebar.button("🔄 Recargar nube"):
    st.rerun()


# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Dashboard PRO")

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

    with st.expander("📥 Subir Excel / CSV de productos"):
        st.write("Columnas esperadas: nombre, costo, precio, cantidad. Fecha opcional.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_productos")
        if archivo is not None and st.button("Cargar productos"):
            df = leer_archivo_subido(archivo)
            df = df.rename(columns={"producto": "nombre"})
            faltan = [c for c in ["nombre", "costo", "precio", "cantidad"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                procesados = 0
                for _, row in df.iterrows():
                    nombre = limpiar_texto(row["nombre"])
                    if not nombre:
                        continue
                    costo = limpiar_numero(row["costo"]) or 0
                    precio = limpiar_numero(row["precio"]) or 0
                    cantidad = limpiar_numero(row["cantidad"]) or 0
                    fecha_row = parsear_fecha(row["fecha"]) if "fecha" in df.columns else ahora_str()

                    existente = get_producto_por_nombre(nombre)
                    if existente is not None:
                        nueva_cantidad = (limpiar_numero(existente.get("cantidad")) or 0) + cantidad
                        actualizar(
                            "productos",
                            existente["id"],
                            {
                                "fecha": fecha_row,
                                "costo": float(costo),
                                "precio": float(precio),
                                "cantidad": float(nueva_cantidad),
                            },
                        )
                    else:
                        insertar(
                            "productos",
                            {
                                "fecha": fecha_row,
                                "nombre": nombre,
                                "costo": float(costo),
                                "precio": float(precio),
                                "cantidad": float(cantidad),
                            },
                        )
                    procesados += 1
                st.success(f"Se procesaron {procesados} productos.")
                st.rerun()

    with st.expander("➕ Agregar producto manual", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="prod_fecha")
            nombre = st.text_input("Nombre", key="prod_nombre")
            costo = st.number_input("Costo", min_value=0.0, step=1.0, key="prod_costo")
        with c2:
            precio = st.number_input("Precio", min_value=0.0, step=1.0, key="prod_precio")
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, key="prod_cantidad")

        if st.button("Guardar producto"):
            if not limpiar_texto(nombre):
                st.error("Debes escribir el nombre del producto.")
            else:
                existente = get_producto_por_nombre(nombre)
                if existente is not None:
                    nueva_cantidad = (limpiar_numero(existente.get("cantidad")) or 0) + float(cantidad)
                    ok = actualizar(
                        "productos",
                        existente["id"],
                        {
                            "fecha": str(fecha),
                            "costo": float(costo),
                            "precio": float(precio),
                            "cantidad": float(nueva_cantidad),
                        },
                    )
                    if ok:
                        st.success("Producto actualizado sumando cantidad.")
                        st.rerun()
                else:
                    ok = insertar(
                        "productos",
                        {
                            "fecha": str(fecha),
                            "nombre": limpiar_texto(nombre),
                            "costo": float(costo),
                            "precio": float(precio),
                            "cantidad": float(cantidad),
                        },
                    )
                    if ok:
                        st.success("Producto creado.")
                        st.rerun()

    st.subheader("📋 Listado")
    df = DATA["productos"].copy()
    if not df.empty:
        txt = st.text_input("Buscar producto", key="buscar_prod")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "productos")
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

    with st.expander("📥 Subir Excel / CSV de compras"):
        st.write("Columnas esperadas: fecha, numero, proveedor, descripcion, monto, metodo")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_compras")
        if archivo is not None and st.button("Cargar compras"):
            df = leer_archivo_subido(archivo)
            faltan = [c for c in ["fecha", "numero", "proveedor", "descripcion", "monto", "metodo"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                count = 0
                for _, row in df.iterrows():
                    fecha = parsear_fecha(row["fecha"])
                    monto = limpiar_numero(row["monto"]) or 0
                    if fecha:
                        insertar(
                            "compras",
                            {
                                "fecha": fecha,
                                "numero": limpiar_texto(row["numero"]),
                                "proveedor": limpiar_texto(row["proveedor"]),
                                "descripcion": limpiar_texto(row["descripcion"]),
                                "monto": float(monto),
                                "metodo": limpiar_texto(row["metodo"]),
                            },
                        )
                        count += 1
                st.success(f"Se cargaron {count} compras.")
                st.rerun()

    with st.expander("➕ Agregar compra manual", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="comp_fecha")
            numero = st.text_input("Número", key="comp_num")
            proveedor = st.text_input("Proveedor", key="comp_prov")
        with c2:
            descripcion = st.text_input("Descripción", key="comp_desc")
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="comp_monto")
            metodo = st.selectbox("Método", ["efectivo", "transferencia", "tarjeta"], key="comp_met")

        if st.button("Guardar compra"):
            if insertar(
                "compras",
                {
                    "fecha": str(fecha),
                    "numero": numero,
                    "proveedor": proveedor,
                    "descripcion": descripcion,
                    "monto": float(monto),
                    "metodo": metodo,
                },
            ):
                st.success("Compra guardada.")
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
# CRUD PRO
# =========================================================
elif menu == "CRUD PRO":
    tabla = st.selectbox(
        "Tabla",
        [
            "productos",
            "empleados",
            "catalogo_gastos",
            "adelantos_empleados",
            "ventas",
            "compras",
            "gastos",
            "perdidas",
            "gastos_dueno",
            "cierre_caja",
            "inventario_actual",
            "conteo_inventario",
            "ajustes_inventario",
            "estado_resultados",
        ],
        key="crud_tabla_general",
    )

    tablas_transaccionales = {"ventas", "compras", "gastos", "perdidas", "gastos_dueno", "cierre_caja", "estado_resultados"}
    permitir_anular = tabla in tablas_transaccionales
    permitir_eliminar = not permitir_anular

    st.info(
        "Productos, empleados, catálogo y adelantos: usa eliminar. "
        "Ventas, compras, gastos, pérdidas, cierre y similares: usa anular."
    )
    crud_pro_tabla(tabla, permitir_anular=permitir_anular, permitir_eliminar=permitir_eliminar)

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

