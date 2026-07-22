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

def render_dashboard():
    st.title("📊 Dashboard PRO")

    desde, hasta = rango_fechas_ui("dash")

    ventas_df = obtener_ventas_periodo_actualizadas(desde, hasta)
    compras_df = filtrar_por_fechas(DATA["compras"], desde, hasta)
    gastos_df = filtrar_por_fechas(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)

    ventas_tot = suma_col(ventas_df, "total")
    compras_tot = suma_col(compras_df, "monto")
    gastos_fijos, gastos_variables = obtener_gastos_fijos_variables(DATA["gastos"], desde, hasta)
    empleados_fijos = obtener_empleados_fijos_periodo(DATA["empleados"], desde, hasta)
    empleados_variables = obtener_empleados_variables_periodo(DATA["gastos"], desde, hasta)
    perdidas_tot = suma_col(perdidas_df, "valor")
    retiros_tot = suma_col(dueno_df, "monto")
    total_inventario_dinero = calcular_total_dinero_inventario()

    pagos_empleados_debug = filtrar_por_fechas(leer_pagos_empleados_actualizados(), desde, hasta) if "leer_pagos_empleados_actualizados" in globals() else DATA.get("adelantos_empleados", pd.DataFrame()).copy()
    pagos_empleados_tot = suma_col(pagos_empleados_debug, "monto")

    utilidad_bruta_manual = st.number_input("Utilidad bruta manual / ajuste", min_value=0.0, step=1.0, key="dash_utilidad_bruta_manual")
    base_utilidad = calcular_utilidad_neta_operativa_periodo(desde, hasta, utilidad_bruta_manual)

    utilidad_bruta_ventas = base_utilidad["utilidad_bruta_ventas"]
    utilidad_bruta = base_utilidad["utilidad_bruta_total"]
    utilidad_neta = base_utilidad["utilidad_neta"]
    utilidad_distribuible = base_utilidad["utilidad_distribuible"]

    # Primero intenta leer la distribución guardada para este mismo periodo.
    # Si existe, el Dashboard muestra exactamente lo guardado en Distribución Beneficios.
    dist_guardada = obtener_distribucion_guardada_periodo(desde, hasta) if "obtener_distribucion_guardada_periodo" in globals() else None

    if dist_guardada:
        porcentaje_gerente_dash = float(limpiar_numero(dist_guardada.get("porcentaje_gerente")) or 35.0)
        porcentaje_dueno_dash = float(limpiar_numero(dist_guardada.get("porcentaje_duena")) or (100.0 - porcentaje_gerente_dash))
        dueno_65 = float(limpiar_numero(dist_guardada.get("monto_duena_calculado")) or 0)
        gerente_35 = float(limpiar_numero(dist_guardada.get("monto_gerente_calculado")) or 0)
        retiros_tot = float(limpiar_numero(dist_guardada.get("gastos_duena_periodo")) or retiros_tot)
        saldo_dueno_final = float(limpiar_numero(dist_guardada.get("disponible_duena")) or (dueno_65 - retiros_tot))
        saldo_gerente_final = gerente_35
        pago_dueno_dash = float(limpiar_numero(dist_guardada.get("pago_duena")) or 0)
        reinversion_dueno_dash = float(limpiar_numero(dist_guardada.get("reinversion_duena")) or 0)
        pendiente_dueno_dash = float(limpiar_numero(dist_guardada.get("pendiente_duena")) or 0)
        pago_gerente_dash = float(limpiar_numero(dist_guardada.get("pago_gerente")) or 0)
        pendiente_gerente_dash = float(limpiar_numero(dist_guardada.get("pendiente_gerente")) or 0)
        fuente_distribucion_dash = "Distribución guardada"
    else:
        # Si no hay distribución guardada, se muestra cálculo preliminar.
        # Si hay pérdida, NO se reparte pérdida. Gerente y dueño quedan en cero.
        porcentaje_gerente_dash = 35.0
        porcentaje_dueno_dash = 100.0 - porcentaje_gerente_dash
        dueno_65 = utilidad_distribuible * (porcentaje_dueno_dash / 100)
        gerente_35 = utilidad_distribuible * (porcentaje_gerente_dash / 100)

        # El retiro/gasto del dueño solo se descuenta de la parte del dueño.
        saldo_dueno_final = dueno_65 - retiros_tot
        saldo_gerente_final = gerente_35
        pago_dueno_dash = 0.0
        reinversion_dueno_dash = max(saldo_dueno_final, 0)
        pendiente_dueno_dash = 0.0
        pago_gerente_dash = 0.0
        pendiente_gerente_dash = gerente_35
        fuente_distribucion_dash = "Cálculo preliminar"

    st.markdown("### 💼 Resumen general")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Ventas", f"RD$ {ventas_tot:,.2f}")
    a2.metric("Compras", f"RD$ {compras_tot:,.2f}")
    a3.metric("Pérdidas", f"RD$ {perdidas_tot:,.2f}")
    a4.metric("Total dinero en inventario", f"RD$ {total_inventario_dinero:,.2f}")

    # 🚨 ALERTAS DE STOCK BAJO (BEBIDAS Y PRODUCTOS)
    productos_alert_df = DATA["productos"].copy()
    if not productos_alert_df.empty:
        if "activo" in productos_alert_df.columns:
            productos_alert_df = productos_alert_df[productos_alert_df["activo"] == True]
        bajo_stock = productos_alert_df[productos_alert_df["stock"] <= 10]
        if not bajo_stock.empty:
            with st.expander(f"🚨 Alerta: Hay {len(bajo_stock)} productos con stock bajo (≤ 10 unidades)", expanded=True):
                st.caption("Los siguientes productos y bebidas están próximos a agotarse. Asegure reabastecerlos a tiempo.")
                st.dataframe(
                    bajo_stock[["codigo", "nombre", "categoria", "stock"]].sort_values(by="stock"),
                    use_container_width=True
                )

    st.markdown("### 💸 Gastos y pagos")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Gastos fijos", f"RD$ {gastos_fijos:,.2f}")
    b2.metric("Gastos variables", f"RD$ {gastos_variables:,.2f}")
    b3.metric("Empleados fijos pagados", f"RD$ {empleados_fijos:,.2f}")
    b4.metric("Empleados variables pagados", f"RD$ {empleados_variables:,.2f}")

    with st.expander("🔎 Ver pagos de empleados tomados para Dashboard", expanded=False):
        if pagos_empleados_debug.empty:
            st.info("No hay pagos de empleados en este rango.")
        else:
            st.dataframe(pagos_empleados_debug, use_container_width=True)

    st.markdown("### 📊 Utilidad y reparto")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Utilidad bruta ventas", f"RD$ {utilidad_bruta_ventas:,.2f}")
    c2.metric("Utilidad bruta total", f"RD$ {utilidad_bruta:,.2f}")
    c3.metric("Utilidad neta", f"RD$ {utilidad_neta:,.2f}")
    c4.metric("Ajuste manual utilidad", f"RD$ {utilidad_bruta_manual:,.2f}")

    st.markdown("### 👥 Reparto dueño / gerente")
    st.caption(f"Fuente del reparto: {fuente_distribucion_dash}. Gerente {porcentaje_gerente_dash:.2f}% | Dueño {porcentaje_dueno_dash:.2f}%")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Parte del dueño", f"RD$ {dueno_65:,.2f}")
    d2.metric("Gastos/retiros dueño", f"RD$ {retiros_tot:,.2f}")
    d3.metric("Disponible dueño", f"RD$ {saldo_dueno_final:,.2f}")
    d4.metric("Beneficio gerente", f"RD$ {saldo_gerente_final:,.2f}")

    if utilidad_neta <= 0:
        st.warning("Este período cerró en pérdida. No hay utilidad distribuible para gerente ni dueño.")

    if dist_guardada:
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Pago dueño", f"RD$ {pago_dueno_dash:,.2f}")
        e2.metric("Reinversión dueño", f"RD$ {reinversion_dueno_dash:,.2f}")
        e3.metric("Pago gerente", f"RD$ {pago_gerente_dash:,.2f}")
        e4.metric("Pendiente gerente", f"RD$ {pendiente_gerente_dash:,.2f}")
    else:
        st.info("Este período todavía no tiene una distribución guardada. El Dashboard muestra un cálculo preliminar. Para fijar el porcentaje, guarda la distribución en el módulo Distribución Beneficios.")

    st.caption("Los retiros/gastos del dueño solo se descuentan de la parte del dueño. No afectan el beneficio del gerente.")

    import plotly.graph_objects as go
    import plotly.express as px

    st.markdown("### 📈 Gráficos Ejecutivos")
    
    tab_tendencia, tab_gastos, tab_utilidad, tab_ranking_productos = st.tabs(["📉 Tendencia Mensual", "🥧 Desglose de Gastos", "📊 Utilidad", "🏆 Top Ventas (Bebidas)"])
    
    with tab_tendencia:
        st.caption("Comparativa de Ingresos Totales vs Egresos Totales por mes.")
        # Preparar datos de tendencia
        v_graf = agrupar_mensual(ventas_df, "total") if not ventas_df.empty else pd.DataFrame(columns=["mes", "valor"])
        v_graf["tipo"] = "Ingresos (Ventas)"
        
        # Agrupar todos los egresos para que sea más fácil de entender
        egresos_totales_df = pd.concat([
            compras_df[["fecha", "monto"]].rename(columns={"monto": "valor"}) if not compras_df.empty else pd.DataFrame(columns=["fecha", "valor"]),
            gastos_df[["fecha", "monto"]].rename(columns={"monto": "valor"}) if not gastos_df.empty else pd.DataFrame(columns=["fecha", "valor"]),
            perdidas_df[["fecha", "valor"]] if not perdidas_df.empty else pd.DataFrame(columns=["fecha", "valor"])
        ], ignore_index=True)
        
        e_graf = agrupar_mensual(egresos_totales_df, "valor") if not egresos_totales_df.empty else pd.DataFrame(columns=["mes", "valor"])
        e_graf["tipo"] = "Egresos (Compras + Gastos + Pérdidas)"
        
        tendencia_df = pd.concat([v_graf, e_graf], ignore_index=True)
        if not tendencia_df.empty:
            fig_tendencia = px.bar(
                tendencia_df, 
                x="mes", y="valor", color="tipo", 
                barmode='group',
                text_auto='.2s',
                title="Ingresos vs Egresos por Mes",
                labels={"valor": "Monto (RD$)", "mes": "Mes", "tipo": "Concepto"},
                color_discrete_map={
                    "Ingresos (Ventas)": "#28a745",
                    "Egresos (Compras + Gastos + Pérdidas)": "#dc3545"
                }
            )
            fig_tendencia.update_layout(hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_tendencia, use_container_width=True)
        else:
            st.info("No hay datos suficientes para graficar tendencias.")

    with tab_gastos:
        st.caption("Proporción de todo el dinero que se saca de la ganancia bruta.")
        gastos_data = {
            "Categoría": ["Gastos Fijos", "Gastos Variables", "Nómina de Empleados", "Pérdida de Mercancía"],
            "Monto": [gastos_fijos, gastos_variables, (empleados_fijos + empleados_variables), perdidas_tot]
        }
        df_pie = pd.DataFrame(gastos_data)
        df_pie = df_pie[df_pie["Monto"] > 0]
        
        if not df_pie.empty:
            fig_pie = px.pie(
                df_pie, values="Monto", names="Categoría", 
                title="Desglose de Gastos y Pérdidas",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No hay gastos registrados en este período.")

    with tab_utilidad:
        st.caption("Comparación de Utilidad Bruta vs Utilidad Neta.")
        utilidad_data = {
            "Métrica": ["Ventas Totales", "Utilidad Bruta", "Utilidad Neta"],
            "Monto": [ventas_tot, utilidad_bruta, utilidad_neta]
        }
        df_util = pd.DataFrame(utilidad_data)
        
        fig_bar = px.bar(
            df_util, x="Métrica", y="Monto", 
            text_auto='.2s',
            title="Embudo de Utilidad",
            color="Métrica",
            color_discrete_map={
                "Ventas Totales": "#007bff",
                "Utilidad Bruta": "#28a745",
                "Utilidad Neta": "#6f42c1"
            }
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)

    with tab_ranking_productos:
        st.caption("Top 10 de productos/bebidas que más se venden y menos se venden en el rango seleccionado.")
        try:
            df_det = DATA.get("detalle_venta")
            if df_det is None or df_det.empty:
                df_det = leer_tabla("detalle_venta")
            
            if df_det is not None and not df_det.empty and not ventas_df.empty:
                venta_ids = ventas_df["id"].dropna().astype(str).tolist() if "id" in ventas_df.columns else []
                df_det_filtrado = df_det[df_det["venta_id"].astype(str).isin(venta_ids)]
                
                if not df_det_filtrado.empty:
                    ranking_df = df_det_filtrado.groupby("producto")["cantidad"].sum().reset_index()
                    ranking_df = ranking_df.rename(columns={"producto": "Producto", "cantidad": "Cantidad Vendida"})
                    
                    col_top1, col_top2 = st.columns(2)
                    
                    with col_top1:
                        st.write("🔥 **Las 10 Más Vendidas**")
                        top_mas = ranking_df.sort_values(by="Cantidad Vendida", ascending=False).head(10)
                        st.dataframe(top_mas, use_container_width=True)
                        fig_top_mas = px.bar(
                            top_mas, x="Cantidad Vendida", y="Producto", orientation='h',
                            title="Top 10 Productos Más Vendidos",
                            color="Cantidad Vendida", color_continuous_scale=px.colors.sequential.Greens
                        )
                        fig_top_mas.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_top_mas, use_container_width=True)
                        
                    with col_top2:
                        st.write("❄️ **Las 10 Menos Vendidas**")
                        top_menos = ranking_df.sort_values(by="Cantidad Vendida", ascending=True).head(10)
                        st.dataframe(top_menos, use_container_width=True)
                        fig_top_menos = px.bar(
                            top_menos, x="Cantidad Vendida", y="Producto", orientation='h',
                            title="Top 10 Productos Menos Vendidos",
                            color="Cantidad Vendida", color_continuous_scale=px.colors.sequential.Reds
                        )
                        fig_top_menos.update_layout(yaxis={'categoryorder':'total descending'})
                        st.plotly_chart(fig_top_menos, use_container_width=True)
                else:
                    st.info("No hay detalles de venta registrados para este período.")
            else:
                st.info("No hay transacciones de venta registradas para este período.")
        except Exception as err_rank:
            st.error(f"Error cargando ranking de ventas: {err_rank}")

