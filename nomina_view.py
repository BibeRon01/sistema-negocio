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

# =========================================================
# CONSTANTES TSS Y ISR DOMINICANAS POR AÑO DE VIGENCIA
# =========================================================
NOMINA_PARAMETROS_POR_ANO = {
    2024: {
        "TSS": {
            "sfs_empleado": 0.0304,
            "afp_empleado": 0.0287,
            "sfs_empleador": 0.0709,
            "afp_empleador": 0.0710,
            "arl_empleador": 0.0110,
            "infotep_empleador": 0.01,
        },
        "ISR_TRAMOS": [
            (72260.25, 6647.92, 0.25),
            (52027.42, 2601.36, 0.20),
            (34685.00, 0.0,     0.15),
        ]
    },
    2025: {
        "TSS": {
            "sfs_empleado": 0.0304,
            "afp_empleado": 0.0287,
            "sfs_empleador": 0.0709,
            "afp_empleador": 0.0710,
            "arl_empleador": 0.0110,
            "infotep_empleador": 0.01,
        },
        "ISR_TRAMOS": [
            (72260.25, 6647.92, 0.25),
            (52027.42, 2601.36, 0.20),
            (34685.00, 0.0,     0.15),
        ]
    },
    2026: {
        "TSS": {
            "sfs_empleado": 0.0304,
            "afp_empleado": 0.0287,
            "sfs_empleador": 0.0709,
            "afp_empleador": 0.0710,
            "arl_empleador": 0.0110,
            "infotep_empleador": 0.01,
        },
        "ISR_TRAMOS": [
            (72260.25, 6647.92, 0.25),
            (52027.42, 2601.36, 0.20),
            (34685.00, 0.0,     0.15),
        ]
    }
}

def obtener_parametros_nomina(ano: int = None) -> tuple[dict, list[tuple]]:
    if not ano:
        ano = date.today().year
    
    anos_disponibles = sorted(list(NOMINA_PARAMETROS_POR_ANO.keys()))
    if ano not in NOMINA_PARAMETROS_POR_ANO:
        if ano < anos_disponibles[0]:
            ano_ref = anos_disponibles[0]
        else:
            ano_ref = anos_disponibles[-1]
    else:
        ano_ref = ano
        
    params = NOMINA_PARAMETROS_POR_ANO[ano_ref]
    return params["TSS"], params["ISR_TRAMOS"]

def calcular_nomina_completa(sueldo_bruto: float, periodo: str = "mensual", ano: int = None) -> dict:
    TSS, ISR_TRAMOS = obtener_parametros_nomina(ano)
    """Calcula deducciones empleado + costo empleador completo."""
    factor = {"mensual": 1.0, "quincenal": 0.5, "semanal": 0.25}.get(periodo, 1.0)
    bruto_mes = sueldo_bruto / factor  # siempre calculamos sobre base mensual

    # Topes de cotización TSS 2026 (SFS: RD$ 232,230.00 | AFP: RD$ 464,460.00 | ARL: RD$ 92,892.00)
    TOPE_SFS = 232230.00
    TOPE_AFP = 464460.00
    TOPE_ARL = 92892.00

    base_sfs = min(bruto_mes, TOPE_SFS)
    base_afp = min(bruto_mes, TOPE_AFP)
    base_arl = min(bruto_mes, TOPE_ARL)

    # Deducciones empleado
    sfs_e  = round(base_sfs * TSS["sfs_empleado"], 2)
    afp_e  = round(base_afp * TSS["afp_empleado"], 2)
    tss_e  = sfs_e + afp_e
    base_isr = bruto_mes - tss_e

    isr = 0.0
    for limite, fijo, tasa in ISR_TRAMOS:
        if base_isr > limite:
            isr = round(fijo + (base_isr - limite) * tasa, 2)
            break

    neto_mes = round(bruto_mes - tss_e - isr, 2)
    neto_periodo = round(neto_mes * factor, 2)

    # Costo empleador (sobre sueldo mensual topeado)
    sfs_p      = round(base_sfs * TSS["sfs_empleador"], 2)
    afp_p      = round(base_afp * TSS["afp_empleador"], 2)
    arl_p      = round(base_arl * TSS["arl_empleador"], 2)
    infotep_p  = round(bruto_mes * TSS["infotep_empleador"], 2)
    tss_p      = sfs_p + afp_p + arl_p + infotep_p
    costo_total = round(bruto_mes + tss_p, 2)

    return {
        "sueldo_bruto":      round(bruto_mes * factor, 2),
        "sueldo_bruto_mes":  bruto_mes,
        "sfs_empleado":      sfs_e,
        "afp_empleado":      afp_e,
        "tss_empleado":      tss_e,
        "base_isr":          base_isr,
        "isr":               isr,
        "neto_pagar":        neto_periodo,
        "neto_pagar_mes":    neto_mes,
        # Empleador
        "sfs_empleador":     sfs_p,
        "afp_empleador":     afp_p,
        "arl_empleador":     arl_p,
        "infotep_empleador": infotep_p,
        "tss_empleador":     tss_p,
        "costo_total_mes":   costo_total,
    }


