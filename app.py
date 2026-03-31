
import io
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd
import streamlit as st
from supabase import Client, create_client

st.set_page_config(page_title="BIBE RON 01", layout="wide")

st.markdown("""
<style>
:root {
    --azul-claro: #dff4ff;
    --azul: #b9e6ff;
    --azul-fuerte: #5dbdf2;
    --rojo: #d94b62;
    --rojo-claro: #ffe2e8;
    --texto: #17384d;
}
html, body, [class*="css"] { color: var(--texto); }
.block-container { padding-top: 1rem; }
h1, h2, h3 { color: #18445f; }
.soft-box {
    background: #f8fdff; border: 1px solid #d8eef8; border-radius: 16px; padding: 14px;
}
.pos-card {
    background: linear-gradient(180deg, var(--azul-claro), #ffffff);
    border: 1px solid #d6edf9; border-radius: 18px; padding: 14px;
    box-shadow: 0 5px 14px rgba(20,50,70,.08); min-height: 185px;
}
.red-box {
    background: #fff6f8; border: 1px solid #ffd3db; border-radius: 16px; padding: 14px;
}
.stButton>button { border-radius: 10px; }
div[data-testid="stMetric"] {
    background: white; border: 1px solid #e7f2f8; border-radius: 12px; padding: 10px;
    box-shadow: 0 2px 8px rgba(0,0,0,.04);
}
</style>
""", unsafe_allow_html=True)

def _secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