# =========================================================
# PRODUCTOS
# =========================================================



def render_usuarios():
    st.title("👤 Usuarios")
    if not es_admin():
        st.error("No tienes permiso para entrar aquí. Solo el administrador de la empresa puede gestionar los usuarios.")
    else:
        df = DATA.get("usuarios", pd.DataFrame()).copy()
        tab_list, tab_create, tab_edit = st.tabs(["👥 Lista de Usuarios", "➕ Crear Usuario", "✏️ Editar / Eliminar Usuario"])
        
        with tab_list:
            if not df.empty:
                df_friendly = df.copy().rename(columns={
                    "usuario": "Usuario",
                    "nombre": "Nombre Completo",
                    "rol": "Rol",
                    "activo": "Activo"
                })
                cols_to_show = ["Usuario", "Nombre Completo", "Rol", "Activo"]
                cols_to_show = [c for c in cols_to_show if c in df_friendly.columns]
                st.dataframe(df_friendly[cols_to_show], use_container_width=True)
            else:
                st.info("No hay usuarios registrados para tu empresa.")
                
        with tab_create:
            c1, c2 = st.columns(2)
            with c1:
                n_usuario = st.text_input("Usuario de Acceso", key="new_usr_usuario")
                n_nombre = st.text_input("Nombre Completo", key="new_usr_nombre")
                n_clave = st.text_input("Contraseña / Clave", type="password", key="new_usr_clave")
                n_rol = st.selectbox("Rol", ["admin", "gerente", "supervisor", "cajero", "cajera"], key="new_usr_rol")
            with c2:
                n_activo = st.checkbox("Usuario Activo", value=True, key="new_usr_activo")
                
            st.markdown("### 🔑 Permisos del Empleado")
            permisos_crear = render_checkboxes_permisos("new_usr", defaults_dict={
                "puede_vender": True,
                "puede_abrir_caja": True,
                "puede_cerrar_caja": True,
                "puede_ver_ventas_propias": True
            })
                
            if st.button("🚀 Crear Usuario", key="btn_crear_usuario_new", use_container_width=True):
                user_clean = n_usuario.strip().lower()
                name_clean = n_nombre.strip()
                pass_clean = n_clave.strip()
                if not user_clean or not pass_clean or not name_clean:
                    st.error("Todos los campos obligatorios deben completarse.")
                else:
                    _tenant = obtener_tenant_actual()
                    # Validar límite de usuarios según el plan
                    try:
                        cfg_plan = supabase.table("configuracion_sistema").select("plan").eq("propietario", _tenant).limit(1).execute().data
                        plan_id_usr = (cfg_plan[0].get("plan") if cfg_plan else None) or "premium"
                    except Exception:
                        plan_id_usr = "premium"
                    
                    plan_info_usr = PLANES_AM.get(plan_id_usr, PLANES_AM["premium"])
                    limite_usrs = plan_info_usr["max_usuarios"]
                    usuarios_actuales = len(df) if not df.empty else 0
                    
                    if usuarios_actuales >= limite_usrs:
                        st.error(f"⚠️ Has alcanzado el límite de usuarios para tu Plan {plan_info_usr['nombre']} (Máximo {limite_usrs} usuarios). Por favor, actualiza tu plan o contacta al administrador A&M.")
                    else:
                        user_exist = supabase.table("usuarios").select("id").eq("usuario", user_clean).execute().data
                        if user_exist:
                            st.error(f"⚠️ El nombre de usuario '{user_clean}' ya está registrado. Por favor, elige uno diferente.")
                        else:
                            new_user_payload = {
                                "usuario": user_clean,
                                "nombre": name_clean,
                                "clave": hashear_clave(pass_clean),
                                "rol": n_rol,
                                "activo": n_activo,
                                "email": "" if _tenant == "global" else _tenant,
                                **permisos_crear
                            }
                            try:
                                supabase.table("usuarios").insert(new_user_payload).execute()
                                invalidar_cache_tabla("usuarios")
                                st.success(f"🎉 ¡Usuario '{user_clean}' creado con éxito!")
                                st.rerun()
                            except Exception as exc:
                                exc_str = str(exc)
                                if "23505" in exc_str or "unique constraint" in exc_str.lower():
                                    st.error(f"⚠️ El nombre de usuario '{user_clean}' ya está registrado. Por favor, elige uno diferente.")
                                else:
                                    st.error(f"Error al crear cuenta: {exc}")
                                
        with tab_edit:
            if df.empty:
                st.info("No hay usuarios registrados para gestionar.")
            else:
                user_options = []
                user_map = {}
                for _, u_row in df.iterrows():
                    lbl = f"{u_row['usuario']} ({u_row['nombre']})"
                    user_options.append(lbl)
                    user_map[lbl] = u_row
                
                selected_lbl = st.selectbox("Selecciona el usuario a gestionar:", user_options, key="select_user_to_edit")
                usr_sel = user_map[selected_lbl]
                
                # Sincronizar y forzar reconstrucción de widgets si cambia el usuario seleccionado
                if "prev_selected_user_id" not in st.session_state or st.session_state["prev_selected_user_id"] != usr_sel["id"]:
                    st.session_state["prev_selected_user_id"] = usr_sel["id"]
                    for k in list(st.session_state.keys()):
                        if k.startswith("edit_usr_") or k.startswith("edit_usr"):
                            st.session_state.pop(k, None)
                
                c1e, c2e = st.columns(2)
                with c1e:
                    edit_username = st.text_input("Usuario de Acceso", value=usr_sel["usuario"], key="edit_usr_user")
                    edit_name = st.text_input("Nombre Completo", value=usr_sel["nombre"], key="edit_usr_name")
                    edit_pass = st.text_input("Contraseña / Clave", type="password", value="", placeholder="Dejar en blanco para no cambiar", key="edit_usr_clave")
                    roles_list = ["admin", "gerente", "supervisor", "cajero", "cajera"]
                    try:
                        rol_idx = roles_list.index(usr_sel["rol"])
                    except ValueError:
                        rol_idx = 0
                    edit_rol = st.selectbox("Rol", roles_list, index=rol_idx, key="edit_usr_rol")
                with c2e:
                    edit_activo = st.checkbox("Usuario Activo", value=bool(usr_sel["activo"]), key="edit_usr_activo")
                
                st.markdown("### 🔑 Permisos del Empleado")
                permisos_editar = render_checkboxes_permisos("edit_usr", defaults_dict=dict(usr_sel))
                
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    if st.button("💾 Guardar Cambios de Usuario", key="btn_save_user_changes", use_container_width=True):
                        try:
                            new_username = edit_username.strip().lower()
                            if new_username != usr_sel["usuario"]:
                                user_exist = supabase.table("usuarios").select("id").eq("usuario", new_username).execute().data
                                if user_exist:
                                    st.error(f"⚠️ El nombre de usuario '{new_username}' ya está registrado. Por favor, elige uno diferente.")
                                    st.stop()
                            
                            payload = {
                                "usuario": new_username,
                                "nombre": edit_name.strip(),
                                "clave": hashear_clave(edit_pass.strip()) if edit_pass.strip() else usr_sel.get("clave"),
                                "rol": edit_rol,
                                "activo": edit_activo,
                                **permisos_editar
                            }
                            supabase.table("usuarios").update(payload).eq("id", usr_sel["id"]).execute()
                            invalidar_cache_tabla("usuarios")
                            st.success(f"🎉 ¡Usuario '{new_username}' actualizado con éxito!")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Error al actualizar usuario: {exc}")
                with c_btn2:
                    if st.button("🗑️ Eliminar Usuario", key="btn_delete_user_changes", use_container_width=True):
                        if usr_sel["usuario"] == nombre_usuario_actual():
                            st.error("⚠️ No puedes eliminar tu propio usuario con el que tienes sesión iniciada.")
                        else:
                            try:
                                supabase.table("usuarios").delete().eq("id", usr_sel["id"]).execute()
                                invalidar_cache_tabla("usuarios")
                                st.success(f"🗑️ Usuario '{usr_sel['usuario']}' eliminado correctamente.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Error al eliminar usuario: {exc}")

