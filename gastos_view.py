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

def render_catalogo_gastos():
    st.title("🗂️ Catálogo de Gastos")

    with st.expander("➕ Agregar al catálogo", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="cat_nom")
            tipo = st.selectbox("Tipo", ["fijo", "variable"], key="cat_tipo")
            categoria = st.text_input("Categoría", key="cat_cat")
            activo = st.checkbox("Activo", value=True, key="cat_activo")
        with c2:
            metodo_pago_default = st.selectbox("Método de pago default", ["efectivo", "transferencia", "tarjeta"], key="cat_met")
            impuesto_default = st.number_input("Impuesto default", min_value=0.0, step=1.0, key="cat_imp")
            descripcion_default = st.text_area("Descripción default", key="cat_desc")

        if st.button("Guardar en catálogo"):
            if insertar(
                "catalogo_gastos",
                {
                    "nombre": nombre,
                    "tipo": tipo,
                    "categoria": categoria,
                    "activo": activo,
                    "metodo_pago_default": metodo_pago_default,
                    "impuesto_default": float(impuesto_default),
                    "descripcion_default": descripcion_default,
                },
            ):
                st.success("Gasto guardado en catálogo.")
                st.rerun()

    df = DATA["catalogo_gastos"].copy()
    if not df.empty:
        txt = st.text_input("Buscar en catálogo", key="buscar_catalogo")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "catalogo_gastos")
        render_crud_generico("catalogo_gastos", df, "🛠️ Editar / eliminar catálogo de gastos")
    else:
        st.info("No hay catálogo de gastos.")





# =========================================================
# GASTOS
# =========================================================


