# Modularized view for A&M ERP v2
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime, date, timedelta
from typing import Any

from core.db import *
from core.auth import *
from core.utils import *
from core.helpers import *

def render_estado_resultados():
    st.title("🧾 Estado de Resultados PRO")
    if not (es_admin() or tiene_permiso("puede_ver_reportes")):
        st.error("No tienes permiso para ver este reporte.")
        st.stop()

    st.caption("Reporte financiero real: ventas, costo de ventas, gastos, utilidad, créditos, retiros y reinversión.")

    desde_er, hasta_er = selector_fechas_universal("er_pro")

    with st.expander("⚙️ Configuración financiera del reporte", expanded=False):
        cfg_fin = obtener_config_financiera()
        st.write("Configura ISR, depreciación y datos del negocio desde Supabase en la tabla configuracion_financiera.")
        st.json({
            "nombre_negocio": cfg_fin.get("nombre_negocio", "BIBE RON 01"),
            "porcentaje_isr": cfg_fin.get("porcentaje_isr", 0),
            "incluir_isr": cfg_fin.get("incluir_isr", False),
            "incluir_depreciacion": cfg_fin.get("incluir_depreciacion", True),
        })

    with st.expander("🔎 Ver datos base usados por el reporte", expanded=False):
        ventas_dbg = _filtrar_periodo_df(_df_actual("ventas"), desde_er, hasta_er)
        st.write("Ventas encontradas en el periodo:", len(ventas_dbg))
        if not ventas_dbg.empty:
            cols_dbg = [c for c in ["fecha", "numero_factura", "total", "total_contable", "subtotal", "venta_bruta", "descuento", "descuento_total", "metodo_pago", "usuario"] if c in ventas_dbg.columns]
            st.dataframe(ventas_dbg[cols_dbg] if cols_dbg else ventas_dbg, use_container_width=True)
        gastos_dbg = _filtrar_periodo_df(_df_actual("gastos"), desde_er, hasta_er)
        st.write("Gastos encontrados en el periodo:", len(gastos_dbg))

    render_estado_resultados_pro(desde_er, hasta_er)



