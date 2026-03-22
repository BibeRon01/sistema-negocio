import streamlit as st
import pandas as pd
from supabase import create_client

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# 🔗 Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

# -------------------------------------------------
# FUNCIONES GENERALES
# -------------------------------------------------
def limpiar_nan(df):
    return df.fillna(0)

def obtener(nombre):
    try:
        data = supabase.table(nombre).select("*").order("id").execute()
        return pd.DataFrame(data.data)
    except:
        return pd.DataFrame()

def insertar(nombre, data):
    supabase.table(nombre).insert(data).execute()

def insertar_masivo(nombre, df):
    df = limpiar_nan(df)
    supabase.table(nombre).insert(df.to_dict(orient="records")).execute()

def actualizar(nombre, data, id):
    supabase.table(nombre).update(data).eq("id", id).execute()

def eliminar(nombre, id):
    supabase.table(nombre).delete().eq("id", id).execute()

def descargar(df, nombre):
    return st.download_button(
        "📥 Descargar Excel",
        df.to_csv(index=False).encode("utf-8"),
        f"{nombre}.csv",
        "text/csv"
    )

# -------------------------------------------------
# MENÚ
# -------------------------------------------------
menu = st.sidebar.selectbox("Menú", [
    "Dashboard","Productos","Ventas","Compras",
    "Gastos","Pérdidas","Gastos Dueño","Empleados","Cierre de Caja"
])

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
if menu == "Dashboard":
    st.title("📊 Dashboard")
    st.info("Aquí verás resumen cuando cargues datos")

# -------------------------------------------------
# PRODUCTOS
# -------------------------------------------------
elif menu == "Productos":

    st.header("📦 Productos")

    # SUBIR EXCEL
    archivo = st.file_uploader("Subir productos Excel", type=["xlsx"])
    if archivo:
        df = pd.read_excel(archivo)
        df.columns = df.columns.str.lower()

        if "nombre" in df.columns:
            if "costo" not in df: df["costo"] = 0
            if "precio" not in df: df["precio"] = 0
            if "cantidad" not in df: df["cantidad"] = 0

            insertar_masivo("productos", df)
            st.success("Subido correctamente ☁️")
        else:
            st.error("Debe tener columna nombre")

    # AGREGAR MANUAL
    st.subheader("Agregar producto")
    nombre = st.text_input("Nombre")
    costo = st.number_input("Costo", 0.0)
    precio = st.number_input("Precio", 0.0)
    cantidad = st.number_input("Cantidad", 0.0)

    if st.button("Guardar producto"):
        insertar("productos", {
            "nombre": nombre,
            "costo": costo,
            "precio": precio,
            "cantidad": cantidad
        })
        st.success("Guardado")
        st.rerun()

    # LISTADO
    df = obtener("productos")
    st.dataframe(df)
    descargar(df, "productos")

    # EDITAR / ELIMINAR
    if not df.empty:
        sel = st.selectbox("Editar", df["nombre"])
        fila = df[df["nombre"] == sel].iloc[0]

        nuevo_precio = st.number_input("Precio", value=float(fila["precio"]))
        nueva_cantidad = st.number_input("Cantidad", value=float(fila["cantidad"]))

        if st.button("Actualizar"):
            actualizar("productos", {
                "precio": nuevo_precio,
                "cantidad": nueva_cantidad
            }, fila["id"])
            st.rerun()

        if st.button("Eliminar"):
            eliminar("productos", fila["id"])
            st.rerun()

# -------------------------------------------------
# PLANTILLA PARA TODOS LOS DEMÁS MÓDULOS
# -------------------------------------------------
def modulo(nombre, campos):

    st.header(nombre)

    # SUBIR EXCEL
    archivo = st.file_uploader(f"Subir {nombre}", type=["xlsx"])
    if archivo:
        df = pd.read_excel(archivo)
        df.columns = df.columns.str.lower()
        insertar_masivo(nombre.lower().replace(" ","_"), df)
        st.success("Subido ☁️")

    # FORMULARIO
    data = {}
    for campo in campos:
        data[campo] = st.text_input(campo)

    if st.button(f"Guardar {nombre}"):
        insertar(nombre.lower().replace(" ","_"), data)
        st.rerun()

    df = obtener(nombre.lower().replace(" ","_"))
    st.dataframe(df)
    descargar(df, nombre)

# -------------------------------------------------
# MÓDULOS
# -------------------------------------------------
elif menu == "Ventas":
    modulo("ventas", ["fecha","producto","cantidad","precio","total"])

elif menu == "Compras":
    modulo("compras", ["fecha","producto","cantidad","costo"])

elif menu == "Gastos":
    modulo("gastos", ["fecha","descripcion","monto","tipo"])

elif menu == "Pérdidas":
    modulo("perdidas", ["fecha","producto","cantidad","motivo"])

elif menu == "Gastos Dueño":
    modulo("gastos_dueno", ["fecha","descripcion","monto"])

elif menu == "Empleados":
    modulo("empleados", ["nombre","cargo","salario"])

elif menu == "Cierre de Caja":
    modulo("cierre_caja", ["fecha","efectivo","banco"])
