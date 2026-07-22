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

def render_productos():
    st.title("📦 Productos")
    st.caption("Catálogo maestro de productos con código, precios múltiples y control de inventario.")

    with st.expander("📥 Subir Excel / CSV de productos", expanded=False):
        st.write("Formato recomendado: Codigo | Nombre | Categoria | Stock | Costo | PrecioVenta")
        modo_carga = st.selectbox(
            "Cómo tratar productos existentes",
            ["Actualizar costo/precio y sumar cantidad", "Actualizar costo/precio y reemplazar cantidad", "Solo actualizar datos sin mover cantidad"],
            key="prod_modo_carga"
        )
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv", "txt"], key="up_productos")

        if archivo is not None:
            df_preview = preparar_import_productos(leer_archivo_subido(archivo))
            st.caption("Vista previa de lo que se va a cargar")
            cols_prev = [c for c in ["codigo", "nombre", "categoria", "stock", "costo", "precio_venta", "precio_especial", "total_costo_inventario", "total_valor_venta", "ganancia_potencial"] if c in df_preview.columns]
            st.dataframe(df_preview[cols_prev].head(20) if cols_prev else df_preview.head(20), use_container_width=True)

            if df_preview.empty or "nombre" not in df_preview.columns:
                st.error("El archivo no tiene productos válidos. Debe traer al menos Nombre.")
            elif st.button("✅ Confirmar y guardar productos", key="btn_confirmar_productos_pro"):
                barra = st.progress(0)
                estado = st.empty()
                procesados = 0
                errores = 0
                filas_con_error = []  # Reporte detallado de fallos

                base_codigo_gen = generar_codigo_producto()
                prefix_part = "PO"
                num_part = base_codigo_gen.replace(prefix_part, "")
                next_num = int(num_part) if num_part.isdigit() else 1

                for i, row in df_preview.iterrows():
                    nombre = ""
                    try:
                        nombre = limpiar_texto(row.get("nombre"))
                        if not nombre:
                            continue  # Fila vacía, se ignora sin contar

                        codigo = limpiar_texto(row.get("codigo"))
                        if not codigo:
                            codigo = f"{prefix_part}{next_num:03d}"
                            next_num += 1
                        
                        categoria = limpiar_texto(row.get("categoria"))
                        stock = float(limpiar_numero(row.get("stock")) or 0)
                        costo = float(limpiar_numero(row.get("costo")) or 0)
                        precio_venta = float(limpiar_numero(row.get("precio_venta")) or 0)
                        precio_especial = float(limpiar_numero(row.get("precio_especial")) or 0)
                        activo = bool(row.get("activo", True))
                        
                        # Columnas tributarias
                        itbis_gravado = bool(row.get("itbis_gravado", True)) if "itbis_gravado" in df_preview.columns else True
                        itbis_tasa = float(limpiar_numero(row.get("itbis_tasa")) or 18.0) if "itbis_tasa" in df_preview.columns else 18.0
                        itbis_incluido = bool(row.get("itbis_incluido", True)) if "itbis_incluido" in df_preview.columns else True

                        existente = get_producto_por_codigo(codigo) if codigo else None
                        if existente is None:
                            existente = get_producto_por_nombre(nombre)

                        ok = False

                        if existente is not None:
                            # ── ACTUALIZAR producto ya existente ──
                            actual = obtener_existencia_producto(existente)
                            nueva_cant = actual
                            if modo_carga == "Actualizar costo/precio y sumar cantidad":
                                nueva_cant = actual + stock
                            elif modo_carga == "Actualizar costo/precio y reemplazar cantidad":
                                nueva_cant = stock

                            payload_upd = {
                                "fecha": str(date.today()),
                                "codigo": codigo or existente.get("codigo"),
                                "codigo_barra": codigo or existente.get("codigo_barra") or existente.get("codigo"),
                                "nombre": nombre,
                                "categoria": categoria,
                                "costo": costo,
                                "costo_unitario": costo,
                                "costo_promedio": costo,
                                "precio": precio_venta,
                                "precio_venta": precio_venta,
                                "precio_especial": precio_especial,
                                "activo": activo,
                                "itbis_gravado": itbis_gravado,
                                "itbis_tasa": itbis_tasa,
                                "itbis_incluido": itbis_incluido,
                                "usar_en_inventario": True,
                                "updated_at": ahora_str(),
                            }

                            if modo_carga != "Solo actualizar datos sin mover cantidad":
                                payload_upd["cantidad"] = float(nueva_cant)
                                payload_upd["stock"] = float(nueva_cant)
                                payload_upd["existencia"] = float(nueva_cant)

                            try:
                                ok = actualizar("productos", existente["id"], payload_upd)
                                if not ok:
                                    raise Exception("La actualización no fue confirmada por la base de datos.")
                            except Exception as exc_upd:
                                filas_con_error.append(f"Fila {i+1} ('{nombre}'): Error al actualizar — {exc_upd}")
                                errores += 1
                                continue

                        else:
                            # ── INSERTAR producto nuevo ──
                            payload_ins = {
                                "fecha": str(date.today()),
                                "codigo": codigo,
                                "codigo_barra": codigo,
                                "nombre": nombre,
                                "categoria": categoria,
                                "costo": costo,
                                "costo_unitario": costo,
                                "costo_promedio": costo,
                                "precio": precio_venta,
                                "precio_venta": precio_venta,
                                "precio_especial": precio_especial,
                                "cantidad": stock,
                                "stock": stock,
                                "existencia": stock,
                                "activo": activo,
                                "itbis_gravado": itbis_gravado,
                                "itbis_tasa": itbis_tasa,
                                "itbis_incluido": itbis_incluido,
                                "usar_en_inventario": True,
                                "fecha_agregado": ahora_str(),
                                "created_at": ahora_str(),
                                "updated_at": ahora_str(),
                            }
                            try:
                                ok = insertar("productos", payload_ins)
                                if not ok:
                                    raise Exception("El sistema rechazó la inserción (código o nombre duplicado, o error de base de datos).")
                                # Recargar cache para que las próximas filas vean este producto
                                invalidar_cache_tabla("productos")
                            except Exception as exc_ins:
                                filas_con_error.append(f"Fila {i+1} ('{nombre}', código '{codigo}'): Error al crear — {exc_ins}")
                                errores += 1
                                continue

                        # ── Sincronizar inventario actual (no bloquea el conteo del producto) ──
                        try:
                            upsert_inventario_actual(
                                nombre, costo, precio_venta,
                                stock if modo_carga != "Solo actualizar datos sin mover cantidad" else obtener_existencia_producto(get_producto_por_nombre(nombre) or pd.Series()),
                                date.today(), "Sincronizado desde carga de productos"
                            )
                        except Exception:
                            pass  # El fallo de inventario actual no impide que el producto cuente como procesado

                        procesados += 1

                    except Exception as e:
                        errores += 1
                        filas_con_error.append(f"Fila {i+1} ('{nombre or 'SIN NOMBRE'}'): Error inesperado — {e}")

                    if len(df_preview) > 0:
                        barra.progress(min((i + 1) / len(df_preview), 1.0))
                        estado.caption(f"Procesando {i + 1} de {len(df_preview)}... ✅ OK: {procesados} | ❌ Errores: {errores}")

                limpiar_cache_datos()

                if procesados > 0:
                    st.success(f"✅ Productos cargados/actualizados correctamente: **{procesados}** de {procesados + errores} filas válidas.")
                if errores > 0:
                    st.error(f"❌ **{errores} productos no se pudieron cargar.** Revisa el detalle abajo.")
                    with st.expander(f"📋 Ver detalle de los {errores} errores", expanded=True):
                        for detalle in filas_con_error:
                            st.warning(detalle)
                st.rerun()

    # ----------------------------------------------------
    # PERSONALIZACIÓN DE ATRIBUTOS POR RUBRO (MARCA BLANCA)
    # ----------------------------------------------------
    st.subheader("🎨 Marca y Atributos Específicos (Multirubro)")
    with st.expander("✨ Abrir Panel de Atributos (Ropa, Minimarket, Ferretería, etc.)", expanded=False):
        st.write("Configura marca, modelo, pasillo, estantería o variantes específicas para adaptar la plataforma a cualquier rubro comercial.")
        st.caption("Los atributos cargados enriquecerán la descripción y se integrarán de forma inteligente en el POS y catálogo.")
        
        productos_master_attr = DATA["productos"].copy()
        if not productos_master_attr.empty:
            prod_seleccionable = sorted(productos_master_attr["nombre"].dropna().unique().tolist())
            prod_attr_sel = st.selectbox("Seleccione el Producto a Personalizar", prod_seleccionable, key="prod_attr_sel_master")
            
            fila_prod_attr = productos_master_attr[productos_master_attr["nombre"] == prod_attr_sel].iloc[0]
            attrs_actuales = obtener_atributos_producto(fila_prod_attr.to_dict() if hasattr(fila_prod_attr, "to_dict") else dict(fila_prod_attr))
            
            rubro_preset = st.selectbox("Rubro Comercial / Preset de Atributos", ["Estándar", "Ropa / Boutique", "Ferretería / Repuestos", "Minimarket / Alimentos"], key="rubro_preset_sel")
            
            marca_val = ""
            modelo_val = ""
            talla_val = ""
            color_val = ""
            estante_val = ""
            pasillo_val = ""
            unidad_val = ""
            
            if attrs_actuales:
                st.info("✅ Este producto ya cuenta con atributos específicos configurados.")
                st.write("**Atributos Actuales:**")
                for k, v in attrs_actuales.items():
                    if v:
                        st.write(f"- **{k.capitalize()}:** {v}")
                
                # Pre-populate values
                marca_val = attrs_actuales.get("marca", "")
                modelo_val = attrs_actuales.get("modelo", "")
                talla_val = attrs_actuales.get("talla", "")
                color_val = attrs_actuales.get("color", "")
                estante_val = attrs_actuales.get("estanteria", "")
                pasillo_val = attrs_actuales.get("pasillo", "")
                unidad_val = attrs_actuales.get("unidad_medida", "")

            st.markdown("---")
            st.write(f"**Ingresar Nuevos Datos ({rubro_preset}):**")
            
            cols_attr = st.columns(2)
            payload_attrs = {}
            
            if rubro_preset == "Ropa / Boutique":
                with cols_attr[0]:
                    payload_attrs["marca"] = st.text_input("Marca", value=marca_val, key="attr_ropa_marca")
                    payload_attrs["talla"] = st.text_input("Talla (e.g. S, M, L, 32)", value=talla_val, key="attr_ropa_talla")
                with cols_attr[1]:
                    payload_attrs["color"] = st.text_input("Color", value=color_val, key="attr_ropa_color")
                    payload_attrs["modelo"] = st.text_input("Modelo / Colección", value=modelo_val, key="attr_ropa_modelo")
                    
            elif rubro_preset == "Ferretería / Repuestos":
                with cols_attr[0]:
                    payload_attrs["marca"] = st.text_input("Marca / Fabricante", value=marca_val, key="attr_ferr_marca")
                    payload_attrs["pasillo"] = st.text_input("Pasillo", value=pasillo_val, key="attr_ferr_pasillo")
                with cols_attr[1]:
                    payload_attrs["estanteria"] = st.text_input("Estantería / Compartimento", value=estante_val, key="attr_ferr_estante")
                    payload_attrs["modelo"] = st.text_input("Número de Parte / Modelo", value=modelo_val, key="attr_ferr_modelo")
                    
            elif rubro_preset == "Minimarket / Alimentos":
                with cols_attr[0]:
                    payload_attrs["marca"] = st.text_input("Marca / Marca Distribuidora", value=marca_val, key="attr_mini_marca")
                    payload_attrs["unidad_medida"] = st.text_input("Unidad de Medida (e.g. Lb, Kg, Litros)", value=unidad_val, key="attr_mini_unidad")
                with cols_attr[1]:
                    payload_attrs["modelo"] = st.text_input("Tipo / Categoría Específica", value=modelo_val, key="attr_mini_modelo")
            
            else:
                with cols_attr[0]:
                    payload_attrs["marca"] = st.text_input("Marca", value=marca_val, key="attr_std_marca")
                with cols_attr[1]:
                    payload_attrs["modelo"] = st.text_input("Modelo", value=modelo_val, key="attr_std_modelo")
            
            st.write("")
            if st.button("💾 Guardar Atributos del Producto", key="btn_save_prod_attributes", use_container_width=True):
                import json
                payload_json = "ATRIBUTOS: " + json.dumps(payload_attrs)
                
                if actualizar("productos", fila_prod_attr["id"], {"observacion": payload_json}):
                    st.success(f"¡Atributos del producto '{prod_attr_sel}' guardados con éxito!")
                    limpiar_cache_datos()
                    st.rerun()

    # ----------------------------------------------------
    # CONFIGURAR RECETAS DE COMBOS (KITS)
    # ----------------------------------------------------
    st.subheader("🍻 Configurar Receta de Combo (Kits de Venta)")
    with st.expander("✨ Abrir Panel de Creación / Edición de Combos", expanded=False):
        st.write("Crea o edita la receta de un combo. El producto del combo debe estar previamente creado en el catálogo.")
        st.caption("Al vender este combo, el sistema descontará automáticamente el stock de cada ingrediente individual en lugar del combo.")
        
        productos_master = DATA["productos"].copy()
        if not productos_master.empty:
            combo_productos = sorted(productos_master["nombre"].dropna().unique().tolist())
            
            combo_sel = st.selectbox("Seleccione el Producto Combo", combo_productos, key="combo_master_sel")
            
            # Mostrar receta actual si existe
            fila_combo = productos_master[productos_master["nombre"] == combo_sel].iloc[0]
            receta_actual = obtener_receta_combo(fila_combo.to_dict() if hasattr(fila_combo, "to_dict") else dict(fila_combo))
            
            if receta_actual:
                st.info("✅ Este producto ya está configurado como un Combo.")
                st.write("**Ingredientes actuales:**")
                for ing in receta_actual.get("items", []):
                    st.write(f"- {ing.get('nombre')}: {ing.get('cantidad')} unidades")
            else:
                st.warning("Este producto no tiene una receta configurada (se vende de forma individual).")
                
            st.markdown("---")
            st.write("**Definir / Actualizar Ingredientes:**")
            
            # Select multiple ingredients
            ingredientes_opciones = sorted(productos_master[productos_master["nombre"] != combo_sel]["nombre"].dropna().unique().tolist())
            ingredientes_sel = st.multiselect("Seleccione los Ingredientes del Combo", ingredientes_opciones, key="combo_ingredientes_sel")
            
            items_receta = []
            if ingredientes_sel:
                st.write("Defina las cantidades por cada ingrediente:")
                cols_ing = st.columns(len(ingredientes_sel))
                for idx_ing, ing_nombre in enumerate(ingredientes_sel):
                    with cols_ing[idx_ing]:
                        fila_ing = productos_master[productos_master["nombre"] == ing_nombre].iloc[0]
                        cant_ing = st.number_input(f"{ing_nombre} (cant)", min_value=0.1, step=1.0, value=1.0, key=f"combo_ing_cant_{idx_ing}")
                        items_receta.append({
                            "producto_id": str(fila_ing["id"]),
                            "nombre": ing_nombre,
                            "cantidad": cant_ing
                        })
            
            if st.button("💾 Guardar Receta de Combo", key="btn_save_combo_recipe"):
                if not items_receta:
                    st.error("Debe seleccionar al menos un ingrediente.")
                else:
                    import json
                    payload_receta = {
                        "es_combo": True,
                        "items": items_receta
                    }
                    receta_json = "RECETA_COMBO: " + json.dumps(payload_receta)
                    
                    # Update observacion of the combo product in the database
                    if actualizar("productos", fila_combo["id"], {"observacion": receta_json}):
                        st.success(f"¡Receta de combo '{combo_sel}' guardada con éxito!")
                        limpiar_cache_datos()
                        st.rerun()

    st.subheader("📋 Listado")
    df = DATA["productos"].copy()
    if not df.empty:
        txt = st.text_input("Buscar producto por nombre o código", key="buscar_prod")
        solo_activos = st.checkbox("Solo activos", value=True, key="solo_activos_prod")
        if solo_activos and "activo" in df.columns:
            df = df[df["activo"] == True]
        if txt:
            mask = df.astype(str).apply(lambda col: col.str.contains(txt, case=False, na=False)).any(axis=1)
            df = df[mask]
        st.dataframe(df, use_container_width=True)
        
        # Módulo de Eliminación Múltiple de Productos
        with st.expander("🗑️ Eliminación Múltiple de Productos", expanded=False):
            st.write("Selecciona las casillas de los productos que deseas eliminar y haz clic en **Eliminar seleccionados**:")
            df_del_sel = df.copy()
            df_edit_cols = ["Código" if "Código" in df_del_sel.columns else "codigo", "nombre", "categoria", "precio"]
            df_edit_cols = [c for c in df_edit_cols if c in df_del_sel.columns]
            
            # We need ID column to perform deletion but we want to hide it
            has_id = "id" in df_del_sel.columns
            if has_id:
                df_edit = df_del_sel[["id"] + df_edit_cols].copy()
            else:
                df_edit = df_del_sel[df_edit_cols].copy()
                
            df_edit.insert(0, "Seleccionar", False)
            
            edited_df = st.data_editor(
                df_edit,
                column_config={
                    "Seleccionar": st.column_config.CheckboxColumn(
                        "🗑️",
                        help="Selecciona para eliminar",
                        default=False,
                    ),
                    "id": None, # Hide ID
                },
                disabled=df_edit_cols + (["id"] if has_id else []),
                use_container_width=True,
                key="prod_bulk_del_editor"
            )
            
            selected_rows = edited_df[edited_df["Seleccionar"] == True]
            if not selected_rows.empty:
                st.warning(f"⚠️ Has seleccionado **{len(selected_rows)}** productos para eliminar.")
                confirm_del = st.checkbox("Confirmar que deseo eliminar permanentemente estos productos", key="confirm_bulk_del_check")
                if confirm_del:
                    if st.button("🗑️ Eliminar seleccionados", key="btn_bulk_delete_confirm", type="primary"):
                        exitos = 0
                        errores = 0
                        for _, row in selected_rows.iterrows():
                            # Find ID in original df or row
                            pid = row.get("id")
                            if not pid and "id" in df_del_sel.columns:
                                # Fallback by index or matching columns
                                pass
                            if pid and eliminar("productos", pid):
                                exitos += 1
                            else:
                                errores += 1
                        if exitos > 0:
                            st.success(f"Se eliminaron {exitos} productos.")
                        if errores > 0:
                            st.error(f"No se pudieron eliminar {errores} productos.")
                        limpiar_cache_datos()
                        st.rerun()
            else:
                st.info("No has seleccionado ningún producto para eliminar.")
                
        descargar_archivos(df, "productos")
        
        # Formulario para registrar producto manualmente con campos de ITBIS
        with st.expander("➕ Registrar Producto Manualmente", expanded=False):
            col_pm1, col_pm2 = st.columns(2)
            with col_pm1:
                pm_nombre = st.text_input("Nombre del producto*", key="pm_nombre")
                pm_codigo = st.text_input("Código (Opcional, se autogenera)", key="pm_codigo")
                pm_categoria = st.text_input("Categoría", key="pm_categoria")
                pm_costo = st.number_input("Costo unitario (RD$)", min_value=0.0, step=1.0, key="pm_costo")
                pm_precio = st.number_input("Precio de venta (RD$)", min_value=0.0, step=1.0, key="pm_precio")
            with col_pm2:
                pm_stock = st.number_input("Cantidad inicial en stock", min_value=0.0, step=1.0, key="pm_stock")
                pm_itbis_gravado = st.checkbox("¿Está gravado con ITBIS?", value=True, key="pm_itbis_gravado")
                pm_itbis_tasa = st.selectbox("Tasa de ITBIS", [18.0, 16.0, 0.0], index=0, key="pm_itbis_tasa")
                pm_itbis_incluido = st.checkbox("¿El precio YA incluye ITBIS?", value=True, key="pm_itbis_incluido")
                pm_activo = st.checkbox("Producto activo", value=True, key="pm_activo")
            
            if st.button("💾 Registrar Producto", key="btn_save_prod_manual"):
                if not pm_nombre.strip():
                    st.error("El nombre del producto es obligatorio.")
                else:
                    try:
                        p_code = pm_codigo.strip() if pm_codigo.strip() else generar_codigo_producto()
                        payload = {
                            "fecha": str(date.today()),
                            "codigo": p_code,
                            "codigo_barra": p_code,
                            "nombre": pm_nombre.strip(),
                            "categoria": pm_categoria.strip(),
                            "costo": float(pm_costo),
                            "costo_unitario": float(pm_costo),
                            "costo_promedio": float(pm_costo),
                            "precio": float(pm_precio),
                            "precio_venta": float(pm_precio),
                            "cantidad": float(pm_stock),
                            "stock": float(pm_stock),
                            "existencia": float(pm_stock),
                            "activo": pm_activo,
                            "itbis_gravado": pm_itbis_gravado,
                            "itbis_tasa": float(pm_itbis_tasa),
                            "itbis_incluido": pm_itbis_incluido,
                            "usar_en_inventario": True,
                            "created_at": ahora_str(),
                            "updated_at": ahora_str()
                        }
                        if insertar("productos", payload):
                            st.success(f"✅ Producto '{pm_nombre}' registrado con éxito con el código '{p_code}'.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar producto: {e}")

        render_crud_generico("productos", df, "🛠️ Editar / eliminar productos")
    else:
        st.info("No hay productos registrados.")

