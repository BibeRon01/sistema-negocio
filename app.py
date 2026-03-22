import streamlit as st
import pandas as pd
from supabase import create_client

from utils import cargar, guardar, subir_excel, filtrar_busqueda, descargar_excel
from dashboard import mostrar_dashboard

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# 🔗 Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# -------------------------------------------------
# FUNCIONES AUXILIARES
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
# CARGA DE DATOS (EXCEL PARA TODO MENOS PRODUCTOS)
# -------------------------------------------------
ventas = convertir_fecha_segura(asegurar_columnas(cargar("ventas.xlsx"), ["fecha","producto","cantidad","precio","total"]))
gastos = convertir_fecha_segura(asegurar_columnas(cargar("gastos.xlsx"), ["fecha","descripcion","monto","tipo"]))
compras = convertir_fecha_segura(asegurar_columnas(cargar("compras.xlsx"), ["fecha","producto","cantidad","costo"]))
perdidas = convertir_fecha_segura(asegurar_columnas(cargar("perdidas.xlsx"), ["fecha","producto","cantidad","motivo"]))
gastos_dueno = convertir_fecha_segura(asegurar_columnas(cargar("gastos_dueno.xlsx"), ["fecha","descripcion","monto"]))
empleados = asegurar_columnas(cargar("empleados.xlsx"), ["nombre","cargo","salario"])
cierre_caja = convertir_fecha_segura(asegurar_columnas(cargar("cierre_caja.xlsx"), ["fecha","efectivo","banco"]))

# -------------------------------------------------
# PRODUCTOS DESDE SUPABASE
# -------------------------------------------------
def obtener_productos():
    try:
        data = supabase.table("productos").select("*").order("id").execute()
        return pd.DataFrame(data.data)
    except:
        return pd.DataFrame(columns=["id","nombre","costo","precio","cantidad"])

# -------------------------------------------------
# MENÚ
# -------------------------------------------------
menu = st.sidebar.selectbox("Menú", [
    "Dashboard","Productos","Ventas","Compras",
    "Gastos","Pérdidas","Gastos Dueño",
    "Empleados","Cierre de Caja"
])

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
if menu == "Dashboard":
    mostrar_dashboard(ventas, gastos, compras, perdidas, gastos_dueno, cierre_caja)

# -------------------------------------------------
# PRODUCTOS (SUPABASE)
# -------------------------------------------------
elif menu == "Productos":
    st.header("📦 Productos")

    productos = obtener_productos()

    st.subheader("Agregar producto")
    nombre = st.text_input("Nombre")
    costo = st.number_input("Costo", min_value=0.0)
    precio = st.number_input("Precio", min_value=0.0)
    cantidad = st.number_input("Cantidad", min_value=0.0)

    if st.button("Guardar producto"):
        if nombre.strip():
            supabase.table("productos").insert({
                "nombre": nombre,
                "costo": costo,
                "precio": precio,
                "cantidad": cantidad
            }).execute()
            st.success("Guardado en la nube ☁️")
            st.rerun()
        else:
            st.warning("Ingrese nombre")

    st.subheader("Listado")
    st.dataframe(productos, width="stretch")

# -------------------------------------------------
# VENTAS (EXCEL)
# -------------------------------------------------
elif menu == "Ventas":
    st.header("Ventas")
    producto = st.text_input("Producto")
    cantidad = st.number_input("Cantidad", min_value=1)
    precio = st.number_input("Precio", min_value=0.0)

    if st.button("Guardar venta"):
        total = cantidad * precio
        nueva = pd.DataFrame([{"fecha":pd.Timestamp.now(),"producto":producto,"cantidad":cantidad,"precio":precio,"total":total}])
        ventas = pd.concat([ventas,nueva])
        guardar(ventas,"ventas.xlsx")
        st.success("Venta guardada")

    st.dataframe(ventas)

# -------------------------------------------------
# COMPRAS (EXCEL)
# -------------------------------------------------
elif menu == "Compras":
    st.header("Compras")
    producto = st.text_input("Producto compra")
    cantidad = st.number_input("Cantidad compra", min_value=1)
    costo = st.number_input("Costo compra", min_value=0.0)

    if st.button("Guardar compra"):
        nueva = pd.DataFrame([{"fecha":pd.Timestamp.now(),"producto":producto,"cantidad":cantidad,"costo":costo}])
        compras = pd.concat([compras,nueva])
        guardar(compras,"compras.xlsx")
        st.success("Compra guardada")

    st.dataframe(compras)

# -------------------------------------------------
# GASTOS (EXCEL)
# -------------------------------------------------
elif menu == "Gastos":
    st.header("Gastos")
    descripcion = st.text_input("Descripción")
    monto = st.number_input("Monto", min_value=0.0)

    if st.button("Guardar gasto"):
        nueva = pd.DataFrame([{"fecha":pd.Timestamp.now(),"descripcion":descripcion,"monto":monto,"tipo":"variable"}])
        gastos = pd.concat([gastos,nueva])
        guardar(gastos,"gastos.xlsx")
        st.success("Gasto guardado")

    st.dataframe(gastos)
    
