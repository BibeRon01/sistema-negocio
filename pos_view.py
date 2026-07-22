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

def render_pos():
    st.title("🛒 POS")
    
    def cerrar_buscador_modal():
        pass

    caja_activa = obtener_caja_abierta()
    if caja_activa is None:
        st.warning("Debes abrir la caja antes de vender.")
        st.stop()
    cfg = obtener_configuracion()
    productos_df = DATA["productos"].copy()
    
    # 🚨 ADVERTENCIA DE STOCK CRÍTICO EN EL POS (SIDEBAR)
    if not productos_df.empty:
        bajo_stock_critico = productos_df[(productos_df["activo"] == True) & (productos_df["stock"] <= 5)]
        if not bajo_stock_critico.empty:
            with st.sidebar:
                st.markdown("### ⚠️ Bebidas por agotarse (Crítico ≤ 5)")
                for _, r_bs in bajo_stock_critico.sort_values(by="stock").head(10).iterrows():
                    st.warning(f"⚠️ **{r_bs['nombre']}**: {int(r_bs['stock'])} unid.")

    if not productos_df.empty and "activo" in productos_df.columns:
        productos_df = productos_df[productos_df["activo"] == True]
    if productos_df.empty:
        st.warning("No hay productos activos para vender.")
    else:
        if "pos_cuenta_abierta_id" not in st.session_state:
            st.session_state["pos_cuenta_abierta_id"] = None
        if "pos_cuenta_abierta_nombre" not in st.session_state:
            st.session_state["pos_cuenta_abierta_nombre"] = None

        def restaurar_inventario_venta(v_id):
            try:
                items = supabase.table("detalle_venta").select("*").eq("venta_id", str(v_id)).execute().data or []
                productos = DATA.get("productos", pd.DataFrame())
                for item in items:
                    prod_id = item.get("producto_id")
                    cant = float(item.get("cantidad") or 0)
                    if prod_id and cant > 0:
                        prod_rows = productos[productos["id"].astype(str) == str(prod_id)]
                        if not prod_rows.empty:
                            p_row = prod_rows.iloc[0]
                            if producto_tiene_inventario(p_row):
                                actual = obtener_existencia_producto(p_row)
                                nueva_cant = actual + cant
                                actualizar_existencia_producto(p_row, nueva_cant)
                                prod_sync = refrescar_producto_por_id(p_row["id"])
                                row_usar = prod_sync if prod_sync is not None else p_row
                                sincronizar_producto_inventario(row_usar, ahora_str(), f"Restauracion por edicion {v_id}")
            except Exception as e:
                st.error(f"Error restaurando inventario: {e}")

        def mostrar_cuentas_abiertas_activas():
            st.subheader("📂 Cuentas Abiertas Activas")
            ventas_all = DATA.get("ventas", pd.DataFrame()).copy()
            if ventas_all.empty:
                st.info("No hay cuentas abiertas registradas.")
                return
            if "estado" in ventas_all.columns:
                cuentas_ab = ventas_all[(ventas_all["estado"].astype(str) == "abierta") & (ventas_all["anulado"] == False)]
            else:
                cuentas_ab = pd.DataFrame()
            if cuentas_ab.empty:
                st.info("No hay cuentas abiertas activas en este momento.")
                return
            for _, c_row in cuentas_ab.iterrows():
                v_id = c_row.get("id")
                num_fact = c_row.get("numero_factura")
                alias = c_row.get("cliente_nombre") or "Sin Nombre"
                fecha = c_row.get("fecha")
                total_c = float(c_row.get("total") or 0)
                
                # Cargar participantes desde observacion JSON
                observacion_raw = c_row.get("observacion") or "{}"
                try:
                    obs_data = json.loads(observacion_raw) if isinstance(observacion_raw, str) and observacion_raw.startswith("{") else {}
                except Exception:
                    obs_data = {}
                participantes = obs_data.get("participantes", [])
                
                with st.container(border=True):
                    col_info, col_acts = st.columns([3, 2])
                    with col_info:
                        st.markdown(f"### 📂 {alias}")
                        st.markdown(f"**Factura:** {num_fact} | **Total mesa:** RD$ {total_c:,.2f}")
                        st.caption(f"Abierta el: {fecha}")
                        
                        # Resumen de participantes si existen
                        if participantes:
                            pendientes = [p for p in participantes if not p.get("pagado")]
                            pagados = [p for p in participantes if p.get("pagado")]
                            total_participantes = sum(float(p.get("monto",0)) for p in participantes)
                            st.markdown(f"👥 **{len(participantes)} participante(s)** — 🔴 {len(pendientes)} pendiente(s), 🟢 {len(pagados)} pagado(s)")
                            st.markdown(f"💰 Total asignado a participantes: **RD$ {total_participantes:,.2f}**")
                    
                    with col_acts:
                        if st.button("✏️ Cargar / Editar", key=f"btn_edit_ab_{v_id}", use_container_width=True):
                            detalles = supabase.table("detalle_venta").select("*").eq("venta_id", str(v_id)).execute().data or []
                            st.session_state["pos_carrito"] = []
                            for d in detalles:
                                p_name = d.get("producto") or d.get("nombre") or ""
                                if not p_name:
                                    p_rows = productos_df[productos_df["id"].astype(str) == str(d["producto_id"])]
                                    if not p_rows.empty:
                                        p_name = str(p_rows.iloc[0].get("nombre") or "")
                                st.session_state["pos_carrito"].append({
                                    "producto_id": str(d["producto_id"]),
                                    "codigo": d.get("codigo"),
                                    "nombre": p_name,
                                    "producto": p_name,
                                    "cantidad": float(d["cantidad"]),
                                    "precio_unitario": float(d["precio_unitario"]),
                                    "total_linea": float(d["total_linea"]),
                                })
                            st.session_state["pos_cuenta_abierta_id"] = v_id
                            st.session_state["pos_cuenta_abierta_nombre"] = alias
                            st.session_state["mostrar_modal_busqueda"] = False
                            st.session_state["_pos_ir_a_carrito"] = True
                            st.rerun()
                        if st.button("❌ Cancelar Cuenta", key=f"btn_del_ab_{v_id}", use_container_width=True):
                            restaurar_inventario_venta(v_id)
                            supabase.table("detalle_venta").delete().eq("venta_id", str(v_id)).execute()
                            supabase.table("ventas").delete().eq("id", str(v_id)).execute()
                            registrar_auditoria("cuenta_abierta_cancelar", "ventas", f"venta_id={v_id} alias={alias}")
                            st.toast(f"❌ Cuenta '{alias}' cancelada y productos devueltos.", icon="🗑️")
                            invalidar_cache_tabla("ventas")
                            invalidar_cache_tabla("productos")
                            DATA.update(cargar_datos())
                            st.rerun()

                    # === PANEL DE PARTICIPANTES (MODO DOMINO) ===
                    with st.expander(f"🎲 Participantes / Deudores de esta cuenta ({len(participantes)})", expanded=len(participantes)>0):
                        st.caption("Registra quién debe qué dentro de esta cuenta (ej: cada jugador de dominó)")
                        
                        # Tabla de participantes actuales
                        if participantes:
                            for pi, p in enumerate(participantes):
                                pc1, pc2, pc3, pc4 = st.columns([3, 2, 1, 1])
                                estado_icon = "🟢" if p.get("pagado") else "🔴"
                                pc1.markdown(f"{estado_icon} **{p.get('nombre','?')}**")
                                pc2.markdown(f"RD$ {float(p.get('monto',0)):,.2f}")
                                
                                if p.get("pagado"):
                                    pc3.markdown("🟢 Pagado")
                                    if pc4.button("↩️", key=f"btn_reopen_part_{v_id}_{pi}", help="Reabrir / Deshacer pago", use_container_width=True):
                                        # Buscar y eliminar el abono de Supabase
                                        try:
                                            monto_part = float(p.get("monto", 0))
                                            # Eliminar de ventas_pagos y movimientos_caja
                                            supabase.table("ventas_pagos").delete().eq("venta_id", str(v_id)).eq("monto", monto_part).execute()
                                            supabase.table("movimientos_caja").delete().eq("referencia_id", str(v_id)).eq("monto", monto_part).eq("origen", "venta").execute()
                                            
                                            # Registrar en Auditoría
                                            registrar_auditoria_pro(
                                                accion="pago_parcial_revertir",
                                                modulo="POS",
                                                descripcion=f"Pago parcial de RD$ {monto_part:,.2f} revertido para el participante '{p.get('nombre')}' en cuenta '{alias}'",
                                                nivel_riesgo="medio",
                                                impacto_economico=-monto_part
                                            )
                                        except Exception:
                                            pass
                                        
                                        participantes[pi]["pagado"] = False
                                        obs_data["participantes"] = participantes
                                        supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                        invalidar_cache_tabla("ventas")
                                        invalidar_cache_tabla("caja")
                                        DATA.update(cargar_datos())
                                        st.toast(f"Pago de {p.get('nombre')} revertido.", icon="↩️")
                                        st.rerun()
                                else:
                                    with pc3.popover("💵 Cobrar", use_container_width=True):
                                        monto_cobrar = st.number_input("Monto (RD$)", min_value=0.01, max_value=float(p.get("monto") or 0.01), value=float(p.get("monto") or 0.01), key=f"pop_monto_{v_id}_{pi}")
                                        met_pago = st.selectbox("Método", ["efectivo", "tarjeta", "transferencia", "credito"], key=f"pop_met_{v_id}_{pi}")
                                        if st.button("Confirmar", key=f"pop_btn_{v_id}_{pi}", use_container_width=True, type="primary"):
                                            monto_part = float(monto_cobrar)
                                            try:
                                                # 1. Registrar pago en ventas_pagos
                                                supabase.table("ventas_pagos").insert({
                                                    "venta_id": str(v_id),
                                                    "metodo": met_pago,
                                                    "monto": monto_part,
                                                    "usuario": nombre_usuario_actual(),
                                                    "caja_id": str(c_row.get("caja_id")),
                                                    "dia_operativo": ahora_str(),
                                                }).execute()
                                                
                                                # 2. Registrar movimiento de caja si no es crédito
                                                if met_pago != "credito":
                                                    supabase.table("movimientos_caja").insert({
                                                        "fecha": datetime.now().isoformat(),
                                                        "dia_operativo": ahora_str(),
                                                        "caja_id": str(c_row.get("caja_id")),
                                                        "tipo_movimiento": "entrada",
                                                        "origen": "venta",
                                                        "referencia_id": str(v_id),
                                                        "metodo_pago": met_pago,
                                                        "monto": monto_part,
                                                        "descripcion": f"Pago parcial {p.get('nombre')} en {alias}",
                                                        "usuario": nombre_usuario_actual(),
                                                        "anulado": False,
                                                    }).execute()
                                                else:
                                                    # Si es crédito, registrar en cuentas_por_cobrar
                                                    supabase.table("cuentas_por_cobrar").insert({
                                                        "cliente_id": None,
                                                        "cliente_nombre": f"{alias} - {p.get('nombre')}",
                                                        "venta_id": str(v_id),
                                                        "monto_original": monto_part,
                                                        "monto_abonado": 0.0,
                                                        "saldo_pendiente": monto_part,
                                                        "estado": "pendiente",
                                                        "usuario": nombre_usuario_actual(),
                                                        "empresa_id": obtener_tenant_actual(),
                                                    }).execute()
                                                
                                                # Registrar auditoría
                                                registrar_auditoria_pro(
                                                    accion="pago_parcial_participante",
                                                    modulo="POS",
                                                    descripcion=f"Pago parcial de RD$ {monto_part:,.2f} ({met_pago}) registrado para {p.get('nombre')} en cuenta '{alias}'",
                                                    nivel_riesgo="bajo",
                                                    impacto_economico=monto_part if met_pago != "credito" else 0.0
                                                )
                                                
                                                nuevo_monto_restante = float(p.get("monto", 0)) - monto_part
                                                if nuevo_monto_restante <= 0.001:
                                                    participantes[pi]["pagado"] = True
                                                    participantes[pi]["monto"] = 0.0
                                                else:
                                                    participantes[pi]["monto"] = nuevo_monto_restante
                                                    participantes[pi]["pagado"] = False
                                                    
                                                obs_data["participantes"] = participantes
                                                supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                                
                                                invalidar_cache_tabla("ventas")
                                                invalidar_cache_tabla("caja")
                                                DATA.update(cargar_datos())
                                                st.toast(f"¡Pago de {p.get('nombre')} de RD$ {monto_part:,.2f} registrado!", icon="✅")
                                                st.rerun()
                                            except Exception as ex:
                                                st.error(f"Error al registrar pago: {ex}")
                                                
                                    if pc4.button("🗑️", key=f"btn_del_part_{v_id}_{pi}", use_container_width=True):
                                        participantes.pop(pi)
                                        obs_data["participantes"] = participantes
                                        supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                        DATA.update(cargar_datos())
                                        st.rerun()
                        else:
                            st.info("💭 Ninguno todavía. Agrega los participantes abajo.")

                        st.markdown("**Agregar participante:**")
                        np1, np2, np3 = st.columns([3, 2, 1])
                        nuevo_nombre_p = np1.text_input("Nombre", key=f"nuevo_p_nombre_{v_id}", placeholder="Ej: Juan, Pedro...")
                        nuevo_monto_p = np2.number_input("Monto que debe (RD$)", min_value=0.0, step=50.0, key=f"nuevo_p_monto_{v_id}")
                        if np3.button("➕", key=f"btn_add_part_{v_id}", use_container_width=True):
                            if not nuevo_nombre_p.strip():
                                st.error("Debes escribir el nombre del participante.")
                            elif nuevo_monto_p <= 0:
                                st.error("El monto debe ser mayor a cero.")
                            else:
                                participantes.append({"nombre": nuevo_nombre_p.strip(), "monto": float(nuevo_monto_p), "pagado": False})
                                obs_data["participantes"] = participantes
                                supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                DATA.update(cargar_datos())
                                st.rerun()

                    # === OPERACIONES EN CALIENTE (DIVIDIR / FUSIONAR) ===
                    with st.expander("✂️ Dividir / 🔗 Fusionar Cuenta", expanded=False):
                        col_div, col_fus = st.columns(2)
                        
                        # DIVIDIR CUENTA
                        with col_div:
                            st.markdown("##### ✂️ Dividir Cuenta (Crear nueva)")
                            # Cargar items
                            detalles_div = supabase.table("detalle_venta").select("*").eq("venta_id", str(v_id)).execute().data or []
                            if detalles_div:
                                items_to_move = {}
                                for d in detalles_div:
                                    d_id = d.get("id")
                                    p_name = d.get("producto") or "Producto"
                                    cant_max = float(d.get("cantidad") or 1)
                                    if cant_max > 1:
                                        cant_move = st.number_input(f"Mover {p_name} (Max {cant_max})", min_value=0.0, max_value=cant_max, step=1.0, value=0.0, key=f"split_cant_{v_id}_{d_id}")
                                    else:
                                        cant_move = st.checkbox(f"Mover {p_name} (1 unidad)", key=f"split_chk_{v_id}_{d_id}")
                                        cant_move = 1.0 if cant_move else 0.0
                                    if cant_move > 0:
                                        items_to_move[d_id] = {
                                            "producto_id": d.get("producto_id"),
                                            "codigo": d.get("codigo"),
                                            "producto": p_name,
                                            "cantidad": cant_move,
                                            "precio_unitario": float(d.get("precio_unitario") or 0),
                                            "costo_unitario": float(d.get("costo_unitario") or 0),
                                            "descuento": float(d.get("descuento") or 0),
                                            "recargo": float(d.get("recargo") or 0),
                                            "item_detail": d
                                        }
                                
                                new_alias = st.text_input("Alias nueva cuenta", placeholder="Ej: Mesa 4...", key=f"split_alias_{v_id}")
                                if st.button("Confirmar División", key=f"btn_split_confirm_{v_id}", use_container_width=True):
                                    if not items_to_move:
                                        st.error("Selecciona al menos un producto.")
                                    elif not new_alias.strip():
                                        st.error("Indica un nombre/alias para la nueva cuenta.")
                                    else:
                                        try:
                                            new_num_fact = generar_numero_factura_pos()
                                            new_venta_resp = supabase.table("ventas").insert(json_safe_payload({
                                                "fecha": datetime.now().isoformat(),
                                                "subtotal": 0.0,
                                                "descuento": 0.0,
                                                "recargo": 0.0,
                                                "total": 0.0,
                                                "metodo_pago": "abierta",
                                                "cliente_id": c_row.get("cliente_id"),
                                                "cliente_nombre": new_alias.strip(),
                                                "usuario": nombre_usuario_actual(),
                                                "dia_operativo": ahora_str(),
                                                "caja_id": str(c_row.get("caja_id")),
                                                "ncf": c_row.get("ncf"),
                                                "numero_factura": new_num_fact,
                                                "tipo_venta": "POS",
                                                "estado": "abierta",
                                                "anulado": False,
                                            })).execute()
                                            
                                            new_venta = (new_venta_resp.data or [{}])[0]
                                            new_v_id = new_venta.get("id")
                                            
                                            for d_id, info in items_to_move.items():
                                                cant_m = info["cantidad"]
                                                d_orig = info["item_detail"]
                                                total_linea_new = cant_m * info["precio_unitario"]
                                                ganancia_linea_new = total_linea_new - (cant_m * info["costo_unitario"])
                                                
                                                supabase.table("detalle_venta").insert({
                                                    "venta_id": str(new_v_id),
                                                    "producto_id": str(info["producto_id"]),
                                                    "codigo": info["codigo"],
                                                    "producto": info["producto"],
                                                    "cantidad": cant_m,
                                                    "precio_unitario": info["precio_unitario"],
                                                    "costo_unitario": info["costo_unitario"],
                                                    "descuento": info["descuento"],
                                                    "recargo": info["recargo"],
                                                    "total_linea": total_linea_new,
                                                    "ganancia_linea": ganancia_linea_new,
                                                    "usuario": nombre_usuario_actual(),
                                                    "anulado": False,
                                                    "empresa_id": obtener_tenant_actual()
                                                }).execute()
                                                
                                                cant_old_new = float(d_orig["cantidad"]) - cant_m
                                                if cant_old_new <= 0:
                                                    supabase.table("detalle_venta").delete().eq("id", d_id).execute()
                                                else:
                                                    total_linea_old = cant_old_new * info["precio_unitario"]
                                                    ganancia_linea_old = total_linea_old - (cant_old_new * info["costo_unitario"])
                                                    supabase.table("detalle_venta").update({
                                                        "cantidad": cant_old_new,
                                                        "total_linea": total_linea_old,
                                                        "ganancia_linea": ganancia_linea_old
                                                    }).eq("id", d_id).execute()
                                                    
                                            new_details = supabase.table("detalle_venta").select("total_linea").eq("venta_id", str(new_v_id)).execute().data or []
                                            new_tot = sum(float(x.get("total_linea") or 0) for x in new_details)
                                            supabase.table("ventas").update({"total": new_tot, "subtotal": new_tot}).eq("id", str(new_v_id)).execute()
                                            
                                            old_details = supabase.table("detalle_venta").select("total_linea").eq("venta_id", str(v_id)).execute().data or []
                                            old_tot = sum(float(x.get("total_linea") or 0) for x in old_details)
                                            if old_tot <= 0:
                                                supabase.table("ventas").delete().eq("id", str(v_id)).execute()
                                                st.success("Toda la cuenta fue dividida. Cuenta original eliminada por quedar vacía.")
                                            else:
                                                supabase.table("ventas").update({"total": old_tot, "subtotal": old_tot}).eq("id", str(v_id)).execute()
                                                st.success("Cuenta dividida correctamente.")
                                                
                                            registrar_auditoria("cuenta_abierta_dividir", "ventas", f"venta_id_origen={v_id} venta_id_destino={new_v_id}")
                                            invalidar_cache_tabla("ventas")
                                            DATA.update(cargar_datos())
                                            st.rerun()
                                        except Exception as ex:
                                            st.error(f"Error al dividir cuenta: {ex}")
                            else:
                                st.info("No hay productos.")
                                
                        # FUSIONAR CUENTAS
                        with col_fus:
                            st.markdown("##### 🔗 Fusionar con otra Cuenta")
                            otras_cuentas = cuentas_ab[cuentas_ab["id"] != v_id]
                            if otras_cuentas.empty:
                                st.info("No hay otras cuentas abiertas para fusionar.")
                            else:
                                opciones_fusion = {f"{r.get('cliente_nombre')} ({r.get('numero_factura')})": r.get("id") for _, r in otras_cuentas.iterrows()}
                                cuenta_fusion_sel = st.selectbox("Seleccione la cuenta a absorber", list(opciones_fusion.keys()), key=f"fusion_sel_{v_id}")
                                id_fusion = opciones_fusion[cuenta_fusion_sel]
                                
                                if st.button("Confirmar Fusión", key=f"btn_fusion_confirm_{v_id}", use_container_width=True):
                                    try:
                                        items_absorb = supabase.table("detalle_venta").select("*").eq("venta_id", str(id_fusion)).execute().data or []
                                        items_dest = supabase.table("detalle_venta").select("*").eq("venta_id", str(v_id)).execute().data or []
                                        dest_prod_map = {str(x["producto_id"]): x for x in items_dest}
                                        
                                        for item in items_absorb:
                                            p_id = str(item["producto_id"])
                                            cant_b = float(item["cantidad"])
                                            
                                            if p_id in dest_prod_map:
                                                d_orig = dest_prod_map[p_id]
                                                cant_new = float(d_orig["cantidad"]) + cant_b
                                                total_linea_new = cant_new * float(d_orig["precio_unitario"])
                                                ganancia_linea_new = total_linea_new - (cant_new * float(d_orig["costo_unitario"]))
                                                
                                                supabase.table("detalle_venta").update({
                                                    "cantidad": cant_new,
                                                    "total_linea": total_linea_new,
                                                    "ganancia_linea": ganancia_linea_new
                                                }).eq("id", d_orig["id"]).execute()
                                            else:
                                                supabase.table("detalle_venta").update({"venta_id": str(v_id)}).eq("id", item["id"]).execute()
                                                
                                        supabase.table("detalle_venta").delete().eq("venta_id", str(id_fusion)).execute()
                                        supabase.table("ventas").delete().eq("id", str(id_fusion)).execute()
                                        
                                        dest_details = supabase.table("detalle_venta").select("total_linea").eq("venta_id", str(v_id)).execute().data or []
                                        dest_tot = sum(float(x.get("total_linea") or 0) for x in dest_details)
                                        supabase.table("ventas").update({"total": dest_tot, "subtotal": dest_tot}).eq("id", str(v_id)).execute()
                                        
                                        st.success("Cuentas fusionadas correctamente.")
                                        registrar_auditoria("cuenta_abierta_fusionar", "ventas", f"venta_id_destino={v_id} venta_id_absorbido={id_fusion}")
                                        invalidar_cache_tabla("ventas")
                                        DATA.update(cargar_datos())
                                        st.rerun()
                                    except Exception as ex:
                                        st.error(f"Error al fusionar cuentas: {ex}")

        # Aplicar la redirección ANTES de renderizar el radio (previene el error de Streamlit)
        if st.session_state.pop("_pos_ir_a_carrito", False):
            st.session_state["pos_vista_seccion"] = "🛒 Carrito de Ventas"
        if "_pos_ir_a_seccion" in st.session_state:
            st.session_state["pos_vista_seccion"] = st.session_state.pop("_pos_ir_a_seccion")

        vista_pos = st.radio("Sección POS", ["🛒 Carrito de Ventas", "📂 Cuentas Abiertas Activas"], horizontal=True, key="pos_vista_seccion")
        if vista_pos == "📂 Cuentas Abiertas Activas":
            mostrar_cuentas_abiertas_activas()
            st.stop()

        if "pos_carrito" not in st.session_state:
            st.session_state["pos_carrito"] = []
        carrito = st.session_state["pos_carrito"]

        def agregar_item_carrito(prod_row, cantidad=1.0, precio_usar=None):
            nombre = obtener_nombre_producto(prod_row)
            precio_base = precio_usar if precio_usar is not None else (limpiar_numero(prod_row.get("precio")) or 0)
            for item in carrito:
                if str(item["producto_id"]) == str(prod_row["id"]):
                    item["cantidad"] += float(cantidad)
                    item["total_linea"] = item["cantidad"] * item["precio_unitario"]
                    return
            carrito.append({
                "producto_id": str(prod_row["id"]),
                "codigo": limpiar_texto(prod_row.get("codigo")),
                        "cantidad": float(cantidad),
                "precio_unitario": float(precio_base),
                "total_linea": float(cantidad) * float(precio_base),
            })

        @st.dialog("🔍 Buscar Productos", width="large")
        def modal_buscar_productos():
            st.markdown("""
            <style>
            .modal-card {
                background-color: #13783b !important;
                color: white !important;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                margin-bottom: 12px;
                height: 190px;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                box-shadow: 0 4px 6px rgba(0,0,0,0.15);
                position: relative;
            }
            .modal-img-placeholder {
                background-color: rgba(255,255,255,0.2);
                height: 55px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                margin-bottom: 6px;
                font-size: 11px;
            }
            .modal-title {
                font-weight: 800;
                font-size: 13px;
                height: 38px;
                overflow: hidden;
                line-height: 1.2;
                margin-bottom: 4px;
            }
            .modal-price {
                font-size: 16px;
                font-weight: 900;
            }
            .modal-stock {
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                margin-top: 4px;
                display: inline-block;
            }
            </style>
            """, unsafe_allow_html=True)

            val_inicial = st.session_state.get("modal_query_src_preloaded") or ""
            if "modal_query_src_preloaded" in st.session_state:
                st.session_state.pop("modal_query_src_preloaded")

            m_col1, m_col2 = st.columns([2, 1])
            with m_col1:
                m_query = st.text_input("BUSCAR POR CODIGO/NOMBRE", value=val_inicial, key="modal_query_src", placeholder="BUSCAR POR CODIGO/NOMBRE", label_visibility="collapsed")
            with m_col2:
                categorias_raw = productos_df["categoria"].unique() if "categoria" in productos_df.columns else []
                categorias = ["-- CATEGORIA --"] + sorted([str(c) for c in categorias_raw if str(c).strip() != "" and str(c).lower() not in ['nan', 'none']])
                m_cat = st.selectbox("CATEGORÍA", categorias, key="modal_cat_src", label_visibility="collapsed")

            df_m = productos_df.copy()
            if m_query:
                df_m = df_m[
                    df_m["nombre"].astype(str).str.contains(m_query, case=False, na=False) |
                    df_m["codigo"].astype(str).str.contains(m_query, case=False, na=False) |
                    df_m["categoria"].astype(str).str.contains(m_query, case=False, na=False)
                ]
            if m_cat != "-- CATEGORIA --":
                df_m = df_m[df_m["categoria"] == m_cat]

            if df_m.empty:
                st.info("No se encontraron productos.")
            else:
                import math
                total_items = len(df_m)
                items_per_page = 12
                total_pages = max(1, math.ceil(total_items / items_per_page))
                
                if "modal_search_page" not in st.session_state:
                    st.session_state["modal_search_page"] = 1
                    
                # Reset page to 1 if search query or category changes
                last_query_key = f"_last_query_{m_query}_{m_cat}"
                if st.session_state.get("_last_query_key") != last_query_key:
                    st.session_state["modal_search_page"] = 1
                    st.session_state["_last_query_key"] = last_query_key
                    
                current_page = st.session_state["modal_search_page"]
                if current_page > total_pages:
                    current_page = total_pages
                    st.session_state["modal_search_page"] = total_pages
                    
                start_idx = (current_page - 1) * items_per_page
                df_display = df_m.iloc[start_idx : start_idx + items_per_page]
                
                cols = st.columns(3)
                for idx, (_, row) in enumerate(df_display.iterrows()):
                    with cols[idx % 3]:
                        nombre = obtener_nombre_producto(row)
                        precio = limpiar_numero(row.get("precio")) or 0.0
                        stock = obtener_existencia_producto(row)
                        stock_bg = "#ffd600" if stock < 5 else "#1e88e5"
                        stock_color = "black" if stock < 5 else "white"
                        
                        html_card = f"""
                        <div class="modal-card" title="Agregar Producto">
                            <div class="modal-img-placeholder">
                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: rgba(255,255,255,0.7);"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>
                            </div>
                            <div class="modal-title">{nombre.upper()}</div>
                            <div class="modal-price">$ {precio:,.2f}</div>
                            <div>
                                <span class="modal-stock" style="background-color: {stock_bg}; color: {stock_color} !important;">Stock: {stock:,.0f}</span>
                            </div>
                        </div>
                        """
                        st.markdown(html_card, unsafe_allow_html=True)
                        if st.button("➕ Seleccionar", key=f"btn_modal_add_{row['id']}_{idx}", use_container_width=True):
                            if producto_tiene_inventario(row) and 1 > stock:
                                st.error("Sin stock")
                            else:
                                agregar_item_carrito(row, 1.0, precio)
                                st.toast(f"✅ Agregado: {nombre}")
                                st.rerun()

                # Render pagination controls at the bottom
                st.markdown("---")
                pag_cols = st.columns([1.5, 7, 1.5])
                with pag_cols[0]:
                    if current_page > 1:
                        if st.button("‹ Anterior", key="btn_modal_prev_page", use_container_width=True):
                            st.session_state["modal_search_page"] = current_page - 1
                            st.rerun()
                    else:
                        st.button("‹ Anterior", key="btn_modal_prev_page_disabled", disabled=True, use_container_width=True)
                        
                with pag_cols[1]:
                    pages_to_show = []
                    if total_pages <= 7:
                        pages_to_show = list(range(1, total_pages + 1))
                    else:
                        if current_page <= 4:
                            pages_to_show = [1, 2, 3, 4, 5, "...", total_pages]
                        elif current_page >= total_pages - 3:
                            pages_to_show = [1, "...", total_pages - 4, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
                        else:
                            pages_to_show = [1, "...", current_page - 1, current_page, current_page + 1, "...", total_pages]
                            
                    num_cols = st.columns(len(pages_to_show))
                    for p_idx, page in enumerate(pages_to_show):
                        with num_cols[p_idx]:
                            if page == "...":
                                st.markdown("<div style='text-align: center; padding-top: 5px; color: #6b7280; font-weight: bold;'>...</div>", unsafe_allow_html=True)
                            elif page == current_page:
                                st.markdown(f"<div style='background-color: #13783b; color: white; border-radius: 4px; text-align: center; padding: 6px 0px; font-weight: bold;'>{page}</div>", unsafe_allow_html=True)
                            else:
                                if st.button(str(page), key=f"btn_modal_page_{page}_{p_idx}", use_container_width=True):
                                    st.session_state["modal_search_page"] = page
                                    st.rerun()
                                    
                with pag_cols[2]:
                    if current_page < total_pages:
                        if st.button("Siguiente ›", key="btn_modal_next_page", use_container_width=True):
                            st.session_state["modal_search_page"] = current_page + 1
                            st.rerun()
                    else:
                        st.button("Siguiente ›", key="btn_modal_next_page_disabled", disabled=True, use_container_width=True)
            
            st.markdown("---")
            if st.button("Cerrar", key="btn_close_modal_pos", use_container_width=True):
                st.session_state["mostrar_modal_busqueda"] = False
                st.rerun()

        # The search modal is now called natively when the form is submitted.

        with st.form("form_buscar_pos", clear_on_submit=True):
            col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
            with col_c1:
                cant_scan = st.number_input("Cant:", min_value=1.0, value=1.0, step=1.0)
            with col_c2:
                codigo_scan = st.text_input("Codigo:", placeholder="Escanear o escribir código...")
            with col_c3:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                submitted_buscar = st.form_submit_button("🔍 Buscar", use_container_width=True)
                
            if submitted_buscar:
                if codigo_scan.strip():
                    prod = get_producto_por_codigo(codigo_scan)
                    if prod is not None:
                        if producto_tiene_inventario(prod) and obtener_existencia_producto(prod) <= 0:
                            st.warning("Ese producto no tiene stock disponible.")
                        else:
                            agregar_item_carrito(prod, float(cant_scan))
                            st.rerun()
                    else:
                        st.session_state["modal_query_src_preloaded"] = codigo_scan.strip()
                        st.session_state["mostrar_modal_busqueda"] = True
                        st.rerun()
                else:
                    st.session_state["mostrar_modal_busqueda"] = True
                    st.rerun()

        if st.session_state.get("mostrar_modal_busqueda", False):
            modal_buscar_productos()

        st.markdown("---")
        st.subheader("📱 Catálogo Rápido")
        st.markdown("""
        <style>
        .pos-card {
            background-color: white;
            border: 2px solid #003366;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            margin-bottom: -5px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            position: relative;
        }
        .pos-img {
            background-color: #f1f1f1;
            height: 70px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 4px;
            margin-bottom: 8px;
            color: #999;
            font-size: 14px;
        }
        .pos-title {
            color: #003366;
            font-size: 13px;
            font-weight: 800;
            line-height: 1.2;
            height: 32px;
            overflow: hidden;
            margin-bottom: 5px;
        }
        .pos-price {
            color: #cc0000;
            font-size: 16px;
            font-weight: 900;
        }
        .pos-stock {
            position: absolute;
            top: 65px;
            right: 15px;
            background-color: #0088cc;
            color: white;
            padding: 2px 6px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            border: 1px solid white;
        }
        .pos-stock.low { background-color: #ff9900; }
        </style>
        """, unsafe_allow_html=True)
        
        buscar_grid = st.text_input("🔍 Escribe un nombre o código para desplegar en el catálogo rápido", key="pos_buscar_grid_filtro")
        
        if not buscar_grid.strip():
            st.info("💡 Por favor, escribe un nombre o código arriba para desplegar los productos en el catálogo rápido.")
        else:
            df_filtrado_grid = productos_df.copy()
            df_filtrado_grid = df_filtrado_grid[df_filtrado_grid.astype(str).apply(lambda col: col.str.contains(buscar_grid, case=False, na=False)).any(axis=1)]
            
            if df_filtrado_grid.empty:
                st.warning("❌ No se encontraron productos con ese filtro.")
            else:
                cols = st.columns(4)
                for idx, (_, row) in enumerate(df_filtrado_grid.iterrows()):
                    with cols[idx % 4]:
                        nombre = obtener_nombre_producto(row)
                        precio = limpiar_numero(row.get("precio")) or 0.0
                        stock = obtener_existencia_producto(row)
                        stock_class = "low" if stock <= 5 else ""
                        
                        img_url = row.get("imagen_url")
                        if img_url and str(img_url).strip():
                            img_html = f'<div class="pos-img" style="background-color: transparent;"><img src="{img_url}" style="max-height: 70px; max-width: 100%; object-fit: contain; border-radius: 4px;" /></div>'
                        else:
                            img_html = '<div class="pos-img">📷 Sin Imagen</div>'
                            
                        html_card = f"""
                        <div class="pos-card">
                            {img_html}
                            <div class="pos-stock {stock_class}">Stock: {stock:,.0f}</div>
                            <div class="pos-title">{nombre}</div>
                            <div class="pos-price">$ {precio:,.2f}</div>
                        </div>
                        """
                        st.markdown(html_card, unsafe_allow_html=True)
                        if st.button("➕", key=f"btn_grid_cat_{row['id']}", use_container_width=True):
                            if producto_tiene_inventario(row) and 1 > stock:
                                st.error("Sin stock")
                            else:
                                agregar_item_carrito(row, 1.0, precio)
                                st.rerun()

        st.subheader("🧾 Carrito")

        post_venta = st.session_state.get("pos_post_venta")
        if post_venta:
            st.success(f"Venta registrada correctamente. Factura No.: {post_venta.get('numero_factura') or post_venta.get('venta_id', '')}")
            p1, p2, p3 = st.columns(3)
            p1.metric("Total", f"RD$ {float(post_venta.get('total', 0)):,.2f}")
            p2.metric("Cambio", f"RD$ {float(post_venta.get('cambio', 0)):,.2f}")
            p3.metric("Método", str(post_venta.get('metodo_pago', '')))

            mostrar_factura_pos(post_venta)

            if st.button("✅ Terminar", key=f"btn_pos_post_venta_terminar_{post_venta.get('venta_id')}"):
                st.session_state["pos_post_venta"] = None
                st.rerun()
            st.markdown("---")

        if carrito:
            st.caption("Si te equivocas antes de cobrar, cambia la cantidad aquí mismo o elimina la línea.")
            nuevo_carrito = []
            eliminar_idx = None

            for i, item in enumerate(list(carrito)):
                item = recalcular_item_carrito(item)
                producto_nombre = nombre_item(item)
                precio_unitario = float(limpiar_numero(item.get("precio_unitario")) or 0)

                # Fetch available stock to dynamically limit maximum amount in the cart input
                prod_id = item.get("producto_id")
                prod_rows = productos_df[productos_df["id"].astype(str) == str(prod_id)]
                stock = 999999.0
                usa_inv = False
                if not prod_rows.empty:
                    p_row = prod_rows.iloc[0]
                    usa_inv = producto_tiene_inventario(p_row)
                    stock = obtener_existencia_producto(p_row)

                col_q1, col_q2, col_q3, col_q4 = st.columns([5, 2, 2, 1])
                with col_q1:
                    st.markdown(f"**{producto_nombre}**")
                with col_q2:
                    max_cant = max(0.0, float(stock)) if usa_inv else 999999.0
                    nueva_cant = st.number_input(
                        "Cantidad",
                        min_value=0.0,
                        max_value=max_cant,
                        step=1.0,
                        value=min(float(item.get("cantidad", 0)), max_cant),
                        key=f"pos_carrito_cant_{i}_{item.get('producto_id','')}_{item.get('codigo','')}",
                        label_visibility="collapsed",
                        on_change=cerrar_buscador_modal,
                    )
                item["cantidad"] = float(nueva_cant)
                item["total_linea"] = float(nueva_cant) * precio_unitario

                with col_q3:
                    st.markdown(f"**RD$ {item['total_linea']:,.2f}**")
                with col_q4:
                    if st.button("❌", key=f"quitar_pos_{i}_{item.get('producto_id','')}_{item.get('codigo','')}"):
                        eliminar_idx = i

                if item["cantidad"] > 0:
                    nuevo_carrito.append(item)

            if eliminar_idx is not None:
                nuevo_carrito = [x for idx_x, x in enumerate(nuevo_carrito) if idx_x != eliminar_idx]
                st.session_state["pos_carrito"] = nuevo_carrito
                st.rerun()

            st.session_state["pos_carrito"] = nuevo_carrito
            carrito = st.session_state["pos_carrito"]
            # 1. Configuración de ITBIS en Venta
            st.markdown("### 🧮 Configuración de ITBIS en Venta")
            es_autorizado_itbis = es_admin() or tiene_permiso("puede_configurar") or tiene_permiso("puede_editar_todo")
            
            col_itb1, col_itb2 = st.columns(2)
            with col_itb1:
                aplicar_itbis_toggle = st.toggle("Aplicar ITBIS a la venta", value=True, disabled=not es_autorizado_itbis, key="pos_aplicar_itbis_toggle")
            with col_itb2:
                itbis_incluido_global = st.selectbox(
                    "Tratamiento de precios",
                    ["Precios YA incluyen ITBIS (Desglosar)", "Precios NO incluyen ITBIS (Sumar)"],
                    index=0 if bool(cfg.get("precios_incluyen_itbis", True)) else 1,
                    disabled=not es_autorizado_itbis,
                    key="pos_itbis_incluido_global_sel"
                )
                pos_itbis_incluido_global = (itbis_incluido_global == "Precios YA incluyen ITBIS (Desglosar)")
                st.session_state["pos_itbis_incluido_global"] = pos_itbis_incluido_global

            # Calcular subtotales e ITBIS por producto
            subtotal_gravado = 0.0
            subtotal_exento = 0.0
            total_itbis = 0.0
            total_carrito = 0.0

            for item in carrito:
                p_id = item.get("producto_id")
                p_rows = productos_df[productos_df["id"].astype(str) == str(p_id)]
                p_row = p_rows.iloc[0] if not p_rows.empty else {}
                
                # Configuración tributaria del producto (con fallbacks si la migración no se ha corrido)
                itbis_gravado = bool(p_row.get("itbis_gravado", True)) if "itbis_gravado" in p_row else True
                itbis_tasa = float(p_row.get("itbis_tasa", 18.0)) if "itbis_tasa" in p_row else 18.0
                itbis_incluido = bool(p_row.get("itbis_incluido", True)) if "itbis_incluido" in p_row else True
                
                t_linea = float(item.get("total_linea") or 0.0)
                
                if aplicar_itbis_toggle and itbis_gravado:
                    tasa = itbis_tasa / 100.0
                    if pos_itbis_incluido_global:
                        base_l = t_linea / (1.0 + tasa)
                        itbis_l = t_linea - base_l
                        total_l = t_linea
                    else:
                        base_l = t_linea
                        itbis_l = t_linea * tasa
                        total_l = t_linea + itbis_l
                    subtotal_gravado += base_l
                    total_itbis += itbis_l
                    total_carrito += total_l
                else:
                    subtotal_exento += t_linea
                    total_carrito += t_linea

            subtotal = subtotal_gravado + subtotal_exento
            st.markdown(f"### Total carrito: RD$ {total_carrito:,.2f}")

            descuento_global = st.number_input("Descuento global", min_value=0.0, step=1.0, key="pos_desc_global")
            
            # Recalcular proporcionalmente con descuento
            total_real_venta = max(total_carrito - descuento_global, 0.0)
            scale = (total_real_venta / total_carrito) if total_carrito > 0 else 1.0
            subtotal_gravado_neto = subtotal_gravado * scale
            subtotal_exento_neto = subtotal_exento * scale
            total_itbis_neto = total_itbis * scale
            subtotal_neto = subtotal * scale

            cliente_df = DATA.get("clientes", pd.DataFrame()).copy()
            cliente_nombre = "Venta general"
            cliente_id = None

            if "pos_cliente_creado_id" not in st.session_state:
                st.session_state["pos_cliente_creado_id"] = None
            if "pos_cliente_creado_nombre" not in st.session_state:
                st.session_state["pos_cliente_creado_nombre"] = None

            usar_cliente = st.checkbox("Asignar cliente", value=False, key="pos_usar_cliente")
            if usar_cliente:
                st.markdown("#### 👤 Cliente")
                tab_cli_existente, tab_cli_nuevo = st.tabs(["Buscar cliente", "Crear cliente rápido"])

                with tab_cli_existente:
                    if not cliente_df.empty and "nombre" in cliente_df.columns:
                        buscar_cli = st.text_input("Buscar cliente por nombre/teléfono/documento", key="pos_buscar_cliente")
                        cli_temp = cliente_df.copy()
                        if buscar_cli:
                            cli_temp = buscar_df(cli_temp, buscar_cli)
                        cli_opt = ["Venta general"] + cli_temp["nombre"].astype(str).tolist()
                        cliente_nombre = st.selectbox("Cliente", cli_opt, key="pos_cliente_sel")
                        if cliente_nombre != "Venta general":
                            cli_row = cli_temp[cli_temp["nombre"].astype(str) == cliente_nombre].iloc[0]
                            cliente_id = json_safe_value(cli_row.get("id"))
                            st.session_state["pos_cliente_creado_id"] = None
                            st.session_state["pos_cliente_creado_nombre"] = None
                    else:
                        st.info("No hay clientes registrados. Puedes crear uno rápido en la pestaña siguiente.")

                with tab_cli_nuevo:
                    cn1, cn2 = st.columns(2)
                    with cn1:
                        nuevo_cliente_nombre = st.text_input("Nombre del cliente", key="pos_nuevo_cliente_nombre")
                        nuevo_cliente_tel = st.text_input("Teléfono", key="pos_nuevo_cliente_tel")
                    with cn2:
                        nuevo_cliente_doc = st.text_input("Cédula/RNC opcional", key="pos_nuevo_cliente_doc")
                        nuevo_cliente_dir = st.text_input("Dirección opcional", key="pos_nuevo_cliente_dir")

                    if st.button("➕ Guardar cliente y asignar", key="btn_pos_crear_cliente_rapido"):
                        creado = crear_cliente_rapido_pos(
                            nuevo_cliente_nombre,
                            telefono=nuevo_cliente_tel,
                            documento=nuevo_cliente_doc,
                            direccion=nuevo_cliente_dir,
                        )
                        if creado:
                            st.session_state["pos_cliente_creado_id"] = creado.get("id")
                            st.session_state["pos_cliente_creado_nombre"] = creado.get("nombre") or nuevo_cliente_nombre
                            st.success(f"Cliente creado y asignado: {st.session_state['pos_cliente_creado_nombre']}")
                            st.rerun()

                if st.session_state.get("pos_cliente_creado_id"):
                    cliente_id = json_safe_value(st.session_state.get("pos_cliente_creado_id"))
                    cliente_nombre = st.session_state.get("pos_cliente_creado_nombre") or "Venta general"
                    st.success(f"Cliente asignado: {cliente_nombre}")
            
            cpa1, cpa2, cpa3, cpa4 = st.columns(4)
            with cpa1:
                pago_efectivo = st.number_input("Efectivo", min_value=0.0, step=1.0, key="pos_pag_ef")
            with cpa2:
                pago_transferencia = st.number_input("Transferencia", min_value=0.0, step=1.0, key="pos_pag_tr")
            with cpa3:
                pago_tarjeta = st.number_input("Tarjeta", min_value=0.0, step=1.0, key="pos_pag_tj")
            with cpa4:
                pago_credito = st.number_input("Crédito / fiado", min_value=0.0, step=1.0, key="pos_pag_cr")
            
            recargo = 0.0

            abonos_previos = 0.0
            cuenta_ab_id = st.session_state.get("pos_cuenta_abierta_id")
            if cuenta_ab_id:
                try:
                    pagos_prev_resp = supabase.table("ventas_pagos").select("monto").eq("venta_id", str(cuenta_ab_id)).execute()
                    abonos_db = sum(float(x.get("monto") or 0) for x in (pagos_prev_resp.data or []))
                    
                    venta_resp_v = supabase.table("ventas").select("observacion").eq("id", str(cuenta_ab_id)).execute()
                    abonos_json = 0.0
                    if venta_resp_v.data:
                        v_row_v = venta_resp_v.data[0]
                        obs_raw_v = v_row_v.get("observacion") or "{}"
                        try:
                            obs_data_v = json.loads(obs_raw_v) if isinstance(obs_raw_v, str) and obs_raw_v.startswith("{") else {}
                        except Exception:
                            obs_data_v = {}
                        parts_v = obs_data_v.get("participantes", [])
                        abonos_json = sum(float(p.get("monto") or 0) for p in parts_v if p.get("pagado"))
                        
                    abonos_previos = max(abonos_db, abonos_json)
                except Exception:
                    pass

            total_real_pendiente = max(total_real_venta - abonos_previos, 0.0)
            total_a_cobrar_cliente = total_real_pendiente
            total_final = total_real_venta

            if abonos_previos > 0:
                st.info(f"💰 **Abonos previos:** Esta cuenta ya registra pagos por **RD$ {abonos_previos:,.2f}**. Monto restante a saldar hoy: **RD$ {total_real_pendiente:,.2f}**.")

            pagos_total = pago_efectivo + pago_transferencia + pago_tarjeta + pago_credito
            diferencia_pagos = round(pagos_total - total_real_pendiente, 2)
            cambio = max(diferencia_pagos, 0.0)
            faltante = max(-diferencia_pagos, 0.0)
            pagos_cuadran = faltante <= 0.001

            csum1, csum2, csum3, csum4, csum5 = st.columns(5)
            csum1.metric("Total venta", f"RD$ {total_real_venta:,.2f}")
            csum2.metric("Abonos previos", f"RD$ {abonos_previos:,.2f}")
            csum3.metric("Pendiente hoy", f"RD$ {total_real_pendiente:,.2f}")
            csum4.metric("Registrado hoy", f"RD$ {pagos_total:,.2f}")
            csum5.metric("Diferencia", f"RD$ {diferencia_pagos:,.2f}")

            # --- DOCUMENTO DE VENTA / Datos Fiscales DGII ---
            st.markdown("### 🏛️ Documento de Venta / Datos Fiscales DGII")
            fact_fiscal_on = st.toggle("Facturación fiscal (e-NCF / NCF)", value=False, key="pos_fact_fiscal_on")
            
            tipo_ncf_ui = "Ninguno"
            rnc_cliente_ui = ""
            nombre_cliente_opcional = ""
            nota_factura = ""
            
            # Inicializar metadatos gubernamentales vacíos
            gub_dep = ""
            gub_oc = ""
            gub_c_nom = ""
            gub_c_corr = ""
            
            if fact_fiscal_on:
                ncf_col1, ncf_col2, ncf_col3 = st.columns(3)
                with ncf_col1:
                    c_lbl1, c_lbl2 = st.columns([5, 1.2])
                    with c_lbl1:
                        tipo_ncf_ui = st.selectbox(
                            "Tipo de Comprobante", 
                            ["E32 – Factura de consumo electrónica", "E31 – Factura de crédito fiscal electrónica", "E45 – Factura Gubernamental electrónica", "B02 (Consumo)", "B01 (Crédito Fiscal)"], 
                            key="pos_tipo_ncf"
                        )
                    with c_lbl2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        st.button("❓", key="btn_pos_ayuda_ncf", help="Explicación DGII en vivo")
                
                # Explicación emergente / dialog si pulsan el botón
                if st.session_state.get("btn_pos_ayuda_ncf") or st.session_state.get("pos_ayuda_abierta"):
                    st.session_state["pos_ayuda_abierta"] = True
                    st.info("""
                    📚 **Guía Rápida de Comprobantes:**
                    *   **E31 / B01 (Crédito Fiscal):** Para empresas/profesionales que deducen gastos e ITBIS. Requiere RNC obligatorio.
                    *   **E32 / B02 (Consumo):** Para personas comunes sin crédito fiscal. RNC opcional.
                    *   **E45 (Gubernamental):** Exclusivo para ventas al Estado (Ministerios, Ayuntamientos). Requiere orden de compra.
                    """)
                    if st.button("Entendido", key="btn_close_ayuda_ncf"):
                        st.session_state["pos_ayuda_abierta"] = False
                        st.rerun()

                # Avisos de validación DGII en vivo
                if "E31" in tipo_ncf_ui or "B01" in tipo_ncf_ui:
                    st.warning("💡 **Recuerda:** Este comprobante requiere:\n✔ RNC del cliente\n✔ Razón social registrada\n✔ Cliente seleccionado")
                elif "E32" in tipo_ncf_ui or "B02" in tipo_ncf_ui:
                    st.success("💡 **Factura de Consumo:** No exige RNC del cliente en una venta normal.")
                elif "E45" in tipo_ncf_ui:
                    st.warning("💡 **Factura Gubernamental:** Verifique que el cliente sea una entidad pública y complete los campos requeridos.")

                if "E31" in tipo_ncf_ui or "B01" in tipo_ncf_ui:
                    # Crédito Fiscal
                    with ncf_col2:
                        rnc_cliente_ui = st.text_input("RNC o Cédula*", key="pos_rnc_cliente", help="Obligatorio para Crédito Fiscal")
                    with ncf_col3:
                        nota_factura = st.text_input("📝 Nota / Observación", key="pos_nota_factura", placeholder="Ej: Sin cambio ni devolución.")
                    
                    st.markdown("##### 🔍 Buscar / Agregar Cliente Fiscal")
                    c_bus1, c_bus2 = st.columns([3, 1])
                    with c_bus1:
                        txt_bus_cliente = st.text_input("Buscar por RNC, Razón Social, Nombre o Teléfono", key="pos_bus_cliente_txt")
                    with c_bus2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        btn_bus_cliente = st.button("🔍 Buscar", key="pos_btn_bus_cliente")
                    
                    with st.expander("➕ Registrar Nuevo Cliente Fiscal", expanded=False):
                        new_rnc = st.text_input("RNC / Cédula*", value=rnc_cliente_ui, key="pos_new_rnc")
                        new_razon = st.text_input("Razón Social / Nombre*", key="pos_new_razon")
                        new_comercial = st.text_input("Nombre Comercial", key="pos_new_comercial")
                        new_tel = st.text_input("Teléfono", key="pos_new_tel")
                        new_email = st.text_input("Correo Electrónico", key="pos_new_email")
                        new_dir = st.text_input("Dirección", key="pos_new_dir")
                        if st.button("💾 Guardar y Seleccionar Cliente", key="pos_btn_add_cliente"):
                            if not new_rnc or not new_razon:
                                st.error("RNC y Razón Social son campos obligatorios (*).")
                            else:
                                if insertar("clientes", {
                                    "rnc": new_rnc,
                                    "nombre": new_razon,
                                    "nombre_comercial": new_comercial,
                                    "telefono": new_tel,
                                    "email": new_email,
                                    "direccion": new_dir
                                }):
                                    st.success(f"✅ Cliente {new_razon} registrado con éxito.")
                                    st.session_state["pos_rnc_cliente"] = new_rnc
                                    st.rerun()
                                    
                    if txt_bus_cliente:
                        df_cli = DATA.get("clientes", pd.DataFrame())
                        if not df_cli.empty:
                            mask = df_cli.astype(str).apply(lambda col: col.str.contains(txt_bus_cliente, case=False, na=False)).any(axis=1)
                            res_cli = df_cli[mask]
                            if not res_cli.empty:
                                for _, r_cli in res_cli.head(5).iterrows():
                                    if st.button(f"👤 {r_cli['nombre']} (RNC: {r_cli.get('rnc', 'N/A')})", key=f"sel_cli_{r_cli['id']}"):
                                        st.session_state["pos_rnc_cliente"] = str(r_cli.get("rnc") or r_cli.get("id"))
                                        st.success(f"Cliente seleccionado: {r_cli['nombre']}")
                                        st.rerun()
                            else:
                                st.info("No se encontraron clientes.")
                
                elif "E45" in tipo_ncf_ui:
                    # Factura Gubernamental E45
                    with ncf_col2:
                        rnc_cliente_ui = st.text_input("RNC Gubernamental*", key="pos_rnc_cliente", help="RNC público obligatorio")
                    with ncf_col3:
                        nota_factura = st.text_input("📝 Nota / Observación", key="pos_nota_factura")
                    
                    st.markdown("##### 🏛️ Metadatos de la Institución Pública (E45)")
                    cg1, cg2 = st.columns(2)
                    with cg1:
                        gub_dep = st.text_input("Dependencia Gubernamental*", key="pos_gub_dep", placeholder="Ej: Departamento de Compras")
                        gub_oc = st.text_input("Orden de Compra*", key="pos_gub_oc", placeholder="Ej: OC-2026-049")
                    with cg2:
                        gub_c_nom = st.text_input("Nombre de Contacto*", key="pos_gub_c_nom", placeholder="Ej: Lic. Mercedes")
                        gub_c_corr = st.text_input("Correo Electrónico de Contacto", key="pos_gub_c_corr", placeholder="Ej: compras@estado.gob.do")
                
                else:
                    # Consumidor Final (E32 / B02)
                    with ncf_col2:
                        nombre_cliente_opcional = st.text_input("Nombre de Cliente (Opcional)", key="pos_cliente_opcional_nom")
                    with ncf_col3:
                        nota_factura = st.text_input("📝 Nota / Observación", key="pos_nota_factura")
                    
                    if nombre_cliente_opcional.strip():
                        cliente_nombre = nombre_cliente_opcional.strip()
            else:
                st.info("ℹ️ Se generará un **Recibo interno** de venta (sin valor fiscal).")
                with st.columns(2)[1]:
                    nota_factura = st.text_input("📝 Nota / Observación", key="pos_nota_factura")
            
            # Asignar número interno o recibo
            if fact_fiscal_on:
                numero_factura_pos = generar_numero_factura_pos()
            else:
                numero_factura_pos = generar_numero_recibo_interno()
            
            es_cuenta_editada = st.session_state.get("pos_cuenta_abierta_id") is not None
            
            if es_cuenta_editada:
                st.markdown(f"### 🔧 Editando Cuenta Abierta: `{st.session_state.get('pos_cuenta_abierta_nombre')}`")
                
                # Elegant session state prefilling for the alias widget to avoid dynamic value override wipes on rerun
                if "pos_edit_cuenta_alias" not in st.session_state or st.session_state.get("pos_cuenta_abierta_nombre") != st.session_state.get("_last_edit_cuenta_nombre"):
                    st.session_state["pos_edit_cuenta_alias"] = st.session_state.get("pos_cuenta_abierta_nombre") or ""
                    st.session_state["_last_edit_cuenta_nombre"] = st.session_state.get("pos_cuenta_abierta_nombre")
                alias_cuenta = st.text_input("Renombrar Alias (Opcional)", value=st.session_state.get("pos_edit_cuenta_alias", ""), key="pos_edit_cuenta_alias")

                # === MODO DOMINO: GESTIÓN DE DEUDORES DIRECTA EN EL CHECKOUT ===
                v_id = st.session_state["pos_cuenta_abierta_id"]
                try:
                    v_resp = supabase.table("ventas").select("*").eq("id", str(v_id)).execute()
                    if v_resp.data:
                        v_row = v_resp.data[0]
                        obs_raw = v_row.get("observacion") or "{}"
                        try:
                            obs_data = json.loads(obs_raw) if isinstance(obs_raw, str) and obs_raw.startswith("{") else {}
                        except Exception:
                            obs_data = {}
                        participantes = obs_data.get("participantes", [])
                        
                        st.markdown("---")
                        st.markdown(f"🎲 **Participantes / Deudores en mesa ({len(participantes)})**")
                        
                        if participantes:
                            for pi, p in enumerate(participantes):
                                pcol1, pcol2, pcol3, pcol4 = st.columns([3, 2, 1, 1])
                                est_icon = "🟢" if p.get("pagado") else "🔴"
                                pcol1.markdown(f"{est_icon} **{p.get('nombre','?')}**")
                                pcol2.markdown(f"RD$ {float(p.get('monto',0)):,.2f}")
                                
                                if p.get("pagado"):
                                    pcol3.markdown("🟢 Pagado")
                                    if pcol4.button("↩️", key=f"pos_btn_reopen_part_{v_id}_{pi}", help="Reabrir / Deshacer pago", use_container_width=True):
                                        try:
                                            monto_part = float(p.get("monto", 0))
                                            supabase.table("ventas_pagos").delete().eq("venta_id", str(v_id)).eq("monto", monto_part).execute()
                                            supabase.table("movimientos_caja").delete().eq("referencia_id", str(v_id)).eq("monto", monto_part).eq("origen", "venta").execute()
                                            
                                            # Registrar en Auditoría
                                            registrar_auditoria_pro(
                                                accion="pago_parcial_revertir",
                                                modulo="POS",
                                                descripcion=f"Pago parcial de RD$ {monto_part:,.2f} revertido para el deudor '{p.get('nombre')}' en cuenta '{v_row.get('cliente_nombre')}'",
                                                nivel_riesgo="medio",
                                                impacto_economico=-monto_part
                                            )
                                        except Exception:
                                            pass
                                        participantes[pi]["pagado"] = False
                                        obs_data["participantes"] = participantes
                                        supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                        invalidar_cache_tabla("ventas")
                                        invalidar_cache_tabla("caja")
                                        DATA.update(cargar_datos())
                                        st.toast(f"Pago de {p.get('nombre')} revertido.", icon="↩️")
                                        st.rerun()
                                else:
                                    with pcol3.popover("💵 Cobrar", use_container_width=True):
                                        met_p = st.selectbox("Método", ["efectivo", "tarjeta", "transferencia"], key=f"pos_pop_met_{v_id}_{pi}")
                                        if st.button("Confirmar", key=f"pos_pop_btn_{v_id}_{pi}", use_container_width=True, type="primary"):
                                            monto_part = float(p.get("monto", 0))
                                            try:
                                                supabase.table("ventas_pagos").insert({
                                                    "venta_id": str(v_id),
                                                    "metodo": met_p,
                                                    "monto": monto_part,
                                                    "usuario": nombre_usuario_actual(),
                                                    "caja_id": str(v_row.get("caja_id")),
                                                    "dia_operativo": ahora_str(),
                                                }).execute()
                                                
                                                supabase.table("movimientos_caja").insert({
                                                    "fecha": datetime.now().isoformat(),
                                                    "dia_operativo": ahora_str(),
                                                    "caja_id": str(v_row.get("caja_id")),
                                                    "tipo_movimiento": "entrada",
                                                    "origen": "venta",
                                                    "referencia_id": str(v_id),
                                                    "metodo_pago": met_p,
                                                    "monto": monto_part,
                                                    "descripcion": f"Pago parcial {p.get('nombre')} en {v_row.get('cliente_nombre')}",
                                                    "usuario": nombre_usuario_actual(),
                                                    "anulado": False,
                                                }).execute()
                                                
                                                registrar_auditoria_pro(
                                                    accion="pago_parcial_participante",
                                                    modulo="POS",
                                                    descripcion=f"Pago parcial de RD$ {monto_part:,.2f} ({met_p}) registrado para {p.get('nombre')} en cuenta '{v_row.get('cliente_nombre')}'",
                                                    nivel_riesgo="bajo",
                                                    impacto_economico=monto_part
                                                )
                                                
                                                participantes[pi]["pagado"] = True
                                                obs_data["participantes"] = participantes
                                                supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                                invalidar_cache_tabla("ventas")
                                                invalidar_cache_tabla("caja")
                                                DATA.update(cargar_datos())
                                                st.toast(f"¡Pago de {p.get('nombre')} registrado!", icon="✅")
                                                st.rerun()
                                            except Exception as ex:
                                                st.error(f"Error: {ex}")
                                                
                                    if pcol4.button("🗑️", key=f"btn_pos_del_part_{v_id}_{pi}", use_container_width=True):
                                        participantes.pop(pi)
                                        obs_data["participantes"] = participantes
                                        supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                        DATA.update(cargar_datos())
                                        st.rerun()
                        else:
                            st.caption("No hay deudores/participantes asignados.")
                            
                        # Permitir agregar deudores directo en el POS
                        st.markdown("**Agregar deudor rápido:**")
                        npa1, npa2, npa3 = st.columns([3, 2, 1])
                        n_n_p = npa1.text_input("Nombre", key=f"pos_nuevo_p_nombre_{v_id}", placeholder="Ej: Pedro...")
                        n_m_p = npa2.number_input("Monto (RD$)", min_value=0.0, step=50.0, key=f"pos_nuevo_p_monto_{v_id}")
                        if npa3.button("➕", key=f"pos_btn_add_part_{v_id}", use_container_width=True):
                            if not n_n_p.strip():
                                st.error("Debes indicar un nombre.")
                            elif n_m_p <= 0:
                                st.error("Monto mayor a 0.")
                            else:
                                participantes.append({"nombre": n_n_p.strip(), "monto": float(n_m_p), "pagado": False})
                                obs_data["participantes"] = participantes
                                supabase.table("ventas").update({"observacion": json.dumps(obs_data, ensure_ascii=False)}).eq("id", str(v_id)).execute()
                                invalidar_cache_tabla("ventas")
                                DATA.update(cargar_datos())
                                st.rerun()
                        st.markdown("---")
                except Exception:
                    pass
                
                if not pagos_cuadran:
                    st.info(f"💡 **Monto pendiente a saldar hoy: RD$ {total_real_pendiente:,.2f}**. Registra cómo se pagará este monto usando las casillas de Efectivo, Tarjeta, etc., para habilitar el botón **Cobrar y Cerrar Cuenta**.")

                ec_1, ec_2, ec_3 = st.columns(3)
                with ec_1:
                    guardar_cambios = st.button("💾 Guardar Cambios", key="btn_pos_guardar_cambios_abierta")
                with ec_2:
                    cobrar_cerrar = st.button("💳 Cobrar y Cerrar Cuenta", key="btn_pos_cobrar_cerrar_abierta", disabled=not pagos_cuadran)
                with ec_3:
                    descartar_cambios = st.button("❌ Descartar Cambios", key="btn_pos_descartar_abierta")
                    
                if descartar_cambios:
                    st.session_state["pos_cuenta_abierta_id"] = None
                    st.session_state["pos_cuenta_abierta_nombre"] = None
                    st.session_state["pos_carrito"] = []
                    st.session_state["pos_nuevo_cuenta_participantes"] = []
                    st.session_state.pop("pos_edit_cuenta_alias", None)
                    st.session_state.pop("pos_new_cuenta_alias", None)
                    st.rerun()
                    
                proceder = guardar_cambios or cobrar_cerrar
                estado_final = "abierta" if guardar_cambios else "completada"
                es_cobro = cobrar_cerrar
            else:
                default_alias = cliente_nombre if cliente_nombre != "Venta general" else f"Cuenta {numero_factura_pos}"
                
                # Elegant session state prefilling for the new alias widget to avoid dynamic value override wipes on rerun
                if "pos_new_cuenta_alias" not in st.session_state or st.session_state.get("_last_cliente_nombre_pos") != cliente_nombre:
                    st.session_state["pos_new_cuenta_alias"] = default_alias
                    st.session_state["_last_cliente_nombre_pos"] = cliente_nombre
                alias_cuenta = st.text_input("Alias / Nombre de la cuenta (Solo para Guardar como Cuenta Abierta)", value=st.session_state.get("pos_new_cuenta_alias", ""), key="pos_new_cuenta_alias")
                
                if "pos_nuevo_cuenta_participantes" not in st.session_state:
                    st.session_state["pos_nuevo_cuenta_participantes"] = []
                
                # Gestión de participantes para nueva cuenta abierta
                with st.expander(f"👥 Participantes de esta nueva cuenta ({len(st.session_state['pos_nuevo_cuenta_participantes'])})", expanded=True):
                    if st.session_state["pos_nuevo_cuenta_participantes"]:
                        for pi, p in enumerate(st.session_state["pos_nuevo_cuenta_participantes"]):
                            pcol1, pcol2, pcol3 = st.columns([3, 2, 1])
                            pcol1.markdown(f"👤 **{p.get('nombre')}**")
                            pcol2.markdown(f"RD$ {float(p.get('monto', 0)):,.2f}")
                            if pcol3.button("🗑️", key=f"btn_pos_new_del_part_{pi}", use_container_width=True):
                                st.session_state["pos_nuevo_cuenta_participantes"].pop(pi)
                                st.rerun()
                    else:
                        st.caption("No hay participantes asignados aún.")
                    
                    st.markdown("**Agregar participante:**")
                    npa1, npa2, npa3 = st.columns([3, 2, 1])
                    n_n_p = npa1.text_input("Nombre de la persona", key="pos_nuevo_p_nombre_temp", placeholder="Ej: Juan...")
                    n_m_p = npa2.number_input("Monto asignado (RD$)", min_value=0.0, step=50.0, key="pos_nuevo_p_monto_temp")
                    if npa3.button("➕ Agregar", key="pos_btn_add_part_temp", use_container_width=True):
                        if not n_n_p.strip():
                            st.error("Indique un nombre.")
                        elif n_m_p <= 0:
                            st.error("Monto mayor a 0.")
                        else:
                            st.session_state["pos_nuevo_cuenta_participantes"].append({"nombre": n_n_p.strip(), "monto": float(n_m_p), "pagado": False})
                            st.rerun()
                
                # Popover para apertura de gaveta sin venta
                with st.popover("🔑 Abrir Gaveta (Sin Venta)", use_container_width=True):
                    motivo_ap = st.text_input("Indique el motivo de la apertura", placeholder="Ej. Cambio de menudo", key="pos_motivo_apertura_gav")
                    if st.button("⚡ Confirmar Apertura de Caja", key="pos_btn_trigger_apertura_gav", use_container_width=True):
                        if not motivo_ap:
                            st.error("Debe indicar un motivo.")
                        else:
                            gatillar_apertura_gaveta(motivo_ap)
                            st.rerun()

                ev_1, ev_2, ev_3 = st.columns(3)
                with ev_1:
                    proceder_venta_normal = st.button("🖨️ Cobrar e Imprimir", key="btn_pos_cobrar", disabled=not pagos_cuadran)
                with ev_2:
                    proceder_venta_solo_cobrar = st.button("💳 Solo Cobrar", key="btn_pos_cobrar_solo", disabled=not pagos_cuadran)
                with ev_3:
                    proceder_cuenta_abierta = st.button("📂 Guardar como Cuenta Abierta", key="btn_pos_guardar_como_abierta")
                    
                proceder = proceder_venta_normal or proceder_venta_solo_cobrar or proceder_cuenta_abierta
                estado_final = "completada" if (proceder_venta_normal or proceder_venta_solo_cobrar) else "abierta"
                es_cobro = proceder_venta_normal or proceder_venta_solo_cobrar
                


            if proceder:
                st.session_state["mostrar_modal_busqueda"] = False
                if 'alias_cuenta' not in locals():
                    alias_cuenta = st.session_state.get("pos_new_cuenta_alias", st.session_state.get("pos_cuenta_abierta_nombre", ""))
                if 'proceder_venta_normal' not in locals():
                    proceder_venta_normal = False
                if es_cobro and faltante > 0.001:
                    st.error("No puedes cobrar hasta que los pagos cuadren con el total real de la venta.")
                    st.stop()
                if es_cobro and pago_credito > 0:
                    if not cliente_id or cliente_nombre == "Venta general":
                        st.error("🚫 **Para registrar una venta a crédito debes asignar un cliente registrado de la base de datos.** Activa 'Asignar cliente' y selecciónalo.")
                        st.stop()
                if not es_cobro and not es_cuenta_editada:
                    # Validación: no se puede guardar cuenta abierta sin identificación
                    nombre_alias_final = alias_cuenta.strip() if alias_cuenta else ""
                    nombre_cliente_final = cliente_nombre if cliente_nombre != "Venta general" else ""
                    if not nombre_alias_final and not nombre_cliente_final:
                        st.error("🚫 **No puedes guardar una Cuenta Abierta sin identificar al cliente.** Escribe un Alias o selecciona un cliente antes de guardar.")
                        st.stop()
                
                # Guardamos variables de estado en caso de que cambien en el rerun
                if True:
                    try:
                            # 1. Validaciones previas de NCF
                            tipo_comp = ""
                            if estado_final == "completada" and fact_fiscal_on and tipo_ncf_ui != "Ninguno":
                                tipo_comp = tipo_ncf_ui.split(" ")[0]
                                if tipo_comp in ["E31", "B01"] and not rnc_cliente_ui.strip():
                                    st.error("🚫 Para emitir Crédito Fiscal debes ingresar el RNC del cliente.")
                                    st.stop()
                                if tipo_comp == "E45":
                                    if not rnc_cliente_ui.strip() or not gub_dep.strip() or not gub_oc.strip() or not gub_c_nom.strip():
                                        st.error("🚫 Para emitir Factura Gubernamental (E45) debes ingresar RNC, Dependencia, Orden de Compra y Nombre de Contacto.")
                                        st.stop()

                            # 2. Construir items payload
                            items_payload = []
                            for item in carrito:
                                p_id = str(item["producto_id"])
                                prod_rows = productos_df[productos_df["id"].astype(str) == p_id]
                                prod = prod_rows.iloc[0] if not prod_rows.empty else {}
                                costo_unit, movimientos_fifo = obtener_costo_fifo(prod, float(item["cantidad"]))
                                total_linea = float(item["cantidad"]) * float(item["precio_unitario"])
                                itbis_m = float(item.get("itbis_monto", 0.0))
                                items_payload.append({
                                    "producto_id": p_id,
                                    "codigo": item["codigo"],
                                    "producto": nombre_item(item),
                                    "cantidad": float(item["cantidad"]),
                                    "precio_unitario": float(item["precio_unitario"]),
                                    "itbis_gravado": bool(item.get("itbis_gravado", True)),
                                    "itbis_tasa": float(item.get("itbis_tasa", 18.0)),
                                    "itbis_monto": itbis_m,
                                    "subtotal": float(item.get("subtotal", total_linea - itbis_m)),
                                    "total_linea": total_linea,
                                    "costo_unitario": float(costo_unit),
                                    "ganancia_linea": total_linea - (float(item["cantidad"]) * float(costo_unit))
                                })
                            
                            # 3. Construir pagos payload
                            efectivo_neto = round(max(float(pago_efectivo or 0) - float(cambio or 0), 0.0), 2)
                            pagos_payload = [
                                {"metodo": "efectivo", "monto": efectivo_neto},
                                {"metodo": "transferencia", "monto": float(pago_transferencia or 0)},
                                {"metodo": "tarjeta", "monto": float(pago_tarjeta or 0)},
                                {"metodo": "credito", "monto": float(pago_credito or 0)}
                            ]

                            # 4. Asientos contables
                            metodo_pago_final = "abierta" if estado_final == "abierta" else ("mixto" if sum(v > 0 for v in [pago_efectivo, pago_transferencia, pago_tarjeta, pago_credito]) > 1 else ("efectivo" if pago_efectivo > 0 else "transferencia" if pago_transferencia > 0 else "tarjeta" if pago_tarjeta > 0 else "credito"))
                            if metodo_pago_final in ["efectivo"]:
                                cuenta_debito_cod, cuenta_debito_nom = "1101", "Efectivo / Caja"
                            elif metodo_pago_final in ["transferencia", "tarjeta"]:
                                cuenta_debito_cod, cuenta_debito_nom = "1102", "Banco / Depósito"
                            elif metodo_pago_final in ["credito"]:
                                cuenta_debito_cod, cuenta_debito_nom = "1201", "Cuentas por Cobrar"
                            else:
                                cuenta_debito_cod, cuenta_debito_nom = "1101", "Efectivo / Caja"

                            total_v = float(total_real_venta)
                            itbis_v = float(total_itbis_neto)
                            ingreso_base = total_v - itbis_v if itbis_v > 0 else total_v

                            asientos_payload = []
                            if total_v > 0:
                                asientos_payload.append({
                                    "cuenta_codigo": cuenta_debito_cod,
                                    "cuenta_nombre": cuenta_debito_nom,
                                    "tipo_cuenta": "activo",
                                    "debito": total_v,
                                    "credito": 0.0,
                                    "descripcion": f"Cobro Venta POS {numero_factura_pos}"
                                })
                            if ingreso_base > 0:
                                asientos_payload.append({
                                    "cuenta_codigo": "4101",
                                    "cuenta_nombre": "Ingresos por Ventas",
                                    "tipo_cuenta": "ingreso",
                                    "debito": 0.0,
                                    "credito": ingreso_base,
                                    "descripcion": f"Ingreso Venta POS {numero_factura_pos}"
                                })
                            if itbis_v > 0:
                                asientos_payload.append({
                                    "cuenta_codigo": "2102",
                                    "cuenta_nombre": "ITBIS por Pagar",
                                    "tipo_cuenta": "pasivo",
                                    "debito": 0.0,
                                    "credito": itbis_v,
                                    "descripcion": f"ITBIS por Pagar Venta POS {numero_factura_pos}"
                                })

                            # 5. Armar payload final
                            payload_unificado = {
                                "total": float(total_real_venta),
                                "subtotal": float(subtotal_neto),
                                "itbis_total": float(total_itbis_neto),
                                "subtotal_gravado": float(subtotal_gravado_neto),
                                "subtotal_exento": float(subtotal_exento_neto),
                                "es_factura_fiscal": fact_fiscal_on,
                                "tipo_documento": tipo_comp if fact_fiscal_on else "Recibo interno",
                                "tipo_comprobante": tipo_comp if fact_fiscal_on else None,
                                "rnc_cliente": rnc_cliente_ui.strip() if fact_fiscal_on else None,
                                "cliente_id": cliente_id,
                                "cliente_nombre": alias_cuenta if (estado_final == "abierta" and alias_cuenta) else cliente_nombre,
                                "usuario": nombre_usuario_actual(),
                                "dia_operativo": ahora_str(),
                                "caja_id": str(caja_activa.get("id")),
                                "numero_factura": numero_factura_pos,
                                "estado": estado_final,
                                "observacion": json.dumps({"participantes": st.session_state.get("pos_nuevo_cuenta_participantes", []), "descuento": descuento_global, "recargo": 0, "nota_factura": nota_factura}),
                                "metodo_pago": metodo_pago_final,
                                "empresa_id": obtener_tenant_actual(),
                                "items": items_payload,
                                "pagos": pagos_payload,
                                "asientos": asientos_payload
                            }

                            if tipo_comp == "E45":
                                payload_unificado["gubernamental_dependencia"] = gub_dep.strip()
                                payload_unificado["gubernamental_orden_compra"] = gub_oc.strip()
                                payload_unificado["gubernamental_contacto_nombre"] = gub_c_nom.strip()
                                payload_unificado["gubernamental_contacto_correo"] = gub_c_corr.strip()

                            # 6. Ejecución del RPC transaccional
                            rpc_res = guardar_venta_rpc(payload_unificado)
                            if not rpc_res.get("success"):
                                st.error(f"❌ Error al guardar la venta: {rpc_res.get('error')}")
                                st.stop()
                            
                            venta_id = rpc_res.get("venta_id")
                            ncf_final = rpc_res.get("ncf")
                            factura_final = numero_factura_pos

                            # Registrar en session state para el ticket
                            if es_cobro:
                                st.session_state["pos_post_venta"] = {
                                    "venta_id": str(venta_id),
                                    "numero_factura": factura_final,
                                    "total": float(total_real_venta),
                                    "total_real": float(total_real_venta),
                                    "subtotal": float(subtotal_neto),
                                    "itbis_total": float(total_itbis_neto),
                                    "tipo_comprobante": tipo_comp if fact_fiscal_on else "",
                                    "rnc_cliente": rnc_cliente_ui.strip() if fact_fiscal_on else "",
                                    "cambio": float(cambio),
                                    "cliente_nombre": payload_unificado["cliente_nombre"],
                                    "metodo_pago": metodo_pago_final,
                                    "ncf": ncf_final,
                                    "nota": nota_factura or "",
                                    "items": [dict(x) for x in carrito],
                                }

                            st.session_state["pos_cuenta_abierta_id"] = None
                            st.session_state["pos_cuenta_abierta_nombre"] = None
                            st.session_state["pos_nuevo_cuenta_participantes"] = []
                            st.session_state.pop("pos_edit_cuenta_alias", None)
                            st.session_state.pop("pos_new_cuenta_alias", None)
                            st.session_state["pos_carrito"] = []
                            
                            if not es_cobro:
                                st.session_state["_pos_ir_a_seccion"] = "📂 Cuentas Abiertas Activas"
                            else:
                                st.session_state["_pos_ir_a_seccion"] = "🛒 Carrito de Ventas"
                            
                            invalidar_cache_tabla("ventas")
                            invalidar_cache_tabla("productos")
                            invalidar_cache_tabla("caja")
                            DATA.update(cargar_datos())
                            
                            if es_cobro and not proceder_venta_normal:
                                st.toast("✅ Venta registrada (sin imprimir).", icon="💵")
                            st.rerun()
                    except Exception as exc:
                        import traceback
                        traceback.print_exc()
                        st.error(f"❌ Error al procesar la venta: {exc}")
                        st.stop()
        else:
            st.info("Carrito vacío.")






def render_ventas():
    st.title("💰 Ventas")

    puede_gestionar_ventas = puede_editar_ventas() or puede_anular_ventas() or puede_eliminar_ventas()
    puede_ver_utilidad = puede_ver_utilidad_global()

    if puede_editar_ventas():
        with st.expander("📥 Subir Excel / CSV de ventas"):
            st.write("Columnas esperadas: fecha, total, metodo. Observación opcional.")
            archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_ventas")
            if archivo is not None and st.button("Cargar ventas"):
                df = leer_archivo_subido(archivo)
                faltan = [c for c in ["fecha", "total", "metodo"] if c not in df.columns]
                if faltan:
                    st.error(f"Faltan columnas: {faltan}")
                else:
                    count = 0
                    for _, row in df.iterrows():
                        fecha = parsear_fecha(row["fecha"])
                        total = limpiar_numero(row["total"]) or 0
                        metodo = limpiar_texto(row["metodo"])
                        observacion = limpiar_texto(row["observacion"]) if "observacion" in df.columns else ""
                        if fecha:
                            insertar(
                                "ventas",
                                {
                                    "fecha": fecha,
                                    "total": float(total),
                                    "metodo": metodo,
                                    "metodo_pago": metodo,
                                    "observacion": observacion,
                                    "usuario": nombre_usuario_actual(),
                                    "cliente_nombre": "Venta general",
                                    "anulado": False,
                                },
                            )
                            count += 1
                    st.success(f"Se cargaron {count} ventas.")
                    st.rerun()

    if not es_cajera():
        with st.expander("➕ Agregar venta manual", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                fecha = st.date_input("Fecha", value=date.today(), key="venta_fecha")
            with c2:
                total = st.number_input("Total", min_value=0.0, step=1.0, key="venta_total")
            with c3:
                metodo = st.selectbox("Método", ["efectivo", "transferencia", "tarjeta"], key="venta_metodo")
            observacion = st.text_input("Observación", key="venta_obs")

            if st.button("Guardar venta"):
                if insertar(
                    "ventas",
                    {
                        "fecha": str(fecha),
                        "total": float(total),
                        "metodo": metodo,
                        "metodo_pago": metodo,
                        "observacion": observacion,
                        "usuario": nombre_usuario_actual(),
                        "cliente_nombre": "Venta general",
                        "anulado": False,
                    },
                ):
                    st.success("Venta guardada.")
                    st.rerun()


    # Lectura robusta: sin filtros cerrados para no ocultar ventas registradas
    try:
        tenant = obtener_tenant_actual()
        df = _leer_tabla_de_supabase("ventas", order_by="fecha", tenant=tenant)
    except Exception:
        df = leer_tabla("ventas")

    if not df.empty:
        if "id" not in df.columns and "identificación" in df.columns:
            df["id"] = df["identificación"]
        if "identificacion" not in df.columns and "identificación" in df.columns:
            df["identificacion"] = df["identificación"]
        if "identificación" not in df.columns and "identificacion" in df.columns:
            df["identificación"] = df["identificacion"]
        if "metodo" not in df.columns and "metodo_pago" in df.columns:
            df["metodo"] = df["metodo_pago"]
        if "metodo_pago" not in df.columns and "metodo" in df.columns:
            df["metodo_pago"] = df["metodo"]
        if "cliente_nombre" not in df.columns:
            df["cliente_nombre"] = "Venta general"
        if "usuario" not in df.columns:
            df["usuario"] = ""
        if "anulado" not in df.columns:
            df["anulado"] = False
        if "motivo_anulacion" not in df.columns:
            df["motivo_anulacion"] = ""
        if "ganancia_bruta" not in df.columns:
            df["ganancia_bruta"] = 0.0
        if "ganancia_bruta_manual" not in df.columns:
            df["ganancia_bruta_manual"] = 0.0

        d1, d2 = rango_fechas_ui("ventas")
        try:
            df["fecha"] = pd.to_datetime(df["fecha"], format="ISO8601", errors="coerce")
        except Exception:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        df = df[(df["fecha"] >= pd.to_datetime(d1)) & (df["fecha"] <= pd.to_datetime(d2) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))]

        txt = st.text_input("Buscar venta (puedes buscar por número de factura, cliente, usuario o por producto vendido)", key="buscar_ventas")
        metodo_filtro = st.selectbox(
            "Filtrar por método",
            ["Todos", "efectivo", "transferencia", "tarjeta", "credito", "mixto"],
            key="ventas_filtro_metodo",
        )

        if txt:
            # 1. Búsqueda normal por campos de la venta
            mask_normal = df.astype(str).apply(lambda col: col.str.contains(txt, case=False, na=False)).any(axis=1)
            
            # 2. Búsqueda inteligente por producto en detalle_venta
            venta_ids_by_prod = set()
            try:
                coincidencias_det = supabase.table("detalle_venta").select("venta_id").ilike("producto", f"%{txt}%").execute()
                venta_ids_by_prod = {str(item.get("venta_id")) for item in (coincidencias_det.data or []) if item.get("venta_id")}
            except Exception:
                try:
                    df_det_local = DATA.get("detalle_venta")
                    if df_det_local is None or df_det_local.empty:
                        df_det_local = leer_tabla("detalle_venta")
                    if df_det_local is not None and not df_det_local.empty:
                        mask_p = df_det_local["producto"].astype(str).str.contains(txt, case=False, na=False)
                        venta_ids_by_prod = set(df_det_local[mask_p]["venta_id"].dropna().astype(str).unique())
                except Exception:
                    pass
            
            mask_prod = df.apply(lambda row: str(row.get("id") or row.get("identificación") or row.get("identificacion") or "") in venta_ids_by_prod, axis=1)
            df = df[mask_normal | mask_prod]

        col_metodo = "metodo_pago" if "metodo_pago" in df.columns else "metodo" if "metodo" in df.columns else None
        if metodo_filtro != "Todos" and col_metodo:
            df = df[df[col_metodo].astype(str).str.lower() == metodo_filtro.lower()]

        if not puede_ver_todas_ventas():
            usuario_actual = normalizar_texto(nombre_usuario_actual())
            if "usuario" in df.columns:
                df = df[df["usuario"].astype(str).apply(normalizar_texto) == usuario_actual]
            elif "cajera" in df.columns:
                df = df[df["cajera"].astype(str).apply(normalizar_texto) == usuario_actual]
            else:
                df = df.iloc[0:0]
            st.caption("Solo puedes ver tus ventas. No tienes permiso para ver las de otros usuarios.")

        total_vendido = float(pd.to_numeric(df.get("total", 0), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
        utilidad_visible = float(pd.to_numeric(df.get("ganancia_bruta", 0), errors="coerce").fillna(0).sum()) if not df.empty else 0.0
        metric_cols = st.columns(3) if puede_ver_utilidad else st.columns(2)
        metric_cols[0].metric("Ventas registradas", int(len(df.index)))
        metric_cols[1].metric("Total vendido", f"RD$ {total_vendido:,.2f}")
        if puede_ver_utilidad:
            metric_cols[2].metric("Utilidad bruta visible", f"RD$ {utilidad_visible:,.2f}")

        df_show = df.copy().sort_values("fecha", ascending=False)
        if not df_show.empty:
            df_show["factura"] = df_show.apply(numero_factura_visible, axis=1)
            
            # Obtener los nombres de los productos vendidos en estas facturas
            detalles_productos_map = {}
            ids_lista = []
            for col_id in ["id", "identificación", "identificacion"]:
                if col_id in df_show.columns:
                    ids_lista.extend(df_show[col_id].dropna().astype(str).unique().tolist())
            ids_lista = list(set(ids_lista))
            if ids_lista:
                try:
                    detalles_data = []
                    for i in range(0, len(ids_lista), 100):
                        lote = ids_lista[i:i+100]
                        resp_det = supabase.table("detalle_venta").select("venta_id, producto").in_("venta_id", lote).execute()
                        detalles_data.extend(resp_det.data or [])
                    
                    for d in detalles_data:
                        v_id = str(d.get("venta_id"))
                        prod = str(d.get("producto") or "")
                        if v_id and prod:
                            if v_id not in detalles_productos_map:
                                detalles_productos_map[v_id] = []
                            if prod not in detalles_productos_map[v_id]:
                                detalles_productos_map[v_id].append(prod)
                except Exception:
                    try:
                        df_det_local = DATA.get("detalle_venta")
                        if df_det_local is None or df_det_local.empty:
                            df_det_local = leer_tabla("detalle_venta")
                        if df_det_local is not None and not df_det_local.empty:
                            df_det_filt = df_det_local[df_det_local["venta_id"].astype(str).isin(ids_lista)]
                            for _, r in df_det_filt.iterrows():
                                v_id = str(r.get("venta_id"))
                                prod = str(r.get("producto") or "")
                                if v_id and prod:
                                    if v_id not in detalles_productos_map:
                                        detalles_productos_map[v_id] = []
                                    if prod not in detalles_productos_map[v_id]:
                                        detalles_productos_map[v_id].append(prod)
                    except Exception:
                        pass
            
            def obtener_productos_string(row):
                v_id = str(row.get("id") or row.get("identificación") or row.get("identificacion") or "")
                prods = detalles_productos_map.get(v_id, [])
                return ", ".join(prods) if prods else "N/A"
            
            df_show["productos"] = df_show.apply(obtener_productos_string, axis=1)

        columnas_preferidas = [
            c
            for c in [
                "numero_factura",
                "factura",
                "fecha",
                "productos",
                "total",
                "subtotal",
                "descuento",
                "recargo",
                "metodo_pago",
                "metodo",
                "cliente_nombre",
                "usuario",
                "anulado",
                "motivo_anulacion",
                "ganancia_bruta",
                "ganancia_bruta_manual",
            ]
            if c in df_show.columns
        ]
        if not puede_ver_utilidad:
            columnas_preferidas = [c for c in columnas_preferidas if c not in ["ganancia_bruta", "ganancia_bruta_manual"]]
        st.dataframe(df_show[columnas_preferidas] if columnas_preferidas else df_show, use_container_width=True)
        if puede_ver_todas_ventas():
            descargar_archivos(df_show[columnas_preferidas] if columnas_preferidas else df_show, "ventas")

        # =========================================================
        # BLOQUE NUEVO: EDITAR VENTA COMPLETA
        # PÉGALO DEBAJO DE:
        # st.dataframe(df[columnas_preferidas] if columnas_preferidas else df, use_container_width=True)
        # descargar_archivos(df, "ventas")
        # DENTRO DEL MÓDULO: elif menu == "Ventas":
        # =========================================================
        if puede_gestionar_ventas:
            st.subheader("✏️ Editar venta completa")

            ventas_visibles = df.copy()
            if not ventas_visibles.empty:
                opciones_venta = []
                mapa_ventas = {}

                for _, row in ventas_visibles.iterrows():
                    venta_id = row.get("id") or row.get("identificación")
                    etiqueta = f"{venta_id} | {row.get('fecha')} | Total RD$ {float(limpiar_numero(row.get('total')) or 0):,.2f}"
                    opciones_venta.append(etiqueta)
                    mapa_ventas[etiqueta] = row

                venta_sel = st.selectbox("Selecciona la venta a editar", opciones_venta, key="venta_editar_sel")
                venta_row = mapa_ventas[venta_sel]
                venta_id = venta_row.get("id") or venta_row.get("identificación")

                has_ncf = bool(str(venta_row.get("ncf") or "").strip())
                if has_ncf:
                    st.warning("⚠️ No se puede modificar el detalle de una factura con NCF oficial. Para realizar correcciones, debe anular la venta y generar una Nota de Crédito (E34).")
                    detalle_df = pd.DataFrame()
                else:
                    detalle_resp = supabase.table("detalle_venta").select("*").eq("venta_id", str(venta_id)).execute()
                    detalle_data = detalle_resp.data or []
                    detalle_df = pd.DataFrame(detalle_data)

                if detalle_df.empty and not has_ncf:
                    st.warning("Esta venta no tiene detalle para editar.")
                elif not detalle_df.empty:
                    productos_df = DATA["productos"].copy()
                    productos_lista = productos_df["nombre"].astype(str).tolist() if not productos_df.empty and "nombre" in productos_df.columns else []

                    st.write("### 🧾 Editar productos de la venta")
                    st.caption("Aquí puedes cambiar cantidad, quitar productos o agregar uno nuevo antes de guardar la edición.")
                    nuevos_items = []

                    for i, item in detalle_df.iterrows():
                        producto_actual = str(item.get("producto") or item.get("nombre") or "")
                        precio_original = float(limpiar_numero(item.get("precio_unitario") or item.get("precio")) or 0)
                        costo_original = float(limpiar_numero(item.get("costo_unitario") or item.get("costo")) or 0)
                        desc_original = float(limpiar_numero(item.get("descuento")) or 0)
                        cant_original = float(limpiar_numero(item.get("cantidad")) or 0)

                        c1, c2, c3, c4 = st.columns([5, 2, 2, 1])
                        with c1:
                            st.markdown(f"**{producto_actual}**")
                        with c2:
                            cantidad_nueva = st.number_input(
                                "Cantidad",
                                min_value=0.0,
                                step=1.0,
                                value=cant_original,
                                key=f"edit_cantidad_{i}",
                                label_visibility="collapsed",
                            )
                        linea_total_vista = max((float(cantidad_nueva) * precio_original) - desc_original, 0)
                        with c3:
                            st.markdown(f"**RD$ {linea_total_vista:,.2f}**")
                        with c4:
                            eliminar_linea = st.checkbox("Quitar", value=False, key=f"edit_eliminar_{i}")

                        with st.expander(f"⚙️ Opciones avanzadas de {producto_actual}", expanded=False):
                            precio_nuevo = st.number_input(
                                "Precio unitario",
                                min_value=0.0,
                                step=1.0,
                                value=precio_original,
                                key=f"edit_precio_{i}"
                            )
                            costo_nuevo = st.number_input(
                                "Costo unitario",
                                min_value=0.0,
                                step=1.0,
                                value=costo_original,
                                key=f"edit_costo_{i}"
                            )
                            descuento_nuevo = st.number_input(
                                "Descuento de esta línea",
                                min_value=0.0,
                                step=1.0,
                                value=desc_original,
                                key=f"edit_desc_{i}"
                            )

                        if not eliminar_linea and cantidad_nueva > 0:
                            linea_total = max((cantidad_nueva * precio_nuevo) - descuento_nuevo, 0)
                            ganancia_linea = (precio_nuevo - costo_nuevo) * cantidad_nueva - descuento_nuevo

                            nuevos_items.append({
                                "producto_id": item.get("producto_id"),
                                "producto": producto_actual,
                                "codigo": item.get("código") or item.get("codigo"),
                                "cantidad": float(cantidad_nueva),
                                "precio_unitario": float(precio_nuevo),
                                "costo_unitario": float(costo_nuevo),
                                "descuento": float(descuento_nuevo),
                                "recargo": float(limpiar_numero(item.get("recargo")) or 0),
                                "total_linea": float(linea_total),
                                "ganancia_linea": float(ganancia_linea),
                                "usuario": nombre_usuario_actual(),
                                "fecha": ahora_str(),
                                "anulado": False,
                                "motivo_anulacion": "",
                            })

                    st.markdown("---")
                    st.write("### ➕ Agregar producto nuevo a esta venta")
                    if productos_lista:
                        cna1, cna2, cna3, cna4 = st.columns([4, 2, 2, 1])
                        with cna1:
                            prod_nuevo_nombre = st.selectbox("Producto nuevo", [""] + productos_lista, key="venta_nuevo_producto")
                        with cna2:
                            prod_nueva_cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, value=0.0, key="venta_nueva_cantidad")
                        precio_preview = 0.0
                        with cna3:
                            if prod_nuevo_nombre:
                                prod_tmp = get_producto_por_nombre(prod_nuevo_nombre)
                                if prod_tmp is not None:
                                    precio_preview = float(limpiar_numero(prod_tmp.get("precio")) or 0)
                            st.markdown(f"**RD$ {float(prod_nueva_cantidad or 0) * precio_preview:,.2f}**")
                        with cna4:
                            agregar_nuevo = st.checkbox("Agregar", key="venta_agregar_nuevo")

                        if agregar_nuevo and prod_nuevo_nombre and prod_nueva_cantidad > 0:
                            prod_row = get_producto_por_nombre(prod_nuevo_nombre)
                            if prod_row is not None:
                                precio_nuevo = float(limpiar_numero(prod_row.get("precio")) or 0)
                                costo_nuevo = float(limpiar_numero(prod_row.get("costo")) or 0)
                                linea_total = prod_nueva_cantidad * precio_nuevo
                                ganancia_linea = (precio_nuevo - costo_nuevo) * prod_nueva_cantidad

                                nuevos_items.append({
                                    "producto_id": prod_row.get("id"),
                                    "producto": prod_nuevo_nombre,
                                    "codigo": prod_row.get("codigo"),
                                    "cantidad": float(prod_nueva_cantidad),
                                    "precio_unitario": float(precio_nuevo),
                                    "costo_unitario": float(costo_nuevo),
                                    "descuento": 0.0,
                                    "recargo": 0.0,
                                    "total_linea": float(linea_total),
                                    "ganancia_linea": float(ganancia_linea),
                                    "usuario": nombre_usuario_actual(),
                                    "fecha": ahora_str(),
                                    "anulado": False,
                                    "motivo_anulacion": "",
                                })

                    total_preview_edit = sum(float(x.get("total_linea") or x.get("linea_total") or 0) for x in nuevos_items)
                    st.markdown(f"### Total editado: RD$ {total_preview_edit:,.2f}")

                    st.write("### Método de pago")
                    metodo_pago_nuevo = st.selectbox(
                        "Método de pago nuevo",
                        ["efectivo", "transferencia", "tarjeta", "credito", "mixto"],
                        index=["efectivo", "transferencia", "tarjeta", "credito", "mixto"].index(
                            str(venta_row.get("metodo_pago") or "efectivo").lower()
                        ) if str(venta_row.get("metodo_pago") or "efectivo").lower() in ["efectivo", "transferencia", "tarjeta", "credito", "mixto"] else 0,
                        key="venta_edit_metodo_pago"
                    )

                    if st.button("💾 Guardar edición completa", key="btn_guardar_edicion_completa"):
                        try:
                            # 1. devolver inventario viejo y registrar movimientos usando helper oficial
                            revertir_inventario_de_venta(venta_id)

                            # 2. borrar detalle viejo
                            supabase.table("detalle_venta").delete().eq("venta_id", str(venta_id)).execute()

                            # 3. insertar detalle nuevo y descontar inventario nuevo
                            nuevo_total = 0.0
                            nueva_ganancia = 0.0

                            for item in nuevos_items:
                                item_insert = item.copy()
                                item_insert["venta_id"] = str(venta_id)
                                item_insert["empresa_id"] = obtener_tenant_actual()
                                supabase.table("detalle_venta").insert(json_safe_payload(item_insert)).execute()

                                prod_id = item.get("producto_id")
                                cant_new = float(item.get("cantidad") or 0)
                                total_l = float(item.get("total_linea") or 0)
                                nuevo_total += total_l
                                nueva_ganancia += float(item.get("ganancia_linea") or 0)

                                if prod_id:
                                    prod = refrescar_producto_por_id(prod_id)
                                    if prod is not None:
                                        stock_actual = float(obtener_existencia_producto(prod))
                                        nueva_cant = max(stock_actual - cant_new, 0.0)
                                        actualizar_existencia_producto(prod, nueva_cant)
                                        
                                        prod_sync = refrescar_producto_por_id(prod_id)
                                        if prod_sync is None:
                                            prod_sync = prod
                                        sincronizar_producto_inventario(prod_sync, ahora_str(), f"Salida por edicion venta {venta_id}")
                                        registrar_movimiento_inventario(prod_id, obtener_nombre_producto(prod_sync), "salida_venta", "ventas", venta_id, -cant_new, float(item.get("costo_unitario") or 0), "Ajuste por edición de venta")

                            # 4. actualizar venta
                            supabase.table("ventas").update(json_safe_payload({
                                "total": float(nuevo_total),
                                "subtotal": float(nuevo_total),
                                "metodo_pago": metodo_pago_nuevo,
                                "ganancia_bruta": float(nueva_ganancia),
                            })).eq("id", str(venta_id)).execute()

                            # 5. actualizar pagos si existe registro
                            try:
                                supabase.table("ventas_pagos").delete().eq("venta_id", str(venta_id)).execute()
                            except Exception:
                                pass

                            try:
                                supabase.table("ventas_pagos").insert(json_safe_payload({
                                    "venta_id": str(venta_id),
                                    "metodo": metodo_pago_nuevo,
                                    "monto": float(nuevo_total),
                                    "usuario": nombre_usuario_actual(),
                                    "caja_id": str(venta_row.get("caja_id")),
                                    "dia_operativo": ahora_str(),
                                })).execute()
                            except Exception:
                                pass

                            try:
                                reconstruir_movimientos_caja_desde_ventas_pagos(venta_id)
                            except Exception:
                                pass

                            # 6. Sincronizar cuentas por cobrar (cxc)
                            if metodo_pago_nuevo == "credito":
                                try:
                                    cxc_exists = supabase.table("cuentas_por_cobrar").select("*").eq("venta_id", str(venta_id)).execute().data or []
                                    if cxc_exists:
                                        cxc_id = cxc_exists[0]["id"]
                                        actualizar("cuentas_por_cobrar", cxc_id, {
                                            "monto_original": float(nuevo_total),
                                            "saldo_pendiente": float(nuevo_total),
                                            "estado": "pendiente"
                                        })
                                        supabase.table("cuentas_por_cobrar").insert({
                                            "cliente_id": venta_row.get("cliente_id"),
                                            "cliente_nombre": venta_row.get("cliente_nombre") or "Venta general",
                                            "venta_id": str(venta_id),
                                            "monto_original": float(nuevo_total),
                                            "monto_abonado": 0,
                                            "saldo_pendiente": float(nuevo_total),
                                            "estado": "pendiente",
                                            "usuario": nombre_usuario_actual(),
                                            "empresa_id": obtener_tenant_actual(),
                                        }).execute()
                                except Exception:
                                    pass
                            else:
                                try:
                                    supabase.table("cuentas_por_cobrar").delete().eq("venta_id", str(venta_id)).execute()
                                except Exception:
                                    pass

                            st.success("Venta editada completamente.")
                            st.rerun()

                        except Exception as exc:
                            st.error(f"No se pudo guardar la edición completa: {exc}")



        if puede_gestionar_ventas:
            with st.expander("🛠️ Control rápido / anular ventas", expanded=False):
                opciones = []
                mapa_ids = {}
                for _, row in df_show.iterrows():
                    row_id = row.get("id") or row.get("identificación")
                    etiqueta = f"{row_id} | {row.get('fecha')} | RD$ {float(limpiar_numero(row.get('total')) or 0):,.2f} | {row.get('metodo_pago') or row.get('metodo') or ''}"
                    opciones.append(etiqueta)
                    mapa_ids[etiqueta] = row
                if opciones:
                    venta_sel = st.selectbox("Selecciona una venta", opciones, key="ventas_sel_edit")
                    venta_row = mapa_ids[venta_sel]
                    venta_id = venta_row.get("id") or venta_row.get("identificación")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        fecha_edit = st.date_input("Fecha edición", value=pd.to_datetime(venta_row.get("fecha")).date() if pd.notna(pd.to_datetime(venta_row.get("fecha"), errors="coerce")) else date.today(), key="venta_edit_fecha")
                    with ce2:
                        total_edit = st.number_input("Total edición", min_value=0.0, step=1.0, value=float(limpiar_numero(venta_row.get("total")) or 0), key="venta_edit_total")
                    with ce3:
                        metodo_edit = st.selectbox("Método edición", ["efectivo", "transferencia", "tarjeta", "credito", "mixto"], index=["efectivo", "transferencia", "tarjeta", "credito", "mixto"].index(str((venta_row.get("metodo_pago") or venta_row.get("metodo") or "efectivo")).lower()) if str((venta_row.get("metodo_pago") or venta_row.get("metodo") or "efectivo")).lower() in ["efectivo", "transferencia", "tarjeta", "credito", "mixto"] else 0, key="venta_edit_metodo")
                    obs_edit = st.text_input("Observación edición", value=limpiar_texto(venta_row.get("observacion")), key="venta_edit_obs")
                    has_ncf = bool(str(venta_row.get("ncf") or "").strip())
                    cl1, cl2, cl3 = st.columns(3)
                    with cl1:
                        if has_ncf:
                            st.error("🛡️ Factura con NCF oficial — **edición bloqueada**. Emita una Nota de Crédito (E34) para correcciones.")
                        elif puede_editar_ventas() and st.button("💾 Guardar datos generales", key="btn_guardar_cambios_venta"):
                            ok = actualizar("ventas", venta_id, {
                                "fecha": str(fecha_edit),
                                "total": float(total_edit),
                                "metodo": metodo_edit,
                                "metodo_pago": metodo_edit,
                                "observacion": obs_edit,
                            })
                            if ok:
                                st.success("Venta actualizada.")
                                st.rerun()
                    with cl2:
                        if puede_anular_ventas() and st.button("🚫 Anular venta", key="btn_anular_venta_admin"):
                            ok = anular_venta_completa_app(venta_id, "Anulada manualmente desde módulo Ventas")
                            if ok:
                                st.success("Venta anulada.")
                                st.rerun()
                    with cl3:
                        if has_ncf:
                            st.error("🛡️ Factura con NCF oficial — **eliminación bloqueada**. La factura es un documento fiscal inamovible.")
                        elif puede_eliminar_ventas() and st.button("🗑️ Eliminar venta", key="btn_eliminar_venta_admin"):
                            ok = eliminar_venta_completa_app(venta_id)
                            if ok:
                                st.success("Venta eliminada.")
                                st.rerun()
    else:
        st.info("No hay ventas registradas.")



# =========================================================
# COMPRAS
# =========================================================



def render_caja():
    st.title("💵 Caja PRO")
    st.caption("La cajera abre caja con fondo inicial. Al cerrar, solo coloca el efectivo contado; el sistema calcula todo lo demás.")

    usuario_act = nombre_usuario_actual() if "nombre_usuario_actual" in globals() else usuario_sesion().get("usuario", "")
    hoy = date.today()

    def _leer_cajas():
        try:
            resp = supabase.table("caja").select("*").order("fecha_apertura", desc=True).execute()
            return pd.DataFrame(resp.data or [])
        except Exception:
            return DATA.get("caja", pd.DataFrame()).copy()

    def _leer_ventas_pagos_actualizadas():
        try:
            resp = supabase.table("ventas_pagos").select("*").execute()
            return pd.DataFrame(resp.data or [])
        except Exception:
            return DATA.get("ventas_pagos", pd.DataFrame()).copy()

    def _leer_ventas_actualizadas():
        try:
            resp = supabase.table("ventas").select("*").execute()
            df = pd.DataFrame(resp.data or [])
            if not df.empty:
                df = aplicar_total_contable_df(df) if "aplicar_total_contable_df" in globals() else df
            return df
        except Exception:
            ventas = DATA.get("ventas", pd.DataFrame()).copy()
            return aplicar_total_contable_df(ventas) if "aplicar_total_contable_df" in globals() else ventas

    def _leer_abonos_credito_actualizados():
        try:
            resp = supabase.table("abonos_credito").select("*").execute()
            return pd.DataFrame(resp.data or [])
        except Exception:
            return DATA.get("abonos_credito", pd.DataFrame()).copy()


    def _obtener_caja_abierta_usuario(usuario_nombre=None):
        usuario_nombre = usuario_nombre or usuario_act
        try:
            resp = (
                supabase.table("caja")
                .select("*")
                .eq("estado", "abierta")
                .eq("usuario", usuario_nombre)
                .order("fecha_apertura", desc=True)
                .limit(1)
                .execute()
            )
            data = resp.data or []
            return data[0] if data else None
        except Exception:
            cajas = _leer_cajas()
            if cajas.empty:
                return None
            if "estado" in cajas.columns:
                cajas = cajas[cajas["estado"].astype(str).apply(normalizar_texto) == "abierta"]
            if "usuario" in cajas.columns:
                cajas = cajas[cajas["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_nombre)]
            if cajas.empty:
                return None
            return cajas.iloc[0].to_dict()

    def _ventas_de_caja(caja):
        ventas = _leer_ventas_actualizadas()
        if ventas.empty:
            return ventas

        caja_id = caja.get("id")
        fecha_apertura = caja.get("fecha_apertura")
        fecha_cierre = caja.get("fecha_cierre")
        usuario_caja = caja.get("usuario") or usuario_act

        # 1) Si la venta tiene caja_id, esa es la fuente principal
        if "caja_id" in ventas.columns and caja_id:
            ventas_caja = ventas[ventas["caja_id"].astype(str) == str(caja_id)].copy()
            if not ventas_caja.empty:
                return ventas_caja

        # 2) Respaldo para ventas viejas sin caja_id: usuario + rango apertura/cierre
        if "fecha" in ventas.columns and fecha_apertura:
            ventas["_fecha_dt"] = pd.to_datetime(ventas["fecha"], errors="coerce")
            apertura_dt = pd.to_datetime(fecha_apertura, errors="coerce")
            ventas = ventas[ventas["_fecha_dt"] >= apertura_dt]
            if fecha_cierre:
                cierre_dt = pd.to_datetime(fecha_cierre, errors="coerce")
                ventas = ventas[ventas["_fecha_dt"] <= cierre_dt]

        if "usuario" in ventas.columns:
            ventas = ventas[ventas["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_caja)]

        return ventas

    def _pagos_de_caja(caja, ventas_caja=None):
        pagos = _leer_ventas_pagos_actualizadas()
        if pagos.empty:
            return pagos

        caja_id = caja.get("id")
        fecha_apertura = caja.get("fecha_apertura")
        fecha_cierre = caja.get("fecha_cierre")
        usuario_caja = caja.get("usuario") or usuario_act

        # 1) Si pagos tiene caja_id, usarlo
        if "caja_id" in pagos.columns and caja_id:
            pagos_caja = pagos[pagos["caja_id"].astype(str) == str(caja_id)].copy()
            if not pagos_caja.empty:
                return pagos_caja

        # 2) Si pagos tiene venta_id, cruzar con ventas de esa caja
        if ventas_caja is not None and not ventas_caja.empty and "venta_id" in pagos.columns:
            venta_ids = set()
            for col in ["id", "identificación", "identificacion"]:
                if col in ventas_caja.columns:
                    venta_ids.update(ventas_caja[col].dropna().astype(str).tolist())
            if venta_ids:
                pagos_match = pagos[pagos["venta_id"].astype(str).isin(venta_ids)].copy()
                if not pagos_match.empty:
                    return pagos_match

        # 3) Respaldo por usuario y rango de fechas
        if "usuario" in pagos.columns:
            pagos = pagos[pagos["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_caja)]

        if "fecha" in pagos.columns and fecha_apertura:
            pagos["_fecha_dt"] = pd.to_datetime(pagos["fecha"], errors="coerce")
            apertura_dt = pd.to_datetime(fecha_apertura, errors="coerce")
            pagos = pagos[pagos["_fecha_dt"] >= apertura_dt]
            if fecha_cierre:
                cierre_dt = pd.to_datetime(fecha_cierre, errors="coerce")
                pagos = pagos[pagos["_fecha_dt"] <= cierre_dt]

        return pagos

    def _abonos_de_caja(caja):
        abonos = _leer_abonos_credito_actualizados()
        if abonos.empty:
            return abonos

        caja_id = caja.get("id")
        fecha_apertura = caja.get("fecha_apertura")
        fecha_cierre = caja.get("fecha_cierre")
        usuario_caja = caja.get("usuario") or usuario_act

        # 1) Si el abono tiene caja_id, usar la caja exacta
        if "caja_id" in abonos.columns and caja_id:
            abonos_caja = abonos[abonos["caja_id"].astype(str) == str(caja_id)].copy()
            if not abonos_caja.empty:
                return abonos_caja

        # 2) Respaldo por usuario y rango de fecha
        if "usuario" in abonos.columns:
            abonos = abonos[abonos["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_caja)]

        fecha_col = "fecha" if "fecha" in abonos.columns else ("created_at" if "created_at" in abonos.columns else None)
        if fecha_col and fecha_apertura:
            abonos["_fecha_dt"] = pd.to_datetime(abonos[fecha_col], errors="coerce")
            apertura_dt = pd.to_datetime(fecha_apertura, errors="coerce")
            abonos = abonos[abonos["_fecha_dt"] >= apertura_dt]
            if fecha_cierre:
                cierre_dt = pd.to_datetime(fecha_cierre, errors="coerce")
                abonos = abonos[abonos["_fecha_dt"] <= cierre_dt]

        return abonos

    def _sumar_pago_metodo(pagos, metodo_buscar):
        if pagos.empty:
            return 0.0
        metodo_col = "metodo" if "metodo" in pagos.columns else ("metodo_pago" if "metodo_pago" in pagos.columns else None)
        if not metodo_col or "monto" not in pagos.columns:
            return 0.0
        temp = pagos[pagos[metodo_col].astype(str).apply(normalizar_texto) == metodo_buscar]
        return float(pd.to_numeric(temp["monto"], errors="coerce").fillna(0).sum())

    def _sumar_ventas_por_metodo_respaldo(ventas_caja, metodo_buscar):
        if ventas_caja.empty:
            return 0.0
        metodo_col = "metodo_pago" if "metodo_pago" in ventas_caja.columns else ("metodo" if "metodo" in ventas_caja.columns else None)
        total_col = "total_contable" if "total_contable" in ventas_caja.columns else "total"
        if not metodo_col or total_col not in ventas_caja.columns:
            return 0.0
        temp = ventas_caja[ventas_caja[metodo_col].astype(str).apply(normalizar_texto) == metodo_buscar]
        return float(pd.to_numeric(temp[total_col], errors="coerce").fillna(0).sum())

    def _calcular_resumen_caja(caja):
        ventas_caja = _ventas_de_caja(caja)
        pagos_caja = _pagos_de_caja(caja, ventas_caja)
        abonos_caja = _abonos_de_caja(caja)

        fondo_inicial = float(limpiar_numero(caja.get("monto_inicial")) or 0)

        # =====================================================
        # REGLA LIMPIA DE CAJA
        # =====================================================
        # 1) Total ventas = suma real de ventas, sin recargo.
        # 2) Métodos de pago = ventas_pagos reales.
        # 3) Si ventas_pagos suma más que ventas reales, el exceso es recargo y se descuenta,
        #    primero de tarjeta, luego de otros métodos si fue digitado mal.
        # =====================================================

        if ventas_caja is None:
            ventas_caja = pd.DataFrame()
        if pagos_caja is None:
            pagos_caja = pd.DataFrame()

        ventas_caja = aplicar_total_contable_df(ventas_caja) if "aplicar_total_contable_df" in globals() and not ventas_caja.empty else ventas_caja

        total_col = "total_contable" if not ventas_caja.empty and "total_contable" in ventas_caja.columns else "total"
        total_ventas = suma_col(ventas_caja, total_col) if not ventas_caja.empty and total_col in ventas_caja.columns else 0.0

        pagos_ajustados = pagos_caja.copy()
        if not pagos_ajustados.empty and "monto" in pagos_ajustados.columns:
            pagos_ajustados["monto"] = pd.to_numeric(pagos_ajustados["monto"], errors="coerce").fillna(0)

            metodo_col = "metodo" if "metodo" in pagos_ajustados.columns else ("metodo_pago" if "metodo_pago" in pagos_ajustados.columns else None)

            # Los pagos se suman como fueron registrados en POS.
            # El recargo de tarjeta no se registra en ventas_pagos, por eso no se descuenta aquí.

        def _sumar_metodo_limpio(df_pagos, metodo_buscar):
            if df_pagos.empty or "monto" not in df_pagos.columns:
                return 0.0
            metodo_col = "metodo" if "metodo" in df_pagos.columns else ("metodo_pago" if "metodo_pago" in df_pagos.columns else None)
            if not metodo_col:
                return 0.0
            temp = df_pagos[df_pagos[metodo_col].astype(str).apply(normalizar_texto) == metodo_buscar]
            return float(pd.to_numeric(temp["monto"], errors="coerce").fillna(0).sum())

        venta_efectivo = _sumar_metodo_limpio(pagos_ajustados, "efectivo")
        venta_transferencia = _sumar_metodo_limpio(pagos_ajustados, "transferencia")
        venta_tarjeta = _sumar_metodo_limpio(pagos_ajustados, "tarjeta")
        venta_credito = _sumar_metodo_limpio(pagos_ajustados, "credito")

        # Abonos de crédito: NO son ventas nuevas, pero SÍ son dinero recibido en caja.
        abono_efectivo = _sumar_metodo_limpio(abonos_caja, "efectivo")
        abono_transferencia = _sumar_metodo_limpio(abonos_caja, "transferencia")
        abono_tarjeta = _sumar_metodo_limpio(abonos_caja, "tarjeta")

        efectivo_caja = venta_efectivo + abono_efectivo
        transferencia_caja = venta_transferencia + abono_transferencia
        tarjeta_caja = venta_tarjeta + abono_tarjeta
        total_abonos = abono_efectivo + abono_transferencia + abono_tarjeta
        total_ingresos_caja = venta_efectivo + venta_transferencia + venta_tarjeta + total_abonos

        # Respaldo para ventas viejas sin ventas_pagos
        if (venta_efectivo + venta_transferencia + venta_tarjeta + venta_credito) == 0 and not ventas_caja.empty:
            metodo_col_v = "metodo_pago" if "metodo_pago" in ventas_caja.columns else ("metodo" if "metodo" in ventas_caja.columns else None)
            if metodo_col_v and total_col in ventas_caja.columns:
                for metodo in ["efectivo", "transferencia", "tarjeta", "credito"]:
                    temp = ventas_caja[ventas_caja[metodo_col_v].astype(str).apply(normalizar_texto) == metodo]
                    monto = float(pd.to_numeric(temp[total_col], errors="coerce").fillna(0).sum())
                    if metodo == "efectivo":
                        venta_efectivo = monto
                    elif metodo == "transferencia":
                        venta_transferencia = monto
                    elif metodo == "tarjeta":
                        venta_tarjeta = monto
                    elif metodo == "credito":
                        venta_credito = monto

        # Efectivo esperado = fondo inicial + efectivo de ventas + abonos en efectivo.
        efectivo_esperado = fondo_inicial + efectivo_caja

        return {
            "ventas_df": ventas_caja,
            "pagos_df": pagos_ajustados,
            "abonos_df": abonos_caja,
            "fondo_inicial": fondo_inicial,

            # ventas reales
            "venta_efectivo": venta_efectivo,
            "venta_transferencia": venta_transferencia,
            "venta_tarjeta": venta_tarjeta,
            "venta_credito": venta_credito,
            "total_ventas": total_ventas,

            # abonos de crédito recibidos
            "abono_efectivo": abono_efectivo,
            "abono_transferencia": abono_transferencia,
            "abono_tarjeta": abono_tarjeta,
            "total_abonos": total_abonos,

            # dinero real que entra al cierre de caja por método
            "efectivo_caja": efectivo_caja,
            "transferencia_caja": transferencia_caja,
            "tarjeta_caja": tarjeta_caja,
            "total_ingresos_caja": total_ingresos_caja,

            "efectivo_esperado": efectivo_esperado,
        }


    def _cerrar_caja(caja, efectivo_contado, obs_cierre, usuario_cierre=None):
        usuario_cierre = usuario_cierre or usuario_act
        resumen = _calcular_resumen_caja(caja)

        diferencia = float(efectivo_contado) - float(resumen["efectivo_esperado"])
        faltante = abs(diferencia) if diferencia < 0 else 0.0
        sobrante = diferencia if diferencia > 0 else 0.0

        cierre_payload = {
            "fecha_cierre": datetime.now().isoformat(),
            "estado": "cerrada",
            "efectivo_contado": float(efectivo_contado),
            "efectivo_esperado": float(resumen["efectivo_esperado"]),
            "total_efectivo": float(resumen.get("efectivo_caja", resumen["venta_efectivo"])),
            "total_transferencia": float(resumen.get("transferencia_caja", resumen["venta_transferencia"])),
            "total_tarjeta": float(resumen.get("tarjeta_caja", resumen["venta_tarjeta"])),
            "total_credito": float(resumen["venta_credito"]),
            "total_ventas": float(resumen["total_ventas"]),
            "faltante": float(faltante),
            "sobrante": float(sobrante),
            "diferencia": float(diferencia),
            "observacion": obs_cierre,
        }

        ok_update = actualizar("caja", caja.get("id"), cierre_payload)

        # C-05: Si hay descuadre (diferencia != 0), registrar evento de auditoría de seguridad
        if abs(diferencia) > 0.01:
            try:
                registrar_auditoria_pro(
                    accion="descuadre_caja_cierre",
                    modulo="Caja",
                    tabla_afectada="caja",
                    registro_id=caja.get("id"),
                    impacto_economico=float(diferencia),
                    nivel_riesgo="alto",
                    riesgo_score=75.0,
                    descripcion=f"Cierre de caja descuadrado (Usuario: {caja.get('usuario')}). Esperado: RD$ {float(resumen['efectivo_esperado']):,.2f}, Contado: RD$ {float(efectivo_contado):,.2f}, Diferencia: RD$ {diferencia:,.2f}. Justificación: {obs_cierre}"
                )
            except Exception:
                pass

        cierre_reg = {
            "caja_id": str(caja.get("id")),
            "usuario": caja.get("usuario") or usuario_cierre,
            "usuario_id": str(caja.get("usuario_id") or usuario_sesion().get("id", "")),
            "fecha": datetime.now().isoformat(),
            "monto_inicial": float(resumen["fondo_inicial"]),
            "efectivo_contado": float(efectivo_contado),
            "efectivo_esperado": float(resumen["efectivo_esperado"]),
            "total_efectivo": float(resumen.get("efectivo_caja", resumen["venta_efectivo"])),
            "total_transferencia": float(resumen.get("transferencia_caja", resumen["venta_transferencia"])),
            "total_tarjeta": float(resumen.get("tarjeta_caja", resumen["venta_tarjeta"])),
            "total_credito": float(resumen["venta_credito"]),
            "total_ventas": float(resumen["total_ventas"]),
            "faltante": float(faltante),
            "sobrante": float(sobrante),
            "diferencia": float(diferencia),
            "observacion": obs_cierre,
        }
        insertar("cierre_caja", cierre_reg)
        return ok_update

    def _tabla_cajas_limpia(cajas_df):
        if cajas_df.empty:
            return cajas_df
        out = cajas_df.copy()
        columnas = [c for c in [
            "usuario", "fecha_apertura", "fecha_cierre", "estado", "monto_inicial",
            "efectivo_esperado", "efectivo_contado", "diferencia", "faltante", "sobrante",
            "total_ventas", "total_efectivo", "total_transferencia", "total_tarjeta", "total_credito", "observacion"
        ] if c in out.columns]
        out = out[columnas].copy()
        nombres = {
            "usuario": "Usuario",
            "fecha_apertura": "Apertura",
            "fecha_cierre": "Cierre",
            "estado": "Estado",
            "monto_inicial": "Caja inicial",
            "efectivo_esperado": "Efectivo esperado",
            "efectivo_contado": "Efectivo contado",
            "diferencia": "Diferencia",
            "faltante": "Faltante",
            "sobrante": "Sobrante",
            "total_ventas": "Total ventas",
            "total_efectivo": "Ventas efectivo",
            "total_transferencia": "Transferencia",
            "total_tarjeta": "Tarjeta",
            "total_credito": "Crédito",
            "observacion": "Observación",
        }
        return out.rename(columns=nombres)

    def _html_cuadre_caja(caja, resumen, efectivo_contado=None):
        efectivo_contado = resumen["efectivo_esperado"] if efectivo_contado is None else float(efectivo_contado)
        diferencia = efectivo_contado - resumen["efectivo_esperado"]
        faltante = abs(diferencia) if diferencia < 0 else 0
        sobrante = diferencia if diferencia > 0 else 0
        negocio = obtener_configuracion().get("negocio_nombre") or "Sistema de Negocio PRO"
        return f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 18px; color: #111; }}
                .box {{ max-width: 520px; margin: 0 auto; border: 1px solid #ddd; padding: 18px; }}
                h2, h3 {{ text-align:center; margin: 4px 0; }}
                table {{ width:100%; border-collapse: collapse; margin-top: 14px; }}
                td {{ padding: 7px; border-bottom:1px solid #eee; }}
                td:last-child {{ text-align:right; font-weight:bold; }}
                .print {{ text-align:center; margin-bottom: 12px; }}
                button {{ padding:10px 16px; font-weight:bold; }}
                @media print {{ .print {{ display:none; }} .box {{ border:none; }} }}
            </style>
        </head>
        <body>
            <div class="print"><button onclick="window.print()">🖨️ Imprimir cuadre de caja</button></div>
            <div class="box">
                <h2>{negocio}</h2>
                <h3>CUADRE DE CAJA</h3>
                <p><b>Usuario:</b> {caja.get("usuario","")}<br>
                <b>Apertura:</b> {caja.get("fecha_apertura","")}<br>
                <b>Estado:</b> {caja.get("estado","")}</p>
                <table>
                    <tr><td>Caja inicial</td><td>RD$ {resumen["fondo_inicial"]:,.2f}</td></tr>
                    <tr><td>Ventas efectivo</td><td>RD$ {resumen["venta_efectivo"]:,.2f}</td></tr>
                    <tr><td>Abonos efectivo</td><td>RD$ {resumen.get("abono_efectivo", 0):,.2f}</td></tr>
                    <tr><td>Efectivo recibido</td><td>RD$ {resumen.get("efectivo_caja", resumen["venta_efectivo"]):,.2f}</td></tr>
                    <tr><td>Transferencia recibida</td><td>RD$ {resumen.get("transferencia_caja", resumen["venta_transferencia"]):,.2f}</td></tr>
                    <tr><td>Tarjeta recibida</td><td>RD$ {resumen.get("tarjeta_caja", resumen["venta_tarjeta"]):,.2f}</td></tr>
                    <tr><td>Crédito vendido</td><td>RD$ {resumen["venta_credito"]:,.2f}</td></tr>
                    <tr><td>Total ventas</td><td>RD$ {resumen["total_ventas"]:,.2f}</td></tr>
                    <tr><td>Total abonos</td><td>RD$ {resumen.get("total_abonos", 0):,.2f}</td></tr>
                    <tr><td>Total ingresos caja</td><td>RD$ {resumen.get("total_ingresos_caja", 0):,.2f}</td></tr>
                    <tr><td>Efectivo esperado</td><td>RD$ {resumen["efectivo_esperado"]:,.2f}</td></tr>
                    <tr><td>Efectivo contado</td><td>RD$ {efectivo_contado:,.2f}</td></tr>
                    <tr><td>Diferencia</td><td>RD$ {diferencia:,.2f}</td></tr>
                    <tr><td>Faltante</td><td>RD$ {faltante:,.2f}</td></tr>
                    <tr><td>Sobrante</td><td>RD$ {sobrante:,.2f}</td></tr>
                </table>
                <br><br>
                <p>Firma cajera: __________________________</p>
                <p>Firma supervisora: ______________________</p>
            </div>
        </body>
        </html>
        """

    caja_abierta = _obtener_caja_abierta_usuario(usuario_act)

    if not caja_abierta:
        st.subheader("🔓 Abrir caja")
        c1, c2 = st.columns(2)
        with c1:
            monto_inicial = st.number_input("Caja inicial / fondo inicial", min_value=0.0, step=1.0, value=0.0, key="caja_apertura_monto")
        with c2:
            obs_apertura = st.text_input("Observación apertura", key="caja_apertura_obs")

        if st.button("Abrir caja", key="btn_abrir_caja_pro"):
            payload = {
                "usuario": usuario_act,
                "usuario_id": str(usuario_sesion().get("id", "")),
                "fecha_apertura": datetime.now().isoformat(),
                "dia_operativo": str(hoy),
                "monto_inicial": float(monto_inicial),
                "estado": "abierta",
                "observacion": obs_apertura,
            }
            ok = insertar("caja", payload)
            if ok:
                st.success("Caja abierta correctamente.")
                st.rerun()
    else:
        st.success("Tienes una caja abierta.")
        resumen = _calcular_resumen_caja(caja_abierta)
        ventas_caja = resumen["ventas_df"]
        pagos_caja = resumen["pagos_df"]
        abonos_caja = resumen.get("abonos_df", pd.DataFrame())

        st.markdown("### 📌 Resumen de caja")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Caja inicial", f"RD$ {resumen['fondo_inicial']:,.2f}")
        r2.metric("Efectivo recibido", f"RD$ {resumen.get('efectivo_caja', resumen['venta_efectivo']):,.2f}")
        r3.metric("Efectivo esperado", f"RD$ {resumen['efectivo_esperado']:,.2f}")
        r4.metric("Total ventas", f"RD$ {resumen['total_ventas']:,.2f}")

        r5, r6, r7, r8 = st.columns(4)
        r5.metric("Ventas efectivo", f"RD$ {resumen['venta_efectivo']:,.2f}")
        r6.metric("Abonos efectivo", f"RD$ {resumen.get('abono_efectivo', 0):,.2f}")
        r7.metric("Transferencia recibida", f"RD$ {resumen.get('transferencia_caja', resumen['venta_transferencia']):,.2f}")
        r8.metric("Tarjeta recibida", f"RD$ {resumen.get('tarjeta_caja', resumen['venta_tarjeta']):,.2f}")

        r9, r10, r11 = st.columns(3)
        r9.metric("Crédito vendido", f"RD$ {resumen['venta_credito']:,.2f}")
        r10.metric("Total abonos", f"RD$ {resumen.get('total_abonos', 0):,.2f}")
        r11.metric("Total ingresos caja", f"RD$ {resumen.get('total_ingresos_caja', 0):,.2f}")

        st.caption("Nota: los abonos de crédito entran a caja y dinero real, pero no aumentan el total de ventas.")

        html_cuadre_pre = _html_cuadre_caja(caja_abierta, resumen)
        with st.expander("🖨️ Imprimir cuadre de caja para contar", expanded=False):
            components.html(html_cuadre_pre, height=780, scrolling=True)
            st.download_button(
                "⬇️ Descargar cuadre de caja",
                data=html_cuadre_pre.encode("utf-8"),
                file_name=f"cuadre_caja_{caja_abierta.get('usuario','')}.html",
                mime="text/html",
                key=f"desc_cuadre_caja_{caja_abierta.get('id')}",
            )

        with st.expander("🔎 Ver ventas y pagos tomados para este cierre", expanded=False):
            st.write("Ventas tomadas:")
            if ventas_caja.empty:
                st.info("No hay ventas registradas para esta caja.")
            else:
                cols = [c for c in ["numero_factura", "fecha", "total", "total_contable", "recargo", "metodo_pago", "metodo", "usuario", "caja_id"] if c in ventas_caja.columns]
                st.dataframe(ventas_caja[cols] if cols else ventas_caja, use_container_width=True)
            st.write("Pagos de ventas tomados:")
            if pagos_caja.empty:
                st.info("No hay pagos separados para esta caja.")
            else:
                cols_p = [c for c in ["venta_id", "metodo", "metodo_pago", "monto", "usuario", "caja_id", "dia_operativo"] if c in pagos_caja.columns]
                st.dataframe(pagos_caja[cols_p] if cols_p else pagos_caja, use_container_width=True)

            st.write("Abonos de crédito tomados:")
            if abonos_caja.empty:
                st.info("No hay abonos de crédito registrados para esta caja.")
            else:
                cols_a = [c for c in ["fecha", "cliente_nombre", "monto", "metodo_pago", "usuario", "caja_id", "cuenta_id", "observacion"] if c in abonos_caja.columns]
                st.dataframe(abonos_caja[cols_a] if cols_a else abonos_caja, use_container_width=True)

        # Popover para apertura de gaveta sin venta
        with st.popover("🔑 Abrir Gaveta (Sin Venta)", use_container_width=True):
            motivo_ap = st.text_input("Indique el motivo de la apertura", placeholder="Ej. Cambio de menudo", key="caja_motivo_apertura_gav")
            if st.button("⚡ Confirmar Apertura de Caja", key="caja_btn_trigger_apertura_gav", use_container_width=True):
                if not motivo_ap:
                    st.error("Debe indicar un motivo.")
                else:
                    gatillar_apertura_gaveta(motivo_ap)
                    st.rerun()

        st.markdown("---")
        st.subheader("🔐 Cierre de caja")
        st.caption("La cajera solo escribe el efectivo físico contado. El sistema calcula si hay sobrante o faltante.")

        efectivo_contado = st.number_input(
            "Efectivo físico contado",
            min_value=0.0,
            step=1.0,
            value=float(resumen["efectivo_esperado"]),
            key="caja_efectivo_fisico_contado",
        )

        diferencia = float(efectivo_contado) - float(resumen["efectivo_esperado"])
        faltante = abs(diferencia) if diferencia < 0 else 0.0
        sobrante = diferencia if diferencia > 0 else 0.0

        c1, c2, c3 = st.columns(3)
        c1.metric("Efectivo esperado", f"RD$ {resumen['efectivo_esperado']:,.2f}")
        c2.metric("Efectivo contado", f"RD$ {efectivo_contado:,.2f}")
        if diferencia < 0:
            c3.metric("Faltante", f"RD$ {faltante:,.2f}")
        elif diferencia > 0:
            c3.metric("Sobrante", f"RD$ {sobrante:,.2f}")
        else:
            c3.metric("Diferencia", "RD$ 0.00")

        obs_cierre = st.text_area("Observación de cierre", key="caja_obs_cierre")

        html_cuadre_final = _html_cuadre_caja(caja_abierta, resumen, efectivo_contado)
        with st.expander("👁️ Vista previa del cuadre final", expanded=False):
            components.html(html_cuadre_final, height=780, scrolling=True)

        if st.button("Cerrar caja", key="btn_cerrar_caja_pro"):
            # C-05: Si hay descuadre, exigir justificación escrita
            if abs(diferencia) > 0.01 and not (obs_cierre and obs_cierre.strip()):
                st.error(f"⚠️ **Justificación Obligatoria por Descuadre:** La caja presenta una diferencia de **RD$ {abs(diferencia):,.2f}** entre el efectivo contado y el esperado. Debe ingresar una **observación de cierre** explicando el motivo del descuadre para poder cerrar la caja.")
            else:
                html_final = _html_cuadre_caja(caja_abierta, resumen, efectivo_contado)
                # Inyectar auto-impresión
                html_final = html_final.replace("<body>", "<body><script>window.onload = function() { window.print(); }</script>")
                st.session_state["imprimir_cierre_z"] = html_final
                ok_update = _cerrar_caja(caja_abierta, efectivo_contado, obs_cierre, usuario_act)
                if ok_update:
                    st.rerun()

    st.markdown("---")
    st.subheader("📚 Historial de cierres")
    cierres = DATA.get("cierre_caja", pd.DataFrame()).copy()
    if cierres.empty:
        st.info("No hay cierres de caja registrados.")
    else:
        if es_cajera() and "usuario" in cierres.columns:
            cierres = cierres[cierres["usuario"].astype(str).apply(normalizar_texto) == normalizar_texto(usuario_act)]
        st.dataframe(_tabla_cajas_limpia(cierres), use_container_width=True)
        if not es_cajera():
            descargar_archivos(_tabla_cajas_limpia(cierres), "cierres_caja")

    if es_admin():
        st.markdown("---")
        st.subheader("🧑‍💼 Control administrativo de cajas")
        cajas_admin = _leer_cajas()
        if cajas_admin.empty:
            st.info("No hay cajas registradas.")
        else:
            cfa, cfb, cfc = st.columns(3)
            usuarios = ["Todos"]
            if "usuario" in cajas_admin.columns:
                usuarios += sorted([u for u in cajas_admin["usuario"].dropna().astype(str).unique().tolist() if u])
            usuario_filtro = cfa.selectbox("Filtrar por usuario", usuarios, key="admin_caja_usuario")
            estado_filtro = cfb.selectbox("Filtrar por estado", ["Todos", "abierta", "cerrada"], key="admin_caja_estado")
            texto_filtro = cfc.text_input("Buscar", key="admin_caja_buscar")

            cajas_vista = cajas_admin.copy()
            if usuario_filtro != "Todos" and "usuario" in cajas_vista.columns:
                cajas_vista = cajas_vista[cajas_vista["usuario"].astype(str) == usuario_filtro]
            if estado_filtro != "Todos" and "estado" in cajas_vista.columns:
                cajas_vista = cajas_vista[cajas_vista["estado"].astype(str).apply(normalizar_texto) == estado_filtro]
            cajas_vista = buscar_df(cajas_vista, texto_filtro)

            st.dataframe(_tabla_cajas_limpia(cajas_vista), use_container_width=True)

            cajas_abiertas = cajas_admin.copy()
            if "estado" in cajas_abiertas.columns:
                cajas_abiertas = cajas_abiertas[cajas_abiertas["estado"].astype(str).apply(normalizar_texto) == "abierta"]

            with st.expander("🔐 Cerrar caja abierta como administradora", expanded=False):
                if cajas_abiertas.empty:
                    st.info("No hay cajas abiertas.")
                else:
                    opciones = []
                    mapa = {}
                    for _, r in cajas_abiertas.iterrows():
                        etiqueta = f"{r.get('usuario','')} | apertura: {r.get('fecha_apertura','')} | fondo RD$ {float(limpiar_numero(r.get('monto_inicial')) or 0):,.2f}"
                        opciones.append(etiqueta)
                        mapa[etiqueta] = r.to_dict()

                    sel = st.selectbox("Selecciona caja abierta", opciones, key="admin_caja_abierta_sel")
                    caja_sel = mapa[sel]
                    resumen_sel = _calcular_resumen_caja(caja_sel)

                    aa, ab, ac, ad = st.columns(4)
                    aa.metric("Usuario", caja_sel.get("usuario", ""))
                    ab.metric("Caja inicial", f"RD$ {resumen_sel['fondo_inicial']:,.2f}")
                    ac.metric("Efectivo esperado", f"RD$ {resumen_sel['efectivo_esperado']:,.2f}")
                    ad.metric("Total ventas", f"RD$ {resumen_sel['total_ventas']:,.2f}")

                    efectivo_admin = st.number_input(
                        "Efectivo contado por administración",
                        min_value=0.0,
                        step=1.0,
                        value=float(resumen_sel["efectivo_esperado"]),
                        key="admin_caja_efectivo_contado",
                    )
                    diferencia_admin = float(efectivo_admin) - float(resumen_sel["efectivo_esperado"])
                    if diferencia_admin < 0:
                        st.warning(f"Faltante: RD$ {abs(diferencia_admin):,.2f}")
                    elif diferencia_admin > 0:
                        st.success(f"Sobrante: RD$ {diferencia_admin:,.2f}")
                    else:
                        st.info("Caja cuadrada. Diferencia RD$ 0.00")

                    obs_admin = st.text_area("Observación cierre administrativo", key="admin_caja_obs")
                    html_admin = _html_cuadre_caja(caja_sel, resumen_sel, efectivo_admin)
                    components.html(html_admin, height=420, scrolling=True)

                    if st.button("Cerrar esta caja como ADMIN", key="admin_btn_cerrar_caja"):
                        html_final = _html_cuadre_caja(caja_sel, resumen_sel, efectivo_admin)
                        html_final = html_final.replace("<body>", "<body><script>window.onload = function() { window.print(); }</script>")
                        st.session_state["imprimir_cierre_z"] = html_final
                        ok = _cerrar_caja(caja_sel, efectivo_admin, f"Cierre administrativo. {obs_admin}", usuario_act)
                        if ok:
                            st.rerun()


            with st.expander("🔄 Recalcular caja cerrada", expanded=False):
                cajas_cerradas_recalc = cajas_admin.copy()
                if "estado" in cajas_cerradas_recalc.columns:
                    cajas_cerradas_recalc = cajas_cerradas_recalc[cajas_cerradas_recalc["estado"].astype(str).apply(normalizar_texto) == "cerrada"]

                if cajas_cerradas_recalc.empty:
                    st.info("No hay cajas cerradas para recalcular.")
                else:
                    opciones_recalc = []
                    mapa_recalc = {}
                    for _, r in cajas_cerradas_recalc.iterrows():
                        etiqueta = f"{r.get('usuario','')} | apertura: {r.get('fecha_apertura','')} | cierre: {r.get('fecha_cierre','')} | esperado actual RD$ {float(limpiar_numero(r.get('efectivo_esperado')) or 0):,.2f}"
                        opciones_recalc.append(etiqueta)
                        mapa_recalc[etiqueta] = r.to_dict()

                    sel_recalc = st.selectbox("Selecciona caja para recalcular", opciones_recalc, key="admin_caja_recalcular_sel")
                    caja_recalc = mapa_recalc[sel_recalc]
                    resumen_recalc = _calcular_resumen_caja(caja_recalc)

                    efectivo_original = float(limpiar_numero(caja_recalc.get("efectivo_contado")) or 0)
                    nuevo_esperado = float(resumen_recalc["efectivo_esperado"])
                    nueva_diferencia = efectivo_original - nuevo_esperado
                    nuevo_faltante = abs(nueva_diferencia) if nueva_diferencia < 0 else 0.0
                    nuevo_sobrante = nueva_diferencia if nueva_diferencia > 0 else 0.0

                    rr1, rr2, rr3, rr4 = st.columns(4)
                    rr1.metric("Caja inicial", f"RD$ {resumen_recalc['fondo_inicial']:,.2f}")
                    rr2.metric("Ventas efectivo recalculadas", f"RD$ {resumen_recalc['venta_efectivo']:,.2f}")
                    rr3.metric("Nuevo efectivo esperado", f"RD$ {nuevo_esperado:,.2f}")
                    rr4.metric("Efectivo contado guardado", f"RD$ {efectivo_original:,.2f}")

                    rr5, rr6, rr7 = st.columns(3)
                    rr5.metric("Nueva diferencia", f"RD$ {nueva_diferencia:,.2f}")
                    rr6.metric("Nuevo faltante", f"RD$ {nuevo_faltante:,.2f}")
                    rr7.metric("Nuevo sobrante", f"RD$ {nuevo_sobrante:,.2f}")

                    with st.expander("Ver ventas/pagos usados en recálculo", expanded=False):
                        st.write("Ventas")
                        vdf = resumen_recalc.get("ventas_df", pd.DataFrame())
                        st.dataframe(vdf, use_container_width=True)
                        st.write("Pagos ajustados sin recargo")
                        pdf = resumen_recalc.get("pagos_df", pd.DataFrame())
                        st.dataframe(pdf, use_container_width=True)

                    if st.button("Aplicar recálculo a esta caja", key="admin_aplicar_recalculo_caja"):
                        payload_recalc = {
                            "efectivo_esperado": float(nuevo_esperado),
                            "total_efectivo": float(resumen_recalc["venta_efectivo"]),
                            "total_transferencia": float(resumen_recalc["venta_transferencia"]),
                            "total_tarjeta": float(resumen_recalc["venta_tarjeta"]),
                            "total_credito": float(resumen_recalc["venta_credito"]),
                            "total_ventas": float(resumen_recalc["total_ventas"]),
                            "diferencia": float(nueva_diferencia),
                            "faltante": float(nuevo_faltante),
                            "sobrante": float(nuevo_sobrante),
                            "observacion": limpiar_texto(caja_recalc.get("observacion")) + " | Caja recalculada sin recargo financiero",
                        }
                        ok = actualizar("caja", caja_recalc.get("id"), payload_recalc)
                        if ok:
                            st.success("Caja recalculada correctamente.")
                            st.rerun()


            with st.expander("✏️ Editar datos de una caja cerrada", expanded=False):
                cajas_cerradas = cajas_admin.copy()
                if "estado" in cajas_cerradas.columns:
                    cajas_cerradas = cajas_cerradas[cajas_cerradas["estado"].astype(str).apply(normalizar_texto) == "cerrada"]

                if cajas_cerradas.empty:
                    st.info("No hay cajas cerradas para editar.")
                else:
                    opciones2 = []
                    mapa2 = {}
                    for _, r in cajas_cerradas.iterrows():
                        etiqueta = f"{r.get('usuario','')} | cierre: {r.get('fecha_cierre','')} | dif RD$ {float(limpiar_numero(r.get('diferencia')) or 0):,.2f}"
                        opciones2.append(etiqueta)
                        mapa2[etiqueta] = r.to_dict()

                    sel2 = st.selectbox("Selecciona caja cerrada", opciones2, key="admin_caja_cerrada_sel")
                    caja_cerrada = mapa2[sel2]

                    efectivo_edit = st.number_input(
                        "Efectivo contado corregido",
                        min_value=0.0,
                        step=1.0,
                        value=float(limpiar_numero(caja_cerrada.get("efectivo_contado")) or 0),
                        key="admin_edit_efectivo_contado",
                    )
                    esperado_edit = float(limpiar_numero(caja_cerrada.get("efectivo_esperado")) or 0)
                    diff_edit = float(efectivo_edit) - esperado_edit
                    falt_edit = abs(diff_edit) if diff_edit < 0 else 0.0
                    sobr_edit = diff_edit if diff_edit > 0 else 0.0
                    obs_edit = st.text_area(
                        "Observación corregida",
                        value=limpiar_texto(caja_cerrada.get("observacion")),
                        key="admin_edit_obs_caja",
                    )

                    st.metric("Nueva diferencia", f"RD$ {diff_edit:,.2f}")

                    if st.button("Guardar corrección de caja", key="admin_guardar_correccion_caja"):
                        payload_edit = {
                            "efectivo_contado": float(efectivo_edit),
                            "diferencia": float(diff_edit),
                            "faltante": float(falt_edit),
                            "sobrante": float(sobr_edit),
                            "observacion": obs_edit,
                        }
                        ok = actualizar("caja", caja_cerrada.get("id"), payload_edit)
                        if ok:
                            st.success("Caja corregida.")
                            st.rerun()

# =========================================================
# ESTADO DE RESULTADOS

# =========================================================


def render_clientes():
    st.title("👥 Clientes")
    next_cli_id = generar_codigo_secuencial("clientes")
    st.caption(f"Identificador del próximo cliente: **{next_cli_id}**")

    tab_lista, tab_estado = st.tabs(["📋 Gestión de Clientes", "📄 Estado de Cuenta"])

    with tab_lista:
        with st.expander("➕ Agregar cliente", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                nombre = st.text_input("Nombre", key="cli_nombre")
                telefono = st.text_input("Teléfono", key="cli_tel")
                cedula_rnc = st.text_input("Cédula / RNC", key="cli_doc")
            with c2:
                direccion = st.text_input("Dirección", key="cli_dir")
                limite_credito = st.number_input("Límite de crédito", min_value=0.0, step=1.0, key="cli_lim")
                observacion = st.text_area("Observación", key="cli_obs")
            if st.button("Guardar cliente", key="btn_guardar_cliente"):
                if insertar("clientes", {"nombre": nombre, "telefono": telefono, "cedula_rnc": cedula_rnc, "direccion": direccion, "limite_credito": float(limite_credito), "balance_pendiente": 0.0, "activo": True, "observacion": observacion}):
                    st.success("Cliente guardado.")
                    st.rerun()
        df = DATA.get("clientes", pd.DataFrame()).copy()
        if not df.empty:
            txt_b = st.text_input("Buscar cliente", key="cli_buscar")
            if txt_b:
                df = buscar_df(df, txt_b)
            st.dataframe(df, use_container_width=True)
            descargar_archivos(df, "clientes")
            render_crud_generico("clientes", df, "🛠️ Editar / eliminar clientes")
        else:
            st.info("No hay clientes.")

    with tab_estado:
        st.subheader("📄 Estado de Cuenta por Cliente")
        st.caption("Visualiza y descarga el estado de cuenta individual con historial de facturas, abonos y saldo pendiente.")

        df_clientes = DATA.get("clientes", pd.DataFrame()).copy()
        if df_clientes.empty:
            st.info("No hay clientes registrados.")
        else:
            nombres_c = ["— Seleccione un cliente —"] + sorted(df_clientes["nombre"].astype(str).tolist())
            cliente_sel = st.selectbox("Seleccionar cliente", nombres_c, key="ec_cliente_sel")

            if cliente_sel and cliente_sel != "— Seleccione un cliente —":
                df_cxc = DATA.get("cuentas_por_cobrar", pd.DataFrame()).copy()
                df_abonos = DATA.get("abonos_credito", pd.DataFrame()).copy()
                df_ventas_cli = DATA.get("ventas", pd.DataFrame()).copy()

                # Filtrar datos del cliente
                cliente_n = normalizar_texto(cliente_sel)
                cxc_cli = pd.DataFrame()
                if not df_cxc.empty and "cliente_nombre" in df_cxc.columns:
                    cxc_cli = df_cxc[df_cxc["cliente_nombre"].astype(str).apply(normalizar_texto) == cliente_n].copy()

                abonos_cli = pd.DataFrame()
                if not df_abonos.empty and "cliente_nombre" in df_abonos.columns:
                    abonos_cli = df_abonos[df_abonos["cliente_nombre"].astype(str).apply(normalizar_texto) == cliente_n].copy()

                # Datos del cliente
                row_cli = df_clientes[df_clientes["nombre"].astype(str).apply(normalizar_texto) == cliente_n]
                rnc_cli = str(row_cli.iloc[0].get("cedula_rnc") or "—") if not row_cli.empty else "—"
                tel_cli = str(row_cli.iloc[0].get("telefono") or "—") if not row_cli.empty else "—"
                dir_cli = str(row_cli.iloc[0].get("direccion") or "—") if not row_cli.empty else "—"
                lim_cred = float(row_cli.iloc[0].get("limite_credito") or 0) if not row_cli.empty else 0.0

                # Calcular totales
                total_facturado = float(cxc_cli["monto_original"].sum()) if not cxc_cli.empty and "monto_original" in cxc_cli.columns else 0.0
                total_abonado = float(abonos_cli["monto"].sum()) if not abonos_cli.empty and "monto" in abonos_cli.columns else 0.0
                saldo_pendiente = total_facturado - total_abonado

                facturas_pendientes = 0
                if not cxc_cli.empty and "estado" in cxc_cli.columns:
                    facturas_pendientes = len(cxc_cli[cxc_cli["estado"].astype(str).str.lower() != "saldada"])

                # KPIs rápidas
                cfg_ec = obtener_configuracion()
                ec_empresa = cfg_ec.get("negocio_nombre") or "A&M"

                k1, k2, k3, k4 = st.columns(4)
                k1.metric("Total Facturado", f"RD$ {total_facturado:,.2f}")
                k2.metric("Total Abonado", f"RD$ {total_abonado:,.2f}")
                k3.metric("💳 Saldo Pendiente", f"RD$ {saldo_pendiente:,.2f}",
                          delta="En deuda" if saldo_pendiente > 0 else "Al día",
                          delta_color="inverse" if saldo_pendiente > 0 else "normal")
                k4.metric("Facturas Abiertas", facturas_pendientes)

                st.divider()

                # Tabla de CXC
                if not cxc_cli.empty:
                    st.markdown("**📋 Historial de Facturas a Crédito:**")
                    cols_show_cxc = [c for c in ["fecha", "numero_factura", "ncf", "monto_original", "monto_abonado", "saldo_pendiente", "estado"] if c in cxc_cli.columns]
                    st.dataframe(cxc_cli[cols_show_cxc] if cols_show_cxc else cxc_cli, use_container_width=True)
                else:
                    st.info("Este cliente no tiene facturas a crédito registradas.")

                if not abonos_cli.empty:
                    st.markdown("**💵 Historial de Abonos:**")
                    cols_show_ab = [c for c in ["fecha", "monto", "metodo_pago", "usuario", "observacion"] if c in abonos_cli.columns]
                    st.dataframe(abonos_cli[cols_show_ab] if cols_show_ab else abonos_cli, use_container_width=True)

                # Generar HTML imprimible del Estado de Cuenta
                filas_cxc_html = ""
                if not cxc_cli.empty:
                    for _, r in cxc_cli.iterrows():
                        fecha_f = str(r.get("fecha") or "—")[:10]
                        nfac = str(r.get("numero_factura") or r.get("ncf") or "—")
                        orig = float(r.get("monto_original") or 0)
                        abon = float(r.get("monto_abonado") or 0)
                        saldo = float(r.get("saldo_pendiente") or (orig - abon))
                        estado = str(r.get("estado") or "pendiente").upper()
                        color = "#c8e6c9" if estado == "SALDADA" else "#ffccbc"
                        filas_cxc_html += f"<tr style='background:{color}'><td>{fecha_f}</td><td>{nfac}</td><td style='text-align:right'>RD$ {orig:,.2f}</td><td style='text-align:right'>RD$ {abon:,.2f}</td><td style='text-align:right'><b>RD$ {saldo:,.2f}</b></td><td>{estado}</td></tr>"

                filas_abonos_html = ""
                if not abonos_cli.empty:
                    for _, r in abonos_cli.iterrows():
                        fecha_a = str(r.get("fecha") or "—")[:10]
                        monto_a = float(r.get("monto") or 0)
                        metodo_a = str(r.get("metodo_pago") or "—")
                        filas_abonos_html += f"<tr><td>{fecha_a}</td><td style='text-align:right'>RD$ {monto_a:,.2f}</td><td>{metodo_a}</td></tr>"

                html_ec = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;color:#111;}}
  h2{{text-align:center;font-size:20px;color:#1a237e;margin:0;}}
  .sub{{text-align:center;font-size:12px;color:#555;margin-bottom:12px;}}
  .datos{{display:flex;justify-content:space-between;background:#f5f5f5;padding:12px;border-radius:8px;margin:10px 0;font-size:12px;}}
  .kpis{{display:flex;gap:12px;margin:10px 0;}}
  .kpi{{flex:1;background:#e8eaf6;border-radius:8px;padding:10px;text-align:center;}}
  .kpi .val{{font-size:18px;font-weight:bold;color:#283593;}}
  .kpi .lbl{{font-size:10px;color:#666;}}
  table{{width:100%;border-collapse:collapse;font-size:11px;margin-top:8px;}}
  th{{background:#1a237e;color:#fff;padding:6px;text-align:left;}}
  td{{padding:5px 6px;border-bottom:1px solid #eee;}}
  .saldo-final{{font-size:16px;font-weight:bold;text-align:center;padding:12px;margin-top:16px;border:2px solid {'#c62828' if saldo_pendiente > 0 else '#2e7d32'};border-radius:8px;color:{'#c62828' if saldo_pendiente > 0 else '#2e7d32'};}}
  @media print{{button{{display:none;}}}}
</style></head><body>
<h2>📄 ESTADO DE CUENTA</h2>
<div class="sub">{ec_empresa} | Generado: {date.today()}</div>
<div class="datos">
  <div><b>Cliente:</b> {cliente_sel}<br><b>RNC/Cédula:</b> {rnc_cli}<br><b>Teléfono:</b> {tel_cli}</div>
  <div><b>Dirección:</b> {dir_cli}<br><b>Límite de Crédito:</b> RD$ {lim_cred:,.2f}</div>
</div>
<div class="kpis">
  <div class="kpi"><div class="val">RD$ {total_facturado:,.2f}</div><div class="lbl">TOTAL FACTURADO</div></div>
  <div class="kpi"><div class="val">RD$ {total_abonado:,.2f}</div><div class="lbl">TOTAL ABONADO</div></div>
  <div class="kpi"><div class="val">RD$ {saldo_pendiente:,.2f}</div><div class="lbl">SALDO PENDIENTE</div></div>
</div>
<h3>📋 Facturas a Crédito</h3>
<table>
<tr><th>Fecha</th><th>N° Factura / NCF</th><th>Monto Original</th><th>Abonado</th><th>Saldo</th><th>Estado</th></tr>
{filas_cxc_html if filas_cxc_html else '<tr><td colspan="6">Sin facturas registradas</td></tr>'}
</table>
<h3>💵 Abonos Realizados</h3>
<table>
<tr><th>Fecha</th><th>Monto</th><th>Método</th></tr>
{filas_abonos_html if filas_abonos_html else '<tr><td colspan="3">Sin abonos registrados</td></tr>'}
</table>
<div class="saldo-final">{'⚠️ SALDO PENDIENTE: RD$ ' + f'{saldo_pendiente:,.2f}' if saldo_pendiente > 0 else '✅ CLIENTE AL DÍA — Sin deudas pendientes'}</div>
<p style="font-size:10px;text-align:center;color:#999;margin-top:20px;">
  Este es un documento informativo generado por el Sistema {ec_empresa}.<br>
  No tiene validez fiscal. Para detalles fiscales consulte sus comprobantes NCF.
</p>
<script>window.onload=function(){{setTimeout(function(){{window.print();}},400);}}</script>
</body></html>"""

                st.download_button(
                    "🖨️ Descargar / Imprimir Estado de Cuenta",
                    data=html_ec.encode("utf-8"),
                    file_name=f"Estado_Cuenta_{cliente_sel.replace(' ', '_')}_{date.today()}.html",
                    mime="text/html",
                    key="btn_ec_imprimir",
                    use_container_width=True
                )



# =========================================================
# PROVEEDORES
# =========================================================


def render_creditos():
    st.title("💳 Créditos y Cuentas por Cobrar")

    def registrar_abono_general_fifo(cliente_nombre: str, monto_total: float, metodo_pago: str, observacion: str = "") -> bool:
        monto_total = float(monto_total)
        if monto_total <= 0:
            st.error("El monto del abono debe ser mayor que cero.")
            return False

        caja_activa = obtener_caja_abierta()
        if caja_activa is None:
            st.error("Debes tener una caja abierta para registrar abonos de crédito.")
            return False

        cxc = DATA.get("cuentas_por_cobrar", pd.DataFrame())
        if cxc.empty:
            st.error("No se encontraron deudas pendientes en cuentas por cobrar.")
            return False

        cxc_clean = cxc.copy()
        cxc_clean["_n"] = cxc_clean["cliente_nombre"].astype(str).apply(normalizar_texto)
        nombre_n = normalizar_texto(cliente_nombre)
        cuentas_cliente = cxc_clean[(cxc_clean["_n"] == nombre_n) & (cxc_clean["estado"].astype(str).str.lower() != "saldada")]
        
        if cuentas_cliente.empty:
            st.warning("Este cliente no tiene facturas con saldos pendientes actualmente.")
            return False

        if "fecha" in cuentas_cliente.columns:
            cuentas_cliente = cuentas_cliente.sort_values("fecha", ascending=True)
        else:
            cuentas_cliente = cuentas_cliente.sort_values("id", ascending=True)

        monto_restante = monto_total
        exito = False

        for _, fila_cxc in cuentas_cliente.iterrows():
            if monto_restante <= 0:
                break
            
            c_id = fila_cxc["id"]
            saldo_pend = float(limpiar_numero(fila_cxc.get("saldo_pendiente")) or 0)
            monto_original = float(limpiar_numero(fila_cxc.get("monto_original")) or 0)
            monto_abonado_ant = float(limpiar_numero(fila_cxc.get("monto_abonado")) or 0)
            
            if saldo_pend <= 0 and monto_original > 0:
                saldo_pend = max(monto_original - monto_abonado_ant, 0)
            
            if saldo_pend <= 0:
                continue

            aplicar = min(monto_restante, saldo_pend)
            nuevo_abonado = monto_abonado_ant + aplicar
            nuevo_saldo = max(monto_original - nuevo_abonado, 0.0)
            nuevo_estado = "saldada" if nuevo_saldo <= 0 else "pendiente"

            payload_abono = json_safe_payload({
                "cuenta_id": str(c_id),
                "cliente_id": fila_cxc.get("cliente_id"),
                "cliente_nombre": cliente_nombre,
                "monto": aplicar,
                "metodo_pago": metodo_pago,
                "fecha": ahora_str(),
                "usuario": nombre_usuario_actual(),
                "caja_id": json_safe_value(caja_activa.get("id")),
                "observacion": f"{observacion} (Abono FIFO general)".strip(),
            })
            
            try:
                supabase.table("abonos_credito").insert(payload_abono).execute()
            except Exception:
                try:
                    supabase.table("abonos_credito").insert(json_safe_payload({
                        "cuenta_id": str(c_id),
                        "cliente_nombre": cliente_nombre,
                        "monto": aplicar,
                        "metodo_pago": metodo_pago,
                        "usuario": nombre_usuario_actual(),
                    })).execute()
                except Exception as ex:
                    st.error(f"Error al guardar abono parcial para cuenta {c_id}: {ex}")
                    continue

            actualizar("cuentas_por_cobrar", c_id, {
                "monto_abonado": float(nuevo_abonado),
                "saldo_pendiente": float(nuevo_saldo),
                "estado": nuevo_estado,
            })

            mov_payload = json_safe_payload({
                "fecha": datetime.now().isoformat(),
                "dia_operativo": str(date.today()),
                "tipo_movimiento": "entrada",
                "origen": "abono_credito",
                "referencia_id": str(c_id),
                "metodo_pago": metodo_pago,
                "monto": float(aplicar),
                "descripcion": f"Abono FIFO a crédito {cliente_nombre}",
                "usuario": nombre_usuario_actual(),
                "caja_id": json_safe_value(caja_activa.get("id")),
            })
            try:
                if not metodo_es_mixto(mov_payload.get("metodo_pago")):
                    supabase.table("movimientos_caja").insert(mov_payload).execute()
            except Exception:
                pass

            cuenta_dinero = cuenta_por_metodo_pago(metodo_pago) if "cuenta_por_metodo_pago" in globals() else ("Efectivo negocio" if metodo_pago == "efectivo" else "Banco")
            try:
                registrar_movimiento_dinero(
                    "entrada",
                    float(aplicar),
                    f"Abono FIFO crédito {cliente_nombre}",
                    metodo_pago=metodo_pago,
                    cuenta=cuenta_dinero,
                    categoria="abono_credito",
                )
            except Exception:
                pass

            monto_restante -= aplicar
            exito = True

        if exito:
            st.success(f"¡Abono FIFO registrado! Se distribuyeron RD$ {monto_total:,.2f} liquidando las facturas más antiguas de {cliente_nombre}.")
            limpiar_cache_datos()
            return True
        return False

    puede_abonar_credito = es_admin() or tiene_permiso("puede_vender") or tiene_permiso("puede_ver_reportes")
    puede_editar_credito = es_admin() or tiene_permiso("puede_editar_todo")

    cxc = DATA.get("cuentas_por_cobrar", pd.DataFrame()).copy()
    if "es_credito" in cxc.columns:
        cxc = cxc[cxc["es_credito"] == True]
    cxc = cxc.copy()
    if not cxc.empty:
        # Ordenar cronológicamente para asignar folios secuenciales estables
        for col_f in ["fecha", "created_at"]:
            if col_f in cxc.columns:
                cxc["fecha_temp"] = pd.to_datetime(cxc[col_f], errors="coerce")
                cxc = cxc.sort_values("fecha_temp", ascending=True).drop(columns=["fecha_temp"])
                break
        cxc["Folio Crédito"] = [f"CR-{str(i+1).zfill(5)}" for i in range(len(cxc))]
    if cxc.empty:
        st.info("No hay cuentas por cobrar registradas actualmente en el sistema.")
    else:
        tab_consolidado, tab_expediente, tab_abono_fifo = st.tabs([
            "📊 Balance Consolidado de Clientes",
            "📂 Expediente y Ledger de Cuenta",
            "💵 Registrar Abono Inteligente (FIFO)"
        ])

        # ----------------------------------------------------
        # TAB 1: BALANCE CONSOLIDADO
        # ----------------------------------------------------
        with tab_consolidado:
            st.subheader("👥 Estado de Cuentas Consolidado")
            st.caption("Consolidado acumulativo de montos originales, abonados y pendientes por cliente.")

            grouped = cxc.groupby("cliente_nombre").agg({
                "monto_original": "sum",
                "monto_abonado": "sum",
                "saldo_pendiente": "sum",
                "estado": lambda x: (x.astype(str).str.lower() != "saldada").sum()
            }).reset_index()
            grouped.rename(columns={"estado": "Facturas Activas"}, inplace=True)

            unpaid = cxc[cxc["estado"].astype(str).str.lower() != "saldada"]
            if not unpaid.empty:
                fechas_min = unpaid.groupby("cliente_nombre")["fecha"].min().reset_index()
                grouped = pd.merge(grouped, fechas_min, on="cliente_nombre", how="left")
                grouped.rename(columns={"fecha": "Deuda Más Antigua"}, inplace=True)
            else:
                grouped["Deuda Más Antigua"] = "Al día"

            grouped["Deuda Más Antigua"] = grouped["Deuda Más Antigua"].fillna("Al día").astype(str).str[:10]

            buscar_cli = st.text_input("Buscar cliente por nombre", key="buscar_creditos_consolidado")
            if buscar_cli:
                grouped = grouped[grouped["cliente_nombre"].astype(str).str.contains(buscar_cli, case=False, na=False)]

            display_df = grouped.copy()
            display_df["Monto Original"] = display_df["monto_original"].apply(lambda x: f"RD$ {x:,.2f}")
            display_df["Total Abonado"] = display_df["monto_abonado"].apply(lambda x: f"RD$ {x:,.2f}")
            display_df["Saldo Pendiente"] = display_df["saldo_pendiente"].apply(lambda x: f"RD$ {x:,.2f}")

            cols_show = ["cliente_nombre", "Facturas Activas", "Monto Original", "Total Abonado", "Saldo Pendiente", "Deuda Más Antigua"]
            display_df = display_df[cols_show]
            display_df.rename(columns={"cliente_nombre": "Cliente"}, inplace=True)

            st.dataframe(display_df, use_container_width=True)
            if not es_cajera():
                descargar_archivos(display_df, "balance_consolidado_creditos")

        # ----------------------------------------------------
        # TAB 2: EXPEDIENTE Y LEDGER
        # ----------------------------------------------------
        with tab_expediente:
            st.subheader("📂 Expediente de Cuenta y Libro Auxiliar (Ledger)")
            st.caption("Visualiza el historial detallado de cargos (ventas) y abonos de forma cronológica.")

            clientes_disponibles = sorted(cxc["cliente_nombre"].dropna().unique().tolist())
            if not clientes_disponibles:
                st.info("No hay clientes registrados en el módulo de crédito.")
            else:
                cliente_sel = st.selectbox("Seleccione el Cliente", clientes_disponibles, key="ledger_cliente_sel")
                cxc_cliente = cxc[cxc["cliente_nombre"] == cliente_sel]

                total_deuda = cxc_cliente["monto_original"].sum()
                total_abonado = cxc_cliente["monto_abonado"].sum()
                saldo_total = cxc_cliente["saldo_pendiente"].sum()
                facturas_activas = (cxc_cliente["estado"].astype(str).str.lower() != "saldada").sum()

                cm1, cm2, cm3, cm4 = st.columns(4)
                cm1.metric("Saldo Pendiente", f"RD$ {saldo_total:,.2f}", delta=f"{facturas_activas} activas" if saldo_total > 0 else "Al día", delta_color="inverse")
                cm2.metric("Total Consumido", f"RD$ {total_deuda:,.2f}")
                cm3.metric("Total Abonado", f"RD$ {total_abonado:,.2f}")
                cm4.metric("Facturas Pendientes", str(facturas_activas))

                ledger_entries = []
                for _, row in cxc_cliente.iterrows():
                    fecha_val = row.get("fecha") or row.get("created_at") or ahora_str()
                    ledger_entries.append({
                        "fecha": fecha_val,
                        "tipo": "Cargo ➕ (Venta)",
                        "referencia": f"Venta #{row.get('venta_id') or row.get('id')}",
                        "monto_cargo": float(row.get("monto_original") or 0),
                        "monto_abono": 0.0,
                        "timestamp": pd.to_datetime(fecha_val, errors="coerce")
                    })

                abonos_df = DATA.get("abonos_credito", pd.DataFrame())
                if not abonos_df.empty:
                    abonos_cliente = abonos_df[abonos_df["cliente_nombre"] == cliente_sel]
                    for _, row in abonos_cliente.iterrows():
                        fecha_val = row.get("fecha") or row.get("created_at") or ahora_str()
                        ledger_entries.append({
                            "fecha": fecha_val,
                            "tipo": "Abono ➖ (Pago)",
                            "referencia": f"Pago: {row.get('metodo_pago','').upper()} - {row.get('observacion','')}".strip(" -"),
                            "monto_cargo": 0.0,
                            "monto_abono": float(row.get("monto") or 0),
                            "timestamp": pd.to_datetime(fecha_val, errors="coerce")
                        })

                if ledger_entries:
                    ledger_df = pd.DataFrame(ledger_entries)
                    ledger_df.sort_values("timestamp", ascending=True, inplace=True)

                    running_balance = 0.0
                    saldos_acumulados = []
                    for _, row in ledger_df.iterrows():
                        running_balance += row["monto_cargo"] - row["monto_abono"]
                        saldos_acumulados.append(running_balance)
                    
                    ledger_df["Saldo Acumulado"] = saldos_acumulados

                    ledger_display = ledger_df.copy()
                    ledger_display["fecha"] = ledger_display["fecha"].astype(str).str[:16]
                    ledger_display["Cargo"] = ledger_display["monto_cargo"].apply(lambda x: f"RD$ {x:,.2f}" if x > 0 else "")
                    ledger_display["Abono"] = ledger_display["monto_abono"].apply(lambda x: f"RD$ {x:,.2f}" if x > 0 else "")
                    ledger_display["Saldo Acumulado"] = ledger_display["Saldo Acumulado"].apply(lambda x: f"RD$ {x:,.2f}")

                    ledger_display = ledger_display[["fecha", "tipo", "referencia", "Cargo", "Abono", "Saldo Acumulado"]]
                    ledger_display.rename(columns={
                        "fecha": "Fecha/Hora",
                        "tipo": "Movimiento",
                        "referencia": "Referencia / Detalle"
                    }, inplace=True)

                    st.dataframe(ledger_display, use_container_width=True)
                    if not es_cajera():
                        descargar_archivos(ledger_display, f"ledger_cxc_{cliente_sel}")
                else:
                    st.info("No hay transacciones registradas para este cliente.")
                # Vista de corrección
                if puede_editar_credito:
                    st.markdown("---")
                    with st.expander("🛠️ Corrección Administrativa de Créditos", expanded=False):
                        st.warning("Solo administración: usa esto para corregir errores, no para registrar pagos normales.")
                        render_crud_generico("cuentas_por_cobrar", cxc, "Editar / eliminar cuentas por cobrar")
                        # Dividir Crédito en cuotas
                        st.subheader("Dividir Crédito en Cuotas")
                        if not cxc.empty:
                            credit_ids = cxc["id"].astype(str).tolist()
                            selected_id = st.selectbox("Seleccionar cuenta de crédito", options=credit_ids, key="dividir_credito_select")
                            if selected_id:
                                row = cxc[cxc["id"].astype(str) == selected_id].iloc[0]
                                saldo = float(limpiar_numero(row.get("saldo_pendiente")) or 0)
                                st.write(f"Saldo pendiente: RD$ {saldo:,.2f}")
                                max_cuotas = max(1, int(saldo) if saldo.is_integer() else int(saldo) + 1)
                                num_cuotas = st.number_input("Número de cuotas", min_value=1, max_value=max_cuotas, value=1, step=1, key="num_cuotas")
                                if st.button("Crear Cuotas", key="btn_dividir_credito"):
                                    monto_cuota = round(saldo / num_cuotas, 2)
                                    caja_activa = obtener_caja_abierta()
                                    if not caja_activa:
                                        st.error("Abre una caja antes de crear abonos.")
                                    else:
                                        for i in range(num_cuotas):
                                            payload_abono = json_safe_payload({
                                                "cuenta_id": selected_id,
                                                "cliente_id": row.get("cliente_id"),
                                                "cliente_nombre": row.get("cliente_nombre"),
                                                "monto": monto_cuota,
                                                "metodo_pago": "cuota",
                                                "fecha": ahora_str(),
                                                "usuario": nombre_usuario_actual(),
                                                "caja_id": json_safe_value(caja_activa.get("id")),
                                                "observacion": f"Dividir crédito en cuota {i+1}/{num_cuotas}"
                                            })
                                            try:
                                                supabase.table("abonos_credito").insert(payload_abono).execute()
                                            except Exception as e:
                                                st.error(f"Error al crear abono: {e}")
                                                break
                                        else:
                                            st.success("Cuotas creadas exitosamente.")
                                            st.rerun()

        # ----------------------------------------------------
        # TAB 3: REGISTRAR ABONO INTELIGENTE (FIFO)
        # ----------------------------------------------------
        with tab_abono_fifo:
            st.subheader("💵 Registrar Abono Inteligente (Método FIFO)")
            st.caption("Ingresa un abono general. El sistema liquidará automáticamente las facturas más antiguas del cliente primero.")

            clientes_con_deuda = sorted(grouped[grouped["saldo_pendiente"] > 0]["cliente_nombre"].unique().tolist())
            if not clientes_con_deuda:
                st.success("🎉 ¡Perfecto! Ningún cliente tiene saldos pendientes de pago.")
            else:
                cliente_deuda_sel = st.selectbox("Seleccione el Cliente deudor", clientes_con_deuda, key="abono_cliente_sel")
                cxc_deudor = cxc[cxc["cliente_nombre"] == cliente_deuda_sel]
                saldo_deuda_total = cxc_deudor["saldo_pendiente"].sum()

                st.info(f"Saldo pendiente total de {cliente_deuda_sel}: **RD$ {saldo_deuda_total:,.2f}**")

                c_a1, c_a2, c_a3 = st.columns(3)
                with c_a1:
                    monto_abono = st.number_input("Monto a Abonar (RD$)", min_value=0.0, step=100.0, max_value=float(saldo_deuda_total), key="abono_fifo_monto")
                with c_a2:
                    metodo_abono = st.selectbox("Método de Pago", ["efectivo", "transferencia", "tarjeta"], key="abono_fifo_metodo")
                with c_a3:
                    saldar_deuda_completa = st.checkbox("Saldar Cuenta Completa", value=False, key="abono_fifo_saldar_todo")
                    if saldar_deuda_completa:
                        monto_abono = float(saldo_deuda_total)

                obs_abono = st.text_input("Observación / Concepto del Pago", placeholder="Ej. Pago parcial del mes", key="abono_fifo_obs")

                caja_activa = obtener_caja_abierta()
                if caja_activa is None:
                    st.warning("⚠️ Debes abrir caja antes de registrar cualquier abono.")
                else:
                    st.success(f"💵 Este abono entrará a la caja activa de **{nombre_usuario_actual()}**.")

                if puede_abonar_credito:
                    if st.button("💾 Guardar Abono Inteligente (FIFO)", key="btn_fifo_abono_save"):
                        if caja_activa is None:
                            st.error("Abre caja antes de registrar abonos.")
                        elif monto_abono <= 0:
                            st.error("El monto debe ser mayor que cero.")
                        else:
                            if registrar_abono_general_fifo(cliente_deuda_sel, monto_abono, metodo_abono, obs_abono):
                                st.rerun()

        # Vista de corrección
# (admin edit UI moved above, duplicated block removed)
# =========================================================
# USUARIOS
# =========================================================

# =========================================================
# CAPITAL BASE
# =========================================================

# =========================================================
# DISTRIBUCIÓN DE BENEFICIOS
# =========================================================


def render_dinero_real():
    st.title("💰 Dinero Real PRO")
    if not es_admin():
        st.error("No tienes permiso para acceder a Dinero Real.")
        st.stop()

    st.caption("Estado de cuenta del negocio: entradas, salidas, balance, efectivo, banco, inversión y ganancia estimada.")

    resumen = resumen_dinero_real_pro()
    hist = resumen["historial"]

    st.markdown("### 📊 Resumen general")
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("💵 Efectivo negocio", f"RD$ {resumen['efectivo']:,.2f}")
    r2.metric("🏦 Banco", f"RD$ {resumen['banco']:,.2f}")
    r3.metric("💰 Total disponible", f"RD$ {resumen['total_disponible']:,.2f}")
    r4.metric("💳 Crédito pendiente", f"RD$ {resumen['credito']:,.2f}")

    st.markdown("### 💵 Distribución del dinero disponible")
    dd1, dd2, dd3 = st.columns(3)
    dd1.metric("💼 Dinero de inversión / capital", f"RD$ {resumen['dinero_inversion']:,.2f}")
    dd2.metric("📈 Dinero de ganancia disponible", f"RD$ {resumen['dinero_ganancia']:,.2f}")
    dd3.metric("⚖️ Saldo inicial / capital base", f"RD$ {resumen['saldo_inicial']:,.2f}")

    st.markdown("### 📦 Inversión y ganancia")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("📦 Inventario a costo", f"RD$ {resumen['inventario_costo']:,.2f}")
    i2.metric("🏷️ Inventario a venta", f"RD$ {resumen['inventario_venta']:,.2f}")
    i3.metric("📈 Ganancia potencial inventario", f"RD$ {resumen['ganancia_potencial_inventario']:,.2f}")
    i4.metric("🧾 Ganancia líquida estimada", f"RD$ {resumen['ganancia_estimada']:,.2f}")
    if resumen.get("fuente_inventario"):
        st.caption(f"Inventario calculado desde: {resumen.get('fuente_inventario')}")
    with st.expander("🔎 Revisar columnas usadas para inventario", expanded=False):
        st.write("El sistema toma la columna de stock, costo y precio que tenga valores reales. Si aquí sale cero, revisa que productos tenga cantidad/stock, costo y precio_venta/precio.")
        try:
            prod_debug = leer_actualizado("productos")
            cols_debug = [c for c in ["nombre", "codigo", "stock", "cantidad", "existencia", "costo", "costo_unitario", "costo_promedio", "precio", "precio_venta", "precio_especial"] if c in prod_debug.columns]
            st.dataframe(prod_debug[cols_debug].head(20) if cols_debug else prod_debug.head(20), use_container_width=True)
        except Exception as e:
            st.warning(f"No se pudo mostrar productos: {e}")

    st.info(
        "Lectura rápida: Total disponible es efectivo + banco. "
        "El crédito pendiente sube cuando vendes fiado y baja cuando registras un abono. "
        "Inventario a costo es mercancía comprada; inventario a venta es una proyección si se vende todo. "
        "La ganancia líquida estimada NO suma el inventario, para no inflar la ganancia."
    )

    st.markdown("---")
    st.subheader("📚 Historial financiero tipo estado de cuenta")

    if hist.empty:
        st.info("Todavía no hay movimientos para mostrar.")
    else:
        f1, f2 = rango_fechas_ui("dinero_real_pro")
        c1, c2, c3 = st.columns(3)
        cuenta_filtro = c1.selectbox("Cuenta", ["Todas"] + sorted(hist["cuenta"].fillna("Pendiente").astype(str).unique().tolist()), key="drp_cuenta")
        tipo_filtro = c2.selectbox("Tipo", ["Todos"] + sorted(hist["tipo"].fillna("").astype(str).unique().tolist()), key="drp_tipo")
        texto = c3.text_input("Buscar", key="drp_buscar")

        vista = hist.copy()
        if "_fecha_dt" in vista.columns:
            vista = vista[(vista["_fecha_dt"].dt.date >= f1) & (vista["_fecha_dt"].dt.date <= f2)]
        if cuenta_filtro != "Todas":
            vista = vista[vista["cuenta"].astype(str) == cuenta_filtro]
        if tipo_filtro != "Todos":
            vista = vista[vista["tipo"].astype(str) == tipo_filtro]
        vista = buscar_df(vista, texto)

        cols = ["fecha", "tipo", "origen", "concepto", "cuenta", "metodo_pago", "entrada", "salida", "neto", "balance_cuenta", "balance_total", "detalle"]
        cols = [c for c in cols if c in vista.columns]
        st.dataframe(vista[cols], use_container_width=True)
        descargar_archivos(vista[cols], "dinero_real_estado_cuenta")

    st.markdown("---")
    st.subheader("➕ Movimiento manual")
    st.caption("Úsalo solo para ajustes, entradas/salidas fuera del sistema o transferencias internas. No lo uses para ventas/gastos/compras ya registrados.")

    tipo_mov = st.selectbox(
        "Tipo de movimiento",
        ["entrada", "salida", "transferencia interna", "depósito al banco", "retiro del banco", "aporte", "retiro"],
        key="dinero_tipo_mov",
    )
    monto_mov = st.number_input("Monto", min_value=0.0, step=1.0, key="dinero_monto")
    descripcion_mov = st.text_input("Descripción", key="dinero_descripcion")

    if tipo_mov in ["transferencia interna", "depósito al banco", "retiro del banco"]:
        if tipo_mov == "depósito al banco":
            cuenta_origen = "Efectivo negocio"
            cuenta_destino = "Banco"
            st.info("Sale del efectivo del negocio y entra al banco. El total general no cambia.")
        elif tipo_mov == "retiro del banco":
            cuenta_origen = "Banco"
            cuenta_destino = "Efectivo negocio"
            st.info("Sale del banco y entra al efectivo del negocio. El total general no cambia.")
        else:
            ca, cb = st.columns(2)
            cuenta_origen = ca.selectbox("Cuenta origen", ["Efectivo negocio", "Banco"], key="dinero_origen")
            cuenta_destino = cb.selectbox("Cuenta destino", ["Banco", "Efectivo negocio"], key="dinero_destino")

        if st.button("Guardar transferencia", key="btn_dinero_transferencia"):
            if monto_mov <= 0:
                st.error("El monto debe ser mayor que cero.")
            elif cuenta_origen == cuenta_destino:
                st.error("La cuenta origen y destino no pueden ser iguales.")
            else:
                ok = registrar_movimiento_dinero(
                    tipo_mov,
                    monto_mov,
                    descripcion_mov,
                    cuenta_origen=cuenta_origen,
                    cuenta_destino=cuenta_destino,
                    categoria="transferencia interna",
                )
                if ok:
                    st.success("Movimiento guardado.")
                    st.rerun()
    else:
        metodo_mov = st.selectbox("Método / cuenta", ["efectivo", "transferencia", "tarjeta", "banco"], key="dinero_metodo")
        cuenta_mov = cuenta_por_metodo_pago(metodo_mov) if "cuenta_por_metodo_pago" in globals() else _cuenta_por_metodo_pro(metodo_mov)
        st.write(f"Afectará la cuenta: **{cuenta_mov}**")

        if st.button("Guardar movimiento", key="btn_dinero_movimiento"):
            if monto_mov <= 0:
                st.error("El monto debe ser mayor que cero.")
            else:
                ok = registrar_movimiento_dinero(
                    tipo_mov,
                    monto_mov,
                    descripcion_mov,
                    metodo_pago=metodo_mov,
                    cuenta=cuenta_mov,
                    categoria="manual",
                )
                if ok:
                    st.success("Movimiento guardado.")
                    st.rerun()

    st.markdown("---")
    st.subheader("✏️ Editar / eliminar movimiento manual")
    movs_edit = leer_actualizado("movimientos_dinero")
    if movs_edit.empty:
        st.info("No hay movimientos manuales para editar.")
    else:
        if "fecha" in movs_edit.columns:
            movs_edit["_fecha_dt"] = pd.to_datetime(movs_edit["fecha"], errors="coerce")
            movs_edit = movs_edit.sort_values("_fecha_dt", ascending=False)

        opciones_mov = []
        mapa_mov = {}
        for _, r in movs_edit.iterrows():
            rid = r.get("id")
            fecha = r.get("fecha", "")
            tipo = r.get("tipo", "")
            monto = float(limpiar_numero(r.get("monto")) or 0)
            desc = limpiar_texto(r.get("descripcion"))
            etiqueta = f"{fecha} | {tipo} | RD$ {monto:,.2f} | {desc[:40]}"
            opciones_mov.append(etiqueta)
            mapa_mov[etiqueta] = r.to_dict()

        sel_mov = st.selectbox("Selecciona movimiento", opciones_mov, key="dinero_edit_sel")
        mov = mapa_mov[sel_mov]
        mov_id = mov.get("id")

        e1, e2 = st.columns(2)
        tipos = ["entrada", "salida", "transferencia interna", "depósito al banco", "retiro del banco", "aporte", "retiro"]
        tipo_actual = limpiar_texto(mov.get("tipo")) or "entrada"
        tipo_edit = e1.selectbox("Tipo", tipos, index=tipos.index(tipo_actual) if tipo_actual in tipos else 0, key="dinero_edit_tipo")
        monto_edit = e2.number_input("Monto", min_value=0.0, step=1.0, value=float(limpiar_numero(mov.get("monto")) or 0), key="dinero_edit_monto")
        desc_edit = st.text_input("Descripción", value=limpiar_texto(mov.get("descripcion")), key="dinero_edit_desc")

        metodo_edit = ""
        cuenta_edit = ""
        cuenta_origen_edit = ""
        cuenta_destino_edit = ""

        if tipo_edit in ["transferencia interna", "depósito al banco", "retiro del banco"]:
            if tipo_edit == "depósito al banco":
                cuenta_origen_edit = "Efectivo negocio"
                cuenta_destino_edit = "Banco"
            elif tipo_edit == "retiro del banco":
                cuenta_origen_edit = "Banco"
                cuenta_destino_edit = "Efectivo negocio"
            else:
                ce1, ce2 = st.columns(2)
                cuentas_opts = ["Efectivo negocio", "Banco"]
                origen_actual = limpiar_texto(mov.get("cuenta_origen")) or "Efectivo negocio"
                destino_actual = limpiar_texto(mov.get("cuenta_destino")) or "Banco"
                cuenta_origen_edit = ce1.selectbox("Cuenta origen", cuentas_opts, index=cuentas_opts.index(origen_actual) if origen_actual in cuentas_opts else 0, key="dinero_edit_origen")
                cuenta_destino_edit = ce2.selectbox("Cuenta destino", cuentas_opts, index=cuentas_opts.index(destino_actual) if destino_actual in cuentas_opts else 1, key="dinero_edit_destino")
        else:
            metodos = ["efectivo", "transferencia", "tarjeta", "banco"]
            metodo_actual = limpiar_texto(mov.get("metodo_pago")) or "efectivo"
            metodo_edit = st.selectbox("Método / cuenta", metodos, index=metodos.index(metodo_actual) if metodo_actual in metodos else 0, key="dinero_edit_metodo")
            cuenta_edit = cuenta_por_metodo_pago(metodo_edit) if "cuenta_por_metodo_pago" in globals() else _cuenta_por_metodo_pro(metodo_edit)

        b1, b2 = st.columns(2)
        with b1:
            if st.button("💾 Guardar corrección", key="btn_dinero_guardar_correccion"):
                payload = {
                    "tipo": tipo_edit,
                    "monto": float(monto_edit),
                    "descripcion": desc_edit,
                    "metodo_pago": metodo_edit,
                    "cuenta": cuenta_edit,
                    "cuenta_origen": cuenta_origen_edit,
                    "cuenta_destino": cuenta_destino_edit,
                    "categoria": limpiar_texto(mov.get("categoria")) or "manual",
                    "usuario": nombre_usuario_actual() if "nombre_usuario_actual" in globals() else "",
                }
                ok = actualizar("movimientos_dinero", mov_id, payload)
                if ok:
                    st.success("Movimiento corregido.")
                    st.rerun()

        with b2:
            confirmar_delete = st.checkbox("Confirmo eliminar este movimiento", key="dinero_confirmar_delete")
            if st.button("🗑️ Eliminar movimiento", key="btn_dinero_eliminar_mov"):
                if not confirmar_delete:
                    st.warning("Marca la confirmación antes de eliminar.")
                else:
                    ok = eliminar("movimientos_dinero", mov_id)
                    if ok:
                        st.success("Movimiento eliminado.")
                        st.rerun()


# =========================================================
# CLIENTES
# =========================================================


