import streamlit as st
import pandas as pd
from supabase import create_client

from utils import cargar, guardar, subir_excel, filtrar_busqueda, descargar_excel
from dashboard import mostrar_dashboard

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# 🔗 SUPABASE
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
# 🔴 PRODUCTOS DESDE SUPABASE
try:
    data = supabase.table("productos").select("*").execute()
    productos = pd.DataFrame(data.data)
except:
    productos = pd.DataFrame(columns=["nombre", "costo", "precio", "cantidad"])

# 🔵 LOS DEMÁS SIGUEN EN EXCEL (NO SE TOCAN)
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

    if archivo_excel:
        df = pd.read_excel(archivo_excel)
        df.columns = df.columns.str.lower()
        df = df.fillna(0)

        for _, row in df.iterrows():
            supabase.table("productos").insert({
                "nombre": row.get("nombre", ""),
                "costo": float(row.get("costo", 0)),
                "precio": float(row.get("precio", 0)),
                "cantidad": int(row.get("cantidad", 0)),
            }).execute()

        st.success("Productos subidos a la nube ☁️")
        st.rerun()

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
            supabase.table("productos").insert({
                "nombre": nombre.strip(),
                "costo": float(costo),
                "precio": float(precio),
                "cantidad": int(cantidad),
            }).execute()
            st.success("Producto guardado en la nube ☁️")
            st.rerun()

    st.subheader("Editar o eliminar producto")
    if not productos.empty:
        producto_sel = st.selectbox(
            "Selecciona un producto",
            productos["nombre"].astype(str).unique(),
        )

        fila = productos[productos["nombre"] == producto_sel].iloc[0]

        col1, col2 = st.columns(2)
        with col1:
            nuevo_costo = st.number_input("Nuevo costo", value=float(fila["costo"]))
            nuevo_precio = st.number_input("Nuevo precio", value=float(fila["precio"]))
        with col2:
            nueva_cantidad = st.number_input("Nueva cantidad", value=int(fila["cantidad"]), step=1)

        if st.button("Actualizar producto"):
            supabase.table("productos").update({
                "costo": float(nuevo_costo),
                "precio": float(nuevo_precio),
                "cantidad": int(nueva_cantidad),
            }).eq("nombre", producto_sel).execute()

            st.success("Producto actualizado")
            st.rerun()

        if st.button("Eliminar producto"):
            supabase.table("productos").delete().eq("nombre", producto_sel).execute()
            st.success("Producto eliminado")
            st.rerun()

    st.subheader("Listado de productos")
    productos_filtrados = filtrar_busqueda(productos)
    st.dataframe(productos_filtrados, use_container_width=True)
    descargar_excel(productos_filtrados, "productos.xlsx")