SUPABASE_URL = _secret("SUPABASE_URL", "")
SUPABASE_KEY = _secret("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Faltan SUPABASE_URL y/o SUPABASE_KEY en secrets.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "carrito" not in st.session_state:
    st.session_state.carrito = []
if "pos_search" not in st.session_state:
    st.session_state.pos_search = ""
if "pos_qty" not in st.session_state:
    st.session_state.pos_qty = 1.0

def now_str() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")

def today_str() -> str:
    return date.today().isoformat()

def to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        if isinstance(v, str):
            v = v.replace("RD$", "").replace("rd$", "").replace("$", "").replace(",", "").strip()
        return float(v)
    except Exception:
        return default

def norm(v: Any) -> str:
    return "" if v is None else str(v).strip().lower()

def can(flag: str) -> bool:
    user = st.session_state.usuario or {}
    if norm(user.get("rol")) == "admin":
        return True
    return bool(user.get(flag, False))

def read_table(tabla: str, order: Optional[str] = None) -> pd.DataFrame:
    q = supabase.table(tabla).select("*")
    if order:
        q = q.order(order)
    r = q.execute()
    return pd.DataFrame(r.data or [])

def log_action(accion: str, tabla: str, detalle: str = ""):
    try:
        user = st.session_state.usuario or {}
        supabase.table("auditoria").insert({
            "fecha": now_str(),
            "usuario": user.get("usuario", "sistema"),
            "accion": accion,
            "tabla": tabla,
            "detalle": detalle[:1000]
        }).execute()
    except Exception:
        pass

def insert_row(tabla: str, payload: dict) -> bool:
    try:
        supabase.table(tabla).insert(payload).execute()
        log_action("crear", tabla, str(payload))
        return True
    except Exception as e:
        st.error(f"Error insertando en {tabla}: {e}")
        return False

def update_row(tabla: str, row_id: Any, payload: dict) -> bool:
    try:
        supabase.table(tabla).update(payload).eq("id", row_id).execute()
        log_action("editar", tabla, f"id={row_id} | {payload}")
        return True
    except Exception as e:
        st.error(f"Error actualizando {tabla}: {e}")
        return False

def delete_row(tabla: str, row_id: Any) -> bool:
    try:
        supabase.table(tabla).delete().eq("id", row_id).execute()
        log_action("eliminar", tabla, f"id={row_id}")
        return True
    except Exception as e:
        st.error(f"Error eliminando en {tabla}: {e}")
        return False

def parse_upload(file) -> pd.DataFrame:
    try:
        if file.name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(file)
            except Exception:
                file.seek(0)
                df = pd.read_csv(file, encoding="latin-1")
        else:
            df = pd.read_excel(file)
        df.columns = [norm(c).replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        st.error(f"No se pudo leer el archivo: {e}")
        return pd.DataFrame()

def export_buttons(df: pd.DataFrame, base_name: str):
    if df.empty:
        return
    csv = df.to_csv(index=False).encode("utf-8-sig")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("⬇️ Descargar CSV", csv, f"{base_name}.csv", "text/csv", key=f"csv_{base_name}")
    with c2:
        x = io.BytesIO()
        with pd.ExcelWriter(x, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="datos")
        st.download_button("⬇️ Descargar Excel", x.getvalue(), f"{base_name}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key=f"xlsx_{base_name}")

def get_config() -> dict:
    df = read_table("configuracion_sistema")
    if df.empty:
        return {"negocio_nombre":"BIBE RON 01","nombre_sistema":"M & A Sistema","propietario":"Nelly Aguilera","slogan":"Control total de ventas e inventario"}
    return df.iloc[0].to_dict()

def stock_df() -> pd.DataFrame:
    inv = read_table("inventario_actual")
    if inv.empty:
        return inv
    if "cantidad" not in inv.columns and "existencia_sistema" in inv.columns:
        inv["cantidad"] = pd.to_numeric(inv["existencia_sistema"], errors="coerce").fillna(0)
    else:
        inv["cantidad"] = pd.to_numeric(inv.get("cantidad", 0), errors="coerce").fillna(0)
    return inv

def get_stock(product_id=None, product_name: str = "") -> float:
    inv = stock_df()
    if inv.empty:
        return 0.0
    if product_id is not None and "producto_id" in inv.columns:
        m = inv[inv["producto_id"].astype(str) == str(product_id)]
        if not m.empty:
            return to_float(m.iloc[0].get("cantidad"))
    if product_name:
        col = "producto" if "producto" in inv.columns else ("nombre" if "nombre" in inv.columns else None)
        if col:
            m = inv[inv[col].astype(str).str.lower() == product_name.lower()]
            if not m.empty:
                return to_float(m.iloc[0].get("cantidad"))
    return 0.0

def sync_product_inventory(prod: dict, qty: Optional[float] = None):
    inv = stock_df()
    pid = prod.get("id")
    nombre = prod.get("nombre", "")
    cantidad = to_float(qty if qty is not None else prod.get("cantidad", 0))
    payload = {
        "producto_id": pid, "producto": nombre, "cantidad": cantidad,
        "costo_unitario": to_float(prod.get("costo")), "precio_unitario": to_float(prod.get("precio")),
        "activo": bool(prod.get("activo", True)),
        "usuario": (st.session_state.usuario or {}).get("usuario", "sistema"),
        "actualizado": now_str(),
    }
    if not inv.empty:
        if "producto_id" in inv.columns:
            m = inv[inv["producto_id"].astype(str) == str(pid)]
            if not m.empty:
                return update_row("inventario_actual", m.iloc[0]["id"], payload)
        if "producto" in inv.columns:
            m = inv[inv["producto"].astype(str).str.lower() == nombre.lower()]
            if not m.empty:
                return update_row("inventario_actual", m.iloc[0]["id"], payload)
    return insert_row("inventario_actual", payload)

def inventory_movement(prod: dict, tipo: str, cantidad: float, referencia_tabla: str = "", referencia_id: str = "", costo_unitario: float = 0.0, observacion: str = ""):
    insert_row("movimientos", {
        "fecha": now_str(), "producto_id": prod.get("id"), "producto": prod.get("nombre"),
        "tipo_movimiento": tipo, "referencia_tabla": referencia_tabla, "referencia_id": str(referencia_id),
        "cantidad": cantidad, "costo_unitario": costo_unitario,
        "usuario": (st.session_state.usuario or {}).get("usuario", "sistema"), "observacion": observacion,
    })

def update_inventory_qty(product_id: Any, product_name: str, delta: float, costo: float = 0.0, ref_tabla: str = "", ref_id: str = "", obs: str = "") -> bool:
    inv = stock_df()
    row = None
    if not inv.empty and "producto_id" in inv.columns:
        m = inv[inv["producto_id"].astype(str) == str(product_id)]
        if not m.empty:
            row = m.iloc[0]
    if row is None and not inv.empty and "producto" in inv.columns:
        m = inv[inv["producto"].astype(str).str.lower() == product_name.lower()]
        if not m.empty:
            row = m.iloc[0]
    if row is None:
        payload = {
            "producto_id": product_id, "producto": product_name, "cantidad": max(delta, 0),
            "costo_unitario": costo, "precio_unitario": 0, "activo": True,
            "usuario": (st.session_state.usuario or {}).get("usuario", "sistema"), "actualizado": now_str(),
        }
        ok = insert_row("inventario_actual", payload)
        if ok:
            inventory_movement({"id": product_id, "nombre": product_name}, "entrada" if delta >= 0 else "salida", delta, ref_tabla, ref_id, costo, obs)
        return ok
    current = to_float(row.get("cantidad"))
    new_qty = current + delta
    if new_qty < 0:
        return False
    ok = update_row("inventario_actual", row["id"], {
        "cantidad": new_qty,
        "costo_unitario": costo if costo else to_float(row.get("costo_unitario")),
        "actualizado": now_str(),
        "usuario": (st.session_state.usuario or {}).get("usuario", "sistema"),
    })
    if ok:
        inventory_movement({"id": product_id, "nombre": product_name}, "entrada" if delta >= 0 else "salida", delta, ref_tabla, ref_id, costo, obs)
    return ok

def merge_products_with_stock() -> pd.DataFrame:
    prods = read_table("productos")
    inv = stock_df()
    if prods.empty:
        return prods
    if inv.empty:
        prods["stock_real"] = 0.0
        return prods
    stock_map, name_map = {}, {}
    if "producto_id" in inv.columns:
        for _, r in inv.iterrows():
            if r.get("producto_id"):
                stock_map[str(r["producto_id"])] = to_float(r.get("cantidad"))
    if "producto" in inv.columns:
        for _, r in inv.iterrows():
            name_map[str(r.get("producto", "")).lower()] = to_float(r.get("cantidad"))
    def stock_for_row(r):
        pid = str(r.get("id"))
        if pid in stock_map:
            return stock_map[pid]
        return name_map.get(str(r.get("nombre", "")).lower(), to_float(r.get("cantidad")))
    prods["stock_real"] = prods.apply(stock_for_row, axis=1)
    return prods

def login():
    cfg = get_config()
    st.markdown(f"<h1 style='text-align:center'>{cfg.get('negocio_nombre','BIBE RON 01')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='text-align:center'>{cfg.get('nombre_sistema','M & A Sistema')}</h4>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center'>{cfg.get('slogan','')}</p>", unsafe_allow_html=True)
    st.markdown("<div class='soft-box'>", unsafe_allow_html=True)
    st.subheader("🔐 Iniciar sesión")
    user = st.text_input("Usuario")
    clave = st.text_input("Clave", type="password")
    if st.button("Entrar", use_container_width=True):
        r = supabase.table("usuarios").select("*").eq("usuario", user).eq("clave", clave).eq("activo", True).execute()
        if r.data:
            st.session_state.usuario = r.data[0]
            st.rerun()
        else:
            st.error("Usuario o clave incorrecta.")
    st.markdown("</div>", unsafe_allow_html=True)

def logout():
    st.session_state.usuario = None
    st.session_state.carrito = []
    st.rerun()

def dashboard():
    st.title("📊 Dashboard")
    ventas = read_table("ventas")
    compras = read_table("compras")
    gastos = read_table("gastos")
    inv = stock_df()
    credito = read_table("cuentas_por_cobrar")
    for d in (ventas, compras, gastos):
        if not d.empty and "fecha" in d.columns:
            d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce")
    c1, c2 = st.columns(2)
    with c1:
        desde = st.date_input("Desde", value=date.today().replace(day=1))
    with c2:
        hasta = st.date_input("Hasta", value=date.today())
    def fil(df):
        if df.empty or "fecha" not in df.columns:
            return df
        return df[(df["fecha"] >= pd.to_datetime(desde)) & (df["fecha"] <= pd.to_datetime(hasta))]
    ventas_f, compras_f, gastos_f = fil(ventas), fil(compras), fil(gastos)
    st.metric("Ventas", f"RD$ {to_float(ventas_f['total'].sum()) if not ventas_f.empty and 'total' in ventas_f.columns else 0:,.2f}")
    st.metric("Compras", f"RD$ {to_float(compras_f['total'].sum()) if not compras_f.empty and 'total' in compras_f.columns else 0:,.2f}")
    st.metric("Gastos", f"RD$ {to_float(gastos_f['monto'].sum()) if not gastos_f.empty and 'monto' in gastos_f.columns else 0:,.2f}")
    st.metric("Crédito", f"RD$ {to_float(credito['saldo_pendiente'].sum()) if not credito.empty and 'saldo_pendiente' in credito.columns else 0:,.2f}")
    if not ventas_f.empty and "fecha" in ventas_f.columns and "total" in ventas_f.columns:
        aux = ventas_f.copy()
        aux["dia"] = aux["fecha"].dt.date.astype(str)
        serie = aux.groupby("dia", as_index=False)["total"].sum()
        st.line_chart(serie.set_index("dia"))
    if not inv.empty and "producto" in inv.columns and "cantidad" in inv.columns:
        st.bar_chart(inv[["producto", "cantidad"]].head(20).set_index("producto"))

def productos():
    st.title("📦 Productos")
    tabs = st.tabs(["Listado", "Crear / Editar", "Subir Excel"])
    prods = read_table("productos")
    with tabs[0]:
        q = st.text_input("Buscar producto o código")
        view = prods.copy()
        if not view.empty and q:
            cond = view.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
            view = view[cond]
        st.dataframe(view, use_container_width=True)
        export_buttons(view, "productos")
    with tabs[1]:
        row, selected_id = {}, None
        if not prods.empty:
            opts = ["Nuevo"] + [f"{r['nombre']} | {r.get('codigo','')}" for _, r in prods.iterrows()]
            sel = st.selectbox("Selecciona para editar", opts)
            if sel != "Nuevo":
                row = prods[prods.apply(lambda x: f"{x['nombre']} | {x.get('codigo','')}" == sel, axis=1)].iloc[0]
                selected_id = row["id"]
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre", value=str(row.get("nombre", "")))
            codigo = st.text_input("Código", value=str(row.get("codigo", "")))
            costo = st.number_input("Costo", min_value=0.0, value=to_float(row.get("costo")), step=1.0)
            precio = st.number_input("Precio normal", min_value=0.0, value=to_float(row.get("precio")), step=1.0)
        with c2:
            precio_desc = st.number_input("Precio descuento", min_value=0.0, value=to_float(row.get("precio_descuento")), step=1.0)
            precio_esp = st.number_input("Precio especial", min_value=0.0, value=to_float(row.get("precio_especial")), step=1.0)
            activo = st.checkbox("Activo", value=bool(row.get("activo", True)))
            usa_inv = st.checkbox("Usa inventario", value=bool(row.get("usa_inventario", True)))
            cantidad = st.number_input("Cantidad inicial / actual", min_value=0.0, value=to_float(row.get("cantidad")), step=1.0)
        payload = {
            "fecha": today_str(), "nombre": nombre.strip(), "codigo": codigo.strip(), "costo": costo,
            "precio": precio, "precio_descuento": precio_desc, "precio_especial": precio_esp,
            "activo": activo, "usa_inventario": usa_inv, "cantidad": cantidad,
        }
        if st.button("💾 Guardar producto", use_container_width=True):
            if selected_id:
                ok = update_row("productos", selected_id, payload)
                payload["id"] = selected_id
            else:
                ok = insert_row("productos", payload)
                fresh = read_table("productos")
                m = fresh[fresh["nombre"].astype(str).str.lower() == nombre.strip().lower()].tail(1)
                payload["id"] = m.iloc[0]["id"] if not m.empty else None
            if ok:
                sync_product_inventory(payload, qty=cantidad if usa_inv else 0)
                st.success("Producto guardado y sincronizado con inventario.")
                st.rerun()
        if selected_id and can("puede_eliminar"):
            if st.button("🗑 Eliminar producto", use_container_width=True):
                delete_row("productos", selected_id)
                st.success("Producto eliminado.")
                st.rerun()
    with tabs[2]:
        file = st.file_uploader("Archivo", type=["xlsx", "xls", "csv"])
        if file is not None and st.button("Procesar archivo"):
            dfx = parse_upload(file)
            if not dfx.empty:
                rename = {}
                for c in dfx.columns:
                    cc = norm(c)
                    if cc in ["codigo_de_barra", "codigo", "barcode", "codigobarra"]:
                        rename[c] = "codigo"
                    elif cc in ["producto", "nombre", "descripcion"]:
                        rename[c] = "nombre"
                    elif cc in ["stock", "existencia", "cantidad"]:
                        rename[c] = "cantidad"
                    elif cc in ["precio_venta", "precio"]:
                        rename[c] = "precio"
                dfx = dfx.rename(columns=rename)
                current, proc = read_table("productos"), 0
                for _, r in dfx.iterrows():
                    nombre = str(r.get("nombre", "")).strip()
                    if not nombre:
                        continue
                    codigo = str(r.get("codigo", "")).strip()
                    payload = {
                        "fecha": today_str(), "nombre": nombre, "codigo": codigo, "costo": to_float(r.get("costo")),
                        "precio": to_float(r.get("precio")), "precio_descuento": to_float(r.get("precio_descuento")),
                        "precio_especial": to_float(r.get("precio_especial")), "activo": bool(r.get("activo", True)),
                        "usa_inventario": bool(r.get("usa_inventario", True)), "cantidad": to_float(r.get("cantidad")),
                    }
                    match = pd.DataFrame()
                    if not current.empty:
                        match = current[current["nombre"].astype(str).str.lower() == nombre.lower()]
                        if match.empty and codigo and "codigo" in current.columns:
                            match = current[current["codigo"].astype(str) == codigo]
                    if not match.empty:
                        ok = update_row("productos", match.iloc[0]["id"], payload)
                        payload["id"] = match.iloc[0]["id"]
                    else:
                        ok = insert_row("productos", payload)
                        fresh = read_table("productos")
                        m = fresh[fresh["nombre"].astype(str).str.lower() == nombre.lower()].tail(1)
                        payload["id"] = m.iloc[0]["id"] if not m.empty else None
                    if ok:
                        sync_product_inventory(payload, qty=payload["cantidad"] if payload["usa_inventario"] else 0)
                        proc += 1
                st.success(f"Procesados {proc} productos.")
                st.rerun()

def clientes():
    d = read_table("clientes")
    st.title("👥 Clientes")
    st.dataframe(d, use_container_width=True)
    export_buttons(d, "clientes")

def proveedores():
    d = read_table("proveedores")
    st.title("🏢 Proveedores")
    st.dataframe(d, use_container_width=True)
    export_buttons(d, "proveedores")

def compras():
    st.title("📥 Compras")
    products = merge_products_with_stock()
    provs = read_table("proveedores")
    search = st.text_input("Buscar producto por nombre o código")
    view = products.copy()
    if not view.empty and search:
        cond = view.astype(str).apply(lambda c: c.str.contains(search, case=False, na=False)).any(axis=1)
        view = view[cond]
    cols = st.columns(4)
    for i, (_, r) in enumerate(view.head(32).iterrows()):
        with cols[i % 4]:
            st.markdown("<div class='pos-card'>", unsafe_allow_html=True)
            st.markdown(f"**{r.get('nombre','')}**")
            st.caption(f"Código: {r.get('codigo','')}")
            st.write(f"Costo actual: RD$ {to_float(r.get('costo')):,.2f}")
            st.write(f"Stock: {to_float(r.get('stock_real')):,.2f}")
            if st.button("Seleccionar", key=f"compra_sel_{r['id']}"):
                st.session_state["compra_prod_id"] = str(r["id"])
            st.markdown("</div>", unsafe_allow_html=True)
    sid = st.session_state.get("compra_prod_id")
    if sid:
        m = products[products["id"].astype(str) == sid]
        if not m.empty:
            prod = m.iloc[0]
            cantidad = st.number_input("Cantidad", min_value=1.0, value=1.0, step=1.0)
            costo_unit = st.number_input("Costo unitario", min_value=0.0, value=max(to_float(prod.get("costo")), 0.0), step=1.0)
            proveedor = st.selectbox("Proveedor", [""] + (provs["nombre"].tolist() if not provs.empty else []))
            fecha_comp = st.date_input("Fecha compra", value=date.today())
            fifo = st.checkbox("Guardar lote FIFO", value=True)
            if st.button("Guardar compra", use_container_width=True):
                payload = {
                    "fecha": str(fecha_comp), "producto_id": prod.get("id"), "producto": prod.get("nombre"),
                    "cantidad": cantidad, "costo_unitario": costo_unit, "total": cantidad * costo_unit,
                    "proveedor": proveedor, "usuario": (st.session_state.usuario or {}).get("usuario", "sistema")
                }
                ok = insert_row("compras", payload)
                if ok:
                    update_inventory_qty(prod.get("id"), prod.get("nombre"), cantidad, costo_unit, "compras", "", "Compra")
                    update_row("productos", prod.get("id"), {"costo": costo_unit})
                    if fifo:
                        insert_row("inventario_lotes", {
                            "fecha": now_str(), "producto_id": prod.get("id"), "producto": prod.get("nombre"),
                            "cantidad_inicial": cantidad, "cantidad_restante": cantidad,
                            "costo_unitario": costo_unit, "fecha_compra": str(fecha_comp), "activo": True
                        })
                    st.success("Compra guardada e inventario actualizado.")
                    st.rerun()
    dc = read_table("compras")
    st.dataframe(dc, use_container_width=True)
    export_buttons(dc, "compras")

def inventario_actual():
    inv = stock_df()
    st.title("📦 Inventario actual")
    st.dataframe(inv, use_container_width=True)
    export_buttons(inv, "inventario_actual")

def conteo_inventario():
    inv = stock_df()
    st.title("🧮 Conteo de inventario")
    if inv.empty:
        st.info("No hay inventario.")
        return
    rows = []
    for i, (_, r) in enumerate(inv.iterrows()):
        c1, c2, c3, c4 = st.columns([4, 2, 2, 2])
        nombre = r.get("producto", r.get("nombre", ""))
        sistema = to_float(r.get("cantidad"))
        c1.write(nombre)
        c2.write(f"Sistema: {sistema}")
        fisica = c3.number_input("Física", min_value=0.0, value=sistema, step=1.0, key=f"fisica_{i}")
        dif = fisica - sistema
        c4.write(f"Dif: {dif}")
        rows.append({"producto_id": r.get("producto_id"), "producto": nombre, "cantidad_sistema": sistema, "cantidad_fisica": fisica, "diferencia": dif})
    if st.button("Guardar conteo"):
        for item in rows:
            insert_row("conteo_inventario", {
                "fecha": now_str(), "producto_id": item["producto_id"], "producto": item["producto"],
                "cantidad_sistema": item["cantidad_sistema"], "cantidad_fisica": item["cantidad_fisica"],
                "diferencia": item["diferencia"], "usuario": (st.session_state.usuario or {}).get("usuario", "sistema"),
                "observacion": "Conteo manual"
            })
        st.success("Conteo guardado.")
        st.rerun()

def ajuste_inventario():
    conteos, inv = read_table("conteo_inventario"), stock_df()
    st.title("🛠 Ajuste de inventario")
    if conteos.empty:
        st.info("No hay conteos.")
        return
    if "fecha" in conteos.columns:
        conteos["fecha"] = pd.to_datetime(conteos["fecha"], errors="coerce")
        conteos = conteos.sort_values("fecha", ascending=False)
    latest = conteos.groupby("producto").head(1) if "producto" in conteos.columns else conteos.head(20)
    st.dataframe(latest, use_container_width=True)
    if st.button("Aplicar último conteo"):
        for _, r in latest.iterrows():
            nombre = r.get("producto", "")
            fisica = to_float(r.get("cantidad_fisica"))
            if "producto" in inv.columns:
                m = inv[inv["producto"].astype(str).str.lower() == str(nombre).lower()]
                if not m.empty:
                    row_inv = m.iloc[0]
                    current = to_float(row_inv.get("cantidad"))
                    diff = fisica - current
                    update_row("inventario_actual", row_inv["id"], {"cantidad": fisica, "actualizado": now_str()})
                    insert_row("ajustes_inventario", {
                        "fecha": now_str(), "producto_id": row_inv.get("producto_id"), "producto": nombre,
                        "cantidad": diff, "motivo": "Ajuste por conteo",
                        "usuario": (st.session_state.usuario or {}).get("usuario", "sistema"),
                        "observacion": f"Sistema {current} vs físico {fisica}"
                    })
                    inventory_movement({"id": row_inv.get("producto_id"), "nombre": nombre}, "ajuste", diff, "ajustes_inventario", "", 0.0, "Ajuste por conteo")
        st.success("Ajuste aplicado.")
        st.rerun()

def pos():
    st.title("🛒 POS PRO")
    productos = merge_products_with_stock()
    top1, top2, top3 = st.columns([1, 2, 1])
    with top1:
        st.session_state.pos_qty = st.number_input("Cant", min_value=1.0, value=float(st.session_state.pos_qty), step=1.0)
    with top2:
        st.session_state.pos_search = st.text_input("Código o nombre", value=st.session_state.pos_search)
    with top3:
        tipo_precio = st.selectbox("Tipo precio", ["normal", "descuento", "especial"])
    view = productos.copy()
    if st.session_state.pos_search:
        cond = view.astype(str).apply(lambda c: c.str.contains(st.session_state.pos_search, case=False, na=False)).any(axis=1)
        view = view[cond]
    if "activo" in view.columns:
        view = view[view["activo"] == True]
    cols = st.columns(4)
    for i, (_, r) in enumerate(view.head(40).iterrows()):
        with cols[i % 4]:
            st.markdown("<div class='pos-card'>", unsafe_allow_html=True)
            st.markdown(f"**{r.get('nombre','')}**")
            st.caption(f"Código: {r.get('codigo','')}")
            precio = to_float(r.get("precio"))
            if tipo_precio == "descuento":
                precio = to_float(r.get("precio_descuento")) or precio
            elif tipo_precio == "especial":
                precio = to_float(r.get("precio_especial")) or precio
            st.write(f"Precio: RD$ {precio:,.2f}")
            stock = to_float(r.get("stock_real"))
            st.write(f"Stock: {stock:,.2f}")
            usa_inv = bool(r.get("usa_inventario", True))
            disabled = usa_inv and stock <= 0
            if st.button("Agregar", key=f"add_{r['id']}", disabled=disabled):
                qty = float(st.session_state.pos_qty)
                if usa_inv and qty > stock:
                    st.error("No hay suficiente stock.")
                else:
                    found = False
                    for item in st.session_state.carrito:
                        if str(item["id"]) == str(r["id"]):
                            nueva = item["cantidad"] + qty
                            if usa_inv and nueva > stock:
                                st.error("No hay suficiente stock.")
                            else:
                                item["cantidad"] = nueva
                            found = True
                            break
                    if not found:
                        st.session_state.carrito.append({
                            "id": r["id"], "codigo": r.get("codigo", ""), "nombre": r.get("nombre", ""),
                            "cantidad": qty, "precio": precio, "stock": stock,
                            "usa_inventario": usa_inv, "descuento_pct": 0.0
                        })
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    st.subheader("Factura")
    if not st.session_state.carrito:
        st.info("Carrito vacío.")
        return
    total_real = 0.0
    for i, item in enumerate(st.session_state.carrito):
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.4, 3.2, 1.3, 1.6, 1.4, 1.8, 0.8])
        c1.write(item.get("codigo", ""))
        c2.write(item["nombre"])
        item["cantidad"] = c3.number_input("Cant", min_value=0.0, value=float(item["cantidad"]), step=1.0, key=f"cant_pos_{i}")
        if can("puede_editar_ventas"):
            item["precio"] = c4.number_input("Precio", min_value=0.0, value=float(item["precio"]), step=1.0, key=f"precio_pos_{i}")
            item["descuento_pct"] = c5.number_input("Desc %", min_value=0.0, value=float(item.get("descuento_pct", 0.0)), step=1.0, key=f"desc_pos_{i}")
        else:
            c4.write(f"RD$ {item['precio']:,.2f}")
            c5.write(f"{item.get('descuento_pct',0):,.0f}%")
        sub = item["cantidad"] * item["precio"]
        desc = sub * (item.get("descuento_pct", 0) / 100)
        linea = sub - desc
        c6.write(f"RD$ {linea:,.2f}")
        total_real += linea
        if c7.button("❌", key=f"remove_pos_{i}"):
            st.session_state.carrito.pop(i)
            st.rerun()
    metodo = st.selectbox("Método de pago", ["efectivo", "tarjeta", "transferencia", "credito"])
    recargo_visual = 0.0
    if metodo == "tarjeta":
        usar_recargo = st.checkbox("Aplicar recargo visual", value=False)
        if usar_recargo:
            porc_recargo = st.number_input("Porcentaje recargo", min_value=0.0, value=4.0, step=0.5)
            recargo_visual = total_real * (porc_recargo / 100)
    total_cobro = total_real + recargo_visual
    cliente_nombre = ""
    cliente_id = None
    if metodo == "credito":
        cli = read_table("clientes")
        if not cli.empty:
            cliente_nombre = st.selectbox("Cliente", cli["nombre"].tolist())
            rowc = cli[cli["nombre"] == cliente_nombre].iloc[0]
            cliente_id = rowc["id"]
    recibido = 0.0
    devuelta = 0.0
    if metodo == "efectivo":
        recibido = st.number_input("Recibido", min_value=0.0, value=0.0, step=1.0)
        devuelta = recibido - total_cobro if recibido >= total_cobro else 0.0
    obs = st.text_input("Observación")
    st.metric("Subtotal real", f"RD$ {total_real:,.2f}")
    st.metric("Recargo visual", f"RD$ {recargo_visual:,.2f}")
    st.metric("Total a cobrar", f"RD$ {total_cobro:,.2f}")
    if metodo == "efectivo":
        st.metric("Devuelta", f"RD$ {devuelta:,.2f}")
    if st.button("💰 Cobrar", use_container_width=True):
        for item in st.session_state.carrito:
            if item["usa_inventario"] and item["cantidad"] > get_stock(item["id"], item["nombre"]):
                st.error(f"No hay stock suficiente de {item['nombre']}.")
                return
        if metodo == "efectivo" and recibido < total_cobro:
            st.error("El dinero recibido no alcanza.")
            return
        if metodo == "credito" and not cliente_nombre:
            st.error("Debes seleccionar un cliente.")
            return
        user = st.session_state.usuario or {}
        venta_payload = {
            "fecha": now_str(), "subtotal": total_real, "descuento": 0, "recargo": 0, "total": total_real,
            "metodo_pago": metodo, "cliente_id": cliente_id, "cliente_nombre": cliente_nombre,
            "usuario": user.get("usuario", "sistema"), "dia_operativo": today_str(),
            "tipo_venta": "POS", "estado": "completada", "observacion": obs if obs else None
        }
        vr = supabase.table("ventas").insert(venta_payload).execute()
        venta_id = vr.data[0]["id"]
        prods_lookup = merge_products_with_stock()
        for item in st.session_state.carrito:
            prod = prods_lookup[prods_lookup["id"].astype(str) == str(item["id"])].iloc[0]
            costo = to_float(prod.get("costo"))
            sub = item["cantidad"] * item["precio"]
            desc = sub * (item.get("descuento_pct", 0) / 100)
            linea = sub - desc
            supabase.table("detalle_venta").insert({
                "fecha": now_str(), "venta_id": venta_id, "producto_id": item["id"], "codigo": item.get("codigo", ""),
                "producto": item["nombre"], "cantidad": item["cantidad"], "precio_unitario": item["precio"],
                "costo_unitario": costo, "descuento": item.get("descuento_pct", 0), "recargo": 0,
                "total_linea": linea, "ganancia_linea": (item["precio"] - costo) * item["cantidad"],
                "usuario": user.get("usuario", "sistema")
            }).execute()
            if item["usa_inventario"]:
                update_inventory_qty(item["id"], item["nombre"], -item["cantidad"], costo, "ventas", str(venta_id), "Venta POS")
        supabase.table("ventas_pagos").insert({
            "fecha": now_str(), "venta_id": venta_id, "metodo": metodo, "monto": total_real,
            "referencia": f"Cobro cliente {total_cobro:.2f} | Recargo visual {recargo_visual:.2f}",
            "usuario": user.get("usuario", "sistema")
        }).execute()
        if metodo == "credito":
            supabase.table("cuentas_por_cobrar").insert({
                "fecha": now_str(), "cliente_id": cliente_id, "cliente_nombre": cliente_nombre, "venta_id": venta_id,
                "monto_original": total_real, "monto_abonado": 0, "saldo_pendiente": total_real,
                "estado": "pendiente", "usuario": user.get("usuario", "sistema")
            }).execute()
        if metodo in ["efectivo", "tarjeta", "transferencia"]:
            insert_row("movimientos_caja", {
                "fecha": now_str(), "dia_operativo": today_str(), "tipo": "entrada", "tipo_movimiento": "entrada",
                "origen": "venta", "referencia": str(venta_id), "referencia_id": str(venta_id), "metodo_pago": metodo,
                "monto": total_real, "descripcion": f"Venta POS #{venta_id}", "usuario": user.get("usuario", "sistema")
            })
        st.session_state.carrito = []
        st.success(f"Venta guardada. Total real RD$ {total_real:,.2f} | Cobro al cliente RD$ {total_cobro:,.2f}")
        st.rerun()

def ventas():
    v = read_table("ventas")
    st.title("📤 Ventas")
    if v.empty:
        st.info("No hay ventas.")
        return
    c1, c2, c3 = st.columns(3)
    with c1:
        q = st.text_input("Buscar venta")
    with c2:
        metodos = ["Todos"] + sorted(v["metodo_pago"].dropna().astype(str).unique().tolist()) if "metodo_pago" in v.columns else ["Todos"]
        metodo = st.selectbox("Método pago", metodos)
    with c3:
        fecha = st.text_input("Fecha contiene (YYYY-MM-DD)", "")
    if q:
        cond = v.astype(str).apply(lambda c: c.str.contains(q, case=False, na=False)).any(axis=1)
        v = v[cond]
    if metodo != "Todos" and "metodo_pago" in v.columns:
        v = v[v["metodo_pago"].astype(str) == metodo]
    if fecha and "fecha" in v.columns:
        v = v[v["fecha"].astype(str).str.contains(fecha, na=False)]
    st.dataframe(v, use_container_width=True)
    export_buttons(v, "ventas")
    if can("puede_editar_ventas"):
        ids = v["id"].astype(str).tolist()
        if ids:
            sel = st.selectbox("Factura / venta", ids)
            row = v[v["id"].astype(str) == sel].iloc[0]
            nuevo_metodo = st.selectbox("Método", ["efectivo", "tarjeta", "transferencia", "credito"], index=["efectivo","tarjeta","transferencia","credito"].index(str(row.get("metodo_pago","efectivo"))) if str(row.get("metodo_pago","efectivo")) in ["efectivo","tarjeta","transferencia","credito"] else 0)
            nuevo_cliente = st.text_input("Cliente", value=str(row.get("cliente_nombre", "")))
            nueva_obs = st.text_input("Observación", value=str(row.get("observacion", "")))
            if st.button("Guardar edición venta"):
                update_row("ventas", row["id"], {"metodo_pago": nuevo_metodo, "cliente_nombre": nuevo_cliente, "observacion": nueva_obs})
                st.success("Venta actualizada.")
                st.rerun()

def reportes():
    st.title("📑 Reportes")
    tabs = st.tabs(["Ventas", "Mis ventas", "Crédito", "Auditoría"])
    with tabs[0]:
        ventas()
    with tabs[1]:
        user = st.session_state.usuario or {}
        v = read_table("ventas")
        if not v.empty and "usuario" in v.columns:
            v = v[v["usuario"].astype(str) == str(user.get("usuario", ""))]
        st.dataframe(v.tail(30), use_container_width=True)
        total = to_float(v["total"].sum()) if not v.empty and "total" in v.columns else 0
        st.metric("Total vendido", f"RD$ {total:,.2f}")
    with tabs[2]:
        c = read_table("cuentas_por_cobrar")
        st.dataframe(c, use_container_width=True)
        export_buttons(c, "creditos")
    with tabs[3]:
        a = read_table("auditoria")
        st.dataframe(a, use_container_width=True)
        export_buttons(a, "auditoria")

def apertura_caja():
    st.title("💵 Apertura de caja")
    fondo = st.number_input("Fondo inicial", min_value=0.0, value=0.0, step=1.0)
    if st.button("Abrir caja", use_container_width=True):
        user = st.session_state.usuario or {}
        insert_row("movimientos_caja", {"fecha": now_str(), "dia_operativo": today_str(), "tipo": "apertura", "tipo_movimiento": "apertura", "origen": "caja", "monto": fondo, "descripcion": "Apertura de caja", "usuario": user.get("usuario", "sistema")})
        insert_row("cierre_caja", {"fecha": now_str(), "usuario": user.get("usuario", "sistema"), "fondo_inicial": fondo, "efectivo_esperado": fondo, "efectivo_real": 0, "diferencia": 0, "estado": "abierta", "dia_operativo": today_str()})
        st.success("Caja abierta.")

def cierre_caja():
    cierres = read_table("cierre_caja")
    movs = read_table("movimientos_caja")
    user = st.session_state.usuario or {}
    st.title("🔒 Cierre de caja")
    abiertos = cierres[cierres["estado"].astype(str).str.lower() == "abierta"] if not cierres.empty and "estado" in cierres.columns else pd.DataFrame()
    if abiertos.empty:
        st.info("No hay caja abierta.")
        return
    caja = abiertos.iloc[-1]
    dia = str(caja.get("dia_operativo", today_str()))
    esperado = to_float(caja.get("fondo_inicial"))
    if not movs.empty and "dia_operativo" in movs.columns:
        dm = movs[movs["dia_operativo"].astype(str) == dia]
        for _, r in dm.iterrows():
            t = norm(r.get("tipo", r.get("tipo_movimiento", "")))
            monto = to_float(r.get("monto"))
            if t in ["entrada", "apertura"]:
                esperado += monto
            elif t in ["salida", "gasto"]:
                esperado -= monto
    real = st.number_input("Efectivo real", min_value=0.0, value=max(esperado, 0.0), step=1.0)
    diferencia = real - esperado
    tipo_dif = "sobrante" if diferencia > 0 else ("faltante" if diferencia < 0 else "exacto")
    st.metric("Efectivo esperado", f"RD$ {esperado:,.2f}")
    st.metric("Diferencia", f"RD$ {diferencia:,.2f}")
    obs = st.text_area("Observación")
    if st.button("Cerrar caja", use_container_width=True):
        update_row("cierre_caja", caja["id"], {"efectivo_esperado": esperado, "efectivo_real": real, "diferencia": diferencia, "tipo_diferencia": tipo_dif, "observacion": obs, "usuario_revision": user.get("usuario", "sistema"), "estado": "cerrada"})
        st.success("Caja cerrada.")

def usuarios():
    du = read_table("usuarios")
    st.title("👤 Usuarios")
    st.dataframe(du, use_container_width=True)
    row, selected_id = {}, None
    if not du.empty:
        opts = ["Nuevo"] + du["usuario"].astype(str).tolist()
        sel = st.selectbox("Usuario", opts)
        if sel != "Nuevo":
            row = du[du["usuario"].astype(str) == sel].iloc[0]
            selected_id = row["id"]
    nombre = st.text_input("Nombre", value=str(row.get("nombre", "")))
    usuario_v = st.text_input("Usuario", value=str(row.get("usuario", "")))
    clave = st.text_input("Clave", value=str(row.get("clave", "")))
    rol = st.selectbox("Rol", ["admin", "gerente", "cajera"], index=["admin", "gerente", "cajera"].index(str(row.get("rol", "cajera"))) if str(row.get("rol", "cajera")) in ["admin", "gerente", "cajera"] else 2)
    activo = st.checkbox("Activo", value=bool(row.get("activo", True)))
    usar_pos = st.checkbox("Usar POS", value=bool(row.get("usar_pos", True if rol in ["admin","cajera"] else False)))
    ver_dashboard = st.checkbox("Ver dashboard", value=bool(row.get("ver_dashboard", True if rol=="admin" else False)))
    ver_productos = st.checkbox("Ver productos", value=bool(row.get("ver_productos", True if rol=="admin" else False)))
    editar_productos = st.checkbox("Editar productos", value=bool(row.get("editar_productos", True if rol=="admin" else False)))
    ver_compras = st.checkbox("Ver compras", value=bool(row.get("ver_compras", True if rol=="admin" else False)))
    ver_inventario = st.checkbox("Ver inventario", value=bool(row.get("ver_inventario", True if rol=="admin" else False)))
    ver_caja = st.checkbox("Ver caja", value=bool(row.get("ver_caja", True if rol in ["admin","cajera"] else False)))
    cerrar_caja_perm = st.checkbox("Cerrar caja", value=bool(row.get("cerrar_caja", True if rol in ["admin","cajera"] else False)))
    ver_credito = st.checkbox("Ver crédito", value=bool(row.get("ver_credito", True if rol=="admin" else False)))
    puede_editar_ventas = st.checkbox("Editar ventas", value=bool(row.get("puede_editar_ventas", True if rol=="admin" else False)))
    puede_eliminar = st.checkbox("Eliminar", value=bool(row.get("puede_eliminar", True if rol=="admin" else False)))
    puede_configurar = st.checkbox("Configurar", value=bool(row.get("puede_configurar", True if rol=="admin" else False)))
    payload = {"nombre": nombre, "usuario": usuario_v, "clave": clave, "rol": rol, "activo": activo, "usar_pos": usar_pos, "ver_dashboard": ver_dashboard, "ver_productos": ver_productos, "editar_productos": editar_productos, "ver_compras": ver_compras, "ver_inventario": ver_inventario, "ver_caja": ver_caja, "cerrar_caja": cerrar_caja_perm, "ver_credito": ver_credito, "puede_editar_ventas": puede_editar_ventas, "puede_eliminar": puede_eliminar, "puede_configurar": puede_configurar, "puede_vender": usar_pos, "puede_ver_reportes": True if rol in ["admin","gerente"] else False, "puede_registrar_compras": True if rol=="admin" else False, "puede_registrar_gastos": True if rol=="admin" else False}
    if st.button("Guardar usuario"):
        if selected_id:
            update_row("usuarios", selected_id, payload)
        else:
            insert_row("usuarios", payload)
        st.success("Usuario guardado.")
        st.rerun()

def configuracion():
    cfg = read_table("configuracion_sistema")
    row = cfg.iloc[0].to_dict() if not cfg.empty else {}
    st.title("⚙️ Configuración")
    negocio = st.text_input("Nombre negocio", value=str(row.get("negocio_nombre", "BIBE RON 01")))
    sistema = st.text_input("Nombre sistema", value=str(row.get("nombre_sistema", "M & A Sistema")))
    propietario = st.text_input("Propietario", value=str(row.get("propietario", "Nelly Aguilera")))
    slogan = st.text_input("Slogan", value=str(row.get("slogan", "")))
    if st.button("Guardar configuración"):
        payload = {"negocio_nombre": negocio, "nombre_sistema": sistema, "propietario": propietario, "slogan": slogan}
        if not cfg.empty:
            update_row("configuracion_sistema", cfg.iloc[0]["id"], payload)
        else:
            insert_row("configuracion_sistema", payload)
        st.success("Configuración guardada.")
        st.rerun()

def simple_table_module(title: str, table: str):
    d = read_table(table)
    st.title(title)
    st.dataframe(d, use_container_width=True)
    export_buttons(d, table)

def admin_menu():
    return ["Dashboard","Apertura de Caja","POS","Cierre de Caja","Productos","Clientes","Proveedores","Inventario Actual","Conteo Inventario","Ajuste Inventario","Ventas","Compras","Catálogo de Gastos","Gastos","Empleados","Adelantos Empleados","Pérdidas","Gastos Dueño","Estado de Resultados","Reportes","Crédito","Usuarios","Configuración","Auditoría"]

def caja_menu():
    return ["Apertura de Caja","POS","Cierre de Caja","Reportes"]

if st.session_state.usuario is None:
    login()
else:
    cfg = get_config()
    user = st.session_state.usuario
    rol = norm(user.get("rol"))
    st.sidebar.markdown(f"## {cfg.get('negocio_nombre', 'BIBE RON 01')}")
    st.sidebar.write(f"👤 {user.get('nombre', 'Usuario')}")
    st.sidebar.write(f"Rol: {user.get('rol', '')}")
    if st.sidebar.button("Cerrar sesión"):
        logout()
    menu = st.sidebar.selectbox("Menú", admin_menu() if rol == "admin" else caja_menu())
    if menu == "Dashboard" and not can("ver_dashboard"):
        st.warning("No tienes permiso.")
    elif menu == "POS" and not can("usar_pos"):
        st.warning("No tienes permiso.")
    elif menu == "Productos" and not can("ver_productos"):
        st.warning("No tienes permiso.")
    elif menu == "Compras" and not can("ver_compras"):
        st.warning("No tienes permiso.")
    elif menu in ["Inventario Actual","Conteo Inventario","Ajuste Inventario"] and not can("ver_inventario"):
        st.warning("No tienes permiso.")
    elif menu in ["Apertura de Caja","Cierre de Caja"] and not can("ver_caja"):
        st.warning("No tienes permiso.")
    elif menu == "Crédito" and not can("ver_credito"):
        st.warning("No tienes permiso.")
    else:
        if menu == "Dashboard":
            dashboard()
        elif menu == "Apertura de Caja":
            apertura_caja()
        elif menu == "POS":
            pos()
        elif menu == "Cierre de Caja":
            cierre_caja()
        elif menu == "Productos":
            productos()
        elif menu == "Clientes":
            clientes()
        elif menu == "Proveedores":
            proveedores()
        elif menu == "Inventario Actual":
            inventario_actual()
        elif menu == "Conteo Inventario":
            conteo_inventario()
        elif menu == "Ajuste Inventario":
            ajuste_inventario()
        elif menu == "Ventas":
            ventas()
        elif menu == "Compras":
            compras()
        elif menu == "Catálogo de Gastos":
            simple_table_module("📚 Catálogo de gastos", "catalogo_gastos")
        elif menu == "Gastos":
            simple_table_module("💸 Gastos", "gastos")
        elif menu == "Empleados":
            simple_table_module("👷 Empleados", "empleados")
        elif menu == "Adelantos Empleados":
            simple_table_module("💵 Adelantos empleados", "adelantos_empleados")
        elif menu == "Pérdidas":
            simple_table_module("📉 Pérdidas", "perdidas")
        elif menu == "Gastos Dueño":
            simple_table_module("🏠 Gastos dueño", "gastos_dueno")
        elif menu == "Estado de Resultados":
            simple_table_module("📈 Estado de resultados", "estado_resultados")
        elif menu == "Reportes":
            reportes()
        elif menu == "Crédito":
            simple_table_module("💳 Crédito", "cuentas_por_cobrar")
        elif menu == "Usuarios":
            usuarios()
        elif menu == "Configuración":
            configuracion()
        elif menu == "Auditoría":
            simple_table_module("🔍 Auditoría", "auditoria")
