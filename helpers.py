# Shared Helper Functions for A&M ERP v2
import streamlit as st
import pandas as pd
import numpy as np
import re
import json
import uuid
import base64
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime, date, timedelta
from typing import Any

try:
    from core.db import (
        supabase, DATA, leer_tabla, insertar, actualizar, eliminar, anular, rpc,
        obtener_tenant_actual, usuario_sesion, nombre_usuario_actual, obtener_configuracion,
        _df_actual, leer_actualizado, invalidar_cache_tabla, limpiar_cache_datos,
        guardar_venta_rpc, custom_table, WrappedQueryBuilder, TABLAS_MULTI_TENANT,
        AM_LOGO_B64, get_am_logo_b64, total_contable_sin_recargo, aplicar_total_contable_df,
        es_superadmin_plataforma, to_decimal, registrar_auditoria_pro, _pii_mask, obtener_secreto
    )
except ModuleNotFoundError:
    from db import (
        supabase, DATA, leer_tabla, insertar, actualizar, eliminar, anular, rpc,
        obtener_tenant_actual, usuario_sesion, nombre_usuario_actual, obtener_configuracion,
        _df_actual, leer_actualizado, invalidar_cache_tabla, limpiar_cache_datos,
        guardar_venta_rpc, custom_table, WrappedQueryBuilder, TABLAS_MULTI_TENANT,
        AM_LOGO_B64, get_am_logo_b64, total_contable_sin_recargo, aplicar_total_contable_df,
        es_superadmin_plataforma, to_decimal, registrar_auditoria_pro, _pii_mask, obtener_secreto
    )

try:
    from core.auth import (
        es_admin, es_cajera, tiene_permiso, cerrar_sesion,
        puede_editar_global, puede_ver_utilidad_global, puede_vender, puede_abrir_caja,
        puede_cerrar_caja, puede_ver_ventas_propias, puede_ver_todas_ventas,
        puede_editar_ventas, puede_anular_ventas, puede_eliminar_ventas,
        puede_registrar_compras, puede_ver_compras, puede_editar_compras,
        puede_eliminar_compras, puede_aprobar_compras, puede_registrar_gastos,
        puede_ver_gastos, puede_editar_gastos, puede_eliminar_gastos,
        puede_ver_inventario, puede_registrar_conteo, puede_aplicar_ajuste_inventario,
        puede_editar_inventario, puede_reportar_perdidas, puede_ver_perdidas,
        puede_aprobar_perdidas, puede_debitar_perdidas, puede_editar_perdidas,
        puede_eliminar_perdidas, puede_ver_productos, puede_crear_productos,
        puede_editar_productos, puede_eliminar_productos, render_checkboxes_permisos,
        verificar_clave_usuario, verificar_codigo_totp,
        verificar_bloqueo_login, registrar_intento_fallido, limpiar_intentos_fallidos,
        mfa_requerido_para_admin
    )
except ModuleNotFoundError:
    from auth import (
        es_admin, es_cajera, tiene_permiso, cerrar_sesion,
        puede_editar_global, puede_ver_utilidad_global, puede_vender, puede_abrir_caja,
        puede_cerrar_caja, puede_ver_ventas_propias, puede_ver_todas_ventas,
        puede_editar_ventas, puede_anular_ventas, puede_eliminar_ventas,
        puede_registrar_compras, puede_ver_compras, puede_editar_compras,
        puede_eliminar_compras, puede_aprobar_compras, puede_registrar_gastos,
        puede_ver_gastos, puede_editar_gastos, puede_eliminar_gastos,
        puede_ver_inventario, puede_registrar_conteo, puede_aplicar_ajuste_inventario,
        puede_editar_inventario, puede_reportar_perdidas, puede_ver_perdidas,
        puede_aprobar_perdidas, puede_debitar_perdidas, puede_editar_perdidas,
        puede_eliminar_perdidas, puede_ver_productos, puede_crear_productos,
        puede_editar_productos, puede_eliminar_productos, render_checkboxes_permisos,
        verificar_clave_usuario, verificar_codigo_totp,
        verificar_bloqueo_login, registrar_intento_fallido, limpiar_intentos_fallidos,
        mfa_requerido_para_admin
    )

try:
    from core.utils import (
        limpiar_texto, quitar_acentos, normalizar_texto, limpiar_numero, parsear_fecha,
        selector_fechas_universal, normalizar_item_carrito, recalcular_item_carrito,
        carrito_limpio, buscar_nombre_producto_por_item, nombre_item, numero_factura_visible,
        predecir_categoria_y_tipo_gasto, generar_codigo_secuencial, generar_codigo_producto,
        agregar_columna_codigo_secuencial
    )
except ModuleNotFoundError:
    from utils import (
        limpiar_texto, quitar_acentos, normalizar_texto, limpiar_numero, parsear_fecha,
        selector_fechas_universal, normalizar_item_carrito, recalcular_item_carrito,
        carrito_limpio, buscar_nombre_producto_por_item, nombre_item, numero_factura_visible,
        predecir_categoria_y_tipo_gasto, generar_codigo_secuencial, generar_codigo_producto,
        agregar_columna_codigo_secuencial
    )
def valor_simple(valor: Any):
    if isinstance(valor, pd.Series):
        if valor.empty:
            return None
        return valor.iloc[0]
    if isinstance(valor, (list, tuple)):
        return valor[0] if valor else None
    return valor


def optimizar_y_codificar_imagen(file_bytes_or_url, is_url=False) -> str | None:
    from PIL import Image
    import io
    import requests
    import base64
    
    try:
        if is_url:
            headers = {"User-Agent": "A&M-ERP-SaaS/1.0 (nelly@amcontable.com)"}
            resp = requests.get(file_bytes_or_url, headers=headers, timeout=5)
            img_file = io.BytesIO(resp.content)
        else:
            img_file = io.BytesIO(file_bytes_or_url)
            
        img = Image.open(img_file)
        
        # Convert to RGB if in RGBA mode
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Resize to thumbnail max 150x150
        img.thumbnail((150, 150))
        
        # Save as WebP with quality 80
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="WebP", quality=80)
        webp_data = out_bytes.getvalue()
        
        # Convert to base64 Data URI
        b64 = base64.b64encode(webp_data).decode("utf-8")
        return f"data:image/webp;base64,{b64}"
    except Exception as e:
        st.error(f"Error procesando imagen: {e}")
        return None


def obtener_sugerencia_imagen_wiki(query) -> list:
    import requests
    import urllib.parse
    headers = {
        "User-Agent": "A&M-ERP-SaaS/1.0 (nelly@amcontable.com)"
    }
    url_search = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&utf8=1"
    try:
        r = requests.get(url_search, headers=headers, timeout=5)
        search_data = r.json()
        search_results = search_data.get("query", {}).get("search", [])
        if not search_results:
            return []
            
        urls = []
        # Get the page image for the top 3 matches
        for res in search_results[:3]:
            title = res.get("title")
            url_img = f"https://es.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=pageimages&format=json&pithumbsize=300"
            r_img = requests.get(url_img, headers=headers, timeout=5)
            pages = r_img.json().get("query", {}).get("pages", {})
            for pid, pdata in pages.items():
                thumb = pdata.get("thumbnail", {})
                if thumb:
                    urls.append({
                        "title": title,
                        "url": thumb.get("source")
                    })
        return urls
    except Exception:
        return []


def render_crud_generico(nombre_tabla: str, df: pd.DataFrame, titulo: str | None = None, excluir: list[str] | None = None, expanded: bool = False):
    # Determinar si tiene permiso de edición y eliminación para esta tabla
    puede_editar = False
    puede_eliminar = False
    
    if es_admin() or tiene_permiso("puede_editar_todo"):
        puede_editar = True
        puede_eliminar = True
    else:
        if nombre_tabla == "productos":
            puede_editar = puede_editar_productos()
            puede_eliminar = puede_eliminar_productos()
        elif nombre_tabla == "compras":
            puede_editar = puede_editar_compras()
            puede_eliminar = puede_eliminar_compras()
        elif nombre_tabla in ["gastos", "catalogo_gastos"]:
            puede_editar = puede_editar_gastos()
            puede_eliminar = puede_eliminar_gastos()
        elif nombre_tabla == "perdidas":
            puede_editar = puede_editar_perdidas()
            puede_eliminar = puede_eliminar_perdidas()
        elif nombre_tabla in ["inventario_actual", "ajustes_inventario", "conteo_inventario"]:
            puede_editar = puede_editar_inventario()
            puede_eliminar = puede_eliminar_inventario()
        elif nombre_tabla == "ventas":
            puede_editar = puede_editar_ventas()
            puede_eliminar = puede_eliminar_ventas()
        else:
            puede_editar = puede_editar_global()
            puede_eliminar = puede_editar_global() or tiene_permiso("puede_eliminar")

    # Si no puede hacer ninguna de las dos cosas, no mostramos el CRUD genérico
    if not puede_editar and not puede_eliminar:
        return

    if df is None or df.empty:
        return
    excluir = set((excluir or []) + ["id", "Código", "codigo_secuencial"])
    if nombre_tabla == "productos":
        excluir.add("imagen_url")
    if "identificación" in df.columns:
        excluir.add("identificación")
    titulo = titulo or f"🛠️ Editar / eliminar en {nombre_tabla}"
    with st.expander(titulo, expanded=expanded):
        df_local = df.copy()
        if "Código" not in df_local.columns:
            df_local = agregar_columna_codigo_secuencial(df_local, nombre_tabla)
            
        if "fecha" in df_local.columns:
            try:
                df_local = df_local.sort_values("fecha", ascending=False)
            except Exception:
                pass
        opciones = []
        mapa = {}
        for _, row in df_local.iterrows():
            row_id = valor_simple(row.get("Código") or row.get("id") or row.get("identificación"))
            etiqueta_partes = [str(row_id)]
            for campo in ["nombre", "producto", "cliente_nombre", "proveedor", "concepto", "usuario", "metodo_pago", "metodo", "fecha", "total", "monto"]:
                if campo in row.index and limpiar_texto(row.get(campo)):
                    etiqueta_partes.append(limpiar_texto(row.get(campo)))
                    if len(etiqueta_partes) >= 4:
                        break
            etiqueta = " | ".join(etiqueta_partes)
            opciones.append(etiqueta)
            mapa[etiqueta] = row
        if not opciones:
            st.info("No hay filas para gestionar.")
            return
        elegido = st.selectbox("Selecciona un registro", opciones, key=f"crud_sel_{nombre_tabla}")
        fila = mapa[elegido]
        fila_id = valor_simple(fila.get("id") or fila.get("identificación"))

        editable_cols = [c for c in df_local.columns if c not in excluir]
        nuevos_datos = {}
        cols = st.columns(2)
        campos_numericos_forzados = {
            "sueldo", "dia_pago_1", "dia_pago_2", "monto", "cantidad", "costo", "precio",
            "total", "subtotal", "descuento", "recargo", "limite_credito", "balance_pendiente",
            "impuesto", "costo_unitario", "precio_unitario", "valor", "existencia_sistema",
            "existencia_fisica", "diferencia"
        }
        for i, col in enumerate(editable_cols):
            valor = valor_simple(fila.get(col))
            cont = cols[i % 2]
            with cont:
                if isinstance(valor, (bool,)) or str(valor).lower() in ["true", "false"]:
                    nuevos_datos[col] = st.checkbox(col, value=bool(valor), disabled=not puede_editar, key=f"crud_{nombre_tabla}_{col}_{fila_id}")
                else:
                    num = limpiar_numero(valor)
                    es_numerico = (
                        (num is not None and col not in ["telefono", "rnc", "cedula_rnc", "codigo", "ncf"])
                        or col in campos_numericos_forzados
                    )
                    if es_numerico:
                        valor_num = float(num) if num is not None else 0.0
                        nuevos_datos[col] = st.number_input(
                            col,
                            value=valor_num,
                            step=1.0,
                            disabled=not puede_editar,
                            key=f"crud_{nombre_tabla}_{col}_{fila_id}"
                        )
                    else:
                        if "fecha" in col.lower():
                            fecha_val = pd.to_datetime(valor, errors="coerce")
                            if pd.isna(fecha_val):
                                nuevos_datos[col] = st.text_input(col, value=limpiar_texto(valor), disabled=not puede_editar, key=f"crud_{nombre_tabla}_{col}_{fila_id}")
                            else:
                                nuevos_datos[col] = str(st.date_input(col, value=fecha_val.date(), disabled=not puede_editar, key=f"crud_{nombre_tabla}_{col}_{fila_id}"))
                        elif len(limpiar_texto(valor)) > 60:
                            nuevos_datos[col] = st.text_area(col, value=limpiar_texto(valor), disabled=not puede_editar, key=f"crud_{nombre_tabla}_{col}_{fila_id}")
                        else:
                            nuevos_datos[col] = st.text_input(col, value=limpiar_texto(valor), disabled=not puede_editar, key=f"crud_{nombre_tabla}_{col}_{fila_id}")

        if nombre_tabla == "productos":
            st.markdown("---")
            st.subheader("🖼️ Imagen del Producto")
            
            img_actual = fila.get("imagen_url")
            if img_actual and str(img_actual).strip():
                st.image(img_actual, width=150, caption="Imagen actual")
                if puede_editar and st.button("🗑️ Quitar Imagen", key=f"btn_remove_img_{fila_id}"):
                    actualizar("productos", fila_id, {"imagen_url": None})
                    st.success("Imagen quitada correctamente.")
                    st.rerun()
            else:
                st.info("Este producto no tiene imagen asignada.")
                
            if puede_editar:
                img_file = st.file_uploader("Subir foto desde galería o cámara:", type=["png", "jpg", "jpeg", "webp"], key=f"uploader_prod_img_{fila_id}")
                if img_file is not None:
                    if st.button("💾 Guardar Foto Subida", key=f"btn_save_uploaded_img_{fila_id}"):
                        webp_b64 = optimizar_y_codificar_imagen(img_file.getvalue(), is_url=False)
                        if webp_b64:
                            actualizar("productos", fila_id, {"imagen_url": webp_b64})
                            st.success("¡Foto guardada y optimizada con éxito!")
                            st.rerun()
                
                prod_nombre = str(fila.get("nombre") or "")
                if st.button("🔍 Sugerir Imagen Inteligente (IA)", key=f"btn_suggest_img_{fila_id}"):
                    sugerencias = obtener_sugerencia_imagen_wiki(prod_nombre)
                    if not sugerencias:
                        st.warning("⚠️ No se encontraron imágenes sugeridas para este producto en la web.")
                    else:
                        st.session_state[f"sugerencias_imgs_{fila_id}"] = sugerencias
                
                sug_state_key = f"sugerencias_imgs_{fila_id}"
                if sug_state_key in st.session_state:
                    st.write("**Sugerencias encontradas (haz clic en una para guardarla):**")
                    sug_cols = st.columns(len(st.session_state[sug_state_key]))
                    for s_idx, sug in enumerate(st.session_state[sug_state_key]):
                        with sug_cols[s_idx]:
                            st.image(sug["url"], use_container_width=True)
                            if st.button(f"Seleccionar {s_idx+1}", key=f"btn_select_sug_{s_idx}_{fila_id}"):
                                with st.spinner("Descargando y optimizando..."):
                                    webp_b64 = optimizar_y_codificar_imagen(sug["url"], is_url=True)
                                    if webp_b64:
                                        actualizar("productos", fila_id, {"imagen_url": webp_b64})
                                        st.success("¡Imagen inteligente guardada!")
                                        del st.session_state[sug_state_key]
                                        st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            if puede_editar:
                if st.button("💾 Guardar datos generales", key=f"crud_save_{nombre_tabla}_{fila_id}"):
                    if nombre_tabla == "productos":
                        valido, msg_err = validar_unicidad_producto(
                            nuevos_datos.get("nombre", ""),
                            nuevos_datos.get("codigo", ""),
                            ignorar_producto_id=fila_id
                        )
                        if not valido:
                            st.error(msg_err)
                            st.stop()
                    if nombre_tabla == "compras":
                        p_id = fila.get("producto_id")
                        cant_antigua = float(fila.get("cantidad") or 0.0)
                        cant_nueva = float(nuevos_datos.get("cantidad") or 0.0)
                        dif_cant = cant_nueva - cant_antigua
                        
                        if dif_cant != 0:
                            fila_prod = refrescar_producto_por_id(p_id) if p_id else get_producto_por_nombre(fila.get("producto"))
                            if fila_prod is not None:
                                stock_real = obtener_existencia_producto(fila_prod)
                                nuevo_stock = max(stock_real + dif_cant, 0.0)
                                actualizar_stock_producto(fila_prod["nombre"], nuevo_stock)
                                
                                registrar_movimiento_inventario(
                                    fila_prod["id"],
                                    fila_prod["nombre"],
                                    "ajuste_compra",
                                    "compras",
                                    fila_id,
                                    dif_cant,
                                    float(nuevos_datos.get("costo_unitario") or 0.0),
                                    f"Ajuste por edición de compra. Diferencia: {dif_cant:+.2f} uds."
                                )
                                costo_nuevo = float(nuevos_datos.get("costo_unitario") or 0.0)
                                if costo_nuevo > 0:
                                    actualizar("productos", fila_prod["id"], {"costo": costo_nuevo})
                    
                    if actualizar(nombre_tabla, fila_id, nuevos_datos):
                        st.success("Registro actualizado.")
                        st.rerun()
            else:
                st.warning("No tienes permisos de edición en esta tabla.")
        with c2:
            if puede_eliminar:
                if st.button("🗑️ Eliminar registro", key=f"crud_delete_{nombre_tabla}_{fila_id}"):
                    if nombre_tabla == "compras":
                        p_id = fila.get("producto_id")
                        cant_comprada = float(fila.get("cantidad") or 0.0)
                        fila_prod = refrescar_producto_por_id(p_id) if p_id else get_producto_por_nombre(fila.get("producto"))
                        if fila_prod is not None:
                            stock_real = obtener_existencia_producto(fila_prod)
                            nuevo_stock = max(stock_real - cant_comprada, 0.0)
                            actualizar_stock_producto(fila_prod["nombre"], nuevo_stock)
                            
                            registrar_movimiento_inventario(
                                fila_prod["id"],
                                fila_prod["nombre"],
                                "reversa_compra",
                                "compras",
                                fila_id,
                                -cant_comprada,
                                float(fila.get("costo_unitario") or 0.0),
                                f"Reversa por eliminación de compra de {cant_comprada} uds."
                            )
                    if eliminar(nombre_tabla, fila_id):
                        st.success("Registro eliminado.")
                        st.rerun()
            else:
                st.warning("No tienes permisos de eliminación en esta tabla.")






# =========================================================
# UTILIDADES
# =========================================================
def ahora_str() -> str:
    return date.today().isoformat()


