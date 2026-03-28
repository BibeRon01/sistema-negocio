import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# =========================================================
# CONFIGURACIÓN / CONEXIÓN
# =========================================================
def obtener_secreto(nombre: str, default: str = "") -> str:
    try:
        return st.secrets[nombre]
    except Exception:
        return default


SUPABASE_URL = obtener_secreto("SUPABASE_URL", "")
SUPABASE_KEY = obtener_secreto("SUPABASE_KEY", "")
APP_PASSWORD = obtener_secreto("APP_PASSWORD", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Faltan SUPABASE_URL y/o SUPABASE_KEY en .streamlit/secrets.toml")
    st.code(
        'SUPABASE_URL = "https://TU-PROYECTO.supabase.co"\n'
        'SUPABASE_KEY = "TU_CLAVE_PUBLICABLE"\n'
        'APP_PASSWORD = "1234"',
        language="toml"
    )
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"No se pudo conectar con Supabase: {e}")
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

    if st.button("Entrar"):
        if clave == APP_PASSWORD:
            st.session_state["autorizado"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")

    return False


if not login_simple():
    st.stop()

# =========================================================
# FUNCIONES BASE
# =========================================================
def leer_tabla(nombre_tabla: str) -> pd.DataFrame:
    try:
        resp = supabase.table(nombre_tabla).select("*").order("id").execute()
        data = resp.data if resp.data else []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al leer {nombre_tabla}: {e}")
        return pd.DataFrame()


def insertar_tabla(nombre_tabla: str, datos: dict) -> bool:
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        return True
    except Exception as e:
        st.error(f"Error al guardar en {nombre_tabla}: {e}")
        return False


def actualizar_tabla(nombre_tabla: str, fila_id: int, datos: dict) -> bool:
    try:
        supabase.table(nombre_tabla).update(datos).eq("id", fila_id).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar en {nombre_tabla}: {e}")
        return False


def eliminar_tabla(nombre_tabla: str, fila_id: int) -> bool:
    try:
        supabase.table(nombre_tabla).delete().eq("id", fila_id).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar en {nombre_tabla}: {e}")
        return False


def convertir_fechas(df: pd.DataFrame, columnas=("fecha",)) -> pd.DataFrame:
    if df.empty:
        return df
    for col in columnas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def suma_segura(df: pd.DataFrame, columna: str) -> float:
    if df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())


def filtrar_rango_fechas(df: pd.DataFrame, fecha_inicio, fecha_fin) -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns:
        return df.copy()
    df2 = df.copy()
    df2["fecha"] = pd.to_datetime(df2["fecha"], errors="coerce")
    inicio = pd.to_datetime(fecha_inicio)
    fin = pd.to_datetime(fecha_fin)
    return df2[(df2["fecha"] >= inicio) & (df2["fecha"] <= fin)]


def buscar_en_df(df: pd.DataFrame, texto: str) -> pd.DataFrame:
    if df.empty or not texto:
        return df
    mask = df.astype(str).apply(
        lambda x: x.str.contains(texto, case=False, na=False)
    ).any(axis=1)
    return df[mask]


def descargar_csv(df: pd.DataFrame, nombre_archivo: str):
    if df.empty:
        st.info("No hay datos para descargar.")
        return
    data = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar CSV",
        data=data,
        file_name=nombre_archivo,
        mime="text/csv"
    )


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def leer_archivo_subido(archivo) -> pd.DataFrame:
    try:
        nombre = archivo.name.lower()
        if nombre.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
        return normalizar_columnas(df)
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        return pd.DataFrame()


def preparar_valor(v):
    if pd.isna(v):
        return None
    if isinstance(v, pd.Timestamp):
        return v.date().isoformat()
    return v


def subir_excel_a_tabla(nombre_tabla: str, columnas_permitidas: list[str], archivo, columnas_fecha=None):
    if columnas_fecha is None:
        columnas_fecha = []

    df = leer_archivo_subido(archivo)
    if df.empty:
        return

    faltantes = [c for c in columnas_permitidas if c not in df.columns]
    if faltantes:
        st.error(f"Al archivo le faltan estas columnas: {faltantes}")
        st.write("Columnas detectadas:", list(df.columns))
        return

    df = df[columnas_permitidas].copy()

    for col in columnas_fecha:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    total_ok = 0
    total_bad = 0

    for _, row in df.iterrows():
        datos = {col: preparar_valor(row[col]) for col in columnas_permitidas}
        ok = insertar_tabla(nombre_tabla, datos)
        if ok:
            total_ok += 1
        else:
            total_bad += 1

    if total_ok:
        st.success(f"Se cargaron {total_ok} registros en {nombre_tabla}.")
    if total_bad:
        st.warning(f"{total_bad} registros no se pudieron cargar.")


