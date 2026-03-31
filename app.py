# ==========================================
# 🔥 POS PRO MASTER FINAL - TODO EN UNO 🔥
# ==========================================

import streamlit as st
from supabase import create_client
from datetime import datetime

st.set_page_config(layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = []

def login():
    st.title("🔐 POS PRO MASTER")
    u = st.text_input("Usuario")
    p = st.text_input("Clave", type="password")
    if st.button("Entrar"):
        r = supabase.table("usuarios").select("*").eq("usuario", u).eq("clave", p).execute()
        if r.data:
            st.session_state.user = r.data[0]
            st.rerun()
        else:
            st.error("Login incorrecto")

def get_productos():
    return supabase.table("vw_pos").select("*").execute().data

def update_stock(pid, qty):
    inv = supabase.table("inventario_actual").select("*").eq("producto_id", pid).execute().data
    if inv:
        supabase.table("inventario_actual").update({
            "cantidad": inv[0]["cantidad"] + qty
        }).eq("id", inv[0]["id"]).execute()

def pos():
    st.title("🛒 POS PRO")

    productos = get_productos()
    col1, col2 = st.columns([2,1])

    with col1:
        buscar = st.text_input("🔍 Buscar producto")

        for p in productos:
            if buscar.lower() in p["nombre"].lower():
                if st.button(f'{p["nombre"]} | ${p["precio"]} | Stock {p["stock"]}', key=p["id"]):
                    if p["stock"] <= 0:
                        st.warning("Sin stock")
                        return
                    st.session_state.cart.append({
                        "id": p["id"],
                        "nombre": p["nombre"],
                        "precio": p["precio"],
                        "cantidad": 1
                    })
                    st.rerun()

        st.subheader("🧾 Carrito")

        total = 0
        for i, item in enumerate(st.session_state.cart):
            c1,c2,c3,c4 = st.columns([3,1,1,1])
            c1.write(item["nombre"])
            item["cantidad"] = c2.number_input("Cant", value=item["cantidad"], key=i)
            subtotal = item["cantidad"] * item["precio"]
            c3.write(subtotal)

            if c4.button("❌", key=f"del{i}"):
                st.session_state.cart.pop(i)
                st.rerun()

            total += subtotal

        st.markdown(f"## 💰 TOTAL: {total}")

    with col2:
        metodo = st.selectbox("💳 Método de pago", ["efectivo","tarjeta","transferencia","credito"])

        cliente = None
        if metodo == "credito":
            clientes = supabase.table("clientes").select("*").execute().data
            cliente = st.selectbox("Cliente", [c["nombre"] for c in clientes])

        recibido = st.number_input("Recibido", value=0.0) if metodo=="efectivo" else 0
        devuelta = recibido - total if recibido >= total else 0
        st.write(f"Devuelta: {devuelta}")

        if st.button("💾 Guardar Venta"):

            venta = supabase.table("ventas").insert({
                "fecha": datetime.now().isoformat(),
                "total": total,
                "metodo_pago": metodo,
                "cliente_nombre": cliente
            }).execute().data[0]

            for item in st.session_state.cart:
                supabase.table("detalle_venta").insert({
                    "venta_id": venta["id"],
                    "producto_id": item["id"],
                    "producto": item["nombre"],
                    "cantidad": item["cantidad"],
                    "precio": item["precio"],
                    "total_linea": item["cantidad"] * item["precio"]
                }).execute()
                update_stock(item["id"], -item["cantidad"])

            if metodo == "credito":
                supabase.table("cuentas_por_cobrar").insert({
                    "venta_id": venta["id"],
                    "cliente_nombre": cliente,
                    "monto_original": total,
                    "saldo_pendiente": total
                }).execute()

            st.session_state.cart = []
            st.success("Venta guardada correctamente")
            st.rerun()

def creditos():
    st.title("💳 Créditos Clientes")
    data = supabase.table("cuentas_por_cobrar").select("*").execute().data

    for c in data:
        st.write(c)
        abono = st.number_input(f"Abono {c['id']}", value=0.0)
        if st.button(f"Pagar {c['id']}"):
            nuevo = c["saldo_pendiente"] - abono
            supabase.table("cuentas_por_cobrar").update({
                "saldo_pendiente": nuevo
            }).eq("id", c["id"]).execute()
            supabase.table("abonos_credito").insert({
                "cuenta_id": c["id"],
                "monto": abono
            }).execute()
            st.success("Pago aplicado")

def compras():
    st.title("📦 Compras")
    productos = get_productos()
    buscar = st.text_input("Buscar producto")

    for p in productos:
        if buscar.lower() in p["nombre"].lower():
            if st.button(p["nombre"], key=p["id"]):
                cantidad = st.number_input("Cantidad", value=1)
                if st.button("Guardar compra"):
                    update_stock(p["id"], cantidad)
                    st.success("Compra registrada")

def inventario():
    st.title("📦 Inventario")
    data = supabase.table("inventario_actual").select("*").execute().data
    st.dataframe(data)

def caja():
    st.title("💵 Caja")
    fondo = st.number_input("Fondo inicial", value=0.0)
    if st.button("Abrir caja"):
        supabase.table("caja").insert({
            "fondo_inicial": fondo,
            "estado": "abierta"
        }).execute()
        st.success("Caja abierta")

def app():
    if not st.session_state.user:
        login()
        return

    rol = st.session_state.user["rol"]

    if rol == "cajera":
        menu = ["POS"]
    else:
        menu = ["POS","Compras","Inventario","Creditos","Caja"]

    opt = st.sidebar.selectbox("Menú", menu)

    if opt == "POS":
        pos()
    elif opt == "Compras":
        compras()
    elif opt == "Inventario":
        inventario()
    elif opt == "Creditos":
        creditos()
    elif opt == "Caja":
        caja()

app()
