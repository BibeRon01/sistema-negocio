import streamlit as st
import pandas as pd
from supabase import create_client
from dashboard import mostrar_dashboard
import io

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# =================================================
# CONEXIÓN SUPABASE
# =================================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# =================================================
# FUNCIONES GENERALES
# =================================================
def convertir_fecha_segura(df, columna="fecha"):
    if not df.empty and columna in df.columns:
        df[columna] = pd.to_datetime(df[columna], errors="coerce")
    return df

def to_numeric_safe(df, columnas):
    for col in columnas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def obtener_df(tabla, columnas_esperadas):
    try:
        resp = supabase.table(tabla).select("*").order("id").execute()
        data = resp.data if resp.data else []
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame(columns=["id"] + columnas_esperadas)
        for col in ["fecha"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        return df
    except Exception as e:
        st.error(f"Error al cargar la tabla '{tabla}': {e}")
        return pd.DataFrame(columns=["id"] + columnas_esperadas)

def insertar_filas(tabla, registros):
    if not registros:
        return
    supabase.table(tabla).insert(registros).execute()

def actualizar_fila(tabla, fila_id, datos):
    supabase.table(tabla).update(datos).eq("id", fila_id).execute()

def eliminar_fila(tabla, fila_id):
    supabase.table(tabla).delete().eq("id", fila_id).execute()

def descargar_excel(df, nombre_archivo):
    if df.empty:
        st.warning("No hay datos para descargar.")
        return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    st.download_button(
        label="📥 Descargar Excel",
        data=output.getvalue(),
        file_name=nombre_archivo,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def filtrar_busqueda(df, key_name):
    if df.empty:
        st.info("No hay datos para mostrar.")
        return df
    busqueda = st.text_input("🔍 Buscar", key=key_name)
    if busqueda:
        df = df[
            df.astype(str)
            .apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1)
        ]
    return df

def subir_excel_a_supabase(tabla, archivo, columnas_requeridas, columnas_numericas=None, columnas_fecha=None):
    if archivo is None:
        return False

    columnas_numericas = columnas_numericas or []
    columnas_fecha = columnas_fecha or []

    try:
        df = pd.read_excel(archivo)
        df.columns = [str(c).strip().lower() for c in df.columns]

        faltantes = [c for c in columnas_requeridas if c not in df.columns]
        if faltantes:
            st.error(f"El archivo debe tener estas columnas: {columnas_requeridas}")
            return False

        df = df[columnas_requeridas].copy()

        for col in columnas_fecha:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        for col in columnas_numericas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        registros = df.to_dict(orient="records")
        insertar_filas(tabla, registros)
        st.success("Archivo cargado correctamente en la nube ☁️")
        return True

    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
        return False

# =================================================
# CARGA DESDE SUPABASE
# =================================================
productos = obtener_df("productos", ["nombre", "costo", "precio", "cantidad"])
ventas = obtener_df("ventas", ["fecha", "total", "metodo"])
compras = obtener_df("compras", ["fecha", "numero", "proveedor", "monto", "metodo"])
gastos = obtener_df("gastos", ["fecha", "tipo", "descripcion", "monto", "metodo"])
perdidas = obtener_df("perdidas", ["fecha", "producto", "cantidad", "valor"])
gastos_dueno = obtener_df("gastos_dueno", ["fecha", "descripcion", "monto", "metodo"])
empleados = obtener_df("empleados", ["nombre", "cargo", "sueldo", "tipo_pago", "metodo_pago"])
cierre_caja = obtener_df(
    "cierre_caja",
    [
        "fecha",
        "negocio_esperado",
        "banco_esperado",
        "negocio_real",
        "banco_real",
        "diferencia_negocio",
        "diferencia_banco",
        "diferencia_total",
        "estado",
        "observacion",
    ],
)

# Normalizar numéricos
productos = to_numeric_safe(productos, ["costo", "precio", "cantidad"])
ventas = to_numeric_safe(ventas, ["total"])
compras = to_numeric_safe(compras, ["monto"])
gastos = to_numeric_safe(gastos, ["monto"])
perdidas = to_numeric_safe(perdidas, ["cantidad", "valor"])
gastos_dueno = to_numeric_safe(gastos_dueno, ["monto"])
empleados = to_numeric_safe(empleados, ["sueldo"])
cierre_caja = to_numeric_safe(
    cierre_caja,
    [
        "negocio_esperado",
        "banco_esperado",
        "negocio_real",
        "banco_real",
        "diferencia_negocio",
        "diferencia_banco",
        "diferencia_total",
    ],
)

# =================================================
# MENÚ
# =================================================
st.title("💼 Sistema de Negocio")

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
    ],
)