def mostrar_tabla_filtrada(df: pd.DataFrame, titulo: str, key_base: str, nombre_descarga: str):
    st.subheader(titulo)

    c1, c2 = st.columns(2)
    with c1:
        f1 = st.date_input("Desde", value=date.today().replace(day=1), key=f"{key_base}_desde")
    with c2:
        f2 = st.date_input("Hasta", value=date.today(), key=f"{key_base}_hasta")

    texto = st.text_input("Buscar", key=f"{key_base}_buscar")

    df_f = filtrar_rango_fechas(df, f1, f2)
    df_f = buscar_en_df(df_f, texto)

    st.dataframe(df_f, use_container_width=True)
    descargar_csv(df_f, nombre_descarga)

# =========================================================
# CARGA DESDE NUBE
# =========================================================
productos = convertir_fechas(leer_tabla("productos"))
ventas = convertir_fechas(leer_tabla("ventas"))
compras = convertir_fechas(leer_tabla("compras"))
gastos = convertir_fechas(leer_tabla("gastos"))
perdidas = convertir_fechas(leer_tabla("perdidas"))
gastos_dueno = convertir_fechas(leer_tabla("gastos_dueno"))
empleados = convertir_fechas(leer_tabla("empleados"))
cierre_caja = convertir_fechas(leer_tabla("cierre_caja"))
estado_resultados = convertir_fechas(leer_tabla("estado_resultados"))

# Detectar si la tabla gastos tiene columna tipo
TIENE_TIPO_GASTO = "tipo" in gastos.columns if not gastos.empty else False

# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("💼 Sistema de Negocio")
menu = st.sidebar.selectbox(
    "Menú",
    [
        "Dashboard",
        "Productos",
        "Ventas",
        "Compras",
        "Gastos",
        "Pérdidas",
        "Gastos Dueño",
        "Empleados",
        "Cierre de Caja",
        "Estado de Resultados",
    ],
)

if st.sidebar.button("🔄 Recargar nube"):
    st.rerun()

# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Dashboard")

    c1, c2 = st.columns(2)
    with c1:
        fecha_inicio = st.date_input("Desde", value=date.today().replace(day=1), key="dash_desde")
    with c2:
        fecha_fin = st.date_input("Hasta", value=date.today(), key="dash_hasta")

    ventas_f = filtrar_rango_fechas(ventas, fecha_inicio, fecha_fin)
    compras_f = filtrar_rango_fechas(compras, fecha_inicio, fecha_fin)
    gastos_f = filtrar_rango_fechas(gastos, fecha_inicio, fecha_fin)
    perdidas_f = filtrar_rango_fechas(perdidas, fecha_inicio, fecha_fin)
    gastos_dueno_f = filtrar_rango_fechas(gastos_dueno, fecha_inicio, fecha_fin)
    cierre_f = filtrar_rango_fechas(cierre_caja, fecha_inicio, fecha_fin)

    ventas_totales = suma_segura(ventas_f, "total")
    compras_totales = suma_segura(compras_f, "monto")
    gastos_totales = suma_segura(gastos_f, "monto")
    perdidas_totales = suma_segura(perdidas_f, "valor")
    retiros_totales = suma_segura(gastos_dueno_f, "monto")

    gastos_fijos = 0.0
    gastos_variables = 0.0

    if not gastos_f.empty and "tipo" in gastos_f.columns:
        gf = gastos_f[gastos_f["tipo"].astype(str).str.lower().str.strip() == "fijo"]
        gv = gastos_f[gastos_f["tipo"].astype(str).str.lower().str.strip() == "variable"]
        gastos_fijos = suma_segura(gf, "monto")
        gastos_variables = suma_segura(gv, "monto")
    else:
        gastos_variables = gastos_totales
        st.info("La tabla gastos no tiene columna 'tipo'. Por ahora todos los gastos se toman como generales/variables.")

    st.markdown("### Utilidad")
    utilidad_bruta_manual = st.number_input(
        "Utilidad bruta (la colocas tú manualmente)",
        min_value=0.0,
        step=1.0,
        key="utilidad_bruta_manual"
    )

    utilidad_neta = float(utilidad_bruta_manual) - float(gastos_fijos) - float(gastos_variables) - float(perdidas_totales)
    porcentaje_dueno = utilidad_neta * 0.65
    porcentaje_gerente = utilidad_neta * 0.35

    m1, m2, m3 = st.columns(3)
    m1.metric("Ventas totales", f"RD$ {ventas_totales:,.2f}")
    m2.metric("Compras totales", f"RD$ {compras_totales:,.2f}")
    m3.metric("Gastos totales", f"RD$ {gastos_totales:,.2f}")

    m4, m5, m6 = st.columns(3)
    m4.metric("Pérdidas totales", f"RD$ {perdidas_totales:,.2f}")
    m5.metric("Retiros del dueño", f"RD$ {retiros_totales:,.2f}")
    m6.metric("Utilidad bruta manual", f"RD$ {utilidad_bruta_manual:,.2f}")

    m7, m8, m9 = st.columns(3)
    m7.metric("Gastos fijos", f"RD$ {gastos_fijos:,.2f}")
    m8.metric("Gastos variables", f"RD$ {gastos_variables:,.2f}")
    m9.metric("Utilidad neta", f"RD$ {utilidad_neta:,.2f}")

    m10, m11 = st.columns(2)
    m10.metric("65% dueño", f"RD$ {porcentaje_dueno:,.2f}")
    m11.metric("35% gerente", f"RD$ {porcentaje_gerente:,.2f}")

    st.subheader("Últimas ventas")
    st.dataframe(ventas_f.tail(10), use_container_width=True)

    st.subheader("Últimos cierres de caja")
    st.dataframe(cierre_f.tail(10), use_container_width=True)