# =========================================================
# CONFIGURACION
# =========================================================


def render_configuracion():
    st.title("⚙️ Configuración del sistema")
    if not es_admin() and not tiene_permiso("puede_configurar"):
        st.error("No tienes permiso para entrar aquí.")
    else:
        cfg = obtener_configuracion()
        if not cfg:
            st.error("No se encontró la configuración del sistema.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                negocio_nombre = st.text_input("Nombre del negocio", value=str(cfg.get("negocio_nombre") or ""), help="Este nombre aparecerá en el encabezado de todas las facturas y tickets.")
                nombre_sistema = st.text_input("Nombre del sistema", value=str(cfg.get("nombre_sistema") or ""))
                propietario = st.text_input("Propietaria / responsable", value=str(cfg.get("propietario") or ""))
                slogan = st.text_input("Slogan", value=str(cfg.get("slogan") or ""))
            with c2:
                telefono = st.text_input("Teléfono del negocio", value=str(cfg.get("telefono") or ""), help="Aparecerá en las facturas impresas.")
                rnc = st.text_input("RNC del negocio (si aplica)", value=str(cfg.get("rnc") or ""), placeholder="Ej: 1-31-12345-6", help="El número de RNC aparecerá en el encabezado de cada factura impresa.")
                direccion = st.text_input("Dirección", value=str(cfg.get("direccion") or ""), help="Dirección física del negocio. Aparece en las facturas.")
                cierre_dia_operativo_hora = st.text_input("Hora cierre día operativo", value=str(cfg.get("cierre_dia_operativo_hora") or "03:00"))
                precios_itbis = st.checkbox("¿Precios de productos YA incluyen ITBIS?", value=bool(cfg.get("precios_incluyen_itbis", True)), help="Activa esto si tus precios de venta finales ya tienen el 18% incluido. El sistema desglosará el monto en la factura automáticamente sin sumarle más dinero al cliente.")
                # C-01: Recargo por tarjeta ELIMINADO — prohibido por Ley 288-05 (RD) y
                # reglas de red Visa/Mastercard. El costo de procesamiento es del comercio.
                st.info("ℹ️ **Recargo por tarjeta:** No aplica. Trasladar el costo de procesamiento de tarjeta al consumidor está prohibido por la Ley 288-05 y las normas de las redes de pago.", icon="🔒")
                recargo_tarjeta_pct = 0.0  # Siempre 0 — C-01
            if st.button("Guardar configuración", key="btn_guardar_cfg"):
                actualizar("configuracion_sistema", cfg["id"], {"negocio_nombre": negocio_nombre, "nombre_sistema": nombre_sistema, "propietario": propietario, "slogan": slogan, "telefono": telefono, "rnc": rnc, "direccion": direccion, "recargo_tarjeta_pct": 0.0, "cierre_dia_operativo_hora": cierre_dia_operativo_hora, "precios_incluyen_itbis": precios_itbis})
                _obtener_configuracion_interna.clear()
                st.success("✅ Configuración guardada correctamente.")
                st.rerun()
            st.subheader("Logo")
            logo_file = st.file_uploader("Sube logo", type=["png", "jpg", "jpeg", "webp"], key="cfg_logo")
            if logo_file is not None and st.button("Guardar logo", key="btn_guardar_logo"):
                if guardar_logo_en_configuracion(logo_file.getvalue(), logo_file.type or "image/png"):
                    st.success("Logo guardado.")
                    st.rerun()
            if cfg.get("logo_url"):
                st.image(cfg.get("logo_url"), width=220)

            st.markdown("---")
            # FASE 5: Configuración de NCF (DGII)
            st.subheader("🏛️ Gestión de Secuencias DGII (NCF)")
            st.caption("Administra los bloques de comprobantes fiscales autorizados por la DGII para esta empresa.")
            
            try:
                sec_resp = supabase.table("secuencia_ncf").select("*").eq("empresa_id", obtener_tenant_actual()).execute()
                df_sec = pd.DataFrame(sec_resp.data or [])
                if not df_sec.empty:
                    st.dataframe(df_sec[["tipo_comprobante", "secuencia_actual", "secuencia_maxima", "fecha_vencimiento", "estado"]], use_container_width=True)
                else:
                    st.info("No hay secuencias registradas actualmente.")
            except Exception as e:
                st.warning(f"Error cargando secuencias: {e}")

            with st.expander("➕ Añadir nuevo bloque de NCF", expanded=False):
                col_n1, col_n2 = st.columns(2)
                with col_n1:
                    n_tipo = st.selectbox("Tipo de Comprobante", ["E31 (Crédito Fiscal Electrónico)", "E32 (Consumo Electrónico)", "B01 (Crédito Fiscal)", "B02 (Consumo)", "B04 (Nota de Crédito)"], key="ncf_tipo")
                    n_desde = st.number_input("Secuencia Inicial (Desde)", min_value=1, step=1, key="ncf_desde")
                with col_n2:
                    n_venc = st.date_input("Fecha de Vencimiento", value=date.today() + timedelta(days=365), key="ncf_venc")
                    n_hasta = st.number_input("Secuencia Máxima (Hasta)", min_value=1, step=1, key="ncf_hasta")
                
                if st.button("Registrar Secuencia", key="btn_guardar_ncf"):
                    tipo_str = n_tipo.split(" ")[0]
                    try:
                        # Desactivar secuencias previas del mismo tipo
                        supabase.table("secuencia_ncf").update({"estado": "agotado"}).eq("empresa_id", obtener_tenant_actual()).eq("tipo_comprobante", tipo_str).eq("estado", "activo").execute()
                        
                        # Crear nueva secuencia
                        supabase.table("secuencia_ncf").insert({
                            "empresa_id": obtener_tenant_actual(),
                            "tipo_comprobante": tipo_str,
                            "secuencia_actual": int(n_desde),
                            "secuencia_maxima": int(n_hasta),
                            "fecha_vencimiento": str(n_venc),
                            "estado": "activo"
                        }).execute()
                        st.success(f"✅ Secuencia {tipo_str} activada correctamente.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error guardando secuencia: {exc}")

            st.markdown("---")
            st.subheader("🧑‍💼 Gestión de Empleados y Permisos")
            st.caption("Crea nuevos usuarios para tus empleados y controla con precisión a qué pantallas y acciones tienen acceso.")
            
            # Fetch users
            usuarios_resp = supabase.table("usuarios").select("*").execute()
            usuarios_data = usuarios_resp.data or []
            
            if usuarios_data:
                df_usuarios = pd.DataFrame(usuarios_data)
                st.dataframe(df_usuarios[["usuario", "nombre", "rol", "activo"]], use_container_width=True)
                
                # Edit / Delete existing user
                user_names = [f"{u['usuario']} | {u['nombre']}" for u in usuarios_data]
                user_sel = st.selectbox("Seleccione el Empleado a Modificar", user_names, key="emp_modify_sel")
                
                selected_user = next(u for u in usuarios_data if f"{u['usuario']} | {u['nombre']}" == user_sel)
                
                st.write(f"**Editar Permisos para {selected_user['nombre']}:**")
                
                col_e1, col_e2 = st.columns(2)
                e_nombre = col_e1.text_input("Nombre Real", value=str(selected_user.get("nombre") or ""), key="edit_emp_nombre")
                e_clave = col_e2.text_input("Cambiar Clave", type="password", value="", placeholder="Dejar en blanco para no cambiar", key="edit_emp_clave")
                e_rol = col_e1.selectbox("Rol", ["cajera", "gerente", "admin"], index=["cajera", "gerente", "admin"].index(selected_user.get("rol", "cajera")), key="edit_emp_rol")
                e_activo = col_e2.checkbox("Usuario Activo", value=bool(selected_user.get("activo", True)), key="edit_emp_activo")
                
                st.markdown("**Permisos Específicos de Acceso:**")
                permisos_emp = render_checkboxes_permisos("edit_emp", defaults_dict=dict(selected_user))
                
                col_btn = st.columns(2)
                if col_btn[0].button("💾 Guardar Permisos y Cambios", key="btn_save_emp_permissions", use_container_width=True):
                    update_data = {
                        "nombre": e_nombre,
                        "rol": e_rol,
                        "activo": e_activo,
                        **permisos_emp
                    }
                    if e_clave.strip():
                        update_data["clave"] = hashear_clave(e_clave.strip())
                    if actualizar("usuarios", selected_user["id"], update_data):
                        st.success(f"¡Permisos de {selected_user['usuario']} actualizados con éxito!")
                        limpiar_cache_datos()
                        st.rerun()
                        
                if col_btn[1].button("🗑️ Eliminar Cuenta de Empleado", key="btn_delete_emp_account", use_container_width=True):
                    if eliminar("usuarios", selected_user["id"]):
                        st.success(f"Cuenta de {selected_user['usuario']} eliminada.")
                        limpiar_cache_datos()
                        st.rerun()
            else:
                st.info("No hay usuarios registrados aparte del administrador maestro.")
            
            st.markdown("---")
            st.subheader("➕ Registrar Nuevo Empleado")
            with st.expander("✨ Haz clic para crear una nueva cuenta de empleado", expanded=False):
                col_n1, col_n2 = st.columns(2)
                n_usuario = col_n1.text_input("Usuario de Acceso (ej. maria123)", key="new_emp_user")
                n_nombre = col_n2.text_input("Nombre Completo (ej. María Delgado)", key="new_emp_name")
                n_clave = col_n1.text_input("Clave Inicial", type="password", key="new_emp_pass")
                n_rol = col_n2.selectbox("Rol Asignado", ["cajera", "gerente", "admin"], key="new_emp_role")
                
                st.write("")
                if st.button("🚀 Crear Cuenta de Empleado", key="btn_create_new_employee", use_container_width=True):
                    if not n_usuario or not n_nombre or not n_clave:
                        st.error("Por favor completa todos los campos del formulario.")
                    else:
                        current_tenant = obtener_tenant_actual()
                        new_user_payload = {
                            "usuario": n_usuario.strip().lower(),
                            "nombre": n_nombre.strip(),
                            "clave": hashear_clave(n_clave.strip()),
                            "rol": n_rol,
                            "activo": True,
                            "email": current_tenant if current_tenant != "global" else "",
                            "puede_vender": n_rol in ["cajera", "gerente", "admin"],
                            "puede_ver_reportes": n_rol in ["gerente", "admin"],
                            "puede_configurar": n_rol == "admin",
                            "puede_registrar_compras": n_rol in ["gerente", "admin"],
                            "puede_registrar_gastos": n_rol in ["gerente", "admin"],
                            "puede_editar_ventas": n_rol in ["gerente", "admin"],
                            "puede_eliminar": n_rol == "admin",
                            "puede_anular": n_rol in ["gerente", "admin"]
                        }
                        try:
                            # Verificar si ya existe el usuario antes de intentar insertarlo
                            user_exists_check = supabase.table("usuarios").select("id").eq("usuario", n_usuario.strip().lower()).execute().data
                            if user_exists_check:
                                st.error(f"⚠️ El nombre de usuario '{n_usuario}' ya está registrado. Por favor, elige uno diferente.")
                            else:
                                supabase.table("usuarios").insert(new_user_payload).execute()
                                st.success(f"¡Cuenta de empleado '{n_usuario}' creada exitosamente!")
                                limpiar_cache_datos()
                                st.rerun()
                        except Exception as exc:
                            exc_str = str(exc)
                            if "23505" in exc_str or "unique constraint" in exc_str.lower():
                                st.error(f"⚠️ El nombre de usuario '{n_usuario}' ya está registrado. Por favor, elige uno diferente.")
                            else:
                                st.error(f"Error al crear cuenta: {exc}")


# =========================================================
# FASE 4 — PANEL SUPER-ADMIN: GESTIÓN DE EMPRESAS
# =========================================================


def render_mi_perfil():
    st.title("🔒 Mi Perfil y Suscripción")
    user = usuario_sesion()
    if not user:
        st.error("No hay sesión activa.")
        return

    cfg = obtener_configuracion()
    nombre_negocio = cfg.get("negocio_nombre") or "Sistema A&M"

    # ── Tabs: Perfil | Suscripción ──────────────────────────────────────
    tab_perfil, tab_plan = st.tabs(["👤 Mi Perfil", "📋 Plan y Suscripción"])

    with tab_perfil:
        user_id = user.get("id")
        rol_actual = str(user.get("rol") or "cajero").lower()

        ICONOS_ROL = {
            "admin": "👑", "propietario": "🏢", "gerente": "📊",
            "contador": "📋", "cajero": "🛒"
        }
        icono_rol = ICONOS_ROL.get(rol_actual, "👤")

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:16px;padding:20px;margin-bottom:16px;border:1px solid rgba(212,175,55,0.3);">
          <div style="font-size:48px;text-align:center;">{icono_rol}</div>
          <div style="text-align:center;color:#fff;font-size:20px;font-weight:700;">{user.get('nombre') or user.get('usuario') or '—'}</div>
          <div style="text-align:center;color:#aaa;font-size:13px;margin-top:4px;">Rol: <b style="color:#d4af37">{rol_actual.upper()}</b> | {nombre_negocio}</div>
        </div>
        """, unsafe_allow_html=True)

        if not user_id or str(user_id).strip() == "None":
            st.warning("⚠️ Conectado con cuenta maestra temporal ('admin'). Esta cuenta está en secrets.toml y no se puede editar aquí.")
            st.stop()

        if not es_admin():
            st.info("ℹ️ Tu perfil es administrado por el administrador del sistema. Solicítale cambios si los necesitas.")

        with st.form("form_mi_perfil"):
            c1, c2 = st.columns(2)
            with c1:
                new_nombre = st.text_input("Nombre Completo", value=str(user.get("nombre") or ""))
                new_usuario = st.text_input("Usuario de acceso", value=str(user.get("usuario") or ""), disabled=not es_admin())
            with c2:
                new_clave = st.text_input("Nueva Contraseña", value="", type="password", disabled=not es_admin(), placeholder="Dejar en blanco para no cambiar")
                st.text_input("Rol asignado", value=rol_actual.upper(), disabled=True)

            if st.form_submit_button("💾 Guardar cambios", type="primary", use_container_width=True):
                usr_clean   = new_usuario.strip().lower()
                name_clean  = new_nombre.strip()
                clave_clean = new_clave.strip()

                if not name_clean:
                    st.error("El nombre no puede estar vacío.")
                else:
                    try:
                        existentes = supabase.table("usuarios").select("*").eq("usuario", usr_clean).execute().data or []
                        existe_otro = any(str(u.get("id")) != str(user_id) for u in existentes)
                    except Exception:
                        existe_otro = False

                    if existe_otro:
                        st.error(f"Ya existe un usuario con el nombre '{usr_clean}'.")
                    else:
                        if es_admin():
                            payload_upd = {"nombre": name_clean, "usuario": usr_clean}
                            if clave_clean:
                                payload_upd["clave"] = hashear_clave(clave_clean)
                        else:
                            payload_upd = {"nombre": name_clean}

                        if actualizar("usuarios", user_id, payload_upd):
                            user.update(payload_upd)
                            st.session_state["usuario_data"] = user
                            st.success("✅ Perfil actualizado correctamente.")
                            st.rerun()

    with tab_plan:
        st.subheader("📋 Plan Activo y Suscripción")

        # ── Leer datos del plan desde configuracion_sistema ──────────────
        plan_nombre     = str(cfg.get("plan") or cfg.get("plan_activo") or "Estándar").upper()
        fecha_venc_raw  = cfg.get("fecha_vencimiento") or cfg.get("vencimiento") or ""
        rnc_empresa     = str(cfg.get("rnc") or cfg.get("rnc_empresa") or "—")
        telefono_emp    = str(cfg.get("telefono") or "—")
        email_emp       = str(cfg.get("email") or cfg.get("correo") or "—")

        # Calcular días restantes
        dias_restantes = None
        venc_str = "No definida"
        if fecha_venc_raw:
            try:
                import re
                fecha_solo = str(fecha_venc_raw)[:10]
                from datetime import date as _date
                venc_date = _date.fromisoformat(fecha_solo)
                dias_restantes = (venc_date - _date.today()).days
                venc_str = venc_date.strftime("%d/%m/%Y")
            except Exception:
                venc_str = str(fecha_venc_raw)[:10]

        # Colores por estado
        if dias_restantes is None:
            color_plan = "#4caf50"
            estado_plan = "✅ Activo"
        elif dias_restantes > 30:
            color_plan = "#4caf50"
            estado_plan = f"✅ Activo — {dias_restantes} días restantes"
        elif dias_restantes > 0:
            color_plan = "#ff9800"
            estado_plan = f"⚠️ Por vencer — {dias_restantes} días"
        else:
            color_plan = "#f44336"
            estado_plan = f"❌ Vencido hace {abs(dias_restantes)} días"

        # Panel de plan
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0d0d0d,#1a2744);border-radius:16px;padding:24px;border:2px solid {color_plan}44;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div style="font-size:28px;font-weight:900;color:{color_plan};">PLAN {plan_nombre}</div>
              <div style="color:#aaa;font-size:13px;margin-top:4px;">{nombre_negocio} | RNC: {rnc_empresa}</div>
            </div>
            <div style="text-align:right;">
              <div style="color:{color_plan};font-weight:700;font-size:14px;">{estado_plan}</div>
              <div style="color:#888;font-size:12px;">Vence: {venc_str}</div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Métricas de uso actual ────────────────────────────────────────
        st.markdown("#### 📊 Uso Actual del Sistema")

        from datetime import date as _d2
        inicio_mes = _d2(_d2.today().year, _d2.today().month, 1)

        try:
            n_empleados = len(_df_actual("empleados"))
        except Exception:
            n_empleados = 0
        try:
            n_productos = len(_df_actual("productos"))
        except Exception:
            n_productos = 0
        try:
            df_ventas_mes = _filtrar_periodo_df(_df_actual("ventas"), inicio_mes, _d2.today())
            n_ventas_mes = len(df_ventas_mes)
            total_ventas_mes = float(df_ventas_mes["total"].sum()) if not df_ventas_mes.empty and "total" in df_ventas_mes.columns else 0.0
        except Exception:
            n_ventas_mes, total_ventas_mes = 0, 0.0
        try:
            n_usuarios = len(_df_actual("usuarios"))
        except Exception:
            n_usuarios = 0

        u1, u2, u3, u4 = st.columns(4)
        u1.metric("👥 Empleados", n_empleados)
        u2.metric("📦 Productos", n_productos)
        u3.metric("🛒 Ventas este mes", n_ventas_mes)
        u4.metric("💰 Facturado este mes", f"RD$ {total_ventas_mes:,.2f}")

        st.divider()

        # ── Módulos incluidos ─────────────────────────────────────────────
        st.markdown("#### ✅ Módulos Incluidos en tu Plan")

        MODULOS_SISTEMA = [
            ("🛒", "Punto de Venta (POS)", True),
            ("📦", "Inventario y Stock", True),
            ("💼", "Ventas y Compras", True),
            ("👥", "Clientes y Estado de Cuenta", True),
            ("💳", "Créditos y CxC", True),
            ("📋", "Notas de Crédito E34", True),
            ("🏛️", "Factura Gubernamental E45", True),
            ("📑", "Nómina TSS/ISR Legal", True),
            ("📊", "Reportes DGII 606/607/IT-1/IR-2", True),
            ("📒", "Libro Mayor", True),
            ("🔒", "Cierre de Período", True),
            ("📚", "Academia DGII", True),
            ("🤖", "Asistente Ayuda AIM", True),
            ("🏗️", "Activos Fijos", True),
            ("📈", "Distribución de Beneficios", True),
            ("🔮", "Predicciones IA", True),
            ("🏢", "Multi-Empresa (Super-Admin)", es_admin()),
        ]

        col_mod_a, col_mod_b = st.columns(2)
        mitad = len(MODULOS_SISTEMA) // 2
        for i, (icono, nombre_mod, incluido) in enumerate(MODULOS_SISTEMA):
            col = col_mod_a if i < mitad else col_mod_b
            badge = "✅" if incluido else "🔒"
            col.markdown(f"{badge} {icono} {nombre_mod}")

        st.divider()

        # ── Info de contacto y renovación ─────────────────────────────────
        st.markdown("#### 📞 Información de la Empresa")
        ic1, ic2, ic3 = st.columns(3)
        ic1.info(f"📧 **Email:** {email_emp}")
        ic2.info(f"📱 **Teléfono:** {telefono_emp}")
        ic3.info(f"🪪 **RNC:** {rnc_empresa}")

        if dias_restantes is not None and dias_restantes <= 30:
            st.warning(f"""
⚠️ **Tu suscripción vence pronto ({venc_str}).**
Para renovar contacta a tu proveedor del sistema o al administrador.
            """)