# =================================================
# DASHBOARD
# =================================================
if menu == "Dashboard":
    mostrar_dashboard(ventas, gastos, compras, perdidas, gastos_dueno, cierre_caja)

# =================================================
# PRODUCTOS
# =================================================
elif menu == "Productos":
    st.header("📦 Productos")

    st.subheader("Subir productos por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de productos",
        type=["xlsx"],
        key="productos_excel"
    )
    if subir_excel_a_supabase(
        "productos",
        archivo_excel,
        ["nombre", "costo", "precio", "cantidad"],
        columnas_numericas=["costo", "precio", "cantidad"]
    ):
        st.rerun()

    st.subheader("Agregar producto manual")
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre del producto")
        costo = st.number_input("Costo", min_value=0.0, step=1.0)
    with col2:
        precio = st.number_input("Precio", min_value=0.0, step=1.0)
        cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)

    if st.button("Guardar producto"):
        if not nombre.strip():
            st.warning("Debes escribir el nombre del producto.")
        else:
            try:
                insertar_filas("productos", [{
                    "nombre": nombre.strip(),
                    "costo": float(costo),
                    "precio": float(precio),
                    "cantidad": float(cantidad),
                }])
                st.success("Producto guardado correctamente en la nube ☁️")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar producto")
    if not productos.empty:
        producto_sel = st.selectbox("Selecciona un producto", productos["nombre"].astype(str).unique(), key="editar_producto")
        fila = productos[productos["nombre"] == producto_sel].iloc[0]
        producto_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            nuevo_nombre = st.text_input("Nuevo nombre", value=str(fila["nombre"]), key="nuevo_nombre_producto")
            nuevo_costo = st.number_input("Nuevo costo", value=float(fila["costo"]), key="nuevo_costo_producto")
        with col2:
            nuevo_precio = st.number_input("Nuevo precio", value=float(fila["precio"]), key="nuevo_precio_producto")
            nueva_cantidad = st.number_input("Nueva cantidad", value=float(fila["cantidad"]), step=1.0, key="nueva_cantidad_producto")

        if st.button("Actualizar producto"):
            try:
                actualizar_fila("productos", producto_id, {
                    "nombre": nuevo_nombre.strip(),
                    "costo": float(nuevo_costo),
                    "precio": float(nuevo_precio),
                    "cantidad": float(nueva_cantidad),
                })
                st.success("Producto actualizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar producto"):
            try:
                eliminar_fila("productos", producto_id)
                st.success("Producto eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de productos")
    productos_filtrados = filtrar_busqueda(productos, "buscar_productos")
    st.dataframe(productos_filtrados, width="stretch")
    descargar_excel(productos_filtrados, "productos.xlsx")