# =========================================================
# PRODUCTOS
# =========================================================
elif menu == "Productos":
    st.title("📦 Productos")

    with st.expander("📥 Subir Excel / CSV de productos"):
        st.write("Columnas esperadas: nombre, costo, precio, cantidad")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_productos")
        if archivo is not None:
            if st.button("Cargar archivo de productos"):
                subir_excel_a_tabla(
                    "productos",
                    ["nombre", "costo", "precio", "cantidad"],
                    archivo
                )
                st.rerun()

    with st.expander("➕ Agregar producto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="prod_nombre")
            costo = st.number_input("Costo", min_value=0.0, step=1.0, key="prod_costo")
        with c2:
            precio = st.number_input("Precio", min_value=0.0, step=1.0, key="prod_precio")
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, key="prod_cantidad")

        if st.button("Guardar producto"):
            if not nombre.strip():
                st.warning("Debes escribir el nombre del producto.")
            else:
                ok = insertar_tabla(
                    "productos",
                    {
                        "nombre": nombre.strip(),
                        "costo": float(costo),
                        "precio": float(precio),
                        "cantidad": float(cantidad),
                    },
                )
                if ok:
                    st.success("Producto guardado correctamente.")
                    st.rerun()

    st.subheader("✏️ Editar o eliminar")
    if not productos.empty:
        opciones = productos["nombre"].fillna("").astype(str).unique()
        producto_sel = st.selectbox("Selecciona un producto", opciones, key="prod_sel")

        fila = productos[productos["nombre"].astype(str) == str(producto_sel)]
        if not fila.empty:
            row = fila.iloc[0]
            fila_id = int(row["id"])

            c1, c2 = st.columns(2)
            with c1:
                nombre_e = st.text_input("Nombre editado", value=str(row["nombre"]), key="prod_nombre_e")
                costo_e = st.number_input("Costo editado", value=float(row["costo"]), key="prod_costo_e")
            with c2:
                precio_e = st.number_input("Precio editado", value=float(row["precio"]), key="prod_precio_e")
                cantidad_e = st.number_input("Cantidad editada", value=float(row["cantidad"]), key="prod_cantidad_e")

            b1, b2 = st.columns(2)
            with b1:
                if st.button("Actualizar producto"):
                    ok = actualizar_tabla(
                        "productos",
                        fila_id,
                        {
                            "nombre": nombre_e.strip(),
                            "costo": float(costo_e),
                            "precio": float(precio_e),
                            "cantidad": float(cantidad_e),
                        },
                    )
                    if ok:
                        st.success("Producto actualizado.")
                        st.rerun()
            with b2:
                if st.button("Eliminar producto"):
                    ok = eliminar_tabla("productos", fila_id)
                    if ok:
                        st.success("Producto eliminado.")
                        st.rerun()

    mostrar_tabla_filtrada(productos, "📋 Listado", "productos_tabla", "productos.csv")

