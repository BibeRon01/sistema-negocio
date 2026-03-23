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
# FUNCIONES
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
# CARGA
# -------------------------------------------------
productos = asegurar_columnas(cargar("productos.xlsx"), ["nombre", "costo", "precio", "cantidad"])
ventas = asegurar_columnas(cargar("ventas.xlsx"), ["fecha", "total", "metodo"])
gastos = asegurar_columnas(cargar("gastos.xlsx"), ["fecha", "tipo", "descripcion", "monto", "metodo"])
compras = asegurar_columnas(cargar("compras.xlsx"), ["fecha", "numero", "proveedor", "monto", "metodo"])
perdidas = asegurar_columnas(cargar("perdidas.xlsx"), ["fecha", "producto", "cantidad", "valor"])
gastos_dueno = asegurar_columnas(cargar("gastos_dueno.xlsx"), ["fecha", "descripcion", "monto", "metodo"])
empleados = asegurar_columnas(cargar("empleados.xlsx"), ["nombre", "cargo", "sueldo", "tipo_pago", "metodo_pago"])
cierre_caja = asegurar_columnas(cargar("cierre_caja.xlsx"), [
    "fecha","negocio_esperado","banco_esperado","negocio_real","banco_real",
    "diferencia_negocio","diferencia_banco","diferencia_total","estado","observacion"
])

# -------------------------------------------------
# MENÚ
# -------------------------------------------------
st.title("💼 Sistema de Negocio")

menu = st.sidebar.selectbox("Menú", [
    "Dashboard","Productos","Ventas","Compras",
    "Gastos","Pérdidas","Gastos Dueño","Empleados","Cierre de Caja"
])

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
if menu == "Dashboard":
    mostrar_dashboard(ventas, gastos, compras, perdidas, gastos_dueno, cierre_caja)

# -------------------------------------------------
# PRODUCTOS (CORREGIDO)
# -------------------------------------------------
elif menu == "Productos":

    st.header("📦 Productos")

    # AGREGAR
    nombre = st.text_input("Nombre")
    costo = st.number_input("Costo", min_value=0.0)
    precio = st.number_input("Precio", min_value=0.0)
    cantidad = st.number_input("Cantidad", min_value=0)

    if st.button("Guardar producto"):
        if nombre.strip() == "":
            st.warning("Nombre vacío")
        else:
            nuevo = pd.DataFrame([{
                "nombre": nombre.strip(),
                "costo": costo,
                "precio": precio,
                "cantidad": cantidad
            }])
            productos = pd.concat([productos, nuevo], ignore_index=True)
            guardar(productos, "productos.xlsx")
            st.success("Guardado")

    # EDITAR / ELIMINAR (ARREGLADO)
    st.subheader("Editar o eliminar producto")

    nombres = productos["nombre"].dropna().astype(str).str.strip()
    nombres = nombres[nombres != ""]

    if not nombres.empty:

        producto_sel = st.selectbox("Selecciona", nombres.unique())

        fila = productos[
            productos["nombre"].fillna("").astype(str).str.strip() == producto_sel
        ]

        if not fila.empty:
            idx = fila.index[0]
            datos = productos.loc[idx]

            col1, col2 = st.columns(2)

            with col1:
                nuevo_costo = st.number_input("Nuevo costo", value=float(datos["costo"]))
                nuevo_precio = st.number_input("Nuevo precio", value=float(datos["precio"]))

            with col2:
                nueva_cantidad = st.number_input("Nueva cantidad", value=int(datos["cantidad"]))

            if st.button("Actualizar"):
                productos.loc[idx, "costo"] = nuevo_costo
                productos.loc[idx, "precio"] = nuevo_precio
                productos.loc[idx, "cantidad"] = nueva_cantidad
                guardar(productos, "productos.xlsx")
                st.success("Actualizado")

            if st.button("Eliminar"):
                productos = productos.drop(index=idx).reset_index(drop=True)
                guardar(productos, "productos.xlsx")
                st.success("Eliminado")

    st.dataframe(productos)

# -------------------------------------------------
# LOS DEMÁS MÓDULOS SIGUEN IGUAL (NO LOS TOQUÉ)
# -------------------------------------------------