def render_gastos():
    st.title("💸 Gastos")
    next_gasto_id = generar_codigo_secuencial("gastos")
    st.caption(f"Identificador del próximo gasto: **{next_gasto_id}**")

    catalogo = DATA["catalogo_gastos"].copy()
    if not catalogo.empty and "activo" in catalogo.columns:
        catalogo_activo = catalogo[catalogo["activo"] == True]
    else:
        catalogo_activo = catalogo

    with st.expander("➕ Registrar gasto", expanded=True):
        usar_catalogo = st.checkbox("Usar catálogo de gastos", value=True, key="usar_catalogo")
        gasto_catalogo = None
        if usar_catalogo and not catalogo_activo.empty and "nombre" in catalogo_activo.columns:
            nombres_cat = catalogo_activo["nombre"].astype(str).tolist()
            nombre_sel = st.selectbox("Selecciona gasto del catálogo", nombres_cat, key="gasto_cat_sel")
            gasto_catalogo = catalogo_activo[catalogo_activo["nombre"].astype(str) == nombre_sel].iloc[0]

        # Predicción inteligente
        cat_sug = ""
        tipo_sug = "variable"

        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="g_fecha")
            nombre = st.text_input("Nombre del gasto", value=str(gasto_catalogo["nombre"]) if gasto_catalogo is not None else "", key="g_nombre")
            
            if nombre:
                cat_sug, tipo_sug = predecir_categoria_y_tipo_gasto(nombre)
                
            default_cat = ""
            if gasto_catalogo is not None and "categoria" in gasto_catalogo.index:
                default_cat = str(gasto_catalogo["categoria"])
            elif nombre:
                default_cat = cat_sug

            default_tipo_idx = 1
            if gasto_catalogo is not None:
                default_tipo_idx = 0 if str(gasto_catalogo.get("tipo", "fijo")).lower() == "fijo" else 1
            elif nombre:
                default_tipo_idx = 0 if tipo_sug == "fijo" else 1

            tipo = st.selectbox(
                "Tipo",
                ["fijo", "variable"],
                index=default_tipo_idx,
                key="g_tipo",
            )
            categoria = st.text_input("Categoría", value=default_cat, key="g_categoria")
            if nombre and not usar_catalogo:
                st.markdown(f"🔮 *IA Sugirió: Categoría* **{cat_sug}** *| Tipo* **{tipo_sug.upper()}**")
            responsable = st.text_input("Quién creó el gasto", key="g_responsable")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="g_monto")
            default_metodo = "efectivo"
            if gasto_catalogo is not None:
                metodo_cat = str(gasto_catalogo.get("metodo_pago_default", "efectivo")).lower()
                if metodo_cat in ["efectivo", "transferencia", "tarjeta"]:
                    default_metodo = metodo_cat
            metodo_pago = st.selectbox("Método de pago", ["efectivo", "transferencia", "tarjeta"], index=["efectivo", "transferencia", "tarjeta"].index(default_metodo), key="g_metodo")
            cuenta = cuenta_por_metodo_pago(metodo_pago) if "cuenta_por_metodo_pago" in globals() else ""
            st.caption(f"Este gasto afectará: {cuenta}")
            impuesto = st.number_input("Impuesto", min_value=0.0, step=1.0, value=float(limpiar_numero(gasto_catalogo.get("impuesto_default")) or 0) if gasto_catalogo is not None else 0.0, key="g_impuesto")
            detalle = st.text_area("Detalle", value=str(gasto_catalogo.get("descripcion_default", "")) if gasto_catalogo is not None else "", key="g_detalle")

        guardar_catalogo_nuevo = st.checkbox("Guardar este gasto nuevo también en el catálogo", value=False, key="g_guardar_cat")

        if st.button("Guardar gasto"):
            if monto <= 0:
                st.error("No puedes guardar un gasto con monto 0.")
            elif not nombre:
                st.error("Debes indicar el nombre del gasto.")
            else:
                ok = insertar(
                    "gastos",
                    {
                        "fecha": str(fecha),
                        "nombre": nombre,
                        "tipo": tipo,
                        "categoria": categoria,
                        "monto": float(monto),
                        "metodo_pago": metodo_pago,
                        "cuenta": cuenta,
                        "impuesto": float(impuesto),
                        "detalle": detalle,
                        "responsable": responsable,
                    },
                )
                if ok and guardar_catalogo_nuevo and nombre:
                    existe = False
                    if not DATA["catalogo_gastos"].empty and "nombre" in DATA["catalogo_gastos"].columns:
                        existe = normalizar_texto(nombre) in DATA["catalogo_gastos"]["nombre"].astype(str).apply(normalizar_texto).tolist()
                    if not existe:
                        insertar(
                            "catalogo_gastos",
                            {
                                "nombre": nombre,
                                "tipo": tipo,
                                "categoria": categoria,
                                "activo": True,
                                "metodo_pago_default": metodo_pago,
                                "impuesto_default": float(impuesto),
                                "descripcion_default": detalle,
                            },
                        )
                if ok:
                    st.success("Gasto guardado.")
                    st.rerun()

    df = DATA["gastos"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("gastos")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar gasto", key="buscar_gastos")
        df = buscar_df(df, txt)
        columnas_gastos = [c for c in ["fecha", "nombre", "tipo", "categoria", "monto", "metodo_pago", "cuenta", "detalle", "responsable"] if c in df.columns]
        st.dataframe(df[columnas_gastos] if columnas_gastos else df, use_container_width=True)
        descargar_archivos(df[columnas_gastos] if columnas_gastos else df, "gastos")
        render_crud_generico("gastos", df, "🛠️ Editar / eliminar gastos")
    else:
        st.info("No hay gastos registrados.")


# =========================================================
# EMPLEADOS
# =========================================================


def render_gastos_dueno():
    st.title("👤 Gastos / Retiros del Dueño")

    with st.expander("➕ Registrar gasto del dueño", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="dueno_fecha")
            concepto = st.text_input("Concepto", key="dueno_concepto")
            metodo_pago = st.selectbox(
                "Método de pago",
                ["efectivo", "transferencia", "tarjeta", "mixto"],
                key="dueno_metodo_pago",
            )
            cuenta = cuenta_por_metodo_pago(metodo_pago) if "cuenta_por_metodo_pago" in globals() else ""
            if metodo_pago == "mixto":
                st.info("Para control exacto de Dinero Real, si el retiro fue mixto conviene registrarlo en dos partes: una en efectivo y otra en transferencia/tarjeta.")
            else:
                st.caption(f"Este retiro afectará: {cuenta}")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="dueno_monto")
            detalle = st.text_area("Detalle", key="dueno_detalle")

        if st.button("Guardar gasto dueño"):
            if insertar(
                "gastos_dueno",
                {
                    "fecha": str(fecha),
                    "concepto": concepto,
                    "monto": float(monto),
                    "detalle": detalle,
                    "metodo_pago": metodo_pago,
                    "cuenta": cuenta,
                    "tipo_movimiento": "retiro_dueño",
                },
            ):
                st.success("Gasto del dueño guardado.")
                st.rerun()

    df = DATA["gastos_dueno"].copy()
    if not df.empty:
        d1, d2 = rango_fechas_ui("dueno")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar gasto dueño", key="buscar_dueno")
        df = buscar_df(df, txt)
        columnas = [c for c in ["fecha", "concepto", "monto", "metodo_pago", "cuenta", "detalle", "tipo_movimiento"] if c in df.columns]
        st.dataframe(df[columnas] if columnas else df, use_container_width=True)
        descargar_archivos(df[columnas] if columnas else df, "gastos_dueno")
        render_crud_generico("gastos_dueno", df, "🛠️ Editar / eliminar gastos del dueño")
    else:
        st.info("No hay gastos del dueño registrados.")


