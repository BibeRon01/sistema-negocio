import streamlit as st
import pandas as pd
from supabase import create_client

from utils import cargar, guardar, subir_excel, filtrar_busqueda, descargar_excel
from dashboard import mostrar_dashboard

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# -------------------------------------------------
# FUNCIONES DE APOYO
# -------------------------------------------------
def asegurar_columnas(df, columnas):
    if df is None or df.empty:
        return pd.DataFrame(columns=columnas)

    for col in columnas:
        if col not in df.columns:
            df[col] = ""

    return df[columnas]

def convertir_fecha_segura(df, columna="fecha"):
    if columna in df.columns and not df.empty:
        df[columna] = pd.to_datetime(df[columna], errors="coerce")
    return df

# -------------------------------------------------
# CARGA DE ARCHIVOS
# -------------------------------------------------
productos = cargar("productos.xlsx")
ventas = cargar("ventas.xlsx")
gastos = cargar("gastos.xlsx")
compras = cargar("compras.xlsx")
perdidas = cargar("perdidas.xlsx")
gastos_dueno = cargar("gastos_dueno.xlsx")
empleados = cargar("empleados.xlsx")
cierre_caja = cargar("cierre_caja.xlsx")

# -------------------------------------------------
# ASEGURAR COLUMNAS
# -------------------------------------------------
productos = asegurar_columnas(productos, ["nombre", "costo", "precio", "cantidad"])
ventas = asegurar_columnas(ventas, ["fecha", "total", "metodo"])
gastos = asegurar_columnas(gastos, ["fecha", "tipo", "descripcion", "monto", "metodo"])
compras = asegurar_columnas(compras, ["fecha", "numero", "proveedor", "monto", "metodo"])
perdidas = asegurar_columnas(perdidas, ["fecha", "producto", "cantidad", "valor"])
gastos_dueno = asegurar_columnas(gastos_dueno, ["fecha", "descripcion", "monto", "metodo"])
empleados = asegurar_columnas(empleados, ["nombre", "cargo", "sueldo", "tipo_pago", "metodo_pago"])
cierre_caja = asegurar_columnas(
    cierre_caja,
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

ventas = convertir_fecha_segura(ventas)
gastos = convertir_fecha_segura(gastos)
compras = convertir_fecha_segura(compras)
perdidas = convertir_fecha_segura(perdidas)
gastos_dueno = convertir_fecha_segura(gastos_dueno)
cierre_caja = convertir_fecha_segura(cierre_caja)

# -------------------------------------------------
# MENÚ
# -------------------------------------------------
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

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
if menu == "Dashboard":
    mostrar_dashboard(ventas, gastos, compras, perdidas, gastos_dueno, cierre_caja)

# -------------------------------------------------
# PRODUCTOS
# -------------------------------------------------
elif menu == "Productos":
    st.header("📦 Productos")

    columnas_productos = ["nombre", "costo", "precio", "cantidad"]

    st.subheader("Subir productos por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de productos",
        type=["xlsx"],
        key="productos_excel"
    )
    productos = subir_excel(productos, archivo_excel, columnas_productos, "productos.xlsx")

    st.subheader("Agregar producto manual")
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre del producto")
        costo = st.number_input("Costo", min_value=0.0, step=1.0)
    with col2:
        precio = st.number_input("Precio", min_value=0.0, step=1.0)
        cantidad = st.number_input("Cantidad", min_value=0, step=1)

    if st.button("Guardar producto"):
        if not nombre.strip():
            st.warning("Debes escribir el nombre del producto.")
        else:
            nuevo = pd.DataFrame([{
                "nombre": nombre.strip(),
                "costo": float(costo),
                "precio": float(precio),
                "cantidad": int(cantidad),
            }])
            productos = pd.concat([productos, nuevo], ignore_index=True)
            guardar(productos, "productos.xlsx")
            st.success("Producto guardado correctamente.")

    st.subheader("Editar o eliminar producto")
    if not productos.empty:
       producto_sel = st.selectbox(
    "Selecciona un producto",
    productos["nombre"].dropna().astype(str).str.strip().unique(),
    key="editar_producto"
)
fila_filtrada = productos[productos["nombre"].astype(str).str.strip() == str(producto_sel).strip()]

if fila_filtrada.empty:
    st.warning("No se encontró el producto seleccionado.")
else:
    idx = fila_filtrada.index[0]
    datos = productos.loc[idx]
        with col1:
            nuevo_costo = st.number_input("Nuevo costo", value=float(datos["costo"]), key="nuevo_costo_producto")
            nuevo_precio = st.number_input("Nuevo precio", value=float(datos["precio"]), key="nuevo_precio_producto")
        with col2:
            nueva_cantidad = st.number_input("Nueva cantidad", value=int(datos["cantidad"]), step=1, key="nueva_cantidad_producto")

        if st.button("Actualizar producto"):
            productos.loc[idx, "costo"] = float(nuevo_costo)
            productos.loc[idx, "precio"] = float(nuevo_precio)
            productos.loc[idx, "cantidad"] = int(nueva_cantidad)
            guardar(productos, "productos.xlsx")
            st.success("Producto actualizado correctamente.")

        if st.button("Eliminar producto"):
            productos = productos.drop(index=idx).reset_index(drop=True)
            guardar(productos, "productos.xlsx")
            st.success("Producto eliminado correctamente.")

    st.subheader("Listado de productos")
    productos_filtrados = filtrar_busqueda(productos)
    st.dataframe(productos_filtrados, use_container_width=True)
    descargar_excel(productos_filtrados, "productos.xlsx")

# -------------------------------------------------
# VENTAS
# -------------------------------------------------
elif menu == "Ventas":
    st.header("💰 Ventas del día")

    columnas_ventas = ["fecha", "total", "metodo"]

    st.subheader("Subir ventas por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de ventas",
        type=["xlsx"],
        key="ventas_excel"
    )
    ventas = subir_excel(ventas, archivo_excel, columnas_ventas, "ventas.xlsx")
    ventas = convertir_fecha_segura(ventas)

    st.subheader("Registrar venta diaria")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha = st.date_input("Fecha de la venta")
    with col2:
        total = st.number_input("Total de la venta del día", min_value=0.0, step=1.0)
    with col3:
        metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta"])

    if st.button("Guardar venta"):
        nuevo = pd.DataFrame([{
            "fecha": pd.to_datetime(fecha),
            "total": float(total),
            "metodo": metodo,
        }])
        ventas = pd.concat([ventas, nuevo], ignore_index=True)
        guardar(ventas, "ventas.xlsx")
        st.success("Venta guardada correctamente.")

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
            ventas.loc[idx, "fecha"] = pd.to_datetime(fecha_edit)
            ventas.loc[idx, "total"] = float(total_edit)
            ventas.loc[idx, "metodo"] = metodo_edit
            guardar(ventas, "ventas.xlsx")
            st.success("Venta actualizada correctamente.")

        if st.button("Eliminar venta"):
            ventas = ventas.drop(index=idx).reset_index(drop=True)
            guardar(ventas, "ventas.xlsx")
            st.success("Venta eliminada correctamente.")

    st.subheader("Listado de ventas")
    ventas_filtradas = filtrar_busqueda(ventas)
    st.dataframe(ventas_filtradas, use_container_width=True)
    descargar_excel(ventas_filtradas, "ventas.xlsx")

# -------------------------------------------------
# COMPRAS
# -------------------------------------------------
elif menu == "Compras":
    st.header("🧾 Compras")

    columnas_compras = ["fecha", "numero", "proveedor", "monto", "metodo"]

    st.subheader("Subir compras por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de compras",
        type=["xlsx"],
        key="compras_excel"
    )
    compras = subir_excel(compras, archivo_excel, columnas_compras, "compras.xlsx")
    compras = convertir_fecha_segura(compras)

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
        nuevo = pd.DataFrame([{
            "fecha": pd.to_datetime(fecha),
            "numero": numero.strip(),
            "proveedor": proveedor.strip(),
            "monto": float(monto),
            "metodo": metodo,
        }])
        compras = pd.concat([compras, nuevo], ignore_index=True)
        guardar(compras, "compras.xlsx")
        st.success("Compra guardada correctamente.")

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
            compras.loc[idx, "fecha"] = pd.to_datetime(fecha_edit)
            compras.loc[idx, "numero"] = numero_edit.strip()
            compras.loc[idx, "proveedor"] = proveedor_edit.strip()
            compras.loc[idx, "monto"] = float(monto_edit)
            compras.loc[idx, "metodo"] = metodo_edit
            guardar(compras, "compras.xlsx")
            st.success("Compra actualizada correctamente.")

        if st.button("Eliminar compra"):
            compras = compras.drop(index=idx).reset_index(drop=True)
            guardar(compras, "compras.xlsx")
            st.success("Compra eliminada correctamente.")

    st.subheader("Listado de compras")
    compras_filtradas = filtrar_busqueda(compras)
    st.dataframe(compras_filtradas, use_container_width=True)
    descargar_excel(compras_filtradas, "compras.xlsx")

# -------------------------------------------------
# GASTOS
# -------------------------------------------------
elif menu == "Gastos":
    st.header("💸 Gastos")

    columnas_gastos = ["fecha", "tipo", "descripcion", "monto", "metodo"]

    st.subheader("Subir gastos por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de gastos",
        type=["xlsx"],
        key="gastos_excel"
    )
    gastos = subir_excel(gastos, archivo_excel, columnas_gastos, "gastos.xlsx")
    gastos = convertir_fecha_segura(gastos)

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
        nuevo = pd.DataFrame([{
            "fecha": pd.to_datetime(fecha),
            "tipo": tipo,
            "descripcion": descripcion.strip(),
            "monto": float(monto),
            "metodo": metodo,
        }])
        gastos = pd.concat([gastos, nuevo], ignore_index=True)
        guardar(gastos, "gastos.xlsx")
        st.success("Gasto guardado correctamente.")

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
            gastos.loc[idx, "fecha"] = pd.to_datetime(fecha_edit)
            gastos.loc[idx, "tipo"] = tipo_edit
            gastos.loc[idx, "descripcion"] = descripcion_edit.strip()
            gastos.loc[idx, "monto"] = float(monto_edit)
            gastos.loc[idx, "metodo"] = metodo_edit
            guardar(gastos, "gastos.xlsx")
            st.success("Gasto actualizado correctamente.")

        if st.button("Eliminar gasto"):
            gastos = gastos.drop(index=idx).reset_index(drop=True)
            guardar(gastos, "gastos.xlsx")
            st.success("Gasto eliminado correctamente.")

    st.subheader("Listado de gastos")
    gastos_filtrados = filtrar_busqueda(gastos)
    st.dataframe(gastos_filtrados, use_container_width=True)
    descargar_excel(gastos_filtrados, "gastos.xlsx")

# -------------------------------------------------
# PÉRDIDAS
# -------------------------------------------------
elif menu == "Pérdidas":
    st.header("📉 Pérdidas de inventario")

    columnas_perdidas = ["fecha", "producto", "cantidad", "valor"]

    st.subheader("Subir pérdidas por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de pérdidas",
        type=["xlsx"],
        key="perdidas_excel"
    )
    perdidas = subir_excel(perdidas, archivo_excel, columnas_perdidas, "perdidas.xlsx")
    perdidas = convertir_fecha_segura(perdidas)

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
        cantidad = st.number_input("Cantidad", min_value=0, step=1)

    if st.button("Guardar pérdida"):
        if producto is None:
            st.warning("No hay productos disponibles.")
        else:
            fila_producto = productos[productos["nombre"] == producto]
            if fila_producto.empty:
                st.warning("El producto no existe.")
            else:
                costo_producto = float(fila_producto.iloc[0]["costo"])
                valor = costo_producto * int(cantidad)

                nuevo = pd.DataFrame([{
                    "fecha": pd.to_datetime(fecha),
                    "producto": producto,
                    "cantidad": int(cantidad),
                    "valor": float(valor),
                }])
                perdidas = pd.concat([perdidas, nuevo], ignore_index=True)
                guardar(perdidas, "perdidas.xlsx")
                st.success("Pérdida guardada correctamente.")

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
            cantidad_edit = st.number_input("Nueva cantidad", value=int(fila["cantidad"]), min_value=0, step=1, key="cantidad_edit_perdida")

        if st.button("Actualizar pérdida"):
            fila_producto = productos[productos["nombre"] == producto_edit]
            if fila_producto.empty:
                st.warning("El producto no existe.")
            else:
                costo_producto = float(fila_producto.iloc[0]["costo"])
                valor_edit = costo_producto * int(cantidad_edit)

                perdidas.loc[idx, "fecha"] = pd.to_datetime(fecha_edit)
                perdidas.loc[idx, "producto"] = producto_edit
                perdidas.loc[idx, "cantidad"] = int(cantidad_edit)
                perdidas.loc[idx, "valor"] = float(valor_edit)
                guardar(perdidas, "perdidas.xlsx")
                st.success("Pérdida actualizada correctamente.")

        if st.button("Eliminar pérdida"):
            perdidas = perdidas.drop(index=idx).reset_index(drop=True)
            guardar(perdidas, "perdidas.xlsx")
            st.success("Pérdida eliminada correctamente.")

    st.subheader("Listado de pérdidas")
    perdidas_filtradas = filtrar_busqueda(perdidas)
    st.dataframe(perdidas_filtradas, use_container_width=True)
    descargar_excel(perdidas_filtradas, "perdidas.xlsx")

# -------------------------------------------------
# GASTOS DUEÑO
# -------------------------------------------------
elif menu == "Gastos Dueño":
    st.header("🏦 Inversiones / gastos del dueño")

    columnas_dueno = ["fecha", "descripcion", "monto", "metodo"]

    st.subheader("Subir gastos del dueño por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de gastos del dueño",
        type=["xlsx"],
        key="dueno_excel"
    )
    gastos_dueno = subir_excel(gastos_dueno, archivo_excel, columnas_dueno, "gastos_dueno.xlsx")
    gastos_dueno = convertir_fecha_segura(gastos_dueno)

    st.subheader("Registrar gasto del dueño")
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha")
        descripcion = st.text_input("Descripción")
    with col2:
        monto = st.number_input("Monto", min_value=0.0, step=1.0)
        metodo = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Tarjeta"], key="metodo_dueno")

    if st.button("Guardar gasto del dueño"):
        nuevo = pd.DataFrame([{
            "fecha": pd.to_datetime(fecha),
            "descripcion": descripcion.strip(),
            "monto": float(monto),
            "metodo": metodo,
        }])
        gastos_dueno = pd.concat([gastos_dueno, nuevo], ignore_index=True)
        guardar(gastos_dueno, "gastos_dueno.xlsx")
        st.success("Gasto del dueño guardado correctamente.")

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
            gastos_dueno.loc[idx, "fecha"] = pd.to_datetime(fecha_edit)
            gastos_dueno.loc[idx, "descripcion"] = descripcion_edit.strip()
            gastos_dueno.loc[idx, "monto"] = float(monto_edit)
            gastos_dueno.loc[idx, "metodo"] = metodo_edit
            guardar(gastos_dueno, "gastos_dueno.xlsx")
            st.success("Gasto del dueño actualizado correctamente.")

        if st.button("Eliminar gasto del dueño"):
            gastos_dueno = gastos_dueno.drop(index=idx).reset_index(drop=True)
            guardar(gastos_dueno, "gastos_dueno.xlsx")
            st.success("Gasto del dueño eliminado correctamente.")

    st.subheader("Listado de gastos del dueño")
    dueno_filtrado = filtrar_busqueda(gastos_dueno)
    st.dataframe(dueno_filtrado, use_container_width=True)
    descargar_excel(dueno_filtrado, "gastos_dueno.xlsx")

# -------------------------------------------------
# EMPLEADOS
# -------------------------------------------------
elif menu == "Empleados":
    st.header("👥 Empleados")

    columnas_empleados = ["nombre", "cargo", "sueldo", "tipo_pago", "metodo_pago"]

    st.subheader("Subir empleados por Excel")
    archivo_excel = st.file_uploader(
        "Selecciona un archivo Excel de empleados",
        type=["xlsx"],
        key="empleados_excel"
    )
    empleados = subir_excel(empleados, archivo_excel, columnas_empleados, "empleados.xlsx")

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
            nuevo = pd.DataFrame([{
                "nombre": nombre.strip(),
                "cargo": cargo.strip(),
                "sueldo": float(sueldo),
                "tipo_pago": tipo_pago,
                "metodo_pago": metodo_pago,
            }])
            empleados = pd.concat([empleados, nuevo], ignore_index=True)
            guardar(empleados, "empleados.xlsx")
            st.success("Empleado guardado correctamente.")

    st.subheader("Editar o eliminar empleado")
    if not empleados.empty:
        empleado_sel = st.selectbox(
            "Selecciona un empleado",
            empleados["nombre"].astype(str).unique(),
            key="editar_empleado"
        )
        idx = empleados[empleados["nombre"] == empleado_sel].index[0]
        datos = empleados.loc[idx]

        col1, col2 = st.columns(2)
        with col1:
            cargo_n = st.text_input("Nuevo cargo", value=str(datos["cargo"]), key="cargo_edit_empleado")
            sueldo_n = st.number_input("Nuevo sueldo", value=float(datos["sueldo"]), key="sueldo_edit_empleado")
        with col2:
            tipo_pago_n = st.selectbox(
                "Nuevo tipo de pago",
                ["Quincenal", "Mensual", "Variable"],
                index=["Quincenal", "Mensual", "Variable"].index(str(datos["tipo_pago"])) if str(datos["tipo_pago"]) in ["Quincenal", "Mensual", "Variable"] else 0,
                key="tipo_pago_edit_empleado"
            )
            metodo_pago_n = st.selectbox(
                "Nuevo método de pago",
                ["Efectivo", "Transferencia", "Cheque"],
                index=["Efectivo", "Transferencia", "Cheque"].index(str(datos["metodo_pago"])) if str(datos["metodo_pago"]) in ["Efectivo", "Transferencia", "Cheque"] else 0,
                key="metodo_pago_edit_empleado"
            )

        if st.button("Actualizar empleado"):
            empleados.loc[idx, "cargo"] = cargo_n.strip()
            empleados.loc[idx, "sueldo"] = float(sueldo_n)
            empleados.loc[idx, "tipo_pago"] = tipo_pago_n
            empleados.loc[idx, "metodo_pago"] = metodo_pago_n
            guardar(empleados, "empleados.xlsx")
            st.success("Empleado actualizado correctamente.")

        if st.button("Eliminar empleado"):
            empleados = empleados.drop(index=idx).reset_index(drop=True)
            guardar(empleados, "empleados.xlsx")
            st.success("Empleado eliminado correctamente.")

    st.subheader("Listado de empleados")
    empleados_filtrados = filtrar_busqueda(empleados)
    st.dataframe(empleados_filtrados, use_container_width=True)
    descargar_excel(empleados_filtrados, "empleados.xlsx")

# -------------------------------------------------
# CIERRE DE CAJA
# -------------------------------------------------
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

    negocio_esperado = ventas_negocio - compras_negocio - gastos_negocio - dueno_negocio
    banco_esperado = ventas_banco - compras_banco - gastos_banco - dueno_banco

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

    diferencia_negocio = negocio_real - negocio_esperado
    diferencia_banco = banco_real - banco_esperado
    diferencia_total = diferencia_negocio + diferencia_banco

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

    if st.button("Guardar cierre de caja"):
        nuevo = pd.DataFrame([{
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

        cierre_caja = pd.concat([cierre_caja, nuevo], ignore_index=True)
        guardar(cierre_caja, "cierre_caja.xlsx")
        st.success("Cierre de caja guardado correctamente.")

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

        col1, col2 = st.columns(2)
        with col1:
            fecha_edit = st.date_input("Nueva fecha", value=pd.to_datetime(fila["fecha"]), key="fecha_edit_cierre")
            negocio_real_edit = st.number_input("Nuevo dinero real en negocio", value=float(fila["negocio_real"]), key="negocio_real_edit")
            banco_real_edit = st.number_input("Nuevo dinero real en banco", value=float(fila["banco_real"]), key="banco_real_edit")
        with col2:
            observacion_edit = st.text_area("Nueva observación", value=str(fila["observacion"]), key="observacion_edit_cierre")

            negocio_esperado_edit = float(fila["negocio_esperado"])
            banco_esperado_edit = float(fila["banco_esperado"])

            diferencia_negocio_edit = negocio_real_edit - negocio_esperado_edit
            diferencia_banco_edit = banco_real_edit - banco_esperado_edit
            diferencia_total_edit = diferencia_negocio_edit + diferencia_banco_edit

            if diferencia_total_edit > 0:
                estado_edit = "Sobrante"
            elif diferencia_total_edit < 0:
                estado_edit = "Faltante"
            else:
                estado_edit = "Cuadrado"

            st.write(f"Estado calculado: {estado_edit}")

        if st.button("Actualizar cierre"):
            cierre_caja.loc[idx, "fecha"] = pd.to_datetime(fecha_edit)
            cierre_caja.loc[idx, "negocio_real"] = float(negocio_real_edit)
            cierre_caja.loc[idx, "banco_real"] = float(banco_real_edit)
            cierre_caja.loc[idx, "diferencia_negocio"] = float(diferencia_negocio_edit)
            cierre_caja.loc[idx, "diferencia_banco"] = float(diferencia_banco_edit)
            cierre_caja.loc[idx, "diferencia_total"] = float(diferencia_total_edit)
            cierre_caja.loc[idx, "estado"] = estado_edit
            cierre_caja.loc[idx, "observacion"] = observacion_edit.strip()
            guardar(cierre_caja, "cierre_caja.xlsx")
            st.success("Cierre actualizado correctamente.")

        if st.button("Eliminar cierre"):
            cierre_caja = cierre_caja.drop(index=idx).reset_index(drop=True)
            guardar(cierre_caja, "cierre_caja.xlsx")
            st.success("Cierre eliminado correctamente.")

    st.subheader("Historial de cierres")
    cierre_filtrado = filtrar_busqueda(cierre_caja)
    st.dataframe(cierre_filtrado, use_container_width=True)
    descargar_excel(cierre_filtrado, "cierre_caja.xlsx")
    
from supabase import create_client

# 🔗 CONEXIÓN SUPABASE
import pandas as pd
import streamlit as st
import os
import io

# -----------------------------
# CARGAR ARCHIVO
# -----------------------------
def cargar(nombre_archivo):
    if os.path.exists(nombre_archivo):
        try:
            return pd.read_excel(nombre_archivo)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

# -----------------------------
# GUARDAR ARCHIVO
# -----------------------------
def guardar(df, nombre_archivo):
    try:
        df.to_excel(nombre_archivo, index=False)
    except Exception as e:
        st.error(f"Error al guardar archivo: {e}")

# -----------------------------
# SUBIR EXCEL
# -----------------------------
def subir_excel(df_actual, archivo, columnas, nombre_archivo):
    if archivo is not None:
        try:
            df_excel = pd.read_excel(archivo)

            if not all(col in df_excel.columns for col in columnas):
                st.error(f"El archivo debe tener estas columnas: {columnas}")
                return df_actual

            df_excel = df_excel[columnas].copy()

            # convertir fecha
            if "fecha" in df_excel.columns:
                df_excel["fecha"] = pd.to_datetime(df_excel["fecha"], errors="coerce")

            # convertir números
            for col in ["monto", "total", "valor", "costo", "precio", "cantidad"]:
                if col in df_excel.columns:
                    df_excel[col] = pd.to_numeric(df_excel[col], errors="coerce").fillna(0)

            df_nuevo = pd.concat([df_actual, df_excel], ignore_index=True)
            guardar(df_nuevo, nombre_archivo)

            st.success("Archivo cargado correctamente ✅")
            return df_nuevo

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            return df_actual

    return df_actual

# -----------------------------
# BUSCADOR
# -----------------------------
def filtrar_busqueda(df):
    if df.empty:
        st.info("No hay datos para mostrar.")
        return df

    busqueda = st.text_input("🔍 Buscar en la tabla")

    if busqueda:
        df_filtrado = df[
            df.astype(str)
            .apply(lambda row: row.str.contains(busqueda, case=False).any(), axis=1)
        ]
        return df_filtrado

    return df

# -----------------------------
# DESCARGAR EXCEL
# -----------------------------
def descargar_excel(df, nombre_archivo):
    if df.empty:
        st.warning("No hay datos para descargar.")
        return

    try:
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            label="📥 Descargar Excel",
            data=output.getvalue(),
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Error al generar el archivo: {e}")

# -----------------------------
# CONVERTIR FECHAS
# -----------------------------
def convertir_fecha(df, columna="fecha"):
    if df.empty:
        return df

    if columna in df.columns:
        df[columna] = pd.to_datetime(df[columna], errors="coerce")

    return df

# -----------------------------
# SUMA SEGURA (CLAVE DEL SISTEMA)
# -----------------------------

def suma_segura(df, columna):
    if df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())
    SUPABASE_URL = "PEGA_AQUI_LA_URL_DE_API"
SUPABASE_KEY = "PEGA_AQUI_LA_CLAVE_PUBLICABLE"
supabase = create_client(url, key)
def backup_nube(tabla, df):
    try:
        if df is None or df.empty:
            return

        df_backup = df.copy()

        # No mandar id a Supabase si viene vacío o si la tabla lo genera sola
        if "id" in df_backup.columns:
            df_backup = df_backup.drop(columns=["id"])

        # Limpiar valores NaN
        df_backup = df_backup.fillna("")

        datos = df_backup.to_dict(orient="records")

        # Borrar contenido anterior y volver a insertar
        supabase.table(tabla).delete().neq("id", 0).execute()
        supabase.table(tabla).insert(datos).execute()

    except Exception as e:
        st.warning(f"Error en backup nube: {e}")
        