def render_reportes_dgii():
    st.title("🏛️ Módulo Educativo — Reportes DGII")
    st.info(
        "ℹ️ **Aviso Informativo & Educativo:** Este módulo es exclusivamente informativo y de orientación general. "
        "AIS no prepara ni presenta declaraciones o formatos oficiales ante la DGII. "
        "Todo formulario debe remitirse mediante la Oficina Virtual (OFV) de la DGII "
        "con el apoyo de un profesional de la contabilidad.",
        icon="ℹ️"
    )

    desde_dgii, hasta_dgii = selector_fechas_universal("dgii_reports")
    periodo_str = desde_dgii.strftime("%Y%m")

    t606, t607, t608, t609, tDiarios, tIT1, tIR2 = st.tabs([
        "📋 Formato 606 (Compras)",
        "📋 Formato 607 (Ventas)",
        "🚫 Formato 608 (Anulados)",
        "🌐 Formato 609 (Exterior)",
        "📊 Diarios Fiscales",
        "💰 IT-1 (ITBIS Mensual)",
        "📑 IR-2 (ISR Anual)"
    ])

    df_compras = _filtrar_periodo_df(_df_actual("compras"), desde_dgii, hasta_dgii)
    df_ventas = _filtrar_periodo_df(_df_actual("ventas"), desde_dgii, hasta_dgii)
    if not df_ventas.empty:
        for col_anulado in ["anulado", "cancelado"]:
            if col_anulado in df_ventas.columns:
                try:
                    df_ventas = df_ventas[~df_ventas[col_anulado].fillna(False).astype(bool)].copy()
                except Exception:
                    pass

    with t606:
        st.subheader("Formato 606 - Envío de Compras de Bienes y Servicios")
        if df_compras.empty:
            st.info("No se registraron compras en el período seleccionado.")
        else:
            st.dataframe(df_compras, use_container_width=True)
            import re
            txt_lines = [f"606|{obtener_tenant_actual()[:11].ljust(11)}|{periodo_str}|{len(df_compras)}"]
            for idx, row in df_compras.iterrows():
                rnc_prov = str(row.get("proveedor_rnc") or row.get("rnc") or "").strip()
                rnc_prov = re.sub(r"\D", "", rnc_prov)
                if not rnc_prov:
                    rnc_prov = "999999999"
                tipo_id = "1" if len(rnc_prov) == 9 else ("2" if len(rnc_prov) == 11 else "3")
                
                ncf_comp = str(row.get("ncf") or row.get("numero_comprobante") or "B0100000000").strip()
                ncf_comp = re.sub(r"\s+", "", ncf_comp).upper()
                
                fecha_c = pd.to_datetime(row.get("fecha")).strftime("%Y%m%d") if row.get("fecha") else periodo_str + "01"
                monto = float(row.get("total") or row.get("monto") or 0.0)
                itbis = round(monto * 0.18, 2)
                txt_lines.append(f"{rnc_prov}|{tipo_id}|02|{ncf_comp}||{fecha_c}||{monto:.2f}|0.00|{monto:.2f}|{itbis:.2f}|0.00|0.00|0.00|0.00|0.00|0.00|")
            
            txt_content = "\n".join(txt_lines)
            st.download_button(
                label="📥 Descargar TXT 606",
                data=txt_content,
                file_name=f"DGII_606_{periodo_str}.txt",
                mime="text/plain",
                key="btn_download_606"
            )

    with t607:
        st.subheader("Formato 607 - Envío de Ventas de Bienes y Servicios")
        df_ventas_fiscal = df_ventas
        if not df_ventas.empty and "ncf" in df_ventas.columns:
            df_ventas_fiscal = df_ventas[df_ventas["ncf"].fillna("").str.strip() != ""].copy()
            
        if df_ventas_fiscal.empty:
            st.info("No se registraron ventas con NCF en el período seleccionado.")
        else:
            st.dataframe(df_ventas_fiscal, use_container_width=True)
            import re
            txt_lines = [f"607|{obtener_tenant_actual()[:11].ljust(11)}|{periodo_str}|{len(df_ventas_fiscal)}"]
            for idx, row in df_ventas_fiscal.iterrows():
                rnc_cl = str(row.get("rnc_cliente") or row.get("cliente_rnc") or row.get("rnc") or "").strip()
                rnc_cl = re.sub(r"\D", "", rnc_cl)
                if not rnc_cl or rnc_cl.lower() == "none" or rnc_cl == "999999999":
                    rnc_cl = "22400000000"
                tipo_id = "1" if len(rnc_cl) == 9 else ("2" if len(rnc_cl) == 11 else "3")
                
                ncf_v = str(row.get("ncf") or "").strip()
                ncf_v = re.sub(r"\s+", "", ncf_v).upper()
                
                fecha_v = pd.to_datetime(row.get("fecha")).strftime("%Y%m%d") if row.get("fecha") else periodo_str + "01"
                
                total = float(row.get("total") or 0.0)
                itbis = float(row.get("itbis_total") or 0.0)
                subtotal_grav = float(row.get("subtotal_gravado") or (total - itbis))
                
                txt_lines.append(f"{rnc_cl}|{tipo_id}|{ncf_v}||01|{fecha_v}||{subtotal_grav:.2f}|{itbis:.2f}|0.00|0.00|0.00|0.00|0.00|0.00|")
                
            txt_content = "\n".join(txt_lines)
            st.download_button(
                label="📥 Descargar TXT 607",
                data=txt_content,
                file_name=f"DGII_607_{periodo_str}.txt",
                mime="text/plain",
            )

    with t608:
        st.subheader("Formato 608 — Envío de Comprobantes Fiscales Anulados")
        df_ventas_raw = _df_actual("ventas")
        df_anulados = pd.DataFrame()
        if not df_ventas_raw.empty and "anulado" in df_ventas_raw.columns:
            df_anulados = df_ventas_raw[df_ventas_raw["anulado"].fillna(False).astype(bool)].copy()
            df_anulados = _filtrar_periodo_df(df_anulados, desde_dgii, hasta_dgii)
        
        if df_anulados.empty:
            st.info("No se registraron comprobantes fiscales anulados en este período.")
        else:
            st.dataframe(df_anulados, use_container_width=True)
            txt_lines_608 = [f"608|{obtener_tenant_actual()[:11].ljust(11)}|{periodo_str}|{len(df_anulados)}"]
            for idx, r in df_anulados.iterrows():
                ncf_a = str(r.get("ncf") or "").strip().upper()
                fecha_a = pd.to_datetime(r.get("fecha")).strftime("%Y%m%d") if r.get("fecha") else periodo_str + "01"
                motivo_a = str(r.get("motivo_anulacion") or "01").strip()
                txt_lines_608.append(f"{ncf_a}|{fecha_a}|{motivo_a}|")
            
            st.download_button(
                label="📥 Descargar TXT 608",
                data="\n".join(txt_lines_608),
                file_name=f"DGII_608_{periodo_str}.txt",
                mime="text/plain",
                key="btn_download_608"
            )

    with t609:
        st.subheader("Formato 609 — Envío de Pagos al Exterior")
        df_exterior = pd.DataFrame()

        st.info("Formato 609 listo para registro de retenciones a proveedores del exterior (normativa DGII).")
        txt_lines_609 = [f"609|{obtener_tenant_actual()[:11].ljust(11)}|{periodo_str}|0"]
        st.download_button(
            label="📥 Descargar TXT 609 (Plantilla)",
            data="\n".join(txt_lines_609),
            file_name=f"DGII_609_{periodo_str}.txt",
            mime="text/plain",
            key="btn_download_609"
        )

    with tDiarios:
        st.subheader("📊 Los 5 Diarios Contables y Fiscales")
        st.caption("Visualiza y audita las ventas clasificadas por su tipo de comprobante, fiscalidad o forma de cobro.")
        
        tipo_diario = st.selectbox(
            "Selecciona el Diario:",
            [
                "Diario de Ventas de Consumo (E32 / B02)",
                "Diario de Ventas de Crédito Fiscal (E31 / B01)",
                "Diario de Ventas al Contado (Cobrado completo sin crédito)",
                "Diario de Ventas a Crédito (Con balance por cobrar)",
                "Diario de Ventas sin Comprobante Fiscal (Recibos internos)"
            ],
            key="sel_diario_fiscal"
        )
        
        df_diario = df_ventas.copy() if not df_ventas.empty else pd.DataFrame()
        
        if df_diario.empty:
            st.info("No hay ventas registradas en el período seleccionado.")
        else:
            df_filtrado = pd.DataFrame()
            if tipo_diario == "Diario de Ventas de Consumo (E32 / B02)":
                df_filtrado = df_diario[df_diario["ncf"].fillna("").str.upper().str.startswith(("E32", "B02"))].copy()
            elif tipo_diario == "Diario de Ventas de Crédito Fiscal (E31 / B01)":
                df_filtrado = df_diario[df_diario["ncf"].fillna("").str.upper().str.startswith(("E31", "B01"))].copy()
            elif tipo_diario == "Diario de Ventas al Contado (Cobrado completo sin crédito)":
                # Ventas cuyo metodo_pago no es crédito y no tienen pago_credito o su metodo_pago está en ['efectivo', 'transferencia', 'tarjeta', 'mixto']
                df_filtrado = df_diario[df_diario["metodo_pago"].fillna("").str.lower() != "credito"].copy()
            elif tipo_diario == "Diario de Ventas a Crédito (Con balance por cobrar)":
                df_filtrado = df_diario[df_diario["metodo_pago"].fillna("").str.lower() == "credito"].copy()
            elif tipo_diario == "Diario de Ventas sin Comprobante Fiscal (Recibos internos)":
                # Ventas que no tienen NCF (recibos internos)
                df_filtrado = df_diario[df_diario["ncf"].fillna("").str.strip() == ""].copy()
                
            if df_filtrado.empty:
                st.info(f"No se encontraron ventas para: {tipo_diario} en este período.")
            else:
                st.write(f"**Ventas en este diario:** {len(df_filtrado)}")
                
                cols_diario_show = [c for c in ["fecha", "numero_factura", "tipo_documento", "ncf", "rnc_cliente", "cliente_nombre", "subtotal", "itbis_total", "total", "metodo_pago", "usuario"] if c in df_filtrado.columns]
                st.dataframe(df_filtrado[cols_diario_show] if cols_diario_show else df_filtrado, use_container_width=True)
                
                # Totales consolidados del diario
                tot_monto = df_filtrado["total"].sum()
                tot_itbis = df_filtrado["itbis_total"].sum() if "itbis_total" in df_filtrado.columns else 0.0
                tot_sub = df_filtrado["subtotal"].sum() if "subtotal" in df_filtrado.columns else (tot_monto - tot_itbis)
                
                c_d1, c_d2, c_d3 = st.columns(3)
                c_d1.metric("Total Subtotal (Base)", f"RD$ {tot_sub:,.2f}")
                c_d2.metric("Total ITBIS", f"RD$ {tot_itbis:,.2f}")
                c_d3.metric("Total Facturado", f"RD$ {tot_monto:,.2f}")

    # ── IT-1: Formulario de Declaración Mensual ITBIS ───────────────────
    with tIT1:
        st.subheader("💰 IT-1 — Declaración Mensual del ITBIS")
        st.caption(f"Período fiscal: **{desde_dgii.strftime('%B %Y')}**. Resumen para completar el formulario IT-1 en la DGII.")

        if df_ventas.empty and df_compras.empty:
            st.info("No hay transacciones en el período seleccionado para calcular el IT-1.")
        else:
            # ── Débito Fiscal (ITBIS cobrado en ventas) ──
            itbis_ventas = 0.0
            base_gravada_ventas = 0.0
            base_exenta_ventas = 0.0

            if not df_ventas.empty:
                for _, row in df_ventas.iterrows():
                    total_v = float(row.get("total") or 0)
                    itbis_v = float(row.get("itbis_total") or 0)
                    base_v = float(row.get("subtotal_gravado") or (total_v - itbis_v if itbis_v > 0 else 0))
                    itbis_ventas += itbis_v
                    base_gravada_ventas += base_v
                    if itbis_v == 0:
                        base_exenta_ventas += total_v

            # ── Crédito Fiscal (ITBIS pagado en compras) ──
            itbis_compras = 0.0
            base_gravada_compras = 0.0

            if not df_compras.empty:
                for _, row in df_compras.iterrows():
                    total_c = float(row.get("total") or row.get("monto") or 0)
                    itbis_c = float(row.get("itbis") or row.get("itbis_total") or round(total_c * 0.18, 2))
                    itbis_compras += itbis_c
                    base_gravada_compras += (total_c - itbis_c)

            itbis_neto = itbis_ventas - itbis_compras

            st.markdown("### 📊 Resumen IT-1")
            col1, col2, col3 = st.columns(3)
            col1.metric("🟢 Débito Fiscal (ITBIS en ventas)", f"RD$ {itbis_ventas:,.2f}")
            col2.metric("🔵 Crédito Fiscal (ITBIS en compras)", f"RD$ {itbis_compras:,.2f}")
            col3.metric("🔴 ITBIS Neto a Pagar", f"RD$ {max(itbis_neto, 0):,.2f}")

            st.divider()
            st.markdown("### 📋 Desglose Detallado para el Formulario IT-1")

            tabla_it1 = [
                {"Línea": "Casilla 1", "Descripción": "Ventas Gravadas 18% (Base Imponible)", "Monto (RD$)": f"{base_gravada_ventas:,.2f}"},
                {"Línea": "Casilla 2", "Descripción": "ITBIS Cobrado en Ventas (Débito Fiscal)", "Monto (RD$)": f"{itbis_ventas:,.2f}"},
                {"Línea": "Casilla 3", "Descripción": "Ventas Exentas o con Tasa 0%", "Monto (RD$)": f"{base_exenta_ventas:,.2f}"},
                {"Línea": "Casilla 4", "Descripción": "Compras Gravadas (Base)", "Monto (RD$)": f"{base_gravada_compras:,.2f}"},
                {"Línea": "Casilla 5", "Descripción": "ITBIS Pagado en Compras (Crédito Fiscal)", "Monto (RD$)": f"{itbis_compras:,.2f}"},
                {"Línea": "Casilla 6", "Descripción": "ITBIS Neto a Pagar (Casilla 2 - Casilla 5)", "Monto (RD$)": f"{max(itbis_neto, 0):,.2f}"},
                {"Línea": "Casilla 7", "Descripción": "Crédito a Favor (si Casilla 5 > Casilla 2)", "Monto (RD$)": f"{max(-itbis_neto, 0):,.2f}"},
            ]
            st.dataframe(pd.DataFrame(tabla_it1), use_container_width=True, hide_index=True)

            if itbis_neto > 0:
                st.warning(f"⚠️ Debes pagar **RD$ {itbis_neto:,.2f}** de ITBIS a la DGII antes del día 20 de {(desde_dgii.replace(day=1) + pd.DateOffset(months=1)).strftime('%B %Y')}.")
            elif itbis_neto < 0:
                st.success(f"✅ Tienes un **crédito a favor de RD$ {abs(itbis_neto):,.2f}** que puedes acreditar al próximo período.")
            else:
                st.info("El ITBIS está en cero para este período.")

            # Botón de descarga TXT IT-1 resumido
            it1_txt = (
                f"DECLARACION IT-1 | PERIODO: {periodo_str}\n"
                f"RNC: {obtener_tenant_actual()[:11]}\n"
                f"---\n"
                f"DEBITO FISCAL (ITBIS VENTAS): {itbis_ventas:.2f}\n"
                f"CREDITO FISCAL (ITBIS COMPRAS): {itbis_compras:.2f}\n"
                f"ITBIS NETO A PAGAR: {max(itbis_neto, 0):.2f}\n"
                f"CREDITO A FAVOR: {max(-itbis_neto, 0):.2f}\n"
                f"BASE GRAVADA VENTAS: {base_gravada_ventas:.2f}\n"
                f"BASE EXENTA VENTAS: {base_exenta_ventas:.2f}\n"
            )
            st.download_button(
                "📥 Descargar Resumen IT-1 (TXT)",
                data=it1_txt,
                file_name=f"IT1_Resumen_{periodo_str}.txt",
                mime="text/plain",
                key="btn_download_it1"
            )

    # ── IR-2: Declaración Anual de ISR ──────────────────────────────────
    with tIR2:
        st.subheader("📑 IR-2 — Declaración Jurada de ISR (Personas Jurídicas)")
        st.caption("Resumen anual de ingresos, costos, gastos y utilidad neta para el cálculo del ISR empresarial.")

        ano_ir2 = st.number_input("Año fiscal", min_value=2020, max_value=2035, value=date.today().year, step=1, key="ir2_ano")
        desde_ir2 = date(int(ano_ir2), 1, 1)
        hasta_ir2 = date(int(ano_ir2), 12, 31)

        df_ventas_ir2 = _filtrar_periodo_df(_df_actual("ventas"), desde_ir2, hasta_ir2)
        df_compras_ir2 = _filtrar_periodo_df(_df_actual("compras"), desde_ir2, hasta_ir2)
        df_gastos_ir2 = _filtrar_periodo_df(_df_actual("gastos"), desde_ir2, hasta_ir2)
        df_nomina_ir2 = _filtrar_periodo_df(_df_actual("adelantos_empleados"), desde_ir2, hasta_ir2)

        ingresos_brutos = float(df_ventas_ir2["total"].sum()) if not df_ventas_ir2.empty and "total" in df_ventas_ir2.columns else 0.0
        itbis_ventas_ir2 = float(df_ventas_ir2["itbis_total"].sum()) if not df_ventas_ir2.empty and "itbis_total" in df_ventas_ir2.columns else 0.0
        ingresos_netos = ingresos_brutos - itbis_ventas_ir2

        costo_compras = float(df_compras_ir2["total"].sum()) if not df_compras_ir2.empty and "total" in df_compras_ir2.columns else 0.0
        gastos_operativos = float(df_gastos_ir2["monto"].sum()) if not df_gastos_ir2.empty and "monto" in df_gastos_ir2.columns else 0.0

        nomina_pagada = 0.0
        if not df_nomina_ir2.empty and "monto" in df_nomina_ir2.columns:
            if "tipo_pago" in df_nomina_ir2.columns:
                df_nom_sal = df_nomina_ir2[df_nomina_ir2["tipo_pago"].fillna("").isin(["salario", "quincena"])]
                nomina_pagada = float(df_nom_sal["monto"].sum())
            else:
                nomina_pagada = float(df_nomina_ir2["monto"].sum())

        total_gastos_deducibles = costo_compras + gastos_operativos + nomina_pagada
        utilidad_bruta = ingresos_netos - costo_compras
        utilidad_neta = ingresos_netos - total_gastos_deducibles

        # ISR empresarial: 27% sobre utilidad neta positiva (tasa RD 2024)
        TASA_ISR_EMPRESA = 0.27
        isr_estimado = round(max(utilidad_neta * TASA_ISR_EMPRESA, 0), 2)

        st.markdown(f"### 📊 Resumen IR-2 — Año {ano_ir2}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ingresos Brutos", f"RD$ {ingresos_brutos:,.2f}")
        m2.metric("Ingresos Netos (sin ITBIS)", f"RD$ {ingresos_netos:,.2f}")
        m3.metric("Utilidad Neta", f"RD$ {utilidad_neta:,.2f}")
        m4.metric(f"ISR Estimado ({int(TASA_ISR_EMPRESA*100)}%)", f"RD$ {isr_estimado:,.2f}")

        st.divider()
        st.markdown("### 📋 Estado de Resultados para IR-2")
        tabla_ir2 = [
            {"Concepto": "(+) Ingresos Brutos por Ventas", "Monto (RD$)": f"{ingresos_brutos:,.2f}"},
            {"Concepto": "(-) ITBIS Cobrado (No es ingreso)", "Monto (RD$)": f"-{itbis_ventas_ir2:,.2f}"},
            {"Concepto": "(=) Ingresos Netos", "Monto (RD$)": f"{ingresos_netos:,.2f}"},
            {"Concepto": "(-) Costo de Compras / Inventario", "Monto (RD$)": f"-{costo_compras:,.2f}"},
            {"Concepto": "(=) Utilidad Bruta", "Monto (RD$)": f"{utilidad_bruta:,.2f}"},
            {"Concepto": "(-) Gastos Operativos", "Monto (RD$)": f"-{gastos_operativos:,.2f}"},
            {"Concepto": "(-) Nómina Pagada (Sueldos)", "Monto (RD$)": f"-{nomina_pagada:,.2f}"},
            {"Concepto": "(=) Utilidad Neta Imponible", "Monto (RD$)": f"{utilidad_neta:,.2f}"},
            {"Concepto": f"(*) ISR Empresarial ({int(TASA_ISR_EMPRESA*100)}% si utilidad > 0)", "Monto (RD$)": f"{isr_estimado:,.2f}"},
        ]
        st.dataframe(pd.DataFrame(tabla_ir2), use_container_width=True, hide_index=True)

        if isr_estimado > 0:
            st.warning(f"⚠️ ISR estimado a pagar: **RD$ {isr_estimado:,.2f}**. Debe declararse antes del 30 de abril del año {ano_ir2 + 1}.")
        elif utilidad_neta < 0:
            st.info(f"ℹ️ El negocio reporta pérdidas de RD$ {abs(utilidad_neta):,.2f} en {ano_ir2}. No hay ISR a pagar. Las pérdidas pueden arrastrarse al próximo año fiscal.")
        else:
            st.success("✅ Utilidad neta en cero. No hay ISR a pagar este período.")

        ir2_txt = (
            f"DECLARACION IR-2 | AÑO: {ano_ir2}\n"
            f"RNC: {obtener_tenant_actual()[:11]}\n"
            f"---\n"
            f"INGRESOS BRUTOS: {ingresos_brutos:.2f}\n"
            f"ITBIS COBRADO: {itbis_ventas_ir2:.2f}\n"
            f"INGRESOS NETOS: {ingresos_netos:.2f}\n"
            f"COSTO COMPRAS: {costo_compras:.2f}\n"
            f"GASTOS OPERATIVOS: {gastos_operativos:.2f}\n"
            f"NOMINA PAGADA: {nomina_pagada:.2f}\n"
            f"UTILIDAD NETA: {utilidad_neta:.2f}\n"
            f"TASA ISR: {int(TASA_ISR_EMPRESA*100)}%\n"
            f"ISR ESTIMADO: {isr_estimado:.2f}\n"
        )
        st.download_button(
            "📥 Descargar Resumen IR-2 (TXT)",
            data=ir2_txt,
            file_name=f"IR2_Resumen_{ano_ir2}.txt",
            mime="text/plain",
            key="btn_download_ir2"
        )

# =========================================================
# REPORTES
# =========================================================