def generar_comprobante_nomina_html(empleado: str, cargo: str, periodo: str,
                                    fecha_str: str, d: dict, empresa: str = "A&M") -> str:
    """Genera un comprobante de nómina imprimible en HTML."""
    return f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Courier New', monospace; max-width:700px; margin:0 auto; padding:20px; color:#111; }}
  h2 {{ text-align:center; font-size:16px; margin:0; }}
  .sub {{ text-align:center; font-size:12px; color:#555; margin-bottom:10px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; margin-top:8px; }}
  th {{ background:#1a1a2e; color:#fff; padding:5px 8px; text-align:left; }}
  td {{ padding:4px 8px; border-bottom:1px solid #eee; }}
  .section {{ font-weight:bold; background:#f4f4f4; padding:4px 8px; margin-top:6px; }}
  .total-row {{ font-weight:bold; background:#e8f5e9; }}
  .total-row-red {{ font-weight:bold; background:#ffebee; }}
  .neto {{ font-size:16px; font-weight:bold; text-align:center; margin-top:12px; padding:10px; border:2px solid #13783b; border-radius:8px; }}
  .firma {{ display:flex; justify-content:space-between; margin-top:30px; font-size:11px; }}
  .firma div {{ border-top:1px solid #999; padding-top:4px; width:40%; text-align:center; }}
  @media print {{ button {{ display:none; }} }}
</style>
</head>
<body>
<h2>🧾 COMPROBANTE DE NÓMINA</h2>
<div class="sub">{empresa} | Período: {periodo.upper()} | Fecha: {fecha_str}</div>
<hr>
<table>
  <tr><th colspan="2">DATOS DEL EMPLEADO</th></tr>
  <tr><td>Nombre</td><td><b>{empleado}</b></td></tr>
  <tr><td>Cargo / Puesto</td><td>{cargo}</td></tr>
  <tr><td>Período de Pago</td><td>{periodo.capitalize()}</td></tr>
  <tr><td>Fecha de Pago</td><td>{fecha_str}</td></tr>
</table>

<table>
  <tr><th colspan="2">INGRESOS</th><th></th></tr>
  <tr><td>Sueldo Bruto ({periodo})</td><td style="text-align:right">RD$ {d['sueldo_bruto']:,.2f}</td></tr>
</table>

<div class="section">DEDUCCIONES DEL EMPLEADO</div>
<table>
  <tr><td>SFS (Salud Familiar) — 3.04%</td><td style="text-align:right">- RD$ {d['sfs_empleado']:,.2f}</td></tr>
  <tr><td>AFP (Fondo de Pensiones) — 2.87%</td><td style="text-align:right">- RD$ {d['afp_empleado']:,.2f}</td></tr>
  <tr><td>Total TSS Empleado (5.91%)</td><td style="text-align:right"><b>- RD$ {d['tss_empleado']:,.2f}</b></td></tr>
  <tr><td>Base Imponible ISR</td><td style="text-align:right">RD$ {d['base_isr']:,.2f}</td></tr>
  <tr><td>ISR Retenido (Escala DGII)</td><td style="text-align:right">- RD$ {d['isr']:,.2f}</td></tr>
</table>

<div class="neto">✅ NETO A PAGAR: RD$ {d['neto_pagar']:,.2f}</div>

<div class="section">COSTO PARA EL EMPLEADOR (informativo)</div>
<table>
  <tr><td>SFS Empleador — 7.09%</td><td style="text-align:right">RD$ {d['sfs_empleador']:,.2f}</td></tr>
  <tr><td>AFP Empleador — 7.10%</td><td style="text-align:right">RD$ {d['afp_empleador']:,.2f}</td></tr>
  <tr><td>ARL (Riesgos Laborales) — 1.10%</td><td style="text-align:right">RD$ {d['arl_empleador']:,.2f}</td></tr>
  <tr><td>INFOTEP — 1.00%</td><td style="text-align:right">RD$ {d['infotep_empleador']:,.2f}</td></tr>
  <tr class="total-row"><td>Total TSS Empleador</td><td style="text-align:right">RD$ {d['tss_empleador']:,.2f}</td></tr>
  <tr class="total-row"><td>Costo Total Mensual al Empleador</td><td style="text-align:right">RD$ {d['costo_total_mes']:,.2f}</td></tr>
</table>

<div class="firma">
  <div>Empleado: {empleado}<br>Firma: _________________</div>
  <div>Empleador: {empresa}<br>Firma: _________________</div>
</div>

<script>
  window.onload = function() {{ setTimeout(function() {{ window.print(); }}, 400); }};
</script>
</body>
</html>
"""

def render_empleados():
    st.title("👥 Empleados")
    next_emp_id = generar_codigo_secuencial("empleados")
    st.caption(f"Identificador del próximo empleado: **{next_emp_id}**. Este módulo es solo para registrar datos del empleado. Para pagar quincenas, comisiones o bonos usa el menú Pagos Empleados.")

    with st.expander("📥 Subir Excel / CSV de empleados"):
        st.write("Columnas esperadas: nombre, puesto, sueldo, tipo_salario, frecuencia_pago. Activo opcional.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_empleados")
        if archivo is not None and st.button("Cargar empleados"):
            df = leer_archivo_subido(archivo)
            faltan = [c for c in ["nombre", "puesto", "sueldo", "tipo_salario", "frecuencia_pago"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                count = 0
                for _, row in df.iterrows():
                    insertar(
                        "empleados",
                        {
                            "fecha": parsear_fecha(row["fecha"]) if "fecha" in df.columns else ahora_str(),
                            "nombre": limpiar_texto(row["nombre"]),
                            "puesto": limpiar_texto(row["puesto"]),
                            "sueldo": float(limpiar_numero(row["sueldo"]) or 0),
                            "tipo_salario": limpiar_texto(row["tipo_salario"]),
                            "frecuencia_pago": limpiar_texto(row["frecuencia_pago"]),
                            "activo": bool(row["activo"]) if "activo" in df.columns else True,
                            "observacion": limpiar_texto(row["observacion"]) if "observacion" in df.columns else "",
                        },
                    )
                    count += 1
                st.success(f"Se cargaron {count} empleados.")
                st.rerun()

    with st.expander("➕ Agregar empleado manual", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="emp_fecha")
            nombre = st.text_input("Nombre", key="emp_nombre")
            puesto = st.text_input("Puesto", key="emp_puesto")
            sueldo = st.number_input("Sueldo", min_value=0.0, step=1.0, key="emp_sueldo")
            metodo_pago = st.selectbox("Método de pago", ["", "efectivo", "transferencia", "tarjeta"], key="emp_metodo_pago")
        with c2:
            tipo_salario = st.selectbox("Tipo salario", ["fijo", "variable"], key="emp_tipo_salario")
            frecuencia_pago = st.selectbox("Frecuencia pago", ["mensual", "quincenal", "semanal"], key="emp_frec")
            dia_pago_1 = st.number_input("Día pago 1", min_value=0.0, step=1.0, value=0.0, key="emp_dia_pago_1")
            dia_pago_2 = st.number_input("Día pago 2", min_value=0.0, step=1.0, value=0.0, key="emp_dia_pago_2")
            activo = st.checkbox("Activo", value=True, key="emp_activo")
            observacion = st.text_area("Observación", key="emp_obs")

        if st.button("Guardar empleado"):
            payload_empleado = {
                "fecha": str(fecha),
                "nombre": nombre,
                "puesto": puesto,
                "sueldo": float(sueldo),
                "tipo_salario": tipo_salario,
                "frecuencia_pago": frecuencia_pago,
                "metodo_pago": metodo_pago or None,
                "dia_pago_1": None if float(dia_pago_1) == 0 else float(dia_pago_1),
                "dia_pago_2": None if float(dia_pago_2) == 0 else float(dia_pago_2),
                "activo": activo,
                "observacion": observacion,
            }
            if insertar("empleados", payload_empleado):
                st.success("Empleado guardado.")
                st.rerun()

    df = DATA["empleados"].copy()
    if not df.empty:
        txt = st.text_input("Buscar empleado", key="buscar_emp")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "empleados")
        render_crud_generico("empleados", df, "🛠️ Editar / eliminar empleados")
    else:
        st.info("No hay empleados registrados.")


# =========================================================
# ADELANTOS EMPLEADOS
# =========================================================


def render_nomina():
    st.title("📑 Nómina Dominicana — TSS & ISR")
    st.caption("Cálculo legal completo de retenciones TSS (SFS + AFP) e ISR del empleado **y** costo TSS del empleador (AFP, SFS, ARL, INFOTEP) según normativas DGII/TSS vigentes.")

    empleados_df = DATA.get("empleados", pd.DataFrame()).copy()
    cfg = obtener_configuracion()
    nombre_empresa = cfg.get("negocio_nombre") or "A&M"

    if empleados_df.empty:
        st.warning("No hay empleados registrados. Ve al módulo **Empleados** para agregarlos.")
        st.stop()

    tab_calc, tab_hist, tab_carga = st.tabs(["🧮 Calculadora y Pago", "📋 Historial Nómina", "📊 Carga TSS Empleador"])

    with tab_calc:
        st.subheader("🧮 Calculadora de Nómina con Deducciones Legales")

        c1, c2 = st.columns(2)
        with c1:
            emp_lista = empleados_df["nombre"].tolist() if "nombre" in empleados_df.columns else []
            emp_sel = st.selectbox("Empleado", emp_lista, key="nom_calc_emp")

            # Pre-llenar sueldo del empleado seleccionado
            sueldo_default = 0.0
            if emp_sel and "sueldo" in empleados_df.columns:
                row_emp = empleados_df[empleados_df["nombre"] == emp_sel]
                if not row_emp.empty:
                    sueldo_default = float(row_emp.iloc[0].get("sueldo") or 0)

            sueldo_bruto = st.number_input("Sueldo Bruto del Período (RD$)", min_value=0.0,
                                           step=100.0, value=sueldo_default, key="nom_bruto")

            cargo_emp = ""
            if emp_sel and "puesto" in empleados_df.columns:
                row_emp = empleados_df[empleados_df["nombre"] == emp_sel]
                if not row_emp.empty:
                    cargo_emp = str(row_emp.iloc[0].get("puesto") or "")

        with c2:
            period_nom = st.selectbox("Período", ["mensual", "quincenal", "semanal"], key="nom_period")
            metodo_nom = st.selectbox("Método de pago", ["efectivo", "transferencia", "tarjeta"], key="nom_metodo")
            obs_nom = st.text_area("Observación (opcional)", key="nom_obs")

        if sueldo_bruto > 0:
            d = calcular_nomina_completa(sueldo_bruto, period_nom)

            st.divider()
            st.markdown("### 📊 Desglose Completo")

            # ── Empleado ──────────────────────────────────────────────────
            st.markdown("#### 👤 Deducciones del Empleado")
            col_a1, col_a2, col_a3, col_a4, col_a5 = st.columns(5)
            col_a1.metric("Sueldo Bruto", f"RD$ {d['sueldo_bruto']:,.2f}")
            col_a2.metric("SFS (3.04%)", f"-RD$ {d['sfs_empleado']:,.2f}")
            col_a3.metric("AFP (2.87%)", f"-RD$ {d['afp_empleado']:,.2f}")
            col_a4.metric("ISR Retenido", f"-RD$ {d['isr']:,.2f}")
            col_a5.metric("🟢 NETO A PAGAR", f"RD$ {d['neto_pagar']:,.2f}", delta=f"-RD$ {d['sueldo_bruto']-d['neto_pagar']:,.2f}")

            # ── Empleador ─────────────────────────────────────────────────
            st.markdown("#### 🏢 Costo TSS del Empleador (su aporte adicional)")
            col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)
            col_b1.metric("SFS Empleador (7.09%)", f"RD$ {d['sfs_empleador']:,.2f}")
            col_b2.metric("AFP Empleador (7.10%)", f"RD$ {d['afp_empleador']:,.2f}")
            col_b3.metric("ARL (1.10%)", f"RD$ {d['arl_empleador']:,.2f}")
            col_b4.metric("INFOTEP (1.00%)", f"RD$ {d['infotep_empleador']:,.2f}")
            col_b5.metric("💰 Costo Total/Mes", f"RD$ {d['costo_total_mes']:,.2f}",
                           delta=f"+RD$ {d['tss_empleador']:,.2f} TSS empleador",
                           delta_color="inverse")

            st.info(f"📋 **Base ISR:** RD$ {d['base_isr']:,.2f} (sueldo mensual menos TSS empleado). "
                    f"El empleador asume un **{(d['tss_empleador']/d['sueldo_bruto_mes']*100):.1f}% adicional** sobre el bruto mensual.")

            st.divider()
            col_btn1, col_btn2 = st.columns(2)

            with col_btn1:
                if st.button("✅ Registrar Pago de Nómina", key="btn_nom_reg", type="primary", use_container_width=True):
                    # C-06: Control de límites salariales en nómina
                    pagos_mes = DATA.get("pagos_empleados", DATA.get("adelantos_empleados", pd.DataFrame()))
                    if not pagos_mes.empty and "empleado" in pagos_mes.columns and "monto" in pagos_mes.columns:
                        pagos_emp = pagos_mes[pagos_mes["empleado"].astype(str) == str(emp_sel)]
                        acumulado_mes = float(pagos_emp["monto"].sum()) if not pagos_emp.empty else 0.0
                        if (acumulado_mes + float(d["neto_pagar"])) > (sueldo_default * 1.05) and not (obs_nom and obs_nom.strip()):
                            st.error(f"⚠️ **Exceso Salarial sin Justificación (C-06):** El pago acumulado mensual para **{emp_sel}** (RD$ {acumulado_mes + d['neto_pagar']:,.2f}) supera su sueldo base mensual (RD$ {sueldo_default:,.2f}). Debe ingresar una **observación** justificando el motivo (ej: bonificación, horas extras, incentivo).")
                            st.stop()

                    try:
                        detalle_txt = (f"NOMINA {period_nom.upper()} | Bruto: {d['sueldo_bruto']:.2f} | "
                                       f"SFS: {d['sfs_empleado']:.2f} | AFP: {d['afp_empleado']:.2f} | "
                                       f"ISR: {d['isr']:.2f} | Neto: {d['neto_pagar']:.2f}" +
                                       (f" | {obs_nom}" if obs_nom else ""))
                        payload_nom = {
                            "fecha": str(date.today()),
                            "empleado": emp_sel,
                            "monto": float(d["neto_pagar"]),
                            "detalle": detalle_txt,
                            "tipo_pago": "salario",
                            "metodo_pago": metodo_nom,
                            "concepto": "salario",
                        }
                        if insertar("adelantos_empleados", payload_nom):
                            # Asiento TSS empleado
                            try:
                                supabase.table("movimientos_contables").insert({
                                    "empresa_id": obtener_tenant_actual(),
                                    "fecha": datetime.now().isoformat(),
                                    "concepto": f"TSS Empleado (SFS+AFP) — {emp_sel} {period_nom}",
                                    "debito": float(d["tss_empleado"]),
                                    "credito": float(d["tss_empleado"]),
                                    "referencia": f"tss_emp:{emp_sel}",
                                }).execute()
                            except Exception:
                                pass
                            # Asiento ISR retenido
                            if d["isr"] > 0:
                                try:
                                    supabase.table("movimientos_contables").insert({
                                        "empresa_id": obtener_tenant_actual(),
                                        "fecha": datetime.now().isoformat(),
                                        "concepto": f"ISR Retenido Nómina — {emp_sel} {period_nom}",
                                        "debito": float(d["isr"]),
                                        "credito": float(d["isr"]),
                                        "referencia": f"isr_nom:{emp_sel}",
                                    }).execute()
                                except Exception:
                                    pass
                            st.success(f"✅ Nómina registrada. Neto pagado: **RD$ {d['neto_pagar']:,.2f}**")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error registrando nómina: {e}")

            with col_btn2:
                html_comp = generar_comprobante_nomina_html(
                    emp_sel, cargo_emp, period_nom,
                    str(date.today()), d, nombre_empresa
                )
                st.download_button(
                    "🖨️ Imprimir Comprobante de Nómina",
                    data=html_comp.encode("utf-8"),
                    file_name=f"Nomina_{emp_sel.replace(' ', '_')}_{date.today()}.html",
                    mime="text/html",
                    key="btn_nom_imprimir",
                    use_container_width=True
                )

    with tab_hist:
        st.subheader("📋 Historial de Pagos de Nómina")
        df_hist = DATA.get("adelantos_empleados", pd.DataFrame()).copy()
        if not df_hist.empty:
            if "tipo_pago" in df_hist.columns:
                df_hist = df_hist[df_hist["tipo_pago"].fillna("").isin(["salario", "quincena"])]
            d1_h, d2_h = selector_fechas_universal("nom_hist")
            df_hist = _filtrar_periodo_df(df_hist, d1_h, d2_h)

            # Métricas rápidas
            total_neto = suma_col(df_hist, "monto")
            cant_pagos = len(df_hist)
            emp_distintos = df_hist["empleado"].nunique() if "empleado" in df_hist.columns else 0

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Neto Pagado", f"RD$ {total_neto:,.2f}")
            m2.metric("Nóminas Registradas", cant_pagos)
            m3.metric("Empleados en Período", emp_distintos)

            # Filtro por empleado
            if "empleado" in df_hist.columns:
                emp_filtro = st.multiselect("Filtrar por empleado", df_hist["empleado"].unique().tolist(), key="nom_hist_emp_filtro")
                if emp_filtro:
                    df_hist = df_hist[df_hist["empleado"].isin(emp_filtro)]

            st.dataframe(df_hist, use_container_width=True)
            descargar_archivos(df_hist, "nomina_historial")
        else:
            st.info("No hay pagos de nómina registrados todavía.")

    with tab_carga:
        st.subheader("📊 Proyección de Carga TSS Total del Negocio")
        st.caption("Muestra el costo TSS mensual estimado que el negocio debe pagar a la TSS/DGII por toda su nómina activa.")

        emp_activos = empleados_df.copy()
        if "activo" in emp_activos.columns:
            emp_activos = emp_activos[emp_activos["activo"].fillna(True).astype(bool)]

        if emp_activos.empty:
            st.info("No hay empleados activos registrados.")
        else:
            rows_tss = []
            total_brutos = 0.0
            total_neto_emp = 0.0
            total_tss_emp = 0.0
            total_tss_patron = 0.0
            total_isr_ret = 0.0

            for _, emp_row in emp_activos.iterrows():
                nombre_emp = str(emp_row.get("nombre") or "—")
                cargo_t = str(emp_row.get("puesto") or "—")
                sueldo_t = float(emp_row.get("sueldo") or 0)
                frec_t = str(emp_row.get("frecuencia_pago") or "mensual")
                if sueldo_t == 0:
                    continue
                dt = calcular_nomina_completa(sueldo_t, frec_t)
                rows_tss.append({
                    "Empleado": nombre_emp,
                    "Cargo": cargo_t,
                    "Sueldo Bruto/Mes": dt["sueldo_bruto_mes"],
                    "TSS Empleado": dt["tss_empleado"],
                    "ISR Retenido": dt["isr"],
                    "Neto Empleado": dt["neto_pagar_mes"],
                    "TSS Patronal": dt["tss_empleador"],
                    "Costo Total/Mes": dt["costo_total_mes"],
                })
                total_brutos += dt["sueldo_bruto_mes"]
                total_neto_emp += dt["neto_pagar_mes"]
                total_tss_emp += dt["tss_empleado"]
                total_isr_ret += dt["isr"]
                total_tss_patron += dt["tss_empleador"]

            if rows_tss:
                df_tss = pd.DataFrame(rows_tss)
                # Agregar fila de totales
                totales = {
                    "Empleado": "TOTAL",
                    "Cargo": "—",
                    "Sueldo Bruto/Mes": total_brutos,
                    "TSS Empleado": total_tss_emp,
                    "ISR Retenido": total_isr_ret,
                    "Neto Empleado": total_neto_emp,
                    "TSS Patronal": total_tss_patron,
                    "Costo Total/Mes": total_brutos + total_tss_patron,
                }
                df_totales = pd.concat([df_tss, pd.DataFrame([totales])], ignore_index=True)

                # Formatear columnas numéricas
                for col in ["Sueldo Bruto/Mes", "TSS Empleado", "ISR Retenido", "Neto Empleado", "TSS Patronal", "Costo Total/Mes"]:
                    df_totales[col] = df_totales[col].apply(lambda x: f"RD$ {x:,.2f}" if isinstance(x, (int, float)) else x)

                st.dataframe(df_totales, use_container_width=True, hide_index=True)

                # Métricas globales
                st.divider()
                mg1, mg2, mg3, mg4 = st.columns(4)
                mg1.metric("Nómina Bruta Mensual", f"RD$ {total_brutos:,.2f}")
                mg2.metric("TSS Empleados (reten.)", f"RD$ {total_tss_emp:,.2f}")
                mg3.metric("TSS Patronal (costo +)", f"RD$ {total_tss_patron:,.2f}")
                mg4.metric("Costo Total Real/Mes", f"RD$ {total_brutos + total_tss_patron:,.2f}",
                           delta=f"+{total_tss_patron/total_brutos*100:.1f}% sobre bruto" if total_brutos > 0 else "")

                st.warning(f"⚠️ El negocio debe declarar **RD$ {total_tss_emp + total_tss_patron:,.2f}** mensuales a la TSS (suma TSS empleado + patronal), más **RD$ {total_isr_ret:,.2f}** de ISR retenido a la DGII.")
                descargar_archivos(df_tss, "carga_tss_empleador")
            else:
                st.info("Los empleados activos no tienen sueldo registrado.")








def render_pagos_empleados():
    st.title("💵 Pagos a Empleados")
    st.caption("Aquí es donde se aplica el pago real. El módulo Empleados solo guarda los datos del empleado y su sueldo acordado.")

    empleados_df = DATA.get("empleados", pd.DataFrame()).copy()
    nombres_empleados = empleados_df["nombre"].astype(str).tolist() if not empleados_df.empty and "nombre" in empleados_df.columns else []
    columnas_pagos = DATA["adelantos_empleados"].columns.tolist() if not DATA["adelantos_empleados"].empty else []

    with st.expander("➕ Aplicar pago a empleado", expanded=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            fecha_pago = st.date_input("Fecha de pago", value=date.today(), key="pago_emp_fecha")
            empleado = st.selectbox("Empleado", nombres_empleados, key="pago_emp_nombre") if nombres_empleados else st.text_input("Empleado", key="pago_emp_nombre_txt")

        with c2:
            tipo_pago = st.selectbox(
                "Tipo de pago",
                ["quincena", "salario", "comisión", "bono", "adelanto", "otro"],
                key="pago_emp_tipo"
            )
            monto_pago = st.number_input("Monto pagado", min_value=0.0, step=1.0, key="pago_emp_monto")

        with c3:
            metodo_pago = st.selectbox(
                "Método de pago",
                ["efectivo", "transferencia", "tarjeta"],
                key="pago_emp_metodo"
            )
            observacion_pago = st.text_area("Observación", key="pago_emp_obs")

        # C-06: Buscar sueldo configurado del empleado y calcular acumulado pagado este mes
        sueldo_base_cfg = 0.0
        if empleado and not empleados_df.empty and "nombre" in empleados_df.columns:
            match_emp = empleados_df[empleados_df["nombre"].astype(str).apply(normalizar_texto) == normalizar_texto(str(empleado))]
            if not match_emp.empty:
                sueldo_base_cfg = float(limpiar_numero(match_emp.iloc[0].get("sueldo")) or 0.0)

        # Calcular acumulado del mes corriente
        pagos_df_all = DATA.get("adelantos_empleados", pd.DataFrame()).copy()
        acumulado_mes = 0.0
        if not pagos_df_all.empty and "empleado" in pagos_df_all.columns:
            # Filtrar por empleado y mes corriente
            pagos_emp = pagos_df_all[pagos_df_all["empleado"].astype(str).apply(normalizar_texto) == normalizar_texto(str(empleado))].copy()
            if not pagos_emp.empty and "fecha" in pagos_emp.columns:
                pagos_emp["_fecha_dt"] = pd.to_datetime(pagos_emp["fecha"], errors="coerce")
                mes_act = fecha_pago.month
                ano_act = fecha_pago.year
                pagos_emp_mes = pagos_emp[(pagos_emp["_fecha_dt"].dt.month == mes_act) & (pagos_emp["_fecha_dt"].dt.year == ano_act)]
                acumulado_mes = float(suma_col(pagos_emp_mes, "monto"))

        nuevo_total_mes = acumulado_mes + float(monto_pago)
        exceso_salario = nuevo_total_mes - sueldo_base_cfg if sueldo_base_cfg > 0 else 0.0

        if sueldo_base_cfg > 0 and exceso_salario > 0.01:
            st.warning(f"⚠️ **Alerta de Exceso Salarial (C-06):** El pago de **RD$ {monto_pago:,.2f}** sumado a los pagos de este mes (**RD$ {acumulado_mes:,.2f}**) da un total de **RD$ {nuevo_total_mes:,.2f}**, superando el sueldo base mensual de **RD$ {sueldo_base_cfg:,.2f}** (Excedente: **RD$ {exceso_salario:,.2f}**).")

        if st.button("Guardar pago de empleado", key="btn_guardar_pago_empleado_real"):
            if not limpiar_texto(empleado):
                st.error("Debes seleccionar o escribir el empleado.")
            elif monto_pago <= 0:
                st.error("El monto pagado debe ser mayor que cero.")
            elif sueldo_base_cfg > 0 and exceso_salario > 0.01 and not (observacion_pago and observacion_pago.strip()):
                st.error("⚠️ **Justificación Obligatoria:** Este pago supera el sueldo mensual configurado del empleado. Debe ingresar una observación especificando la razón (ej. horas extras, bonificación, comisión).")
            else:
                detalle_final = f"tipo_pago: {tipo_pago} | metodo_pago: {metodo_pago}"
                if observacion_pago:
                    detalle_final += f" | {observacion_pago}"

                payload_pago = {
                    "fecha": str(fecha_pago),
                    "empleado": empleado,
                    "monto": float(monto_pago),
                    "detalle": detalle_final,
                }

                if "tipo_pago" in columnas_pagos:
                    payload_pago["tipo_pago"] = tipo_pago
                if "metodo_pago" in columnas_pagos:
                    payload_pago["metodo_pago"] = metodo_pago
                if "concepto" in columnas_pagos:
                    payload_pago["concepto"] = tipo_pago

                if insertar("adelantos_empleados", payload_pago):
                    if sueldo_base_cfg > 0 and exceso_salario > 0.01:
                        try:
                            registrar_auditoria_pro(
                                accion="exceso_salario_empleado",
                                modulo="Nómina",
                                tabla_afectada="adelantos_empleados",
                                impacto_economico=float(exceso_salario),
                                nivel_riesgo="medio",
                                riesgo_score=40.0,
                                descripcion=f"Pago excedente sobre sueldo base a {empleado}. Sueldo: {sueldo_base_cfg:.2f}, Acumulado mes: {nuevo_total_mes:.2f}, Excedente: {exceso_salario:.2f}. Justificación: {observacion_pago}"
                            )
                        except Exception:
                            pass
                    st.success("Pago aplicado correctamente. Ya debe reflejarse en el Dashboard.")
                    st.rerun()

    st.subheader("📋 Historial de pagos aplicados")
    df = DATA["adelantos_empleados"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("pagos_empleados")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar pago", key="buscar_pagos_empleados")
        df = buscar_df(df, txt)

        total_pagos = suma_col(df, "monto")
        st.metric("Total pagado en el período", f"RD$ {total_pagos:,.2f}")

        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "pagos_empleados")
        render_crud_generico("adelantos_empleados", df, "🛠️ Editar / eliminar pagos aplicados")
    else:
        st.info("No hay pagos registrados todavía.")



# =========================================================
# PÉRDIDAS
# =========================================================


