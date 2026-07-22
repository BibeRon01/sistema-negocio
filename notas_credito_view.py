import streamlit as st
import pandas as pd
from datetime import datetime
try:
    from core.helpers import (
        leer_tabla, insertar, actualizar, normalizar_texto,
        refrescar_producto_por_id, producto_tiene_inventario,
        obtener_existencia_producto, actualizar_existencia_producto,
        sincronizar_producto_inventario, registrar_movimiento_inventario,
        consumir_ncf_siguiente, obtener_tenant_actual, nombre_usuario_actual,
        ahora_str, json_safe_payload
    )
except ModuleNotFoundError:
    from helpers import (
        leer_tabla, insertar, actualizar, normalizar_texto,
        refrescar_producto_por_id, producto_tiene_inventario,
        obtener_existencia_producto, actualizar_existencia_producto,
        sincronizar_producto_inventario, registrar_movimiento_inventario,
        consumir_ncf_siguiente, obtener_tenant_actual, nombre_usuario_actual,
        ahora_str, json_safe_payload
    )

def render_notas_credito():
    st.title("❌ Notas de Crédito (E34 / B04)")
    st.caption("Emisión oficial de Notas de Crédito para devoluciones, descuentos o corrección de facturas.")

    # 1. Mostrar Historial de Notas de Crédito emitidas
    st.subheader("📜 Historial de Notas de Crédito")
    try:
        nc_data = leer_tabla("notas_credito")
        df_nc = pd.DataFrame(nc_data or [])
        if not df_nc.empty:
            df_nc = df_nc.sort_values("fecha", ascending=False)
            cols_nc = [c for c in ["fecha", "ncf", "venta_id", "motivo", "subtotal", "itbis", "monto_total", "usuario"] if c in df_nc.columns]
            st.dataframe(df_nc[cols_nc] if cols_nc else df_nc, use_container_width=True)
        else:
            st.info("No se han registrado Notas de Crédito en el sistema.")
    except Exception as e:
        st.warning(f"Error cargando historial de notas de crédito: {e}")

    st.markdown("---")
    st.subheader("➕ Emitir Nueva Nota de Crédito")

    # 2. Buscar Factura Original
    st.write("Busca la factura de venta original que deseas anular o modificar:")
    c_bus1, c_bus2 = st.columns([3, 1])
    with c_bus1:
        txt_bus = st.text_input("Ingrese NCF o Número de Factura original", key="nc_fact_bus_txt")
    with c_bus2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        btn_bus = st.button("🔍 Buscar Factura", key="nc_btn_bus_fact")

    if txt_bus:
        try:
            ventas_data = leer_tabla("ventas")
            df_ventas = pd.DataFrame(ventas_data or [])
            
            factura_encontrada = None
            if not df_ventas.empty:
                # Filtrar ventas no anuladas
                df_ventas = df_ventas[~df_ventas["anulado"].fillna(False).astype(bool)]
                
                # Buscar coincidencia exacta
                mask = (df_ventas["numero_factura"].astype(str).str.strip().str.upper() == txt_bus.strip().upper()) | \
                       (df_ventas["ncf"].astype(str).str.strip().str.upper() == txt_bus.strip().upper())
                res = df_ventas[mask]
                if not res.empty:
                    factura_encontrada = res.iloc[0].to_dict()
                    
            if not factura_encontrada:
                st.error("🚫 No se encontró ninguna factura activa con el NCF o número provisto.")
            else:
                venta_id = factura_encontrada["id"]
                st.success(f"✅ Factura encontrada: {factura_encontrada.get('numero_factura')} (NCF: {factura_encontrada.get('ncf') or 'Ninguno'})")
                
                # Mostrar datos de la factura
                col_info1, col_info2, col_info3 = st.columns(3)
                col_info1.markdown(f"**Cliente:** {factura_encontrada.get('cliente_nombre')}")
                col_info2.markdown(f"**Fecha:** {factura_encontrada.get('fecha')[:10] if factura_encontrada.get('fecha') else 'N/A'}")
                col_info3.markdown(f"**Total Facturado:** RD$ {float(factura_encontrada.get('total') or 0):,.2f}")
                
                # Cargar detalle de la factura
                det_data = leer_tabla("detalle_venta")
                df_det = pd.DataFrame(det_data or [])
                
                if df_det.empty:
                    st.warning("Esta factura no registra renglones o detalles en la base de datos.")
                else:
                    df_det_fact = df_det[df_det["venta_id"].astype(str) == str(venta_id)].copy()
                    if df_det_fact.empty:
                        st.warning("No se encontraron partidas para esta factura.")
                    else:
                        st.markdown("### 📋 Partidas de la Factura y Cantidades a Devolver")
                        st.write("Indique la cantidad de cada producto que será devuelta o acreditada:")
                        
                        items_devolucion = []
                        total_devolucion = 0.0
                        total_itbis_devolucion = 0.0
                        
                        for idx, item in df_det_fact.iterrows():
                            p_id = item.get("producto_id")
                            p_nom = item.get("producto") or ""
                            p_cant = float(item.get("cantidad") or 0.0)
                            p_precio = float(item.get("precio_unitario") or 0.0)
                            p_total_linea = float(item.get("total_linea") or 0.0)
                            
                            c_item1, c_item2, c_item3, c_item4 = st.columns([4, 2, 2, 2])
                            with c_item1:
                                st.markdown(f"📦 **{p_nom}**")
                            with c_item2:
                                st.write(f"Precio: RD$ {p_precio:,.2f}")
                            with c_item3:
                                st.write(f"Facturado: {p_cant:.0f} uds.")
                            with c_item4:
                                cant_dev = st.number_input(
                                    "Devolver:",
                                    min_value=0.0,
                                    max_value=p_cant,
                                    value=0.0,
                                    step=1.0,
                                    key=f"nc_dev_cant_{venta_id}_{p_id}"
                                )
                                
                            if cant_dev > 0:
                                val_linea = cant_dev * p_precio
                                # Calcular proporcionalidad de ITBIS
                                # Si la venta original tenía ITBIS, extraemos proporcionalmente
                                # total_itbis de venta original
                                v_itbis_total = float(factura_encontrada.get("itbis_total") or 0.0)
                                v_total = float(factura_encontrada.get("total") or 1.0)
                                ratio_itbis = v_itbis_total / v_total if v_total > 0 else 0.0
                                
                                itbis_linea = val_linea * ratio_itbis
                                total_devolucion += val_linea
                                total_itbis_devolucion += itbis_linea
                                
                                items_devolucion.append({
                                    "producto_id": str(p_id),
                                    "producto": p_nom,
                                    "cantidad": cant_dev,
                                    "precio_unitario": p_precio,
                                    "total": val_linea,
                                    "costo_unitario": float(item.get("costo_unitario") or 0.0)
                                })
                        
                        if total_devolucion > 0:
                            st.markdown("---")
                            st.markdown("### 🧮 Resumen del Crédito / Devolución")
                            
                            subtotal_devolucion = total_devolucion - total_itbis_devolucion
                            
                            c_r1, c_r2, c_r3 = st.columns(3)
                            c_r1.metric("Subtotal Acreditado", f"RD$ {subtotal_devolucion:,.2f}")
                            c_r2.metric("ITBIS Acreditado", f"RD$ {total_itbis_devolucion:,.2f}")
                            c_r3.metric("Monto Total de Crédito", f"RD$ {total_devolucion:,.2f}")
                            
                            # Motivo de la Nota de Crédito
                            motivo = st.selectbox(
                                "Motivo de la Nota de Crédito*",
                                ["Devolución parcial de mercancías", "Devolución total de mercancías", "Descuento o bonificación", "Error en facturación de precios / cantidades", "Otros"],
                                key="nc_motivo"
                            )
                            
                            observacion_extra = st.text_input("Comentarios / Detalles del motivo", key="nc_obs_extra")
                            
                            # Confirmar y generar
                            if st.button("🔥 Emitir Nota de Crédito E34 / B04", key="nc_btn_confirmar_emision", type="primary"):
                                try:
                                    # Generar NCF Nota de Crédito (E34 si factura original empieza por E, B04 si empieza por B)
                                    original_ncf = factura_encontrada.get("ncf") or ""
                                    tipo_nc = "B04"
                                    if original_ncf.upper().startswith("E"):
                                        tipo_nc = "E34"
                                        
                                    ncf_nc = consumir_ncf_siguiente(tipo_nc)
                                    if not ncf_nc:
                                        st.error(f"⚠️ No hay secuencias DGII disponibles para {tipo_nc}. Registra un nuevo bloque en Configuración.")
                                        st.stop()
                                        
                                    # 1. Registrar Nota de Crédito en BD
                                    payload_nc = {
                                        "empresa_id": obtener_tenant_actual(),
                                        "venta_id": str(venta_id),
                                        "ncf": ncf_nc,
                                        "fecha": datetime.now().isoformat(),
                                        "motivo": f"{motivo} - {observacion_extra}".strip(" -"),
                                        "monto_total": float(total_devolucion),
                                        "subtotal": float(subtotal_devolucion),
                                        "itbis": float(total_itbis_devolucion),
                                        "detalles": items_devolucion,
                                        "usuario": nombre_usuario_actual()
                                    }
                                    
                                    nc_resp = insertar("notas_credito", payload_nc)
                                    if not nc_resp:
                                        st.error("No se pudo guardar la Nota de Crédito en la base de datos.")
                                        st.stop()
                                        
                                    # 2. Devolver stock a inventario
                                    for it in items_devolucion:
                                        pid = it["producto_id"]
                                        cant = float(it["cantidad"])
                                        
                                        prod_ref = refrescar_producto_por_id(pid)
                                        if prod_ref is not None:
                                            if producto_tiene_inventario(prod_ref):
                                                cant_actual = obtener_existencia_producto(prod_ref)
                                                nueva_cant = cant_actual + cant
                                                actualizar_existencia_producto(prod_ref, nueva_cant)
                                                
                                                prod_sync = refrescar_producto_por_id(pid) or prod_ref
                                                sincronizar_producto_inventario(prod_sync, ahora_str(), f"Devolución Nota de Crédito {ncf_nc}")
                                                
                                                registrar_movimiento_inventario(
                                                    prod_ref["id"],
                                                    prod_ref["nombre"],
                                                    "entrada_devolucion",
                                                    "notas_credito",
                                                    ncf_nc,
                                                    cant,
                                                    float(it["costo_unitario"]),
                                                    f"Devolución por Nota de Crédito NCF {ncf_nc}"
                                                )
                                                
                                    st.success(f"🎉 Nota de Crédito {ncf_nc} emitida con éxito. Stock reincorporado al inventario.")
                                    st.rerun()
                                except Exception as e_nc:
                                    st.error(f"Error procesando Nota de Crédito: {e_nc}")
                        else:
                            st.info("💡 Aumente la cantidad a devolver en al menos un producto para habilitar la emisión de la Nota de Crédito.")
        except Exception as e_glob:
            st.error(f"Error al buscar o cargar detalles de factura: {e_glob}")
