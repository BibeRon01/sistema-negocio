# Modularized view for A&M ERP v2
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime, date, timedelta
from typing import Any

try:
    try:
        from core.db import *
    except ModuleNotFoundError:
        from db import *
    try:
        from core.auth import *
    except ModuleNotFoundError:
        from auth import *
    try:
        from core.utils import *
    except ModuleNotFoundError:
        from utils import *
    try:
        from core.helpers import *
    except ModuleNotFoundError:
        from helpers import *
except ModuleNotFoundError:
    from db import *
    from auth import *
    from utils import *
    from helpers import *

def render_predicciones_ia():
    st.markdown("""
<div style='padding: 15px; background: linear-gradient(135deg, #1e1b4b 0%, #0f0728 100%); border: 1px solid #4338ca; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;'>
<div>
<h1 style='margin: 0; font-size: 24px; font-weight: 900; color: #f3f4f6;'>🔮 Predicciones Financieras e Inteligencia del Negocio</h1>
<p style='margin: 3px 0 0 0; font-size: 13px; color: #a5b4fc; font-weight: 500;'>Proyecciones predictivas de flujo de caja, control de retiros y optimización de capital por IA</p>
</div>
<span style='background-color:rgba(99, 102, 241, 0.12); color:#818cf8; border:1px solid #818cf8; border-radius:6px; padding:4px 10px; font-size:12px; font-weight:700;'>
IA Engine v2.0
</span>
</div>
""", unsafe_allow_html=True)

    df_ventas = DATA["ventas"].copy() if "ventas" in DATA else pd.DataFrame()
    df_gastos = DATA["gastos"].copy() if "gastos" in DATA else pd.DataFrame()
    df_gastos_dueno = DATA["gastos_dueno"].copy() if "gastos_dueno" in DATA else pd.DataFrame()
    
    if not df_ventas.empty:
        for col_anulado in ["anulado", "cancelado"]:
            if col_anulado in df_ventas.columns:
                try:
                    df_ventas = df_ventas[~df_ventas[col_anulado].fillna(False).astype(bool)].copy()
                except Exception:
                    pass
        if "estado" in df_ventas.columns:
            df_ventas = df_ventas[~df_ventas["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()

    hoy = datetime.now()
    mes_actual_str = hoy.strftime("%Y-%m")

    ventas_mensuales = {}
    if not df_ventas.empty and "fecha" in df_ventas.columns:
        try:
            df_ventas["mes"] = pd.to_datetime(df_ventas["fecha"]).dt.strftime("%Y-%m")
            ventas_mensuales = df_ventas.groupby("mes")["total"].sum().to_dict()
        except Exception:
            pass

    gastos_mensuales = {}
    if not df_gastos.empty and "fecha" in df_gastos.columns:
        try:
            df_gastos["mes"] = pd.to_datetime(df_gastos["fecha"]).dt.strftime("%Y-%m")
            gastos_mensuales = df_gastos.groupby("mes")["monto"].sum().to_dict()
        except Exception:
            pass

    meses_rango = []
    for i in range(5, -1, -1):
        m = (hoy - timedelta(days=i*30)).strftime("%Y-%m")
        meses_rango.append(m)

    x_vals = []
    y_ventas = []
    y_gastos = []

    for idx, m in enumerate(meses_rango):
        v = float(ventas_mensuales.get(m, 0.0))
        g = float(gastos_mensuales.get(m, 0.0))
        x_vals.append(idx + 1)
        y_ventas.append(v)
        y_gastos.append(g)

    def calcular_regresion_simple(x_vec, y_vec):
        N = len(x_vec)
        if N < 2:
            return 0.0, y_vec[0] if y_vec else 0.0
        sum_x = sum(x_vec)
        sum_y = sum(y_vec)
        sum_xy = sum(a*b for a, b in zip(x_vec, y_vec))
        sum_x2 = sum(a*a for a in x_vec)
        denom = (N * sum_x2) - (sum_x ** 2)
        if denom == 0:
            return 0.0, sum_y / N
        pendiente = ((N * sum_xy) - (sum_x * sum_y)) / denom
        intercepto = (sum_y - (pendiente * sum_x)) / N
        return pendiente, intercepto

    m_v, b_v = calcular_regresion_simple(x_vals, y_ventas)
    m_g, b_g = calcular_regresion_simple(x_vals, y_gastos)

    proj_ventas = []
    proj_gastos = []
    meses_proj = []

    for i in range(1, 4):
        x_proj = len(meses_rango) + i
        v_proj = max(m_v * x_proj + b_v, 0.0)
        g_proj = max(m_g * x_proj + b_g, 0.0)
        
        if sum(y_ventas) == 0:
            v_proj = 0.0
        if sum(y_gastos) == 0:
            g_proj = 0.0

        proj_ventas.append(v_proj)
        proj_gastos.append(g_proj)
        
        mes_futuro = (hoy + timedelta(days=i*30)).strftime("%B %Y").capitalize()
        meses_proj.append(mes_futuro)

    ventas_mes_actual = float(ventas_mensuales.get(mes_actual_str, 0.0))
    gastos_mes_actual = float(gastos_mensuales.get(mes_actual_str, 0.0))
    
    df_gastos_actual = pd.DataFrame()
    if not df_gastos.empty and "fecha" in df_gastos.columns:
        try:
            df_gastos_actual = df_gastos[df_gastos["mes"] == mes_actual_str]
        except Exception:
            pass

    gastos_fijos_mes = 0.0
    gastos_var_mes = 0.0
    if not df_gastos_actual.empty:
        if "tipo" in df_gastos_actual.columns:
            gastos_fijos_mes = float(df_gastos_actual[df_gastos_actual["tipo"].astype(str).str.lower() == "fijo"]["monto"].sum())
            gastos_var_mes = float(df_gastos_actual[df_gastos_actual["tipo"].astype(str).str.lower() == "variable"]["monto"].sum())
        else:
            gastos_var_mes = float(df_gastos_actual["monto"].sum())

    utilidad_neta_mes = ventas_mes_actual - (gastos_fijos_mes + gastos_var_mes)

    retiros_dueno_mes = 0.0
    if not df_gastos_dueno.empty and "fecha" in df_gastos_dueno.columns:
        try:
            df_gastos_dueno["mes"] = pd.to_datetime(df_gastos_dueno["fecha"]).dt.strftime("%Y-%m")
            df_dueno_act = df_gastos_dueno[df_gastos_dueno["mes"] == mes_actual_str]
            for col in ["anulado", "cancelado"]:
                if col in df_dueno_act.columns:
                    df_dueno_act = df_dueno_act[~df_dueno_act[col].fillna(False).astype(bool)]
            retiros_dueno_mes = float(df_dueno_act["monto"].sum())
        except Exception:
            pass

    sobrante_mes = utilidad_neta_mes - retiros_dueno_mes

    porcentaje_retiros = 0.0
    if utilidad_neta_mes > 0:
        porcentaje_retiros = (retiros_dueno_mes / utilidad_neta_mes) * 100

    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        st.markdown(f"""
<div style='background-color:#1e293b; padding:15px; border-radius:10px; border-left:4px solid #10b981; text-align:center;'>
<span style='font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase;'>Ventas Actuales</span><br/>
<strong style='font-size:19px; color:#f8fafc;'>RD$ {ventas_mes_actual:,.2f}</strong>
</div>
""", unsafe_allow_html=True)
    with kpi_col2:
        st.markdown(f"""
<div style='background-color:#1e293b; padding:15px; border-radius:10px; border-left:4px solid #f43f5e; text-align:center;'>
<span style='font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase;'>Gastos Fijos + Var</span><br/>
<strong style='font-size:19px; color:#f8fafc;'>RD$ {gastos_fijos_mes + gastos_var_mes:,.2f}</strong>
</div>
""", unsafe_allow_html=True)
    with kpi_col3:
        color_util = "#10b981" if utilidad_neta_mes >= 0 else "#f43f5e"
        st.markdown(f"""
<div style='background-color:#1e293b; padding:15px; border-radius:10px; border-left:4px solid {color_util}; text-align:center;'>
<span style='font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase;'>Utilidad Neta Real</span><br/>
<strong style='font-size:19px; color:#f8fafc;'>RD$ {utilidad_neta_mes:,.2f}</strong>
</div>
""", unsafe_allow_html=True)
    with kpi_col4:
        color_sob = "#818cf8" if sobrante_mes >= 0 else "#f43f5e"
        st.markdown(f"""
<div style='background-color:#1e293b; padding:15px; border-radius:10px; border-left:4px solid {color_sob}; text-align:center;'>
<span style='font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase;'>Reinversión / Excedente</span><br/>
<strong style='font-size:19px; color:#f8fafc;'>RD$ {sobrante_mes:,.2f}</strong>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    col_regla1, col_regla2 = st.columns(2)
    with col_regla1:
        st.markdown("""
<div style='background: #111827; border: 1px solid #1f2937; padding: 20px; border-radius: 12px; margin-bottom:15px;'>
<h3 style='margin-top:0; font-size:16px; color:#f3f4f6;'>👑 Desglose de Retiros del Dueño</h3>
<p style='font-size:13px; color:#9ca3af;'>Proporción de la Utilidad Neta que es retirada del negocio por el propietario.</p>
</div>
""", unsafe_allow_html=True)
        if retiros_dueno_mes > 0:
            st.info(f"El propietario ha retirado **RD$ {retiros_dueno_mes:,.2f}** este mes.")
            if utilidad_neta_mes > 0:
                st.metric("Porcentaje de Utilidad Retirado", f"{porcentaje_retiros:.1f}%", help="Límite saludable sugerido: < 40%")
                if porcentaje_retiros > 50:
                    st.warning("🚨 **Alerta de Caja:** Los retiros superan el 50% de la utilidad neta. Esto reduce severamente la liquidez del negocio para el próximo mes.")
                else:
                    st.success("🟢 **Retiros Saludables:** El nivel de retiro del dueño está dentro del margen de reinversión saludable del negocio.")
            else:
                st.error("🚨 **Alerta de Liquidez:** Hay retiros del dueño en un mes con utilidad neta menor o igual a cero. Esto descapitaliza el negocio de inmediato.")
        else:
            st.success("🟢 No se registran retiros del dueño este mes. El 100% de la utilidad se retiene para el capital de trabajo.")

    with col_regla2:
        st.markdown("""
<div style='background: #111827; border: 1px solid #1f2937; padding: 20px; border-radius: 12px; margin-bottom:15px;'>
<h3 style='margin-top:0; font-size:16px; color:#f3f4f6;'>📊 Estructura de Costos del Mes</h3>
<p style='font-size:13px; color:#9ca3af;'>Separación de gastos fijos vs gastos variables del periodo.</p>
</div>
""", unsafe_allow_html=True)
        tot_gast = gastos_fijos_mes + gastos_var_mes
        if tot_gast > 0:
            pct_fijo = (gastos_fijos_mes / tot_gast) * 100
            pct_var = (gastos_var_mes / tot_gast) * 100
            st.progress(gastos_fijos_mes / tot_gast, text=f"Fijo: {pct_fijo:.1f}%")
            st.progress(gastos_var_mes / tot_gast, text=f"Variable: {pct_var:.1f}%")
            st.write(f"* Gastos Fijos del mes: **RD$ {gastos_fijos_mes:,.2f}**")
            st.write(f"* Gastos Variables del mes: **RD$ {gastos_var_mes:,.2f}**")
        else:
            st.info("No hay transacciones de gastos registradas para el mes actual.")

    st.markdown("---")

    st.subheader("📈 Proyecciones de Flujo de Caja (Próximos 3 Meses)")
    
    datos_hist_proj = []
    for m in meses_rango[-3:]:
        v = float(ventas_mensuales.get(m, 0.0))
        g = float(gastos_mensuales.get(m, 0.0))
        datos_hist_proj.append({"Mes": m, "Ventas": v, "Gastos": g, "Tipo": "Histórico"})
        
    for i in range(3):
        datos_hist_proj.append({
            "Mes": meses_proj[i],
            "Ventas": proj_ventas[i],
            "Gastos": proj_gastos[i],
            "Tipo": "Proyección IA"
        })
        
    df_chart = pd.DataFrame(datos_hist_proj)
    st.dataframe(df_chart, use_container_width=True)
    
    try:
        df_chart_pivot = df_chart.set_index("Mes")[["Ventas", "Gastos"]]
        st.line_chart(df_chart_pivot)
    except Exception:
        pass

    st.markdown("---")
    st.markdown("""
<div style='background-color:#1e1b4b; border:1px solid #4338ca; border-radius:10px; padding:20px; margin-bottom:20px;'>
<h3 style='margin:0 0 10px 0; color:#f3f4f6;'>🤖 Análisis y Diagnóstico Predictivo de IA</h3>
<p style='font-size:13.5px; color:#c7d2fe; margin-bottom:15px;'>El motor de IA supervisada ha analizado la tendencia de tu negocio y recomienda tomar las siguientes medidas de optimización financiera:</p>
</div>
""", unsafe_allow_html=True)

    recom_col1, recom_col2 = st.columns(2)
    with recom_col1:
        if m_v > 0:
            st.success("📈 **Tendencia de Ventas en Alza:** La pendiente de ventas es positiva. El modelo predictivo proyecta un crecimiento sostenido para los próximos meses. Es un excelente momento para expandir inventario de alta rotación.")
        elif m_v < 0:
            st.warning("📉 **Tendencia de Ventas a la Baja:** Se detectó una pendiente negativa en la facturación mensual. Se sugiere lanzar promociones especiales y revisar los precios de los productos más vendidos.")
        else:
            st.info("📊 **Ventas Estables / Datos Insuficientes:** No hay suficiente historial de ventas para proyectar una tendencia clara. Siga registrando sus facturas para habilitar la predicción automática.")

    with recom_col2:
        if m_g > m_v and m_v > 0:
            st.error("🚨 **¡Alerta de Márgenes!** Tus gastos mensuales proyectados están creciendo a un ritmo mayor que tus ventas. Debes aplicar un plan de reducción de gastos variables inmediato para proteger tu utilidad.")
        elif m_g < 0:
            st.success("🟢 **Control de Gastos Óptimo:** La tendencia de egresos es descendente. Se felicita la administración por la contención de gastos fijos y variables del negocio.")
        else:
            st.info("💡 **Consejo de Capital de Trabajo:** Recomendamos mantener un fondo de reserva equivalente a al menos 1.5 veces los gastos fijos mensuales proyectados para contingencias.")