# =========================================================
# VENTAS
# =========================================================
elif menu == "Ventas":
    st.title("💰 Ventas")

    with st.expander("📥 Subir Excel / CSV de ventas"):
        st.write("Columnas esperadas: fecha, total, metodo")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_ventas")
        if archivo is not None:
            if st.button("Cargar archivo de ventas"):
                subir_excel_a_tabla(
                    "ventas",
                    ["fecha", "total", "metodo"],
                    archivo,
                    columnas_fecha=["fecha"]
                )
                st.rerun()

    with st.expander("➕ Registrar venta", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="venta_fecha")
        with c2:
            total = st.number_input("Total", min_value=0.0, step=1.0, key="venta_total")
        with c3:
            metodo = st.selectbox("Método", ["Efectivo", "Transferencia", "Tarjeta"], key="venta_metodo")

        if st.button("Guardar venta"):
            ok = insertar_tabla(
                "ventas",
                {
                    "fecha": str(fecha),
                    "total": float(total),
                    "metodo": metodo,
                },
            )
            if ok:
                st.success("Venta guardada correctamente.")
                st.rerun()

    if not ventas.empty:
        aux = ventas.copy()
        aux["texto"] = (
            aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | " + aux["total"].astype(str)
            + " | " + aux["metodo"].astype(str)
        )
        venta_sel = st.selectbox("Selecciona una venta", aux["texto"].tolist(), key="venta_sel")
        fila = aux[aux["texto"] == venta_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="venta_fecha_e")
        with c2:
            total_e = st.number_input("Total editado", value=float(fila["total"]), key="venta_total_e")
        with c3:
            metodos = ["Efectivo", "Transferencia", "Tarjeta"]
            idx = metodos.index(str(fila["metodo"])) if str(fila["metodo"]) in metodos else 0
            metodo_e = st.selectbox("Método editado", metodos, index=idx, key="venta_metodo_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar venta"):
                ok = actualizar_tabla(
                    "ventas",
                    fila_id,
                    {"fecha": str(fecha_e), "total": float(total_e), "metodo": metodo_e},
                )
                if ok:
                    st.success("Venta actualizada.")
                    st.rerun()
        with b2:
            if st.button("Eliminar venta"):
                ok = eliminar_tabla("ventas", fila_id)
                if ok:
                    st.success("Venta eliminada.")
                    st.rerun()

    mostrar_tabla_filtrada(ventas, "📋 Listado", "ventas_tabla", "ventas.csv")

# =========================================================
# COMPRAS
# =========================================================
elif menu == "Compras":
    st.title("🧾 Compras")

    with st.expander("📥 Subir Excel / CSV de compras"):
        st.write("Columnas esperadas: fecha, numero, proveedor, descripcion, monto, metodo")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_compras")
        if archivo is not None:
            if st.button("Cargar archivo de compras"):
                subir_excel_a_tabla(
                    "compras",
                    ["fecha", "numero", "proveedor", "descripcion", "monto", "metodo"],
                    archivo,
                    columnas_fecha=["fecha"]
                )
                st.rerun()

    with st.expander("➕ Registrar compra", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="compra_fecha")
            numero = st.text_input("Número / referencia", key="compra_numero")
            proveedor = st.text_input("Proveedor", key="compra_proveedor")
        with c2:
            descripcion = st.text_input("Descripción", key="compra_descripcion")
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="compra_monto")
            metodo = st.selectbox("Método", ["Efectivo", "Transferencia", "Tarjeta"], key="compra_metodo")

        if st.button("Guardar compra"):
            ok = insertar_tabla(
                "compras",
                {
                    "fecha": str(fecha),
                    "numero": numero.strip(),
                    "proveedor": proveedor.strip(),
                    "descripcion": descripcion.strip(),
                    "monto": float(monto),
                    "metodo": metodo,
                },
            )
            if ok:
                st.success("Compra guardada correctamente.")
                st.rerun()

    if not compras.empty:
        aux = compras.copy()
        aux["texto"] = (
            aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | " + aux["proveedor"].astype(str)
            + " | " + aux["monto"].astype(str)
        )
        compra_sel = st.selectbox("Selecciona una compra", aux["texto"].tolist(), key="compra_sel")
        fila = aux[aux["texto"] == compra_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="compra_fecha_e")
            numero_e = st.text_input("Número editado", value=str(fila["numero"]), key="compra_numero_e")
            proveedor_e = st.text_input("Proveedor editado", value=str(fila["proveedor"]), key="compra_proveedor_e")
        with c2:
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="compra_descripcion_e")
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="compra_monto_e")
            metodos = ["Efectivo", "Transferencia", "Tarjeta"]
            idx = metodos.index(str(fila["metodo"])) if str(fila["metodo"]) in metodos else 0
            metodo_e = st.selectbox("Método editado", metodos, index=idx, key="compra_metodo_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar compra"):
                ok = actualizar_tabla(
                    "compras",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "numero": numero_e.strip(),
                        "proveedor": proveedor_e.strip(),
                        "descripcion": descripcion_e.strip(),
                        "monto": float(monto_e),
                        "metodo": metodo_e,
                    },
                )
                if ok:
                    st.success("Compra actualizada.")
                    st.rerun()
        with b2:
            if st.button("Eliminar compra"):
                ok = eliminar_tabla("compras", fila_id)
                if ok:
                    st.success("Compra eliminada.")
                    st.rerun()

    mostrar_tabla_filtrada(compras, "📋 Listado", "compras_tabla", "compras.csv")

