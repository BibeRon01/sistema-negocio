# modules/cxp_view.py — Módulo de Cuentas por Pagar (CxP) A&M ERP
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

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


def render_cxp():
    st.title("💳 Cuentas por Pagar (CxP)")
    st.caption("Gestión de deudas con proveedores, programación de pagos y antigüedad de saldos.")

    tab_cuentas, tab_abono, tab_antiguedad, tab_proveedores = st.tabs([
        "📋 Cuentas Pendientes", "💸 Registrar Pago / Abono", "📊 Antigüedad de Saldos", "🏬 Proveedores"
    ])

    try:
        resp_compras = supabase.table("compras").select("*").eq("empresa_id", obtener_tenant_actual()).execute()
        compras_data = resp_compras.data or []
    except Exception:
        compras_data = []

    try:
        resp_abonos = supabase.table("abonos_proveedores").select("*").execute()
        abonos_data = resp_abonos.data or []
    except Exception:
        abonos_data = []

    df_cxp = pd.DataFrame(compras_data) if compras_data else pd.DataFrame()
    df_abonos = pd.DataFrame(abonos_data) if abonos_data else pd.DataFrame()

    # Calcular saldos y abonos dinámicamente
    if not df_cxp.empty:
        df_cxp["total"] = pd.to_numeric(df_cxp["total"], errors="coerce").fillna(0.0)
        df_cxp["monto"] = pd.to_numeric(df_cxp["monto"], errors="coerce").fillna(0.0)
        df_cxp["total_compra"] = df_cxp["total"].where(df_cxp["total"] > 0, df_cxp["monto"])

        if not df_abonos.empty:
            df_abonos["monto"] = pd.to_numeric(df_abonos["monto"], errors="coerce").fillna(0.0)
            abonos_grouped = df_abonos.groupby("referencia")["monto"].sum().to_dict()
        else:
            abonos_grouped = {}

        df_cxp["monto_abonado"] = df_cxp.apply(
            lambda r: float(abonos_grouped.get(str(r.get("numero")), 0.0) or abonos_grouped.get(str(r.get("id")), 0.0)),
            axis=1
        )
        df_cxp["saldo_pendiente"] = df_cxp["total_compra"] - df_cxp["monto_abonado"]
    else:
        df_cxp = pd.DataFrame(columns=["id", "fecha", "numero", "proveedor", "descripcion", "total_compra", "monto_abonado", "saldo_pendiente", "usuario"])

    # Filtrar compras a crédito
    df_credito = pd.DataFrame()
    if not df_cxp.empty and "metodo_pago" in df_cxp.columns:
        df_credito = df_cxp[df_cxp["metodo_pago"].fillna("").astype(str).str.lower() == "credito"].copy()

    with tab_cuentas:
        st.subheader("📋 Facturas y Deudas de Compras a Crédito")

        if df_credito.empty:
            st.info("No hay facturas registradas a crédito.")
        else:
            df_pendientes = df_credito[df_credito["saldo_pendiente"] > 0.01].copy()
            if df_pendientes.empty:
                st.info("Actualmente no tienes deudas pendientes con proveedores.")
            else:
                total_deuda = float(df_pendientes["saldo_pendiente"].sum())
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Facturas a Crédito Pendientes", len(df_pendientes))
                c2.metric("Total Pendiente CxP", f"RD$ {total_deuda:,.2f}")
                c3.metric("Proveedores Afectados", df_pendientes["proveedor"].nunique() if "proveedor" in df_pendientes.columns else 0)

                st.divider()
                st.dataframe(df_pendientes[[
                    "id", "fecha", "numero", "proveedor", "descripcion", "total_compra", "monto_abonado", "saldo_pendiente", "usuario"
                ]], use_container_width=True, hide_index=True)
                descargar_archivos(df_pendientes, "cuentas_por_pagar")

    with tab_abono:
        st.subheader("💸 Registrar Pago o Abono a Proveedor")
        
        if df_credito.empty or df_credito[df_credito["saldo_pendiente"] > 0.01].empty:
            st.info("No hay compras con saldo pendiente de pago.")
        else:
            df_unpaid = df_credito[df_credito["saldo_pendiente"] > 0.01].copy()
            
            opciones_fact = []
            mapa_fact = {}
            for _, r in df_unpaid.iterrows():
                lbl = f"{r.get('proveedor')} | Fac: {r.get('numero') or r.get('id')[:8]} | Pendiente: RD$ {float(r.get('saldo_pendiente')):,.2f}"
                opciones_fact.append(lbl)
                mapa_fact[lbl] = r

            selected_lbl = st.selectbox("Selecciona la Factura a Pagar", opciones_fact, key="cxp_fac_sel")
            compra_row = mapa_fact[selected_lbl]
            
            prov_sel = compra_row.get("proveedor")
            num_fact = compra_row.get("numero") or str(compra_row.get("id"))
            max_pago = float(compra_row.get("saldo_pendiente"))

            with st.form("form_abono_cxp"):
                f1, f2 = st.columns(2)
                with f1:
                    st.text_input("Proveedor", value=prov_sel, disabled=True)
                    st.text_input("Número de Factura / NCF", value=num_fact, disabled=True)
                with f2:
                    monto_pago = st.number_input("Monto a Pagar (RD$) *", min_value=1.0, max_value=max_pago, value=min(5000.0, max_pago), step=500.0)
                    metodo_pago = st.selectbox("Método de Pago", ["Transferencia Bancaria", "Cheque", "Efectivo / Caja"])
                
                concepto_pago = st.text_area("Concepto / Referencia de Pago", placeholder=f"Pago parcial factura {num_fact}")

                if st.form_submit_button("💳 Registrar Pago a Proveedor", type="primary", use_container_width=True):
                    try:
                        # Buscar proveedor_id por nombre
                        prov_id = None
                        try:
                            resp_prov = supabase.table("proveedores").select("id").eq("nombre", prov_sel).eq("empresa_id", obtener_tenant_actual()).execute()
                            if resp_prov.data:
                                prov_id = resp_prov.data[0].get("id")
                        except Exception:
                            pass

                        # 1. Registrar el abono en abonos_proveedores
                        insertar("abonos_proveedores", {
                            "proveedor_id": prov_id,
                            "monto": float(monto_pago),
                            "metodo_pago": metodo_pago,
                            "fecha": datetime.now().isoformat(),
                            "usuario": nombre_usuario_actual(),
                            "referencia": num_fact,
                            "observacion": concepto_pago.strip()
                        })

                        # 2. Registrar movimiento contable
                        registrar_movimiento_contable(
                            "compras",
                            num_fact,
                            "2101",
                            "Cuentas por Pagar",
                            "pasivo",
                            debito=monto_pago,
                            credito=0.0,
                            descripcion=f"Pago CxP a {prov_sel}: {concepto_pago.strip()}"
                        )
                        
                        st.success(f"✅ Pago de **RD$ {monto_pago:,.2f}** a **{prov_sel}** registrado correctamente.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar pago: {e}")

    with tab_antiguedad:
        st.subheader("📊 Reporte de Antigüedad de Saldos (CxP)")
        
        if df_credito.empty or df_credito[df_credito["saldo_pendiente"] > 0.01].empty:
            st.info("No hay facturas pendientes para generar el reporte de antigüedad de saldos.")
        else:
            df_unpaid = df_credito[df_credito["saldo_pendiente"] > 0.01].copy()
            df_unpaid["fecha_parsed"] = pd.to_datetime(df_unpaid["fecha"], errors="coerce")
            hoy = pd.Timestamp(date.today())
            
            # Calcular días transcurridos
            df_unpaid["dias_antiguedad"] = (hoy - df_unpaid["fecha_parsed"]).dt.days.fillna(0).astype(int)
            
            # Clasificar en rangos
            bins = [-9999, 30, 60, 90, 99999]
            labels = ["0 a 30 días", "31 a 60 días", "61 a 90 días", "Más de 90 días"]
            df_unpaid["rango"] = pd.cut(df_unpaid["dias_antiguedad"], bins=bins, labels=labels)
            
            # Agrupar y resumir
            resumen_ant = df_unpaid.groupby("rango", observed=False)["saldo_pendiente"].sum().reset_index()
            resumen_ant.columns = ["Rango de Días", "Monto Pendiente"]
            
            total_pendiente = resumen_ant["Monto Pendiente"].sum()
            resumen_ant["% del Total"] = resumen_ant["Monto Pendiente"].apply(
                lambda x: f"{(x / total_pendiente * 100):.1f}%" if total_pendiente > 0 else "0.0%"
            )
            
            st.dataframe(resumen_ant, use_container_width=True, hide_index=True)
            
            if total_pendiente > 0:
                fig_ant = px.pie(resumen_ant, names="Rango de Días", values="Monto Pendiente",
                                 title="Distribución de Deuda por Antigüedad Real",
                                 color_discrete_sequence=px.colors.sequential.RdBu)
                st.plotly_chart(fig_ant, use_container_width=True)

    with tab_proveedores:
        st.subheader("🏬 Catálogo de Proveedores")
        render_proveedores()