def agregar_columna_codigo_secuencial(df: pd.DataFrame, nombre_tabla: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
        
    df = df.copy()
    PREFIJOS = {
        "productos": "PO",
        "compras": "CP",
        "ventas": "VT",
        "clientes": "CL",
        "proveedores": "PR",
        "empleados": "EM",
        "gastos": "GS",
        "adelantos_empleados": "AE",
        "perdidas": "PE",
        "ajustes_inventario": "AI",
        "conteo_inventario": "CI",
        "cuentas_por_cobrar": "CC",
        "caja": "CJ",
        "movimientos_caja": "MC",
        "cotizaciones": "CT",
        "bancos": "BN"
    }
    prefijo = PREFIJOS.get(nombre_tabla)
    if not prefijo:
        return df

    # Evitar duplicados
    if "Código" in df.columns:
        return df

    sort_cols = []
    for c in ["fecha", "created_at", "fecha_apertura", "id", "identificación"]:
        if c in df.columns:
            sort_cols.append(c)
            
    indices = {}
    if sort_cols:
        try:
            df_sorted = df.sort_values(by=sort_cols, ascending=True)
            col_id = "id" if "id" in df.columns else "identificación"
            for idx, row_id in enumerate(df_sorted[col_id].tolist()):
                indices[str(row_id)] = idx + 1
        except Exception:
            pass

    codigos = []
    col_id = "id" if "id" in df.columns else "identificación" if "identificación" in df.columns else None
    
    for _, row in df.iterrows():
        row_id = str(row.get(col_id)) if col_id and row.get(col_id) is not None else ""
        
        # Intentar extraer de campos existentes
        codigo_existente = None
        if nombre_tabla == "productos" and "codigo" in row.index:
            codigo_existente = row.get("codigo")
        elif nombre_tabla == "compras" and "numero" in row.index:
            codigo_existente = row.get("numero")
        elif nombre_tabla == "ventas" and "numero_factura" in row.index:
            codigo_existente = row.get("numero_factura")
            
        if codigo_existente and str(codigo_existente).strip():
            c_str = str(codigo_existente).strip().upper()
            if c_str.startswith(prefijo):
                codigos.append(c_str)
            else:
                codigos.append(f"{prefijo}{c_str}")
        else:
            try:
                if row_id.isdigit():
                    codigos.append(f"{prefijo}{int(row_id):03d}")
                else:
                    idx_num = indices.get(row_id)
                    if idx_num is not None:
                        codigos.append(f"{prefijo}{idx_num:03d}")
                    else:
                        codigos.append(f"{prefijo}000")
            except Exception:
                codigos.append(f"{prefijo}000")
                
    df.insert(0, "Código", codigos)
    return df


def generar_codigo_secuencial(nombre_tabla: str) -> str:
    PREFIJOS = {
        "productos": "PO",
        "compras": "CP",
        "ventas": "VT",
        "clientes": "CL",
        "proveedores": "PR",
        "empleados": "EM",
        "gastos": "GS",
        "adelantos_empleados": "AE",
        "perdidas": "PE",
        "ajustes_inventario": "AI",
        "conteo_inventario": "CI",
        "cuentas_por_cobrar": "CC",
        "caja": "CJ",
        "movimientos_caja": "MC",
        "cotizaciones": "CT",
        "bancos": "BN"
    }
    prefijo = PREFIJOS.get(nombre_tabla, "XX")
    
    try:
        df = leer_tabla(nombre_tabla)
    except Exception:
        df = DATA.get(nombre_tabla, pd.DataFrame()).copy()

    if df.empty:
        return f"{prefijo}001"

    if nombre_tabla == "productos" and "codigo" in df.columns:
        max_num = 0
        for val in df["codigo"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("PO"):
                num_part = txt.replace("PO", "")
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"PO{(max_num + 1):03d}"

    if nombre_tabla == "compras" and "numero" in df.columns:
        max_num = 0
        for val in df["numero"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("CP"):
                num_part = txt.replace("CP", "")
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"CP{(max_num + 1):03d}"

    if nombre_tabla == "ventas" and "numero_factura" in df.columns:
        max_num = 0
        for val in df["numero_factura"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("VT"):
                num_part = txt.replace("VT", "")
                if num_part.isdigit():
                    max_num = max(max_num, int(num_part))
        return f"VT{(max_num + 1):03d}"

    col_id = "id" if "id" in df.columns else "identificación" if "identificación" in df.columns else None
    if col_id:
        ids = df[col_id].dropna().tolist()
        numeric_ids = []
        for x in ids:
            try:
                numeric_ids.append(int(x))
            except Exception:
                pass
        if numeric_ids:
            return f"{prefijo}{(max(numeric_ids) + 1):03d}"
        
    return f"{prefijo}{(len(df) + 1):03d}"


def generar_codigo_producto() -> str:
    return generar_codigo_secuencial("productos")


def obtener_historial_inventario_completo() -> pd.DataFrame:
    try:
        prods = leer_tabla("productos")
    except Exception:
        prods = DATA.get("productos", pd.DataFrame()).copy()

    name_to_code = {}
    if not prods.empty:
        for _, r in prods.iterrows():
            name = str(r.get("nombre") or "").lower().strip()
            code = r.get("Código") or r.get("codigo") or ""
            if name:
                name_to_code[name] = str(code).strip()

    try:
        movs = leer_tabla("movimientos")
    except Exception:
        movs = pd.DataFrame()
        
    try:
        perd = leer_tabla("perdidas")
    except Exception:
        perd = pd.DataFrame()
        
    try:
        ajustes = leer_tabla("ajustes_inventario")
    except Exception:
        ajustes = pd.DataFrame()
        
    try:
        conteos = leer_tabla("conteo_inventario")
    except Exception:
        conteos = pd.DataFrame()

    hist_rows = []

    # 1. Compras y Ventas
    if not movs.empty:
        for _, row in movs.iterrows():
            tipo = row.get("tipo_movimiento")
            tipo_friendly = "Compra" if tipo == "entrada_compra" else "Venta (POS)" if tipo == "salida_venta" else "Reversa Venta" if tipo == "reversa_venta" else str(tipo)
            p_name = row.get("producto") or ""
            p_code = name_to_code.get(p_name.lower().strip(), "")
            cant = float(row.get("cantidad") or 0.0)
            costo = float(row.get("costo_unitario") or 0.0)
            
            hist_rows.append({
                "Fecha": row.get("fecha"),
                "Código": p_code,
                "Producto": p_name,
                "Movimiento": tipo_friendly,
                "Cantidad": cant,
                "Costo Unitario": costo,
                "Total (Costo)": cant * costo,
                "Usuario": row.get("usuario") or "",
                "Observación": row.get("observacion") or ""
            })

    # 2. Pérdidas
    if not perd.empty:
        for _, row in perd.iterrows():
            if not bool(row.get("anulado", False)):
                p_name = row.get("producto") or ""
                p_code = name_to_code.get(p_name.lower().strip(), "")
                cant = -abs(float(row.get("cantidad") or 0.0))
                costo = float(row.get("costo_unitario") or 0.0)
                
                hist_rows.append({
                    "Fecha": row.get("fecha"),
                    "Código": p_code,
                    "Producto": p_name,
                    "Movimiento": f"Pérdida ({row.get('tipo_perdida') or 'general'})",
                    "Cantidad": cant,
                    "Costo Unitario": costo,
                    "Total (Costo)": cant * costo,
                    "Usuario": row.get("usuario") or "",
                    "Observación": row.get("observacion") or ""
                })

    # 3. Ajustes
    if not ajustes.empty:
        for _, row in ajustes.iterrows():
            qty = float(row.get("cantidad") or 0.0)
            p_origen = row.get("producto_origen") or ""
            p_destino = row.get("producto_destino") or ""
            tipo_aj = row.get("tipo_ajuste") or "Ajuste"
            
            if p_origen:
                p_code = name_to_code.get(p_origen.lower().strip(), "")
                costo = float(row.get("costo_origen") or 0.0)
                hist_rows.append({
                    "Fecha": row.get("fecha"),
                    "Código": p_code,
                    "Producto": p_origen,
                    "Movimiento": f"Ajuste ({tipo_aj}) - Origen",
                    "Cantidad": qty,
                    "Costo Unitario": costo,
                    "Total (Costo)": qty * costo,
                    "Usuario": row.get("usuario") or "",
                    "Observación": f"Traspaso a {p_destino}. " + str(row.get("observacion") or "")
                })
            if p_destino:
                p_code = name_to_code.get(p_destino.lower().strip(), "")
                costo = float(row.get("costo_destino") or 0.0)
                hist_rows.append({
                    "Fecha": row.get("fecha"),
                    "Código": p_code,
                    "Producto": p_destino,
                    "Movimiento": f"Ajuste ({tipo_aj}) - Destino",
                    "Cantidad": -qty,
                    "Costo Unitario": costo,
                    "Total (Costo)": -qty * costo,
                    "Usuario": row.get("usuario") or "",
                    "Observación": f"Traspaso desde {p_origen}. " + str(row.get("observacion") or "")
                })

    # 4. Conteos
    if not conteos.empty:
        for _, row in conteos.iterrows():
            if bool(row.get("aplicado", False)):
                p_name = row.get("producto") or ""
                p_code = name_to_code.get(p_name.lower().strip(), "")
                dif = float(row.get("diferencia") or 0.0)
                
                hist_rows.append({
                    "Fecha": row.get("fecha_aplicacion") or row.get("fecha"),
                    "Código": p_code,
                    "Producto": p_name,
                    "Movimiento": "Conteo Aprobado",
                    "Cantidad": dif,
                    "Costo Unitario": 0.0,
                    "Total (Costo)": 0.0,
                    "Usuario": row.get("usuario") or "",
                    "Observación": f"Conteo físico. " + str(row.get("observacion") or "")
                })

    if not hist_rows:
        return pd.DataFrame()

    df_hist = pd.DataFrame(hist_rows)
    df_hist["Fecha"] = pd.to_datetime(df_hist["Fecha"], errors="coerce")
    df_hist = df_hist.sort_values(by="Fecha", ascending=False).reset_index(drop=True)
    return df_hist



def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    columnas = []
    for c in df.columns:
        c2 = normalizar_texto(c).replace(" ", "_")
        columnas.append(c2)
    df.columns = columnas
    df = df.loc[:, ~df.columns.str.contains("^unnamed", case=False)]
    return df



def limpiar_numero(valor: Any) -> float | None:
    if pd.isna(valor) or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    txt = str(valor).strip()
    txt = txt.replace("RD$", "").replace("rd$", "").replace("$", "")
    txt = txt.replace(",", "")
    txt = txt.replace(" ", "")
    try:
        return float(txt)
    except Exception:
        return None



def parsear_fecha(valor: Any) -> str | None:
    if pd.isna(valor) or valor == "":
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.date().isoformat()
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()

    txt = str(valor).strip()
    formatos = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%y",
        "%d-%m-%y",
    ]
    for fmt in formatos:
        try:
            return datetime.strptime(txt, fmt).date().isoformat()
        except Exception:
            pass

    try:
        fecha = pd.to_datetime(txt, dayfirst=True, errors="coerce")
        if pd.isna(fecha):
            return None
        return fecha.date().isoformat()
    except Exception:
        return None






def limpiar_codigo_import(valor: Any) -> str:
    """Limpia códigos/barcodes para evitar que Excel los deje como 74621774.0."""
    if pd.isna(valor) or valor == "":
        return ""
    txt = str(valor).strip()
    if txt.lower() in ["nan", "none", "null"]:
        return ""
    if txt.endswith(".0"):
        txt = txt[:-2]
    return txt.strip()


def _clave_columna(col: Any) -> str:
    return normalizar_texto(str(col)).replace("_", " ").replace("-", " ").strip()


def _alias_match(col_norm: str, aliases: list[str]) -> bool:
    col_norm = _clave_columna(col_norm)
    aliases_norm = [_clave_columna(a) for a in aliases]
    if col_norm in aliases_norm:
        return True
    # lectura flexible: "precio de venta", "precio venta normal", "stock actual", etc.
    for a in aliases_norm:
        if a and (col_norm == a or col_norm.startswith(a + " ") or a in col_norm):
            return True
    return False


def mapear_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mapea columnas por NOMBRE, no por posición.
    Acepta diferentes encabezados: producto/nombre/descripción, stock/cantidad/existencia,
    costo/precio compra, precio venta/precio normal, precio especial, activo, categoría, etc.
    """
    mapa = {
        "id_externo": ["id", "uuid", "id producto", "id_producto"],
        "nombre": ["producto", "nombre", "nombre producto", "item", "articulo", "artículo", "descripcion", "descripción", "descripcion producto"],
        "categoria": ["categoria", "categoría", "category", "departamento", "familia", "grupo"],
        "codigo": ["codigo", "código", "codigo barra", "codigo de barra", "código de barra", "codigo barras", "barcode", "bar code", "ean", "upc", "sku", "referencia"],
        "costo": ["costo", "cost", "precio compra", "precio_compra", "costo unitario", "costo_unitario", "precio costo", "ultimo costo", "último costo"],
        "precio": ["precio", "precio venta", "precio_venta", "precio de venta", "venta", "precio normal", "precio publico", "precio público", "pvp"],
        "precio_descuento": ["precio descuento", "precio_descuento", "precio oferta", "oferta", "precio minimo", "precio mínimo", "precio 2"],
        "precio_especial": ["precio especial", "precio_especial", "especial", "precio 3", "precio mayorista", "precio mayoreo"],
        "cantidad": ["cantidad", "stock", "stock actual", "existencia", "existencias", "existencia sistema", "existencia_sistema", "inventario", "inventario actual", "qty", "quantity"],
        "fecha": ["fecha", "date", "fecha agregado", "fecha agregada", "fecha creacion", "fecha creación", "created_at", "creado"],
        "activo": ["activo", "estado", "estatus", "status", "habilitado", "disponible"],
        "usa_inventario": ["usa inventario", "usa_inventario", "inventariable", "control inventario", "control_inventario"],
        "proveedor": ["proveedor", "suplidor", "supplier"],
        "descripcion": ["detalle", "observacion", "observación", "nota", "notas"],
        "numero": ["numero", "número", "factura", "documento", "no factura"],
        "metodo": ["metodo", "método", "metodo pago", "metodo_pago", "forma pago", "forma_pago"],
    }
    ren = {}
    usados = set()
    for col in df.columns:
        norm = _clave_columna(col)
        for destino, aliases in mapa.items():
            if destino in usados:
                continue
            if _alias_match(norm, aliases):
                ren[col] = destino
                usados.add(destino)
                break
    return df.rename(columns=ren)


def detectar_formato_productos_sin_encabezado(df: pd.DataFrame) -> pd.DataFrame:
    """
    Respaldo para exportaciones sin encabezado como el archivo viejo:
    ID | NOMBRE | COSTO | PRECIO | STOCK | ... | STOCK_2 | CODIGO | ACTIVO...
    Solo se usa si después del mapeo no aparece nombre/cantidad.
    """
    out = df.copy()
    # Si ya trae encabezados reconocidos, no tocar.
    if "nombre" in out.columns and ("cantidad" in out.columns or "stock" in out.columns):
        return out

    # Convertir columnas a posiciones si no reconoció encabezados.
    if out.shape[1] >= 10:
        temp = pd.DataFrame()
        temp["id_externo"] = out.iloc[:, 0]
        temp["nombre"] = out.iloc[:, 1]
        temp["costo"] = out.iloc[:, 2]
        temp["precio"] = out.iloc[:, 3]
        # En tu exportación hay dos columnas que pueden reflejar stock; tomamos la mayor para no bajar inventario por error.
        stock1 = pd.to_numeric(out.iloc[:, 4], errors="coerce").fillna(0)
        stock2 = pd.to_numeric(out.iloc[:, 8], errors="coerce").fillna(0) if out.shape[1] > 8 else stock1
        temp["cantidad"] = stock1.where(stock1.abs() >= stock2.abs(), stock2)
        temp["fecha"] = out.iloc[:, 6] if out.shape[1] > 6 else ""
        temp["codigo"] = out.iloc[:, 9].apply(limpiar_codigo_import) if out.shape[1] > 9 else ""
        temp["activo"] = out.iloc[:, 10] if out.shape[1] > 10 else True
        temp["usa_inventario"] = out.iloc[:, 11] if out.shape[1] > 11 else True
        return temp
    return out





def payload_producto_importado(row: dict) -> dict:
    """Arma el payload limpio para productos/inventario desde preparar_import_productos."""
    nombre = limpiar_texto(row.get("nombre"))
    codigo = limpiar_texto(row.get("codigo"))
    categoria = limpiar_texto(row.get("categoria"))
    stock = float(limpiar_numero(row.get("stock")) or 0)
    costo = float(limpiar_numero(row.get("costo")) or 0)
    precio_venta = float(limpiar_numero(row.get("precio_venta")) or 0)
    precio_especial = float(limpiar_numero(row.get("precio_especial")) or 0)
    activo = bool(row.get("activo", True))

    return {
        "nombre": nombre,
        "codigo": codigo,
        "codigo_barra": codigo,
        "categoria": categoria,
        "stock": stock,
        "cantidad": stock,
        "existencia": stock,
        "costo": costo,
        "costo_unitario": costo,
        "costo_promedio": costo,
        "precio": precio_venta,
        "precio_venta": precio_venta,
        "precio_especial": precio_especial,
        "activo": activo,
        "usar_en_inventario": True,
        "fecha_agregado": str(date.today()) if "date" in globals() else None,
    }


def preparar_import_productos(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Importador PRO de productos.
    Lee por encabezados normalizados, no por posición.
    Devuelve columnas limpias:
    codigo, nombre, categoria, stock, costo, precio_venta, precio_especial, activo,
    total_costo_inventario, total_valor_venta, ganancia_potencial.
    """
    if df_raw is None or df_raw.empty:
        return pd.DataFrame()

    df = df_raw.copy()
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]

    def _norm(txt):
        t = normalizar_texto(txt)
        t = t.replace(".", " ").replace("_", " ").replace("-", " ").replace("/", " ")
        t = " ".join(t.split())
        return t

    def _compact(txt):
        return _norm(txt).replace(" ", "")

    def _num_safe(x):
        try:
            v = limpiar_numero(x)
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    def _codigo_safe(x):
        try:
            if pd.isna(x):
                return ""
        except Exception:
            pass
        # Si es número (float/int), convertir a entero primero para evitar
        # notación científica de Excel (ej: 7.70235e+12 → "7702350000000")
        if isinstance(x, float):
            try:
                return str(int(x))
            except (ValueError, OverflowError):
                pass
        if isinstance(x, int):
            return str(x)
        txt = str(x).strip()
        # Detectar notación científica en texto (ej: "7.70235e+12")
        if 'e' in txt.lower() and '+' in txt:
            try:
                return str(int(float(txt)))
            except (ValueError, OverflowError):
                pass
        if txt.endswith(".0"):
            txt = txt[:-2]
        return txt

    def _activo_safe(x):
        t = _norm(x)
        if t in ["false", "falso", "0", "no", "inactivo", "inactiva"]:
            return False
        return True

    # Detectar y eliminar fila basura si el archivo trae encabezado repetido como primera fila
    first_row_text = " ".join([str(v) for v in df.iloc[0].tolist()]) if len(df) else ""
    if "Nombre" in first_row_text and ("Stock" in first_row_text or "Costo" in first_row_text):
        # Si pandas leyó columnas incorrectas y la primera fila realmente era encabezado
        df.columns = [str(v).strip() for v in df.iloc[0].tolist()]
        df = df.iloc[1:].reset_index(drop=True)
        df = df.loc[:, ~pd.Index(df.columns).duplicated()]

    col_norm = {c: _norm(c) for c in df.columns}
    col_comp = {c: _compact(c) for c in df.columns}

    def pick_col(candidates, must_not=None):
        must_not = must_not or []
        cand_norm = [_norm(x) for x in candidates]
        cand_comp = [_compact(x) for x in candidates]
        bad_norm = [_norm(x) for x in must_not]
        bad_comp = [_compact(x) for x in must_not]

        # exact compact
        for c in df.columns:
            cc = col_comp[c]
            if cc in cand_comp and all(b not in cc for b in bad_comp):
                return c

        # exact norm
        for c in df.columns:
            cn = col_norm[c]
            if cn in cand_norm and all(b not in cn for b in bad_norm):
                return c

        # contains compact
        for c in df.columns:
            cc = col_comp[c]
            if all(b not in cc for b in bad_comp):
                for cand in cand_comp:
                    if cand and (cand in cc or cc in cand):
                        return c

        return None

    col_codigo = pick_col([
        "Codigo", "Código", "Codigo Barra", "Código Barra", "Barcode", "Bar Code", "SKU", "Referencia"
    ])
    col_nombre = pick_col([
        "Nombre", "Producto", "Descripcion", "Descripción", "Nombre Producto", "Producto Nombre"
    ])
    col_categoria = pick_col([
        "Categoria", "Categoría", "Familia", "Grupo", "Departamento"
    ])
    col_stock = pick_col([
        "Stock", "Cantidad", "Existencia", "Inventario", "Inventario Actual", "Disponible", "Cantidad Disponible"
    ], must_not=["precio", "costo", "total"])
    col_costo = pick_col([
        "Costo", "Costo Unitario", "Precio Compra", "Precio Costo", "Costo Promedio", "Costo Prom."
    ], must_not=["total"])
    col_precio = pick_col([
        "PrecioVenta", "Precio Venta", "Precio V", "Precio V.", "Precio de Venta",
        "Precio", "Precio Normal", "Precio Publico", "Precio Público", "PVP", "Venta"
    ], must_not=["especial", "descuento", "oferta", "costo", "compra", "total"])
    col_especial = pick_col([
        "Precio Especial", "Precio Descuento", "Precio Oferta", "Oferta", "Especial", "Descuento"
    ])

    # Si no encuentra encabezados, intenta formato anterior por posición:
    # Codigo | Nombre | Categoria | Stock | Costo | PrecioVenta
    out = pd.DataFrame(index=df.index)
    if col_nombre is None and df.shape[1] >= 6:
        out["codigo"] = df.iloc[:, 0]
        out["nombre"] = df.iloc[:, 1]
        out["categoria"] = df.iloc[:, 2]
        out["stock"] = df.iloc[:, 3]
        out["costo"] = df.iloc[:, 4]
        out["precio_venta"] = df.iloc[:, 5]
        out["precio_especial"] = 0
        out["activo"] = True
    else:
        out["codigo"] = df[col_codigo] if col_codigo in df.columns else ""
        out["nombre"] = df[col_nombre] if col_nombre in df.columns else ""
        out["categoria"] = df[col_categoria] if col_categoria in df.columns else ""

        # stock/costo/precio por nombre
        out["stock"] = df[col_stock] if col_stock in df.columns else 0
        out["costo"] = df[col_costo] if col_costo in df.columns else 0
        out["precio_venta"] = df[col_precio] if col_precio in df.columns else 0
        out["precio_especial"] = df[col_especial] if col_especial in df.columns else 0

        col_activo = pick_col(["Activo", "Estado", "Estatus"])
        out["activo"] = df[col_activo] if col_activo in df.columns else True

    # Limpieza final
    out = out.loc[:, ~pd.Index(out.columns).duplicated()]

    for c in ["stock", "costo", "precio_venta", "precio_especial"]:
        if c not in out.columns:
            out[c] = 0.0
        serie = out[c].iloc[:, 0] if isinstance(out[c], pd.DataFrame) else out[c]
        out[c] = serie.apply(_num_safe)

    out["codigo"] = out["codigo"].apply(_codigo_safe) if "codigo" in out.columns else ""
    out["nombre"] = out["nombre"].fillna("").astype(str).str.strip()
    out["categoria"] = out["categoria"].fillna("").astype(str).str.strip() if "categoria" in out.columns else ""
    out["activo"] = out["activo"].apply(_activo_safe) if "activo" in out.columns else True

    # Si precio_venta quedó en 0 pero precio_especial tiene valor, usar precio_especial como precio venta
    out.loc[(out["precio_venta"] <= 0) & (out["precio_especial"] > 0), "precio_venta"] = out["precio_especial"]

    # Evitar filas sin nombre
    out = out[out["nombre"].astype(str).str.strip() != ""].copy()

    # Validaciones visibles
    out["total_costo_inventario"] = out["stock"] * out["costo"]
    out["total_valor_venta"] = out["stock"] * out["precio_venta"]
    out["ganancia_potencial"] = out["total_valor_venta"] - out["total_costo_inventario"]

    return out.reset_index(drop=True)

def get_producto_por_codigo(codigo: str):
    codigo_n = normalizar_texto(codigo)
    if not codigo_n:
        return None
    df = DATA.get("productos", pd.DataFrame()).copy()
    if df.empty or "codigo" not in df.columns:
        return None
    tmp = df.copy()
    tmp["_c"] = tmp["codigo"].astype(str).apply(normalizar_texto)
    match = tmp[tmp["_c"] == codigo_n]
    if match.empty:
        return None
    return match.iloc[0]



def obtener_tenant_actual() -> str:
    usuario_data = st.session_state.get("usuario_data")
    if not usuario_data:
        return "global"
    username = str(usuario_data.get("usuario") or "").lower()
    rol = str(usuario_data.get("rol") or "").lower()
    email_val = str(usuario_data.get("email") or "").lower()
    es_superadmin = (rol == "superadmin" or (username in ["admin", "nelly"] and email_val == "global"))
    if es_superadmin:
        tenant_sel = st.session_state.get("superadmin_tenant_seleccionado")
        if tenant_sel:
            return tenant_sel
        return "global"
    parent = usuario_data.get("email") or ""
    if parent.strip() and "@" not in parent:
        return parent.strip().lower()
    return username

def obtener_configuracion() -> dict:
    tenant = obtener_tenant_actual()
    return _obtener_configuracion_interna(tenant)

@st.cache_data(ttl=60, show_spinner=False)
def _obtener_configuracion_interna(tenant: str) -> dict:
    try:
        if tenant != "global":
            resp = supabase.table("configuracion_sistema").select("*").eq("propietario", tenant).execute()
            filas = resp.data or []
            if filas:
                return filas[0]
            else:
                # Clonamos la configuración global con ID 1 para crear la de este nuevo tenant
                default_cfg = supabase.table("configuracion_sistema").select("*").eq("id", 1).execute().data
                if default_cfg:
                    new_cfg = default_cfg[0].copy()
                    new_cfg.pop("id", None)
                    new_cfg["propietario"] = tenant
                    new_cfg["negocio_nombre"] = f"Empresa {tenant.capitalize()}"
                    insert_resp = supabase.table("configuracion_sistema").insert(new_cfg).execute()
                    if insert_resp.data:
                        return insert_resp.data[0]
                        
        # Carga la configuración global por defecto (id=1)
        resp = supabase.table("configuracion_sistema").select("*").eq("id", 1).execute()
        filas = resp.data or []
        return filas[0] if filas else {}
    except Exception:
        # Fallback seguro
        try:
            resp = supabase.table("configuracion_sistema").select("*").limit(1).execute()
            filas = resp.data or []
            return filas[0] if filas else {}
        except Exception:
            return {}



def logo_actual() -> str:
    cfg = obtener_configuracion()
    return str(cfg.get("logo_url") or "")



def construir_data_uri(file_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"



def guardar_logo_en_configuracion(file_bytes: bytes, mime: str) -> bool:
    cfg = obtener_configuracion()
    if not cfg:
        return False
    uri = construir_data_uri(file_bytes, mime)
    try:
        supabase.table("configuracion_sistema").update({"logo_url": uri}).eq("id", cfg["id"]).execute()
        registrar_auditoria("actualizar_logo", "configuracion_sistema", "Logo actualizado")
        return True
    except Exception as exc:
        st.error(f"No se pudo guardar el logo: {exc}")
        return False

# =========================================================
# FASE 5: INTEGRACIÓN DGII (NCF E ITBIS)
# ==========================================

def calcular_itbis(total_venta: float, precios_incluyen_itbis: bool) -> tuple[float, float]:
    """Calcula subtotal e itbis basándose en la configuración de la empresa usando precisión Decimal."""
    from decimal import Decimal, ROUND_HALF_UP
    try:
        total = Decimal(str(total_venta))
    except:
        total = Decimal('0.00')
    
    itbis_tasa = Decimal('0.18')
    divisor = Decimal('1.18')
    
    if precios_incluyen_itbis:
        subtotal = (total / divisor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        itbis = (total - subtotal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        subtotal = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        itbis = (total * itbis_tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
    return float(subtotal), float(itbis)

def consumir_ncf_siguiente(tipo_comprobante: str) -> str | None:
    """Consume y retorna el próximo NCF disponible para la empresa actual.
    Retorna None si no hay secuencia configurada o se agotaron."""
    tenant = obtener_tenant_actual()
    try:
        # Buscar secuencia activa
        resp = supabase.table("secuencia_ncf")\
            .select("*")\
            .eq("empresa_id", tenant)\
            .eq("tipo_comprobante", tipo_comprobante)\
            .eq("estado", "activo")\
            .execute()
        
        datos = resp.data or []
        if not datos:
            return None
        
        sec = datos[0]
        actual = int(sec["secuencia_actual"])
        maxima = int(sec["secuencia_maxima"])
        
        if actual > maxima:
            # Marcar agotada
            supabase.table("secuencia_ncf").update({"estado": "agotado"}).eq("id", sec["id"]).execute()
            return None
            
        # Formatear NCF (Prefijo + 8 o 10 dígitos, DGII usa 13 caracteres para comprobantes electrónicos E31/E32 y 11 para tradicionales B01/B02)
        prefijo = str(sec.get("tipo_comprobante", "B02"))
        if prefijo.upper().startswith("E"):
            numero_formateado = f"{actual:010d}"
        else:
            numero_formateado = f"{actual:08d}"
        ncf_generado = f"{prefijo}{numero_formateado}"
        
        # Aumentar la secuencia
        supabase.table("secuencia_ncf").update({"secuencia_actual": actual + 1}).eq("id", sec["id"]).execute()
        
        return ncf_generado
    except Exception as exc:
        print(f"Error generando NCF: {exc}")
        return None
# =========================================================
# CONTROL DE ACCESO GLOBAL Y TEMAS (WHITE-LABEL)
# =========================================================
TEMAS_CSS = {
    "A&M Minimalist (Fondo Claro)": """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: #ffffff !important;
            font-family: 'Inter', sans-serif !important;
            color: #0f172a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #f8fafc !important;
            border-right: 1px solid #cbd5e1 !important;
        }
        [data-testid="stSidebar"] * {
            color: #0f172a !important;
        }
        div[data-testid="stMetricValue"] {
            color: #2563eb !important;
            font-weight: 700 !important;
        }
        .stButton>button {
            background-color: #2563eb !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2) !important;
        }
        .stButton>button:hover {
            background-color: #1d4ed8 !important;
        }
        .stMetric {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
        }
    </style>
    """,
    "Bibe Ron Royal (Azul & Rojo)": """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: #f1f5f9 !important;
            font-family: 'Inter', sans-serif !important;
            color: #0f172a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #cbd5e1 !important;
        }
        [data-testid="stSidebar"] * {
            color: #0f172a !important;
        }
        div[data-testid="stMetricValue"] {
            color: #1e3a8a !important;
            font-weight: 700 !important;
        }
        .stButton>button {
            background-color: #e63946 !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
        }
        .stButton>button:hover {
            background-color: #c0392b !important;
        }
        .stMetric {
            background: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 12px !important;
        }
    </style>
    """,
    "Onyx Carbon (Dark Mode Premium)": """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: #f8fafc !important;
            font-family: 'Outfit', sans-serif !important;
            color: #0f172a !important;
        }
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b !important;
        }
        [data-testid="stSidebar"] * {
            color: #ffffff !important;
        }
        div[data-testid="stMetricValue"] {
            color: #0f172a !important;
            font-weight: 700 !important;
        }
        .stButton>button {
            background: #0f172a !important;
            color: #ffffff !important;
            font-weight: bold !important;
            border-radius: 10px !important;
            border: none !important;
        }
        .stMetric {
            background: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 16px !important;
        }
    </style>
    """,
    "Esmeralda Merchant (Verde & Pizarra)": """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: #f0fdf4 !important;
            font-family: 'Inter', sans-serif !important;
            color: #166534 !important;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #bbf7d0 !important;
        }
        [data-testid="stSidebar"] * {
            color: #166534 !important;
        }
        div[data-testid="stMetricValue"] {
            color: #166534 !important;
        }
        .stButton>button {
            background-color: #166534 !important;
            color: white !important;
            border-radius: 8px !important;
            border: none !important;
            font-weight: 600 !important;
        }
        .stButton>button:hover {
            background-color: #14532d !important;
        }
        .stMetric {
            background: #ffffff !important;
            border: 1px solid #bbf7d0 !important;
            border-radius: 12px !important;
        }
    </style>
    """,
    "Gold Velvet (Lujo & Oro)": """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
        html, body, [data-testid="stAppViewContainer"], .stApp {
            background-color: #fdfbf7 !important;
            font-family: 'Outfit', sans-serif !important;
            color: #854d0e !important;
        }
        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #fef08a !important;
        }
        [data-testid="stSidebar"] * {
            color: #854d0e !important;
        }
        div[data-testid="stMetricValue"] {
            color: #854d0e !important;
        }
        .stButton>button {
            background: #854d0e !important;
            color: white !important;
            font-weight: bold !important;
            border-radius: 12px !important;
            border: none !important;
        }
        .stMetric {
            background: #ffffff !important;
            border: 1px solid #fef08a !important;
            border-radius: 16px !important;
        }
    </style>
    """
}

def obtener_tema_guardado() -> str:
    cfg = obtener_configuracion()
    slogan = cfg.get("slogan") or ""
    if slogan.startswith("TEMA:"):
        partes = slogan.split("|", 1)
        tema = partes[0].replace("TEMA:", "").strip()
        if tema in TEMAS_CSS:
            return tema
    return "A&M Minimalist (Fondo Claro)"

def guardar_tema_en_db(tema_nombre: str):
    cfg = obtener_configuracion()
    if not cfg:
        return False
    slogan = cfg.get("slogan") or ""
    slogan_limpio = ""
    if slogan.startswith("TEMA:"):
        partes = slogan.split("|", 1)
        if len(partes) > 1:
            slogan_limpio = partes[1].strip()
    else:
        slogan_limpio = slogan.strip()
    
    nuevo_slogan = f"TEMA:{tema_nombre} | {slogan_limpio}"
    try:
        supabase.table("configuracion_sistema").update({"slogan": nuevo_slogan}).eq("id", cfg["id"]).execute()
        return True
    except Exception:
        return False

def login_simple() -> bool:
    usuario_data = st.session_state.get("usuario_data")
    if usuario_data:
        # Control de tiempo de inactividad de sesión (cierre automático tras 15 minutos)
        max_inactividad = 900
        ultimo_acceso = st.session_state.get("last_activity")
        ahora = datetime.now()
        if ultimo_acceso is not None:
            if (ahora - ultimo_acceso).total_seconds() > max_inactividad:
                st.session_state.pop("usuario_data", None)
                st.session_state.pop("last_activity", None)
                st.session_state.pop("ultimo_check_usuario", None)
                st.error("⚠️ Sesión cerrada automáticamente por inactividad.")
                st.rerun()
        st.session_state["last_activity"] = ahora

        # Revalidar sesión cada 60 segundos contra Supabase para detectar desactivaciones/cambios
        ultimo_check = st.session_state.get("ultimo_check_usuario")
        if ultimo_check is None or (ahora - ultimo_check).total_seconds() > 60.0:
            try:
                usr_id = usuario_data.get("id")
                if usr_id:
                    resp = supabase.table("usuarios").select("*").eq("id", str(usr_id)).execute()
                    fresh = resp.data[0] if resp.data else None
                    if not fresh or not fresh.get("activo", True):
                        st.session_state.pop("usuario_data", None)
                        st.session_state.pop("ultimo_check_usuario", None)
                        st.session_state.pop("last_activity", None)
                        st.error("⚠️ Su cuenta ha sido desactivada o eliminada.")
                        st.rerun()
                    if fresh.get("clave") != usuario_data.get("clave") or fresh.get("rol") != usuario_data.get("rol"):
                        st.session_state.pop("usuario_data", None)
                        st.session_state.pop("ultimo_check_usuario", None)
                        st.session_state.pop("last_activity", None)
                        st.error("⚠️ Sus credenciales o privilegios han cambiado. Inicie sesión de nuevo.")
                        st.rerun()
                    st.session_state["usuario_data"] = fresh
                st.session_state["ultimo_check_usuario"] = ahora
            except Exception:
                # Tolerar fallos de red temporales para continuidad operativa
                pass
        return True

    # Retrieve logo dynamically to ensure fresh updates are shown immediately
    logo_b64 = get_am_logo_b64()

    # Render a truly professional macOS-style executive login interface
    st.markdown(f"""
    <style>
        /* Full-screen sleek macOS-style light slate background */
        [data-testid="stAppViewContainer"], .stApp {{
            background-color: #f5f5f7 !important;
            background-image: 
                radial-gradient(at 0% 0%, #fafafa 0px, transparent 50%),
                radial-gradient(at 100% 0%, #eaeaea 0px, transparent 50%),
                radial-gradient(at 50% 100%, #f0f0f3 0px, transparent 50%) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            min-height: 100vh !important;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}

        /* Hide Streamlit default toolbars and headers */
        [data-testid="stHeader"] {{
            display: none !important;
        }}
        [data-testid="stSidebar"] {{
            display: none !important;
        }}
        [data-testid="stToolbar"] {{
            display: none !important;
        }}

        /* Bulletproof centering and sizing for the login card container */
        html body [data-testid="stAppViewContainer"] [data-testid="stAppViewBlockContainer"],
        html body [data-testid="stAppViewContainer"] .stMainBlockContainer,
        html body [data-testid="stAppViewContainer"] .main .block-container,
        div[data-testid="stAppViewBlockContainer"],
        div.stMainBlockContainer,
        .main .block-container {{
            max-width: 440px !important;
            width: 440px !important;
            min-width: 320px !important;
            padding: 3rem 2.5rem !important;
            background: #ffffff !important; /* Pure solid crisp white for ultimate executive quality */
            border-radius: 16px !important;
            border: 1px solid #d2d2d7 !important; /* Elegant light gray border */
            box-shadow: 
                0 20px 40px rgba(0, 0, 0, 0.05),
                0 1px 3px rgba(0, 0, 0, 0.02) !important;
            margin: 10vh auto !important;
            box-sizing: border-box !important;
            display: block !important;
        }}

        /* Ensure input wrapper doesn't stretch beyond card boundaries */
        div[data-testid="stTextInput"] {{
            width: 100% !important;
            max-width: 100% !important;
        }}

        /* macOS-style elegant input labels */
        div[data-testid="stTextInput"] label {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            color: #1d1d1f !important;
            margin-bottom: 8px !important;
            padding-left: 1px !important;
        }}

        /* macOS-style premium input elements */
        div[data-testid="stTextInput"] input {{
            border-radius: 8px !important;
            border: 1px solid #d2d2d7 !important;
            background: #ffffff !important;
            color: #1d1d1f !important;
            padding: 10px 12px !important;
            font-size: 14px !important;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif !important;
            box-shadow: none !important;
            transition: all 0.15s ease-in-out !important;
            width: 100% !important;
        }}

        div[data-testid="stTextInput"] input:focus {{
            border-color: #8e8e93 !important; /* Neutral premium gray focus ring */
            background: #ffffff !important;
            box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.05) !important;
            outline: none !important;
        }}

        div[data-testid="stTextInput"] div[data-testid="InputInstructions"] {{
            display: none !important;
        }}

        /* macOS-style Executive Solid Dark Button */
        div[data-testid="stButton"] button {{
            background: #1d1d1f !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 10px 20px !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
            transition: all 0.15s ease-in-out !important;
            width: 100% !important;
            height: 42px !important;
            margin-top: 1.2rem !important;
            cursor: pointer !important;
        }}

        div[data-testid="stButton"] button:hover {{
            background: #000000 !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.12) !important;
        }}

        div[data-testid="stButton"] button:active {{
            background: #2c2c2e !important;
        }}

        /* Header elements */
        .login-header {{
            text-align: center !important;
            margin-bottom: 2rem !important;
        }}
        .logo-container {{
            width: 72px !important;
            height: 72px !important;
            margin: 0 auto 1.2rem auto !important;
            background: #ffffff !important;
            border-radius: 16px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
            border: 1px solid #e5e5ea !important;
        }}
        .logo-img {{
            width: 50px !important;
            height: 50px !important;
            object-fit: contain !important;
            border-radius: 10px !important;
        }}
        .brand-title {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, sans-serif !important;
            font-size: 1.7rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.03em !important;
            color: #1d1d1f !important;
            margin-bottom: 0.25rem !important;
        }}
        .brand-subtitle {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif !important;
            font-size: 0.9rem !important;
            font-weight: 450 !important;
            color: #86868b !important;
            letter-spacing: -0.01em !important;
            margin-bottom: 0.5rem !important;
        }}
        .login-footer {{
            text-align: center !important;
            font-size: 11px !important;
            color: #86868b !important;
            font-weight: 400 !important;
            margin-top: 2rem !important;
            letter-spacing: -0.01em !important;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    # Centered branding panel
    st.markdown(f"""
    <div class="login-header">
        <div class="logo-container">
            <img class="logo-img" src="{logo_b64}" alt="Logo A&M" />
        </div>
        <div class="brand-title">SISTEMA CONTABLE A&M</div>
        <div class="brand-subtitle">Sistema Contable con Punto de Venta</div>
    </div>
    """, unsafe_allow_html=True)

    # Flujo de login en dos pasos si el segundo factor está activado
    pending_mfa = st.session_state.get("login_pending_mfa")
    
    if pending_mfa:
        st.warning("🔒 Se requiere el Segundo Factor de Autenticación (MFA)")
        mfa_code = st.text_input("Ingrese el código de 6 dígitos de su aplicación autenticadora", key="login_mfa_code", max_chars=6)
        
        c1, c2 = st.columns(2)
        if c1.button("Verificar", key="btn_verify_mfa", use_container_width=True):
            secret = str(pending_mfa.get("totp_secret") or "").strip()
            if secret and verificar_codigo_totp(secret, mfa_code):
                st.session_state["usuario_data"] = pending_mfa
                st.session_state.pop("login_pending_mfa", None)
                st.success("MFA verificado. Iniciando sesión...")
                st.rerun()
            else:
                st.error("Código de verificación incorrecto o expirado.")
                
        if c2.button("Cancelar", key="btn_cancel_mfa", use_container_width=True):
            st.session_state.pop("login_pending_mfa", None)
            st.rerun()
            
    else:
        usuario_in = st.text_input("Correo Electrónico o Usuario", placeholder="ejemplo@correo.com o tu_usuario", key="login_usuario")
        clave_in = st.text_input("Clave", type="password", key="login_clave")

        if st.button("Entrar", key="btn_login_usuario", use_container_width=True):
            usr_in_clean = str(usuario_in or "").strip()
            pwd_in_clean = str(clave_in or "").strip()
            
            verificar_bloqueo_login(usr_in_clean)
            
            encontrado = None
            error_login = None
            usr_clean_lower = usr_in_clean.lower()
            
            # Paso 1: Autenticar vía Supabase Auth (admite Correo Completo o Usuario)
            try:
                if supabase is not None:
                    email_auth = usr_clean_lower
                    if "@" not in email_auth:
                        email_auth = f"{email_auth}@ais-erp.com"
                    
                    auth_resp = supabase.auth.sign_in_with_password({
                        "email": email_auth,
                        "password": pwd_in_clean
                    })
                    
                    session = auth_resp.session
                    st.session_state["access_token"] = session.access_token
                    supabase.postgrest.auth(session.access_token)
                    
                    resp = supabase.table("usuarios").select("*").eq("id", auth_resp.user.id).execute()
                    filas = resp.data or []
                    if filas:
                        encontrado = filas[0]
            except Exception as exc:
                error_login = exc

            # Paso 2: Consultar directamente la tabla de usuarios (por correo o por usuario)
            if encontrado is None and supabase is not None:
                try:
                    resp_db = supabase.table("usuarios").select("*").or_(f"email.eq.{usr_clean_lower},usuario.eq.{usr_clean_lower}").execute()
                    candidatos = resp_db.data or []
                    for c in candidatos:
                        clave_guardada = c.get("clave") or ""
                        if verificar_clave_usuario(clave_guardada, pwd_in_clean) or str(clave_guardada).strip() == pwd_in_clean:
                            encontrado = c
                            break
                except Exception:
                    pass

            # Paso 3: Fallback de seguridad administrativo local
            if encontrado is None:
                app_pwd = "20162907"
                try:
                    app_pwd = obtener_secreto("APP_PASSWORD", "20162907")
                except Exception:
                    pass
                if usr_clean_lower in ["biberon", "nelly", "admin", "biberon01", "biberon01@gmail.com", "nelly@gmail.com"] and (pwd_in_clean == app_pwd or pwd_in_clean == "20162907"):
                    encontrado = {
                        "id": "e8d379ce-3b97-4879-b21d-c306643fd7d5",
                        "usuario": "biberon",
                        "nombre": "Nelly Aguilera",
                        "rol": "admin",
                        "email": "global",
                        "activo": True,
                        "puede_vender": True,
                        "puede_editar_ventas": True,
                        "puede_eliminar": True,
                        "puede_anular": True,
                        "puede_ver_reportes": True,
                        "puede_registrar_compras": True,
                        "puede_registrar_gastos": True,
                        "puede_configurar": True
                    }

            if encontrado is not None:
                limpiar_intentos_fallidos(usr_in_clean)
                # S-02: Bloquear admins sin MFA antes de dar acceso
                if mfa_requerido_para_admin(encontrado):
                    st.stop()
                username_lc = str(encontrado.get("usuario") or usr_clean_lower).lower()
                tenant_lc = "global"
                if username_lc not in ["admin", "nelly"]:
                    parent_lc = encontrado.get("email") or ""
                    if parent_lc.strip() and "@" not in parent_lc:
                        tenant_lc = parent_lc.strip().lower()
                    else:
                        tenant_lc = username_lc
                
                if tenant_lc != "global":
                    try:
                        cfg_resp = supabase.table("configuracion_sistema").select("slogan").eq("propietario", tenant_lc).execute()
                        if cfg_resp.data:
                            slogan_val = cfg_resp.data[0].get("slogan") or ""
                            if "[SUSPENDIDO]" in slogan_val:
                                st.error("⚠️ Su empresa ha sido suspendida. Comuníquese con el administrador A&M.")
                                st.stop()
                    except Exception:
                        pass

                if encontrado.get("mfa_enabled") and encontrado.get("totp_secret"):
                    st.session_state["login_pending_mfa"] = encontrado
                    st.rerun()
                else:
                    st.session_state["usuario_data"] = encontrado
                    st.rerun()
            else:
                registrar_intento_fallido(usr_in_clean)
                st.error("Credenciales inválidas, usuario/correo no encontrado o cuenta inactiva.")

        # Opción de Restablecimiento de Contraseña
        with st.expander("🔑 ¿Olvidaste tu contraseña?", expanded=False):
            st.markdown("""
            <div style="font-size: 0.82rem; color: #495057; line-height: 1.4; margin-bottom: 0.6rem;">
                • <b>Administradores Principales:</b> Ingrese su correo registrado para recibir el enlace de recuperación.<br>
                • <b>Usuarios Secundarios (Cajeros / Empleados):</b> El Administrador Principal puede restablecer su clave desde el panel de <i>Administración -> Usuarios</i>.
            </div>
            """, unsafe_allow_html=True)
            recup_in = st.text_input("Correo o Usuario a recuperar", key="login_recup_input", placeholder="ejemplo@correo.com o tu_usuario")
            if st.button("Restablecer Contraseña", key="btn_solicitar_recup", use_container_width=True):
                recup_clean = str(recup_in or "").strip().lower()
                if not recup_clean:
                    st.warning("⚠️ Ingrese su correo o nombre de usuario.")
                else:
                    if "@" in recup_clean:
                        if supabase is not None:
                            try:
                                supabase.auth.reset_password_for_email(recup_clean)
                            except Exception:
                                pass
                        st.success(f"📩 Si el correo <b>{recup_clean}</b> está registrado como Administrador, enviamos las instrucciones a su bandeja de entrada.")
                    else:
                        st.info(f"ℹ️ El usuario secundario <b>'{recup_clean}'</b> debe solicitar la actualización de clave al Administrador Principal desde <b>Administración -> Usuarios</b>.")

    # Premium footer
    st.markdown("""
    <div class="login-footer">
        🔒 Conexión Cifrada y Protegida &middot; Nivel Bancario
    </div>
    """, unsafe_allow_html=True)

    return False


# ═══════════════════════════════════════════════════════════════
# CENTRAL A&M — PLANES DE SERVICIO Y CONTROL DE ACCESO POR PLAN
# ═══════════════════════════════════════════════════════════════
PLANES_AM = {
    "gratuito": {
        "nombre": "Gratuito",
        "precio_mensual": 0,
        "emoji": "🆓",
        "color": "#6b7280",
        "modulos": ["Dashboard", "Caja", "POS", "Ventas", "Clientes", "Productos", "Gastos"],
        "max_usuarios": 1,
        "descripcion": "Ideal para negocios en inicio. Funciones básicas de venta.",
    },
    "basico": {
        "nombre": "Básico",
        "precio_mensual": 1500,
        "emoji": "🥈",
        "color": "#3b82f6",
        "modulos": ["Dashboard", "Caja", "POS", "Ventas", "Clientes", "Productos", "Gastos",
                    "Compras", "Proveedores", "Inventario Actual", "Historial de Inventario",
                    "Conteo Inventario", "Ajustes Inventario", "Cierre de Caja", "Empleados",
                    "Pagos Empleados", "Pérdidas", "Catálogo de Gastos"],
        "max_usuarios": 3,
        "descripcion": "Gestión completa de ventas, inventario y empleados.",
    },
    "premium": {
        "nombre": "Premium",
        "precio_mensual": 2500,
        "emoji": "⭐",
        "color": "#f59e0b",
        "modulos": ["Dashboard", "Caja", "Dinero Real", "POS", "Ventas", "Clientes", "Productos",
                    "Gastos", "Compras", "Proveedores", "Inventario Actual", "Historial de Inventario",
                    "Conteo Inventario", "Ajustes Inventario", "Cierre de Caja", "Empleados",
                    "Nómina", "Pagos Empleados", "Pérdidas", "Gastos Dueño", "Catálogo de Gastos",
                    "Estado de Resultados", "Informes", "Reportes DGII", "Créditos",
                    "Activos Fijos", "Capital Base"],
        "max_usuarios": 8,
        "descripcion": "Suite financiera completa con nómina y reportes DGII.",
    },
    "enterprise": {
        "nombre": "Enterprise",
        "precio_mensual": 4500,
        "emoji": "🏆",
        "color": "#10b981",
        "modulos": None,  # None = acceso a todos los módulos
        "max_usuarios": 999,
        "descripcion": "Acceso ilimitado a todo el ecosistema A&M con soporte prioritario.",
    },
}

def verificar_plan_permite(modulo: str) -> bool:
    """Devuelve True si el plan de la empresa actual permite acceder a 'modulo'."""
    tenant = obtener_tenant_actual()
    if tenant == "global":
        return True
    try:
        cfg = supabase.table("configuracion_sistema").select("plan").eq("propietario", tenant).limit(1).execute().data
        plan_id = (cfg[0].get("plan") if cfg else None) or "premium"
    except Exception:
        plan_id = "premium"
    plan = PLANES_AM.get(plan_id, PLANES_AM["premium"])
    if plan["modulos"] is None:
        return True
    return modulo in plan["modulos"]

def verificar_licencia_y_alertas():
    tenant = obtener_tenant_actual()
    if tenant == "global":
        return
        
    try:
        resp = supabase.table("suscripciones_empresas").select("*").eq("empresa_id", tenant).order("fecha_vencimiento", desc=True).limit(1).execute()
        suscripciones = resp.data or []
        
        if not suscripciones:
            st.warning("⚠️ Su empresa no tiene un registro de licencia activo en el sistema. Por favor, comuníquese con el administrador A&M para registrar su pago.")
            return

        ultima_sub = suscripciones[0]
        fecha_venc_str = ultima_sub.get("fecha_vencimiento")
        if not fecha_venc_str:
            return
            
        fecha_venc = datetime.strptime(fecha_venc_str, "%Y-%m-%d").date()
        hoy = datetime.now().date()
        dias_restantes = (fecha_venc - hoy).days
        dias_gracia = int(ultima_sub.get("dias_gracia") or 5)

        # Mostrar badge de plan en el sidebar
        try:
            cfg_tenant = supabase.table("configuracion_sistema").select("plan").eq("propietario", tenant).limit(1).execute().data
            plan_id_tenant = (cfg_tenant[0].get("plan") if cfg_tenant else None) or "premium"
            plan_info_tenant = PLANES_AM.get(plan_id_tenant, PLANES_AM["premium"])
            plan_color_tenant = plan_info_tenant["color"]
            st.sidebar.markdown(f"""
<div style='background:rgba(0,0,0,0.12);border:1px solid {plan_color_tenant}44;border-radius:8px;padding:6px 10px;margin-bottom:4px;text-align:center;'>
<span style='font-size:10px;font-weight:700;color:{plan_color_tenant};letter-spacing:1px;'>
{plan_info_tenant["emoji"]} PLAN {plan_info_tenant["nombre"].upper()}</span>
</div>
""", unsafe_allow_html=True)
        except Exception:
            pass

        # Bloqueo de login si excede los 5 días de gracia
        if dias_restantes + dias_gracia < 0:
            st.markdown(f"""
            <div style="background-color: #ff4b4b; color: white; padding: 24px; border-radius: 12px; border: 2px solid #b91c1c; text-align: center; margin-top: 50px; font-family: -apple-system, sans-serif;">
                <h2 style="color: white; margin: 0 0 10px 0; font-size: 26px;">❌ SISTEMA SUSPENDIDO</h2>
                <p style="font-size: 15px; margin: 0 0 15px 0; line-height: 1.5;">
                    Estimado usuario, el período de gracia de su licencia ha expirado.<br>
                    Su servicio de sistema contable venció el <strong>{fecha_venc.strftime('%d/%m/%Y')}</strong> y se han agotado los {dias_gracia} días de gracia para regularizar su pago.
                </p>
                <div style="background-color: rgba(0,0,0,0.2); padding: 12px 18px; border-radius: 8px; font-size: 14px; font-weight: bold; display: inline-block;">
                    📞 Por favor, comuníquese de inmediato con Nelly / A&M para reactivar su servicio.
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.stop()

        # Banner Naranja: Período de Gracia Activo (Vencido pero dentro de los 5 días)
        elif dias_restantes < 0:
            dias_gracia_restantes = dias_gracia + dias_restantes
            st.sidebar.warning(f"⚠️ Período de gracia activo: Su licencia venció el {fecha_venc.strftime('%d/%m/%Y')}. Le quedan {dias_gracia_restantes} día(s) de gracia antes de la suspensión automática del sistema.")
            st.warning(f"⚠️ **Atención**: Su licencia contable ha vencido el **{fecha_venc.strftime('%d/%m/%Y')}**. Actualmente se encuentra en su período de gracia y le quedan **{dias_gracia_restantes} día(s) de gracia** para realizar su pago antes del bloqueo automático del sistema.")

        # Banner Amarillo: Licencia por vencer pronto (dentro de los próximos 5 días)
        elif dias_restantes <= 5:
            st.sidebar.info(f"⚠️ Su licencia vence en {dias_restantes} días (el {fecha_venc.strftime('%d/%m/%Y')}). Por favor, prepare su próximo pago.")
            st.info(f"⚠️ **Atención**: Su licencia de servicio vence pronto en **{dias_restantes} días** (el **{fecha_venc.strftime('%d/%m/%Y')}**). Por favor, coordine su próximo pago para evitar interrupciones de servicio.")

    except Exception:
        pass



if not login_simple():
    st.stop()

# Forzar visibilidad del Sidebar y del Header (para evitar que se queden ocultos por el CSS del login)
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        display: flex !important;
    }
    [data-testid="stHeader"] {
        display: flex !important;
    }
</style>
""", unsafe_allow_html=True)

verificar_licencia_y_alertas()



def obtener_nombre_producto(row) -> str:
    if row is None:
        return ""
    data = {}
    if hasattr(row, "to_dict"):
        try:
            data = row.to_dict()
        except Exception:
            data = dict(row)
    elif isinstance(row, dict):
        data = row
    else:
        try:
            data = dict(row)
        except Exception:
            pass
            
    base_nombre = limpiar_texto(data.get("nombre") or data.get("producto"))
    obs = data.get("observacion") or ""
    if isinstance(obs, str) and obs.startswith("ATRIBUTOS:"):
        try:
            import json
            attr_str = obs.replace("ATRIBUTOS:", "").strip()
            attrs = json.loads(attr_str)
            partes = []
            for k in ["marca", "talla", "color", "pasillo", "estanteria"]:
                if attrs.get(k):
                    partes.append(f"{k.capitalize()}: {attrs[k]}")
            if partes:
                return f"{base_nombre} ({' | '.join(partes)})"
        except Exception:
            pass
    return base_nombre




def producto_tiene_inventario(row: pd.Series) -> bool:
    return bool(row.get("usa_inventario", True))



def obtener_existencia_producto(row: pd.Series) -> float:
    return (
        limpiar_numero(row.get("cantidad"))
        or limpiar_numero(row.get("stock"))
        or limpiar_numero(row.get("existencias"))
        or 0.0
    )



def actualizar_existencia_producto(producto_row: pd.Series, nueva_cantidad: float) -> bool:
    payload = {"cantidad": float(nueva_cantidad)}
    if "stock" in producto_row.index:
        payload["stock"] = float(nueva_cantidad)
    return actualizar("productos", producto_row["id"], payload)


def obtener_detalle_venta(venta_id):
    return supabase.table("detalle_venta").select("*").eq("venta_id", venta_id).execute().data


def eliminar_linea_detalle(id_linea):
    supabase.table("detalle_venta").delete().eq("id", id_linea).execute()


def actualizar_linea_detalle(id_linea, cantidad):
    supabase.table("detalle_venta").update({"cantidad": cantidad}).eq("id", id_linea).execute()


def insertar_linea_detalle(venta_id, producto, cantidad, precio, costo):
    supabase.table("detalle_venta").insert({
        "venta_id": venta_id,
        "producto": producto,
        "cantidad": cantidad,
        "precio_unitario": precio,
        "costo_unitario": costo,
        "total_linea": cantidad * precio,
        "ganancia_linea": (precio - costo) * cantidad,
        "empresa_id": obtener_tenant_actual()
    }).execute()



def registrar_movimiento_inventario(producto_id, producto, tipo_movimiento, referencia_tabla, referencia_id, cantidad, costo_unitario, observacion=""):
    datos = {
        "producto_id": producto_id,
        "producto": producto,
        "tipo_movimiento": tipo_movimiento,
        "referencia_tabla": referencia_tabla,
        "referencia_id": str(referencia_id) if referencia_id is not None else None,
        "cantidad": float(cantidad),
        "costo_unitario": float(costo_unitario or 0),
        "observacion": observacion,
        "usuario": nombre_usuario_actual(),
    }
    try:
        supabase.table("movimientos").insert(datos).execute()
    except Exception:
        pass



def registrar_compra_producto(producto_row: pd.Series, cantidad: float, costo_unitario: float, fecha_compra: str, proveedor: str = "", numero: str = "", descripcion: str = "", metodo: str = "") -> bool:
    producto_id = producto_row["id"]
    producto_nombre = obtener_nombre_producto(producto_row)
    total = float(cantidad) * float(costo_unitario)
    try:
        resp = supabase.table("compras").insert({
            "fecha": fecha_compra,
            "numero": numero,
            "proveedor": proveedor,
            "descripcion": descripcion or f"Compra de {producto_nombre}",
            "monto": total,
            "metodo": metodo,
            "producto_id": str(producto_id),
            "producto": producto_nombre,
            "cantidad": float(cantidad),
            "costo_unitario": float(costo_unitario),
            "total": total,
            "usuario": nombre_usuario_actual(),
        }).execute()
        compra_id = (resp.data or [{}])[0].get("id") if hasattr(resp, "data") else None
        existencia_actual = float(obtener_existencia_producto(producto_row) or 0.0)
        costo_actual = float(producto_row.get("costo_promedio") or producto_row.get("costo") or 0.0)
        cant_nueva = float(cantidad)
        costo_nuevo = float(costo_unitario)
        denominador = existencia_actual + cant_nueva
        if denominador > 0:
            cpp_calculado = ((existencia_actual * costo_actual) + (cant_nueva * costo_nuevo)) / denominador
        else:
            cpp_calculado = costo_nuevo

        nueva_existencia = existencia_actual + cant_nueva
        payload = {"costo": float(cpp_calculado), "cantidad": float(nueva_existencia)}
        if "stock" in producto_row.index:
            payload["stock"] = float(nueva_existencia)
        if "costo_promedio" in producto_row.index:
            payload["costo_promedio"] = float(cpp_calculado)
        supabase.table("productos").update(payload).eq("id", producto_id).execute()
        try:
            supabase.table("inventario_lotes").insert({
                "producto_id": str(producto_id),
                "producto": producto_nombre,
                "compra_id": str(compra_id) if compra_id else None,
                "cantidad_inicial": float(cantidad),
                "cantidad_restante": float(cantidad),
                "costo_unitario": float(costo_unitario),
                "fecha_compra": fecha_compra,
                "activo": True,
            }).execute()
        except Exception:
            pass
        registrar_movimiento_inventario(producto_id, producto_nombre, "entrada_compra", "compras", compra_id, cantidad, costo_unitario, descripcion)
        registrar_auditoria("compra_producto", "compras", f"producto={producto_nombre} cantidad={cantidad} costo={costo_unitario}")
        return True
    except Exception as exc:
        st.error(f"No se pudo registrar la compra: {exc}")
        return False



def obtener_costo_fifo(producto_row: pd.Series, cantidad: float) -> tuple[float, list[dict]]:
    producto_id = str(producto_row["id"])
    producto_nombre = obtener_nombre_producto(producto_row)
    lotes = leer_tabla("inventario_lotes")
    movimientos = []
    if lotes.empty:
        costo = limpiar_numero(producto_row.get("costo")) or 0.0
        return costo, movimientos
    tmp = lotes.copy()
    if "producto_id" in tmp.columns:
        tmp = tmp[tmp["producto_id"].astype(str) == producto_id]
    if "cantidad_restante" in tmp.columns:
        tmp = tmp[pd.to_numeric(tmp["cantidad_restante"], errors="coerce").fillna(0) > 0]
    if "fecha_compra" in tmp.columns:
        tmp["fecha_compra"] = pd.to_datetime(tmp["fecha_compra"], errors="coerce")
        tmp = tmp.sort_values(["fecha_compra", "fecha"], na_position="last")
    restante = float(cantidad)
    costo_total = 0.0
    for _, lote in tmp.iterrows():
        if restante <= 0:
            break
        disponible = limpiar_numero(lote.get("cantidad_restante")) or 0
        if disponible <= 0:
            continue
        tomar = min(disponible, restante)
        costo = limpiar_numero(lote.get("costo_unitario")) or 0
        costo_total += tomar * costo
        movimientos.append({"lote_id": lote["id"], "tomar": tomar, "costo": costo, "restante_final": disponible - tomar})
        restante -= tomar
    if cantidad <= 0:
        return 0.0, movimientos
    if costo_total <= 0:
        costo_total = (limpiar_numero(producto_row.get("costo")) or 0.0) * float(cantidad)
    return costo_total / float(cantidad), movimientos



def aplicar_consumo_fifo(movimientos: list[dict]):
    for mov in movimientos:
        payload = {
            "cantidad_restante": float(mov["restante_final"]),
            "activo": float(mov["restante_final"]) > 0,
        }
        try:
            supabase.table("inventario_lotes").update(payload).eq("id", mov["lote_id"]).execute()
        except Exception:
            pass


def promover_encabezado_inteligente(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    
    keywords = {"nombre", "producto", "codigo", "barra", "costo", "precio", "stock", "cantidad", "existencia", "categoria", "empleado", "sueldo", "salario", "cedula", "telefono", "rnc", "direccion"}
    
    for idx in range(min(8, len(df))):
        row_values = [str(v).strip().lower() for v in df.iloc[idx].tolist()]
        coincidencias = 0
        for val in row_values:
            if any(k in val for k in keywords):
                coincidencias += 1
        
        if coincidencias >= 2:
            nuevas_columnas = []
            for col_idx, val in enumerate(df.iloc[idx].tolist()):
                val_str = str(val).strip()
                if not val_str or val_str.lower() == "nan":
                    val_str = f"Columna_{col_idx}"
                nuevas_columnas.append(val_str)
            
            df.columns = nuevas_columnas
            df = df.iloc[idx+1:].reset_index(drop=True)
            return df
            
    return df


def leer_archivo_subido(archivo) -> pd.DataFrame:
    try:
        nombre = archivo.name.lower()
        if nombre.endswith((".csv", ".txt")):
            try:
                df = pd.read_csv(archivo, sep=None, engine="python")
            except Exception:
                archivo.seek(0)
                try:
                    df = pd.read_csv(archivo, sep=None, engine="python", encoding="latin-1")
                except Exception:
                    archivo.seek(0)
                    df = pd.read_csv(archivo, sep="\t", encoding="latin-1")
        else:
            df = pd.read_excel(archivo)
        df = promover_encabezado_inteligente(df)
        df = normalizar_columnas(df)
        df = mapear_columnas(df)
        return df
    except Exception as exc:
        st.error(f"No se pudo leer el archivo: {exc}")
        return pd.DataFrame()

def filtrar_por_fechas(df: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns:
        return df.copy()
    out = df.copy()
    try:
        out["fecha"] = pd.to_datetime(out["fecha"], format="ISO8601", errors="coerce")
    except Exception:
        out["fecha"] = pd.to_datetime(out["fecha"], errors="coerce")
    desde_dt = pd.to_datetime(desde)
    hasta_dt = pd.to_datetime(hasta) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return out[(out["fecha"] >= desde_dt) & (out["fecha"] <= hasta_dt)]



def buscar_df(df: pd.DataFrame, texto: str) -> pd.DataFrame:
    if df.empty or not texto:
        return df
    mask = df.astype(str).apply(lambda col: col.str.contains(texto, case=False, na=False)).any(axis=1)
    return df[mask]



def suma_col(df: pd.DataFrame, columna: str) -> float:
    if df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())


def obtener_utilidad_bruta_periodo(ventas_df: pd.DataFrame) -> float:
    if ventas_df.empty:
        return 0.0
    utilidad = 0.0
    if "ganancia_bruta" in ventas_df.columns:
        utilidad += float(pd.to_numeric(ventas_df["ganancia_bruta"], errors="coerce").fillna(0).sum())
    if utilidad == 0.0 and "ganancia_bruta_manual" in ventas_df.columns:
        utilidad += float(pd.to_numeric(ventas_df["ganancia_bruta_manual"], errors="coerce").fillna(0).sum())
    return float(utilidad)


def obtener_ventas_periodo_actualizadas(desde, hasta) -> pd.DataFrame:
    try:
        tenant = obtener_tenant_actual()
        df = _leer_tabla_de_supabase("ventas", order_by="fecha", tenant=tenant)
        if not df.empty and "fecha" in df.columns:
            try:
                df["fecha"] = pd.to_datetime(df["fecha"], format="ISO8601", errors="coerce")
            except Exception:
                df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return filtrar_por_fechas(df, desde, hasta)
    except Exception:
        return filtrar_por_fechas(DATA["ventas"], desde, hasta)



def agrupar_mensual(df: pd.DataFrame, columna_valor: str) -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns or columna_valor not in df.columns:
        return pd.DataFrame(columns=["mes", "valor"])
    temp = df.copy()
    temp["fecha"] = pd.to_datetime(temp["fecha"], errors="coerce")
    temp[columna_valor] = pd.to_numeric(temp[columna_valor], errors="coerce").fillna(0)
    temp = temp.dropna(subset=["fecha"])
    if temp.empty:
        return pd.DataFrame(columns=["mes", "valor"])
    temp["mes"] = temp["fecha"].dt.to_period("M").astype(str)
    out = temp.groupby("mes", as_index=False)[columna_valor].sum()
    out.columns = ["mes", "valor"]
    return out



def rango_fechas_ui(key_base: str):
    if f"{key_base}_desde_val" not in st.session_state:
        st.session_state[f"{key_base}_desde_val"] = date.today().replace(day=1)
    if f"{key_base}_hasta_val" not in st.session_state:
        st.session_state[f"{key_base}_hasta_val"] = date.today()

    c1, c2, c3 = st.columns([3, 3, 2])
    with c1:
        desde = st.date_input("Desde", value=st.session_state[f"{key_base}_desde_val"], key=f"{key_base}_desde_input")
    with c2:
        hasta = st.date_input("Hasta", value=st.session_state[f"{key_base}_hasta_val"], key=f"{key_base}_hasta_input")
    with c3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔍 Buscar", key=f"{key_base}_btn_filtrar", use_container_width=True):
            st.session_state[f"{key_base}_desde_val"] = desde
            st.session_state[f"{key_base}_hasta_val"] = hasta
            st.rerun()
            
    return st.session_state[f"{key_base}_desde_val"], st.session_state[f"{key_base}_hasta_val"]



def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="datos")
    buffer.seek(0)
    return buffer.getvalue()



def embellecer_df_exportacion(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    
    df_clean = df.copy()
    
    # 1. Eliminar columnas técnicas internas
    cols_a_eliminar = [
        "id", "empresa_id", "clave", "logo_url", "slogan", "slogan_e",
        "propietario_id", "producto_id", "cliente_id", "proveedor_id", "empleado_id",
        "antes_json", "despues_json"
    ]
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if col_lower.endswith("_id") or col_lower.endswith("_idx") or col_lower == "identificación":
            if col not in cols_a_eliminar:
                cols_a_eliminar.append(col)
                
    df_clean = df_clean.drop(columns=cols_a_eliminar, errors="ignore")
    
    # 2. Formatear booleanos a Sí/No
    for col in df_clean.columns:
        if df_clean[col].dtype == "bool":
            df_clean[col] = df_clean[col].map({True: "Sí", False: "No"})
            
    # 3. Formatear fechas/horas
    for col in df_clean.columns:
        col_lower = str(col).lower()
        if "fecha" in col_lower or "created_at" in col_lower:
            try:
                df_clean[col] = pd.to_datetime(df_clean[col]).dt.strftime('%d/%m/%Y %I:%M %p')
            except Exception:
                try:
                    df_clean[col] = pd.to_datetime(df_clean[col]).dt.strftime('%d/%m/%Y')
                except Exception:
                    pass
                    
    # 4. Mapear nombres de columnas a nombres hermosos en español
    mapeo_hermoso = {
        "codigo": "Código",
        "nombre": "Nombre",
        "categoria": "Categoría",
        "stock": "Existencia en Inventario",
        "producto": "Producto Comprado",
        "cantidad": "Cantidad",
        "costo": "Costo (RD$)",
        "costo_unitario": "Costo Unitario (RD$)",
        "precio": "Precio de Venta (RD$)",
        "precio_venta": "Precio de Venta (RD$)",
        "precio_descuento": "Precio Oferta (RD$)",
        "precio_especial": "Precio Mayorista (RD$)",
        "activo": "Estado Activo",
        "usa_inventario": "Controla Inventario",
        "proveedor": "Proveedor",
        "descripcion": "Descripción / Detalle",
        "numero_factura": "No. Factura",
        "numero": "No. Documento",
        "metodo_pago": "Método de Pago",
        "metodo": "Método de Pago",
        "fecha": "Fecha",
        "created_at": "Fecha de Registro",
        "cliente_nombre": "Nombre de Cliente",
        "vendedor_nombre": "Vendedor",
        "total": "Total Facturado (RD$)",
        "subtotal": "Subtotal (RD$)",
        "itbis": "ITBIS (RD$)",
        "ganancia": "Ganancia Estimada (RD$)",
        "usuario": "Nombre de Usuario",
        "rol": "Rol de Usuario",
        "negocio_nombre": "Nombre de Empresa",
        "rnc": "RNC",
        "telefono": "Teléfono",
        "direccion": "Dirección",
        "fecha_vencimiento": "Fecha de Vencimiento",
        "fecha_inicio": "Fecha de Inicio",
        "monto_pagado": "Monto Pagado (RD$)",
        "periodo": "Periodo de Suscripción",
        "observacion": "Observaciones",
        "accion": "Acción Realizada",
        "modulo": "Módulo de Sistema",
        "tabla_afectada": "Mesa / Tabla de Datos",
        "tipo_comprobante": "Tipo de Comprobante (NCF)",
        "secuencia_actual": "Secuencia NCF Actual",
        "secuencia_maxima": "Límite Secuencia NCF",
        "utilidad": "Utilidad Neta (RD$)",
        "ganancia_bruta": "Ganancia Bruta (RD$)",
        "detalle": "Detalle",
        "monto": "Monto (RD$)",
        "motivo": "Motivo / Concepto",
        "tipo_gasto": "Tipo de Gasto",
        "salario": "Sueldo Neto (RD$)",
        "cedula": "Cédula / ID",
        "pago_monto": "Sueldo Pagado (RD$)",
        "tipo_pago": "Tipo de Pago",
        "total_costo_inventario": "Costo Total Inventario (RD$)",
        "total_valor_venta": "Valor Venta Total (RD$)",
        "ganancia_potencial": "Margen Ganancia Potencial (RD$)"
    }
    
    nuevos_headers = {}
    for col in df_clean.columns:
        col_str = str(col)
        col_lower = col_str.lower()
        if col_lower in mapeo_hermoso:
            nuevos_headers[col_str] = mapeo_hermoso[col_lower]
        else:
            hermoso = col_str.replace("_", " ").title()
            nuevos_headers[col_str] = hermoso
            
    df_clean = df_clean.rename(columns=nuevos_headers)
    return df_clean


def descargar_archivos(df: pd.DataFrame, base_name: str):
    if df is None or df.empty:
        st.info("No hay datos para descargar.")
        return

    # Embellecer DataFrame para exportación
    df_clean = embellecer_df_exportacion(df)

    csv_bytes = df_clean.to_csv(index=False).encode("utf-8-sig")
    xlsx_bytes = df_to_excel_bytes(df_clean)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Descargar CSV",
            data=csv_bytes,
            file_name=f"{base_name}.csv",
            mime="text/csv",
            key=f"dl_csv_{base_name}_{uuid.uuid4().hex}",
        )
    with c2:
        st.download_button(
            "⬇️ Descargar Excel",
            data=xlsx_bytes,
            file_name=f"{base_name}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"dl_xlsx_{base_name}_{uuid.uuid4().hex}",
        )


# =========================================================
# SUPABASE CRUD
# =========================================================
def registrar_auditoria(accion: str, tabla: str, detalle: str = ""):
    try:
        supabase.table("auditoria").insert(
            {
                "accion": accion,
                "tabla": tabla,
                "usuario": nombre_usuario_actual(),
                "fecha": datetime.now().isoformat(),
                "detalle": detalle,
            }
        ).execute()
    except Exception:
        pass


# C-05/N-05: registrar_auditoria_pro se importa directamente desde core.db (con PII masking)



def gatillar_apertura_gaveta(motivo: str):
    registrar_auditoria("apertura_gaveta_sin_venta", "caja", f"Motivo: {motivo}")
    
    negocio = obtener_configuracion().get("negocio_nombre") or "Bibe Ron 01"
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    usuario = nombre_usuario_actual()
    
    html_gaveta = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: monospace; font-size: 14px; text-align: center; color: #000; padding: 10px; }}
            .line {{ border-top: 1px dashed #000; margin: 10px 0; }}
        </style>
    </head>
    <body onload="window.print();">
        <h3>*** {negocio.upper()} ***</h3>
        <p><b>APERTURA DE GAVETA</b></p>
        <div class="line"></div>
        <p><b>Fecha:</b> {ahora}</p>
        <p><b>Cajero:</b> {usuario}</p>
        <p><b>Motivo:</b> {motivo}</p>
        <div class="line"></div>
        <p>AUDITORÍA DE SEGURIDAD</p>
    </body>
    </html>
    """
    st.session_state["imprimir_apertura_gaveta"] = html_gaveta




def total_contable_sin_recargo(row) -> float:
    """
    Total real para contabilidad/caja/dashboard.
    Regla actual:
    - El POS guarda en total la venta real.
    - El recargo de tarjeta queda solo como nota informativa.
    - Por eso NO se debe restar el recargo otra vez.
    """
    try:
        subtotal = float(limpiar_numero(row.get("subtotal")) or 0)
        descuento = float(limpiar_numero(row.get("descuento")) or limpiar_numero(row.get("descuento_global")) or 0)
        total = float(limpiar_numero(row.get("total")) or 0)

        # Si existe subtotal, usarlo como base real.
        if subtotal > 0:
            return max(subtotal - descuento, 0)

        # Si no existe subtotal, usar total tal como está guardado.
        return max(total, 0)
    except Exception:
        try:
            return float(limpiar_numero(row.get("total")) or 0)
        except Exception:
            return 0.0


def aplicar_total_contable_df(df):
    """
    Crea una columna total_contable con la venta real.
    No resta recargo porque el recargo ya no es financiero.
    """
    try:
        if df is None or df.empty:
            return df
        out = df.copy()
        out["total_contable"] = out.apply(total_contable_sin_recargo, axis=1)
        return out
    except Exception:
        return df


def _leer_tabla_de_supabase(nombre_tabla: str, order_by: str = "id", tenant: str = "global") -> pd.DataFrame:
    """Descarga la tabla desde Supabase. Si tenant != 'global' y la tabla es multi-tenant, filtra por empresa_id (o email en caso de usuarios)."""
    try:
        query = supabase.table(nombre_tabla).select("*")
        # ── Fase 4: Aislamiento por empresa ──────────────────────────────────────
        if tenant and nombre_tabla in TABLAS_MULTI_TENANT:
            if nombre_tabla == "usuarios":
                if tenant != "global":
                    query = query.eq("email", tenant)
            else:
                if tenant == "global":
                    query = query.or_("empresa_id.eq.global,empresa_id.is.null")
                else:
                    query = query.eq("empresa_id", tenant)
        # ─────────────────────────────────────────────────────────────────────────
        try:
            ordered_query = query.order(order_by)
        except Exception:
            ordered_query = query

        data = []
        start = 0
        chunk_size = 1000
        while True:
            resp = ordered_query.range(start, start + chunk_size - 1).execute()
            chunk_data = resp.data or []
            data.extend(chunk_data)
            if len(chunk_data) < chunk_size:
                break
            start += chunk_size
            
        df = pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

    if not df.empty:
        if "identificación" in df.columns and "id" not in df.columns:
            df["id"] = df["identificación"]
        if "metodo_pago" not in df.columns and "método_pago" in df.columns:
            df["metodo_pago"] = df["método_pago"]
        if "metodo" not in df.columns and "método" in df.columns:
            df["metodo"] = df["método"]
        if "cliente_nombre" not in df.columns and "cliente_nombr" in df.columns:
            df["cliente_nombre"] = df["cliente_nombr"]
    if nombre_tabla == "productos" and not df.empty and "nombre" in df.columns:
        try:
            df = df.sort_values(by="nombre", key=lambda col: col.str.lower(), ascending=True).reset_index(drop=True)
        except Exception:
            pass
    if nombre_tabla == "ventas":
        return aplicar_total_contable_df(df)
    return df


def leer_tabla(nombre_tabla: str, order_by: str = "id") -> pd.DataFrame:
    """Lee la tabla de forma selectiva, ultra-rápida y multi-tenant."""
    tenant = obtener_tenant_actual()
    cache_key = f"{nombre_tabla}::{tenant}"

    if "session_cache_tablas" not in st.session_state:
        st.session_state["session_cache_tablas"] = {}

    ahora = datetime.now()
    cache = st.session_state["session_cache_tablas"].get(cache_key)

    # TTL de 5 minutos (300 segundos) para evitar consultas redundantes de red
    if cache is not None:
        df, timestamp = cache
        if (ahora - timestamp).total_seconds() < 300.0:
            return df.copy()

    # Si no hay caché válido, descargar de base de datos con filtro de tenant
    df = _leer_tabla_de_supabase(nombre_tabla, order_by, tenant=tenant)
    df = agregar_columna_codigo_secuencial(df, nombre_tabla)
    if not df.empty and "fecha" in df.columns:
        try:
            df["fecha"] = pd.to_datetime(df["fecha"], format="ISO8601", errors="coerce")
        except Exception:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    st.session_state["session_cache_tablas"][cache_key] = (df, ahora)
    return df.copy()


# C-05/N-05: Las funciones CRUD (insertar, actualizar, eliminar, _campos_pk) y registrar_auditoria_pro
# son importadas desde core.db (donde están protegidas por PII masking, inmutabilidad NCF y barreras de período contable).




def anular(nombre_tabla: str, fila_id: Any, motivo: str = "") -> bool:
    campos = _campos_pk(nombre_tabla)
    ultimo_error = None
    
    # Obtener antes_json
    antes_json = None
    try:
        df = DATA[nombre_tabla]
        if not df.empty and "id" in df.columns:
            match = df[df["id"].astype(str) == str(fila_id)]
            if not match.empty:
                antes_json = match.iloc[0].to_dict()
    except Exception:
        pass

    for campo in campos:
        try:
            supabase.table(nombre_tabla).update({"anulado": True, "motivo_anulacion": motivo}).eq(campo, fila_id).execute()
            
            despues_json = antes_json.copy() if antes_json else {}
            despues_json["anulado"] = True
            despues_json["motivo_anulacion"] = motivo
            
            # Registrar auditoría avanzada
            registrar_auditoria_pro(
                accion="anular",
                modulo=nombre_tabla.capitalize(),
                tabla_afectada=nombre_tabla,
                registro_id=fila_id,
                antes_json=antes_json,
                despues_json=despues_json,
                descripcion=f"Registro anulado en {nombre_tabla}. Motivo: {motivo}"
            )
            invalidar_cache_tabla(nombre_tabla)
            return True
        except Exception as exc:
            ultimo_error = exc
    st.error(f"Error al anular en {nombre_tabla}: {ultimo_error}")
    return False


def ajustar_pagos_sin_recargo_tarjeta(pagos_df: pd.DataFrame, ventas_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if pagos_df is None or pagos_df.empty:
        return pagos_df
    pagos = pagos_df.copy()
    if "monto" not in pagos.columns:
        return pagos
    pagos["monto"] = pd.to_numeric(pagos["monto"], errors="coerce").fillna(0)
    metodo_col = "metodo" if "metodo" in pagos.columns else ("metodo_pago" if "metodo_pago" in pagos.columns else None)
    if not metodo_col or ventas_df is None or ventas_df.empty:
        return pagos
    ventas = ventas_df.copy()
    ventas = aplicar_total_contable_df(ventas) if "aplicar_total_contable_df" in globals() else ventas

    def descontar(indices, exceso):
        for metodo_prioridad in ["tarjeta", "efectivo", "transferencia", "credito"]:
            for idx in indices:
                if exceso <= 0:
                    return
                if normalizar_texto(pagos.at[idx, metodo_col]) != metodo_prioridad:
                    continue
                monto = float(pagos.at[idx, "monto"])
                quitar = min(monto, exceso)
                pagos.at[idx, "monto"] = monto - quitar
                exceso -= quitar

    id_col = next((c for c in ["id", "identificación", "identificacion"] if c in ventas.columns), None)
    if id_col and "venta_id" in pagos.columns:
        for _, venta in ventas.iterrows():
            venta_id = str(venta.get(id_col))
            idxs = list(pagos[pagos["venta_id"].astype(str) == venta_id].index)
            if not idxs:
                continue
            total_real = float(limpiar_numero(venta.get("total_contable")) or limpiar_numero(venta.get("subtotal")) or limpiar_numero(venta.get("total")) or 0)
            total_pagado = float(pagos.loc[idxs, "monto"].sum())
            exceso = max(total_pagado - total_real, 0.0)
            if exceso > 0:
                descontar(idxs, exceso)
    return pagos

# =========================================================
# CARGA GLOBAL
# =========================================================
class LazyDataDict(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = leer_tabla(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except Exception:
            return default

    def copy(self):
        return self

    def update(self, other=None, **kwargs):
        self.clear()
        if other:
            if isinstance(other, dict):
                for k, v in other.items():
                    self[k] = v
            elif hasattr(other, "keys"):
                for k in other.keys():
                    self[k] = other[k]


def cargar_datos() -> LazyDataDict:
    # No limpiamos la caché global en cada renderizado de Streamlit para permitir
    # que la caché en memoria (session_cache_tablas) con TTL de 30s en leer_tabla funcione correctamente.
    # Esto elimina las consultas de red redundantes y acelera drásticamente todo el sistema (especialmente el POS).
    return LazyDataDict()


DATA = cargar_datos()

if "pos_post_venta" not in st.session_state:
    st.session_state["pos_post_venta"] = None

if "dash_desde" not in st.session_state:
    st.session_state["dash_desde"] = date.today()
if "dash_hasta" not in st.session_state:
    st.session_state["dash_hasta"] = date.today()

# =========================================================
# HELPERS DE NEGOCIO
# =========================================================
def get_producto_por_nombre(nombre: str):
    df = DATA["productos"]
    if df.empty or "nombre" not in df.columns:
        return None
    nombre_n = normalizar_texto(nombre)
    tmp = df.copy()
    tmp["_n"] = tmp["nombre"].astype(str).apply(normalizar_texto)
    match = tmp[tmp["_n"] == nombre_n]
    if match.empty:
        return None
    return match.iloc[0]


def validar_unicidad_producto(nombre: str, codigo: str, ignorar_producto_id: Any = None) -> tuple[bool, str]:
    df = DATA.get("productos", pd.DataFrame())
    if df.empty:
        return True, ""
    
    nombre_norm = normalizar_texto(nombre)
    codigo_norm = str(codigo).strip()
    
    tmp_df = df.copy()
    if ignorar_producto_id is not None:
        if "id" in tmp_df.columns:
            tmp_df = tmp_df[tmp_df["id"].astype(str) != str(ignorar_producto_id)]
            
    # Validar duplicados de nombre
    if "nombre" in tmp_df.columns:
        for idx, row in tmp_df.iterrows():
            n_existente = normalizar_texto(row.get("nombre"))
            if n_existente == nombre_norm:
                return False, f"⚠️ El nombre '{nombre}' ya está registrado en otro producto."
                
    # Validar duplicados de código
    if codigo_norm and "codigo" in tmp_df.columns:
        for idx, row in tmp_df.iterrows():
            c_existente = str(row.get("codigo")).strip()
            if c_existente == codigo_norm:
                return False, f"⚠️ El código '{codigo}' ya está asignado al producto '{row.get('nombre')}'."
                
    return True, ""



def actualizar_stock_producto(nombre: str, nueva_cantidad: float, fecha_mov=None):
    fila = get_producto_por_nombre(nombre)
    if fila is None:
        return False
    payload = {"cantidad": float(nueva_cantidad)}
    if "stock" in fila.index:
        payload["stock"] = float(nueva_cantidad)
    if fecha_mov is not None:
        payload["fecha"] = str(fecha_mov)
    return actualizar("productos", fila["id"], payload)



def upsert_inventario_actual(producto: str, costo: float, precio: float, existencia: float, fecha_mov, observacion: str = "") -> bool:
    invent = DATA["inventario_actual"]
    producto_n = normalizar_texto(producto)
    if not invent.empty and "producto" in invent.columns:
        tmp = invent.copy()
        tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
        match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            fila_id = match.iloc[0]["id"]
            return actualizar(
                "inventario_actual",
                fila_id,
                {
                    "fecha": str(fecha_mov),
                    "producto": limpiar_texto(producto),
                    "costo": float(costo),
                    "precio": float(precio),
                    "existencia_sistema": float(existencia),
                    "observacion": observacion,
                },
            )

    return insertar(
        "inventario_actual",
        {
            "fecha": str(fecha_mov),
            "producto": limpiar_texto(producto),
            "costo": float(costo),
            "precio": float(precio),
            "existencia_sistema": float(existencia),
            "observacion": observacion,
        },
    )





def upsert_conteo_base(producto: str, existencia: float, fecha_mov, observacion: str = "") -> bool:
    conteo = DATA.get("conteo_inventario", pd.DataFrame()).copy()
    producto_n = normalizar_texto(producto)
    fecha_txt = str(fecha_mov)
    if not conteo.empty and "producto" in conteo.columns:
        tmp = conteo.copy()
        tmp["_n"] = tmp["producto"].astype(str).apply(normalizar_texto)
        if "fecha" in tmp.columns:
            tmp["_f"] = pd.to_datetime(tmp["fecha"], errors="coerce").dt.date.astype(str)
            match = tmp[(tmp["_n"] == producto_n) & (tmp["_f"] == fecha_txt)]
        else:
            match = tmp[tmp["_n"] == producto_n]
        if not match.empty:
            fila = match.iloc[0]
            existencia_fisica = limpiar_numero(fila.get("existencia_fisica"))
            if existencia_fisica is None:
                existencia_fisica = float(existencia)
            diferencia = float(existencia_fisica) - float(existencia)
            estado = "cuadrado" if abs(diferencia) < 0.0001 else ("faltante" if diferencia < 0 else "sobrante")
            return actualizar(
                "conteo_inventario",
                fila["id"],
                {
                    "fecha": fecha_txt,
                    "producto": limpiar_texto(producto),
                    "existencia_sistema": float(existencia),
                    "existencia_fisica": float(existencia_fisica),
                    "diferencia": float(diferencia),
                    "estado": estado,
                    "observacion": observacion or fila.get("observacion") or "Sincronizado desde productos",
                },
            )
    return insertar(
        "conteo_inventario",
        {
            "fecha": fecha_txt,
            "producto": limpiar_texto(producto),
            "existencia_sistema": float(existencia),
            "existencia_fisica": float(existencia),
            "diferencia": 0.0,
            "estado": "cuadrado",
            "observacion": observacion or "Sincronizado desde productos",
        },
    )


def sincronizar_producto_inventario(producto_row: pd.Series | dict, fecha_mov=None, observacion: str = "") -> bool:
    if fecha_mov is None:
        fecha_mov = ahora_str()
    nombre = obtener_nombre_producto(producto_row)
    costo = float(limpiar_numero(producto_row.get("costo")) or 0)
    precio = float(limpiar_numero(producto_row.get("precio")) or 0)
    existencia = float(obtener_existencia_producto(producto_row))
    ok1 = upsert_inventario_actual(nombre, costo, precio, existencia, fecha_mov, observacion or "Sincronizado desde productos")
    ok2 = upsert_conteo_base(nombre, existencia, fecha_mov, observacion or "Sincronizado desde productos")
    return bool(ok1 and ok2)


def refrescar_producto_por_id(producto_id: Any):
    try:
        resp = supabase.table("productos").select("*").eq("id", producto_id).limit(1).execute()
        filas = resp.data or []
        if filas:
            return pd.Series(filas[0])
    except Exception:
        pass
    return None


def revertir_inventario_de_venta(venta_id: Any, marcar_detalle_anulado: bool = False) -> bool:
    try:
        resp = supabase.table("detalle_venta").select("*").eq("venta_id", str(venta_id)).execute()
        detalles = resp.data or []
    except Exception as exc:
        st.error(f"No se pudo leer el detalle de venta: {exc}")
        return False
    for det in detalles:
        producto_id = det.get("producto_id")
        cantidad = float(limpiar_numero(det.get("cantidad")) or 0)
        if not producto_id or cantidad <= 0:
            continue
        prod = refrescar_producto_por_id(producto_id)
        if prod is None:
            continue
        nueva_cant = float(obtener_existencia_producto(prod)) + cantidad
        actualizar_existencia_producto(prod, nueva_cant)
        prod2 = refrescar_producto_por_id(producto_id)
        if prod2 is None:
            prod2 = prod
        sincronizar_producto_inventario(prod2, ahora_str(), f"Reintegro por venta {venta_id}")
        registrar_movimiento_inventario(producto_id, obtener_nombre_producto(prod2), "reversa_venta", "ventas", venta_id, cantidad, float(limpiar_numero(det.get("costo_unitario")) or 0), "Reversa por anulación/eliminación de venta")
        
        # Reintegrar lote en inventario_lotes para restablecer el costo base FIFO
        try:
            supabase.table("inventario_lotes").insert({
                "producto_id": str(producto_id),
                "producto": obtener_nombre_producto(prod2),
                "compra_id": None,
                "cantidad_inicial": cantidad,
                "cantidad_restante": cantidad,
                "costo_unitario": float(limpiar_numero(det.get("costo_unitario")) or 0.0),
                "fecha_compra": date.today().isoformat(),
                "activo": True,
                "empresa_id": obtener_tenant_actual()
            }).execute()
        except Exception:
            pass

        if marcar_detalle_anulado and det.get("id"):
            try:
                supabase.table("detalle_venta").update({"anulado": True}).eq("id", det.get("id")).execute()
            except Exception:
                pass
    return True


def eliminar_venta_completa_app(venta_id: Any) -> bool:
    if not revertir_inventario_de_venta(venta_id, marcar_detalle_anulado=False):
        return False
    try:
        try:
            cxc = supabase.table("cuentas_por_cobrar").select("id").eq("venta_id", str(venta_id)).execute().data or []
            for row in cxc:
                supabase.table("abonos_credito").delete().eq("cuenta_id", str(row.get("id"))).execute()
            supabase.table("cuentas_por_cobrar").delete().eq("venta_id", str(venta_id)).execute()
        except Exception:
            pass
        for tabla in ["ventas_pagos", "detalle_venta"]:
            try:
                supabase.table(tabla).delete().eq("venta_id", str(venta_id)).execute()
            except Exception:
                pass
        ok = eliminar("ventas", venta_id)
        if ok:
            registrar_auditoria("eliminar_venta_completa", "ventas", f"venta_id={venta_id}")
        return ok
    except Exception as exc:
        st.error(f"No se pudo eliminar la venta completa: {exc}")
        return False


def anular_venta_completa_app(venta_id: Any, motivo: str = "") -> bool:
    if not revertir_inventario_de_venta(venta_id, marcar_detalle_anulado=True):
        return False
    try:
        venta_actual = supabase.table("ventas").select("*").eq("id", str(venta_id)).execute().data or []
        if not venta_actual:
            return False
            
        venta = venta_actual[0]
        total_v = float(venta.get("total") or 0)
        subtotal_v = float(venta.get("subtotal") or total_v)
        itbis_v = float(venta.get("itbis_total") or 0)
        metodo_pago = str(venta.get("metodo_pago") or "efectivo").lower()
        emp_id = venta.get("empresa_id") or obtener_tenant_actual()
        
        # 1. Asiento de Nota de Crédito (Reversión positiva de doble partida)
        if total_v > 0:
            if metodo_pago in ["efectivo"]:
                cuenta_credito_cod, cuenta_credito_nom = "1101", "Efectivo / Caja"
            elif metodo_pago in ["transferencia", "tarjeta"]:
                cuenta_credito_cod, cuenta_credito_nom = "1102", "Banco / Depósito"
            elif metodo_pago in ["credito"]:
                cuenta_credito_cod, cuenta_credito_nom = "1201", "Cuentas por Cobrar"
            else:
                cuenta_credito_cod, cuenta_credito_nom = "1101", "Efectivo / Caja"

            ingreso_base = total_v - itbis_v if itbis_v > 0 else total_v

            ncf_nota = ""
            if bool(venta.get("es_factura_fiscal")):
                try:
                    sec_resp = supabase.table("secuencia_ncf").select("*").eq("tipo_comprobante", "E34").eq("activa", True).execute()
                    if sec_resp.data:
                        sec = sec_resp.data[0]
                        sec_id = sec.get("id")
                        curr = int(sec.get("secuencia_actual") or 1)
                        pref = str(sec.get("prefijo") or "E34")
                        ncf_nota = f"{pref}{curr:08d}"
                        supabase.table("secuencia_ncf").update({"secuencia_actual": curr + 1}).eq("id", sec_id).execute()
                except Exception:
                    ncf_nota = f"E34-REV-{str(venta_id)[:8]}"

            try:
                supabase.table("notas_credito").insert(json_safe_payload({
                    "ncf_nota": ncf_nota or f"NC-{str(venta_id)[:8]}",
                    "venta_id": str(venta_id),
                    "monto": total_v,
                    "motivo": motivo or "Anulación",
                    "fecha": datetime.now().isoformat(),
                    "usuario": nombre_usuario_actual(),
                    "empresa_id": emp_id,
                })).execute()
            except Exception:
                pass

            try:
                if ingreso_base > 0:
                    supabase.table("movimientos_contables").insert(json_safe_payload({
                        "empresa_id": emp_id,
                        "fecha": datetime.now().isoformat(),
                        "modulo": "notas_credito",
                        "referencia_id": str(venta_id),
                        "cuenta_codigo": "4101",
                        "cuenta_nombre": "Ingresos por Ventas",
                        "tipo_cuenta": "ingreso",
                        "debito": ingreso_base,
                        "credito": 0.0,
                        "descripcion": f"Reversión Ingreso por NC {ncf_nota or venta_id}"
                    })).execute()

                if itbis_v > 0:
                    supabase.table("movimientos_contables").insert(json_safe_payload({
                        "empresa_id": emp_id,
                        "fecha": datetime.now().isoformat(),
                        "modulo": "notas_credito",
                        "referencia_id": str(venta_id),
                        "cuenta_codigo": "2102",
                        "cuenta_nombre": "ITBIS por Pagar",
                        "tipo_cuenta": "pasivo",
                        "debito": itbis_v,
                        "credito": 0.0,
                        "descripcion": f"Reversión ITBIS por NC {ncf_nota or venta_id}"
                    })).execute()

                supabase.table("movimientos_contables").insert(json_safe_payload({
                    "empresa_id": emp_id,
                    "fecha": datetime.now().isoformat(),
                    "modulo": "notas_credito",
                    "referencia_id": str(venta_id),
                    "cuenta_codigo": cuenta_credito_cod,
                    "cuenta_nombre": cuenta_credito_nom,
                    "tipo_cuenta": "activo",
                    "debito": 0.0,
                    "credito": total_v,
                    "descripcion": f"Crédito NC {ncf_nota or venta_id} — {cuenta_credito_nom}"
                })).execute()
            except Exception:
                pass

        try:
            supabase.table("ventas_pagos").update({"anulado": True}).eq("venta_id", str(venta_id)).execute()
        except Exception:
            pass
            
        ok = actualizar("ventas", venta_id, {
            "anulado": True,
            "motivo_anulacion": motivo or "Anulada manualmente",
            "estado": "anulada",
        })
        if ok:
            registrar_auditoria("anular_venta_completa", "ventas", f"venta_id={venta_id}")
        return ok
    except Exception as exc:
        st.error(f"No se pudo anular la venta completa: {exc}")
        return False


def obtener_costo_desde_inventario(producto: str) -> float:
    """
    Toma el costo en vivo directamente desde la tabla productos.
    """
    prod = get_producto_por_nombre(producto)
    if prod is not None:
        costo = limpiar_numero(prod.get("costo")) or limpiar_numero(prod.get("costo_unitario")) or 0.0
        return float(costo)
    return 0.0


def obtener_existencia_desde_inventario(producto: str) -> float:
    """
    Toma la existencia en vivo directamente desde la tabla productos.
    """
    prod = get_producto_por_nombre(producto)
    if prod is not None:
        return float(obtener_existencia_producto(prod))
    return 0.0

def registrar_perdida(fecha_mov, producto, cantidad, costo_unitario, tipo_perdida, observacion="", estado="pendiente", hora=None, reportado_por=None, persona_involucrada=None) -> bool:
    cantidad = float(cantidad)
    costo_unitario = float(costo_unitario)
    valor = cantidad * costo_unitario
    payload = {
        "fecha": str(fecha_mov),
        "producto": limpiar_texto(producto),
        "cantidad": cantidad,
        "costo_unitario": costo_unitario,
        "valor": valor,
        "tipo_perdida": tipo_perdida,
        "observacion": observacion,
        "estado": estado,
    }
    if hora is not None:
        payload["hora"] = hora
    if reportado_por is not None:
        payload["reportado_por"] = reportado_por
    else:
        payload["reportado_por"] = nombre_usuario_actual()
    if persona_involucrada is not None:
        payload["persona_involucrada"] = persona_involucrada
    return insertar("perdidas", payload)




def leer_pagos_empleados_actualizados() -> pd.DataFrame:
    """Lee los pagos de empleados directamente desde Supabase para que el Dashboard se actualice en vivo."""
    try:
        resp = supabase.table("adelantos_empleados").select("*").execute()
        df = pd.DataFrame(resp.data or [])
        if not df.empty and "fecha" in df.columns:
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
        return df
    except Exception:
        return DATA.get("adelantos_empleados", pd.DataFrame()).copy()


def obtener_texto_clasificacion_pago(df: pd.DataFrame) -> pd.Series:
    texto = pd.Series([""] * len(df), index=df.index)
    for col in ["tipo_pago", "concepto", "detalle", "observacion", "descripción", "descripcion", "tipo", "categoria"]:
        if col in df.columns:
            texto = texto + " " + df[col].astype(str)
    return texto.apply(normalizar_texto)


def obtener_empleados_fijos_periodo(empleados_df: pd.DataFrame, desde, hasta) -> float:
    """
    El sueldo del empleado NO se descuenta automático.
    Solo se suma lo pagado realmente en la tabla adelantos_empleados.
    Todo pago que no sea comisión/bono/variable se trata como empleado fijo.
    """
    pagos = leer_pagos_empleados_actualizados()
    if pagos.empty:
        return 0.0

    pagos_f = filtrar_por_fechas(pagos, desde, hasta).copy()
    if pagos_f.empty or "monto" not in pagos_f.columns:
        return 0.0

    pagos_f["monto"] = pd.to_numeric(pagos_f["monto"], errors="coerce").fillna(0)
    texto = obtener_texto_clasificacion_pago(pagos_f)

    mask_variable = texto.str.contains("variable|comision|comisión|bono|incentivo", na=False)
    return float(pagos_f.loc[~mask_variable, "monto"].sum())



def obtener_empleados_variables_periodo(gastos_df: pd.DataFrame, desde, hasta) -> float:
    """
    Solo se suman pagos variables reales: comisión, bono, incentivo o variable.
    """
    total = 0.0

    pagos = leer_pagos_empleados_actualizados()
    if not pagos.empty:
        pagos_f = filtrar_por_fechas(pagos, desde, hasta).copy()
        if not pagos_f.empty and "monto" in pagos_f.columns:
            pagos_f["monto"] = pd.to_numeric(pagos_f["monto"], errors="coerce").fillna(0)
            texto = obtener_texto_clasificacion_pago(pagos_f)
            mask_var = texto.str.contains("variable|comision|comisión|bono|incentivo", na=False)
            total += float(pagos_f.loc[mask_var, "monto"].sum())

    if not gastos_df.empty and "categoria" in gastos_df.columns:
        temp = filtrar_por_fechas(gastos_df, desde, hasta).copy()
        if not temp.empty:
            temp["categoria"] = temp["categoria"].astype(str).apply(normalizar_texto)
            temp = temp[temp["categoria"] == "nomina variable"]
            total += suma_col(temp, "monto")

    return float(total)



def obtener_gastos_fijos_variables(gastos_df: pd.DataFrame, desde, hasta):
    temp = filtrar_por_fechas(gastos_df, desde, hasta).copy()
    if temp.empty or "tipo" not in temp.columns:
        return 0.0, 0.0
    temp["tipo"] = temp["tipo"].astype(str).apply(normalizar_texto)
    fijos = suma_col(temp[temp["tipo"] == "fijo"], "monto")
    variables = suma_col(temp[temp["tipo"] == "variable"], "monto")
    return fijos, variables



def analisis_negocio(ventas, compras, gastos_fijos, gastos_variables, empleados_fijos, empleados_variables, perdidas, utilidad_neta):
    mensajes: list[str] = []

    if utilidad_neta > 0:
        mensajes.append("🟢 El negocio está dejando utilidad neta positiva.")
    elif utilidad_neta == 0:
        mensajes.append("🟡 El negocio quedó en equilibrio, sin ganancia neta.")
    else:
        mensajes.append("🔴 El negocio está quedando con pérdida neta.")

    if ventas > 0:
        porcentaje_perdidas = (perdidas / ventas) * 100
        if porcentaje_perdidas >= 8:
            mensajes.append(f"🔴 Las pérdidas representan {porcentaje_perdidas:.2f}% de las ventas. Está alto.")
        elif porcentaje_perdidas >= 3:
            mensajes.append(f"🟡 Las pérdidas representan {porcentaje_perdidas:.2f}% de las ventas.")
        else:
            mensajes.append(f"🟢 Las pérdidas representan {porcentaje_perdidas:.2f}% de las ventas.")
    else:
        mensajes.append("⚪ No hay ventas en el período seleccionado.")

    gasto_total = gastos_fijos + gastos_variables + empleados_fijos + empleados_variables
    if ventas > 0 and (gasto_total / ventas) > 0.7:
        mensajes.append("🟡 Tus gastos están consumiendo más del 70% de las ventas.")

    if compras > ventas and ventas > 0:
        mensajes.append("🟡 Las compras superan las ventas en el período. Revísalo.")

    return mensajes



def guardar_snapshot_estado_resultados(
    fecha,
    desde,
    hasta,
    ventas,
    compras,
    costo_ventas,
    utilidad_bruta,
    gastos_fijos,
    gastos_variables,
    empleados_fijos,
    empleados_variables,
    perdidas,
    retiros_dueno,
    utilidad_neta,
):
    return insertar(
        "estado_resultados",
        {
            "fecha": str(fecha),
            "desde": str(desde),
            "hasta": str(hasta),
            "ventas": float(ventas),
            "compras": float(compras),
            "costo_ventas": float(costo_ventas),
            "utilidad_bruta": float(utilidad_bruta),
            "gastos_fijos": float(gastos_fijos),
            "gastos_variables": float(gastos_variables),
            "empleados_fijos": float(empleados_fijos),
            "empleados_variables": float(empleados_variables),
            "perdidas": float(perdidas),
            "retiros_dueno": float(retiros_dueno),
            "utilidad_neta": float(utilidad_neta),
        },
    )



def columnas_disponibles(df: pd.DataFrame, candidatas: Iterable[str]) -> list[str]:
    return [c for c in candidatas if c in df.columns]



def rango_periodo(tipo_periodo: str):
    hoy = date.today()
    if tipo_periodo == "Día":
        return hoy, hoy
    if tipo_periodo == "Mes actual":
        return hoy.replace(day=1), hoy
    if tipo_periodo == "Año actual":
        return date(hoy.year, 1, 1), hoy
    return hoy.replace(day=1), hoy




def calcular_valores_inventario_pro():
    """
    Calcula inventario a costo, inventario a venta y ganancia potencial.
    No se queda con la primera columna que exista; elige la columna con valores reales.
    Fuente principal: productos. Respaldo: inventario_actual.
    """
    fuentes = []
    try:
        fuentes.append(("productos", leer_actualizado("productos")))
    except Exception:
        fuentes.append(("productos", DATA.get("productos", pd.DataFrame()).copy()))
    try:
        fuentes.append(("inventario_actual", leer_actualizado("inventario_actual")))
    except Exception:
        fuentes.append(("inventario_actual", DATA.get("inventario_actual", pd.DataFrame()).copy()))

    def _serie_num(df, col):
        try:
            return pd.to_numeric(df[col].apply(lambda x: limpiar_numero(x)), errors="coerce").fillna(0)
        except Exception:
            return pd.Series([0] * len(df))

    def _mejor_columna(df, candidatos):
        mejores = []
        for c in candidatos:
            if c in df.columns:
                s = _serie_num(df, c)
                suma_pos = float(s.clip(lower=0).sum())
                cant_pos = int((s > 0).sum())
                maximo = float(s.max()) if len(s) else 0
                mejores.append((c, suma_pos, cant_pos, maximo))
        if not mejores:
            return None
        # Elegir columna con más valores positivos y mayor suma real
        mejores = sorted(mejores, key=lambda x: (x[2], x[1], x[3]), reverse=True)
        col = mejores[0][0]
        # Si la mejor está totalmente en cero, devolverla solo como último recurso
        return col

    # Obtener nombres de productos válidos para filtrar inventario_actual
    productos_df = fuentes[0][1] if len(fuentes) > 0 else None
    nombres_productos_validos = set()
    if productos_df is not None and not productos_df.empty:
        nombres_productos_validos = set(productos_df["nombre"].dropna().astype(str).str.strip().apply(normalizar_texto))

    for nombre_fuente, df in fuentes:
        if df is None or df.empty:
            continue

        # Filtrar inventario_actual si corresponde para no incluir huérfanos
        if nombre_fuente == "inventario_actual" and not df.empty:
            if "producto" in df.columns:
                df = df[df["producto"].dropna().astype(str).str.strip().apply(normalizar_texto).isin(nombres_productos_validos)].copy()
            elif "nombre" in df.columns:
                df = df[df["nombre"].dropna().astype(str).str.strip().apply(normalizar_texto).isin(nombres_productos_validos)].copy()
            
            if df.empty:
                continue

        col_stock = _mejor_columna(df, [
            "stock", "cantidad", "existencia", "existencia_sistema", "existencias",
            "inventario", "inventario_actual", "disponible"
        ])
        col_costo = _mejor_columna(df, [
            "costo", "costo_unitario", "costo_promedio", "precio_compra",
            "precio_costo", "ultimo_costo", "costo_producto"
        ])
        col_precio = _mejor_columna(df, [
            "precio_venta", "precio", "precio_normal", "precio_publico",
            "precio_v", "precioespecial", "precio_especial", "venta", "pvp"
        ])

        if not col_stock:
            continue

        temp = df.copy()
        temp["_stock"] = _serie_num(temp, col_stock)
        temp["_costo"] = _serie_num(temp, col_costo) if col_costo else pd.Series([0] * len(temp))
        temp["_precio"] = _serie_num(temp, col_precio) if col_precio else pd.Series([0] * len(temp))

        temp["_stock_valor"] = temp["_stock"].clip(lower=0)

        inv_costo = float((temp["_stock_valor"] * temp["_costo"]).sum())
        inv_venta = float((temp["_stock_valor"] * temp["_precio"]).sum())
        ganancia_potencial = inv_venta - inv_costo

        if inv_costo > 0 or inv_venta > 0:
            return {
                "fuente": f"{nombre_fuente} | stock={col_stock} | costo={col_costo or 'no encontrado'} | precio={col_precio or 'no encontrado'}",
                "inventario_costo": inv_costo,
                "inventario_venta": inv_venta,
                "ganancia_potencial_inventario": ganancia_potencial,
            }

    return {
        "fuente": "No se encontraron columnas con valores de stock/costo/precio",
        "inventario_costo": 0.0,
        "inventario_venta": 0.0,
        "ganancia_potencial_inventario": 0.0,
    }



def calcular_total_dinero_inventario() -> float:
    """
    Calcula el valor total del inventario a costo.
    Usa inventario_actual y, si está vacío o no tiene valores, usa productos.
    """
    try:
        return float(calcular_valores_inventario_pro().get("inventario_costo", 0.0))
    except Exception:
        return 0.0


def calcular_utilidad_neta_operativa_periodo(desde, hasta, utilidad_bruta_manual=0.0) -> dict:
    """
    Fuente única para Dashboard y Distribución.
    Regla:
    Utilidad bruta + ajuste manual
    - gastos fijos
    - gastos variables
    - empleados fijos
    - empleados variables
    - pérdidas de mercancía
    = utilidad neta operativa

    Gastos/retiros del dueño NO bajan la utilidad neta operativa.
    Solo se descuentan de la parte del dueño luego del reparto.
    """
    ventas_df = obtener_ventas_periodo_actualizadas(desde, hasta)
    gastos_fijos, gastos_variables = obtener_gastos_fijos_variables(DATA["gastos"], desde, hasta)
    empleados_fijos = obtener_empleados_fijos_periodo(DATA["empleados"], desde, hasta)
    empleados_variables = obtener_empleados_variables_periodo(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)

    utilidad_bruta_ventas = obtener_utilidad_bruta_periodo(ventas_df)
    utilidad_bruta_total = float(utilidad_bruta_ventas) + float(utilidad_bruta_manual or 0)
    perdidas_tot = suma_col(perdidas_df, "valor")
    retiros_dueno = suma_col(dueno_df, "monto")

    utilidad_neta = (
        utilidad_bruta_total
        - gastos_fijos
        - gastos_variables
        - empleados_fijos
        - empleados_variables
        - perdidas_tot
    )

    utilidad_distribuible = max(utilidad_neta, 0)

    return {
        "ventas_df": ventas_df,
        "utilidad_bruta_ventas": float(utilidad_bruta_ventas),
        "utilidad_bruta_total": float(utilidad_bruta_total),
        "gastos_fijos": float(gastos_fijos),
        "gastos_variables": float(gastos_variables),
        "empleados_fijos": float(empleados_fijos),
        "empleados_variables": float(empleados_variables),
        "perdidas": float(perdidas_tot),
        "retiros_dueno": float(retiros_dueno),
        "utilidad_neta": float(utilidad_neta),
        "utilidad_distribuible": float(utilidad_distribuible),
    }


def resumen_financiero_periodo(desde, hasta, utilidad_bruta_manual: float = 0.0) -> dict[str, float]:
    ventas_df = obtener_ventas_periodo_actualizadas(desde, hasta)
    compras_df = filtrar_por_fechas(DATA["compras"], desde, hasta)
    gastos_df = filtrar_por_fechas(DATA["gastos"], desde, hasta)
    perdidas_df = filtrar_por_fechas(DATA["perdidas"], desde, hasta)
    dueno_df = filtrar_por_fechas(DATA["gastos_dueno"], desde, hasta)
    adelantos_df = filtrar_por_fechas(DATA["adelantos_empleados"], desde, hasta)

    ventas_tot = suma_col(ventas_df, "total")
    compras_tot = suma_col(compras_df, "monto")
    gastos_fijos, gastos_variables = obtener_gastos_fijos_variables(DATA["gastos"], desde, hasta)
    empleados_fijos = obtener_empleados_fijos_periodo(DATA["empleados"], desde, hasta)
    empleados_variables = obtener_empleados_variables_periodo(DATA["gastos"], desde, hasta)
    perdidas_tot = suma_col(perdidas_df, "valor")
    retiros_tot = suma_col(dueno_df, "monto")
    adelantos_tot = suma_col(adelantos_df, "monto")
    utilidad_bruta_ventas = obtener_utilidad_bruta_periodo(ventas_df)
    utilidad_bruta = float(utilidad_bruta_ventas) + float(utilidad_bruta_manual)

    utilidad_neta = (
        float(utilidad_bruta)
        - gastos_fijos
        - gastos_variables
        - empleados_fijos
        - empleados_variables
        - perdidas_tot
    )
    return {
        "ventas": ventas_tot,
        "compras": compras_tot,
        "gastos_fijos": gastos_fijos,
        "gastos_variables": gastos_variables,
        "empleados_fijos": empleados_fijos,
        "empleados_variables": empleados_variables,
        "adelantos": adelantos_tot,
        "perdidas": perdidas_tot,
        "retiros_dueno": retiros_tot,
        "utilidad_bruta_ventas": float(utilidad_bruta_ventas),
        "utilidad_bruta_manual": float(utilidad_bruta_manual),
        "utilidad_bruta": float(utilidad_bruta),
        "utilidad_neta": utilidad_neta,
        "dueno_65": utilidad_neta * 0.65,
        "gerente_35": utilidad_neta * 0.35,
    }


def serie_periodica(df: pd.DataFrame, columna: str, frecuencia: str = "M") -> pd.DataFrame:
    if df.empty or "fecha" not in df.columns or columna not in df.columns:
        etiqueta = "periodo"
        return pd.DataFrame(columns=[etiqueta, "valor"])
    temp = df.copy()
    temp["fecha"] = pd.to_datetime(temp["fecha"], errors="coerce")
    temp[columna] = pd.to_numeric(temp[columna], errors="coerce").fillna(0)
    etiqueta = "periodo"
    temp[etiqueta] = temp["fecha"].dt.to_period(frecuencia).astype(str)
    out = temp.groupby(etiqueta, as_index=False)[columna].sum()
    out.columns = [etiqueta, "valor"]
    return out




def usuario_id_actual():
    user = usuario_sesion()
    return user.get("id")




def json_safe_value(valor):
    """Convierte valores numpy/pandas a tipos JSON normales para Supabase."""
    try:
        import numpy as np
        if isinstance(valor, (np.integer,)):
            return int(valor)
        if isinstance(valor, (np.floating,)):
            return float(valor)
        if isinstance(valor, (np.bool_,)):
            return bool(valor)
    except Exception:
        pass

    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass

    if isinstance(valor, dict):
        return {str(k): json_safe_value(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [json_safe_value(v) for v in valor]
    if isinstance(valor, tuple):
        return [json_safe_value(v) for v in valor]

    return valor


def json_safe_payload(payload: dict) -> dict:
    """Limpia un diccionario antes de enviarlo a Supabase."""
    return {str(k): json_safe_value(v) for k, v in payload.items()}

def aplicar_venta_pos(payload: dict):
    """Insert a POS sale into the `ventas` table, adding the `es_credito` flag.
    Automatically registers double-entry accounting entries in movimientos_contables.
    """
    payload = payload.copy()
    payload["es_credito"] = payload.get("pago_credito", 0) > 0
    venta_id_nuevo = None
    try:
        safe_payload = json_safe_payload(payload)
        resp = supabase.table("ventas").insert(safe_payload).execute()
        # Obtener el ID de la venta recién insertada
        if resp.data:
            venta_id_nuevo = resp.data[0].get("id")
    except Exception as e:
        st.error(f"Error inserting venta POS: {e}")
        raise

    # ── Asientos Contables Automáticos ──────────────────────────────────
    # Se ejecutan de forma silenciosa (sin bloquear si falla)
    try:
        total_v      = float(payload.get("total") or 0)
        subtotal_v   = float(payload.get("subtotal") or total_v)
        itbis_v      = float(payload.get("itbis_total") or 0)
        metodo_pago  = str(payload.get("metodo_pago") or "efectivo").lower()
        empresa_id   = payload.get("empresa_id") or obtener_tenant_actual()
        ref_id       = str(venta_id_nuevo or "pos")
        ncf_ref      = str(payload.get("ncf") or payload.get("numero_factura") or ref_id)
        usuario_v    = payload.get("usuario") or nombre_usuario_actual()
        fecha_v      = datetime.now().isoformat()

        # Determinar cuenta de débito según método de pago
        if metodo_pago in ["efectivo"]:
            cuenta_debito = "1101 - Efectivo / Caja"
        elif metodo_pago in ["transferencia", "tarjeta"]:
            cuenta_debito = "1102 - Banco / Depósito"
        elif metodo_pago in ["credito"]:
            cuenta_debito = "1201 - Cuentas por Cobrar"
        else:
            cuenta_debito = "1101 - Efectivo / Caja"

        asientos = []

        # Asiento 1: DÉBITO — Cuenta de cobro (Efectivo/Banco/CxC)
        if total_v > 0:
            asientos.append({
                "empresa_id": empresa_id,
                "fecha": fecha_v,
                "concepto": f"Venta POS {ncf_ref} — {cuenta_debito}",
                "debito": total_v,
                "credito": 0.0,
                "referencia": f"venta:{ref_id}",
                "modulo": "ventas",
                "usuario": usuario_v,
            })

        # Asiento 2: CRÉDITO — Ingresos por Ventas (sin ITBIS)
        ingreso_base = subtotal_v - itbis_v if itbis_v > 0 else subtotal_v
        if ingreso_base > 0:
            asientos.append({
                "empresa_id": empresa_id,
                "fecha": fecha_v,
                "concepto": f"Ingreso por Venta {ncf_ref}",
                "debito": 0.0,
                "credito": ingreso_base,
                "referencia": f"venta:{ref_id}",
                "modulo": "ventas",
                "usuario": usuario_v,
            })

        # Asiento 3: CRÉDITO — ITBIS por Pagar (si aplica)
        if itbis_v > 0:
            asientos.append({
                "empresa_id": empresa_id,
                "fecha": fecha_v,
                "concepto": f"ITBIS por Pagar Venta {ncf_ref}",
                "debito": 0.0,
                "credito": itbis_v,
                "referencia": f"venta_itbis:{ref_id}",
                "modulo": "ventas",
                "usuario": usuario_v,
            })

        # Insertar todos los asientos de una vez
        for asiento in asientos:
            try:
                supabase.table("movimientos_contables").insert(json_safe_payload(asiento)).execute()
            except Exception:
                pass  # silencioso — no bloquear la venta

    except Exception:
        pass  # silencioso — los asientos son informativos




def crear_cliente_rapido_pos(nombre, telefono="", documento="", direccion="", email=""):
    """Crea un cliente desde el POS usando la tabla clientes existente."""
    nombre = limpiar_texto(nombre)
    if not nombre:
        return None

    intentos = [
        {
            "nombre": nombre,
            "telefono": limpiar_texto(telefono),
            "documento": limpiar_texto(documento),
            "direccion": limpiar_texto(direccion),
            "email": limpiar_texto(email),
            "activo": True,
        },
        {
            "nombre": nombre,
            "telefono": limpiar_texto(telefono),
            "documento": limpiar_texto(documento),
            "direccion": limpiar_texto(direccion),
        },
        {
            "nombre": nombre,
            "telefono": limpiar_texto(telefono),
        },
        {
            "nombre": nombre,
        },
    ]

    for payload in intentos:
        try:
            resp = supabase.table("clientes").insert(payload).execute()
            data = resp.data or []
            if data:
                return data[0]
        except Exception:
            continue

    st.error("No se pudo crear el cliente. Revisa las columnas de la tabla clientes en Supabase.")
    return None


def obtener_caja_abierta():
    usuario_id = usuario_id_actual()
    if not usuario_id:
        return None
    try:
        # Intentamos usar la caché de session_state a través de leer_tabla
        caja_df = leer_tabla("caja")
        if not caja_df.empty and "usuario_id" in caja_df.columns and "estado" in caja_df.columns:
            abiertas = caja_df[(caja_df["usuario_id"].astype(str) == str(usuario_id)) & (caja_df["estado"] == "abierta")]
            if not abiertas.empty:
                if "fecha_apertura" in abiertas.columns:
                    abiertas = abiertas.sort_values(by="fecha_apertura", ascending=False)
                return abiertas.iloc[0].to_dict()
            return None
    except Exception:
        pass
    try:
        resp = (
            supabase.table("caja")
            .select("*")
            .eq("usuario_id", str(usuario_id))
            .eq("estado", "abierta")
            .order("fecha_apertura", desc=True)
            .limit(1)
            .execute()
        )
        filas = resp.data or []
        return filas[0] if filas else None
    except Exception:
        return None


def abrir_caja(monto_inicial: float, observacion: str = "") -> tuple[bool, str]:
    if obtener_caja_abierta() is not None:
        return False, "Ya tienes una caja abierta."
    usuario_id = usuario_id_actual()
    if not usuario_id:
        return False, "No se encontró el usuario actual."
    try:
        supabase.table("caja").insert({
            "usuario_id": str(usuario_id),
            "fecha_apertura": datetime.now().isoformat(),
            "monto_inicial": float(monto_inicial),
            "estado": "abierta",
            "dia_operativo": ahora_str(),
            "observacion": observacion,
            "anulado": False,
            "empresa_id": obtener_tenant_actual(),
        }).execute()
        registrar_auditoria("abrir_caja", "caja", f"monto_inicial={monto_inicial}")
        return True, "Caja abierta correctamente."
    except Exception as exc:
        return False, f"No se pudo abrir caja: {exc}"


def cerrar_caja(caja_row: dict, monto_cierre: float, observacion: str = "") -> tuple[bool, str]:
    try:
        monto_inicial = float(limpiar_numero(caja_row.get("monto_inicial")) or 0)
        diferencia = float(monto_cierre) - monto_inicial
        supabase.table("caja").update({
            "fecha_cierre": datetime.now().isoformat(),
            "monto_cierre": float(monto_cierre),
            "diferencia": float(diferencia),
            "observacion": observacion or caja_row.get("observacion") or "",
            "estado": "cerrada",
        }).eq("id", caja_row["id"]).execute()
        insertar("cierre_caja", {
            "fecha": datetime.now().isoformat(),
            "apertura": monto_inicial,
            "efectivo_sistema": monto_inicial,
            "efectivo_fisico": float(monto_cierre),
            "diferencia": float(diferencia),
            "detalle": observacion,
        })
        registrar_auditoria("cerrar_caja", "caja", f"id={caja_row['id']} monto_cierre={monto_cierre}")
        return True, "Caja cerrada correctamente."
    except Exception as exc:
        return False, f"No se pudo cerrar caja: {exc}"



def html_escape(valor: Any) -> str:
    txt = limpiar_texto(valor)
    return (
        txt.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def construir_html_impresion(post_venta: dict, tipo: str = "factura") -> str:
    _cfg = obtener_configuracion()
    negocio = _cfg.get("negocio_nombre") or "Sistema de Negocio PRO"
    telefono_neg = limpiar_texto(_cfg.get("telefono") or "")
    rnc_neg = limpiar_texto(_cfg.get("rnc") or "")
    direccion_neg = limpiar_texto(_cfg.get("direccion") or "")
    titulo = "TICKET" if tipo == "ticket" else "FACTURA"
    items = post_venta.get("items") or []
    filas = ""
    for item in items:
        filas += f"""
        <tr>
            <td>{html_escape(nombre_item(item))}</td>
            <td style='text-align:center'>{float(item.get('cantidad', 0)):.0f}</td>
            <td style='text-align:right'>RD$ {float(item.get('precio_unitario', 0)):,.2f}</td>
            <td style='text-align:right'>RD$ {float(item.get('total_linea', 0)):,.2f}</td>
        </tr>
        """
    if not filas:
        filas = "<tr><td colspan='4' style='text-align:center'>Sin detalle</td></tr>"

    ncf_val = post_venta.get("ncf") or ""
    ncf_txt = html_escape(ncf_val) if ncf_val else html_escape(post_venta.get("numero_factura") or post_venta.get("venta_id") or "")
    
    # Extraer variables DGII
    rnc_cli_val = post_venta.get("rnc_cliente") or ""
    rnc_cliente_txt = html_escape(rnc_cli_val)
    subtotal_val = float(post_venta.get("subtotal") or post_venta.get("total", 0.0))
    itbis_val = float(post_venta.get("itbis_total") or 0.0)
    tipo_comp = post_venta.get("tipo_comprobante") or ""
    
    # Si es NCF de la DGII, forzamos que el título diga FACTURA VALIDA PARA...
    if ncf_val and ncf_val.upper().startswith("E31"):
        titulo = "FACTURA DE CRÉDITO FISCAL ELECTRÓNICA (E31)"
    elif ncf_val and ncf_val.upper().startswith("E32"):
        titulo = "FACTURA DE CONSUMO ELECTRÓNICA (E32)"
    elif ncf_val and ncf_val.upper().startswith("E45"):
        titulo = "FACTURA GUBERNAMENTAL ELECTRÓNICA (E45)"
    elif ncf_val and ncf_val.upper().startswith("E34"):
        titulo = "NOTA DE CRÉDITO ELECTRÓNICA (E34)"
    elif ncf_val and ncf_val.upper().startswith("B01"):
        titulo = "FACTURA DE CRÉDITO FISCAL (B01)"
    elif ncf_val and ncf_val.upper().startswith("B02"):
        titulo = "FACTURA DE CONSUMO (B02)"
    elif ncf_val and ncf_val.upper().startswith("B04"):
        titulo = "NOTA DE CRÉDITO (B04)"
    elif ncf_val:
        titulo = f"COMPROBANTE {tipo_comp}"
        
    cliente = html_escape(post_venta.get("cliente_nombre") or "Venta general")
    metodo = html_escape(post_venta.get("metodo_pago") or "")
    fecha_txt = html_escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    total = float(post_venta.get("total", 0) or 0)
    cambio = float(post_venta.get("cambio", 0) or 0)
    nota_txt = limpiar_texto(post_venta.get("nota") or "")

    logo_url = logo_actual() or AM_LOGO_B64
    logo_img = f"<img src='{logo_url}' style='max-width: 150px; margin-bottom: 10px; border-radius: 8px;'/>" if logo_url else ""

    # Información del negocio para el encabezado (teléfono, rnc, dirección)
    info_negocio_extra = ""
    if telefono_neg:
        info_negocio_extra += f"<p style='margin:2px 0;font-size:13px;'>📞 {html_escape(telefono_neg)}</p>"
    if rnc_neg:
        info_negocio_extra += f"<p style='margin:2px 0;font-size:13px;'><strong>RNC:</strong> {html_escape(rnc_neg)}</p>"
    if direccion_neg:
        info_negocio_extra += f"<p style='margin:2px 0;font-size:12px;color:#555;'>{html_escape(direccion_neg)}</p>"

    # Metadatos gubernamentales (para E45)
    g_dep = post_venta.get("gubernamental_dependencia") or ""
    g_oc = post_venta.get("gubernamental_orden_compra") or ""
    info_gubernamental_extra = ""
    if g_dep or g_oc:
        if g_dep:
            info_gubernamental_extra += f"<p style='margin:2px 0;font-size:13px;'><strong>Dependencia:</strong> {html_escape(g_dep)}</p>"
        if g_oc:
            info_gubernamental_extra += f"<p style='margin:2px 0;font-size:13px;'><strong>Orden de Compra:</strong> {html_escape(g_oc)}</p>"

    return f"""
    <html>
    <head>
      <meta charset="utf-8" />
      <title>{titulo} - {html_escape(negocio)}</title>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; color: #111; }}
        .wrap {{ max-width: 800px; margin: 0 auto; }}
        h1,h2,h3,p {{ margin: 0 0 8px 0; }}
        .top {{ text-align: center; margin-bottom: 16px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ border-bottom: 1px solid #ddd; padding: 8px; font-size: 14px; }}
        th {{ background: #f7f7f7; text-align: left; }}
        .totales {{ margin-top: 18px; width: 100%; }}
        .totales td {{ border: none; padding: 6px 0; }}
        .right {{ text-align: right; }}
        .strong {{ font-weight: bold; }}
        @media print {{
          body {{ padding: 0; }}
          .no-print {{ display: none; }}
        }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="top">
          {logo_img}
          <h2 style="font-size:20px; margin-bottom:4px;">{html_escape(negocio)}</h2>
          {info_negocio_extra}
          <hr style="margin:10px 0;"/>
          <h1 style="font-size:18px;">{titulo}</h1>
          <p><strong>NCF:</strong> {ncf_txt}</p>
          <p><strong>Fecha:</strong> {fecha_txt}</p>
          <p><strong>Cliente:</strong> {cliente}</p>
          {f"<p><strong>RNC Cliente:</strong> {rnc_cliente_txt}</p>" if rnc_cliente_txt else ""}
          {info_gubernamental_extra}
          <p><strong>Método:</strong> {metodo}</p>
        </div>

        <table>
          <thead>
            <tr>
              <th>Producto</th>
              <th>Cant.</th>
              <th>Precio</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {filas}
          </tbody>
        </table>

        <table class="totales">
          {"<tr><td class='strong'>Subtotal</td><td class='right strong'>RD$ " + f"{subtotal_val:,.2f}" + "</td></tr>" if itbis_val > 0 else ""}
          {"<tr><td class='strong'>ITBIS (18%)</td><td class='right strong'>RD$ " + f"{itbis_val:,.2f}" + "</td></tr>" if itbis_val > 0 else ""}
          <tr><td class="strong">TOTAL A PAGAR</td><td class="right strong" style="font-size:16px;">RD$ {total:,.2f}</td></tr>
          <tr><td class="strong">Cambio</td><td class="right">RD$ {cambio:,.2f}</td></tr>
        </table>
        {f'''<div style="margin-top:18px; padding:10px 14px; background:#f8f9fa; border-left:4px solid #0066cc; border-radius:4px;"><p style="margin:0; font-size:13px; color:#333;"><strong>📝 Nota:</strong> {html_escape(nota_txt)}</p></div>''' if nota_txt else ""}
      </div>
    </body>
    </html>
    """


def lanzar_impresion_navegador(html_doc: str):
    """
    Abre una ventana imprimible. Si el navegador bloquea el pop-up,
    el usuario podrá imprimir desde la vista previa con el botón interno.
    """
    html_js = f"""
    <html>
    <body>
    <script>
      const contenido = {html_doc!r};
      const w = window.open('', '_blank');
      if (w) {{
        w.document.open();
        w.document.write(contenido);
        w.document.close();
        w.focus();
        setTimeout(() => {{
          w.print();
        }}, 500);
      }} else {{
        alert('El navegador bloqueó la ventana de impresión. Usa el botón Imprimir dentro de la vista previa.');
      }}
    </script>
    </body>
    </html>
    """
    components.html(html_js, height=80, width=300)

def generar_numero_factura_pos() -> str:
    """
    Genera una secuencia limpia de factura con prefijo VT:
    VT001, VT002, VT003...
    """
    try:
        ventas = leer_tabla("ventas")
    except Exception:
        ventas = DATA.get("ventas", pd.DataFrame()).copy()

    max_num = 0

    if not ventas.empty and "numero_factura" in ventas.columns:
        for val in ventas["numero_factura"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("VT"):
                num_part = txt.replace("VT", "")
                if num_part.isdigit():
                    try:
                        max_num = max(max_num, int(num_part))
                    except Exception:
                        pass
            elif txt.startswith("FAC-"):
                num_part = txt.replace("FAC-", "")
                if num_part.isdigit():
                    try:
                        max_num = max(max_num, int(num_part))
                    except Exception:
                        pass
            elif txt.isdigit():
                try:
                    max_num = max(max_num, int(txt))
                except Exception:
                    pass

    return f"VT{(max_num + 1):03d}"


def generar_numero_recibo_interno() -> str:
    """
    Genera una secuencia de recibo interno de ventas con prefijo V-:
    V-0000101, V-0000102...
    """
    try:
        ventas = leer_tabla("ventas")
    except Exception:
        ventas = DATA.get("ventas", pd.DataFrame()).copy()

    max_num = 0
    if not ventas.empty and "numero_factura" in ventas.columns:
        for val in ventas["numero_factura"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("V-"):
                num_part = txt.replace("V-", "")
                if num_part.isdigit():
                    try:
                        max_num = max(max_num, int(num_part))
                    except Exception:
                        pass
    return f"V-{(max_num + 1):07d}"


def generar_numero_compra() -> str:
    """
    Genera una secuencia limpia de compras con prefijo CP:
    CP001, CP002, CP003...
    """
    try:
        compras = leer_tabla("compras")
    except Exception:
        compras = DATA.get("compras", pd.DataFrame()).copy()

    max_num = 0

    if not compras.empty and "numero" in compras.columns:
        for val in compras["numero"].dropna().astype(str):
            txt = val.strip().upper()
            if txt.startswith("CP"):
                num_part = txt.replace("CP", "")
                if num_part.isdigit():
                    try:
                        max_num = max(max_num, int(num_part))
                    except Exception:
                        pass
            elif txt.startswith("COM-"):
                num_part = txt.replace("COM-", "")
                if num_part.isdigit():
                    try:
                        max_num = max(max_num, int(num_part))
                    except Exception:
                        pass
            elif txt.isdigit():
                try:
                    max_num = max(max_num, int(txt))
                except Exception:
                    pass

    return f"CP{(max_num + 1):03d}"

def mostrar_factura_pos(post_venta: dict):
    """
    Muestra factura/ticket visible y descargable para cajera y admin.
    Permite elegir el formato en pantalla y ofrece un único botón de impresión
    limpio que nunca es bloqueado por el navegador.
    """
    if not post_venta:
        return

    html_factura = construir_html_impresion(post_venta, "factura")
    html_ticket = construir_html_impresion(post_venta, "ticket")
    venta_ref = post_venta.get("numero_factura") or post_venta.get("venta_id") or "factura"

    st.markdown("### 🧾 Factura / Ticket")
    
    # Selector de formato único y limpio
    formato = st.radio(
        "Formato de impresión:",
        ["Ticket Térmico (80mm)", "Factura Completa (Carta/A4)"],
        horizontal=True,
        key=f"formato_impresion_{post_venta.get('venta_id')}"
    )

    # Cargar el HTML correspondiente
    html_seleccionado = html_ticket if "Ticket" in formato else html_factura

    html_preview = f"""
    <html>
    <head>
      <meta charset='utf-8'>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 12px; }}
        .toolbar {{
          position: sticky;
          top: 0;
          background: #ffffff;
          padding: 10px;
          border-bottom: 1px solid #ddd;
          z-index: 999;
          text-align: center;
        }}
        .btn {{
          padding: 10px 18px;
          border: none;
          border-radius: 6px;
          background: #0f766e;
          color: white;
          font-weight: bold;
          cursor: pointer;
          margin: 4px;
          font-family: Arial, sans-serif;
        }}
        @media print {{
          .toolbar {{ display: none; }}
          body {{ padding: 0; }}
        }}
      </style>
    </head>
    <body>
      <div class='toolbar'>
        <button class='btn' onclick='window.print()'>🖨️ Imprimir</button>
        <button class='btn' onclick='document.body.style.zoom="85%"'>Ajustar vista</button>
      </div>
      {html_seleccionado}
    </body>
    </html>
    """

    with st.expander("👁️ Ver factura antes de imprimir", expanded=True):
        components.html(html_preview, height=760, scrolling=True)
        st.info("Para imprimir: usa el botón verde 'Imprimir' dentro de la vista previa de arriba.")





def _monto_de_row(row, campos=("monto", "total", "valor", "importe")) -> float:
    for c in campos:
        try:
            v = limpiar_numero(row.get(c))
            if v is not None and float(v) != 0:
                return float(v)
        except Exception:
            pass
    return 0.0


def _cuenta_por_metodo_pro(metodo_pago: str, cuenta: str = "") -> str:
    cuenta_limpia = limpiar_texto(cuenta)
    if cuenta_limpia:
        return cuenta_limpia
    metodo = normalizar_texto(metodo_pago)
    if metodo == "efectivo":
        return "Efectivo negocio"
    if metodo in ["transferencia", "tarjeta", "banco"]:
        return "Banco"
    if metodo == "credito":
        return "Crédito pendiente"
    return "Pendiente"


def _agregar_movimiento(filas, fecha, tipo, origen, concepto, cuenta, entrada=0.0, salida=0.0, metodo_pago="", referencia="", detalle=""):
    cuenta = cuenta or "Pendiente"
    filas.append({
        "fecha": fecha,
        "tipo": tipo,
        "origen": origen,
        "concepto": concepto,
        "cuenta": cuenta,
        "metodo_pago": metodo_pago,
        "entrada": float(entrada or 0),
        "salida": float(salida or 0),
        "neto": float(entrada or 0) - float(salida or 0),
        "referencia": referencia,
        "detalle": detalle,
    })


def construir_historial_dinero_real() -> pd.DataFrame:
    filas = []

    # 1) Saldos iniciales de cuentas
    cuentas = leer_actualizado("cuentas_dinero")
    if not cuentas.empty:
        for _, r in cuentas.iterrows():
            saldo = float(limpiar_numero(r.get("saldo_inicial")) or 0)
            if saldo != 0:
                _agregar_movimiento(
                    filas,
                    r.get("created_at") or "",
                    "entrada",
                    "Saldo inicial",
                    f"Saldo inicial {r.get('nombre', '')}",
                    r.get("nombre", ""),
                    entrada=saldo,
                    metodo_pago=r.get("tipo", ""),
                    detalle=r.get("observacion", ""),
                )

    # 1.5) Capital base multi-tenant como saldo inicial de caja/banco
    capital_df = leer_actualizado("capital_base")
    if not capital_df.empty:
        if "activo" in capital_df.columns:
            capital_df = capital_df[capital_df["activo"] == True]
        for _, r in capital_df.iterrows():
            concepto_n = normalizar_texto(r.get("concepto") or "")
            origen_n = normalizar_texto(r.get("origen") or "")
            monto = float(r.get("monto") or r.get("valor") or r.get("total") or 0.0)
            if monto != 0:
                if "banco" in concepto_n or "banco" in origen_n or "transferencia" in concepto_n or "transferencia" in origen_n:
                    cuenta = "Banco"
                    metodo = "transferencia"
                else:
                    cuenta = "Efectivo negocio"
                    metodo = "efectivo"
                
                _agregar_movimiento(
                    filas,
                    r.get("fecha") or r.get("created_at") or "",
                    "entrada",
                    "Capital inicial",
                    f"Capital base: {r.get('concepto', '')}",
                    cuenta,
                    entrada=monto,
                    metodo_pago=metodo,
                    detalle=r.get("observacion", ""),
                )

    # 2) Ventas cobradas por ventas_pagos
    pagos = leer_actualizado("ventas_pagos")
    if not pagos.empty and "monto" in pagos.columns:
        metodo_col = "metodo" if "metodo" in pagos.columns else ("metodo_pago" if "metodo_pago" in pagos.columns else None)
        for _, r in pagos.iterrows():
            metodo = r.get(metodo_col) if metodo_col else r.get("metodo_pago", "")
            metodo_n = normalizar_texto(metodo)
            monto = float(limpiar_numero(r.get("monto")) or 0)
            if monto <= 0:
                continue
            if metodo_n == "credito":
                cuenta = "Crédito pendiente"
            else:
                cuenta = _cuenta_por_metodo_pro(metodo)
            _agregar_movimiento(
                filas,
                r.get("fecha") or r.get("created_at") or r.get("dia_operativo") or "",
                "entrada",
                "Venta",
                f"Venta {r.get('venta_id', '')}".strip(),
                cuenta,
                entrada=monto,
                metodo_pago=metodo,
                referencia=r.get("venta_id", ""),
                detalle=f"Caja: {r.get('caja_id', '')}",
            )


    # 2B) Abonos de crédito
    # Regla: el abono entra al método elegido (efectivo/banco) y baja Crédito pendiente.
    abonos = leer_actualizado("abonos_credito")
    if not abonos.empty and "monto" in abonos.columns:
        for _, r in abonos.iterrows():
            monto = float(limpiar_numero(r.get("monto")) or 0)
            if monto <= 0:
                continue
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta_entrada = _cuenta_por_metodo_pro(metodo)
            fecha_abono = r.get("fecha") or r.get("created_at") or ""

            _agregar_movimiento(
                filas,
                fecha_abono,
                "entrada",
                "Abono crédito",
                f"Abono crédito {r.get('cliente_nombre', '')}".strip(),
                cuenta_entrada,
                entrada=monto,
                metodo_pago=metodo,
                referencia=r.get("cuenta_id", ""),
                detalle="Dinero recibido por cuenta por cobrar",
            )

            _agregar_movimiento(
                filas,
                fecha_abono,
                "salida",
                "Abono crédito",
                f"Disminuye crédito pendiente {r.get('cliente_nombre', '')}".strip(),
                "Crédito pendiente",
                salida=monto,
                metodo_pago=metodo,
                referencia=r.get("cuenta_id", ""),
                detalle="Abono aplicado a crédito pendiente",
            )

    # 3) Compras
    compras = leer_actualizado("compras")
    if not compras.empty:
        for _, r in compras.iterrows():
            monto = _monto_de_row(r, ("monto", "total", "valor", "costo_total"))
            if monto <= 0:
                continue
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta = _cuenta_por_metodo_pro(metodo, r.get("cuenta", ""))
            concepto = r.get("producto") or r.get("descripcion") or r.get("concepto") or "Compra"
            _agregar_movimiento(
                filas,
                r.get("fecha") or r.get("created_at") or "",
                "salida",
                "Compra",
                concepto,
                cuenta,
                salida=monto,
                metodo_pago=metodo,
                referencia=r.get("id", ""),
                detalle="Compra de mercancía / inversión",
            )

    # 4) Gastos fijos y variables
    gastos = leer_actualizado("gastos")
    if not gastos.empty:
        for _, r in gastos.iterrows():
            monto = _monto_de_row(r, ("monto", "total", "valor"))
            if monto <= 0:
                continue
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta = _cuenta_por_metodo_pro(metodo, r.get("cuenta", ""))
            tipo_gasto = limpiar_texto(r.get("tipo")) or "gasto"
            concepto = r.get("nombre") or r.get("concepto") or r.get("categoria") or "Gasto"
            _agregar_movimiento(
                filas,
                r.get("fecha") or r.get("created_at") or "",
                "salida",
                f"Gasto {tipo_gasto}",
                concepto,
                cuenta,
                salida=monto,
                metodo_pago=metodo,
                referencia=r.get("id", ""),
                detalle=r.get("detalle") or r.get("descripcion") or "",
            )

    # 5) Pagos y adelantos empleados
    for tabla, origen_nombre in [("pagos_empleados", "Pago empleado"), ("adelantos_empleados", "Adelanto empleado")]:
        df = leer_actualizado(tabla)
        if df.empty:
            continue
        for _, r in df.iterrows():
            monto = _monto_de_row(r, ("monto", "total", "valor"))
            if monto <= 0:
                continue
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta = _cuenta_por_metodo_pro(metodo, r.get("cuenta", ""))
            empleado = r.get("empleado") or r.get("empleado_nombre") or r.get("nombre") or origen_nombre
            _agregar_movimiento(
                filas,
                r.get("fecha") or r.get("created_at") or "",
                "salida",
                origen_nombre,
                empleado,
                cuenta,
                salida=monto,
                metodo_pago=metodo,
                referencia=r.get("id", ""),
                detalle=r.get("tipo_pago") or r.get("observacion") or "",
            )

    # 6) Gastos/retiros dueño
    dueno = leer_actualizado("gastos_dueno")
    if not dueno.empty:
        for _, r in dueno.iterrows():
            monto = _monto_de_row(r, ("monto", "total", "valor"))
            if monto <= 0:
                continue
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta = _cuenta_por_metodo_pro(metodo, r.get("cuenta", ""))
            concepto = r.get("concepto") or r.get("descripcion") or r.get("detalle") or "Retiro dueño"
            _agregar_movimiento(
                filas,
                r.get("fecha") or r.get("created_at") or "",
                "salida",
                "Gasto dueño",
                concepto,
                cuenta,
                salida=monto,
                metodo_pago=metodo,
                referencia=r.get("id", ""),
                detalle=r.get("detalle") or "",
            )

    # 7) Pérdidas: afectan utilidad, pero no siempre dinero físico. Se muestran como salida operacional.
    perdidas = leer_actualizado("perdidas")
    if not perdidas.empty:
        for _, r in perdidas.iterrows():
            monto = _monto_de_row(r, ("monto", "total", "valor", "costo_total"))
            if monto <= 0:
                continue
            _agregar_movimiento(
                filas,
                r.get("fecha") or r.get("created_at") or "",
                "salida",
                "Pérdida mercancía",
                r.get("producto") or r.get("descripcion") or "Pérdida",
                "Inventario",
                salida=monto,
                metodo_pago="inventario",
                referencia=r.get("id", ""),
                detalle=r.get("motivo") or r.get("detalle") or "",
            )

    # 8) Movimientos manuales
    movs = leer_actualizado("movimientos_dinero")
    if not movs.empty:
        for _, r in movs.iterrows():
            tipo = normalizar_texto(r.get("tipo"))
            monto = float(limpiar_numero(r.get("monto")) or 0)
            if monto <= 0:
                continue
            fecha = r.get("fecha") or r.get("created_at") or ""
            desc = r.get("descripcion") or "Movimiento manual"

            if tipo in ["entrada", "aporte", "ingreso"]:
                cuenta = _cuenta_por_metodo_pro(r.get("metodo_pago"), r.get("cuenta", ""))
                _agregar_movimiento(filas, fecha, "entrada", "Manual", desc, cuenta, entrada=monto, metodo_pago=r.get("metodo_pago", ""), referencia=r.get("id", ""))
            elif tipo in ["salida", "retiro", "gasto"]:
                cuenta = _cuenta_por_metodo_pro(r.get("metodo_pago"), r.get("cuenta", ""))
                _agregar_movimiento(filas, fecha, "salida", "Manual", desc, cuenta, salida=monto, metodo_pago=r.get("metodo_pago", ""), referencia=r.get("id", ""))
            elif tipo in ["transferencia interna", "deposito al banco", "depósito al banco", "retiro del banco"]:
                origen = r.get("cuenta_origen") or ""
                destino = r.get("cuenta_destino") or ""
                _agregar_movimiento(filas, fecha, "transferencia", "Transferencia interna", desc + " (sale)", origen, salida=monto, metodo_pago="interno", referencia=r.get("id", ""))
                _agregar_movimiento(filas, fecha, "transferencia", "Transferencia interna", desc + " (entra)", destino, entrada=monto, metodo_pago="interno", referencia=r.get("id", ""))

    df = pd.DataFrame(filas)
    if df.empty:
        return df

    df["_fecha_dt"] = pd.to_datetime(df["fecha"], errors="coerce")
    df = df.sort_values(["_fecha_dt", "origen"], ascending=[True, True]).reset_index(drop=True)

    # balances por cuenta
    df["balance_cuenta"] = 0.0
    for cuenta in df["cuenta"].fillna("Pendiente").unique():
        idx = df["cuenta"].fillna("Pendiente") == cuenta
        df.loc[idx, "balance_cuenta"] = df.loc[idx, "neto"].cumsum()

    df["balance_total"] = df["neto"].cumsum()
    return df


def resumen_dinero_real_pro() -> dict:
    hist = construir_historial_dinero_real()
    if hist.empty:
        efectivo = banco = credito = total = 0.0
    else:
        efectivo = float(hist[hist["cuenta"].astype(str).apply(normalizar_texto).isin(["efectivo negocio", "efectivo", "caja"])]["neto"].sum())
        banco = float(hist[hist["cuenta"].astype(str).apply(normalizar_texto).isin(["banco", "transferencia", "tarjeta"])]["neto"].sum())
        credito = float(hist[hist["cuenta"].astype(str).apply(normalizar_texto) == "credito pendiente"]["neto"].sum())
        total = efectivo + banco

    # Inventario financiero: usar inventario_actual y, si no hay valores, productos.
    inv_vals = calcular_valores_inventario_pro() if "calcular_valores_inventario_pro" in globals() else {}
    inv_costo = float(inv_vals.get("inventario_costo", 0.0) or 0.0)
    inv_venta = float(inv_vals.get("inventario_venta", 0.0) or 0.0)
    fuente_inventario = inv_vals.get("fuente", "")

    # Capital base configurado por la administración.
    cuentas = leer_actualizado("cuentas_dinero")
    saldo_inicial = 0.0
    if not cuentas.empty:
        saldo_inicial += sum(float(limpiar_numero(r.get("saldo_inicial")) or 0) for _, r in cuentas.iterrows())
    capital_df = _df_actual("capital_base") if "_df_actual" in globals() else pd.DataFrame()
    if not capital_df.empty:
        if "activo" in capital_df.columns:
            capital_df = capital_df[capital_df["activo"] == True]
        saldo_inicial += _sum_any(capital_df, ["monto", "valor", "total"]) if "_sum_any" in globals() else 0.0

    # Lectura financiera correcta:
    # - Inventario a costo NO es ganancia; es mercancía/inversión.
    # - Inventario a venta NO es dinero disponible; es una proyección si todo se vendiera.
    # - Ganancia disponible = dinero líquido por encima del capital base.
    dinero_inversion = min(max(total, 0), max(saldo_inicial, 0))
    dinero_ganancia = max(total - saldo_inicial, 0)

    # Antes se sumaba total + inventario a costo, eso inflaba la "ganancia".
    # Ahora la ganancia estimada líquida se mantiene como dinero disponible por encima del capital base.
    ganancia_estim = dinero_ganancia

    return {
        "historial": hist,
        "efectivo": efectivo,
        "banco": banco,
        "credito": credito,
        "total_disponible": total,
        "dinero_inversion": dinero_inversion,
        "dinero_ganancia": dinero_ganancia,
        "inventario_costo": inv_costo,
        "inventario_venta": inv_venta,
        "ganancia_potencial_inventario": float(inv_vals.get("ganancia_potencial_inventario", inv_venta - inv_costo) or 0.0),
        "fuente_inventario": fuente_inventario,
        "saldo_inicial": saldo_inicial,
        "ganancia_estimada": ganancia_estim,
    }


def cuenta_por_metodo_pago(metodo_pago: str) -> str:
    metodo = normalizar_texto(metodo_pago)
    if metodo == "efectivo":
        return "Efectivo negocio"
    if metodo in ["transferencia", "tarjeta", "banco"]:
        return "Banco"
    return ""


def leer_actualizado(tabla: str) -> pd.DataFrame:
    try:
        tenant = obtener_tenant_actual()
        return _leer_tabla_de_supabase(tabla, tenant=tenant)
    except Exception:
        return DATA.get(tabla, pd.DataFrame()).copy()


def calcular_dinero_real() -> dict:
    efectivo = 0.0
    banco = 0.0

    def sumar(cuenta, monto):
        nonlocal efectivo, banco
        cuenta_n = normalizar_texto(cuenta)
        monto = float(monto or 0)
        if cuenta_n in ["efectivo negocio", "efectivo", "caja"]:
            efectivo += monto
        elif cuenta_n in ["banco", "transferencia", "tarjeta"]:
            banco += monto

    cuentas = leer_actualizado("cuentas_dinero")
    if not cuentas.empty:
        for _, r in cuentas.iterrows():
            sumar(r.get("nombre", ""), float(limpiar_numero(r.get("saldo_inicial")) or 0))

    pagos = leer_actualizado("ventas_pagos")
    if not pagos.empty and "monto" in pagos.columns:
        metodo_col = "metodo" if "metodo" in pagos.columns else ("metodo_pago" if "metodo_pago" in pagos.columns else None)
        if metodo_col:
            for _, r in pagos.iterrows():
                metodo = normalizar_texto(r.get(metodo_col))
                monto = float(limpiar_numero(r.get("monto")) or 0)
                if metodo == "efectivo":
                    sumar("Efectivo negocio", monto)
                elif metodo in ["transferencia", "tarjeta"]:
                    sumar("Banco", monto)

    for tabla in ["gastos", "compras", "pagos_empleados", "adelantos_empleados", "gastos_dueno"]:
        df = leer_actualizado(tabla)
        if df.empty:
            continue
        for _, r in df.iterrows():
            monto = float(limpiar_numero(r.get("monto")) or limpiar_numero(r.get("total")) or limpiar_numero(r.get("valor")) or 0)
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta = r.get("cuenta") or cuenta_por_metodo_pago(metodo)
            if normalizar_texto(metodo) == "mixto" and not cuenta:
                continue
            if cuenta:
                sumar(cuenta, -monto)

    movs = leer_actualizado("movimientos_dinero")
    if not movs.empty:
        for _, r in movs.iterrows():
            tipo = normalizar_texto(r.get("tipo"))
            monto = float(limpiar_numero(r.get("monto")) or 0)
            cuenta = r.get("cuenta") or cuenta_por_metodo_pago(r.get("metodo_pago"))
            origen = r.get("cuenta_origen")
            destino = r.get("cuenta_destino")

            if tipo in ["entrada", "aporte", "ingreso"]:
                sumar(cuenta, monto)
            elif tipo in ["salida", "retiro", "gasto"]:
                sumar(cuenta, -monto)
            elif tipo in ["transferencia interna", "deposito al banco", "depósito al banco", "retiro del banco"]:
                sumar(origen, -monto)
                sumar(destino, monto)

    return {"efectivo": efectivo, "banco": banco, "total": efectivo + banco}



def resumen_salidas_automaticas_dinero() -> pd.DataFrame:
    filas = []
    tablas = [
        ("gastos", "Gastos"),
        ("compras", "Compras"),
        ("pagos_empleados", "Pagos empleados"),
        ("adelantos_empleados", "Adelantos empleados"),
        ("gastos_dueno", "Gastos dueño"),
    ]
    for tabla, nombre in tablas:
        df = leer_actualizado(tabla)
        if df.empty:
            continue
        for _, r in df.iterrows():
            monto = float(limpiar_numero(r.get("monto")) or limpiar_numero(r.get("total")) or limpiar_numero(r.get("valor")) or 0)
            metodo = r.get("metodo_pago") or r.get("metodo") or ""
            cuenta = r.get("cuenta") or cuenta_por_metodo_pago(metodo)
            concepto = r.get("nombre") or r.get("concepto") or r.get("descripcion") or r.get("detalle") or r.get("producto") or nombre
            fecha = r.get("fecha") or r.get("created_at") or ""
            filas.append({
                "fecha": fecha,
                "origen": nombre,
                "tipo_gasto": r.get("tipo") or "",
                "concepto": concepto,
                "monto": monto,
                "metodo_pago": metodo,
                "cuenta": cuenta,
                "afecta_dinero": "sí" if cuenta else "pendiente",
            })
    return pd.DataFrame(filas)


def registrar_movimiento_dinero(tipo, monto, descripcion="", metodo_pago="", cuenta="", cuenta_origen="", cuenta_destino="", categoria="manual"):
    payload = {
        "fecha": datetime.now().isoformat(),
        "dia_operativo": str(date.today()),
        "tipo": tipo,
        "categoria": categoria,
        "origen": "manual",
        "metodo_pago": metodo_pago,
        "cuenta": cuenta,
        "cuenta_origen": cuenta_origen,
        "cuenta_destino": cuenta_destino,
        "monto": float(monto or 0),
        "descripcion": descripcion,
        "usuario": nombre_usuario_actual() if "nombre_usuario_actual" in globals() else "",
    }
    return insertar("movimientos_dinero", payload)



def registrar_abono_credito_seguro(fila, monto, metodo_pago, observacion=""):
    """Registra un abono a crédito y lo mete como entrada de caja/dinero por el método elegido."""
    monto = float(limpiar_numero(monto) or 0)
    if monto <= 0:
        st.error("El monto del abono debe ser mayor que cero.")
        return False

    caja_activa = obtener_caja_abierta()
    if caja_activa is None:
        st.error("Debes tener una caja abierta para registrar abonos de crédito.")
        return False

    cuenta_id = json_safe_value(fila.get("id"))
    cliente_id = json_safe_value(fila.get("cliente_id"))
    cliente_nombre = limpiar_texto(fila.get("cliente_nombre")) or limpiar_texto(fila.get("cliente")) or "Cliente"
    monto_original = float(limpiar_numero(fila.get("monto_original")) or limpiar_numero(fila.get("total")) or 0)
    monto_abonado_anterior = float(limpiar_numero(fila.get("monto_abonado")) or 0)
    saldo_anterior = float(limpiar_numero(fila.get("saldo_pendiente")) or max(monto_original - monto_abonado_anterior, 0))
    monto_real = min(monto, saldo_anterior) if saldo_anterior > 0 else monto
    nuevo_abonado = monto_abonado_anterior + monto_real
    nuevo_saldo = max(monto_original - nuevo_abonado, 0.0)
    nuevo_estado = "saldada" if nuevo_saldo <= 0 else "pendiente"

    payload_abono = json_safe_payload({
        "cuenta_id": cuenta_id,
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre,
        "monto": monto_real,
        "metodo_pago": metodo_pago,
        "fecha": ahora_str(),
        "usuario": nombre_usuario_actual(),
        "caja_id": json_safe_value(caja_activa.get("id")),
        "observacion": observacion,
    })

    # Guardar abono. Si alguna columna no existe, intentar con payload mínimo.
    try:
        supabase.table("abonos_credito").insert(payload_abono).execute()
    except Exception:
        try:
            supabase.table("abonos_credito").insert(json_safe_payload({
                "cuenta_id": cuenta_id,
                "cliente_id": cliente_id,
                "cliente_nombre": cliente_nombre,
                "monto": monto_real,
                "metodo_pago": metodo_pago,
                "usuario": nombre_usuario_actual(),
            })).execute()
        except Exception as e:
            st.error(f"No se pudo guardar el abono: {e}")
            return False

    # Actualizar cuenta por cobrar
    ok_cuenta = actualizar("cuentas_por_cobrar", cuenta_id, {
        "monto_abonado": float(nuevo_abonado),
        "saldo_pendiente": float(nuevo_saldo),
        "estado": nuevo_estado,
    })

    # Registrar entrada para caja
    mov_payload = json_safe_payload({
        "fecha": datetime.now().isoformat(),
        "dia_operativo": str(date.today()),
        "tipo_movimiento": "entrada",
        "origen": "abono_credito",
        "referencia_id": str(cuenta_id),
        "metodo_pago": metodo_pago,
        "monto": float(monto_real),
        "descripcion": f"Abono crédito {cliente_nombre}",
        "usuario": nombre_usuario_actual(),
        "caja_id": json_safe_value(caja_activa.get("id")),
    })
    try:
        if not metodo_es_mixto(mov_payload.get("metodo_pago")):
            supabase.table("movimientos_caja").insert(mov_payload).execute()
    except Exception:
        pass

    # Registrar en movimientos_dinero para Dinero Real, si existe la tabla/columnas
    cuenta_dinero = cuenta_por_metodo_pago(metodo_pago) if "cuenta_por_metodo_pago" in globals() else ("Efectivo negocio" if metodo_pago == "efectivo" else "Banco")
    try:
        registrar_movimiento_dinero(
            "entrada",
            float(monto_real),
            f"Abono crédito {cliente_nombre}",
            metodo_pago=metodo_pago,
            cuenta=cuenta_dinero,
            categoria="abono_credito",
        )
    except Exception:
        pass

    st.success(f"Abono registrado: RD$ {monto_real:,.2f}. Saldo pendiente: RD$ {nuevo_saldo:,.2f}.")
    return True



# =========================================================
# MOTOR FINANCIERO / CONTABLE PRO - BIBE RON 01
# =========================================================

def _df_actual(tabla: str) -> pd.DataFrame:
    try:
        return leer_actualizado(tabla)
    except Exception:
        return DATA.get(tabla, pd.DataFrame()).copy()

def _fecha_col(df: pd.DataFrame):
    for c in ["fecha", "created_at", "fecha_apertura", "fecha_compra"]:
        if c in df.columns:
            return c
    return None

def _filtrar_periodo_df(df: pd.DataFrame, desde, hasta) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    col = _fecha_col(df)
    if not col:
        return df.copy()
    out = df.copy()
    out["_fecha_dt"] = pd.to_datetime(out[col], errors="coerce")
    try:
        return out[(out["_fecha_dt"].dt.date >= desde) & (out["_fecha_dt"].dt.date <= hasta)].copy()
    except Exception:
        return out.copy()

def _num(v) -> float:
    try:
        return float(limpiar_numero(v) or 0)
    except Exception:
        return 0.0

def _sum_any(df: pd.DataFrame, cols) -> float:
    """
    Suma la mejor columna disponible.
    Importante: si una columna existe pero está toda en cero, no se queda con esa;
    busca otra columna con valores reales. Esto evita que venta_bruta default 0
    opaque los totales reales de ventas.
    """
    if df is None or df.empty:
        return 0.0

    mejores = []
    for c in cols:
        if c in df.columns:
            try:
                serie = pd.to_numeric(df[c].apply(lambda x: limpiar_numero(x)), errors="coerce").fillna(0)
                suma = float(serie.sum())
                positivos = int((serie.abs() > 0).sum())
                mejores.append((c, suma, positivos))
            except Exception:
                continue

    if not mejores:
        return 0.0

    # elegir columna con más valores reales; si empatan, mayor suma absoluta
    mejores = sorted(mejores, key=lambda x: (x[2], abs(x[1])), reverse=True)
    return float(mejores[0][1])



def registrar_movimiento_contable(modulo, referencia_id, cuenta_codigo, cuenta_nombre, tipo_cuenta, debito=0, credito=0, descripcion="", usuario=None):
    try:
        payload = {
            "fecha": datetime.now().isoformat(),
            "modulo": modulo,
            "referencia_id": str(referencia_id or ""),
            "cuenta_codigo": str(cuenta_codigo or ""),
            "cuenta_nombre": str(cuenta_nombre or ""),
            "tipo_cuenta": str(tipo_cuenta or ""),
            "debito": float(debito or 0),
            "credito": float(credito or 0),
            "descripcion": descripcion,
            "usuario": usuario or nombre_usuario_actual(),
            "empresa_id": obtener_tenant_actual()
        }
        if "json_safe_payload" in globals():
            payload = json_safe_payload(payload)
        supabase.table("movimientos_contables").insert(payload).execute()
        return True
    except Exception as e:
        raise RuntimeError(f"Error al registrar movimiento contable obligatorio: {e}")

def obtener_inventario_a_costo_fecha(fecha_limite=None) -> float:
    try:
        vals = calcular_valores_inventario_pro()
        return float(vals.get("inventario_costo", 0) or 0)
    except Exception:
        return 0.0

def obtener_inventario_a_venta_fecha(fecha_limite=None) -> float:
    try:
        vals = calcular_valores_inventario_pro()
        return float(vals.get("inventario_venta", 0) or 0)
    except Exception:
        return 0.0

def calcular_deducciones_nomina(sueldo_bruto: float) -> dict:
    sfs = round(sueldo_bruto * 0.0304, 2)
    afp = round(sueldo_bruto * 0.0287, 2)
    total_tss = sfs + afp
    sueldo_neto_tss = sueldo_bruto - total_tss
    
    isr = 0.0
    if sueldo_neto_tss > 72260.25:
        isr = round(6647.92 + (sueldo_neto_tss - 72260.25) * 0.25, 2)
    elif sueldo_neto_tss > 52027.42:
        isr = round(2601.36 + (sueldo_neto_tss - 52027.42) * 0.20, 2)
    elif sueldo_neto_tss > 34685.00:
        isr = round((sueldo_neto_tss - 34685.00) * 0.15, 2)
        
    sueldo_neto_pagar = round(sueldo_neto_tss - isr, 2)
    return {
        "sfs": sfs,
        "afp": afp,
        "total_tss": total_tss,
        "sueldo_neto_tss": sueldo_neto_tss,
        "isr": isr,
        "neto_pagar": sueldo_neto_pagar
    }

def obtener_config_financiera():
    cfg = _df_actual("configuracion_financiera")
    if cfg.empty:
        return {"nombre_negocio": "BIBE RON 01", "porcentaje_isr": 0, "incluir_isr": False, "incluir_depreciacion": True, "moneda": "RD$"}
    return cfg.iloc[0].to_dict()


def calcular_costo_ventas_real(desde, hasta, ventas_df=None) -> float:
    """
    Calcula el costo de ventas real desde detalle_venta.
    Cruza detalle_venta con ventas del período por venta_id.
    """
    detalle = _df_actual("detalle_venta")
    if detalle is None or detalle.empty:
        if ventas_df is not None and not ventas_df.empty:
            return float(_sum_any(ventas_df, ["costo_venta", "costo_total", "costo"]))
        return 0.0

    if ventas_df is not None and not ventas_df.empty and "venta_id" in detalle.columns:
        venta_ids = set()
        for c in ["id", "identificación", "identificacion", "venta_id"]:
            if c in ventas_df.columns:
                venta_ids.update(ventas_df[c].dropna().astype(str).tolist())
        if venta_ids:
            detalle = detalle[detalle["venta_id"].astype(str).isin(venta_ids)].copy()
    else:
        detalle = _filtrar_periodo_df(detalle, desde, hasta)

    if detalle.empty:
        if ventas_df is not None and not ventas_df.empty:
            return float(_sum_any(ventas_df, ["costo_venta", "costo_total", "costo"]))
        return 0.0

    for col_anulado in ["anulado", "cancelado"]:
        if col_anulado in detalle.columns:
            try:
                detalle = detalle[~detalle[col_anulado].fillna(False).astype(bool)].copy()
            except Exception:
                pass

    directo = _sum_any(detalle, ["total_costo", "costo_total", "costo_venta"])
    if directo > 0:
        return float(directo)

    productos = _df_actual("productos")

    def _buscar_costo_producto(row):
        try:
            pid = row.get("producto_id")
            if pid and not productos.empty and "id" in productos.columns:
                m = productos[productos["id"].astype(str) == str(pid)]
                if not m.empty:
                    return _num(m.iloc[0].get("costo") or m.iloc[0].get("costo_unitario") or m.iloc[0].get("costo_promedio"))
        except Exception:
            pass
        try:
            codigo = row.get("codigo") or row.get("codigo_barra")
            if codigo and not productos.empty:
                for c in ["codigo", "codigo_barra"]:
                    if c in productos.columns:
                        m = productos[productos[c].astype(str) == str(codigo)]
                        if not m.empty:
                            return _num(m.iloc[0].get("costo") or m.iloc[0].get("costo_unitario") or m.iloc[0].get("costo_promedio"))
        except Exception:
            pass
        try:
            nombre = row.get("producto") or row.get("nombre")
            if nombre and not productos.empty and "nombre" in productos.columns:
                nn = normalizar_texto(nombre)
                tmp = productos.copy()
                tmp["_n"] = tmp["nombre"].astype(str).apply(normalizar_texto)
                m = tmp[tmp["_n"] == nn]
                if not m.empty:
                    return _num(m.iloc[0].get("costo") or m.iloc[0].get("costo_unitario") or m.iloc[0].get("costo_promedio"))
        except Exception:
            pass
        return 0.0

    total = 0.0
    for _, r in detalle.iterrows():
        cant = _num(r.get("cantidad") or r.get("qty") or 0)
        costo_unit = _num(r.get("costo_unitario") or r.get("costo") or r.get("costo_promedio"))
        if costo_unit <= 0:
            costo_unit = _buscar_costo_producto(r)
        total += max(cant, 0) * max(costo_unit, 0)

    return float(total)


def calcular_estado_resultados_pro(desde, hasta) -> dict:
    cfg = obtener_config_financiera()

    ventas = _filtrar_periodo_df(_df_actual("ventas"), desde, hasta)
    ventas = aplicar_total_contable_df(ventas) if "aplicar_total_contable_df" in globals() and not ventas.empty else ventas
    if not ventas.empty:
        for col_anulado in ["anulado", "cancelado"]:
            if col_anulado in ventas.columns:
                try:
                    ventas = ventas[~ventas[col_anulado].fillna(False).astype(bool)].copy()
                except Exception:
                    pass
        if "estado" in ventas.columns:
            ventas = ventas[~ventas["estado"].astype(str).apply(normalizar_texto).isin(["anulada", "cancelada"])].copy()
    total_col = "total_contable" if "total_contable" in ventas.columns else "total"
    ventas_brutas = _sum_any(ventas, ["venta_bruta", total_col, "total", "subtotal"])
    descuentos = _sum_any(ventas, ["descuento_total", "descuento", "descuentos"])
    devoluciones = _sum_any(ventas, ["devolucion_total", "devolucion", "devoluciones"])

    # Si venta_bruta quedó en cero por columna nueva agregada en Supabase,
    # tomar total real como base.
    if ventas_brutas <= 0 and not ventas.empty:
        ventas_brutas = _sum_any(ventas, [total_col, "total", "subtotal"])

    ventas_netas = max(ventas_brutas - descuentos - devoluciones, 0)

    compras = _filtrar_periodo_df(_df_actual("compras"), desde, hasta)
    compras_periodo = _sum_any(compras, ["monto", "total", "valor", "costo_total"])
    fletes = _sum_any(compras, ["flete", "fletes", "acarreo", "acarreos"])

    ajustes = _filtrar_periodo_df(_df_actual("ajustes_inventario"), desde, hasta)
    ajustes_positivos = 0.0
    ajustes_negativos = 0.0
    if not ajustes.empty:
        for _, r in ajustes.iterrows():
            monto = _num(r.get("valor") or r.get("monto") or r.get("total") or r.get("costo_total"))
            tipo = normalizar_texto(r.get("tipo") or r.get("tipo_ajuste") or r.get("movimiento") or "")
            if tipo in ["entrada", "positivo", "aumento", "ajuste positivo"]:
                ajustes_positivos += monto
            elif tipo in ["salida", "negativo", "disminucion", "disminución", "ajuste negativo"]:
                ajustes_negativos += monto

    inv_final = obtener_inventario_a_costo_fecha(hasta)

    # Costo de ventas real: mercancía vendida, no compras del periodo.
    costo_ventas_real = calcular_costo_ventas_real(desde, hasta, ventas)

    # Para presentación, si no hay snapshot de inventario inicial, se calcula estimado
    # para cuadrar con: Inventario inicial + Compras + Fletes + Ajustes - Inventario final = Costo de ventas.
    inventario_inicial = max(costo_ventas_real + inv_final - compras_periodo - fletes - ajustes_positivos + ajustes_negativos, 0)
    costo_ventas_formula = max(inventario_inicial + compras_periodo + fletes + ajustes_positivos - inv_final, 0)

    # Si detalle_venta trae costo real, usarlo como fuente principal.
    costo_ventas = costo_ventas_real if costo_ventas_real > 0 else costo_ventas_formula

    utilidad_bruta = ventas_netas - costo_ventas
    margen_bruto = (utilidad_bruta / ventas_netas * 100) if ventas_netas else 0

    gastos = _filtrar_periodo_df(_df_actual("gastos"), desde, hasta)
    adelantos = _filtrar_periodo_df(_df_actual("adelantos_empleados"), desde, hasta)
    pagos_empleados = _filtrar_periodo_df(_df_actual("pagos_empleados"), desde, hasta)

    personal = _sum_any(pagos_empleados, ["monto", "total", "valor"]) + _sum_any(adelantos, ["monto", "total", "valor"])
    cargas_sociales = gastos_fijos = gastos_variables = comisiones_bancarias = 0.0

    if not gastos.empty:
        for _, r in gastos.iterrows():
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

    perdidas = _filtrar_periodo_df(_df_actual("perdidas"), desde, hasta)
    perdidas_merma = _sum_any(perdidas, ["valor", "monto", "total", "costo_total"]) + ajustes_negativos

    depreciaciones = _filtrar_periodo_df(_df_actual("depreciaciones"), desde, hasta)
    depreciacion = _sum_any(depreciaciones, ["monto", "valor", "total"]) if bool(cfg.get("incluir_depreciacion", True)) else 0.0

    total_gastos_operativos = personal + cargas_sociales + gastos_fijos + gastos_variables + perdidas_merma + depreciacion
    utilidad_operativa = utilidad_bruta - total_gastos_operativos
    margen_operativo = (utilidad_operativa / ventas_netas * 100) if ventas_netas else 0

    porcentaje_isr = _num(cfg.get("porcentaje_isr"))
    incluir_isr = bool(cfg.get("incluir_isr", False))
    utilidad_antes_isr = utilidad_operativa - comisiones_bancarias
    isr = max(utilidad_antes_isr * (porcentaje_isr / 100), 0) if incluir_isr else 0.0
    utilidad_neta = utilidad_antes_isr - isr
    margen_neto = (utilidad_neta / ventas_netas * 100) if ventas_netas else 0

    dueno = _filtrar_periodo_df(_df_actual("gastos_dueno"), desde, hasta)
    retiros_dueno = _sum_any(dueno, ["monto", "total", "valor"])
    excedente_reinversion = utilidad_neta - retiros_dueno

    cxc = _df_actual("cuentas_por_cobrar")
    cxc_pend = cxc
    if not cxc.empty and "estado" in cxc.columns:
        cxc_pend = cxc[cxc["estado"].astype(str).str.lower() != "saldada"]
    credito_pendiente = _sum_any(cxc_pend, ["saldo_pendiente", "monto_original"])
    abonos = _filtrar_periodo_df(_df_actual("abonos_credito"), desde, hasta)
    abonos_recibidos = _sum_any(abonos, ["monto", "total", "valor"])

    inv_venta = obtener_inventario_a_venta_fecha(hasta)
    inv_costo = inv_final
    ganancia_potencial = inv_venta - inv_costo

    return {
        "cfg": cfg,
        "ventas_brutas": ventas_brutas,
        "descuentos": descuentos,
        "devoluciones": devoluciones,
        "ventas_netas": ventas_netas,
        "inventario_inicial": inventario_inicial,
        "compras_periodo": compras_periodo,
        "fletes": fletes,
        "ajustes_positivos": ajustes_positivos,
        "inventario_final": inv_final,
        "costo_ventas": costo_ventas,
        "costo_ventas_real": costo_ventas_real,
        "costo_ventas_formula": costo_ventas_formula,
        "utilidad_bruta": utilidad_bruta,
        "margen_bruto": margen_bruto,
        "personal": personal,
        "cargas_sociales": cargas_sociales,
        "gastos_fijos": gastos_fijos,
        "gastos_variables": gastos_variables,
        "perdidas_merma": perdidas_merma,
        "depreciacion": depreciacion,
        "total_gastos_operativos": total_gastos_operativos,
        "utilidad_operativa": utilidad_operativa,
        "margen_operativo": margen_operativo,
        "comisiones_bancarias": comisiones_bancarias,
        "utilidad_antes_isr": utilidad_antes_isr,
        "isr": isr,
        "utilidad_neta": utilidad_neta,
        "margen_neto": margen_neto,
        "retiros_dueno": retiros_dueno,
        "excedente_reinversion": excedente_reinversion,
        "credito_pendiente": credito_pendiente,
        "abonos_recibidos": abonos_recibidos,
        "inventario_a_costo": inv_costo,
        "inventario_a_venta": inv_venta,
        "ganancia_potencial_inventario": ganancia_potencial,
    }

def _fmt_rd(v):
    v = float(v or 0)
    if v < 0:
        return f"(RD$ {abs(v):,.2f})"
    return f"RD$ {v:,.2f}"

def _estado_tabla(items):
    return pd.DataFrame([{"Concepto": k, "RD$": _fmt_rd(v)} for k, v in items])


# =========================================================
# DISTRIBUCIÓN DE BENEFICIOS
# =========================================================


def obtener_distribucion_guardada_periodo(desde, hasta) -> dict | None:
    """
    Busca la última distribución guardada para el mismo rango de fechas.
    El Dashboard debe usar esto para verse igual que Distribución Beneficios.
    """
    try:
        df = _df_actual("distribucion_beneficios")
    except Exception:
        df = pd.DataFrame()

    if df is None or df.empty:
        return None

    dsd = str(desde)
    hst = str(hasta)

    try:
        tmp = df.copy()
        if "periodo_desde" in tmp.columns and "periodo_hasta" in tmp.columns:
            tmp = tmp[
                (tmp["periodo_desde"].astype(str).str[:10] == dsd) &
                (tmp["periodo_hasta"].astype(str).str[:10] == hst)
            ].copy()
        else:
            return None

        if tmp.empty:
            return None

        if "fecha_registro" in tmp.columns:
            tmp["_fecha_registro"] = pd.to_datetime(tmp["fecha_registro"], errors="coerce")
            tmp = tmp.sort_values("_fecha_registro", ascending=False)
        elif "created_at" in tmp.columns:
            tmp["_fecha_registro"] = pd.to_datetime(tmp["created_at"], errors="coerce")
            tmp = tmp.sort_values("_fecha_registro", ascending=False)

        return tmp.iloc[0].to_dict()
    except Exception:
        return None


def calcular_distribucion_beneficios(desde, hasta, porc_duena=65.0, porc_gerente=35.0) -> dict:
    """
    Calcula la distribución mensual correctamente.
    Si la utilidad neta es negativa o cero, NO se reparte.
    Las pérdidas de mercancía sí afectan al gerente porque bajan la utilidad neta.
    Los gastos/retiros del dueño solo afectan la parte del dueño.
    """
    base = calcular_utilidad_neta_operativa_periodo(desde, hasta, 0.0) if "calcular_utilidad_neta_operativa_periodo" in globals() else {}
    utilidad_neta = float(base.get("utilidad_neta", 0) or 0)
    utilidad_distribuible = max(utilidad_neta, 0)

    monto_dueno = utilidad_distribuible * (float(porc_duena) / 100)
    monto_gerente = utilidad_distribuible * (float(porc_gerente) / 100)

    dueno = _filtrar_periodo_df(_df_actual("gastos_dueno"), desde, hasta)
    if not dueno.empty and "afecta_distribucion" in dueno.columns:
        dueno = dueno[(dueno["afecta_distribucion"] == True) | (dueno["afecta_distribucion"].isna())]
    gastos_dueno = _sum_any(dueno, ["monto", "total", "valor"])

    disponible_duena = monto_dueno - gastos_dueno
    exceso_gastos_duena = abs(disponible_duena) if disponible_duena < 0 else 0.0

    return {
        "utilidad_neta": utilidad_neta,
        "utilidad_distribuible": utilidad_distribuible,
        "periodo_en_perdida": utilidad_neta <= 0,
        "porcentaje_duena": float(porc_duena),
        "porcentaje_gerente": float(porc_gerente),
        "monto_duena_calculado": monto_dueno,
        "monto_gerente_calculado": monto_gerente,
        "gastos_duena_periodo": gastos_dueno,
        "disponible_duena": disponible_duena,
        "exceso_gastos_duena": exceso_gastos_duena,
        "estado_resultados": base,
    }


def guardar_distribucion_beneficios(
    desde, hasta, calc,
    pago_duena, reinversion_duena, pendiente_duena,
    pago_gerente, pendiente_gerente,
    metodo_duena, metodo_gerente,
    observacion,
    pago_dueno_efectivo=0.0, pago_dueno_transferencia=0.0, pago_dueno_tarjeta=0.0,
    pago_gerente_efectivo=0.0, pago_gerente_transferencia=0.0, pago_gerente_tarjeta=0.0,
):
    # Totales reales desde desglose mixto
    pago_duena_total = float(pago_dueno_efectivo or 0) + float(pago_dueno_transferencia or 0) + float(pago_dueno_tarjeta or 0)
    pago_gerente_total = float(pago_gerente_efectivo or 0) + float(pago_gerente_transferencia or 0) + float(pago_gerente_tarjeta or 0)

    # Compatibilidad: si no se usó desglose, usa el campo anterior
    if pago_duena_total <= 0:
        pago_duena_total = float(pago_duena or 0)
    if pago_gerente_total <= 0:
        pago_gerente_total = float(pago_gerente or 0)

    payload = {
        "periodo_desde": str(desde),
        "periodo_hasta": str(hasta),
        "utilidad_neta": float(calc["utilidad_neta"]),
        "porcentaje_duena": float(calc["porcentaje_duena"]),
        "porcentaje_gerente": float(calc["porcentaje_gerente"]),
        "monto_duena_calculado": float(calc["monto_duena_calculado"]),
        "monto_gerente_calculado": float(calc["monto_gerente_calculado"]),
        "gastos_duena_periodo": float(calc["gastos_duena_periodo"]),
        "disponible_duena": float(calc["disponible_duena"]),
        "pago_duena": float(pago_duena_total),
        "reinversion_duena": float(reinversion_duena),
        "pendiente_duena": float(pendiente_duena),
        "pago_gerente": float(pago_gerente_total),
        "pendiente_gerente": float(pendiente_gerente),
        "metodo_pago_duena": "mixto" if pago_duena_total > 0 else metodo_duena,
        "metodo_pago_gerente": "mixto" if pago_gerente_total > 0 else metodo_gerente,
        "estado": "registrada",
        "observacion": observacion,
        "usuario": nombre_usuario_actual(),
        "fecha_registro": datetime.now().isoformat(),
        # Desglose mixto
        "pago_dueno_efectivo": float(pago_dueno_efectivo or 0),
        "pago_dueno_transferencia": float(pago_dueno_transferencia or 0),
        "pago_dueno_tarjeta": float(pago_dueno_tarjeta or 0),
        "pago_gerente_efectivo": float(pago_gerente_efectivo or 0),
        "pago_gerente_transferencia": float(pago_gerente_transferencia or 0),
        "pago_gerente_tarjeta": float(pago_gerente_tarjeta or 0),
    }
    if "json_safe_payload" in globals():
        payload = json_safe_payload(payload)

    try:
        resp = supabase.table("distribucion_beneficios").insert(payload).execute()
        data = resp.data or []
        dist_id = data[0].get("id") if data else ""
    except Exception as e:
        st.error(f"No se pudo guardar la distribución: {e}")
        return False

    def _registrar_salida_mixta(persona, monto, metodo, cuenta_contable_codigo, cuenta_contable_nombre, tipo_cuenta, descripcion):
        if float(monto or 0) <= 0:
            return
        cuenta = cuenta_por_metodo_pago(metodo) if "cuenta_por_metodo_pago" in globals() else ("Efectivo negocio" if metodo == "efectivo" else "Banco")
        try:
            registrar_movimiento_dinero(
                "salida",
                float(monto),
                descripcion,
                metodo_pago=metodo,
                cuenta=cuenta,
                categoria="distribucion_beneficios" if persona == "dueno" else "beneficio_gerente",
            )
        except Exception:
            pass
        registrar_movimiento_contable(
            "distribucion_beneficios",
            dist_id,
            cuenta_contable_codigo,
            cuenta_contable_nombre,
            tipo_cuenta,
            debito=float(monto),
            descripcion=f"{descripcion} por {metodo}",
        )

    try:
        # Pagos mixtos dueño
        _registrar_salida_mixta("dueno", pago_dueno_efectivo, "efectivo", "3003", "Retiros del dueño", "capital", "Pago beneficio dueño")
        _registrar_salida_mixta("dueno", pago_dueno_transferencia, "transferencia", "3003", "Retiros del dueño", "capital", "Pago beneficio dueño")
        _registrar_salida_mixta("dueno", pago_dueno_tarjeta, "tarjeta", "3003", "Retiros del dueño", "capital", "Pago beneficio dueño")

        # Respaldo si no hay desglose
        if float(pago_duena_total or 0) > 0 and (float(pago_dueno_efectivo or 0) + float(pago_dueno_transferencia or 0) + float(pago_dueno_tarjeta or 0)) <= 0:
            _registrar_salida_mixta("dueno", pago_duena_total, metodo_duena, "3003", "Retiros del dueño", "capital", "Pago beneficio dueño")

        # Pagos mixtos gerente
        _registrar_salida_mixta("gerente", pago_gerente_efectivo, "efectivo", "6009", "Beneficio gerente", "gasto", "Pago beneficio gerente")
        _registrar_salida_mixta("gerente", pago_gerente_transferencia, "transferencia", "6009", "Beneficio gerente", "gasto", "Pago beneficio gerente")
        _registrar_salida_mixta("gerente", pago_gerente_tarjeta, "tarjeta", "6009", "Beneficio gerente", "gasto", "Pago beneficio gerente")

        if float(pago_gerente_total or 0) > 0 and (float(pago_gerente_efectivo or 0) + float(pago_gerente_transferencia or 0) + float(pago_gerente_tarjeta or 0)) <= 0:
            _registrar_salida_mixta("gerente", pago_gerente_total, metodo_gerente, "6009", "Beneficio gerente", "gasto", "Pago beneficio gerente")

        if float(reinversion_duena or 0) > 0:
            registrar_movimiento_contable("distribucion_beneficios", dist_id, "3006", "Reinversión de utilidades", "capital", credito=float(reinversion_duena), descripcion="Utilidad dueño reinvertida")

        if float(pendiente_duena or 0) > 0:
            registrar_movimiento_contable("distribucion_beneficios", dist_id, "3004", "Beneficio pendiente dueño", "capital", credito=float(pendiente_duena), descripcion="Beneficio pendiente por pagar a dueño")

        if float(pendiente_gerente or 0) > 0:
            registrar_movimiento_contable("distribucion_beneficios", dist_id, "3005", "Beneficio pendiente gerente", "pasivo", credito=float(pendiente_gerente), descripcion="Beneficio pendiente por pagar a gerente")
    except Exception:
        pass

    return True


def render_estado_resultados_pro(desde, hasta):
    er = calcular_estado_resultados_pro(desde, hasta)
    cfg = er["cfg"]
    nombre_negocio = cfg.get("nombre_negocio") or "BIBE RON 01"

    st.markdown(f"## 🧾 {nombre_negocio}")
    st.markdown("### Estado de Resultados Ejecutivo PRO")
    st.caption(f"Período: {desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')} | Valores expresados en RD$")

    st.markdown("### 📊 Resumen ejecutivo")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Ventas netas", _fmt_rd(er["ventas_netas"]))
    k2.metric("Utilidad bruta", _fmt_rd(er["utilidad_bruta"]), f"{er['margen_bruto']:.2f}%")
    k3.metric("Utilidad neta", _fmt_rd(er["utilidad_neta"]), f"{er['margen_neto']:.2f}%")
    k4.metric("Reinversión", _fmt_rd(er["excedente_reinversion"]))

    with st.expander("🔎 Validación rápida del costo de ventas", expanded=False):
        st.write(f"Costo de ventas real leído desde detalle/productos: {_fmt_rd(er.get('costo_ventas_real', 0))}")
        st.write(f"Costo por fórmula de inventario: {_fmt_rd(er.get('costo_ventas_formula', 0))}")
        st.write("La utilidad bruta debe ser: Ventas netas - Costo de ventas.")

    secciones = [
        ("🟦 1. Ingresos por ventas", [
            ("Ventas Brutas", er["ventas_brutas"]),
            ("(-) Descuentos aplicados", -er["descuentos"]),
            ("(-) Devoluciones / anulaciones", -er["devoluciones"]),
            ("VENTAS NETAS", er["ventas_netas"]),
        ]),
        ("🟨 2. Costo de ventas", [
            ("Inventario inicial", er["inventario_inicial"]),
            ("(+) Compras del período", er["compras_periodo"]),
            ("(+) Fletes y acarreos", er["fletes"]),
            ("(+) Ajustes positivos inventario", er["ajustes_positivos"]),
            ("(-) Inventario final", -er["inventario_final"]),
            ("TOTAL COSTO DE VENTAS", er["costo_ventas"]),
        ]),
        ("🟩 3. Margen de beneficio", [
            ("Ventas Netas", er["ventas_netas"]),
            ("(-) Costo de Ventas", -er["costo_ventas"]),
            ("UTILIDAD BRUTA", er["utilidad_bruta"]),
        ]),
        ("🟥 4. Gastos operativos", [
            ("Sueldos y pagos empleados", er["personal"]),
            ("TSS / INFOTEP / Cargas sociales", er["cargas_sociales"]),
            ("Gastos fijos", er["gastos_fijos"]),
            ("Gastos variables", er["gastos_variables"]),
            ("Pérdidas de mercancía / merma", er["perdidas_merma"]),
            ("Depreciación", er["depreciacion"]),
            ("TOTAL GASTOS OPERATIVOS", er["total_gastos_operativos"]),
        ]),
        ("🟫 5. Resultado operativo", [
            ("Utilidad Bruta", er["utilidad_bruta"]),
            ("(-) Gastos Operativos", -er["total_gastos_operativos"]),
            ("UTILIDAD OPERATIVA (EBIT)", er["utilidad_operativa"]),
        ]),
        ("🟨 6. Gastos financieros e impuestos", [
            ("Comisiones bancarias / intereses", -er["comisiones_bancarias"]),
            ("UTILIDAD ANTES DE ISR", er["utilidad_antes_isr"]),
            ("(-) ISR estimado", -er["isr"]),
            ("UTILIDAD NETA DEL PERÍODO", er["utilidad_neta"]),
        ]),
        ("🟦 7. Cuentas por cobrar", [
            ("Créditos pendientes clientes", er["credito_pendiente"]),
            ("Abonos recibidos en el período", er["abonos_recibidos"]),
        ]),
        ("🟪 8. Disponibilidad y reinversión", [
            ("Utilidad Neta", er["utilidad_neta"]),
            ("(-) Retiros / gastos del dueño", -er["retiros_dueno"]),
            ("EXCEDENTE PARA REINVERSIÓN", er["excedente_reinversion"]),
        ]),
        ("📦 9. Posición del negocio", [
            ("Inventario a costo", er["inventario_a_costo"]),
            ("Inventario a venta", er["inventario_a_venta"]),
            ("Ganancia potencial inventario", er["ganancia_potencial_inventario"]),
            ("Crédito pendiente", er["credito_pendiente"]),
        ]),
    ]

    for titulo, items in secciones:
        st.markdown(f"### {titulo}")
        st.dataframe(_estado_tabla(items), use_container_width=True, hide_index=True)

    st.markdown("### 🚦 Alertas financieras")
    alertas = []
    if er["ventas_netas"] > 0 and er["costo_ventas"] <= 0:
        alertas.append("🔴 Costo de ventas en cero: revisar costo_unitario en detalle_venta o costo en productos.")
    elif er["ventas_netas"] > 0 and er["margen_bruto"] < 20:
        alertas.append("🔴 Margen bruto bajo: revisar precios, costos o descuentos.")
    elif er["ventas_netas"] > 0:
        alertas.append("🟢 Margen bruto en seguimiento.")
    if er["ventas_netas"] > 0 and er["gastos_fijos"] > er["ventas_netas"] * 0.20:
        alertas.append("🟡 Gastos fijos altos respecto a ventas.")
    if er["ventas_netas"] > 0 and er["credito_pendiente"] > er["ventas_netas"] * 0.25:
        alertas.append("🟡 Crédito pendiente elevado; dar seguimiento a cobros.")
    if er["ventas_netas"] > 0 and er["perdidas_merma"] > er["ventas_netas"] * 0.03:
        alertas.append("🔴 Merma/pérdidas altas.")
    if not alertas:
        alertas.append("🟢 Sin alertas críticas para este período.")
    for a in alertas:
        st.write(a)

    st.caption("Firma propietaria: ______________________    |    Preparado por: ______________________")



# =========================================================
# PROTECCIÓN CAJA: NO DUPLICAR VENTAS MIXTAS
# =========================================================

def metodo_es_mixto(metodo):
    try:
        return normalizar_texto(metodo) == "mixto"
    except Exception:
        return str(metodo or "").strip().lower() == "mixto"



# =========================================================
# RECONSTRUIR CAJA DESDE VENTAS_PAGOS
# =========================================================

def reconstruir_movimientos_caja_desde_ventas_pagos(venta_id):
    """
    Fuente real: ventas_pagos.
    Borra cualquier movimiento de caja de esa venta y lo reconstruye por método real.
    Nunca crea metodo_pago='mixto'.
    Crédito no entra como dinero físico, pero puede quedar fuera de caja para no inflar efectivo.
    """
    try:
        venta_id_txt = str(venta_id)

        # Buscar la venta para tomar caja_id y fecha si hace falta
        venta_resp = supabase.table("ventas").select("*").eq("id", venta_id_txt).execute()
        venta_row = (venta_resp.data or [{}])[0] if venta_resp.data else {}
        caja_id_venta = venta_row.get("caja_id")
        dia_venta = venta_row.get("dia_operativo") or str(date.today())
        usuario_venta = venta_row.get("usuario") or nombre_usuario_actual()

        # Buscar pagos reales
        pagos_resp = supabase.table("ventas_pagos").select("*").eq("venta_id", venta_id_txt).execute()
        pagos = pagos_resp.data or []

        # Borrar movimientos viejos de esa venta para evitar duplicados o mixto
        try:
            supabase.table("movimientos_caja").delete().eq("origen", "venta").eq("referencia_id", venta_id_txt).execute()
        except Exception:
            pass

        for p in pagos:
            metodo = normalizar_texto(p.get("metodo") or p.get("metodo_pago") or "")
            monto = float(limpiar_numero(p.get("monto")) or 0)

            if monto <= 0:
                continue

            # Nunca registrar mixto. Se guardan solo las partes reales.
            if metodo == "mixto":
                continue

            # Crédito no es dinero físico; ya vive en cuentas por cobrar.
            if metodo == "credito":
                continue

            caja_id = p.get("caja_id") or caja_id_venta
            dia_operativo = p.get("dia_operativo") or dia_venta
            usuario = p.get("usuario") or usuario_venta

            payload = {
                "fecha": datetime.now().isoformat(),
                "dia_operativo": str(dia_operativo),
                "caja_id": str(caja_id) if caja_id else None,
                "tipo_movimiento": "entrada",
                "origen": "venta",
                "referencia_id": venta_id_txt,
                "metodo_pago": metodo,
                "monto": monto,
                "descripcion": "Ingreso automático por venta desde ventas_pagos",
                "usuario": usuario,
                "anulado": False,
            }
            if "json_safe_payload" in globals():
                payload = json_safe_payload(payload)
            supabase.table("movimientos_caja").insert(payload).execute()

        return True
    except Exception as e:
        try:
            st.warning(f"No se pudo reconstruir movimientos de caja: {e}")
        except Exception:
            pass
        return False




def obtener_receta_combo(producto: dict) -> dict | None:
    obs = producto.get("observacion") or ""
    if isinstance(obs, str) and obs.startswith("RECETA_COMBO:"):
        try:
            import json
            receta_str = obs.replace("RECETA_COMBO:", "").strip()
            return json.loads(receta_str)
        except Exception:
            return None
    return None


def obtener_atributos_producto(producto: dict) -> dict | None:
    obs = producto.get("observacion") or ""
    if isinstance(obs, str) and obs.startswith("ATRIBUTOS:"):
        try:
            import json
            attr_str = obs.replace("ATRIBUTOS:", "").strip()
            return json.loads(attr_str)
        except Exception:
            return None
    return None


# =========================================================
# DASHBOARD
# =========================================================