# =========================================================
# GASTOS
# =========================================================
elif menu == "Gastos":
    st.title("💸 Gastos")

    with st.expander("📥 Subir Excel / CSV de gastos"):
        columnas = ["fecha", "descripcion", "monto"]
        if TIENE_TIPO_GASTO:
            columnas.append("tipo")

        st.write(f"Columnas esperadas: {', '.join(columnas)}")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_gastos")
        if archivo is not None:
            if st.button("Cargar archivo de gastos"):
                subir_excel_a_tabla(
                    "gastos",
                    columnas,
                    archivo,
                    columnas_fecha=["fecha"]
                )
                st.rerun()

    with st.expander("➕ Registrar gasto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="gasto_fecha")
            descripcion = st.text_input("Descripción", key="gasto_descripcion")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="gasto_monto")

        datos = {
            "fecha": str(fecha),
            "descripcion": descripcion.strip(),
            "monto": float(monto),
        }

        if TIENE_TIPO_GASTO:
            tipo = st.selectbox("Tipo de gasto", ["fijo", "variable"], key="gasto_tipo")
            datos["tipo"] = tipo
        else:
            st.info("Si quieres separar gastos fijos y variables, agrega la columna 'tipo' a la tabla gastos.")

        if st.button("Guardar gasto"):
            ok = insertar_tabla("gastos", datos)
            if ok:
                st.success("Gasto guardado correctamente.")
                st.rerun()

    if not gastos.empty:
        aux = gastos.copy()
        aux["texto"] = (
            aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | " + aux["descripcion"].astype(str)
            + " | " + aux["monto"].astype(str)
        )
        gasto_sel = st.selectbox("Selecciona un gasto", aux["texto"].tolist(), key="gasto_sel")
        fila = aux[aux["texto"] == gasto_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="gasto_fecha_e")
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="gasto_descripcion_e")
        with c2:
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="gasto_monto_e")

        datos_e = {
            "fecha": str(fecha_e),
            "descripcion": descripcion_e.strip(),
            "monto": float(monto_e),
        }

        if "tipo" in fila.index:
            tipo_actual = str(fila["tipo"]) if pd.notna(fila["tipo"]) else "variable"
            idx_tipo = 0 if tipo_actual == "fijo" else 1
            tipo_e = st.selectbox("Tipo de gasto editado", ["fijo", "variable"], index=idx_tipo, key="gasto_tipo_e")
            datos_e["tipo"] = tipo_e

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar gasto"):
                ok = actualizar_tabla("gastos", fila_id, datos_e)
                if ok:
                    st.success("Gasto actualizado.")
                    st.rerun()
        with b2:
            if st.button("Eliminar gasto"):
                ok = eliminar_tabla("gastos", fila_id)
                if ok:
                    st.success("Gasto eliminado.")
                    st.rerun()

    mostrar_tabla_filtrada(gastos, "📋 Listado", "gastos_tabla", "gastos.csv")

