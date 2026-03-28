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
    st.error(
        "Faltan las credenciales de Supabase en .streamlit/secrets.toml. "
        "Debes agregar SUPABASE_URL y SUPABASE_KEY."
    )
    st.code(
        'SUPABASE_URL = "https://TU-PROYECTO.supabase.co"\n'
        'SUPABASE_KEY = "TU_CLAVE_PUBLICABLE"\n'
        'APP_PASSWORD = "1234"',
        language="toml",
    )
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"No se pudo conectar con Supabase: {e}")
    st.stop()

# =========================================================
# SEGURIDAD SIMPLE
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
# FUNCIONES GENERALES
# =========================================================
def leer_tabla(nombre_tabla: str) -> pd.DataFrame:
    try:
        resp = supabase.table(nombre_tabla).select("*").order("id").execute()
        data = resp.data if resp.data else []
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al leer la tabla {nombre_tabla}: {e}")
        return pd.DataFrame()


def insertar_tabla(nombre_tabla: str, datos: dict) -> bool:
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        return True
    except Exception as e:
        st.error(f"Error al insertar en {nombre_tabla}: {e}")
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


def filtrar_busqueda(df: pd.DataFrame, key_busqueda: str) -> pd.DataFrame:
    if df.empty:
        return df

    busqueda = st.text_input("Buscar", key=key_busqueda)
    if not busqueda:
        return df

    mask = df.astype(str).apply(
        lambda x: x.str.contains(busqueda, case=False, na=False)
    ).any(axis=1)
    return df[mask]


def descargar_csv(df: pd.DataFrame, nombre_archivo: str):
    if df.empty:
        st.info("No hay datos para descargar.")
        return

    datos = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar CSV",
        data=datos,
        file_name=nombre_archivo,
        mime="text/csv",
    )


def refrescar():
    st.rerun()


# =========================================================
# CARGAR DATOS DESDE LA NUBE
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

# =========================================================
# MENÚ
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

if st.sidebar.button("🔄 Recargar datos"):
    refrescar()

# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Dashboard")

    total_ventas = suma_segura(ventas, "total")
    total_compras = suma_segura(compras, "monto")
    total_gastos = suma_segura(gastos, "monto")
    total_perdidas = suma_segura(perdidas, "valor")
    total_dueno = suma_segura(gastos_dueno, "monto")
    utilidad_estimada = total_ventas - total_compras - total_gastos - total_perdidas - total_dueno

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas", f"RD$ {total_ventas:,.2f}")
    c2.metric("Compras", f"RD$ {total_compras:,.2f}")
    c3.metric("Gastos", f"RD$ {total_gastos:,.2f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Pérdidas", f"RD$ {total_perdidas:,.2f}")
    c5.metric("Retiros dueño", f"RD$ {total_dueno:,.2f}")
    c6.metric("Utilidad estimada", f"RD$ {utilidad_estimada:,.2f}")

    st.subheader("Últimas ventas")
    if ventas.empty:
        st.info("No hay ventas registradas.")
    else:
        st.dataframe(ventas.tail(10), use_container_width=True)

    st.subheader("Últimos cierres de caja")
    if cierre_caja.empty:
        st.info("No hay cierres de caja registrados.")
    else:
        st.dataframe(cierre_caja.tail(10), use_container_width=True)

# =========================================================
# PRODUCTOS
# =========================================================
elif menu == "Productos":
    st.title("📦 Productos")

    with st.expander("➕ Agregar producto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre del producto", key="prod_nombre")
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
                    refrescar()

    st.subheader("✏️ Editar o eliminar producto")
    if not productos.empty:
        nombres = productos["nombre"].fillna("").astype(str)
        producto_sel = st.selectbox("Selecciona un producto", nombres.unique(), key="prod_sel")

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
                        refrescar()

            with b2:
                if st.button("Eliminar producto"):
                    ok = eliminar_tabla("productos", fila_id)
                    if ok:
                        st.success("Producto eliminado.")
                        refrescar()

    st.subheader("📋 Listado de productos")
    productos_f = filtrar_busqueda(productos, "busc_prod")
    st.dataframe(productos_f, use_container_width=True)
    descargar_csv(productos_f, "productos.csv")