def render_informes():
    import plotly.graph_objects as go
    import plotly.express as px
    from datetime import date

    # 1. PREMIUM TITLING & CUSTOM BRAND BANNER
    st.markdown("""
<div class="informes-title-container">
    <h1>📊 Centro de Informes Financieros y Análisis PRO</h1>
    <p>Análisis de rendimiento, rentabilidad y auditoría cruzada multimódulo en tiempo real.</p>
</div>
""", unsafe_allow_html=True)

    # Custom styling inject
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;900&display=swap');
    
    .kpi-card {
        background: rgba(17, 25, 40, 0.75);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 4px 16px 0 rgba(0, 0, 0, 0.15);
        font-family: 'Outfit', sans-serif;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(0, 145, 255, 0.5);
    }
    .kpi-title {
        font-size: 0.82rem;
        color: #8a99ad;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 6px;
    }
    .kpi-trend {
        font-size: 0.8rem;
        font-weight: 600;
    }
    .yo-contra-yo-better {
        background-color: rgba(46, 248, 160, 0.15);
        color: #2ef8a0;
        padding: 4px 8px;
        border-radius: 8px;
        font-weight: 600;
    }
    .yo-contra-yo-worse {
        background-color: rgba(255, 77, 77, 0.15);
        color: #ff4d4d;
        padding: 4px 8px;
        border-radius: 8px;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

    # 2. FILTER CONTROLLER HEADER
    c_f1, c_f2, c_f3, c_f4 = st.columns([2, 2, 1.2, 1.8])
    with c_f1:
        desde = st.date_input("Fecha desde", value=date.today(), key="inf_desde")
    with c_f2:
        hasta = st.date_input("Fecha hasta", value=date.today(), key="inf_hasta")
    with c_f3:
        comparar = st.checkbox("Comparar con anterior", value=True, key="inf_comparar")
    with c_f4:
        agrupacion = st.selectbox("Agrupación temporal", ["Diario", "Semanal", "Mensual", "Anual"], index=0, key="inf_agrupacion")

    # Safe conversion to date
    desde = pd.to_datetime(desde).date()
    hasta = pd.to_datetime(hasta).date()

    # Previous comparative period calculations
    delta_days = (hasta - desde).days + 1
    desde_ant = desde - pd.Timedelta(days=delta_days)
    hasta_ant = desde - pd.Timedelta(days=1)
    desde_ant = desde_ant.date() if hasattr(desde_ant, "date") else desde_ant
    hasta_ant = hasta_ant.date() if hasattr(hasta_ant, "date") else hasta_ant

    # 3. HIGH FIDELITY METRICS COMPUTATION ENGINE
    def obtener_metrics_dict(desde_p, hasta_p):
        res = {
            "ventas_netas": 0.0,
            "costo_ventas": 0.0,
            "utilidad_bruta": 0.0,
            "margen_bruto": 0.0,
            "gastos_operativos": 0.0,
            "utilidad_neta": 0.0,
            "margen_neto": 0.0,
            "compras": 0.0,
            "credito_pendiente": 0.0,
            "abonos_recibidos": 0.0,
            "inventario_costo": 0.0,
            "inventario_venta": 0.0,
            "ganancia_potencial": 0.0,
            "efectivo_caja": 0.0,
            "banco_transferencia": 0.0,
            "flujo_neto": 0.0
        }
        
        # 1. Ventas netas (exclude cancelled)
        v_df = obtener_ventas_periodo_actualizadas(desde_p, hasta_p)
        if not v_df.empty:
            for c in ["anulado", "cancelado"]:
                if c in v_df.columns:
                    try:
                        v_df = v_df[~v_df[c].fillna(False).astype(bool)].copy()
                    except Exception:
                        pass
            if "estado" in v_df.columns:
                try:
                    v_df = v_df[~v_df["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()
                except Exception:
                    pass
                    
        total_col = "total_contable" if "total_contable" in v_df.columns else "total"
        v_netas = float(_sum_any(v_df, ["venta_bruta", total_col, "total", "subtotal"]))
        if v_netas <= 0 and not v_df.empty:
            v_netas = float(_sum_any(v_df, [total_col, "total", "subtotal"]))
            
        # Deducir Notas de Crédito emitidas en el periodo
        nc_monto_total = 0.0
        nc_costo_total = 0.0
        try:
            nc_rows = leer_tabla("notas_credito")
            if nc_rows:
                df_nc = pd.DataFrame(nc_rows)
                if not df_nc.empty and "fecha" in df_nc.columns:
                    df_nc["fecha"] = pd.to_datetime(df_nc["fecha"], errors="coerce")
                    df_nc = df_nc[(df_nc["fecha"].dt.date >= desde_p) & (df_nc["fecha"].dt.date <= hasta_p)]
                    if not df_nc.empty:
                        nc_monto_total = float(df_nc["monto_total"].sum())
                        for _, nc_row in df_nc.iterrows():
                            detalles = nc_row.get("detalles") or []
                            if isinstance(detalles, list):
                                for det in detalles:
                                    if isinstance(det, dict):
                                        nc_costo_total += float(det.get("costo_unitario") or 0.0) * float(det.get("cantidad") or 0.0)
        except Exception:
            pass
            
        v_netas = max(0.0, v_netas - nc_monto_total)
        res["ventas_netas"] = v_netas
        
        # 2. Costo de ventas (detail sales FIFO/weighted)
        c_ventas = float(calcular_costo_ventas_real(desde_p, hasta_p, v_df))
        c_ventas = max(0.0, c_ventas - nc_costo_total)
        res["costo_ventas"] = c_ventas
        
        # 3. Utilidad bruta
        u_bruta = v_netas - c_ventas
        res["utilidad_bruta"] = u_bruta
        
        # 4. Margen bruto
        res["margen_bruto"] = (u_bruta / v_netas * 100) if v_netas > 0 else 0.0
        
        # 5. Gastos operativos (Payroll + general expenses + losses)
        g_df = _filtrar_periodo_df(_df_actual("gastos"), desde_p, hasta_p)
        ade_df = _filtrar_periodo_df(_df_actual("adelantos_empleados"), desde_p, hasta_p)
        pag_emp_df = _filtrar_periodo_df(_df_actual("pagos_empleados"), desde_p, hasta_p)
        
        personal = float(_sum_any(pag_emp_df, ["monto", "total", "valor"])) + float(_sum_any(ade_df, ["monto", "total", "valor"]))
        cargas_sociales = 0.0
        gastos_fijos = 0.0
        gastos_variables = 0.0
        comisiones_bancarias = 0.0
        
        if not g_df.empty:
            for _, r in g_df.iterrows():
                monto = _num(r.get("monto") or r.get("total") or r.get("valor"))
                cat = normalizar_texto(r.get("categoria_estado_resultado") or r.get("categoria") or r.get("tipo") or r.get("concepto") or "")
                concepto = normalizar_texto(r.get("concepto") or r.get("descripcion") or "")
                texto = f"{cat} {concepto}"
                if any(k in texto for k in ["tss", "infotep", "carga social", "seguridad social"]):
                    cargas_sociales += monto
                elif any(k in texto for k in ["sueldo", "empleado", "nomina", "nómina", "personal", "comision empleado", "comisión empleado"]):
                    personal += monto
                elif any(k in texto for k in ["alquiler", "luz", "energia", "energía", "agua", "internet", "telefono", "teléfono", "basura", "fijo"]):
                    gastos_fijos += monto
                elif any(k in texto for k in ["banco", "interes", "interés", "comision bancaria", "comisión bancaria", "financiero"]):
                    comisiones_bancarias += monto
                else:
                    gastos_variables += monto
                    
        per_df = _filtrar_periodo_df(_df_actual("perdidas"), desde_p, hasta_p)
        aj_df = _filtrar_periodo_df(_df_actual("ajustes_inventario"), desde_p, hasta_p)
        ajustes_negativos = 0.0
        if not aj_df.empty:
            for _, r in aj_df.iterrows():
                monto = _num(r.get("valor") or r.get("monto") or r.get("total") or r.get("costo_total"))
                tipo = normalizar_texto(r.get("tipo") or r.get("tipo_ajuste") or r.get("movimiento") or "")
                if tipo in ["salida", "negativo", "disminucion", "disminución", "ajuste negativo"]:
                    ajustes_negativos += monto
                    
        perdidas_tot = float(_sum_any(per_df, ["valor", "monto", "total", "costo_total"])) + ajustes_negativos
        
        gastos_ope = personal + cargas_sociales + gastos_fijos + gastos_variables + perdidas_tot + comisiones_bancarias
        res["gastos_operativos"] = gastos_ope
        
        # 6. Utilidad neta
        u_neta = u_bruta - gastos_ope
        res["utilidad_neta"] = u_neta
        
        # 7. Margen neto
        res["margen_neto"] = (u_neta / v_netas * 100) if v_netas > 0 else 0.0
        
        # 8. Compras
        comp_df = _filtrar_periodo_df(_df_actual("compras"), desde_p, hasta_p)
        res["compras"] = float(_sum_any(comp_df, ["monto", "total", "valor", "costo_total"]))
        
        # 9. Crédito pendiente
        cxc = _df_actual("cuentas_por_cobrar")
        cxc_pend = cxc
        if not cxc.empty and "estado" in cxc.columns:
            cxc_pend = cxc[cxc["estado"].astype(str).str.lower() != "saldada"]
        res["credito_pendiente"] = float(_sum_any(cxc_pend, ["saldo_pendiente", "monto_original"]))
        
        # 10. Abonos recibidos
        ab_df = _filtrar_periodo_df(_df_actual("abonos_credito"), desde_p, hasta_p)
        res["abonos_recibidos"] = float(_sum_any(ab_df, ["monto", "total", "valor"]))
        
        # 11, 12, 13. Inventario
        inv_vals = calcular_valores_inventario_pro()
        res["inventario_costo"] = float(inv_vals.get("inventario_costo", 0) or 0)
        res["inventario_venta"] = float(inv_vals.get("inventario_venta", 0) or 0)
        res["ganancia_potencial"] = res["inventario_venta"] - res["inventario_costo"]
        
        # 14, 15, 16. Flujo de efectivo
        hist_df = construir_historial_dinero_real()
        if not hist_df.empty and "fecha" in hist_df.columns:
            try:
                hist_df["_fecha_dt"] = pd.to_datetime(hist_df["fecha"], errors="coerce")
                hist_df = hist_df[(hist_df["_fecha_dt"].dt.date >= desde_p) & (hist_df["_fecha_dt"].dt.date <= hasta_p)].copy()
            except Exception:
                pass
                
        if not hist_df.empty:
            efectivo_movs = hist_df[hist_df["cuenta"].astype(str).apply(normalizar_texto) == "efectivo negocio"]
            res["efectivo_caja"] = float(efectivo_movs["entrada"].sum()) - float(efectivo_movs["salida"].sum())
            
            banco_movs = hist_df[hist_df["cuenta"].astype(str).apply(normalizar_texto) == "banco"]
            res["banco_transferencia"] = float(banco_movs["entrada"].sum()) - float(banco_movs["salida"].sum())
            
            flujo_movs = hist_df[hist_df["metodo_pago"].astype(str).apply(normalizar_texto) != "interno"]
            res["flujo_neto"] = float(flujo_movs["entrada"].sum()) - float(flujo_movs["salida"].sum())
            
        return res

    # Perform calculations for current and prior period
    m_act = obtener_metrics_dict(desde, hasta)
    m_ant = obtener_metrics_dict(desde_ant, hasta_ant) if comparar else {k: 0.0 for k in m_act.keys()}

    # Helper function to print cards
    def draw_kpi_card(title, value, prev_value, is_percentage=False, invert_trend=False):
        if is_percentage:
            val_str = f"{value:.2f}%"
            diff = value - prev_value
            diff_str = f"{diff:+.2f}%"
        else:
            val_str = f"RD$ {value:,.2f}"
            if prev_value != 0:
                pct_diff = ((value - prev_value) / abs(prev_value)) * 100
                diff_str = f"{pct_diff:+.1f}%"
            else:
                pct_diff = 100.0 if (value - prev_value) > 0 else (0.0 if (value - prev_value) == 0 else -100.0)
                diff_str = f"{pct_diff:+.1f}%"

        diff_val = value - prev_value
        if diff_val > 0:
            trend_arrow = "▲"
            is_good = not invert_trend
        elif diff_val < 0:
            trend_arrow = "▼"
            is_good = invert_trend
        else:
            trend_arrow = "■"
            is_good = True

        color = "#2ef8a0" if is_good else "#ff4d4d"
        if diff_val == 0:
            color = "#a0a0a0"

        card_html = f"""
<div class="kpi-card">
    <div class="kpi-title">{title}</div>
    <div class="kpi-value">{val_str}</div>
    <div class="kpi-trend" style="color: {color};">
        <span>{trend_arrow} {diff_str}</span> vs anterior
    </div>
</div>
"""
        return card_html

    # 4. TAB CONTROLLER LAYOUT (11 TABS)
    tabs = st.tabs([
        "📊 Resumen del período",
        "⚖️ Comparación de períodos",
        "🎯 Yo contra Yo",
        "📈 Series para análisis",
        "📅 Detalle por día",
        "🏆 Top productos",
        "💵 Flujo de efectivo",
        "📦 Inventario",
        "💳 Créditos",
        "🤝 Distribución de utilidad",
        "🛡️ Análisis avanzado"
    ])

    # ----------------------------------------------------
    # TAB 1: RESUMEN DEL PERÍODO
    # ----------------------------------------------------
    with tabs[0]:
        st.subheader("Cuadrícula Financiera Ejecutiva (16 KPIs)")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(draw_kpi_card("Ventas Netas", m_act["ventas_netas"], m_ant["ventas_netas"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Gastos Operativos", m_act["gastos_operativos"], m_ant["gastos_operativos"], invert_trend=True), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Crédito Pendiente", m_act["credito_pendiente"], m_ant["credito_pendiente"], invert_trend=True), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Ganancia Potencial Stock", m_act["ganancia_potencial"], m_ant["ganancia_potencial"]), unsafe_allow_html=True)
        with c2:
            st.markdown(draw_kpi_card("Costo de Ventas", m_act["costo_ventas"], m_ant["costo_ventas"], invert_trend=True), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Utilidad Neta", m_act["utilidad_neta"], m_ant["utilidad_neta"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Abonos Recibidos", m_act["abonos_recibidos"], m_ant["abonos_recibidos"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Efectivo en Caja", m_act["efectivo_caja"], m_ant["efectivo_caja"]), unsafe_allow_html=True)
        with c3:
            st.markdown(draw_kpi_card("Utilidad Bruta", m_act["utilidad_bruta"], m_ant["utilidad_bruta"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Margen Neto", m_act["margen_neto"], m_ant["margen_neto"], is_percentage=True), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Inventario a Costo", m_act["inventario_costo"], m_ant["inventario_costo"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Banco / Transferencia", m_act["banco_transferencia"], m_ant["banco_transferencia"]), unsafe_allow_html=True)
        with c4:
            st.markdown(draw_kpi_card("Margen Bruto", m_act["margen_bruto"], m_ant["margen_bruto"], is_percentage=True), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Compras del Período", m_act["compras"], m_ant["compras"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Inventario a Venta", m_act["inventario_venta"], m_ant["inventario_venta"]), unsafe_allow_html=True)
            st.markdown(draw_kpi_card("Flujo Neto Líquido", m_act["flujo_neto"], m_ant["flujo_neto"]), unsafe_allow_html=True)

        st.markdown("---")
        cg1, cg2 = st.columns([1.2, 1])
        with cg1:
            st.subheader("🍰 Distribución de Egresos y Utilidad")
            labels = ['Costo de Ventas', 'Gastos Operativos', 'Utilidad Neta']
            values = [m_act["costo_ventas"], m_act["gastos_operativos"], max(m_act["utilidad_neta"], 0)]
            if sum(values) <= 0:
                st.info("Sin registros financieros en este período para graficar.")
            else:
                fig_donut = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.45, marker_colors=['#ff4d4d', '#ffc107', '#2ef8a0'])])
                fig_donut.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    margin=dict(t=0, b=0, l=10, r=10),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5)
                )
                st.plotly_chart(fig_donut, use_container_width=True)
        
        with cg2:
            st.subheader("💡 Panel de Inteligencia Contable")
            # Build AI executive message insights
            insights = []
            if m_act["ventas_netas"] > 0:
                if m_act["margen_neto"] >= 20:
                    insights.append("🟢 **Excelente rentabilidad:** El margen neta es óptimo ({:.1f}%), operando con una excelente relación costo-ingreso.".format(m_act["margen_neto"]))
                elif m_act["margen_neto"] >= 5:
                    insights.append("🟡 **Rentabilidad moderada:** Margen neto de {:.1f}%. Se sugiere optimizar los costos de inventario o nómina.".format(m_act["margen_neto"]))
                else:
                    insights.append("🔴 **Bajo margen neto:** El margen neto ({:.1f}%) está presionado. Audite gastos variables y pérdidas de stock inmediatamente.".format(m_act["margen_neto"]))

                ratio_cxc = (m_act["credito_pendiente"] / m_act["ventas_netas"]) * 100
                if ratio_cxc > 30:
                    insights.append("🔴 **Riesgo en Liquidez (CxC alto):** Las deudas activas equivalen al {:.1f}% de las ventas. Aumente la gestión de abonos.".format(ratio_cxc))
                else:
                    insights.append("🟢 **Bajo apalancamiento a clientes:** Cuentas pendientes representan solo {:.1f}% de las ventas.".format(ratio_cxc))
            else:
                insights.append("⚪ No hay registros de ventas en este rango de fechas para evaluar.")
            
            if m_act["compras"] > m_act["ventas_netas"] * 0.5:
                insights.append("🟡 **Alta reinversión en inventario:** Las compras representan el {:.1f}% de las ventas netas. Evite acumular stock ocioso.".format((m_act["compras"]/m_act["ventas_netas"]*100) if m_act["ventas_netas"] > 0 else 0))

            for ins in insights:
                st.markdown(ins)
            
            st.subheader("💵 Arqueo Rápido de Caja")
            hist_df_caja = construir_historial_dinero_real()
            if not hist_df_caja.empty and "fecha" in hist_df_caja.columns:
                try:
                    hist_df_caja["_fecha_dt"] = pd.to_datetime(hist_df_caja["fecha"], errors="coerce")
                    hist_df_caja = hist_df_caja[(hist_df_caja["_fecha_dt"].dt.date >= desde) & (hist_df_caja["_fecha_dt"].dt.date <= hasta)].copy()
                except Exception:
                    pass
            
            ventas_efectivo = float(hist_df_caja[(hist_df_caja["origen"] == "Venta") & (hist_df_caja["metodo_pago"].astype(str).str.lower() == "efectivo")]["entrada"].sum()) if not hist_df_caja.empty else 0.0
            compras_efectivo = float(hist_df_caja[(hist_df_caja["origen"] == "Compra") & (hist_df_caja["metodo_pago"].astype(str).str.lower() == "efectivo")]["salida"].sum()) if not hist_df_caja.empty else 0.0
            gastos_efectivo = float(hist_df_caja[(hist_df_caja["origen"].astype(str).str.contains("Gasto")) & (hist_df_caja["metodo_pago"].astype(str).str.lower() == "efectivo")]["salida"].sum()) if not hist_df_caja.empty else 0.0

            st.write(f"🔹 **Ventas cobradas en efectivo:** RD$ {ventas_efectivo:,.2f}")
            st.write(f"🔹 **Compras liquidadas en efectivo:** RD$ {compras_efectivo:,.2f}")
            st.write(f"🔹 **Gastos liquidados en efectivo:** RD$ {gastos_efectivo:,.2f}")

    # ----------------------------------------------------
    # TAB 2: COMPARACIÓN DE PERÍODOS
    # ----------------------------------------------------
    with tabs[1]:
        st.subheader("Balance Comparativo de Métricas")
        comp_rows = []
        names = {
            "ventas_netas": "Ventas Netas",
            "costo_ventas": "Costo de Ventas",
            "utilidad_bruta": "Utilidad Bruta",
            "margen_bruto": "Margen Bruto (%)",
            "gastos_operativos": "Gastos Operativos",
            "utilidad_neta": "Utilidad Neta",
            "margen_neto": "Margen Neto (%)",
            "compras": "Compras del Período",
            "credito_pendiente": "Crédito Pendiente (CxC)",
            "abonos_recibidos": "Abonos Recibidos",
            "inventario_costo": "Inventario a Costo",
            "inventario_venta": "Inventario a Venta",
            "ganancia_potencial": "Ganancia Potencial Stock",
            "efectivo_caja": "Efectivo en Caja",
            "banco_transferencia": "Banco / Transferencias",
            "flujo_neto": "Flujo Neto Líquido"
        }
        
        for k in m_act.keys():
            val_act = m_act[k]
            val_ant = m_ant[k]
            diff = val_act - val_ant
            if val_ant != 0:
                pct = (diff / abs(val_ant)) * 100
            else:
                pct = 100.0 if diff > 0 else (0.0 if diff == 0 else -100.0)
            
            comp_rows.append({
                "Métrica": names.get(k, k),
                "Período Actual": val_act,
                "Período Anterior": val_ant,
                "Diferencia": diff,
                "Diferencia (%)": pct
            })
            
        comp_df = pd.DataFrame(comp_rows)
        disp_df = comp_df.copy()
        
        disp_df["Período Actual"] = disp_df.apply(lambda r: f"{r['Período Actual']:.2f}%" if "%" in r["Métrica"] else f"RD$ {r['Período Actual']:,.2f}", axis=1)
        disp_df["Período Anterior"] = disp_df.apply(lambda r: f"{r['Período Anterior']:.2f}%" if "%" in r["Métrica"] else f"RD$ {r['Período Anterior']:,.2f}", axis=1)
        disp_df["Diferencia"] = disp_df.apply(lambda r: f"{r['Diferencia']:+.2f}%" if "%" in r["Métrica"] else f"RD$ {r['Diferencia']:+,.2f}", axis=1)
        disp_df["Diferencia (%)"] = disp_df["Diferencia (%)"].apply(lambda v: f"{v:+.2f}%")
        
        st.dataframe(disp_df, use_container_width=True, hide_index=True)
        
        # Multiformat download
        csv_data = comp_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Informe en CSV",
            data=csv_data,
            file_name=f"informe_{desde}_al_{hasta}.csv",
            mime="text/csv"
        )

    # ----------------------------------------------------
    # TAB 3: YO CONTRA YO (EVALUACIÓN)
    # ----------------------------------------------------
    with tabs[2]:
        st.subheader("Cuadro de Autoevaluación Operativa (Yo contra Yo)")
        st.caption("Semáforos inteligentes que evalúan el crecimiento operativo comparando el rendimiento real actual vs histórico.")
        
        html_rows = ""
        for row in comp_rows:
            name = row["Métrica"]
            act = row["Período Actual"]
            ant = row["Período Anterior"]
            diff = row["Diferencia"]
            pct = row["Diferencia (%)"]
            
            if "%" in name:
                act_str = f"{act:.2f}%"
                ant_str = f"{ant:.2f}%"
                diff_str = f"{diff:+.2f}%"
            else:
                act_str = f"RD$ {act:,.2f}"
                ant_str = f"RD$ {ant:,.2f}"
                diff_str = f"RD$ {diff:+,.2f}"
                
            pct_str = f"{pct:+.1f}%"
            
            is_cost_or_expense = any(k in name.lower() for k in ["costo", "gasto", "compras", "pendiente"])
            if diff > 0:
                status = "🔴 Empeoró" if is_cost_or_expense else "🟢 Mejoró"
                badge_class = "yo-contra-yo-worse" if is_cost_or_expense else "yo-contra-yo-better"
                color_eval = "#ff4d4d" if is_cost_or_expense else "#2ef8a0"
            elif diff < 0:
                status = "🟢 Mejoró" if is_cost_or_expense else "🔴 Empeoró"
                badge_class = "yo-contra-yo-better" if is_cost_or_expense else "yo-contra-yo-worse"
                color_eval = "#2ef8a0" if is_cost_or_expense else "#ff4d4d"
            else:
                status = "🟡 Sin cambios"
                badge_class = ""
                color_eval = "#a0a0a0"
                
            html_rows += f"""
<tr>
    <td style='padding:12px; border-bottom:1px solid rgba(255,255,255,0.08); font-weight:600;'>{name}</td>
    <td style='padding:12px; border-bottom:1px solid rgba(255,255,255,0.08);'>{act_str}</td>
    <td style='padding:12px; border-bottom:1px solid rgba(255,255,255,0.08); color:#a0a0a0;'>{ant_str}</td>
    <td style='padding:12px; border-bottom:1px solid rgba(255,255,255,0.08); font-weight:600; color:{color_eval};'>{diff_str} ({pct_str})</td>
    <td style='padding:12px; border-bottom:1px solid rgba(255,255,255,0.08);'><span class='{badge_class}'>{status}</span></td>
</tr>
"""
            
        st.markdown(f"""
<table style='width:100%; border-collapse:collapse; background:rgba(17,25,40,0.4); border-radius:12px; overflow:hidden;'>
    <thead>
        <tr style='background:rgba(0,145,255,0.15); text-align:left; color:#0091ff;'>
            <th style='padding:12px;'>Métrica</th>
            <th style='padding:12px;'>Período Actual</th>
            <th style='padding:12px;'>Período Anterior</th>
            <th style='padding:12px;'>Variación</th>
            <th style='padding:12px;'>Evaluación</th>
        </tr>
    </thead>
    <tbody>
        {html_rows}
    </tbody>
</table>
""", unsafe_allow_html=True)

    # ----------------------------------------------------
    # TAB 4: SERIES PARA ANÁLISIS (CHARTS OVERLAY)
    # ----------------------------------------------------
    with tabs[3]:
        st.subheader("📈 Series Históricas Paralelas")
        st.caption("Superposición de curvas que muestra la evolución exacta del período actual contra el período anterior.")

        def obtener_serie_agrupada(desde_s, hasta_s, agrupacion_s):
            v_df = _filtrar_periodo_df(_df_actual("ventas"), desde_s, hasta_s)
            if not v_df.empty:
                for c in ["anulado", "cancelado"]:
                    if c in v_df.columns:
                        v_df = v_df[~v_df[c].fillna(False).astype(bool)].copy()
                if "estado" in v_df.columns:
                    v_df = v_df[~v_df["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()
            
            c_df = _filtrar_periodo_df(_df_actual("compras"), desde_s, hasta_s)
            g_df = _filtrar_periodo_df(_df_actual("gastos"), desde_s, hasta_s)
            
            dates = pd.date_range(start=desde_s, end=hasta_s, freq='D')
            series_df = pd.DataFrame({"fecha": dates})
            
            if not v_df.empty and "fecha" in v_df.columns:
                v_df["fecha_only"] = pd.to_datetime(v_df["fecha"]).dt.date
                v_daily = v_df.groupby("fecha_only")["total"].sum().reset_index()
                v_daily.columns = ["fecha", "ventas"]
                v_daily["fecha"] = pd.to_datetime(v_daily["fecha"])
                series_df = pd.merge(series_df, v_daily, on="fecha", how="left")
            else:
                series_df["ventas"] = 0.0
                
            if not c_df.empty and "fecha" in c_df.columns:
                c_df["fecha_only"] = pd.to_datetime(c_df["fecha"]).dt.date
                c_daily = c_df.groupby("fecha_only")["monto"].sum().reset_index()
                c_daily.columns = ["fecha", "compras"]
                c_daily["fecha"] = pd.to_datetime(c_daily["fecha"])
                series_df = pd.merge(series_df, c_daily, on="fecha", how="left")
            else:
                series_df["compras"] = 0.0
                
            if not g_df.empty and "fecha" in g_df.columns:
                g_df["fecha_only"] = pd.to_datetime(g_df["fecha"]).dt.date
                g_daily = g_df.groupby("fecha_only")["monto"].sum().reset_index()
                g_daily.columns = ["fecha", "gastos"]
                g_daily["fecha"] = pd.to_datetime(g_daily["fecha"])
                series_df = pd.merge(series_df, g_daily, on="fecha", how="left")
            else:
                series_df["gastos"] = 0.0
                
            series_df = series_df.fillna(0.0)
            
            if agrupacion_s == "Semanal":
                series_df["periodo"] = series_df["fecha"].dt.to_period("W").astype(str)
                series_df = series_df.groupby("periodo")[["ventas", "compras", "gastos"]].sum().reset_index()
            elif agrupacion_s == "Mensual":
                series_df["periodo"] = series_df["fecha"].dt.to_period("M").astype(str)
                series_df = series_df.groupby("periodo")[["ventas", "compras", "gastos"]].sum().reset_index()
            elif agrupacion_s == "Anual":
                series_df["periodo"] = series_df["fecha"].dt.to_period("Y").astype(str)
                series_df = series_df.groupby("periodo")[["ventas", "compras", "gastos"]].sum().reset_index()
            else:
                series_df["periodo"] = series_df["fecha"].dt.strftime("%Y-%m-%d")
                series_df = series_df[["periodo", "ventas", "compras", "gastos"]]
                
            return series_df

        serie_act = obtener_serie_agrupada(desde, hasta, agrupacion)
        serie_ant = obtener_serie_agrupada(desde_ant, hasta_ant, agrupacion)

        if not serie_act.empty:
            serie_act["Paso"] = range(1, len(serie_act) + 1)
            serie_ant["Paso"] = range(1, len(serie_ant) + 1)
            
            merged_series = pd.merge(
                serie_act[["Paso", "periodo", "ventas", "compras", "gastos"]],
                serie_ant[["Paso", "periodo", "ventas", "compras", "gastos"]],
                on="Paso",
                suffixes=("_actual", "_anterior"),
                how="outer"
            ).fillna(0.0)
            
            selected_metric = st.selectbox("Seleccione métrica para graficar", ["Ventas", "Compras", "Gastos"], key="inf_metric_chart")
            col_act = f"{selected_metric.lower()}_actual"
            col_ant = f"{selected_metric.lower()}_anterior"
            
            fig_series = go.Figure()
            fig_series.add_trace(go.Scatter(x=merged_series["Paso"], y=merged_series[col_act], name=f"{selected_metric} Período Actual", line=dict(color='#0091ff', width=3)))
            fig_series.add_trace(go.Scatter(x=merged_series["Paso"], y=merged_series[col_ant], name=f"{selected_metric} Período Anterior", line=dict(color='#ff4d4d', width=2, dash='dash')))
            
            fig_series.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font_color='white',
                hovermode="x unified",
                xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
            )
            st.plotly_chart(fig_series, use_container_width=True)
        else:
            st.info("Sin registros suficientes para graficar las series comparativas.")

    # ----------------------------------------------------
    # TAB 5: DETALLE POR DÍA
    # ----------------------------------------------------
    with tabs[4]:
        st.subheader("📅 Desglose Diario Consolidado")
        
        serie_diaria = obtener_serie_agrupada(desde, hasta, "Diario")
        if not serie_diaria.empty:
            st.dataframe(serie_diaria, use_container_width=True, hide_index=True)
            
            # Export controls
            st.download_button(
                label="📥 Descargar CSV de Detalle Diario",
                data=serie_diaria.to_csv(index=False).encode('utf-8'),
                file_name=f"detalle_diario_{desde}_a_{hasta}.csv",
                mime="text/csv"
            )
            
            # Imprimible HTML
            def generar_html_impresion(empresa_nombre, d_desde, d_hasta, m, user):
                return f"""
                <html>
                <head>
                    <style>
                        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 45px; }}
                        .header {{ text-align: center; border-bottom: 3px solid #0091ff; padding-bottom: 25px; margin-bottom: 30px; }}
                        .title {{ font-size: 28px; font-weight: 900; margin: 0; color: #111; text-transform: uppercase; }}
                        .subtitle {{ font-size: 15px; color: #666; margin-top: 5px; font-weight: 500; }}
                        .metadata {{ font-size: 11px; color: #888; margin-top: 15px; text-transform: uppercase; letter-spacing: 0.5px; }}
                        .kpi-section {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 30px; }}
                        .kpi-box {{ border: 1px solid #e2e8f0; padding: 15px; border-radius: 12px; background: #f8fafc; text-align: center; }}
                        .kpi-box-title {{ font-size: 10px; color: #64748b; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; }}
                        .kpi-box-val {{ font-size: 18px; font-weight: 800; margin-top: 6px; color: #0f172a; }}
                        .footer {{ margin-top: 60px; text-align: center; font-size: 11px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 25px; }}
                        .signatures {{ display: flex; justify-content: space-between; margin-top: 80px; padding: 0 40px; }}
                        .sig-line {{ border-top: 2px solid #0f172a; width: 220px; text-align: center; padding-top: 8px; font-size: 11px; font-weight: 700; color: #334155; text-transform: uppercase; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <div class="title">{empresa_nombre}</div>
                        <div class="subtitle">Auditoría Financiera y Operativa Consolidada</div>
                        <div class="metadata">Período Fiscal: {d_desde} al {d_hasta} | Auditor Activo: {user} | Emisión: {pd.Timestamp.now().strftime('%d/%m/%Y %I:%M %p')}</div>
                    </div>
                    
                    <h3 style="text-transform: uppercase; font-size: 14px; color: #0f172a; letter-spacing: 0.5px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px;">1. Indicadores Financieros de Control</h3>
                    <div class="kpi-section">
                        <div class="kpi-box"><div class="kpi-box-title">Ventas Netas</div><div class="kpi-box-val">RD$ {m['ventas_netas']:,.2f}</div></div>
                        <div class="kpi-box"><div class="kpi-box-title">Costo de Ventas</div><div class="kpi-box-val">RD$ {m['costo_ventas']:,.2f}</div></div>
                        <div class="kpi-box"><div class="kpi-box-title">Utilidad Bruta</div><div class="kpi-box-val">RD$ {m['utilidad_bruta']:,.2f}</div></div>
                        <div class="kpi-box"><div class="kpi-box-title">Margen Bruto</div><div class="kpi-box-val">{m['margen_bruto']:.2f}%</div></div>
                    </div>
                    <div class="kpi-section" style="margin-top: 15px;">
                        <div class="kpi-box"><div class="kpi-box-title">Gastos Operativos</div><div class="kpi-box-val">RD$ {m['gastos_operativos']:,.2f}</div></div>
                        <div class="kpi-box"><div class="kpi-box-title">Utilidad Neta</div><div class="kpi-box-val">RD$ {m['utilidad_neta']:,.2f}</div></div>
                        <div class="kpi-box"><div class="kpi-box-title">Margen Neto</div><div class="kpi-box-val">{m['margen_neto']:.2f}%</div></div>
                        <div class="kpi-box"><div class="kpi-box-title">Flujo Neto</div><div class="kpi-box-val">RD$ {m['flujo_neto']:,.2f}</div></div>
                    </div>
                    
                    <div class="signatures">
                        <div class="sig-line">Auditor Interno</div>
                        <div class="sig-line">Gerente General</div>
                    </div>
                    
                    <div class="footer">
                        Este documento constituye un informe administrativo interno del sistema contable oficial. No reemplaza dictámenes impositivos regulados.
                    </div>
                </body>
                </html>
                """

            html_print = generar_html_impresion("BIBE RON 01", desde, hasta, m_act, st.session_state.get("usuario", "ADMIN"))
            st.download_button(
                label="🖨️ Descargar Informe Imprimible (PDF/HTML)",
                data=html_print,
                file_name=f"informe_imprimible_{desde}_a_{hasta}.html",
                mime="text/html"
            )
        else:
            st.info("Sin registros suficientes para desglose diario.")

    # ----------------------------------------------------
    # TAB 6: TOP PRODUCTOS
    # ----------------------------------------------------
    with tabs[5]:
        st.subheader("🏆 Evaluación de Rotación y Margen de Productos")
        st.caption("Top 10 productos que aportan mayor volumen y rentabilidad líquida en el período seleccionado.")

        detalle_p_df = _df_actual("detalle_venta")
        ventas_p_df = obtener_ventas_periodo_actualizadas(desde, hasta)
        
        if not ventas_p_df.empty and "id" in ventas_p_df.columns and not detalle_p_df.empty and "venta_id" in detalle_p_df.columns:
            for c in ["anulado", "cancelado"]:
                if c in ventas_p_df.columns:
                    ventas_p_df = ventas_p_df[~ventas_p_df[c].fillna(False).astype(bool)].copy()
            if "estado" in ventas_p_df.columns:
                ventas_p_df = ventas_p_df[~ventas_p_df["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()
                
            v_ids = ventas_p_df["id"].astype(str).tolist()
            detalle_per = detalle_p_df[detalle_p_df["venta_id"].astype(str).isin(v_ids)].copy()
            
            if not detalle_per.empty:
                prod_col = "producto" if "producto" in detalle_per.columns else ("nombre" if "nombre" in detalle_per.columns else None)
                if prod_col:
                    # Let's perform robust grouping dynamically identifying the total column
                    det_val_col = "total_linea" if "total_linea" in detalle_per.columns else ("total" if "total" in detalle_per.columns else ("total_precio" if "total_precio" in detalle_per.columns else None))
                    if det_val_col:
                        detalle_per["cantidad"] = pd.to_numeric(detalle_per["cantidad"], errors="coerce").fillna(0)
                        detalle_per[det_val_col] = pd.to_numeric(detalle_per[det_val_col], errors="coerce").fillna(0)
                        
                        prod_grouped = detalle_per.groupby(prod_col).agg({
                            "cantidad": "sum",
                            det_val_col: "sum"
                        }).reset_index()
                        prod_grouped.columns = ["Producto", "Unidades Vendidas", "Ingreso Recaudado"]
                        prod_grouped = prod_grouped.sort_values("Ingreso Recaudado", ascending=False).head(10)
                        
                        st.dataframe(prod_grouped, use_container_width=True, hide_index=True)
                    else:
                        st.info("Sin registros de montos legibles en el detalle de productos.")
                else:
                    st.info("Sin registros legibles en el detalle de productos.")
            else:
                st.info("Sin registros de detalle en este rango de fechas.")
        else:
            st.info("Sin transacciones registradas en este período.")

    # ----------------------------------------------------
    # TAB 7: FLUJO DE EFECTIVO
    # ----------------------------------------------------
    with tabs[6]:
        st.subheader("💵 Conciliación de Liquidez Real")
        st.caption("Desglose detallado de las entradas y salidas de efectivo y banco del negocio.")
        
        c_fl1, c_fl2 = st.columns(2)
        with c_fl1:
            st.info(f"💰 **Efectivo en Caja del Período:** RD$ {m_act['efectivo_caja']:,.2f}")
        with c_fl2:
            st.success(f"💳 **Banco / Transferencias Netas:** RD$ {m_act['banco_transferencia']:,.2f}")
            
        st.markdown("---")
        st.subheader("Detalle de Transacciones del Flujo")
        hist_df_all = construir_historial_dinero_real()
        if not hist_df_all.empty and "fecha" in hist_df_all.columns:
            try:
                hist_df_all["_fecha_dt"] = pd.to_datetime(hist_df_all["fecha"], errors="coerce")
                hist_df_all = hist_df_all[(hist_df_all["_fecha_dt"].dt.date >= desde) & (hist_df_all["_fecha_dt"].dt.date <= hasta)].copy()
            except Exception:
                pass
                
        if not hist_df_all.empty:
            # Drop temporary datetime column for display
            display_hist = hist_df_all.drop(columns=["_fecha_dt"], errors="ignore")
            st.dataframe(display_hist, use_container_width=True, hide_index=True)
        else:
            st.info("Sin movimientos financieros para el rango de fechas seleccionado.")

    # ----------------------------------------------------
    # TAB 8: INVENTARIO
    # ----------------------------------------------------
    with tabs[7]:
        st.subheader("📦 Valoración e Indicadores de Inventario")
        
        ci1, ci2, ci3 = st.columns(3)
        with ci1:
            st.metric("Inventario a Costo de Stock", f"RD$ {m_act['inventario_costo']:,.2f}")
        with ci2:
            st.metric("Inventario a Precio de Venta", f"RD$ {m_act['inventario_venta']:,.2f}")
        with ci3:
            st.metric("Ganancia Potencial de Stock", f"RD$ {m_act['ganancia_potencial']:,.2f}")
            
        st.markdown("---")
        st.subheader("🚨 Alertas de Quiebre de Stock")
        prod_df = _df_actual("productos")
        if not prod_df.empty and "stock" in prod_df.columns:
            prod_df["stock"] = pd.to_numeric(prod_df["stock"], errors="coerce").fillna(0)
            agotados = prod_df[prod_df["stock"] <= 0]
            bajos = prod_df[(prod_df["stock"] > 0) & (prod_df["stock"] <= 5)]
            
            st.write(f"🛑 **Productos Agotados (Stock 0):** {len(agotados)}")
            if not agotados.empty:
                st.dataframe(agotados[["nombre", "codigo", "stock", "precio"]].head(5), use_container_width=True, hide_index=True)
                
            st.write(f"⚠️ **Productos con Stock Crítico (<= 5):** {len(bajos)}")
            if not bajos.empty:
                st.dataframe(bajos[["nombre", "codigo", "stock", "precio"]].head(5), use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros de catálogo de inventario activos.")

    # ----------------------------------------------------
    # TAB 9: CRÉDITOS
    # ----------------------------------------------------
    with tabs[8]:
        st.subheader("💳 Deuda y Antigüedad de Cuentas por Cobrar")
        
        cred_df = _df_actual("cuentas_por_cobrar")
        if not cred_df.empty:
            for c_col in ["monto_original", "saldo_pendiente", "monto_abonado"]:
                if c_col in cred_df.columns:
                    cred_df[c_col] = pd.to_numeric(cred_df[c_col], errors="coerce").fillna(0)
                    
            if "estado" in cred_df.columns:
                activas = cred_df[cred_df["estado"].astype(str).str.lower() != "saldada"].copy()
            else:
                activas = cred_df.copy()
                
            if not activas.empty:
                st.dataframe(activas[["cliente_nombre", "monto_original", "monto_abonado", "saldo_pendiente", "fecha"]], use_container_width=True, hide_index=True)
            else:
                st.info("Todas las cuentas por cobrar se encuentran saldadas al día.")
        else:
            st.info("No hay transacciones registradas bajo la modalidad de crédito.")

    # ----------------------------------------------------
    # TAB 10: DISTRIBUCIÓN DE UTILIDAD
    # ----------------------------------------------------
    with tabs[9]:
        st.subheader("🤝 Distribución Societaria y Dividendos")
        st.caption("Distribución automática basada en el acuerdo oficial: 65% Propietario / 35% Gerente Administrador.")
        
        utilidad_distribuible = max(m_act["utilidad_neta"], 0.0)
        dueno_pct = utilidad_distribuible * 0.65
        gerente_pct = utilidad_distribuible * 0.35
        
        cd1, cd2 = st.columns(2)
        with cd1:
            st.info(f"💼 **Participación Propietario (65%):** RD$ {dueno_pct:,.2f}")
        with cd2:
            st.success(f"👔 **Participación Gerente (35%):** RD$ {gerente_pct:,.2f}")
            
        st.markdown("---")
        st.subheader("⚖️ Excedente Real de Reinversión")
        
        # Withdrawals made by the owner in the period
        retiros_dueno_df = _filtrar_periodo_df(_df_actual("gastos_dueno"), desde, hasta)
        retiros_tot = float(_sum_any(retiros_dueno_df, ["monto", "total", "valor"]))
        excedente = m_act["utilidad_neta"] - retiros_tot
        
        st.write(f"🔹 **Utilidad Neta Generada:** RD$ {m_act['utilidad_neta']:,.2f}")
        st.write(f"🔹 **Retiros Realizados por Socio/Dueño:** RD$ {retiros_tot:,.2f}")
        
        if excedente >= 0:
            st.success(f"🟢 **Excedente neto para Reinversión:** RD$ {excedente:,.2f}")
        else:
            st.warning(f"🔴 **Exceso de Retiros (Déficit de Caja):** RD$ {excedente:,.2f}")

    # ----------------------------------------------------
    # TAB 11: ANÁLISIS AVANZADO
    # ----------------------------------------------------
    with tabs[10]:
        st.subheader("🛡️ Centro de Auditoría Contable y Cruce de Datos")
        st.caption("Validaciones cruzadas automáticas entre los módulos de facturación general y detalle financiero.")
        
        v_aud = obtener_ventas_periodo_actualizadas(desde, hasta)
        det_aud = _df_actual("detalle_venta")
        
        if not v_aud.empty and not det_aud.empty and "id" in v_aud.columns and "venta_id" in det_aud.columns:
            for c in ["anulado", "cancelado"]:
                if c in v_aud.columns:
                    v_aud = v_aud[~v_aud[c].fillna(False).astype(bool)].copy()
            if "estado" in v_aud.columns:
                v_aud = v_aud[~v_aud["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()
                
            v_ids = v_aud["id"].astype(str).tolist()
            det_aud_filtered = det_aud[det_aud["venta_id"].astype(str).isin(v_ids)].copy()
            
            v_total_sum = float(v_aud["total"].sum())
            
            # Dynamic total column checking to prevent KeyError
            det_total_col = "total_linea" if "total_linea" in det_aud_filtered.columns else ("total" if "total" in det_aud_filtered.columns else None)
            if det_total_col:
                det_total_sum = float(pd.to_numeric(det_aud_filtered[det_total_col], errors="coerce").fillna(0).sum())
            else:
                det_total_sum = 0.0
            diff = abs(v_total_sum - det_total_sum)
            
            if diff < 1.0:
                st.success("🟢 **Consistencia Ventas vs Detalle de Productos: ÉXITO** (Diferencia: RD$ 0.00)")
                st.caption(f"Total cabeceras: RD$ {v_total_sum:,.2f} | Total detalle: RD$ {det_total_sum:,.2f}")
            else:
                st.error(f"🔴 **Descuadre Contable Detectado (Cabecera vs Detalle):**")
                st.write(f"❌ Cabecera de Ventas: RD$ {v_total_sum:,.2f}")
                st.write(f"❌ Detalle de Ventas: RD$ {det_total_sum:,.2f}")
                st.write(f"⚠️ Diferencia sin registrar en inventario: **RD$ {diff:,.2f}**")
        else:
            st.info("Sin registros históricos suficientes en el período para auditar consistencias.")

        st.markdown("---")
        st.subheader("💵 C-07 · Conciliación Automática: Ventas vs Pagos vs Cierres de Caja")
        st.caption("Verificación cruzada entre las ventas cobradas y el flujo reportado en caja y pagos.")

        v_conc = obtener_ventas_periodo_actualizadas(desde, hasta)
        if not v_conc.empty:
            for c in ["anulado", "cancelado"]:
                if c in v_conc.columns:
                    v_conc = v_conc[~v_conc[c].fillna(False).astype(bool)].copy()
            if "estado" in v_conc.columns:
                v_conc = v_conc[~v_conc["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()

        pagos_df_conc = _df_actual("ventas_pagos")
        cajas_df_conc = _df_actual("cierre_caja")

        tot_ventas_efectivo = 0.0
        tot_ventas_transf = 0.0
        tot_ventas_tarjeta = 0.0

        if not v_conc.empty:
            met_col = "metodo_pago" if "metodo_pago" in v_conc.columns else ("metodo" if "metodo" in v_conc.columns else None)
            tot_col = "total_contable" if "total_contable" in v_conc.columns else "total"
            if met_col and tot_col:
                v_ef = v_conc[v_conc[met_col].astype(str).apply(normalizar_texto).isin(["efectivo", "cash"])]
                v_tr = v_conc[v_conc[met_col].astype(str).apply(normalizar_texto).isin(["transferencia", "transfer"])]
                v_tj = v_conc[v_conc[met_col].astype(str).apply(normalizar_texto).isin(["tarjeta", "card"])]
                tot_ventas_efectivo = float(v_ef[tot_col].sum()) if not v_ef.empty else 0.0
                tot_ventas_transf = float(v_tr[tot_col].sum()) if not v_tr.empty else 0.0
                tot_ventas_tarjeta = float(v_tj[tot_col].sum()) if not v_tj.empty else 0.0

        tot_pagos_efectivo = 0.0
        tot_pagos_transf = 0.0
        tot_pagos_tarjeta = 0.0
        if not pagos_df_conc.empty and "metodo" in pagos_df_conc.columns and "monto" in pagos_df_conc.columns:
            p_ef = pagos_df_conc[pagos_df_conc["metodo"].astype(str).apply(normalizar_texto) == "efectivo"]
            p_tr = pagos_df_conc[pagos_df_conc["metodo"].astype(str).apply(normalizar_texto) == "transferencia"]
            p_tj = pagos_df_conc[pagos_df_conc["metodo"].astype(str).apply(normalizar_texto) == "tarjeta"]
            tot_pagos_efectivo = float(p_ef["monto"].sum()) if not p_ef.empty else 0.0
            tot_pagos_transf = float(p_tr["monto"].sum()) if not p_tr.empty else 0.0
            tot_pagos_tarjeta = float(p_tj["monto"].sum()) if not p_tj.empty else 0.0

        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            st.metric("Ventas Efectivo Registradas", f"RD$ {tot_ventas_efectivo:,.2f}")
        with cc2:
            st.metric("Ventas Transferencia Registradas", f"RD$ {tot_ventas_transf:,.2f}")
        with cc3:
            st.metric("Ventas Tarjeta Registradas", f"RD$ {tot_ventas_tarjeta:,.2f}")

        diff_ef = abs(tot_ventas_efectivo - tot_pagos_efectivo) if tot_pagos_efectivo > 0 else 0.0
        if tot_pagos_efectivo > 0 and diff_ef > 1.0:
            st.warning(f"⚠️ **Diferencia en desglose de pagos en efectivo:** Ventas: RD$ {tot_ventas_efectivo:,.2f} vs Pagos recibidos: RD$ {tot_pagos_efectivo:,.2f} (Diferencia: RD$ {diff_ef:,.2f})")
        else:
            st.success("🟢 **Conciliación de Medios de Pago:** Consistente.")


# =========================================================
# AUDITORÍA
# =========================================================


def render_distribucion_beneficios():
    st.title("💼 Distribución de Beneficios")
    if not es_admin():
        st.error("Solo administración puede registrar la distribución de beneficios.")
        st.stop()

    st.caption("Divide la utilidad neta positiva según el % del gerente. Los gastos/retiros del dueño se descuentan solo de la parte del dueño.")

    c1, c2 = st.columns(2)
    with c1:
        desde_db = st.date_input("Desde", value=date.today(), key="dist_desde")
    with c2:
        hasta_db = st.date_input("Hasta", value=date.today(), key="dist_hasta")

    st.markdown("### ⚖️ Porcentaje de distribución")
    p1, p2 = st.columns(2)
    with p1:
        porc_gerente = st.number_input(
            "% Gerente",
            min_value=0.0,
            max_value=100.0,
            value=35.0,
            step=1.0,
            key="dist_porc_gerente",
            help="Puedes subirlo o bajarlo según el acuerdo del mes."
        )
    porc_duena = max(100.0 - float(porc_gerente), 0.0)
    with p2:
        st.metric("% Dueño", f"{porc_duena:.2f}%")

    calc = calcular_distribucion_beneficios(desde_db, hasta_db, porc_duena, porc_gerente)

    st.markdown("### 📊 Cálculo automático")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Utilidad neta", _fmt_rd(calc["utilidad_neta"]))
    k2.metric("Beneficio gerente", _fmt_rd(calc["monto_gerente_calculado"]))
    k3.metric("Parte del dueño", _fmt_rd(calc["monto_duena_calculado"]))
    k4.metric("Gastos dueño", _fmt_rd(calc["gastos_duena_periodo"]))

    if calc.get("periodo_en_perdida"):
        st.warning("Este período está en pérdida. No se calcula beneficio para gerente ni dueño. Los gastos del dueño quedan como consumo/deuda contra el negocio.")

    st.markdown("### 👑 Parte del dueño")
    d1, d2 = st.columns(2)
    d1.metric("Disponible dueño después de gastos", _fmt_rd(calc["disponible_duena"]))

    max_duena = max(calc["disponible_duena"], 0)

    st.caption("Puedes pagar al dueño por varios métodos. El sistema suma efectivo + transferencia + tarjeta.")
    pd1, pd2, pd3 = st.columns(3)
    with pd1:
        pago_dueno_efectivo = st.number_input("Pago dueño efectivo", min_value=0.0, value=0.0, step=1.0, key="dist_pago_dueno_efectivo")
    with pd2:
        pago_dueno_transferencia = st.number_input("Pago dueño transferencia", min_value=0.0, value=0.0, step=1.0, key="dist_pago_dueno_transferencia")
    with pd3:
        pago_dueno_tarjeta = st.number_input("Pago dueño tarjeta", min_value=0.0, value=0.0, step=1.0, key="dist_pago_dueno_tarjeta")

    pago_duena = float(pago_dueno_efectivo or 0) + float(pago_dueno_transferencia or 0) + float(pago_dueno_tarjeta or 0)

    if pago_duena > max_duena:
        st.error("El pago total al dueño no puede ser mayor que el disponible del dueño.")
        pago_duena = max_duena

    restante_dueno = max(max_duena - pago_duena, 0)
    reinversion_duena = st.number_input(
        "Monto a reinvertir",
        min_value=0.0,
        max_value=float(restante_dueno) if restante_dueno > 0 else None,
        value=float(restante_dueno),
        step=1.0,
        key="dist_reinv_duena"
    )

    pendiente_duena = max(max_duena - pago_duena - reinversion_duena, 0)
    exceso_gastos_duena = abs(calc["disponible_duena"]) if calc["disponible_duena"] < 0 else 0

    st.markdown("### 👨‍💼 Parte del gerente")
    g1, g2 = st.columns(2)
    g1.metric("Calculado gerente", _fmt_rd(calc["monto_gerente_calculado"]))

    max_gerente = max(calc["monto_gerente_calculado"], 0)

    st.caption("Puedes pagar al gerente por varios métodos. El sistema suma efectivo + transferencia + tarjeta.")
    pg1, pg2, pg3 = st.columns(3)
    with pg1:
        pago_gerente_efectivo = st.number_input("Pago gerente efectivo", min_value=0.0, value=0.0, step=1.0, key="dist_pago_gerente_efectivo")
    with pg2:
        pago_gerente_transferencia = st.number_input("Pago gerente transferencia", min_value=0.0, value=0.0, step=1.0, key="dist_pago_gerente_transferencia")
    with pg3:
        pago_gerente_tarjeta = st.number_input("Pago gerente tarjeta", min_value=0.0, value=0.0, step=1.0, key="dist_pago_gerente_tarjeta")

    pago_gerente = float(pago_gerente_efectivo or 0) + float(pago_gerente_transferencia or 0) + float(pago_gerente_tarjeta or 0)

    if pago_gerente > max_gerente:
        st.error("El pago total al gerente no puede ser mayor que el beneficio calculado del gerente.")
        pago_gerente = max_gerente

    pendiente_gerente = max(max_gerente - pago_gerente, 0)
    g2.metric("Pendiente gerente", _fmt_rd(pendiente_gerente))

    metodo_duena = "mixto"
    metodo_gerente = "mixto"

    st.markdown("### 📌 Resumen final")
    resumen_dist = pd.DataFrame([
        {"Concepto": "Utilidad neta", "RD$": _fmt_rd(calc["utilidad_neta"])},
        {"Concepto": "Beneficio gerente según %", "RD$": _fmt_rd(calc["monto_gerente_calculado"])},
        {"Concepto": "Pago gerente", "RD$": _fmt_rd(pago_gerente)},
        {"Concepto": "Pendiente gerente", "RD$": _fmt_rd(pendiente_gerente)},
        {"Concepto": "Parte del dueño", "RD$": _fmt_rd(calc["monto_duena_calculado"])},
        {"Concepto": "Gastos/retiros dueño", "RD$": _fmt_rd(-calc["gastos_duena_periodo"])},
        {"Concepto": "Disponible dueño", "RD$": _fmt_rd(calc["disponible_duena"])},
        {"Concepto": "Pago dueño", "RD$": _fmt_rd(pago_duena)},
        {"Concepto": "Reinversión dueño", "RD$": _fmt_rd(reinversion_duena)},
        {"Concepto": "Pendiente dueño", "RD$": _fmt_rd(pendiente_duena)},
        {"Concepto": "Dueño debe al negocio por exceso de gastos", "RD$": _fmt_rd(exceso_gastos_duena)},
    ])
    st.dataframe(resumen_dist, use_container_width=True, hide_index=True)

    if exceso_gastos_duena > 0:
        st.warning(f"La dueño gastó más de su 65%. Diferencia a favor del negocio: {_fmt_rd(exceso_gastos_duena)}")

    observacion = st.text_area("Observación", key="dist_obs")

    if st.button("💾 Guardar distribución", key="btn_guardar_distribucion"):
        if guardar_distribucion_beneficios(
            desde_db, hasta_db, calc,
            pago_duena, reinversion_duena, pendiente_duena,
            pago_gerente, pendiente_gerente,
            metodo_duena, metodo_gerente,
            observacion,
            pago_dueno_efectivo=pago_dueno_efectivo,
            pago_dueno_transferencia=pago_dueno_transferencia,
            pago_dueno_tarjeta=pago_dueno_tarjeta,
            pago_gerente_efectivo=pago_gerente_efectivo,
            pago_gerente_transferencia=pago_gerente_transferencia,
            pago_gerente_tarjeta=pago_gerente_tarjeta,
        ):
            st.success("Distribución guardada correctamente.")
            st.rerun()

    st.markdown("---")
    st.subheader("📚 Historial de distribuciones")
    hist_dist = _df_actual("distribucion_beneficios")
    if hist_dist.empty:
        st.info("No hay distribuciones registradas.")
    else:
        st.dataframe(hist_dist, use_container_width=True)
        descargar_archivos(hist_dist, "distribucion_beneficios")





def render_capital_base():
    st.title("💼 Capital Base")
    if not es_admin():
        st.error("Solo administración puede configurar el capital base.")
        st.stop()

    st.caption("Aquí registras el capital que pertenece al negocio para que no se confunda con ganancia.")

    with st.expander("➕ Registrar capital base", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            concepto = st.text_input("Concepto", value="Capital base inicial", key="cap_concepto")
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="cap_monto")
        with c2:
            origen = st.selectbox("Origen", ["Inventario + dinero real", "Aporte dueño", "Ajuste contable", "Otro"], key="cap_origen")
            obs = st.text_area("Observación", key="cap_obs")
        if st.button("Guardar capital base", key="btn_cap_guardar"):
            if insertar("capital_base", {"fecha": datetime.now().isoformat(), "concepto": concepto, "monto": float(monto), "origen": origen, "observacion": obs, "activo": True}):
                registrar_movimiento_contable("capital_base", concepto, "3001", "Capital base", "capital", credito=float(monto), descripcion=obs)
                st.success("Capital base guardado.")
                st.rerun()

    df = _df_actual("capital_base")
    if df.empty:
        st.info("No hay capital base registrado.")
    else:
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "capital_base")

# =========================================================
# ACTIVOS FIJOS
# =========================================================


def render_activos_fijos():
    st.title("🧊 Activos Fijos y Depreciación")
    if not es_admin():
        st.error("Solo administración puede gestionar activos fijos.")
        st.stop()

    st.caption("Registra freezers, neveras, mobiliario y equipos para calcular depreciación.")

    with st.expander("➕ Registrar activo fijo", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            nombre = st.text_input("Activo", key="af_nombre")
            categoria = st.selectbox("Categoría", ["Freezer", "Nevera", "Mobiliario", "Equipo", "Vehículo", "Otro"], key="af_cat")
        with c2:
            fecha_compra = st.date_input("Fecha compra", value=date.today(), key="af_fecha")
            costo = st.number_input("Costo", min_value=0.0, step=1.0, key="af_costo")
        with c3:
            vida = st.number_input("Vida útil meses", min_value=1.0, step=1.0, value=60.0, key="af_vida")
            dep_mensual = costo / vida if vida else 0
            st.metric("Depreciación mensual", f"RD$ {dep_mensual:,.2f}")
        obs = st.text_area("Observación", key="af_obs")
        if st.button("Guardar activo fijo", key="btn_af_guardar"):
            payload = {
                "fecha_compra": str(fecha_compra),
                "nombre": nombre,
                "categoria": categoria,
                "costo": float(costo),
                "vida_util_meses": float(vida),
                "depreciacion_mensual": float(dep_mensual),
                "depreciacion_acumulada": 0,
                "valor_en_libros": float(costo),
                "estado": "activo",
                "observacion": obs,
            }
            if insertar("activos_fijos", payload):
                st.success("Activo fijo guardado.")
                st.rerun()

    activos = _df_actual("activos_fijos")
    if activos.empty:
        st.info("No hay activos fijos registrados.")
    else:
        st.dataframe(activos, use_container_width=True)
        descargar_archivos(activos, "activos_fijos")

    with st.expander("📉 Generar depreciación mensual", expanded=False):
        periodo = st.text_input("Periodo", value=date.today().strftime("%Y-%m"), key="dep_periodo")
        if st.button("Generar depreciación del mes", key="btn_dep_generar"):
            creados = 0
            for _, r in activos.iterrows():
                if str(r.get("estado", "activo")).lower() != "activo":
                    continue
                monto = float(limpiar_numero(r.get("depreciacion_mensual")) or 0)
                if monto <= 0:
                    continue
                if insertar("depreciaciones", {
                    "activo_id": r.get("id"),
                    "fecha": str(date.today()),
                    "activo_nombre": r.get("nombre"),
                    "monto": monto,
                    "periodo": periodo,
                    "observacion": "Depreciación mensual automática",
                }):
                    registrar_movimiento_contable("depreciacion", r.get("id"), "6006", "Depreciación", "gasto", debito=monto, descripcion=f"Depreciación {r.get('nombre')}")
                    creados += 1
            st.success(f"Depreciaciones generadas: {creados}")
            st.rerun()

    deps = _df_actual("depreciaciones")
    if not deps.empty:
        st.subheader("Historial de depreciaciones")
        st.dataframe(deps, use_container_width=True)


# =========================================================
# LIBRO MAYOR NAVEGABLE
# =========================================================

def render_libro_mayor():
    st.title("📒 Libro Mayor")
    st.caption("Vista del Libro Mayor navegable por cuenta contable. Muestra saldo inicial, movimientos del período y saldo final.")

    if not (es_admin() or tiene_permiso("puede_ver_reportes")):
        st.error("No tienes permiso para ver este módulo.")
        st.stop()

    desde_lm, hasta_lm = selector_fechas_universal("libro_mayor")

    # Obtener los movimientos del periodo desde movimientos_contables
    try:
        resp = supabase.table("movimientos_contables")\
            .select("*")\
            .gte("fecha", desde_lm.strftime("%Y-%m-%dT00:00:00"))\
            .lte("fecha", hasta_lm.strftime("%Y-%m-%dT23:59:59"))\
            .execute()
        movimientos_raw = resp.data or []
    except Exception as e:
        st.error(f"Error al cargar movimientos contables: {e}")
        movimientos_raw = []

    if not movimientos_raw:
        st.info("No hay movimientos contables registrados en el período seleccionado.")
        return

    df_mov = pd.DataFrame(movimientos_raw)
    
    # Crear una columna amigable para seleccionar
    df_mov["cuenta_completa"] = df_mov.apply(
        lambda r: f"{r.get('cuenta_codigo') or 'S/C'} - {r.get('cuenta_nombre') or 'Sin Cuenta'}", axis=1
    )
    
    cuentas_disponibles = sorted(df_mov["cuenta_completa"].unique())
    cuenta_sel = st.selectbox("Seleccionar Cuenta Contable", cuentas_disponibles, key="lm_cuenta")
    
    df_filtrado = df_mov[df_mov["cuenta_completa"] == cuenta_sel].copy()
    
    if df_filtrado.empty:
        st.info(f"No hay movimientos para la cuenta seleccionada en este período.")
        return
        
    # Ordenar por fecha
    df_filtrado = df_filtrado.sort_values(by="fecha")

    # Identificar el tipo de cuenta contable para calcular el saldo acumulado correctamente
    tipo_cuenta = str(df_filtrado["tipo_cuenta"].iloc[0]).lower() if "tipo_cuenta" in df_filtrado.columns else "activo"
    
    movimientos = []
    saldo_acum = 0.0
    for _, row in df_filtrado.iterrows():
        debito = float(row.get("debito") or 0.0)
        credito = float(row.get("credito") or 0.0)
        fecha_mov = str(row.get("fecha") or "—")[:10]
        desc = str(row.get("descripcion") or row.get("concepto") or "—")
        ref = str(row.get("referencia_id") or "—")

        if tipo_cuenta in ["activo", "gasto"]:
            saldo_acum += (debito - credito)
        else:
            saldo_acum += (credito - debito)

        movimientos.append({
            "Fecha": fecha_mov,
            "Referencia": ref,
            "Descripción": desc,
            "Débito (RD$)": debito,
            "Crédito (RD$)": credito,
            "Saldo Acumulado (RD$)": saldo_acum,
        })

    df_lm = pd.DataFrame(movimientos)
    total_deb = df_lm["Débito (RD$)"].sum()
    total_cred = df_lm["Crédito (RD$)"].sum()
    saldo_final = df_lm["Saldo Acumulado (RD$)"].iloc[-1] if not df_lm.empty else 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Movimientos", len(df_lm))
    m2.metric("Total Débito", f"RD$ {total_deb:,.2f}")
    m3.metric("Total Crédito", f"RD$ {total_cred:,.2f}")
    m4.metric("Saldo Final", f"RD$ {saldo_final:,.2f}")

    st.dataframe(df_lm, use_container_width=True, hide_index=True)
    descargar_archivos(df_lm, f"libro_mayor_{cuenta_sel.replace('/', '_').replace(' ', '_')}")

    if len(df_lm) > 1:
        st.markdown("#### 📈 Evolución del Saldo")
        fig_lm = px.line(df_lm, x="Fecha", y="Saldo Acumulado (RD$)",
                         title=f"Saldo Acumulado — {cuenta_sel}",
                         color_discrete_sequence=["#1a237e"])
        fig_lm.update_layout(height=280)
        st.plotly_chart(fig_lm, use_container_width=True)


# =========================================================
# CIERRE DE PERÍODO CONTABLE
# =========================================================

def render_cierre_periodo():
    import calendar
    st.title("🔒 Cierre de Período Contable")
    st.caption("Congela un mes contable para preparar reportes DGII definitivos y registrar el cierre en el sistema.")

    if not es_admin():
        st.error("⛔ Solo el Administrador puede realizar cierres de período.")
        st.stop()

    st.warning("""
⚠️ **¿Qué hace el Cierre de Período?**
- Registra el cierre oficial del mes en el libro de movimientos contables.
- Genera un **Resumen de Cierre** descargable (ventas, ITBIS, compras, gastos, utilidad).
- Recuerda descargar y enviar el **IT-1** a la DGII antes del día 20 del mes siguiente.
    """)

    col_cp1, col_cp2 = st.columns(2)
    with col_cp1:
        ano_cierre = st.number_input("Año", min_value=2020, max_value=2035,
                                     value=date.today().year, key="cp_ano")
    with col_cp2:
        MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
                 7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
        mes_cierre = st.selectbox("Mes a Cerrar", list(MESES.keys()),
                                   format_func=lambda x: MESES[x],
                                   index=max(date.today().month - 2, 0),
                                   key="cp_mes")

    desde_cp = date(int(ano_cierre), mes_cierre, 1)
    ultimo_dia = calendar.monthrange(int(ano_cierre), mes_cierre)[1]
    hasta_cp = date(int(ano_cierre), mes_cierre, ultimo_dia)

    st.info(f"📅 Período a cerrar: **{MESES[mes_cierre]} {ano_cierre}** ({desde_cp} → {hasta_cp})")

    df_v_cp = _filtrar_periodo_df(_df_actual("ventas"), desde_cp, hasta_cp)
    df_c_cp = _filtrar_periodo_df(_df_actual("compras"), desde_cp, hasta_cp)
    df_g_cp = _filtrar_periodo_df(_df_actual("gastos"), desde_cp, hasta_cp)

    total_ventas_cp   = float(df_v_cp["total"].sum())       if not df_v_cp.empty and "total" in df_v_cp.columns else 0.0
    total_itbis_cp    = float(df_v_cp["itbis_total"].sum()) if not df_v_cp.empty and "itbis_total" in df_v_cp.columns else 0.0
    total_compras_cp  = float(df_c_cp["total"].sum())       if not df_c_cp.empty and "total" in df_c_cp.columns else 0.0
    total_gastos_cp   = float(df_g_cp["monto"].sum())       if not df_g_cp.empty and "monto" in df_g_cp.columns else 0.0
    utilidad_cp = total_ventas_cp - total_itbis_cp - total_compras_cp - total_gastos_cp

    st.divider()
    st.markdown(f"### 📊 Resumen: {MESES[mes_cierre]} {ano_cierre}")
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("Ventas Brutas",  f"RD$ {total_ventas_cp:,.2f}")
    r2.metric("ITBIS Cobrado",  f"RD$ {total_itbis_cp:,.2f}")
    r3.metric("Compras",        f"RD$ {total_compras_cp:,.2f}")
    r4.metric("Gastos",         f"RD$ {total_gastos_cp:,.2f}")
    r5.metric("Utilidad Neta",  f"RD$ {utilidad_cp:,.2f}",
              delta="Ganancia" if utilidad_cp >= 0 else "Pérdida",
              delta_color="normal" if utilidad_cp >= 0 else "inverse")
    st.caption(f"Facturas: {len(df_v_cp)} | Compras: {len(df_c_cp)} | Gastos: {len(df_g_cp)}")

    resumen_txt = (
        f"CIERRE DE PERÍODO CONTABLE\n"
        f"Empresa: {obtener_tenant_actual()}\n"
        f"Período: {MESES[mes_cierre]} {ano_cierre} ({desde_cp} → {hasta_cp})\n"
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Usuario: {nombre_usuario_actual()}\n"
        f"{'='*44}\n"
        f"VENTAS BRUTAS:      RD$ {total_ventas_cp:>12,.2f}\n"
        f"ITBIS COBRADO:      RD$ {total_itbis_cp:>12,.2f}\n"
        f"VENTAS NETAS:       RD$ {total_ventas_cp-total_itbis_cp:>12,.2f}\n"
        f"COSTO COMPRAS:      RD$ {total_compras_cp:>12,.2f}\n"
        f"GASTOS OPERATIVOS:  RD$ {total_gastos_cp:>12,.2f}\n"
        f"UTILIDAD NETA:      RD$ {utilidad_cp:>12,.2f}\n"
        f"{'='*44}\n"
        f"ITBIS A DECLARAR:   RD$ {total_itbis_cp:>12,.2f}\n"
        f"Facturas emitidas:  {len(df_v_cp)}\n"
        f"Compras registradas:{len(df_c_cp)}\n"
        f"Gastos registrados: {len(df_g_cp)}\n"
    )

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.download_button(
            "📥 Descargar Resumen de Cierre (TXT)",
            data=resumen_txt.encode("utf-8"),
            file_name=f"Cierre_{MESES[mes_cierre]}_{ano_cierre}.txt",
            mime="text/plain",
            key="btn_cierre_dl",
            use_container_width=True
        )
    with col_b2:
        confirmacion = st.text_input(
            f'Escribe "CERRAR {MESES[mes_cierre].upper()}" para confirmar:',
            key="cp_conf"
        )
        if st.button("🔒 Ejecutar Cierre de Período", key="btn_cp_exec",
                     type="primary", use_container_width=True):
            if confirmacion.strip().upper() == f"CERRAR {MESES[mes_cierre].upper()}":
                try:
                    tenant = obtener_tenant_actual()
                    ref_c = f"cierre:{ano_cierre}{str(mes_cierre).zfill(2)}"
                    periodo_str = f"{ano_cierre}-{str(mes_cierre).zfill(2)}"

                    supabase.table("movimientos_contables").insert({
                        "empresa_id": tenant,
                        "fecha": datetime.now().isoformat(),
                        "concepto": f"CIERRE DE PERÍODO — {MESES[mes_cierre]} {ano_cierre}",
                        "debito": 0.0,
                        "credito": 0.0,
                        "referencia": ref_c,
                    }).execute()

                    # C-08: Persistir cierre oficial en periodos_contables
                    try:
                        supabase.table("periodos_contables").insert({
                            "empresa_id": tenant,
                            "periodo": periodo_str,
                            "estado": "cerrado",
                            "fecha_cierre": datetime.now().isoformat(),
                            "usuario_cierre": nombre_usuario_actual()
                        }).execute()
                    except Exception:
                        pass

                    # Auditoría de seguridad
                    try:
                        registrar_auditoria_pro(
                            accion="cierre_periodo_contable",
                            modulo="Contabilidad",
                            tabla_afectada="movimientos_contables",
                            impacto_economico=float(utilidad_cp),
                            nivel_riesgo="alto",
                            riesgo_score=80.0,
                            descripcion=f"Cierre contable congelado para {MESES[mes_cierre]} {ano_cierre}. Ventas: RD$ {total_ventas_cp:,.2f}, ITBIS: RD$ {total_itbis_cp:,.2f}, Utilidad: RD$ {utilidad_cp:,.2f}."
                        )
                    except Exception:
                        pass
                except Exception as ex_cp:
                    st.error(f"Error al procesar el cierre de período: {ex_cp}")
                st.success(f"✅ Período **{MESES[mes_cierre]} {ano_cierre}** cerrado y congelado exitosamente. Descarga el resumen TXT para tus archivos.")
                st.balloons()
            else:
                st.error(f'Escribe exactamente: CERRAR {MESES[mes_cierre].upper()}')






