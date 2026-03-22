import streamlit as st
import pandas as pd
from supabase import create_client

from utils import cargar, guardar, subir_excel, filtrar_busqueda, descargar_excel
from dashboard import mostrar_dashboard

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# 🔗 SUPABASE (solo productos por ahora)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# -------------------------------------------------
# FUNCIONES GENERALES
# -------------------------------------------------
def asegurar(df, cols):
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df

def fecha(df):
    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df

# -------------------------------------------------
# CARGA (EXCEL)
# -------------------------------------------------
ventas = fecha(asegurar(cargar("ventas.xlsx"), ["fecha","producto","cantidad","precio","total"]))
compras = fecha(asegurar(cargar("compras.xlsx"), ["fecha","producto","cantidad","costo"]))
gastos = fecha(asegurar(cargar("gastos.xlsx"), ["fecha","descripcion","monto","tipo"]))
perdidas = fecha(asegurar(cargar("perdidas.xlsx"), ["fecha","producto","cantidad","motivo"]))
gastos_dueno = fecha(asegurar(cargar("gastos_dueno.xlsx"), ["fecha","descripcion","monto"]))
empleados = asegurar(cargar("empleados.xlsx"), ["nombre","cargo","salario"])
cierre = fecha(asegurar(cargar("cierre_caja.xlsx"), ["fecha","efectivo","banco"]))

# -------------------------------------------------
# MENÚ
# -------------------------------------------------
menu = st.sidebar.selectbox("Menú", [
    "Dashboard","Productos","Ventas","Compras","Gastos",
    "Pérdidas","Gastos Dueño","Empleados","Cierre de Caja"
])

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
if menu == "Dashboard":
    mostrar_dashboard(ventas, gastos, compras, perdidas, gastos_dueno, cierre)

# -------------------------------------------------
# PRODUCTOS (SUPABASE + EXCEL MASIVO)
# -------------------------------------------------
elif menu == "Productos":

    st.header("📦 Productos")

    # 🔹 SUBIR EXCEL
    st.subheader("Subir productos por Excel")
    archivo = st.file_uploader("Archivo Excel", type=["xlsx"])

    if archivo:
        df = pd.read_excel(archivo)
        df.columns = df.columns.str.lower()
        df = df.fillna(0)

        if "nombre" in df.columns:
            if "costo" not in df: df["costo"] = 0
            if "precio" not in df: df["precio"] = 0
            if "cantidad" not in df: df["cantidad"] = 0

            supabase.table("productos").insert(df.to_dict(orient="records")).execute()
            st.success("Subido correctamente ☁️")
        else:
            st.error("Debe tener columna nombre")

    # 🔹 AGREGAR
    st.subheader("Agregar producto")
    nombre = st.text_input("Nombre")
    costo = st.number_input("Costo", 0.0)
    precio = st.number_input("Precio", 0.0)
    cantidad = st.number_input("Cantidad", 0.0)

    if st.button("Guardar producto"):
        if nombre.strip():
            supabase.table("productos").insert({
                "nombre": nombre,
                "costo": costo,
                "precio": precio,
                "cantidad": cantidad
            }).execute()
            st.success("Guardado ☁️")
            st.rerun()
        else:
            st.warning("Ingrese nombre")

    # 🔹 LISTADO
    try:
        data = supabase.table("productos").select("*").order("id").execute()
        productos = pd.DataFrame(data.data)
    except:
        productos = pd.DataFrame()

    st.subheader("Listado")
    st.dataframe(productos, width="stretch")
    descargar_excel(productos, "productos.xlsx")

    # 🔹 EDITAR / ELIMINAR
    if not productos.empty:
        sel = st.selectbox("Selecciona producto", productos["nombre"])
        fila = productos[productos["nombre"] == sel].iloc[0]

        nuevo_precio = st.number_input("Nuevo precio", float(fila["precio"]))
        nueva_cantidad = st.number_input("Nueva cantidad", float(fila["cantidad"]))

        col1, col2 = st.columns(2)

        if col1.button("Actualizar"):
            supabase.table("productos").update({
                "precio": nuevo_precio,
                "cantidad": nueva_cantidad
            }).eq("id", fila["id"]).execute()
            st.rerun()

        if col2.button("Eliminar"):
            supabase.table("productos").delete().eq("id", fila["id"]).execute()
            st.rerun()

# -------------------------------------------------
# FUNCIÓN PARA RESTO DE MÓDULOS (EXCEL)
# -------------------------------------------------
def modulo(nombre, df, columnas, archivo):

    st.header(nombre)

    archivo_up = st.file_uploader("Subir Excel", type=["xlsx"])
    if archivo_up:
        nuevo = pd.read_excel(archivo_up)
        df = pd.concat([df, nuevo])
        guardar(df, archivo)
        st.success("Subido")

    datos = {}
    for col in columnas:
        datos[col] = st.text_input(col)

    if st.button("Guardar"):
        nuevo = pd.DataFrame([datos])
        df = pd.concat([df, nuevo])
        guardar(df, archivo)
        st.success("Guardado")

    st.dataframe(df)
    descargar_excel(df, archivo)

# -------------------------------------------------
# RESTO MÓDULOS (SIN ROMPER)
# -------------------------------------------------
elif menu == "Ventas":
    modulo("Ventas", ventas, ["fecha","producto","cantidad","precio","total"], "ventas.xlsx")

elif menu == "Compras":
    modulo("Compras", compras, ["fecha","producto","cantidad","costo"], "compras.xlsx")

elif menu == "Gastos":
    modulo("Gastos", gastos, ["fecha","descripcion","monto","tipo"], "gastos.xlsx")

elif menu == "Pérdidas":
    modulo("Pérdidas", perdidas, ["fecha","producto","cantidad","motivo"], "perdidas.xlsx")

elif menu == "Gastos Dueño":
    modulo("Gastos Dueño", gastos_dueno, ["fecha","descripcion","monto"], "gastos_dueno.xlsx")

elif menu == "Empleados":
    modulo("Empleados", empleados, ["nombre","cargo","salario"], "empleados.xlsx")

elif menu == "Cierre de Caja":
    modulo("Cierre de Caja", cierre, ["fecha","efectivo","banco"], "cierre_caja.xlsx")