# =========================================================
# INVENTARIO ACTUAL
# =========================================================


def render_inventario_actual():
    st.title("📊 Inventario Actual")

    tab_existencia, tab_alertas, tab_excel = st.tabs([
        "📋 Existencias en Tiempo Real", 
        "🚨 Alertas de Reposición y Demanda", 
        "📥 Subir Excel / CSV de inventario actual"
    ])

    with tab_excel:
        st.write("Columnas esperadas: nombre o producto, cantidad o existencia_sistema. Costo y precio opcionales.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv", "txt"], key="up_inventario")
        fecha_inv = st.date_input("Fecha del inventario", value=date.today(), key="fecha_inv_actual")

        if archivo is not None and st.button("Cargar inventario actual"):
            df = preparar_import_productos(leer_archivo_subido(archivo))
            st.caption("Vista previa de columnas detectadas automáticamente")
            st.dataframe(df.head(10), use_container_width=True)
            df = df.rename(columns={"nombre": "producto", "stock": "existencia_sistema", "cantidad": "existencia_sistema", "precio_venta": "precio"})
            faltan = [c for c in ["producto", "existencia_sistema"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                procesados = 0
                for _, row in df.iterrows():
                    producto = limpiar_texto(row["producto"])
                    if not producto:
                        continue
                    existencia = limpiar_numero(row["existencia_sistema"]) or 0
                    fila_prod = get_producto_por_nombre(producto)

                    if fila_prod is not None:
                        costo = limpiar_numero(row["costo"]) if "costo" in df.columns else limpiar_numero(fila_prod.get("costo")) or 0
                        precio = limpiar_numero(row["precio"]) if "precio" in df.columns else limpiar_numero(row.get("precio_venta")) or limpiar_numero(fila_prod.get("precio")) or 0
                        actualizar(
                            "productos",
                            fila_prod["id"],
                            {
                                "fecha": str(fecha_inv),
                                "cantidad": float(existencia),
                                "costo": float(costo),
                                "precio": float(precio),
                            },
                        )
                        upsert_inventario_actual(producto, costo, precio, existencia, fecha_inv, "Carga inventario actual")
                    else:
                        costo = limpiar_numero(row["costo"]) if "costo" in df.columns else 0
                        precio = limpiar_numero(row["precio"]) if "precio" in df.columns else limpiar_numero(row.get("precio_venta")) or 0
                        insertar(
                            "productos",
                            {
                                "fecha": str(fecha_inv),
                                "nombre": producto,
                                "costo": float(costo),
                                "precio": float(precio),
                                "cantidad": float(existencia),
                            },
                        )
                        upsert_inventario_actual(producto, costo, precio, existencia, fecha_inv, "Creado desde inventario actual")
                    procesados += 1
                st.success(f"Inventario actualizado: {procesados} productos.")
                st.rerun()

    with tab_existencia:
        prods = DATA["productos"].copy()
        if not prods.empty:
            if "usar_en_inventario" in prods.columns:
                prods = prods[prods["usar_en_inventario"] == True]
                
            prods_display = pd.DataFrame()
            prods_display["Código"] = prods["Código"] if "Código" in prods.columns else prods.get("codigo", "")
            prods_display["Producto"] = prods["nombre"]
            
            existencia_col = "stock" if "stock" in prods.columns else "existencia" if "existencia" in prods.columns else "cantidad"
            prods_display["Existencia Actual"] = prods[existencia_col].fillna(0.0).astype(float)
            prods_display["Costo Unitario"] = prods["costo"].fillna(0.0).astype(float)
            prods_display["Precio Venta"] = prods["precio"].fillna(0.0).astype(float)
            prods_display["Valor Inventario"] = prods_display["Existencia Actual"] * prods_display["Costo Unitario"]
            
            prods_display = prods_display.sort_values("Producto")
            
            txt_search = st.text_input("Buscar producto en inventario", key="buscar_inv_actual_realtime")
            if txt_search:
                mask = prods_display.astype(str).apply(lambda col: col.str.contains(txt_search, case=False, na=False)).any(axis=1)
                prods_display = prods_display[mask]
                
            st.subheader("📋 Existencias en Tiempo Real (Fotografía Actual)")
            st.dataframe(prods_display, use_container_width=True)
            
            total_valor_inv = prods_display["Valor Inventario"].sum()
            st.metric("💰 Valor Total del Inventario (Costo)", f"RD$ {total_valor_inv:,.2f}")
            
            descargar_archivos(prods_display, "inventario_actual_realtime")
        else:
            st.info("No hay productos registrados en el catálogo de inventario.")

    with tab_alertas:
        import math
        st.subheader("🚨 Alertas de Reposición y Mayor Demanda (Flujo)")
        st.caption("Analiza la velocidad de venta de tus productos para recomendarte qué comprar y en qué cantidad.")
        
        # Inputs para el análisis
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            dias_analisis = st.selectbox(
                "Rango de análisis de ventas",
                [7, 15, 30, 60, 90],
                index=2,
                format_func=lambda x: f"Últimos {x} días",
                key="alertas_dias_analisis"
            )
        with col_c2:
            dias_cobertura = st.number_input(
                "Días de stock deseados a cubrir",
                min_value=1,
                max_value=365,
                value=15,
                step=1,
                help="¿Para cuántos días quieres tener inventario al comprar?",
                key="alertas_dias_cobertura"
            )
        with col_c3:
            umbral_alerta = st.number_input(
                "Umbral de alerta (días restantes)",
                min_value=1,
                max_value=90,
                value=7,
                step=1,
                help="Te alertará si el inventario actual dura menos de estos días.",
                key="alertas_umbral_alerta"
            )
            
        # Calcular fechas del análisis
        fecha_fin = date.today()
        fecha_ini = fecha_fin - timedelta(days=dias_analisis)
        
        # Cargar datos
        ventas_df = _df_actual("ventas")
        detalles_df = _df_actual("detalle_venta")
        productos_df = _df_actual("productos")
        
        if not ventas_df.empty and not detalles_df.empty and not productos_df.empty:
            # Filtrar ventas del período
            v_col = _fecha_col(ventas_df) or "fecha"
            ventas_df["_fecha_dt"] = pd.to_datetime(ventas_df[v_col], errors="coerce").dt.date
            ventas_periodo = ventas_df[(ventas_df["_fecha_dt"] >= fecha_ini) & (ventas_df["_fecha_dt"] <= fecha_fin)]
            
            # Quitar ventas anuladas si aplica
            for col_anulado in ["anulado", "cancelado"]:
                if col_anulado in ventas_periodo.columns:
                    try:
                        ventas_periodo = ventas_periodo[~ventas_periodo[col_anulado].fillna(False).astype(bool)]
                    except Exception:
                        pass
                        
            if not ventas_periodo.empty:
                # Obtener IDs de ventas válidas
                venta_ids = set()
                for c in ["id", "identificación", "identificacion", "venta_id"]:
                    if c in ventas_periodo.columns:
                        venta_ids.update(ventas_periodo[c].dropna().astype(str).tolist())
                        
                # Filtrar detalles de ventas correspondientes a esas ventas
                detalles_periodo = detalles_df[detalles_df["venta_id"].astype(str).isin(venta_ids)].copy() if venta_ids else pd.DataFrame()
                
                # Quitar detalles anulados si aplica
                for col_anulado in ["anulado", "cancelado"]:
                    if col_anulado in detalles_periodo.columns:
                        try:
                            detalles_periodo = detalles_periodo[~detalles_periodo[col_anulado].fillna(False).astype(bool)]
                        except Exception:
                            pass
                
                if not detalles_periodo.empty:
                    # Agrupar por producto para calcular volumen de ventas
                    detalles_periodo["cantidad"] = pd.to_numeric(detalles_periodo["cantidad"], errors="coerce").fillna(0.0)
                    
                    prod_sales = detalles_periodo.groupby("producto")["cantidad"].sum().reset_index()
                    prod_sales = prod_sales.rename(columns={"cantidad": "cantidad_vendida"})
                    
                    # Calcular velocidad diaria (flujo)
                    prod_sales["flujo_diario"] = prod_sales["cantidad_vendida"] / dias_analisis
                    
                    # Cruzar con tabla de productos para obtener stock actual y costo
                    prod_catalogo = productos_df.copy()
                    prod_catalogo["Producto"] = prod_catalogo["nombre"]
                    existencia_col = "stock" if "stock" in prod_catalogo.columns else "existencia" if "existencia" in prod_catalogo.columns else "cantidad"
                    prod_catalogo["Stock Actual"] = pd.to_numeric(prod_catalogo[existencia_col], errors="coerce").fillna(0.0)
                    prod_catalogo["Costo Unitario"] = pd.to_numeric(prod_catalogo["costo"], errors="coerce").fillna(0.0)
                    
                    # Realizar cruce (merge)
                    analisis = pd.merge(prod_sales, prod_catalogo[["Producto", "Stock Actual", "Costo Unitario"]], left_on="producto", right_on="Producto", how="right")
                    analisis["producto"] = analisis["producto"].fillna(analisis["Producto"])
                    analisis["cantidad_vendida"] = analisis["cantidad_vendida"].fillna(0.0)
                    analisis["flujo_diario"] = analisis["flujo_diario"].fillna(0.0)
                    analisis["Stock Actual"] = analisis["Stock Actual"].fillna(0.0)
                    analisis["Costo Unitario"] = analisis["Costo Unitario"].fillna(0.0)
                    
                    # Calcular días restantes de inventario
                    analisis["dias_restantes"] = analisis.apply(
                        lambda r: r["Stock Actual"] / r["flujo_diario"] if r["flujo_diario"] > 0 else 9999.0,
                        axis=1
                    )
                    
                    # Calcular cantidad sugerida a comprar
                    analisis["sugerido_comprar"] = analisis.apply(
                        lambda r: max(0.0, (r["flujo_diario"] * dias_cobertura) - r["Stock Actual"]) if r["flujo_diario"] > 0 else 0.0,
                        axis=1
                    )
                    analisis["sugerido_comprar"] = analisis["sugerido_comprar"].apply(lambda x: float(math.ceil(x)))
                    analisis["costo_reposicion"] = analisis["sugerido_comprar"] * analisis["Costo Unitario"]
                    
                    # Dividir la pantalla en dos columnas
                    col_izq, col_der = st.columns(2)
                    
                    with col_izq:
                        st.subheader("🏆 Productos con Mayor Flujo (Más Vendidos)")
                        st.caption(f"Top 10 productos con mayor volumen de ventas en los últimos {dias_analisis} días.")
                        top_flujo = analisis.sort_values("cantidad_vendida", ascending=False).head(10)
                        
                        top_display = pd.DataFrame()
                        top_display["Producto"] = top_flujo["producto"]
                        top_display["Vendidos"] = top_flujo["cantidad_vendida"]
                        top_display["Venta Diaria Prom."] = top_flujo["flujo_diario"].round(2)
                        top_display["Stock Actual"] = top_flujo["Stock Actual"]
                        
                        st.dataframe(top_display, use_container_width=True, hide_index=True)
                        
                    with col_der:
                        st.subheader("🚨 Alertas de Stock y Reposición")
                        st.caption(f"Productos cuyo stock dura menos de {umbral_alerta} días o que ya se agotaron.")
                        
                        # Alertas son productos con dias_restantes <= umbral_alerta y flujo_diario > 0
                        # O productos que tienen stock = 0 y flujo_diario > 0
                        alertas_df = analisis[
                            (analisis["flujo_diario"] > 0) & 
                            ((analisis["dias_restantes"] <= umbral_alerta) | (analisis["Stock Actual"] <= 0))
                        ].copy()
                        
                        if not alertas_df.empty:
                            alertas_df = alertas_df.sort_values("dias_restantes")
                            
                            alertas_display = pd.DataFrame()
                            alertas_display["Producto"] = alertas_df["producto"]
                            alertas_display["Stock Actual"] = alertas_df["Stock Actual"]
                            alertas_display["Venta Diaria"] = alertas_df["flujo_diario"].round(2)
                            
                            def _format_dias(d):
                                if d == 9999.0: return "Sin ventas"
                                if d <= 0: return "❌ Agotado"
                                return f"⚠️ {d:.1f} días"
                                
                            alertas_display["Duración Stock"] = alertas_df["dias_restantes"].apply(_format_dias)
                            alertas_display["Sugerido Comprar"] = alertas_df["sugerido_comprar"].astype(int)
                            alertas_display["Costo Reposición (RD$)"] = alertas_df["costo_reposicion"].round(2)
                            
                            st.dataframe(alertas_display, use_container_width=True, hide_index=True)
                            
                            total_costo_rep = alertas_display["Costo Reposición (RD$)"].sum()
                            st.info(f"💰 **Presupuesto estimado de reposición:** RD$ {total_costo_rep:,.2f}")
                            
                            # Botón de descargar sugeridos
                            descargar_archivos(alertas_display, "sugerencias_compra")
                        else:
                            st.success("✅ ¡Todo en orden! No hay productos con alertas de stock bajo según la velocidad de venta actual.")
                else:
                    st.info("No se encontraron detalles de productos vendidos en este período de análisis.")
            else:
                st.info("No se registraron ventas en este período de análisis.")
        else:
            st.info("Cargando catálogo e historial para generar las alertas...")


# =========================================================
# HISTORIAL DE INVENTARIO
# =========================================================


def render_historial_inventario():
    st.title("📜 Historial de Inventario")
    st.caption("Consulta el registro histórico detallado de movimientos de inventario: Compras, Ventas, Pérdidas, Ajustes y Conteos.")

    df_hist = obtener_historial_inventario_completo()
    
    if not df_hist.empty:
        # Renombrar para compatibilidad con filtros
        df_hist = df_hist.rename(columns={"Fecha": "fecha"})
        
        # Filtros de fecha
        d1, d2 = rango_fechas_ui("historial_inventario")
        df_hist = filtrar_por_fechas(df_hist, d1, d2)
        
        # Filtro de tipo de movimiento
        tipos_disponibles = ["Todos"] + sorted(df_hist["Movimiento"].unique().tolist()) if "Movimiento" in df_hist.columns else ["Todos"]
        tipo_sel = st.selectbox("Filtrar por tipo de movimiento", tipos_disponibles, key="filtro_hist_tipo")
        if tipo_sel != "Todos":
            df_hist = df_hist[df_hist["Movimiento"] == tipo_sel]
            
        # Filtro de texto
        txt_search = st.text_input("Buscar por producto, observación o usuario", key="buscar_hist_inv")
        if txt_search:
            df_hist = buscar_df(df_hist, txt_search)
            
        if not df_hist.empty:
            # Mostrar tabla con formato amigable
            df_display = df_hist.copy()
            df_display["fecha"] = df_display["fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")
            df_display = df_display.rename(columns={"fecha": "Fecha"})
            
            st.dataframe(df_display, use_container_width=True)
            
            # Botones de descarga de archivos
            descargar_archivos(df_hist.rename(columns={"fecha": "Fecha"}), "historial_inventario")
        else:
            st.info("No hay movimientos que coincidan con los filtros seleccionados.")
    else:
        st.info("No se han registrado movimientos de inventario en el sistema.")


# =========================================================
# CONTEO INVENTARIO
# =========================================================


def render_conteo_inventario():
    st.title("🧮 Conteo de Inventario")

    productos_df = DATA["productos"].copy()
    productos_lista = productos_df["nombre"].astype(str).tolist() if not productos_df.empty and "nombre" in productos_df.columns else []

    # =====================================================
    # CONTEO MANUAL
    # =====================================================
    with st.expander("✍️ Conteo manual", expanded=True):
        if not productos_lista:
            st.info("No hay productos para contar.")
        else:
            c1, c2, c3 = st.columns(3)

            with c1:
                fecha_manual = st.date_input("Fecha", value=date.today(), key="conteo_manual_fecha")
                producto_manual = st.selectbox("Producto", productos_lista, key="conteo_manual_producto")

            fila_prod_manual = get_producto_por_nombre(producto_manual) if producto_manual else None
            existencia_sistema_manual = obtener_existencia_producto(fila_prod_manual) if fila_prod_manual is not None else 0.0

            with c2:
                st.number_input(
                    "Existencia sistema",
                    min_value=0.0,
                    step=1.0,
                    value=float(existencia_sistema_manual),
                    disabled=True,
                    key=f"conteo_manual_existencia_sistema_{producto_manual}",
                )
                existencia_fisica_manual = st.number_input(
                    "Existencia física real",
                    min_value=0.0,
                    step=1.0,
                    value=0.0,
                    key=f"conteo_manual_existencia_fisica_{producto_manual}",
                )

            diferencia_manual = float(existencia_fisica_manual) - float(existencia_sistema_manual)
            if diferencia_manual == 0:
                estado_manual = "Cuadrado"
            elif diferencia_manual < 0:
                estado_manual = "Faltante"
            else:
                estado_manual = "Sobrante"

            with c3:
                st.metric("Diferencia", f"{diferencia_manual:+.2f}")
                st.text_input("Estado", value=estado_manual, disabled=True, key=f"conteo_manual_estado_{producto_manual}")
                observacion_manual = st.text_area("Observación", key=f"conteo_manual_obs_{producto_manual}")

            if st.button("Guardar conteo manual", key="btn_guardar_conteo_manual"):
                ok = insertar(
                    "conteo_inventario",
                    {
                        "fecha": str(fecha_manual),
                        "producto": producto_manual,
                        "existencia_sistema": float(existencia_sistema_manual),
                        "existencia_fisica": float(existencia_fisica_manual),
                        "diferencia": float(diferencia_manual),
                        "estado": estado_manual.lower(),
                        "observacion": observacion_manual,
                    },
                )
                if ok:
                    st.success("Conteo manual guardado.")
                    st.rerun()

    # =====================================================
    # CARGA MASIVA POR EXCEL / CSV
    # =====================================================
    with st.expander("📥 Subir conteo físico por Excel / CSV", expanded=False):
        st.write("Columnas esperadas: producto o nombre, existencia_fisica o cantidad.")
        archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_conteo")
        fecha_conteo = st.date_input("Fecha del conteo", value=date.today(), key="fecha_conteo")

        if archivo is not None and st.button("Procesar conteo"):
            df = leer_archivo_subido(archivo)
            df = df.rename(columns={"nombre": "producto", "cantidad": "existencia_fisica"})
            faltan = [c for c in ["producto", "existencia_fisica"] if c not in df.columns]
            if faltan:
                st.error(f"Faltan columnas: {faltan}")
            else:
                procesados = 0
                for _, row in df.iterrows():
                    producto = limpiar_texto(row["producto"])
                    if not producto:
                        continue
                    fila_prod = get_producto_por_nombre(producto)
                    existencia_sistema = obtener_existencia_producto(fila_prod) if fila_prod is not None else 0.0
                    existencia_fisica = float(limpiar_numero(row["existencia_fisica"]) or 0)
                    diferencia = existencia_fisica - existencia_sistema

                    if diferencia == 0:
                        estado = "cuadrado"
                    elif diferencia < 0:
                        estado = "faltante"
                    else:
                        estado = "sobrante"

                    insertar(
                        "conteo_inventario",
                        {
                            "fecha": str(fecha_conteo),
                            "producto": producto,
                            "existencia_sistema": float(existencia_sistema),
                            "existencia_fisica": float(existencia_fisica),
                            "diferencia": float(diferencia),
                            "estado": estado,
                            "observacion": "",
                        },
                    )
                    procesados += 1
                st.success(f"Se procesaron {procesados} filas de conteo.")
                st.rerun()

    # =====================================================
    # LISTADO + ACCIONES
    # =====================================================
    conteo = DATA["conteo_inventario"].copy()
    if not conteo.empty:
        st.subheader("📋 Conteos guardados")
        d1, d2 = rango_fechas_ui("conteo_inv")
        conteo_f = filtrar_por_fechas(conteo, d1, d2)
        estado_filtro = st.selectbox(
            "Filtrar por estado",
            ["Todos", "cuadrado", "faltante", "sobrante"],
            key="filtro_estado_conteo",
        )
        if estado_filtro != "Todos" and "estado" in conteo_f.columns:
            conteo_f = conteo_f[conteo_f["estado"].astype(str).str.lower() == estado_filtro]

        st.dataframe(conteo_f, use_container_width=True)
        descargar_archivos(conteo_f, "conteo_inventario")

        st.subheader("⚙️ Procesar faltantes y sobrantes")
        pendientes = (
            conteo_f[conteo_f["estado"].astype(str).str.lower().isin(["faltante", "sobrante"])]
            if not conteo_f.empty else pd.DataFrame()
        )

        if not pendientes.empty:
            opciones = pendientes.apply(
                lambda r: f"{r['producto']} | sistema: {r['existencia_sistema']} | físico: {r['existencia_fisica']} | estado: {r['estado']}",
                axis=1,
            ).tolist()
            sel = st.selectbox("Selecciona una fila", opciones, key="conteo_sel")
            fila = pendientes.iloc[opciones.index(sel)]

            producto = fila["producto"]
            existencia_sistema = float(fila["existencia_sistema"])
            existencia_fisica = float(fila["existencia_fisica"])
            diferencia = float(fila["diferencia"])
            fecha_mov = pd.to_datetime(fila["fecha"]).date()

            fila_prod = get_producto_por_nombre(producto)
            costo = float(limpiar_numero(fila_prod.get("costo")) or 0) if fila_prod is not None else 0.0
            precio = float(limpiar_numero(fila_prod.get("precio")) or 0) if fila_prod is not None else 0.0

            col1, col2, col3 = st.columns(3)

            with col1:
                if diferencia < 0 and st.button("Enviar este faltante a pérdidas", key="btn_faltante_individual"):
                    cant_perdida = abs(diferencia)
                    ok1 = registrar_perdida(
                        fecha_mov,
                        producto,
                        cant_perdida,
                        costo,
                        "mercancia",
                        f"Generado desde conteo. Sistema: {existencia_sistema}, físico: {existencia_fisica}",
                        estado="debitada",
                    )
                    ok2 = actualizar_stock_producto(producto, existencia_fisica, fecha_mov)
                    ok3 = upsert_inventario_actual(producto, costo, precio, existencia_fisica, fecha_mov, "Ajustado por conteo a pérdida")
                    if ok1 and ok2 and ok3:
                        st.success("Faltante enviado a pérdidas y stock ajustado.")
                        st.rerun()

            with col2:
                if diferencia > 0 and st.button("Aplicar ajuste positivo", key="btn_ajuste_positivo_individual"):
                    ok2 = actualizar_stock_producto(producto, existencia_fisica, fecha_mov)
                    ok3 = upsert_inventario_actual(producto, costo, precio, existencia_fisica, fecha_mov, "Ajuste positivo por conteo")
                    if ok2 and ok3:
                        st.success("Ajuste positivo aplicado.")
                        st.rerun()

            with col3:
                if st.button("Marcar pendiente / dejar como está", key="btn_pendiente_individual"):
                    st.info("No se hizo cambio en inventario. Queda el registro para revisión.")

            faltantes_df = pendientes[pendientes["estado"].astype(str).str.lower() == "faltante"]
            if not faltantes_df.empty and st.button("Enviar TODOS los faltantes del filtro a pérdidas", key="btn_faltantes_masivo"):
                count = 0
                for _, r in faltantes_df.iterrows():
                    prod = r["producto"]
                    fis = float(r["existencia_fisica"])
                    sist = float(r["existencia_sistema"])
                    dif = abs(float(r["diferencia"]))
                    ff = pd.to_datetime(r["fecha"]).date()
                    p = get_producto_por_nombre(prod)
                    c = float(limpiar_numero(p.get("costo")) or 0) if p is not None else 0.0
                    pr = float(limpiar_numero(p.get("precio")) or 0) if p is not None else 0.0
                    registrar_perdida(ff, prod, dif, c, "mercancia", f"Generado masivamente desde conteo. Sistema: {sist}, físico: {fis}", estado="debitada")
                    actualizar_stock_producto(prod, fis, ff)
                    upsert_inventario_actual(prod, c, pr, fis, ff, "Ajustado por envío masivo a pérdidas")
                    count += 1
                st.success(f"Se enviaron {count} faltantes a pérdidas.")
                st.rerun()
        else:
            st.info("No hay faltantes ni sobrantes en el filtro seleccionado.")
    else:
        st.info("No hay conteos registrados.")


# =========================================================
# AJUSTES INVENTARIO
# =========================================================


def render_ajustes_inventario():
    st.title("🔄 Ajustes de Inventario")

    productos_lista = DATA["productos"]["nombre"].astype(str).tolist() if not DATA["productos"].empty and "nombre" in DATA["productos"].columns else []

    with st.expander("➕ Registrar ajuste", expanded=True):
        fecha = st.date_input("Fecha", value=date.today(), key="aj_fecha")
        c1, c2 = st.columns(2)
        with c1:
            producto_origen = st.selectbox("Producto origen (faltante / correcto)", productos_lista, key="aj_origen") if productos_lista else ""
            cantidad = st.number_input("Cantidad", min_value=1.0, step=1.0, key="aj_cantidad")
            tipo_ajuste = st.selectbox("Tipo de ajuste", ["ajuste_cruzado", "ajuste_positivo", "ajuste_negativo"], key="aj_tipo")
        with c2:
            producto_destino = st.selectbox("Producto destino (sobrante / cruzado)", productos_lista, key="aj_destino") if productos_lista else ""
            observacion = st.text_area("Observación", key="aj_obs")

        if st.button("Guardar ajuste"):
            po = get_producto_por_nombre(producto_origen)
            pdst = get_producto_por_nombre(producto_destino)
            if po is None or pdst is None:
                st.error("No se encontraron productos para ajustar.")
            else:
                costo_origen = float(limpiar_numero(po.get("costo")) or 0)
                costo_destino = float(limpiar_numero(pdst.get("costo")) or 0)
                diferencia_costo = abs((costo_origen - costo_destino) * float(cantidad))
                if costo_origen > costo_destino:
                    impacto = "perdida"
                elif costo_origen < costo_destino:
                    impacto = "ganancia"
                else:
                    impacto = "neutral"

                ok = insertar(
                    "ajustes_inventario",
                    {
                        "fecha": str(fecha),
                        "producto_origen": producto_origen,
                        "producto_destino": producto_destino,
                        "cantidad": float(cantidad),
                        "tipo_ajuste": tipo_ajuste,
                        "costo_origen": costo_origen,
                        "costo_destino": costo_destino,
                        "diferencia_costo": diferencia_costo,
                        "impacto": impacto,
                        "observacion": observacion,
                    },
                )

                if ok:
                    cant_origen = float(limpiar_numero(po.get("cantidad")) or 0) + float(cantidad)
                    cant_destino = float(limpiar_numero(pdst.get("cantidad")) or 0) - float(cantidad)
                    actualizar_stock_producto(producto_origen, cant_origen, fecha)
                    actualizar_stock_producto(producto_destino, cant_destino, fecha)
                    upsert_inventario_actual(producto_origen, costo_origen, float(limpiar_numero(po.get("precio")) or 0), cant_origen, fecha, "Ajuste inventario")
                    upsert_inventario_actual(producto_destino, costo_destino, float(limpiar_numero(pdst.get("precio")) or 0), cant_destino, fecha, "Ajuste inventario")
                    if impacto == "perdida":
                        registrar_perdida(
                            fecha,
                            producto_origen,
                            float(cantidad),
                            abs(costo_origen - costo_destino),
                            "ajuste_mercancia",
                            f"Ajuste contra {producto_destino}. Diferencia de costo total: {diferencia_costo}",
                            estado="debitada",
                        )
                    st.success("Ajuste guardado y stock actualizado.")
                    st.rerun()

    df = DATA["ajustes_inventario"].copy()
    if not df.empty:
        st.subheader("📋 Historial de ajustes")
        d1, d2 = rango_fechas_ui("ajustes")
        df = filtrar_por_fechas(df, d1, d2)
        txt = st.text_input("Buscar ajuste", key="buscar_ajustes")
        df = buscar_df(df, txt)
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "ajustes_inventario")
        render_crud_generico("ajustes_inventario", df, "🛠️ Editar / eliminar ajustes de inventario")
    else:
        st.info("No hay ajustes registrados.")


# =========================================================
# VENTAS
# =========================================================


def render_compras():
    st.title("🧾 Panel de Compras y Proveedores")
    st.caption("Gestiona las entradas de mercancía al inventario y el catálogo de proveedores asociados en un solo lugar.")
    
    # Inicializar variables de estado de sesión para el buscador de Compras
    if "comp_producto_seleccionado" not in st.session_state:
        st.session_state["comp_producto_seleccionado"] = None
    if "comp_search_page" not in st.session_state:
        st.session_state["comp_search_page"] = 1
        
    productos_df = DATA["productos"].copy()
    proveedores_df = DATA.get("proveedores", pd.DataFrame()).copy()
    
    tab_compras, tab_proveedores, tab_utilidad_historico = st.tabs(["🧾 Cargar Compras & Historial", "🚚 Control de Proveedores", "📈 Utilidad por Producto (Histórico)"])
    
    with tab_compras:
        with st.expander("📥 Subir Excel / CSV de compras", expanded=False):
            st.write("Acepta columnas como fecha, producto/nombre, código, cantidad, costo, proveedor, número, descripción y método.")
            archivo = st.file_uploader("Sube archivo", type=["xlsx", "xls", "csv"], key="up_compras_pro")
            if archivo is not None and st.button("Cargar compras", key="btn_cargar_compras_pro"):
                df = leer_archivo_subido(archivo)
                if "nombre" not in df.columns and "producto" not in df.columns:
                    st.error("El archivo debe traer producto o nombre.")
                else:
                    procesadas = 0
                    for _, row in df.iterrows():
                        nombre = limpiar_texto(row.get("nombre") or row.get("producto"))
                        codigo = limpiar_texto(row.get("codigo"))
                        cantidad = limpiar_numero(row.get("cantidad")) or 0
                        costo_unitario = limpiar_numero(row.get("costo") or row.get("costo_unitario")) or 0
                        if not nombre or cantidad <= 0:
                            continue
                        prod = get_producto_por_codigo(codigo) if codigo else None
                        if prod is None:
                            prod = get_producto_por_nombre(nombre)
                        if prod is None:
                            payload = {
                                "fecha": parsear_fecha(row.get("fecha")) or ahora_str(),
                                "codigo": codigo,
                                "nombre": nombre,
                                "costo": float(costo_unitario),
                                "precio": float(limpiar_numero(row.get("precio")) or 0),
                                "cantidad": 0.0,
                                "activo": True,
                                "usa_inventario": True,
                            }
                            if "stock" in DATA["productos"].columns:
                                payload["stock"] = 0.0
                            try:
                                supabase.table("productos").insert(payload).execute()
                            except Exception:
                                pass
                            DATA.update(cargar_datos())
                            prod = get_producto_por_codigo(codigo) if codigo else get_producto_por_nombre(nombre)
                        if prod is not None:
                            ok = registrar_compra_producto(
                                prod,
                                cantidad=float(cantidad),
                                costo_unitario=float(costo_unitario),
                                fecha_compra=parsear_fecha(row.get("fecha")) or ahora_str(),
                                proveedor=limpiar_texto(row.get("proveedor") or ""),
                                numero=limpiar_texto(row.get("numero") or ""),
                                descripcion=limpiar_texto(row.get("descripcion") or ""),
                                metodo=limpiar_texto(row.get("metodo") or "efectivo"),
                            )
                            if ok:
                                procesadas += 1
                    st.success(f"Se cargaron {procesadas} compras.")
                    st.rerun()

        # --- FACTURADOR DE COMPRAS DE ALTA FIDELIDAD (INVOICE BUILDER) ---
        if "compra_carrito" not in st.session_state:
            st.session_state["compra_carrito"] = []

        # --- REGISTRO DE DIÁLOGOS EMERGENTES DE SOPORTE ---
        
        @st.dialog("🔍 Buscar Productos", width="large")
        def dialog_buscar_productos_compra():
            st.markdown("""
            <style>
            .dialog-badge {
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                color: white;
            }
            </style>
            """, unsafe_allow_html=True)
            
            c_col1, c_col2 = st.columns([2, 1])
            with c_col1:
                m_query = st.text_input("BUSCAR POR CODIGO/NOMBRE", key="comp_modal_query_src", placeholder="BUSCAR POR CODIGO/NOMBRE", label_visibility="collapsed")
            with c_col2:
                categorias_raw = productos_df["categoria"].unique() if "categoria" in productos_df.columns else []
                categorias = ["-- CATEGORÍA --"] + sorted([str(c) for c in categorias_raw if str(c).strip() != "" and str(c).lower() not in ['nan', 'none']])
                m_cat = st.selectbox("CATEGORÍA", categorias, key="comp_modal_cat_src", label_visibility="collapsed")
                
            df_m = productos_df.copy()
            if "activo" in df_m.columns:
                df_m = df_m[df_m["activo"] == True]
            if m_query:
                df_m = df_m[
                    df_m["nombre"].astype(str).str.contains(m_query, case=False, na=False) |
                    df_m["codigo"].astype(str).str.contains(m_query, case=False, na=False) |
                    df_m["categoria"].astype(str).str.contains(m_query, case=False, na=False)
                ]
            if m_cat != "-- CATEGORÍA --":
                df_m = df_m[df_m["categoria"] == m_cat]
                
            if df_m.empty:
                st.info("No se encontraron productos.")
            else:
                import math
                total_items = len(df_m)
                items_per_page = 8
                total_pages = max(1, math.ceil(total_items / items_per_page))
                
                if "comp_modal_page" not in st.session_state:
                    st.session_state["comp_modal_page"] = 1
                    
                last_query_key = f"_comp_modal_last_query_{m_query}_{m_cat}"
                if st.session_state.get("_comp_modal_last_query_key") != last_query_key:
                    st.session_state["comp_modal_page"] = 1
                    st.session_state["_comp_modal_last_query_key"] = last_query_key
                    
                current_page = st.session_state["comp_modal_page"]
                if current_page > total_pages:
                    current_page = total_pages
                    st.session_state["comp_modal_page"] = total_pages
                    
                start_idx = (current_page - 1) * items_per_page
                df_display = df_m.iloc[start_idx : start_idx + items_per_page]
                
                # Cabecera de la Tabla
                st.markdown("<div style='background-color: rgba(255,255,255,0.05); padding: 8px; font-weight: bold; border-bottom: 2px solid rgba(255,255,255,0.1);'><div style='display: grid; grid-template-columns: 2fr 3fr 1fr 1.2fr 1.2fr 0.8fr; gap: 8px; font-size: 11px; text-transform: uppercase;'><div>Cod.</div><div>Producto</div><div>Stock</div><div>Cant</div><div>Costo</div><div></div></div></div>", unsafe_allow_html=True)
                
                for idx, (_, row) in enumerate(df_display.iterrows()):
                    row_id = str(row["id"])
                    p_nom = obtener_nombre_producto(row)
                    p_cod = limpiar_texto(row.get("codigo")) or "SIN CODIGO"
                    p_st = obtener_existencia_producto(row)
                    p_bg = "#ffd600" if p_st < 5 else "#1e88e5"
                    p_color = "black" if p_st < 5 else "white"
                    p_costo_sug = float(row.get("costo") or 0.0)
                    
                    row_cols = st.columns([2, 3, 1, 1.2, 1.2, 0.8])
                    with row_cols[0]:
                        st.markdown(f"<div style='font-size:12px; font-family:monospace; padding-top:6px;'>{p_cod}</div>", unsafe_allow_html=True)
                    with row_cols[1]:
                        st.markdown(f"<div style='font-size:12px; font-weight:bold; padding-top:6px;'>{p_nom.upper()}</div>", unsafe_allow_html=True)
                    with row_cols[2]:
                        st.markdown(f"<div style='padding-top:4px;'><span class='dialog-badge' style='background-color:{p_bg}; color:{p_color} !important;'>{p_st:,.0f}</span></div>", unsafe_allow_html=True)
                    with row_cols[3]:
                        cant_val = st.number_input("Cant", min_value=1.0, value=1.0, step=1.0, key=f"modal_cant_{row_id}", label_visibility="collapsed")
                    with row_cols[4]:
                        costo_val = st.number_input("Costo", min_value=0.0, value=p_costo_sug, step=1.0, key=f"modal_costo_{row_id}", label_visibility="collapsed")
                    with row_cols[5]:
                        st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                        if st.button("➕", key=f"btn_modal_add_{row_id}_{idx}", use_container_width=True):
                            # Añadir a st.session_state["compra_carrito"]
                            st.session_state["compra_carrito"].append({
                                "producto_id": row_id,
                                "codigo": p_cod,
                                "nombre": p_nom,
                                "cantidad": float(cant_val),
                                "costo_unitario": float(costo_val)
                            })
                            st.toast(f"✅ Agregado: {p_nom}")
                            st.rerun()
                            
                # Controles de Paginación
                st.markdown("---")
                pag_cols = st.columns([2, 6, 2])
                with pag_cols[0]:
                    if current_page > 1:
                        if st.button("‹ Anterior", key="btn_modal_prev_page", use_container_width=True):
                            st.session_state["comp_modal_page"] = current_page - 1
                            st.rerun()
                    else:
                        st.button("‹ Anterior", key="btn_modal_prev_page_disabled", disabled=True, use_container_width=True)
                with pag_cols[1]:
                    st.markdown(f"<div style='text-align: center; padding-top: 5px; font-weight: bold;'>Página {current_page} de {total_pages}</div>", unsafe_allow_html=True)
                with pag_cols[2]:
                    if current_page < total_pages:
                        if st.button("Siguiente ›", key="btn_modal_next_page", use_container_width=True):
                            st.session_state["comp_modal_page"] = current_page + 1
                            st.rerun()
                    else:
                        st.button("Siguiente ›", key="btn_modal_next_page_disabled", disabled=True, use_container_width=True)
                        
            st.markdown("---")
            if st.button("Cerrar", key="btn_close_modal_comp", use_container_width=True):
                st.rerun()

        @st.dialog("➕ Crear Nuevo Producto", width="large")
        def dialog_crear_producto_compra():
            st.markdown("##### 📦 Crear Producto desde Compra")
            c1, c2 = st.columns(2)
            with c1:
                nuevo_codigo = st.text_input("Código de barras / SKU", key="dialog_prod_codigo")
                nuevo_nombre = st.text_input("Nombre del producto", key="dialog_prod_nombre")
            with c2:
                nuevo_precio = st.number_input("Precio de venta sugerido", min_value=0.0, step=1.0, key="dialog_prod_precio")
                nuevo_categoria = st.text_input("Categoría", key="dialog_prod_categoria")
                
            if st.button("Crear y agregar al carrito", key="btn_dialog_crear_prod", use_container_width=True):
                nombre_clean = limpiar_texto(nuevo_nombre)
                if not nombre_clean:
                    st.error("Debes poner nombre al producto.")
                    st.stop()
                valido, msg_err = validar_unicidad_producto(nombre_clean, nuevo_codigo)
                if not valido:
                    st.error(msg_err)
                    st.stop()
                existente = None
                if existente is None:
                    payload = {
                        "fecha": ahora_str(),
                        "codigo": limpiar_texto(nuevo_codigo),
                        "nombre": nombre_clean,
                        "categoria": limpiar_texto(nuevo_categoria),
                        "costo": 0.0,
                        "precio": float(nuevo_precio),
                        "cantidad": 0.0,
                        "activo": True,
                        "usa_inventario": True,
                    }
                    if "stock" in DATA["productos"].columns:
                        payload["stock"] = 0.0
                    supabase.table("productos").insert(payload).execute()
                    DATA.update(cargar_datos())
                    
                prod = get_producto_por_codigo(nuevo_codigo) if nuevo_codigo else get_producto_por_nombre(nombre_clean)
                if prod is not None:
                    st.session_state["compra_carrito"].append({
                        "producto_id": str(prod["id"]),
                        "codigo": prod.get("codigo") or "SIN CODIGO",
                        "nombre": obtener_nombre_producto(prod),
                        "cantidad": 1.0,
                        "costo_unitario": 0.0
                    })
                    st.success(f"✅ Creado y agregado: {obtener_nombre_producto(prod)}")
                    st.rerun()

        @st.dialog("➕ Crear Nuevo Proveedor", width="large")
        def dialog_crear_proveedor_compra():
            st.markdown("##### 🚚 Registrar Proveedor Inline")
            cp1, cp2 = st.columns(2)
            with cp1:
                nuevo_prov_nombre = st.text_input("Nombre del proveedor", key="dialog_prov_nombre")
                nuevo_prov_telefono = st.text_input("Teléfono", key="dialog_prov_tel")
                nuevo_prov_rnc = st.text_input("RNC", key="dialog_prov_rnc")
            with cp2:
                nuevo_prov_direccion = st.text_input("Dirección", key="dialog_prov_dir")
                nuevo_prov_contacto = st.text_input("Nombre de contacto", key="dialog_prov_contacto")
                
            if st.button("Guardar y seleccionar", key="btn_dialog_crear_prov", use_container_width=True):
                prov_nombre_clean = limpiar_texto(nuevo_prov_nombre)
                if not prov_nombre_clean:
                    st.error("El nombre del proveedor es obligatorio.")
                    st.stop()
                prov_exists = not proveedores_df.empty and prov_nombre_clean.lower() in proveedores_df["nombre"].astype(str).str.lower().tolist()
                if not prov_exists:
                    prov_payload = {
                        "nombre": prov_nombre_clean,
                        "telefono": limpiar_texto(nuevo_prov_telefono),
                        "rnc": limpiar_texto(nuevo_prov_rnc),
                        "direccion": limpiar_texto(nuevo_prov_direccion),
                        "contacto": limpiar_texto(nuevo_prov_contacto),
                        "activo": True
                    }
                    insertar("proveedores", prov_payload)
                    DATA.update(cargar_datos())
                    
                st.session_state["comp_prov_sel"] = prov_nombre_clean
                st.success("✅ Proveedor creado y seleccionado.")
                st.rerun()

        # --- SECCIONES DE DOS COLUMNAS DE ALTA FIDELIDAD ---
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        col_izq, col_der = st.columns([6, 4])
        
        with col_izq:
            # Cabecera Solid Blue/Green Banner
            st.markdown("""
            <div style="background-color: #0091ff; color: white; padding: 12px 18px; border-radius: 8px 8px 0 0; font-weight: bold; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 0px;">
                <span style="font-size: 15px; letter-spacing: 0.5px; font-weight: 800;">NUEVA COMPRA</span>
                <span style="font-size: 11px; opacity: 0.9; font-family: monospace;">REGISTRO DE MERCANCÍA</span>
            </div>
            """, unsafe_allow_html=True)
            
            with st.container(border=True):
                # Fila de Acciones Rápidas
                quick_cols = st.columns([1.2, 3, 0.8, 0.8])
                with quick_cols[0]:
                    cant_quick = st.number_input("Cant:", min_value=1.0, value=1.0, step=1.0, key="comp_quick_cant")
                with quick_cols[1]:
                    codigo_quick = st.text_input("Código:", key="comp_quick_codigo", placeholder="Escanear o ingresar código...", label_visibility="collapsed")
                with quick_cols[2]:
                    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                    if st.button("🔍", key="btn_comp_trigger_search", help="Buscar en el catálogo", use_container_width=True):
                        dialog_buscar_productos_compra()
                with quick_cols[3]:
                    st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                    if st.button("➕", key="btn_comp_trigger_add_prod", help="Crear producto nuevo", use_container_width=True):
                        dialog_crear_producto_compra()
                
                with st.expander("🧮 Calculadora de Compra por Cajas (Automática)", expanded=False):
                    st.caption("Digita la cantidad de cajas, unidades por caja y costo total. El sistema calculará el costo unitario de forma automática.")
                    
                    prod_lista_calc = [""] + sorted(productos_df["nombre"].dropna().unique().tolist()) if not productos_df.empty else [""]
                    prod_calc_sel = st.selectbox("Seleccione el Producto a comprar", prod_lista_calc, key="comp_calc_prod")
                    
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        cajas_val = st.number_input("Cantidad de cajas", min_value=1.0, value=1.0, step=1.0, key="comp_calc_cajas")
                        uds_caja_val = st.number_input("Unidades por caja", min_value=1.0, value=24.0, step=1.0, key="comp_calc_uds")
                    with cc2:
                        costo_total_val = st.number_input("Costo total de la compra (RD$)", min_value=0.0, value=0.0, step=100.0, key="comp_calc_costo_total")
                    
                    total_unidades = float(cajas_val * uds_caja_val)
                    costo_caja = float(costo_total_val / cajas_val) if cajas_val > 0 else 0.0
                    costo_unidad = float(costo_total_val / total_unidades) if total_unidades > 0 else 0.0
                    
                    st.markdown("---")
                    st.markdown(f"**Resultados del cálculo:**")
                    st.write(f"- 📦 **Total de unidades compradas:** {total_unidades:,.0f} uds.")
                    st.write(f"- 💵 **Costo por caja:** RD$ {costo_caja:,.2f}")
                    st.write(f"- 🪙 **Costo por unidad:** RD$ {costo_unidad:,.2f}")
                    
                    if st.button("📥 Cargar al carrito desde calculadora", key="btn_comp_calc_add", use_container_width=True):
                        if not prod_calc_sel:
                            st.error("Por favor seleccione un producto.")
                        elif costo_total_val <= 0:
                            st.error("El costo total de la compra debe ser mayor a 0.")
                        else:
                            p_row_calc = productos_df[productos_df["nombre"] == prod_calc_sel].iloc[0]
                            st.session_state["compra_carrito"].append({
                                "producto_id": str(p_row_calc["id"]),
                                "codigo": p_row_calc.get("codigo") or "SIN CODIGO",
                                "nombre": prod_calc_sel,
                                "cantidad": float(total_unidades),
                                "costo_unitario": float(costo_unidad),
                                "cajas": float(cajas_val),
                                "unidades_por_caja": float(uds_caja_val)
                            })
                            st.toast(f"✅ Agregado: {prod_calc_sel} ({total_unidades:,.0f} uds)")
                            st.rerun()
                
                # Procesar código rápido de barra ingresado
                if codigo_quick.strip():
                    codigo_clean = codigo_quick.strip()
                    prod_quick = get_producto_por_codigo(codigo_clean)
                    if prod_quick is None:
                        prod_quick = get_producto_por_nombre(codigo_clean)
                    if prod_quick is not None:
                        # Añadir al carrito
                        st.session_state["compra_carrito"].append({
                            "producto_id": str(prod_quick["id"]),
                            "codigo": prod_quick.get("codigo") or "SIN CODIGO",
                            "nombre": obtener_nombre_producto(prod_quick),
                            "cantidad": float(cant_quick),
                            "costo_unitario": float(prod_quick.get("costo") or 0.0)
                        })
                        st.toast(f"✅ Agregado: {obtener_nombre_producto(prod_quick)}")
                        st.session_state.pop("comp_quick_codigo", None)
                        st.rerun()
                    else:
                        st.error("Código de producto no encontrado. Presione 🔍 para buscar en el catálogo.")
                
                st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
                
                # Cabecera de la Tabla
                st.markdown("<div style='background-color: rgba(255,255,255,0.04); padding: 8px 10px; border-bottom: 2px solid rgba(255,255,255,0.08);'><div style='display: grid; grid-template-columns: 2.2fr 1.5fr 3.3fr 2fr 2fr 0.8fr; gap: 8px; font-size: 11px; font-weight: bold; text-transform: uppercase; color: #888888;'><div>Cod.</div><div>Cant.</div><div>Descripción</div><div>Costo</div><div>Total</div><div></div></div></div>", unsafe_allow_html=True)
                
                # Sincronizar en caliente los valores modificados de la tabla con el estado
                for idx, item in enumerate(st.session_state["compra_carrito"]):
                    cant_key = f"comp_cart_cant_{idx}"
                    costo_key = f"comp_cart_costo_{idx}"
                    if cant_key in st.session_state:
                        st.session_state["compra_carrito"][idx]["cantidad"] = float(st.session_state[cant_key])
                    if costo_key in st.session_state:
                        st.session_state["compra_carrito"][idx]["costo_unitario"] = float(st.session_state[costo_key])
                
                carrito_list = st.session_state["compra_carrito"]
                subtotal = 0.0
                
                if not carrito_list:
                    st.info("El carrito está vacío. Agregue productos escaneando un código o haciendo clic en 🔍.")
                else:
                    for idx, item in enumerate(carrito_list):
                        item_id = item["producto_id"]
                        item_cod = item["codigo"]
                        item_nom = item["nombre"]
                        item_cant = item["cantidad"]
                        item_costo = item["costo_unitario"]
                        item_total = item_cant * item_costo
                        subtotal += item_total
                        
                        row_cols = st.columns([2.2, 1.5, 3.3, 2, 2, 0.8])
                        with row_cols[0]:
                            st.markdown(f"<div style='font-size:12px; font-family:monospace; padding-top:8px;'>{item_cod}</div>", unsafe_allow_html=True)
                        with row_cols[1]:
                            st.number_input("Cant", min_value=1.0, value=item_cant, step=1.0, key=f"comp_cart_cant_{idx}", label_visibility="collapsed")
                        with row_cols[2]:
                            st.markdown(f"<div style='font-size:12px; font-weight:bold; padding-top:8px;'>{item_nom.upper()}</div>", unsafe_allow_html=True)
                        with row_cols[3]:
                            st.number_input("Costo", min_value=0.0, value=item_costo, step=1.0, key=f"comp_cart_costo_{idx}", label_visibility="collapsed")
                        with row_cols[4]:
                            st.markdown(f"<div style='font-size:12px; font-weight:bold; padding-top:8px;'>$ {item_total:,.2f}</div>", unsafe_allow_html=True)
                        with row_cols[5]:
                            st.markdown("<div style='height: 4px;'></div>", unsafe_allow_html=True)
                            if st.button("❌", key=f"btn_comp_del_row_{idx}", help="Eliminar fila", use_container_width=True):
                                st.session_state["compra_carrito"].pop(idx)
                                st.rerun()
                                
                # Sección de Totales
                st.markdown("---")
                t_cols = st.columns([6, 4])
                with t_cols[1]:
                    itbis_amt = subtotal * 0.0 # 0% ITBIS por defecto en el facturador
                    total_fact = subtotal + itbis_amt
                    
                    st.markdown(f"""
                    <div style="text-align: right; font-size: 14px; font-family: monospace; line-height: 1.8;">
                        <div>SUBTOTAL $: <strong style="font-size: 15px; color: white;">{subtotal:,.2f}</strong></div>
                        <div style="color: #888888;">ITBIS (0)%: <strong>$ {itbis_amt:,.2f}</strong></div>
                        <div style="border-top: 1px solid rgba(255,255,255,0.1); margin-top: 4px; padding-top: 4px; font-size: 16px; color: #a3ffb4;">
                            TOTAL $: <strong style="font-size: 18px; color: #2ecc71;">{total_fact:,.2f}</strong>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
        with col_der:
            st.markdown("##### 📋 Datos Generales de la Compra")
            with st.container(border=True):
                # Proveedor Selector
                prov_list = [""]
                if not proveedores_df.empty and "nombre" in proveedores_df.columns:
                    prov_list = [""] + proveedores_df["nombre"].astype(str).tolist()
                
                prov_cols = st.columns([4, 1])
                with prov_cols[0]:
                    proveedor_sel = st.selectbox("Buscar Proveedor", prov_list, key="comp_prov_sel")
                with prov_cols[1]:
                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("➕", key="btn_comp_add_prov_trigger", help="Registrar nuevo proveedor", use_container_width=True):
                        dialog_crear_proveedor_compra()
                
                # Cargar el RNC del proveedor seleccionado
                rnc_prov = ""
                if proveedor_sel and not proveedores_df.empty and "nombre" in proveedores_df.columns:
                    prov_match = proveedores_df[proveedores_df["nombre"].astype(str) == proveedor_sel]
                    if not prov_match.empty:
                        rnc_prov = limpiar_texto(prov_match.iloc[0].get("rnc")) or ""
                
                # Demás campos
                c_fields1, c_fields2 = st.columns(2)
                with c_fields1:
                    num_fact = st.text_input("No. Factura", value=generar_numero_compra(), key="comp_num")
                    metodo_pago = st.selectbox("Pago", ["Efectivo", "Transferencia", "Tarjeta", "Crédito"], key="comp_met")
                with c_fields2:
                    ref_fact = st.text_input("Referencia", key="comp_ref")
                    fecha_fact = st.date_input("Fecha", value=date.today(), key="comp_fecha")
                    
                st.text_input("RNC", value=rnc_prov, key="comp_rnc", disabled=True)
                desc_fact = st.text_area("Descripción / observación", key="comp_desc", placeholder="Opcional...", height=80)
                
                # Estilo de inyección CSS para botón de guardado rojo
                st.markdown("""
                <style>
                div.stButton > button:first-child[key*="btn_save_compra_final"] {
                    background-color: #ef5350 !important;
                    color: white !important;
                    border: none !important;
                    height: 45px !important;
                    font-size: 16px !important;
                    font-weight: 800 !important;
                    border-radius: 6px !important;
                }
                div.stButton > button:first-child[key*="btn_save_compra_final"]:hover {
                    background-color: #d32f2f !important;
                    color: white !important;
                }
                </style>
                """, unsafe_allow_html=True)
                
                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("🖨️ Guardar", key="btn_save_compra_final", use_container_width=True):
                    if not st.session_state["compra_carrito"]:
                        st.error("El carrito está vacío. Agregue productos antes de guardar.")
                    elif not proveedor_sel:
                        st.error("Debe seleccionar un proveedor.")
                    elif not num_fact.strip():
                        st.error("Debe ingresar el número de factura.")
                    else:
                        # Guardar compras en cascada
                        guardados_ok = 0
                        for item in st.session_state["compra_carrito"]:
                            p_id = item["producto_id"]
                            p_cant = item["cantidad"]
                            p_costo = item["costo_unitario"]
                            p_nom = item["nombre"]
                            
                            p_cajas = item.get("cajas")
                            p_uds_caja = item.get("unidades_por_caja")
                            if p_cajas and p_uds_caja:
                                p_desc = f"Compra de {p_cajas:.0f} cajas de {p_uds_caja:.0f} uds. Costo/caja: RD$ {p_costo * p_uds_caja:,.2f}."
                                if desc_fact.strip():
                                    p_desc += f" - {desc_fact.strip()}"
                            else:
                                p_desc = desc_fact.strip() or f"Compra de {p_nom}"
                            
                            p_rows = productos_df[productos_df["id"].astype(str) == str(p_id)]
                            if not p_rows.empty:
                                p_row = p_rows.iloc[0]
                                ok = registrar_compra_producto(
                                    producto_row=p_row,
                                    cantidad=float(p_cant),
                                    costo_unitario=float(p_costo),
                                    fecha_compra=str(fecha_fact),
                                    proveedor=proveedor_sel,
                                    numero=num_fact.strip(),
                                    descripcion=p_desc,
                                    metodo=metodo_pago.lower()
                                )
                                if ok:
                                    guardados_ok += 1
                                    
                        if guardados_ok > 0:
                            st.session_state["compra_carrito"] = []
                            st.session_state.pop("comp_num", None)
                            st.session_state.pop("comp_ref", None)
                            st.session_state.pop("comp_desc", None)
                            st.success(f"Factura de compra guardada con éxito. Se registraron {guardados_ok} productos.")
                            DATA.update(cargar_datos())
                            st.rerun()

        # =====================================================
        # HISTORIAL DE COMPRAS — EDITOR AVANZADO
        # =====================================================
        st.markdown("---")
        st.subheader("📋 Historial de Compras del Período")
        df_hist_c = DATA["compras"].copy()

        if not df_hist_c.empty:
            d1, d2 = rango_fechas_ui("compras")
            df_hist_c = filtrar_por_fechas(df_hist_c, d1, d2)

            # --- Buscador ---
            busq_c = st.text_input("🔍 Buscar proveedor, factura o producto", key="buscar_compras_hist")
            if busq_c:
                df_hist_c = buscar_df(df_hist_c, busq_c)

            if df_hist_c.empty:
                st.info("No hay compras en ese período / búsqueda.")
            else:
                # Añadir Código secuencial para visualización
                df_hist_c = agregar_columna_codigo_secuencial(df_hist_c, "compras")

                # Columnas visibles en la tabla resumen
                cols_vis = [c for c in ["Código", "fecha", "numero", "proveedor", "producto", "cantidad", "costo_unitario", "total", "metodo", "descripcion"]
                            if c in df_hist_c.columns]
                st.dataframe(df_hist_c[cols_vis], use_container_width=True)
                descargar_archivos(df_hist_c, "compras")

                if puede_editar_compras() or puede_eliminar_compras():
                    st.markdown("---")
                    st.markdown("#### ✏️ Editar Compra Seleccionada")

                    # Selector de compra a editar
                    opciones_c = []
                    mapa_c = {}
                    for _, r in df_hist_c.iterrows():
                        cod = r.get("Código") or r.get("id") or ""
                        prov = limpiar_texto(r.get("proveedor") or "")
                        num = limpiar_texto(r.get("numero") or "")
                        prod = limpiar_texto(r.get("producto") or "")
                        fecha_r = str(r.get("fecha") or "")[:10]
                        etiq = f"{cod} | {fecha_r} | {prov} | {num} | {prod}"
                        opciones_c.append(etiq)
                        mapa_c[etiq] = r
                    etiq_sel = st.selectbox("Selecciona la compra a editar", opciones_c, key="edit_compra_sel")
                    fila_c = mapa_c[etiq_sel]
                    fila_c_id = valor_simple(fila_c.get("id") or fila_c.get("identificación"))

                    with st.container(border=True):
                        st.markdown("##### 📅 Datos Generales de la Compra")
                        ec1, ec2, ec3 = st.columns(3)

                        with ec1:
                            fecha_actual_c = pd.to_datetime(fila_c.get("fecha"), errors="coerce")
                            fecha_edit_c = st.date_input(
                                "📅 Fecha de la compra",
                                value=fecha_actual_c.date() if not pd.isna(fecha_actual_c) else date.today(),
                                key=f"edit_c_fecha_{fila_c_id}"
                            )
                            num_fact_edit = st.text_input("No. Factura (no editable)", value=limpiar_texto(fila_c.get("numero") or ""), key=f"edit_c_num_{fila_c_id}", disabled=True, help="El número de factura es un identificador único y no puede modificarse.")

                        with ec2:
                            prov_list_e = [""] + (proveedores_df["nombre"].astype(str).tolist() if not proveedores_df.empty and "nombre" in proveedores_df.columns else [])
                            prov_actual = limpiar_texto(fila_c.get("proveedor") or "")
                            prov_idx = prov_list_e.index(prov_actual) if prov_actual in prov_list_e else 0
                            prov_edit_c = st.selectbox("Proveedor", prov_list_e, index=prov_idx, key=f"edit_c_prov_{fila_c_id}")
                            metodo_edit_c = st.selectbox(
                                "Método de pago",
                                ["Efectivo", "Transferencia", "Tarjeta", "Crédito"],
                                index=["efectivo", "transferencia", "tarjeta", "credito"].index(
                                    normalizar_texto(limpiar_texto(fila_c.get("metodo") or "efectivo"))
                                ) if normalizar_texto(limpiar_texto(fila_c.get("metodo") or "efectivo")) in ["efectivo", "transferencia", "tarjeta", "credito"] else 0,
                                key=f"edit_c_metodo_{fila_c_id}"
                            )

                        with ec3:
                            desc_edit_c = st.text_area("Descripción / Observación", value=limpiar_texto(fila_c.get("descripcion") or ""), height=100, key=f"edit_c_desc_{fila_c_id}")

                        st.markdown("---")
                        st.markdown("##### 📦 Detalles del Producto en Esta Línea")

                        ep1, ep2 = st.columns(2)
                        cant_actual_c = float(limpiar_numero(fila_c.get("cantidad")) or 0.0)
                        costo_u_actual_c = float(limpiar_numero(fila_c.get("costo_unitario")) or 0.0)

                        with ep1:
                            # Campos directos
                            cant_edit_c = st.number_input("Cantidad total (unidades)", min_value=0.0, value=cant_actual_c, step=1.0, key=f"edit_c_cant_{fila_c_id}")
                            costo_u_edit_c = st.number_input("Costo por unidad (RD$)", min_value=0.0, value=costo_u_actual_c, step=0.01, key=f"edit_c_cu_{fila_c_id}")

                        with ep2:
                            total_edit_c = cant_edit_c * costo_u_edit_c
                            st.metric("Total de esta línea", f"RD$ {total_edit_c:,.2f}")

                        # Calculadora de cajas (igual que en nueva compra)
                        with st.expander("🧮 Recalcular usando Cajas (Opcional)", expanded=False):
                            st.caption("Rellena estos campos para recalcular automáticamente la cantidad y el costo por unidad.")
                            bc1, bc2 = st.columns(2)
                            with bc1:
                                cajas_e = st.number_input("Cantidad de cajas", min_value=1.0, value=1.0, step=1.0, key=f"edit_c_cajas_{fila_c_id}")
                                uds_e = st.number_input("Unidades por caja", min_value=1.0, value=24.0, step=1.0, key=f"edit_c_uds_{fila_c_id}")
                            with bc2:
                                costo_total_e = st.number_input("Costo total compra (RD$)", min_value=0.0, value=float(limpiar_numero(fila_c.get("total") or fila_c.get("monto")) or 0.0), step=100.0, key=f"edit_c_ctotal_{fila_c_id}")
                            total_uds_e = cajas_e * uds_e
                            costo_caja_e = costo_total_e / cajas_e if cajas_e > 0 else 0.0
                            costo_ud_e = costo_total_e / total_uds_e if total_uds_e > 0 else 0.0
                            st.write(f"- 📦 **Total unidades:** {total_uds_e:,.0f}")
                            st.write(f"- 💵 **Costo por caja:** RD$ {costo_caja_e:,.2f}")
                            st.write(f"- 🪙 **Costo por unidad:** RD$ {costo_ud_e:,.2f}")
                            if st.button("↩️ Aplicar cálculo al formulario arriba", key=f"edit_c_aplicar_calc_{fila_c_id}"):
                                st.session_state[f"edit_c_cant_{fila_c_id}"] = total_uds_e
                                st.session_state[f"edit_c_cu_{fila_c_id}"] = costo_ud_e
                                st.rerun()

                        st.markdown("---")
                        btn_c1, btn_c2 = st.columns(2)

                        with btn_c1:
                            if puede_editar_compras():
                                if st.button("💾 Guardar cambios en esta compra", key=f"btn_save_edit_c_{fila_c_id}", use_container_width=True):
                                    nuevos_c = {
                                        "fecha": str(fecha_edit_c),
                                        # numero NO se incluye: es identificador único inmutable
                                        "proveedor": prov_edit_c,
                                        "metodo": metodo_edit_c.lower(),
                                        "descripcion": desc_edit_c.strip(),
                                        "cantidad": float(cant_edit_c),
                                        "costo_unitario": float(costo_u_edit_c),
                                        "total": float(total_edit_c),
                                        "monto": float(total_edit_c),
                                    }
                                    # Sincronizar diferencia de cantidad con inventario
                                    dif_c = float(cant_edit_c) - float(cant_actual_c)
                                    if dif_c != 0:
                                        p_id_c = fila_c.get("producto_id")
                                        fp = refrescar_producto_por_id(p_id_c) if p_id_c else get_producto_por_nombre(fila_c.get("producto"))
                                        if fp is not None:
                                            nuevo_stk = max(obtener_existencia_producto(fp) + dif_c, 0.0)
                                            actualizar_stock_producto(fp["nombre"], nuevo_stk)
                                            if float(costo_u_edit_c) > 0:
                                                actualizar("productos", fp["id"], {"costo": float(costo_u_edit_c)})
                                    if actualizar("compras", fila_c_id, nuevos_c):
                                        st.success("✅ Compra actualizada correctamente.")
                                        DATA.update(cargar_datos())
                                        st.rerun()
                            else:
                                st.warning("No tienes permisos para editar compras.")

                        with btn_c2:
                            if puede_eliminar_compras():
                                if st.button("🗑️ Eliminar esta compra", key=f"btn_del_edit_c_{fila_c_id}", use_container_width=True):
                                    p_id_c = fila_c.get("producto_id")
                                    fp = refrescar_producto_por_id(p_id_c) if p_id_c else get_producto_por_nombre(fila_c.get("producto"))
                                    if fp is not None:
                                        nuevo_stk = max(obtener_existencia_producto(fp) - cant_actual_c, 0.0)
                                        actualizar_stock_producto(fp["nombre"], nuevo_stk)
                                    if eliminar("compras", fila_c_id):
                                        st.success("🗑️ Compra eliminada y stock revertido.")
                                        DATA.update(cargar_datos())
                                        st.rerun()
                            else:
                                st.warning("No tienes permisos para eliminar compras.")
        else:
            st.info("No hay compras registradas.")


    with tab_proveedores:
        st.subheader("🚚 Control de Proveedores Integrado")
        with st.expander("➕ Agregar nuevo proveedor", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                prov_nombre = st.text_input("Nombre", key="prov_nombre_tab")
                prov_telefono = st.text_input("Teléfono", key="prov_tel_tab")
                prov_rnc = st.text_input("RNC", key="prov_rnc_tab")
            with c2:
                prov_direccion = st.text_input("Dirección", key="prov_dir_tab")
                prov_contacto = st.text_input("Contacto", key="prov_contacto_tab")
                prov_observacion = st.text_area("Observación", key="prov_obs_tab")
            if st.button("Guardar proveedor", key="btn_guardar_prov_tab", use_container_width=True):
                if not prov_nombre.strip():
                    st.error("El nombre del proveedor es obligatorio.")
                else:
                    prov_payload = {
                        "nombre": prov_nombre,
                        "telefono": prov_telefono,
                        "rnc": prov_rnc,
                        "direccion": prov_direccion,
                        "contacto": prov_contacto,
                        "activo": True,
                        "observacion": prov_observacion
                    }
                    if insertar("proveedores", prov_payload):
                        st.success("Proveedor guardado correctamente.")
                        DATA.update(cargar_datos())
                        st.rerun()
                        
        df_p = DATA.get("proveedores", pd.DataFrame()).copy()
        if not df_p.empty:
            st.dataframe(df_p, use_container_width=True)
            descargar_archivos(df_p, "proveedores")
            render_crud_generico("proveedores", df_p, "🛠️ Editar / eliminar proveedores")
        else:
            st.info("No hay proveedores registrados.")

    with tab_utilidad_historico:
        st.subheader("📈 Reporte de Utilidad Histórica por Producto")
        st.caption("Consolidado acumulado de cantidades vendidas, costos y utilidad neta por producto.")
        import os
        filepath = "/Users/user/Desktop/APP.PY....copias.PY/Base de dato Bibe Ron/reporte_financiero.xls"
        if os.path.exists(filepath):
            try:
                df_fin = pd.read_html(filepath)[0]
                
                # Search filter
                txt_fin = st.text_input("🔍 Buscar producto en el reporte de utilidad", key="buscar_utilidad_fin")
                df_display = df_fin.copy()
                if txt_fin:
                    df_display = df_display[df_display["Producto"].astype(str).str.contains(txt_fin, case=False, na=False)]
                
                # Format numeric columns for summary metrics
                def clean_col_val(v):
                    if pd.isna(v): return 0.0
                    return float(str(v).replace("$", "").replace(",", "").strip())
                
                tot_cost = df_display["Total Costo"].apply(clean_col_val).sum()
                tot_vend = df_display["Total Vendido"].apply(clean_col_val).sum()
                tot_util = df_display["Utilidad"].apply(clean_col_val).sum()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Costo Total Acumulado", f"RD$ {tot_cost:,.2f}")
                col2.metric("Venta Total Acumulada", f"RD$ {tot_vend:,.2f}")
                col3.metric("Utilidad Acumulada", f"RD$ {tot_util:,.2f}")
                
                st.dataframe(df_display, use_container_width=True)
                descargar_archivos(df_display, "utilidad_historica_por_producto")
            except Exception as e:
                st.error(f"Error al leer el archivo de utilidad: {e}")
        else:
            st.info("No se encontró el archivo de reporte financiero histórico en el servidor.")

# =========================================================
# CATÁLOGO DE GASTOS
# =========================================================


def render_proveedores():
    st.title("🚚 Proveedores")
    next_prov_id = generar_codigo_secuencial("proveedores")
    st.caption(f"Identificador del próximo proveedor: **{next_prov_id}**")
    with st.expander("➕ Agregar proveedor", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", key="prov_nombre")
            telefono = st.text_input("Teléfono", key="prov_tel")
            rnc = st.text_input("RNC", key="prov_rnc")
        with c2:
            direccion = st.text_input("Dirección", key="prov_dir")
            contacto = st.text_input("Contacto", key="prov_contacto")
            observacion = st.text_area("Observación", key="prov_obs")
        if st.button("Guardar proveedor", key="btn_guardar_prov"):
            if insertar("proveedores", {"nombre": nombre, "telefono": telefono, "rnc": rnc, "direccion": direccion, "contacto": contacto, "activo": True, "observacion": observacion}):
                st.success("Proveedor guardado.")
                st.rerun()
    df = DATA.get("proveedores", pd.DataFrame()).copy()
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        descargar_archivos(df, "proveedores")
        render_crud_generico("proveedores", df, "🛠️ Editar / eliminar proveedores")
    else:
        st.info("No hay proveedores.")

# =========================================================
# CREDITOS
# =========================================================