# =========================================================
# CIERRE DE CAJA
# =========================================================


def render_perdidas():
    st.title("📉 Pérdidas de Mercancía")
    st.caption("Módulo de reporte, revisión y descargo de pérdidas de mercancía en inventario.")

    productos_lista = DATA["productos"]["nombre"].astype(str).tolist() if not DATA["productos"].empty and "nombre" in DATA["productos"].columns else []
    
    tab_reportar, tab_historial = st.tabs(["📝 Reportar Pérdida", "🛡️ Aprobación & Historial"])
    
    with tab_reportar:
        if not puede_reportar_perdidas():
            st.warning("No tienes permiso para reportar pérdidas de mercancía.")
        else:
            # Formulario de pérdidas interactivo sin st.form para permitir recarga y autocompletado en vivo
            st.markdown("### ➕ Formulario de Reporte de Pérdida")
            c1, c2 = st.columns(2)
            with c1:
                fecha = st.date_input("Fecha de la pérdida", value=date.today(), key="rep_fecha")
                hora = st.text_input("Hora (HH:MM)", value=datetime.now().strftime("%H:%M"), key="rep_hora")
                producto = st.selectbox("Producto", productos_lista, key="rep_prod") if productos_lista else st.text_input("Producto", key="rep_prod_txt")
                existencia_actual = obtener_existencia_desde_inventario(producto) if producto else 0.0
                st.number_input(
                    "Existencia actual en inventario (Informativo)",
                    value=float(existencia_actual),
                    step=1.0,
                    disabled=True,
                    key=f"rep_existencia_{normalizar_texto(producto)}"
                )
            with c2:
                cantidad = st.number_input("Cantidad perdida", min_value=0.0, step=1.0, key="rep_cant")
                costo_auto = obtener_costo_desde_inventario(producto) if producto else 0.0
                costo_unitario = st.number_input(
                    "Costo unitario",
                    min_value=0.0,
                    step=0.01,
                    value=float(costo_auto),
                    key=f"rep_costo_{normalizar_texto(producto)}"
                )
                tipo_perdida = st.selectbox("Tipo de pérdida", ["mercancia", "vencimiento", "rotura", "ajuste_mercancia", "otro"], key="rep_tipo")
                persona_involucrada = st.text_input("Persona involucrada (Cajera / Empleado)", key="rep_persona")
            
            observacion = st.text_area("Observación / Justificación detallada", key="rep_obs")
            
            if st.button("📋 Reportar pérdida", use_container_width=True, key="btn_reportar_perdida_submit"):
                if not limpiar_texto(producto):
                    st.error("Debes seleccionar un producto.")
                elif cantidad <= 0:
                    st.error("La cantidad perdida debe ser mayor que cero.")
                elif costo_unitario <= 0:
                    st.error("El costo unitario no puede ser cero.")
                else:
                    ok = registrar_perdida(
                        fecha_mov=fecha,
                        producto=producto,
                        cantidad=cantidad,
                        costo_unitario=costo_unitario,
                        tipo_perdida=tipo_perdida,
                        observacion=observacion,
                        estado="pendiente",
                        hora=hora,
                        reportado_por=nombre_usuario_actual(),
                        persona_involucrada=persona_involucrada
                    )
                    if ok:
                        st.success("Pérdida reportada correctamente. Queda en estado 'pendiente' para revisión de administración.")
                        st.rerun()

    with tab_historial:
        df = DATA["perdidas"].copy()
        
        # --- PANEL DE APROBACIÓN PARA ADMINS ---
        if puede_aprobar_perdidas() or puede_debitar_perdidas():
            st.markdown("### 🛡️ Panel de Revisión de Pérdidas Pendientes")
            
            if not df.empty and "estado" in df.columns:
                df_pendientes = df[df["estado"].isin(["pendiente", "en_investigacion"])].copy()
            else:
                df_pendientes = pd.DataFrame()
                
            if df_pendientes.empty:
                st.info("No hay pérdidas pendientes de revisión. ¡Buen trabajo!")
            else:
                opciones_rev = []
                mapa_rev = {}
                for _, r in df_pendientes.iterrows():
                    p_id = r.get("id") or r.get("identificación") or r.get("identificacion")
                    prod = r.get("producto", "")
                    cant = float(limpiar_numero(r.get("cantidad")) or 0)
                    fecha_r = r.get("fecha", "")
                    estado_r = r.get("estado", "pendiente")
                    lbl = f"ID: {p_id} | {prod} | Cant: {cant:,.0f} | Fecha: {fecha_r} | [{estado_r.upper()}]"
                    opciones_rev.append(lbl)
                    mapa_rev[lbl] = r
                    
                sel_rev = st.selectbox("Selecciona pérdida para revisar", opciones_rev, key="rev_sel_perdida")
                fila_rev = mapa_rev[sel_rev]
                
                rev_id = fila_rev.get("id") or fila_rev.get("identificación") or fila_rev.get("identificacion")
                rev_producto = limpiar_texto(fila_rev.get("producto"))
                rev_cantidad = float(limpiar_numero(fila_rev.get("cantidad")) or 0)
                rev_costo = float(limpiar_numero(fila_rev.get("costo_unitario")) or 0)
                rev_valor = float(limpiar_numero(fila_rev.get("valor")) or (rev_cantidad * rev_costo))
                rev_estado = fila_rev.get("estado", "pendiente")
                rev_fecha = fila_rev.get("fecha", "")
                rev_hora = fila_rev.get("hora", "") or "No especificada"
                rev_reportado = fila_rev.get("reportado_por", "") or "No especificado"
                rev_involucrado = fila_rev.get("persona_involucrada", "") or "No especificada"
                rev_obs = fila_rev.get("observacion", "") or ""
                
                # Tarjeta de detalles
                with st.container(border=True):
                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.markdown(f"**📦 Producto:** {rev_producto}")
                        st.markdown(f"**🔢 Cantidad:** {rev_cantidad:,.0f} uds.")
                        st.markdown(f"**💵 Valor:** RD$ {rev_valor:,.2f}")
                        st.markdown(f"**📅 Fecha y Hora:** {rev_fecha} a las {rev_hora}")
                    with col_d2:
                        st.markdown(f"**👤 Reportado por:** {rev_reportado}")
                        st.markdown(f"**👥 Persona Involucrada:** {rev_involucrado}")
                        st.markdown(f"**📝 Observación Empleado:** {rev_obs}")
                        st.markdown(f"**🔄 Estado Actual:** `{rev_estado.upper()}`")
                        
                obs_admin = st.text_area("Observación / Nota del Administrador", key=f"rev_obs_admin_{rev_id}")
                
                col_b1, col_b2, col_b3 = st.columns(3)
                with col_b1:
                    if st.button("🔍 Poner en investigación", key=f"btn_investigar_{rev_id}", use_container_width=True):
                        ok_up = actualizar("perdidas", rev_id, {
                            "estado": "en_investigacion",
                            "observacion_admin": obs_admin,
                            "revisado_por": nombre_usuario_actual(),
                            "fecha_revision": str(date.today()),
                            "decision_admin": "Puesta en investigación"
                        })
                        if ok_up:
                            st.success("La pérdida ha sido marcada 'En investigación'.")
                            st.rerun()
                            
                with col_b2:
                    if st.button("❌ Rechazar pérdida", key=f"btn_rechazar_{rev_id}", use_container_width=True):
                        ok_up = actualizar("perdidas", rev_id, {
                            "estado": "rechazada",
                            "observacion_admin": obs_admin,
                            "revisado_por": nombre_usuario_actual(),
                            "fecha_revision": str(date.today()),
                            "decision_admin": "Rechazada"
                        })
                        if ok_up:
                            st.success("La pérdida ha sido rechazada.")
                            st.rerun()
                            
                with col_b3:
                    if puede_debitar_perdidas():
                        if st.button("✅ Aprobar y descontar stock", key=f"btn_aprobar_debitar_{rev_id}", use_container_width=True):
                            existencia = obtener_existencia_desde_inventario(rev_producto)
                            if rev_cantidad > existencia:
                                st.error(f"Error: La existencia actual del producto ({existencia:,.0f}) es insuficiente para descontar {rev_cantidad:,.0f} uds.")
                            else:
                                nueva_existencia = max(existencia - rev_cantidad, 0.0)
                                fila_prod = get_producto_por_nombre(rev_producto)
                                precio = float(limpiar_numero(fila_prod.get("precio")) or 0) if fila_prod is not None else 0.0
                                
                                ok_stock = True
                                ok_inv = True
                                if fila_prod is not None:
                                    ok_stock = actualizar_stock_producto(rev_producto, nueva_existencia, date.today())
                                    ok_inv = upsert_inventario_actual(
                                        rev_producto,
                                        rev_costo,
                                        precio,
                                        nueva_existencia,
                                        date.today(),
                                        f"Descontado por aprobación de pérdida ID: {rev_id}"
                                    )
                                    
                                ok_up = actualizar("perdidas", rev_id, {
                                    "estado": "debitada",
                                    "observacion_admin": obs_admin,
                                    "revisado_por": nombre_usuario_actual(),
                                    "fecha_revision": str(date.today()),
                                    "decision_admin": "Aprobada y debitada del inventario"
                                })
                                if ok_stock and ok_inv and ok_up:
                                    st.success("Pérdida aprobada y descontada del inventario correctamente.")
                                    st.rerun()
                    else:
                        if st.button("✅ Aprobar pérdida", key=f"btn_aprobar_{rev_id}", use_container_width=True):
                            ok_up = actualizar("perdidas", rev_id, {
                                "estado": "aprobada",
                                "observacion_admin": obs_admin,
                                "revisado_por": nombre_usuario_actual(),
                                "fecha_revision": str(date.today()),
                                "decision_admin": "Aprobada (pendiente de debitar)"
                            })
                            if ok_up:
                                st.success("Pérdida aprobada. Queda pendiente de debitar stock por un usuario con ese permiso.")
                                st.rerun()

            st.markdown("---")

        # --- SECCIÓN APLICAR DESCUENTO A PÉRDIDAS PENDIENTES/APROBADAS ---
        if puede_debitar_perdidas():
            st.markdown("### 📉 Descontar del inventario una pérdida ya guardada/aprobada")
            if not df.empty and "estado" in df.columns:
                df_debitables = df[df["estado"].isin(["pendiente", "aprobada"])].copy()
            else:
                df_debitables = pd.DataFrame()
                
            if df_debitables.empty:
                st.info("No hay pérdidas pendientes de descontar stock en el inventario.")
            else:
                opciones_deb = []
                mapa_deb = {}
                for _, r in df_debitables.iterrows():
                    p_id = r.get("id") or r.get("identificación") or r.get("identificacion")
                    prod = r.get("producto", "")
                    cant = float(limpiar_numero(r.get("cantidad")) or 0)
                    costo = float(limpiar_numero(r.get("costo_unitario")) or 0)
                    fecha_r = r.get("fecha", "")
                    lbl = f"ID: {p_id} | {prod} | Cant: {cant:,.0f} | Costo: {costo:,.2f} | Fecha: {fecha_r}"
                    opciones_deb.append(lbl)
                    mapa_deb[lbl] = r
                    
                sel_deb = st.selectbox("Selecciona pérdida para descontar stock", opciones_deb, key="deb_sel_perdida")
                fila_deb = mapa_deb[sel_deb]
                
                deb_id = fila_deb.get("id") or fila_deb.get("identificación") or fila_deb.get("identificacion")
                deb_producto = limpiar_texto(fila_deb.get("producto"))
                deb_cantidad = float(limpiar_numero(fila_deb.get("cantidad")) or 0)
                deb_costo = float(limpiar_numero(fila_deb.get("costo_unitario")) or obtener_costo_desde_inventario(deb_producto) or 0)
                deb_existencia = obtener_existencia_desde_inventario(deb_producto)
                deb_nueva_existencia = max(deb_existencia - deb_cantidad, 0.0)
                
                cpa, cpb, cpc = st.columns(3)
                cpa.metric("Existencia actual", f"{deb_existencia:,.0f}")
                cpb.metric("Cantidad a descontar", f"{deb_cantidad:,.0f}")
                cpc.metric("Nueva existencia", f"{deb_nueva_existencia:,.0f}")
                
                if st.button("📉 Aplicar descuento al inventario", key=f"btn_debitar_directo_{deb_id}"):
                    if deb_cantidad <= 0:
                        st.error("La pérdida seleccionada no tiene cantidad válida.")
                    elif deb_cantidad > deb_existencia:
                        st.error("La cantidad perdida no puede ser mayor que la existencia actual.")
                    else:
                        fila_prod = get_producto_por_nombre(deb_producto)
                        precio = float(limpiar_numero(fila_prod.get("precio")) or 0) if fila_prod is not None else 0.0
                        
                        ok_stock = True
                        ok_inv = True
                        if fila_prod is not None:
                            ok_stock = actualizar_stock_producto(deb_producto, deb_nueva_existencia, date.today())
                            ok_inv = upsert_inventario_actual(
                                deb_producto,
                                deb_costo,
                                precio,
                                deb_nueva_existencia,
                                date.today(),
                                f"Descontado desde historial de pérdidas. ID: {deb_id}"
                            )
                            
                        obs_ant = limpiar_texto(fila_deb.get("observacion"))
                        obs_n = (obs_ant + " | " if obs_ant else "") + "Inventario descontado por administración"
                        ok_up = actualizar("perdidas", deb_id, {
                            "estado": "debitada",
                            "observacion": obs_n,
                            "revisado_por": nombre_usuario_actual(),
                            "fecha_revision": str(date.today()),
                            "decision_admin": "Descontada de inventario"
                        })
                        
                        if ok_stock and ok_inv and ok_up:
                            st.success("Pérdida aplicada al inventario correctamente.")
                            st.rerun()
            st.markdown("---")

        # --- LISTADO HISTÓRICO GENERAL DE PÉRDIDAS ---
        if puede_ver_perdidas():
            st.markdown("### 📊 Historial General de Pérdidas")
            if not df.empty:
                d1, d2 = rango_fechas_ui("perdidas")
                df_filtered = filtrar_por_fechas(df, d1, d2)
                txt = st.text_input("Buscar pérdida en historial", key="buscar_perd_hist")
                df_filtered = buscar_df(df_filtered, txt)
                
                # Columnas amigables para visualización
                cols_perd = ["id", "fecha", "hora", "producto", "cantidad", "costo_unitario", "valor", "estado", "reportado_por", "persona_involucrada", "decision_admin", "observacion"]
                cols_vis = [c for c in cols_perd if c in df_filtered.columns]
                st.dataframe(df_filtered[cols_vis], use_container_width=True)
                descargar_archivos(df_filtered, "perdidas")
                
                # CRUD genérico para edición/eliminación si tiene permisos
                render_crud_generico("perdidas", df_filtered, "🛠️ Editar / eliminar registros de pérdidas")
            else:
                st.info("No hay pérdidas registradas en el sistema.")
        else:
            st.warning("No tienes permiso para ver el historial de pérdidas.")



# =========================================================
# GASTOS DUEÑO
# =========================================================


