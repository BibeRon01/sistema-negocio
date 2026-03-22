import streamlit as st
import pandas as pd
from utils import suma_segura

def mostrar_dashboard(ventas, gastos, compras, perdidas, gastos_dueno, cierre_caja):
    st.title("📊 Dashboard del Negocio")

    def convertir_fecha(df):
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return df

    ventas = convertir_fecha(ventas)
    gastos = convertir_fecha(gastos)
    compras = convertir_fecha(compras)
    perdidas = convertir_fecha(perdidas)
    gastos_dueno = convertir_fecha(gastos_dueno)
    cierre_caja = convertir_fecha(cierre_caja)

    meses = set()

    for df in [ventas, gastos, compras, perdidas, gastos_dueno, cierre_caja]:
        if not df.empty and "fecha" in df.columns:
            df_validas = df.dropna(subset=["fecha"])
            if not df_validas.empty:
                meses.update(df_validas["fecha"].dt.to_period("M").astype(str).tolist())

    meses = sorted(list(meses))

    mes_actual = pd.Timestamp.today().to_period("M").strftime("%Y-%m")
    if mes_actual not in meses:
        meses.append(mes_actual)
        meses = sorted(meses)

    st.subheader("📅 Resumen mensual")
    indice_mes_actual = meses.index(mes_actual) if mes_actual in meses else 0
    mes_seleccionado = st.selectbox("Selecciona el mes", meses, index=indice_mes_actual)

    def filtrar_por_mes(df, mes):
        if df.empty or "fecha" not in df.columns:
            return df
        df = df.dropna(subset=["fecha"])
        if df.empty:
            return df
        return df[df["fecha"].dt.to_period("M").astype(str) == mes]

    ventas_mes = filtrar_por_mes(ventas, mes_seleccionado)
    gastos_mes = filtrar_por_mes(gastos, mes_seleccionado)
    compras_mes = filtrar_por_mes(compras, mes_seleccionado)
    perdidas_mes = filtrar_por_mes(perdidas, mes_seleccionado)
    gastos_dueno_mes = filtrar_por_mes(gastos_dueno, mes_seleccionado)
    cierre_mes = filtrar_por_mes(cierre_caja, mes_seleccionado)

    total_ventas = suma_segura(ventas_mes, "total")
    total_compras = suma_segura(compras_mes, "monto")

    gastos_fijos = 0.0
    gastos_variables = 0.0

    if not gastos_mes.empty and "tipo" in gastos_mes.columns and "monto" in gastos_mes.columns:
        gastos_fijos = suma_segura(
            gastos_mes[gastos_mes["tipo"].astype(str).str.lower() == "fijo"],
            "monto"
        )
        gastos_variables = suma_segura(
            gastos_mes[gastos_mes["tipo"].astype(str).str.lower() == "variable"],
            "monto"
        )

    inversiones = suma_segura(gastos_dueno_mes, "monto")
    perdidas_total = suma_segura(perdidas_mes, "valor")

    st.markdown("### 📝 Datos que tú suministras")

    col_input1, col_input2 = st.columns(2)
    with col_input1:
        inventario_dinero = st.number_input(
            "Dinero que tienes en inventario",
            min_value=0.0,
            step=1.0,
            value=0.0
        )
    with col_input2:
        ganancia_bruta = st.number_input(
            "Ganancia bruta (la da el POS)",
            min_value=0.0,
            step=1.0,
            value=0.0
        )

    ganancia_neta = ganancia_bruta - gastos_fijos - gastos_variables - perdidas_total

    admin = ganancia_neta * 0.35
    duena = ganancia_neta * 0.65
    duena_real = duena - inversiones

    dinero_negocio = total_ventas - gastos_fijos - gastos_variables - inversiones
    sobrante = ganancia_neta - admin - duena_real

    st.markdown("## 📌 Resumen del mes")

    c1, c2, c3 = st.columns(3)
    c1.metric("Total de ventas", f"{total_ventas:,.2f}")
    c2.metric("Total de compras", f"{total_compras:,.2f}")
    c3.metric("Dinero en inventario", f"{inventario_dinero:,.2f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Gastos fijos", f"{gastos_fijos:,.2f}")
    c5.metric("Gastos variables", f"{gastos_variables:,.2f}")
    c6.metric("Inversiones / gastos del dueño", f"{inversiones:,.2f}")

    c7, c8 = st.columns(2)
    c7.metric("Pérdidas de inventario", f"{perdidas_total:,.2f}")
    c8.metric("Dinero que queda en el negocio", f"{dinero_negocio:,.2f}")

    st.markdown("---")

    st.markdown("## 📈 Estado de resultados")
    g1, g2 = st.columns(2)
    g1.metric("Ganancia bruta", f"{ganancia_bruta:,.2f}")
    g2.metric("Ganancia neta", f"{ganancia_neta:,.2f}")

    st.markdown("## 👥 Distribución")
    d1, d2 = st.columns(2)
    d1.metric("Administrador (35%)", f"{admin:,.2f}")
    d2.metric("Dueña (65%)", f"{duena_real:,.2f}")

    st.metric("Dinero que sobra", f"{sobrante:,.2f}")

    st.markdown("## 💰 Cierre de caja del mes")

    negocio_esperado = suma_segura(cierre_mes, "negocio_esperado")
    banco_esperado = suma_segura(cierre_mes, "banco_esperado")
    negocio_real = suma_segura(cierre_mes, "negocio_real")
    banco_real = suma_segura(cierre_mes, "banco_real")
    diferencia_total = suma_segura(cierre_mes, "diferencia_total")

    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Negocio esperado", f"{negocio_esperado:,.2f}")
    cc2.metric("Banco esperado", f"{banco_esperado:,.2f}")
    cc3.metric("Diferencia total", f"{diferencia_total:,.2f}")

    cc4, cc5 = st.columns(2)
    cc4.metric("Negocio real", f"{negocio_real:,.2f}")
    cc5.metric("Banco real", f"{banco_real:,.2f}")

    st.markdown("## 📑 Estado de resultados detallado")

    estado = pd.DataFrame({
        "Concepto": [
            "Ventas",
            "Compras",
            "Gastos Fijos",
            "Gastos Variables",
            "Inversiones / Dueño",
            "Pérdidas de inventario",
            "Ganancia Bruta",
            "Ganancia Neta",
            "Administrador 35%",
            "Dueña 65%",
            "Dinero que sobra"
        ],
        "Monto": [
            total_ventas,
            total_compras,
            gastos_fijos,
            gastos_variables,
            inversiones,
            perdidas_total,
            ganancia_bruta,
            ganancia_neta,
            admin,
            duena_real,
            sobrante
        ]
    })

    st.dataframe(estado, use_container_width=True)

    st.markdown("## 📊 Gráficos")

    colg1, colg2 = st.columns(2)

    with colg1:
        st.write("Ventas vs Compras")
        grafico1 = pd.DataFrame({
            "Concepto": ["Ventas", "Compras"],
            "Monto": [total_ventas, total_compras]
        })
        st.bar_chart(grafico1.set_index("Concepto"))

    with colg2:
        st.write("Gastos y pérdidas")
        grafico2 = pd.DataFrame({
            "Concepto": ["Gastos Fijos", "Gastos Variables", "Pérdidas", "Inversiones"],
            "Monto": [gastos_fijos, gastos_variables, perdidas_total, inversiones]
        })
        st.bar_chart(grafico2.set_index("Concepto"))

    st.markdown("## 📂 Registros del mes")

    with st.expander("Ver ventas del mes"):
        st.dataframe(ventas_mes, use_container_width=True)

    with st.expander("Ver compras del mes"):
        st.dataframe(compras_mes, use_container_width=True)

    with st.expander("Ver gastos del mes"):
        st.dataframe(gastos_mes, use_container_width=True)

    with st.expander("Ver pérdidas del mes"):
        st.dataframe(perdidas_mes, use_container_width=True)

    with st.expander("Ver gastos del dueño del mes"):
        st.dataframe(gastos_dueno_mes, use_container_width=True)

    with st.expander("Ver cierres de caja del mes"):
        st.dataframe(cierre_mes, use_container_width=True)
        