# =========================================================
# PÉRDIDAS
# =========================================================
elif menu == "Pérdidas":
    st.title("📉 Pérdidas")

    with st.expander("📥 Subir Excel / CSV de pérdidas"):
        st.write("Columnas esperadas: fecha, producto, cantidad, valor")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_perdidas")
        if archivo is not None:
            if st.button("Cargar archivo de pérdidas"):
                subir_excel_a_tabla(
                    "perdidas",
                    ["fecha", "producto", "cantidad", "valor"],
                    archivo,
                    columnas_fecha=["fecha"]
                )
                st.rerun()

    with st.expander("➕ Registrar pérdida", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="perdida_fecha")
            lista_productos = productos["nombre"].astype(str).tolist() if not productos.empty else [""]
            producto = st.selectbox("Producto", lista_productos, key="perdida_producto")
        with c2:
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, key="perdida_cantidad")
            valor = st.number_input("Valor", min_value=0.0, step=1.0, key="perdida_valor")

        if st.button("Guardar pérdida"):
            ok = insertar_tabla(
                "perdidas",
                {
                    "fecha": str(fecha),
                    "producto": str(producto),
                    "cantidad": float(cantidad),
                    "valor": float(valor),
                },
            )
            if ok:
                st.success("Pérdida guardada correctamente.")
                st.rerun()

    if not perdidas.empty:
        aux = perdidas.copy()
        aux["texto"] = (
            aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | " + aux["producto"].astype(str)
            + " | " + aux["valor"].astype(str)
        )
        perdida_sel = st.selectbox("Selecciona una pérdida", aux["texto"].tolist(), key="perdida_sel")
        fila = aux[aux["texto"] == perdida_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="perdida_fecha_e")
            lista_productos = productos["nombre"].astype(str).tolist() if not productos.empty else [""]
            idx_prod = lista_productos.index(str(fila["producto"])) if str(fila["producto"]) in lista_productos else 0
            producto_e = st.selectbox("Producto editado", lista_productos, index=idx_prod, key="perdida_producto_e")
        with c2:
            cantidad_e = st.number_input("Cantidad editada", value=float(fila["cantidad"]), key="perdida_cantidad_e")
            valor_e = st.number_input("Valor editado", value=float(fila["valor"]), key="perdida_valor_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar pérdida"):
                ok = actualizar_tabla(
                    "perdidas",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "producto": str(producto_e),
                        "cantidad": float(cantidad_e),
                        "valor": float(valor_e),
                    },
                )
                if ok:
                    st.success("Pérdida actualizada.")
                    st.rerun()
        with b2:
            if st.button("Eliminar pérdida"):
                ok = eliminar_tabla("perdidas", fila_id)
                if ok:
                    st.success("Pérdida eliminada.")
                    st.rerun()

    mostrar_tabla_filtrada(perdidas, "📋 Listado", "perdidas_tabla", "perdidas.csv")

# =========================================================
# GASTOS DUEÑO
# =========================================================
elif menu == "Gastos Dueño":
    st.title("🏦 Gastos del dueño / retiros")

    with st.expander("📥 Subir Excel / CSV de gastos del dueño"):
        st.write("Columnas esperadas: fecha, descripcion, monto")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_dueno")
        if archivo is not None:
            if st.button("Cargar archivo de gastos del dueño"):
                subir_excel_a_tabla(
                    "gastos_dueno",
                    ["fecha", "descripcion", "monto"],
                    archivo,
                    columnas_fecha=["fecha"]
                )
                st.rerun()

    with st.expander("➕ Registrar retiro", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="dueno_fecha")
            descripcion = st.text_input("Descripción", key="dueno_descripcion")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="dueno_monto")

        if st.button("Guardar gasto del dueño"):
            ok = insertar_tabla(
                "gastos_dueno",
                {
                    "fecha": str(fecha),
                    "descripcion": descripcion.strip(),
                    "monto": float(monto),
                },
            )
            if ok:
                st.success("Gasto del dueño guardado correctamente.")
                st.rerun()

    if not gastos_dueno.empty:
        aux = gastos_dueno.copy()
        aux["texto"] = (
            aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | " + aux["descripcion"].astype(str)
            + " | " + aux["monto"].astype(str)
        )
        gd_sel = st.selectbox("Selecciona un gasto del dueño", aux["texto"].tolist(), key="dueno_sel")
        fila = aux[aux["texto"] == gd_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="dueno_fecha_e")
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="dueno_descripcion_e")
        with c2:
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="dueno_monto_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar gasto del dueño"):
                ok = actualizar_tabla(
                    "gastos_dueno",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "descripcion": descripcion_e.strip(),
                        "monto": float(monto_e),
                    },
                )
                if ok:
                    st.success("Gasto del dueño actualizado.")
                    st.rerun()
        with b2:
            if st.button("Eliminar gasto del dueño"):
                ok = eliminar_tabla("gastos_dueno", fila_id)
                if ok:
                    st.success("Gasto del dueño eliminado.")
                    st.rerun()

    mostrar_tabla_filtrada(gastos_dueno, "📋 Listado", "dueno_tabla", "gastos_dueno.csv")