# =========================================================
# VENTAS
# =========================================================
elif menu == "Ventas":
    st.title("💰 Ventas")

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
                refrescar()

    st.subheader("✏️ Editar o eliminar venta")
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
            opciones_metodo = ["Efectivo", "Transferencia", "Tarjeta"]
            idx_met = opciones_metodo.index(str(fila["metodo"])) if str(fila["metodo"]) in opciones_metodo else 0
            metodo_e = st.selectbox("Método editado", opciones_metodo, index=idx_met, key="venta_metodo_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar venta"):
                ok = actualizar_tabla(
                    "ventas",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "total": float(total_e),
                        "metodo": metodo_e,
                    },
                )
                if ok:
                    st.success("Venta actualizada.")
                    refrescar()
        with b2:
            if st.button("Eliminar venta"):
                ok = eliminar_tabla("ventas", fila_id)
                if ok:
                    st.success("Venta eliminada.")
                    refrescar()

    st.subheader("📋 Listado de ventas")
    ventas_f = filtrar_busqueda(ventas, "busc_ventas")
    st.dataframe(ventas_f, use_container_width=True)
    descargar_csv(ventas_f, "ventas.csv")

# =========================================================
# COMPRAS
# =========================================================
elif menu == "Compras":
    st.title("🧾 Compras")

    with st.expander("➕ Registrar compra", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="compra_fecha")
            numero = st.text_input("Número / referencia", key="compra_numero")
            proveedor = st.text_input("Proveedor", key="compra_proveedor")
        with c2:
            descripcion = st.text_input("Descripción", key="compra_desc")
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
                refrescar()

    st.subheader("✏️ Editar o eliminar compra")
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
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="compra_desc_e")
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="compra_monto_e")
            opciones_met = ["Efectivo", "Transferencia", "Tarjeta"]
            idx_m = opciones_met.index(str(fila["metodo"])) if str(fila["metodo"]) in opciones_met else 0
            metodo_e = st.selectbox("Método editado", opciones_met, index=idx_m, key="compra_metodo_e")

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
                    refrescar()
        with b2:
            if st.button("Eliminar compra"):
                ok = eliminar_tabla("compras", fila_id)
                if ok:
                    st.success("Compra eliminada.")
                    refrescar()

    st.subheader("📋 Listado de compras")
    compras_f = filtrar_busqueda(compras, "busc_compras")
    st.dataframe(compras_f, use_container_width=True)
    descargar_csv(compras_f, "compras.csv")

# =========================================================
# GASTOS
# =========================================================
elif menu == "Gastos":
    st.title("💸 Gastos")

    with st.expander("➕ Registrar gasto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="gasto_fecha")
            descripcion = st.text_input("Descripción", key="gasto_desc")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="gasto_monto")

        if st.button("Guardar gasto"):
            ok = insertar_tabla(
                "gastos",
                {
                    "fecha": str(fecha),
                    "descripcion": descripcion.strip(),
                    "monto": float(monto),
                },
            )
            if ok:
                st.success("Gasto guardado correctamente.")
                refrescar()

    st.subheader("✏️ Editar o eliminar gasto")
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
        with c2:
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="gasto_monto_e")

        descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="gasto_desc_e")

        b1, b2 = st.columns(2)
        with b1:
            if st.button("Actualizar gasto"):
                ok = actualizar_tabla(
                    "gastos",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "descripcion": descripcion_e.strip(),
                        "monto": float(monto_e),
                    },
                )
                if ok:
                    st.success("Gasto actualizado.")
                    refrescar()
        with b2:
            if st.button("Eliminar gasto"):
                ok = eliminar_tabla("gastos", fila_id)
                if ok:
                    st.success("Gasto eliminado.")
                    refrescar()

    st.subheader("📋 Listado de gastos")
    gastos_f = filtrar_busqueda(gastos, "busc_gastos")
    st.dataframe(gastos_f, use_container_width=True)
    descargar_csv(gastos_f, "gastos.csv")

# =========================================================
# PÉRDIDAS
# =========================================================
elif menu == "Pérdidas":
    st.title("📉 Pérdidas")

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
                refrescar()

    st.subheader("✏️ Editar o eliminar pérdida")
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
                    refrescar()
        with b2:
            if st.button("Eliminar pérdida"):
                ok = eliminar_tabla("perdidas", fila_id)
                if ok:
                    st.success("Pérdida eliminada.")
                    refrescar()

    st.subheader("📋 Listado de pérdidas")
    perdidas_f = filtrar_busqueda(perdidas, "busc_perdidas")
    st.dataframe(perdidas_f, use_container_width=True)
    descargar_csv(perdidas_f, "perdidas.csv")

# =========================================================
# GASTOS DUEÑO
# =========================================================
elif menu == "Gastos Dueño":
    st.title("🏦 Gastos del dueño")

    with st.expander("➕ Registrar retiro / gasto del dueño", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="dueno_fecha")
            descripcion = st.text_input("Descripción", key="dueno_desc")
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
                refrescar()

    st.subheader("✏️ Editar o eliminar gasto del dueño")
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
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="dueno_desc_e")
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
                    refrescar()
        with b2:
            if st.button("Eliminar gasto del dueño"):
                ok = eliminar_tabla("gastos_dueno", fila_id)
                if ok:
                    st.success("Gasto del dueño eliminado.")
                    refrescar()

    st.subheader("📋 Listado")
    gd_f = filtrar_busqueda(gastos_dueno, "busc_dueno")
    st.dataframe(gd_f, use_container_width=True)
    descargar_csv(gd_f, "gastos_dueno.csv")

