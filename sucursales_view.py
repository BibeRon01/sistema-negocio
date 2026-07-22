# modules/sucursales_view.py — Módulo de Sucursales A&M ERP
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date

from core.db import *
from core.auth import *
from core.utils import *
from core.helpers import *


def render_sucursales():
    st.title("🏢 Sucursales y Puntos de Venta")
    st.caption("Gestiona múltiples ubicaciones del negocio. Cada sucursal puede tener sus propios usuarios, ventas e inventario.")

    if not es_admin():
        st.error("⛔ Solo el Administrador puede gestionar sucursales.")
        st.stop()

    tab_lista, tab_nueva, tab_comparativo = st.tabs([
        "📋 Mis Sucursales", "➕ Nueva Sucursal", "📊 Comparativo"
    ])

    try:
        resp_suc = supabase.table("sucursales").select("*").eq(
            "empresa_id", obtener_tenant_actual()
        ).execute()
        sucursales_data = resp_suc.data or []
    except Exception:
        sucursales_data = []

    df_suc = pd.DataFrame(sucursales_data) if sucursales_data else pd.DataFrame()

    with tab_lista:
        st.subheader("📋 Sucursales Registradas")
        if df_suc.empty:
            st.info("No hay sucursales registradas. Crea la primera en la pestaña **➕ Nueva Sucursal**.")
        else:
            cols_cards = st.columns(min(len(df_suc), 3))
            for i, (_, suc_row) in enumerate(df_suc.iterrows()):
                col = cols_cards[i % 3]
                nombre_s = str(suc_row.get("nombre") or "—")
                dir_s    = str(suc_row.get("direccion") or "—")
                tel_s    = str(suc_row.get("telefono") or "—")
                activa_s = bool(suc_row.get("activa", True))
                color_s  = "#4caf50" if activa_s else "#9e9e9e"
                estado_s = "✅ Activa" if activa_s else "⏸ Inactiva"
                col.markdown(f"""
<div style="background:rgba(26,35,126,0.3);border:1px solid {color_s}44;border-radius:12px;padding:16px;margin-bottom:12px;">
  <div style="font-size:18px;font-weight:700;color:#fff;">🏢 {nombre_s}</div>
  <div style="font-size:12px;color:#aaa;margin-top:4px;">📍 {dir_s}</div>
  <div style="font-size:12px;color:#aaa;">📞 {tel_s}</div>
  <div style="font-size:12px;color:{color_s};margin-top:8px;font-weight:600;">{estado_s}</div>
</div>
                """, unsafe_allow_html=True)

            st.divider()
            st.dataframe(df_suc, use_container_width=True)
            descargar_archivos(df_suc, "sucursales")

            with st.expander("🛠️ Editar Sucursal"):
                if "nombre" in df_suc.columns:
                    suc_editar = st.selectbox("Sucursal a editar", df_suc["nombre"].tolist(), key="suc_edit_sel")
                    row_edit = df_suc[df_suc["nombre"] == suc_editar].iloc[0] if suc_editar else None
                    if row_edit is not None:
                        suc_id_edit = row_edit.get("id")
                        with st.form("form_edit_suc"):
                            ec1, ec2 = st.columns(2)
                            with ec1:
                                edit_nombre = st.text_input("Nombre", value=str(row_edit.get("nombre") or ""))
                                edit_dir    = st.text_input("Dirección", value=str(row_edit.get("direccion") or ""))
                            with ec2:
                                edit_tel   = st.text_input("Teléfono", value=str(row_edit.get("telefono") or ""))
                                edit_activa = st.checkbox("Sucursal activa", value=bool(row_edit.get("activa", True)))
                            edit_obs = st.text_area("Observación", value=str(row_edit.get("observacion") or ""))
                            if st.form_submit_button("💾 Guardar cambios", type="primary"):
                                ok = actualizar("sucursales", suc_id_edit, {
                                    "nombre": edit_nombre.strip(),
                                    "direccion": edit_dir.strip(),
                                    "telefono": edit_tel.strip(),
                                    "activa": edit_activa,
                                    "observacion": edit_obs.strip(),
                                })
                                if ok:
                                    st.success(f"Sucursal '{edit_nombre}' actualizada.")
                                    st.rerun()

    with tab_nueva:
        st.subheader("➕ Registrar Nueva Sucursal")
        with st.form("form_nueva_sucursal"):
            nc1, nc2 = st.columns(2)
            with nc1:
                new_nombre = st.text_input("Nombre de la sucursal *", placeholder="Ej: Sucursal Norte")
                new_dir    = st.text_input("Dirección *", placeholder="Ej: Calle 27 de Febrero #45, Santiago")
            with nc2:
                new_tel    = st.text_input("Teléfono", placeholder="809-000-0000")
                new_encarg = st.text_input("Encargado / Gerente")
            new_obs = st.text_area("Observaciones")

            if st.form_submit_button("🏢 Crear Sucursal", type="primary", use_container_width=True):
                if not new_nombre.strip():
                    st.error("El nombre es obligatorio.")
                elif not new_dir.strip():
                    st.error("La dirección es obligatoria.")
                else:
                    payload_suc = {
                        "empresa_id": obtener_tenant_actual(),
                        "nombre": new_nombre.strip(),
                        "direccion": new_dir.strip(),
                        "telefono": new_tel.strip(),
                        "encargado": new_encarg.strip(),
                        "activa": True,
                        "observacion": new_obs.strip(),
                    }
                    try:
                        resp_ins = supabase.table("sucursales").insert(payload_suc).execute()
                        if resp_ins.data:
                            st.success(f"✅ Sucursal **{new_nombre}** creada exitosamente.")
                            st.rerun()
                        else:
                            st.error("No se pudo crear. Verifica que la tabla 'sucursales' existe en Supabase.")
                    except Exception as e:
                        st.error(f"Error: {e}")

        with st.expander("🔧 SQL para crear la tabla sucursales en Supabase"):
            st.code("""
CREATE TABLE IF NOT EXISTS sucursales (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  empresa_id text NOT NULL,
  nombre text NOT NULL,
  direccion text,
  telefono text,
  encargado text,
  activa boolean DEFAULT true,
  observacion text,
  created_at timestamptz DEFAULT now()
);
ALTER TABLE sucursales ENABLE ROW LEVEL SECURITY;
CREATE POLICY "tenant_sucursales" ON sucursales
  USING (empresa_id = current_setting('app.empresa_id', true));
-- Campo opcional en ventas:
ALTER TABLE ventas ADD COLUMN IF NOT EXISTS sucursal_nombre text;
""", language="sql")

    with tab_comparativo:
        st.subheader("📊 Comparativo de Ventas por Sucursal")
        if df_suc.empty:
            st.info("Registra al menos 2 sucursales para ver el comparativo.")
        else:
            desde_cmp, hasta_cmp = selector_fechas_universal("suc_comparativo")
            df_ventas = _filtrar_periodo_df(_df_actual("ventas"), desde_cmp, hasta_cmp)

            if df_ventas.empty:
                st.info("No hay ventas en el período seleccionado.")
            elif "sucursal_nombre" not in df_ventas.columns:
                st.info("Las ventas no tienen campo 'sucursal_nombre'. Agrega la columna a ventas (ver SQL) y registra ventas por sucursal para ver este comparativo.")
            else:
                df_con_suc = df_ventas[df_ventas["sucursal_nombre"].fillna("").astype(str).str.strip() != ""]
                if df_con_suc.empty:
                    st.info("Aún no hay ventas con sucursal asignada.")
                else:
                    resumen_suc = (
                        df_con_suc.groupby("sucursal_nombre")
                        .agg(Ventas=("total", "count"), Total=("total", "sum"), Promedio=("total", "mean"))
                        .reset_index()
                        .sort_values("Total", ascending=False)
                    )
                    ms1, ms2, ms3 = st.columns(3)
                    ms1.metric("Sucursales activas", len(resumen_suc))
                    ms2.metric("Total período", f"RD$ {resumen_suc['Total'].sum():,.2f}")
                    ms3.metric("Mejor sucursal", resumen_suc.iloc[0]["sucursal_nombre"])

                    disp = resumen_suc.copy()
                    disp["Total"]    = disp["Total"].apply(lambda x: f"RD$ {x:,.2f}")
                    disp["Promedio"] = disp["Promedio"].apply(lambda x: f"RD$ {x:,.2f}")
                    disp.columns = ["Sucursal", "N° Ventas", "Total Ventas", "Ticket Promedio"]
                    st.dataframe(disp, use_container_width=True, hide_index=True)

                    fig_suc = px.bar(resumen_suc, x="sucursal_nombre", y="Total",
                                     title="Ventas por Sucursal",
                                     color="sucursal_nombre",
                                     color_discrete_sequence=px.colors.qualitative.Set2,
                                     text_auto=True)
                    fig_suc.update_layout(showlegend=False, height=350)
                    st.plotly_chart(fig_suc, use_container_width=True)
                    descargar_archivos(resumen_suc, "comparativo_sucursales")