# =========================================================
# EMPLEADOS
# =========================================================
elif menu == "Empleados":
    st.title("👥 Empleados")

    with st.expander("📥 Subir Excel / CSV de empleados"):
        st.write("Columnas esperadas: nombre, cargo, sueldo, tipo_pago, metodo_pago")
        archivo = st.file_uploader("Sube el archivo", type=["xlsx", "xls", "csv"], key="up_empleados")
        if archivo is not None:
            if st.button("Cargar archivo de empleados"):
                subir_excel_a_tabla(
                    "empleados",
                    ["nombre", "cargo", "sueldo", "tipo_pago", "metodo_pago"],
                    archivo
                )
                st.rerun()

    with st.expander("➕ Agregar empleado", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="emp_nombre")
            cargo = st.text_input("Cargo", key="emp_cargo")
            sueldo = st.number_input("Sueldo", min_value=0.0, step=1.0, key="emp_sueldo")
        with c2:
            tipo_pago = st.selectbox("Tipo de pago", ["Quincenal", "Mensual", "Variable"], key="emp_tipo_pago")
            metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Cheque"], key="emp_metodo_pago")

        if st.button("Guardar empleado"):
            ok = insertar_tabla(
                "empleados",
                {
                    "nombre": nombre.strip(),
                    "cargo": cargo.strip(),
                    "sueldo": float(sueldo),
                    "tipo_pago": tipo_pago,
                    "metodo_pago": metodo_pago,
                },
            )
            if ok:
                st.success("Empleado guardado correctamente.")
                st.rerun()

    if not empleados.empty:
        emp_sel = st.selectbox("Selecciona un empleado", empleados["nombre"].astype(str).tolist(), key="emp_sel")
        fila = empleados[empleados["nombre"].astype(str) == str(emp_sel)].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            nombre_e = st.text_input("Nombre editado", value=str(fila["nombre"]), key="emp_nombre_e")
            cargo_e = st.text_input("Cargo editado", value=str(fila["cargo"]), key="emp_cargo_e")
            sueldo_e = st.number_input("Sueldo editado", value=float(fila["sueldo"]), key="emp_sueldo_e")
        with c2:
            tipos = ["Quincenal", "Mensual", "Variable"]
            metodos = ["Efectivo", "Transferencia", "Cheque"]
            idx_t = tipos.index(str(fila["tipo_pago"])) if str(fila["tipo_pago"]) in tipos else 0
            idx_m = metodos.index(str(fila["metodo_pago"])) if str(fila["metodo_pago"]) in metodos else 0
            tipo_pago_e = st.selectbox("Tipo de pago editado", tipos, index=idx_t, key="emp_tipo_pago_e")
            metodo_pago_e = st.selectbox("Método de pago editado", metodos, index=idx_m, key="emp_metodo_pago_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar empleado"):
                ok = actualizar_tabla(
                    "empleados",
                    fila_id,
                    {
                        "nombre": nombre_e.strip(),
                        "cargo": cargo_e.strip(),
                        "sueldo": float(sueldo_e),
                        "tipo_pago": tipo_pago_e,
                        "metodo_pago": metodo_pago_e,
                    },
                )
                if ok:
                    st.success("Empleado actualizado.")
                    st.rerun()
        with b2:
            if st.button("Eliminar empleado"):
                ok = eliminar_tabla("empleados", fila_id)
                if ok:
                    st.success("Empleado eliminado.")
                    st.rerun()

    mostrar_tabla_filtrada(empleados, "📋 Listado", "empleados_tabla", "empleados.csv")

# =========================================================
# CIERRE DE CAJA
# =========================================================
elif menu == "Cierre de Caja":
    st.title("💵 Cierre de Caja")

    fecha_cierre = st.date_input("Fecha del cierre", value=date.today(), key="cc_fecha")
    fecha_dt = pd.to_datetime(fecha_cierre)

    ventas_dia = ventas[ventas["fecha"].dt.date == fecha_dt.date()] if not ventas.empty else pd.DataFrame()
    compras_dia = compras[compras["fecha"].dt.date == fecha_dt.date()] if not compras.empty else pd.DataFrame()
    gastos_dia = gastos[gastos["fecha"].dt.date == fecha_dt.date()] if not gastos.empty else pd.DataFrame()
    perdidas_dia = perdidas[perdidas["fecha"].dt.date == fecha_dt.date()] if not perdidas.empty else pd.DataFrame()
    dueno_dia = gastos_dueno[gastos_dueno["fecha"].dt.date == fecha_dt.date()] if not gastos_dueno.empty else pd.DataFrame()

    monto_sistema = (
        suma_segura(ventas_dia, "total")
        - suma_segura(compras_dia, "monto")
        - suma_segura(gastos_dia, "monto")
        - suma_segura(perdidas_dia, "valor")
        - suma_segura(dueno_dia, "monto")
    )

    st.metric("Monto sistema", f"RD$ {monto_sistema:,.2f}")

    monto_real = st.number_input("Monto real contado", min_value=0.0, step=1.0, key="cc_monto_real")
    diferencia = float(monto_real) - float(monto_sistema)

    st.metric("Diferencia", f"RD$ {diferencia:,.2f}")

    if st.button("Guardar cierre de caja"):
        ok = insertar_tabla(
            "cierre_caja",
            {
                "fecha": str(fecha_cierre),
                "monto_sistema": float(monto_sistema),
                "monto_real": float(monto_real),
                "diferencia": float(diferencia),
            },
        )
        if ok:
            st.success("Cierre de caja guardado correctamente.")
            st.rerun()

    mostrar_tabla_filtrada(cierre_caja, "📋 Historial", "cierre_tabla", "cierre_caja.csv")