# =========================================================
# EMPLEADOS
# =========================================================
elif menu == "Empleados":
    st.title("👥 Empleados")

    with st.expander("➕ Agregar empleado", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="emp_nombre")
            cargo = st.text_input("Cargo", key="emp_cargo")
            sueldo = st.number_input("Sueldo", min_value=0.0, step=1.0, key="emp_sueldo")
        with c2:
            tipo_pago = st.selectbox("Tipo de pago", ["Quincenal", "Mensual", "Variable"], key="emp_tipo")
            metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Cheque"], key="emp_metodo")

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
                refrescar()

    st.subheader("✏️ Editar o eliminar empleado")
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
            idx_tipo = tipos.index(str(fila["tipo_pago"])) if str(fila["tipo_pago"]) in tipos else 0
            idx_metodo = metodos.index(str(fila["metodo_pago"])) if str(fila["metodo_pago"]) in metodos else 0
            tipo_pago_e = st.selectbox("Tipo de pago editado", tipos, index=idx_tipo, key="emp_tipo_e")
            metodo_pago_e = st.selectbox("Método de pago editado", metodos, index=idx_metodo, key="emp_metodo_e")

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
                    refrescar()
        with b2:
            if st.button("Eliminar empleado"):
                ok = eliminar_tabla("empleados", fila_id)
                if ok:
                    st.success("Empleado eliminado.")
                    refrescar()

    st.subheader("📋 Listado de empleados")
    empleados_f = filtrar_busqueda(empleados, "busc_empleados")
    st.dataframe(empleados_f, use_container_width=True)
    descargar_csv(empleados_f, "empleados.csv")

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

    monto_real = st.number_input("Monto real contado", min_value=0.0, step=1.0, key="cc_real")
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
            refrescar()

    st.subheader("📋 Historial de cierres")
    cierre_f = filtrar_busqueda(cierre_caja, "busc_cierre")
    st.dataframe(cierre_f, use_container_width=True)
    descargar_csv(cierre_f, "cierre_caja.csv")

# =========================================================
# ESTADO DE RESULTADOS
# =========================================================
elif menu == "Estado de Resultados":
    st.title("📈 Estado de Resultados")

    c1, c2 = st.columns(2)
    with c1:
        fecha_desde = st.date_input("Desde", value=date.today().replace(day=1), key="er_desde")
    with c2:
        fecha_hasta = st.date_input("Hasta", value=date.today(), key="er_hasta")

    desde = pd.to_datetime(fecha_desde)
    hasta = pd.to_datetime(fecha_hasta)

    def filtrar_rango(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "fecha" not in df.columns:
            return pd.DataFrame()
        return df[(df["fecha"] >= desde) & (df["fecha"] <= hasta)]

    ventas_r = filtrar_rango(ventas)
    compras_r = filtrar_rango(compras)
    gastos_r = filtrar_rango(gastos)
    perdidas_r = filtrar_rango(perdidas)

    total_ventas = suma_segura(ventas_r, "total")
    total_compras = suma_segura(compras_r, "monto")
    total_gastos = suma_segura(gastos_r, "monto")
    total_perdidas = suma_segura(perdidas_r, "valor")
    utilidad = total_ventas - total_compras - total_gastos - total_perdidas

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas", f"RD$ {total_ventas:,.2f}")
    c2.metric("Compras", f"RD$ {total_compras:,.2f}")
    c3.metric("Gastos", f"RD$ {total_gastos:,.2f}")

    c4, c5 = st.columns(2)
    c4.metric("Pérdidas", f"RD$ {total_perdidas:,.2f}")
    c5.metric("Utilidad", f"RD$ {utilidad:,.2f}")

    if st.button("Guardar estado de resultados"):
        ok = insertar_tabla(
            "estado_resultados",
            {
                "fecha": str(fecha_hasta),
                "ventas": float(total_ventas),
                "compras": float(total_compras),
                "gastos": float(total_gastos),
                "perdidas": float(total_perdidas),
                "utilidad": float(utilidad),
            },
        )
        if ok:
            st.success("Estado de resultados guardado correctamente.")
            refrescar()

    st.subheader("📋 Historial")
    er_f = filtrar_busqueda(estado_resultados, "busc_er")
    st.dataframe(er_f, use_container_width=True)
    descargar_csv(er_f, "estado_resultados.csv")
