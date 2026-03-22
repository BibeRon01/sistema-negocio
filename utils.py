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
    