# =========================================================
# ESTADO DE RESULTADOS
# =========================================================
elif menu == "Estado de Resultados":
    st.title("📈 Estado de Resultados")

    c1, c2 = st.columns(2)
    with c1:
        fecha_inicio = st.date_input("Desde", value=date.today().replace(day=1), key="er_desde")
    with c2:
        fecha_fin = st.date_input("Hasta", value=date.today(), key="er_hasta")

    ventas_f = filtrar_rango_fechas(ventas, fecha_inicio, fecha_fin)
    compras_f = filtrar_rango_fechas(compras, fecha_inicio, fecha_fin)
    gastos_f = filtrar_rango_fechas(gastos, fecha_inicio, fecha_fin)
    perdidas_f = filtrar_rango_fechas(perdidas, fecha_inicio, fecha_fin)

    ventas_totales = suma_segura(ventas_f, "total")
    compras_totales = suma_segura(compras_f, "monto")
    gastos_totales = suma_segura(gastos_f, "monto")
    perdidas_totales = suma_segura(perdidas_f, "valor")

    gastos_fijos = 0.0
    gastos_variables = 0.0
    if not gastos_f.empty and "tipo" in gastos_f.columns:
        gf = gastos_f[gastos_f["tipo"].astype(str).str.lower().str.strip() == "fijo"]
        gv = gastos_f[gastos_f["tipo"].astype(str).str.lower().str.strip() == "variable"]
        gastos_fijos = suma_segura(gf, "monto")
        gastos_variables = suma_segura(gv, "monto")
    else:
        gastos_variables = gastos_totales

    utilidad_bruta_manual = st.number_input(
        "Utilidad bruta (la colocas tú)",
        min_value=0.0,
        step=1.0,
        key="er_util_bruta"
    )
    utilidad_neta = float(utilidad_bruta_manual) - float(gastos_fijos) - float(gastos_variables) - float(perdidas_totales)
    dueno_65 = utilidad_neta * 0.65
    gerente_35 = utilidad_neta * 0.35

    m1, m2, m3 = st.columns(3)
    m1.metric("Ventas", f"RD$ {ventas_totales:,.2f}")
    m2.metric("Compras", f"RD$ {compras_totales:,.2f}")
    m3.metric("Gastos", f"RD$ {gastos_totales:,.2f}")

    m4, m5, m6 = st.columns(3)
    m4.metric("Pérdidas", f"RD$ {perdidas_totales:,.2f}")
    m5.metric("Gastos fijos", f"RD$ {gastos_fijos:,.2f}")
    m6.metric("Gastos variables", f"RD$ {gastos_variables:,.2f}")

    m7, m8, m9 = st.columns(3)
    m7.metric("Utilidad bruta", f"RD$ {utilidad_bruta_manual:,.2f}")
    m8.metric("Utilidad neta", f"RD$ {utilidad_neta:,.2f}")
    m9.metric("65% dueño", f"RD$ {dueno_65:,.2f}")

    st.metric("35% gerente", f"RD$ {gerente_35:,.2f}")

    if st.button("Guardar estado de resultados"):
        datos = {
            "fecha": str(fecha_fin),
            "ventas": float(ventas_totales),
            "compras": float(compras_totales),
            "gastos": float(gastos_totales),
            "perdidas": float(perdidas_totales),
            "utilidad": float(utilidad_neta),
        }
        ok = insertar_tabla("estado_resultados", datos)
        if ok:
            st.success("Estado de resultados guardado correctamente.")
            st.rerun()

    mostrar_tabla_filtrada(estado_resultados, "📋 Historial", "estado_resultados_tabla", "estado_resultados.csv")