# =================================================
# VENTAS
# =================================================
elif menu == "Ventas":
    st.header("💰 Ventas del día")

    st.subheader("Subir ventas por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de ventas",
        type=["xlsx"],
        key="ventas_excel"
    )
    if subir_excel_a_supabase(
        "ventas",
        archivo_excel,
        ["fecha", "total", "metodo"],
        columnas_numericas=["total"],
        columnas_fecha=["fecha"]
    ):
        st.rerun()

    st.subheader("Registrar venta diaria")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha = st.date_input("Fecha de la venta")
    with col2:
        total = st.number_input("Total de la venta del día", min_value=0.0, step=1.0)
    with col3:
        metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta"])

    if st.button("Guardar venta"):
        try:
            insertar_filas("ventas", [{
                "fecha": pd.to_datetime(fecha),
                "total": float(total),
                "metodo": metodo,
            }])
            st.success("Venta guardada correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar venta")
    if not ventas.empty:
        ventas_edit = ventas.copy()
        ventas_edit["texto"] = (
            ventas_edit["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + ventas_edit["total"].astype(str)
            + " | "
            + ventas_edit["metodo"].astype(str)
        )

        venta_sel = st.selectbox("Selecciona una venta", ventas_edit["texto"], key="editar_venta")
        idx = ventas_edit[ventas_edit["texto"] == venta_sel].index[0]
        fila = ventas.loc[idx]
        fila_id = int(fila["id"])

        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_venta")
        with col2:
            total_edit = st.number_input("Nuevo total", value=float(fila["total"]), key="total_edit_venta")
        with col3:
            metodo_edit = st.selectbox(
                "Nuevo método",
                ["Efectivo", "Transferencia", "Tarjeta"],
                index=["Efectivo", "Transferencia", "Tarjeta"].index(str(fila["metodo"])) if str(fila["metodo"]) in ["Efectivo", "Transferencia", "Tarjeta"] else 0,
                key="metodo_edit_venta"
            )

        if st.button("Actualizar venta"):
            try:
                actualizar_fila("ventas", fila_id, {
                    "fecha": pd.to_datetime(fecha_edit),
                    "total": float(total_edit),
                    "metodo": metodo_edit,
                })
                st.success("Venta actualizada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar venta"):
            try:
                eliminar_fila("ventas", fila_id)
                st.success("Venta eliminada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de ventas")
    ventas_filtradas = filtrar_busqueda(ventas, "buscar_ventas")
    st.dataframe(ventas_filtradas, width="stretch")
    descargar_excel(ventas_filtradas, "ventas.xlsx")

# =================================================
# COMPRAS
# =================================================
elif menu == "Compras":
    st.header("🧾 Compras")

    st.subheader("Subir compras por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de compras",
        type=["xlsx"],
        key="compras_excel"
    )
    if subir_excel_a_supabase(
        "compras",
        archivo_excel,
        ["fecha", "numero", "proveedor", "monto", "metodo"],
        columnas_numericas=["monto"],
        columnas_fecha=["fecha"]
    ):
        st.rerun()

    st.subheader("Registrar compra")
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha de la compra")
        numero = st.text_input("Número de compra")
        proveedor = st.text_input("Proveedor")
    with col2:
        monto = st.number_input("Monto total", min_value=0.0, step=1.0)
        metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta"], key="metodo_compra")

    if st.button("Guardar compra"):
        try:
            insertar_filas("compras", [{
                "fecha": pd.to_datetime(fecha),
                "numero": numero.strip(),
                "proveedor": proveedor.strip(),
                "monto": float(monto),
                "metodo": metodo,
            }])
            st.success("Compra guardada correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar compra")
    if not compras.empty:
        compras_edit = compras.copy()
        compras_edit["texto"] = (
            compras_edit["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + compras_edit["numero"].astype(str)
            + " | "
            + compras_edit["proveedor"].astype(str)
            + " | "
            + compras_edit["monto"].astype(str)
        )

        compra_sel = st.selectbox("Selecciona una compra", compras_edit["texto"], key="editar_compra")
        idx = compras_edit[compras_edit["texto"] == compra_sel].index[0]
        fila = compras.loc[idx]
        fila_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_compra")
            numero_edit = st.text_input("Nuevo número", value=str(fila["numero"]), key="numero_edit_compra")
            proveedor_edit = st.text_input("Nuevo proveedor", value=str(fila["proveedor"]), key="proveedor_edit_compra")
        with col2:
            monto_edit = st.number_input("Nuevo monto", value=float(fila["monto"]), key="monto_edit_compra")
            metodo_edit = st.selectbox(
                "Nuevo método",
                ["Efectivo", "Transferencia", "Tarjeta"],
                index=["Efectivo", "Transferencia", "Tarjeta"].index(str(fila["metodo"])) if str(fila["metodo"]) in ["Efectivo", "Transferencia", "Tarjeta"] else 0,
                key="metodo_edit_compra"
            )

        if st.button("Actualizar compra"):
            try:
                actualizar_fila("compras", fila_id, {
                    "fecha": pd.to_datetime(fecha_edit),
                    "numero": numero_edit.strip(),
                    "proveedor": proveedor_edit.strip(),
                    "monto": float(monto_edit),
                    "metodo": metodo_edit,
                })
                st.success("Compra actualizada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar compra"):
            try:
                eliminar_fila("compras", fila_id)
                st.success("Compra eliminada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de compras")
    compras_filtradas = filtrar_busqueda(compras, "buscar_compras")
    st.dataframe(compras_filtradas, width="stretch")
    descargar_excel(compras_filtradas, "compras.xlsx")

# =================================================
# GASTOS
# =================================================
elif menu == "Gastos":
    st.header("💸 Gastos")

    st.subheader("Subir gastos por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de gastos",
        type=["xlsx"],
        key="gastos_excel"
    )
    if subir_excel_a_supabase(
        "gastos",
        archivo_excel,
        ["fecha", "tipo", "descripcion", "monto", "metodo"],
        columnas_numericas=["monto"],
        columnas_fecha=["fecha"]
    ):
        st.rerun()

    st.subheader("Registrar gasto")
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha del gasto")
        tipo = st.selectbox("Tipo de gasto", ["Fijo", "Variable"])
        descripcion = st.text_input("Descripción")
    with col2:
        monto = st.number_input("Monto", min_value=0.0, step=1.0)
        metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta"], key="metodo_gasto")

    if st.button("Guardar gasto"):
        try:
            insertar_filas("gastos", [{
                "fecha": pd.to_datetime(fecha),
                "tipo": tipo,
                "descripcion": descripcion.strip(),
                "monto": float(monto),
                "metodo": metodo,
            }])
            st.success("Gasto guardado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar gasto")
    if not gastos.empty:
        gastos_edit = gastos.copy()
        gastos_edit["texto"] = (
            gastos_edit["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + gastos_edit["tipo"].astype(str)
            + " | "
            + gastos_edit["descripcion"].astype(str)
            + " | "
            + gastos_edit["monto"].astype(str)
        )

        gasto_sel = st.selectbox("Selecciona un gasto", gastos_edit["texto"], key="editar_gasto")
        idx = gastos_edit[gastos_edit["texto"] == gasto_sel].index[0]
        fila = gastos.loc[idx]
        fila_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_gasto")
            tipo_edit = st.selectbox(
                "Nuevo tipo",
                ["Fijo", "Variable"],
                index=["Fijo", "Variable"].index(str(fila["tipo"])) if str(fila["tipo"]) in ["Fijo", "Variable"] else 0,
                key="tipo_edit_gasto"
            )
            descripcion_edit = st.text_input("Nueva descripción", value=str(fila["descripcion"]), key="descripcion_edit_gasto")
        with col2:
            monto_edit = st.number_input("Nuevo monto", value=float(fila["monto"]), key="monto_edit_gasto")
            metodo_edit = st.selectbox(
                "Nuevo método",
                ["Efectivo", "Transferencia", "Tarjeta"],
                index=["Efectivo", "Transferencia", "Tarjeta"].index(str(fila["metodo"])) if str(fila["metodo"]) in ["Efectivo", "Transferencia", "Tarjeta"] else 0,
                key="metodo_edit_gasto"
            )

        if st.button("Actualizar gasto"):
            try:
                actualizar_fila("gastos", fila_id, {
                    "fecha": pd.to_datetime(fecha_edit),
                    "tipo": tipo_edit,
                    "descripcion": descripcion_edit.strip(),
                    "monto": float(monto_edit),
                    "metodo": metodo_edit,
                })
                st.success("Gasto actualizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar gasto"):
            try:
                eliminar_fila("gastos", fila_id)
                st.success("Gasto eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de gastos")
    gastos_filtrados = filtrar_busqueda(gastos, "buscar_gastos")
    st.dataframe(gastos_filtrados, width="stretch")
    descargar_excel(gastos_filtrados, "gastos.xlsx")

# =================================================
# PÉRDIDAS
# =================================================
elif menu == "Pérdidas":
    st.header("📉 Pérdidas de inventario")

    st.subheader("Subir pérdidas por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de pérdidas",
        type=["xlsx"],
        key="perdidas_excel"
    )
    if subir_excel_a_supabase(
        "perdidas",
        archivo_excel,
        ["fecha", "producto", "cantidad", "valor"],
        columnas_numericas=["cantidad", "valor"],
        columnas_fecha=["fecha"]
    ):
        st.rerun()

    st.subheader("Registrar pérdida")
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha de la pérdida")
        if productos.empty:
            st.warning("Primero debes registrar productos.")
            producto = None
        else:
            producto = st.selectbox("Producto", productos["nombre"].astype(str).unique())
    with col2:
        cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)

    if st.button("Guardar pérdida"):
        if producto is None:
            st.warning("No hay productos disponibles.")
        else:
            fila_producto = productos[productos["nombre"] == producto]
            if fila_producto.empty:
                st.warning("El producto no existe.")
            else:
                costo_producto = float(fila_producto.iloc[0]["costo"])
                valor = costo_producto * float(cantidad)
                try:
                    insertar_filas("perdidas", [{
                        "fecha": pd.to_datetime(fecha),
                        "producto": producto,
                        "cantidad": float(cantidad),
                        "valor": float(valor),
                    }])
                    st.success("Pérdida guardada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar pérdida")
    if not perdidas.empty:
        perdidas_edit = perdidas.copy()
        perdidas_edit["texto"] = (
            perdidas_edit["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + perdidas_edit["producto"].astype(str)
            + " | "
            + perdidas_edit["cantidad"].astype(str)
            + " | "
            + perdidas_edit["valor"].astype(str)
        )

        perdida_sel = st.selectbox("Selecciona una pérdida", perdidas_edit["texto"], key="editar_perdida")
        idx = perdidas_edit[perdidas_edit["texto"] == perdida_sel].index[0]
        fila = perdidas.loc[idx]
        fila_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_perdida")
            producto_edit = st.selectbox(
                "Nuevo producto",
                productos["nombre"].astype(str).unique() if not productos.empty else [],
                index=list(productos["nombre"].astype(str).unique()).index(str(fila["producto"])) if not productos.empty and str(fila["producto"]) in list(productos["nombre"].astype(str).unique()) else 0,
                key="producto_edit_perdida"
            )
        with col2:
            cantidad_edit = st.number_input("Nueva cantidad", value=float(fila["cantidad"]), min_value=0.0, step=1.0, key="cantidad_edit_perdida")

        if st.button("Actualizar pérdida"):
            fila_producto = productos[productos["nombre"] == producto_edit]
            if fila_producto.empty:
                st.warning("El producto no existe.")
            else:
                costo_producto = float(fila_producto.iloc[0]["costo"])
                valor_edit = costo_producto * float(cantidad_edit)
                try:
                    actualizar_fila("perdidas", fila_id, {
                        "fecha": pd.to_datetime(fecha_edit),
                        "producto": producto_edit,
                        "cantidad": float(cantidad_edit),
                        "valor": float(valor_edit),
                    })
                    st.success("Pérdida actualizada correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar pérdida"):
            try:
                eliminar_fila("perdidas", fila_id)
                st.success("Pérdida eliminada correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de pérdidas")
    perdidas_filtradas = filtrar_busqueda(perdidas, "buscar_perdidas")
    st.dataframe(perdidas_filtradas, width="stretch")
    descargar_excel(perdidas_filtradas, "perdidas.xlsx")

# =================================================
# GASTOS DUEÑO
# =================================================
elif menu == "Gastos Dueño":
    st.header("🏦 Inversiones / gastos del dueño")

    st.subheader("Subir gastos del dueño por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de gastos del dueño",
        type=["xlsx"],
        key="dueno_excel"
    )
    if subir_excel_a_supabase(
        "gastos_dueno",
        archivo_excel,
        ["fecha", "descripcion", "monto", "metodo"],
        columnas_numericas=["monto"],
        columnas_fecha=["fecha"]
    ):
        st.rerun()

    st.subheader("Registrar gasto del dueño")
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha")
        descripcion = st.text_input("Descripción")
    with col2:
        monto = st.number_input("Monto", min_value=0.0, step=1.0)
        metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta"], key="metodo_dueno")

    if st.button("Guardar gasto del dueño"):
        try:
            insertar_filas("gastos_dueno", [{
                "fecha": pd.to_datetime(fecha),
                "descripcion": descripcion.strip(),
                "monto": float(monto),
                "metodo": metodo,
            }])
            st.success("Gasto del dueño guardado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar gasto del dueño")
    if not gastos_dueno.empty:
        dueno_edit = gastos_dueno.copy()
        dueno_edit["texto"] = (
            dueno_edit["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + dueno_edit["descripcion"].astype(str)
            + " | "
            + dueno_edit["monto"].astype(str)
        )

        dueno_sel = st.selectbox("Selecciona un gasto del dueño", dueno_edit["texto"], key="editar_dueno")
        idx = dueno_edit[dueno_edit["texto"] == dueno_sel].index[0]
        fila = gastos_dueno.loc[idx]
        fila_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_dueno")
            descripcion_edit = st.text_area("Nueva descripción", value=str(fila["descripcion"]), key="descripcion_edit_dueno")
        with col2:
            monto_edit = st.number_input("Nuevo monto", value=float(fila["monto"]), key="monto_edit_dueno")
            metodo_edit = st.selectbox(
                "Nuevo método",
                ["Efectivo", "Transferencia", "Tarjeta"],
                index=["Efectivo", "Transferencia", "Tarjeta"].index(str(fila["metodo"])) if str(fila["metodo"]) in ["Efectivo", "Transferencia", "Tarjeta"] else 0,
                key="metodo_edit_dueno"
            )

        if st.button("Actualizar gasto del dueño"):
            try:
                actualizar_fila("gastos_dueno", fila_id, {
                    "fecha": pd.to_datetime(fecha_edit),
                    "descripcion": descripcion_edit.strip(),
                    "monto": float(monto_edit),
                    "metodo": metodo_edit,
                })
                st.success("Gasto del dueño actualizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar gasto del dueño"):
            try:
                eliminar_fila("gastos_dueno", fila_id)
                st.success("Gasto del dueño eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de gastos del dueño")
    dueno_filtrado = filtrar_busqueda(gastos_dueno, "buscar_dueno")
    st.dataframe(dueno_filtrado, width="stretch")
    descargar_excel(dueno_filtrado, "gastos_dueno.xlsx")

# =================================================
# EMPLEADOS
# =================================================
elif menu == "Empleados":
    st.header("👥 Empleados")

    st.subheader("Subir empleados por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de empleados",
        type=["xlsx"],
        key="empleados_excel"
    )
    if subir_excel_a_supabase(
        "empleados",
        archivo_excel,
        ["nombre", "cargo", "sueldo", "tipo_pago", "metodo_pago"],
        columnas_numericas=["sueldo"]
    ):
        st.rerun()

    st.subheader("Registrar empleado")
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre del empleado")
        cargo = st.text_input("Cargo")
        sueldo = st.number_input("Sueldo", min_value=0.0, step=1.0)
    with col2:
        tipo_pago = st.selectbox("Tipo de pago", ["Quincenal", "Mensual", "Variable"])
        metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Cheque"])

    if st.button("Guardar empleado"):
        if not nombre.strip():
            st.warning("Debes escribir el nombre del empleado.")
        else:
            try:
                insertar_filas("empleados", [{
                    "nombre": nombre.strip(),
                    "cargo": cargo.strip(),
                    "sueldo": float(sueldo),
                    "tipo_pago": tipo_pago,
                    "metodo_pago": metodo_pago,
                }])
                st.success("Empleado guardado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar empleado")
    if not empleados.empty:
        empleado_sel = st.selectbox("Selecciona un empleado", empleados["nombre"].astype(str).unique(), key="editar_empleado")
        fila = empleados[empleados["nombre"] == empleado_sel].iloc[0]
        fila_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            cargo_n = st.text_input("Nuevo cargo", value=str(fila["cargo"]), key="cargo_edit_empleado")
            sueldo_n = st.number_input("Nuevo sueldo", value=float(fila["sueldo"]), key="sueldo_edit_empleado")
        with col2:
            tipo_pago_n = st.selectbox(
                "Nuevo tipo de pago",
                ["Quincenal", "Mensual", "Variable"],
                index=["Quincenal", "Mensual", "Variable"].index(str(fila["tipo_pago"])) if str(fila["tipo_pago"]) in ["Quincenal", "Mensual", "Variable"] else 0,
                key="tipo_pago_edit_empleado"
            )
            metodo_pago_n = st.selectbox(
                "Nuevo método de pago",
                ["Efectivo", "Transferencia", "Cheque"],
                index=["Efectivo", "Transferencia", "Cheque"].index(str(fila["metodo_pago"])) if str(fila["metodo_pago"]) in ["Efectivo", "Transferencia", "Cheque"] else 0,
                key="metodo_pago_edit_empleado"
            )

        if st.button("Actualizar empleado"):
            try:
                actualizar_fila("empleados", fila_id, {
                    "cargo": cargo_n.strip(),
                    "sueldo": float(sueldo_n),
                    "tipo_pago": tipo_pago_n,
                    "metodo_pago": metodo_pago_n,
                })
                st.success("Empleado actualizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar empleado"):
            try:
                eliminar_fila("empleados", fila_id)
                st.success("Empleado eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Listado de empleados")
    empleados_filtrados = filtrar_busqueda(empleados, "buscar_empleados")
    st.dataframe(empleados_filtrados, width="stretch")
    descargar_excel(empleados_filtrados, "empleados.xlsx")

# =================================================
# CIERRE DE CAJA
# =================================================
elif menu == "Cierre de Caja":
    st.header("💰 Cierre de Caja")

    fecha_cierre = st.date_input("Fecha del cierre")
    fecha_cierre_dt = pd.to_datetime(fecha_cierre)

    ventas_dia = ventas[ventas["fecha"].dt.date == fecha_cierre_dt.date()] if not ventas.empty else pd.DataFrame()
    compras_dia = compras[compras["fecha"].dt.date == fecha_cierre_dt.date()] if not compras.empty else pd.DataFrame()
    gastos_dia = gastos[gastos["fecha"].dt.date == fecha_cierre_dt.date()] if not gastos.empty else pd.DataFrame()
    gastos_dueno_dia = gastos_dueno[gastos_dueno["fecha"].dt.date == fecha_cierre_dt.date()] if not gastos_dueno.empty else pd.DataFrame()

    ventas_negocio = ventas_dia[ventas_dia["metodo"].astype(str).str.lower() == "efectivo"]["total"].sum() if not ventas_dia.empty else 0
    ventas_banco = ventas_dia[ventas_dia["metodo"].astype(str).str.lower().isin(["transferencia", "tarjeta"])]["total"].sum() if not ventas_dia.empty else 0

    compras_negocio = compras_dia[compras_dia["metodo"].astype(str).str.lower() == "efectivo"]["monto"].sum() if not compras_dia.empty else 0
    compras_banco = compras_dia[compras_dia["metodo"].astype(str).str.lower().isin(["transferencia", "tarjeta"])]["monto"].sum() if not compras_dia.empty else 0

    gastos_negocio = gastos_dia[gastos_dia["metodo"].astype(str).str.lower() == "efectivo"]["monto"].sum() if not gastos_dia.empty else 0
    gastos_banco = gastos_dia[gastos_dia["metodo"].astype(str).str.lower().isin(["transferencia", "tarjeta"])]["monto"].sum() if not gastos_dia.empty else 0

    dueno_negocio = gastos_dueno_dia[gastos_dueno_dia["metodo"].astype(str).str.lower() == "efectivo"]["monto"].sum() if not gastos_dueno_dia.empty else 0
    dueno_banco = gastos_dueno_dia[gastos_dueno_dia["metodo"].astype(str).str.lower().isin(["transferencia", "tarjeta"])]["monto"].sum() if not gastos_dueno_dia.empty else 0

    negocio_esperado = float(ventas_negocio - compras_negocio - gastos_negocio - dueno_negocio)
    banco_esperado = float(ventas_banco - compras_banco - gastos_banco - dueno_banco)

    st.subheader("Resumen esperado del día")
    c1, c2 = st.columns(2)
    c1.metric("Dinero esperado en negocio", f"{negocio_esperado:,.2f}")
    c2.metric("Dinero esperado en banco", f"{banco_esperado:,.2f}")

    st.subheader("Registrar conteo real")
    c3, c4 = st.columns(2)
    with c3:
        negocio_real = st.number_input("Dinero real en negocio", min_value=0.0, step=1.0)
    with c4:
        banco_real = st.number_input("Dinero real en banco", min_value=0.0, step=1.0)

    observacion = st.text_area("Observación")

    diferencia_negocio = float(negocio_real - negocio_esperado)
    diferencia_banco = float(banco_real - banco_esperado)
    diferencia_total = float(diferencia_negocio + diferencia_banco)

    if diferencia_total > 0:
        estado = "Sobrante"
    elif diferencia_total < 0:
        estado = "Faltante"
    else:
        estado = "Cuadrado"

    c5, c6, c7 = st.columns(3)
    c5.metric("Diferencia negocio", f"{diferencia_negocio:,.2f}")
    c6.metric("Diferencia banco", f"{diferencia_banco:,.2f}")
    c7.metric("Estado", estado)

    st.subheader("Subir cierres por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de cierre de caja",
        type=["xlsx"],
        key="cierre_excel"
    )
    if subir_excel_a_supabase(
        "cierre_caja",
        archivo_excel,
        [
            "fecha",
            "negocio_esperado",
            "banco_esperado",
            "negocio_real",
            "banco_real",
            "diferencia_negocio",
            "diferencia_banco",
            "diferencia_total",
            "estado",
            "observacion",
        ],
        columnas_numericas=[
            "negocio_esperado",
            "banco_esperado",
            "negocio_real",
            "banco_real",
            "diferencia_negocio",
            "diferencia_banco",
            "diferencia_total",
        ],
        columnas_fecha=["fecha"]
    ):
        st.rerun()

    if st.button("Guardar cierre de caja"):
        try:
            insertar_filas("cierre_caja", [{
                "fecha": pd.to_datetime(fecha_cierre),
                "negocio_esperado": float(negocio_esperado),
                "banco_esperado": float(banco_esperado),
                "negocio_real": float(negocio_real),
                "banco_real": float(banco_real),
                "diferencia_negocio": float(diferencia_negocio),
                "diferencia_banco": float(diferencia_banco),
                "diferencia_total": float(diferencia_total),
                "estado": estado,
                "observacion": observacion.strip(),
            }])
            st.success("Cierre de caja guardado correctamente.")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar: {e}")

    st.subheader("Editar o eliminar cierre")
    if not cierre_caja.empty:
        cierres_edit = cierre_caja.copy()
        cierres_edit["texto"] = (
            cierres_edit["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + cierres_edit["estado"].astype(str)
        )

        cierre_sel = st.selectbox("Selecciona un cierre", cierres_edit["texto"], key="editar_cierre")
        idx = cierres_edit[cierres_edit["texto"] == cierre_sel].index[0]
        fila = cierre_caja.loc[idx]
        fila_id = int(fila["id"])

        col1, col2 = st.columns(2)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_cierre")
            negocio_real_edit = st.number_input("Nuevo dinero real en negocio", value=float(fila["negocio_real"]), key="negocio_real_edit")
            banco_real_edit = st.number_input("Nuevo dinero real en banco", value=float(fila["banco_real"]), key="banco_real_edit")
        with col2:
            observacion_edit = st.text_area("Nueva observación", value=str(fila["observacion"]), key="observacion_edit_cierre")

            negocio_esperado_edit = float(fila["negocio_esperado"])
            banco_esperado_edit = float(fila["banco_esperado"])

            diferencia_negocio_edit = float(negocio_real_edit - negocio_esperado_edit)
            diferencia_banco_edit = float(banco_real_edit - banco_esperado_edit)
            diferencia_total_edit = float(diferencia_negocio_edit + diferencia_banco_edit)

            if diferencia_total_edit > 0:
                estado_edit = "Sobrante"
            elif diferencia_total_edit < 0:
                estado_edit = "Faltante"
            else:
                estado_edit = "Cuadrado"

            st.write(f"Estado calculado: {estado_edit}")

        if st.button("Actualizar cierre"):
            try:
                actualizar_fila("cierre_caja", fila_id, {
                    "fecha": pd.to_datetime(fecha_edit),
                    "negocio_real": float(negocio_real_edit),
                    "banco_real": float(banco_real_edit),
                    "diferencia_negocio": float(diferencia_negocio_edit),
                    "diferencia_banco": float(diferencia_banco_edit),
                    "diferencia_total": float(diferencia_total_edit),
                    "estado": estado_edit,
                    "observacion": observacion_edit.strip(),
                })
                st.success("Cierre actualizado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al actualizar: {e}")

        if st.button("Eliminar cierre"):
            try:
                eliminar_fila("cierre_caja", fila_id)
                st.success("Cierre eliminado correctamente.")
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")

    st.subheader("Historial de cierres")
    cierre_filtrado = filtrar_busqueda(cierre_caja, "buscar_cierre")
    st.dataframe(cierre_filtrado, width="stretch")
    descargar_excel(cierre_filtrado, "cierre_caja.xlsx")
