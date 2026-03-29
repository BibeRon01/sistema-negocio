import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# =========================================================
# CONFIGURACION
# =========================================================
st.set_page_config(page_title="Sistema Negocio PRO", layout="wide")


def obtener_secreto(nombre: str, default: str = "") -> str:
    try:
        return st.secrets.get(nombre, default)
    except Exception:
        return default


SUPABASE_URL = obtener_secreto("SUPABASE_URL", "")
SUPABASE_KEY = obtener_secreto("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Faltan SUPABASE_URL y/o SUPABASE_KEY en .streamlit/secrets.toml")
    st.stop()

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"No se pudo conectar con Supabase: {e}")
    st.stop()


# =========================================================
# HELPERS GENERALES
# =========================================================
def limpiar_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def limpiar_numero(valor) -> float:
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    txt = str(valor).strip().replace("RD$", "").replace("rd$", "").replace("$", "")
    txt = txt.replace(",", "")
    try:
        return float(txt)
    except Exception:
        return 0.0


def ahora() -> str:
    return datetime.now().isoformat()


def a_dataframe(data) -> pd.DataFrame:
    return pd.DataFrame(data or [])


# =========================================================
# CRUD + AUDITORIA
# =========================================================
def insertar_auditoria(accion: str, tabla: str, usuario: str = "sistema", detalle: str = ""):
    try:
        supabase.table("auditoria").insert(
            {
                "accion": accion,
                "tabla": tabla,
                "usuario": usuario,
                "fecha": ahora(),
                "detalle": detalle,
            }
        ).execute()
    except Exception:
        pass


@st.cache_data(ttl=10)
def leer_tabla(nombre_tabla: str) -> pd.DataFrame:
    try:
        resp = supabase.table(nombre_tabla).select("*").execute()
        return a_dataframe(resp.data)
    except Exception as e:
        st.error(f"Error al leer {nombre_tabla}: {e}")
        return pd.DataFrame()


def insertar(nombre_tabla: str, datos: dict, detalle_auditoria: str = "") -> bool:
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        insertar_auditoria("insertar", nombre_tabla, "sistema", detalle_auditoria or str(datos))
        leer_tabla.clear()
        return True
    except Exception as e:
        st.error(f"Error al insertar en {nombre_tabla}: {e}")
        return False


def actualizar(nombre_tabla: str, fila_id: str, datos: dict, detalle_auditoria: str = "") -> bool:
    try:
        supabase.table(nombre_tabla).update(datos).eq("id", fila_id).execute()
        insertar_auditoria("actualizar", nombre_tabla, "sistema", detalle_auditoria or f"id={fila_id} | {datos}")
        leer_tabla.clear()
        return True
    except Exception as e:
        st.error(f"Error al actualizar en {nombre_tabla}: {e}")
        return False


def eliminar(nombre_tabla: str, fila_id: str, detalle_auditoria: str = "") -> bool:
    try:
        supabase.table(nombre_tabla).delete().eq("id", fila_id).execute()
        insertar_auditoria("eliminar", nombre_tabla, "sistema", detalle_auditoria or f"id={fila_id}")
        leer_tabla.clear()
        return True
    except Exception as e:
        st.error(f"Error al eliminar en {nombre_tabla}: {e}")
        return False


# =========================================================
# LOGIN SIMPLE CON TABLA USUARIOS
# =========================================================
def login() -> bool:
    if st.session_state.get("autorizado", False):
        return True

    st.title("🔐 Acceso al sistema")
    correo = st.text_input("Correo")
    clave = st.text_input("Contraseña", type="password")

    col1, col2 = st.columns(2)
    with col1:
        entrar = st.button("Entrar", use_container_width=True)
    with col2:
        demo = st.button("Entrar en modo demo", use_container_width=True)

    if demo:
        st.session_state["autorizado"] = True
        st.session_state["usuario"] = "demo"
        st.rerun()

    if entrar:
        try:
            resp = (
                supabase.table("usuarios")
                .select("*")
                .eq("email", correo)
                .eq("password", clave)
                .limit(1)
                .execute()
            )
            if resp.data:
                st.session_state["autorizado"] = True
                st.session_state["usuario"] = resp.data[0].get("email", "usuario")
                st.session_state["rol"] = resp.data[0].get("rol", "usuario")
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")
        except Exception as e:
            st.error(f"No se pudo validar el acceso: {e}")

    return False


if not login():
    st.stop()

USUARIO_ACTUAL = st.session_state.get("usuario", "sistema")


# =========================================================
# NEGOCIO
# =========================================================
def cargar_productos() -> pd.DataFrame:
    return leer_tabla("productos")


def buscar_producto_por_nombre(nombre: str):
    df = cargar_productos()
    if df.empty or "nombre" not in df.columns:
        return None
    temp = df.copy()
    temp["_nombre"] = temp["nombre"].astype(str).str.strip().str.lower()
    nombre_n = limpiar_texto(nombre).lower()
    match = temp[temp["_nombre"] == nombre_n]
    if match.empty:
        return None
    return match.iloc[0].to_dict()


def actualizar_stock_y_costo_promedio(producto_id: str, cantidad_compra: float, costo_compra: float):
    productos = cargar_productos()
    fila = productos[productos["id"] == producto_id]
    if fila.empty:
        return False

    p = fila.iloc[0]
    stock_actual = limpiar_numero(p.get("stock", 0))
    costo_promedio_actual = limpiar_numero(p.get("costo_promedio", 0))

    total_actual = stock_actual * costo_promedio_actual
    total_nuevo = cantidad_compra * costo_compra
    nuevo_stock = stock_actual + cantidad_compra
    nuevo_costo_promedio = (total_actual + total_nuevo) / nuevo_stock if nuevo_stock > 0 else 0

    return actualizar(
        "productos",
        str(producto_id),
        {
            "stock": nuevo_stock,
            "costo_promedio": nuevo_costo_promedio,
            "costo": costo_compra,
            "fecha": ahora(),
        },
        detalle_auditoria=f"Compra a producto_id={producto_id} | cantidad={cantidad_compra} | costo={costo_compra}",
    )


def registrar_movimiento(producto_id: str, tipo: str, cantidad: float, costo: float):
    return insertar(
        "movimientos",
        {
            "producto_id": producto_id,
            "tipo": tipo,
            "cantidad": cantidad,
            "costo": costo,
            "fecha": ahora(),
        },
        detalle_auditoria=f"Movimiento {tipo} | producto_id={producto_id} | cantidad={cantidad} | costo={costo}",
    )


def registrar_compra(producto_id: str, cantidad: float, costo: float):
    ok1 = actualizar_stock_y_costo_promedio(producto_id, cantidad, costo)
    ok2 = insertar(
        "compras",
        {
            "producto_id": producto_id,
            "cantidad": cantidad,
            "costo": costo,
            "fecha": ahora(),
        },
        detalle_auditoria=f"Compra registrada | producto_id={producto_id} | cantidad={cantidad} | costo={costo}",
    )
    ok3 = registrar_movimiento(producto_id, "entrada", cantidad, costo)
    return ok1 and ok2 and ok3


def registrar_venta(producto_id: str, cantidad: float, metodo: str):
    productos = cargar_productos()
    fila = productos[productos["id"] == producto_id]
    if fila.empty:
        st.error("Producto no encontrado.")
        return False

    p = fila.iloc[0]
    stock = limpiar_numero(p.get("stock", 0))
    precio = limpiar_numero(p.get("precio", 0))
    costo_promedio = limpiar_numero(p.get("costo_promedio", 0))

    if cantidad <= 0:
        st.error("La cantidad debe ser mayor que cero.")
        return False

    if cantidad > stock:
        st.error("No hay stock suficiente para esta venta.")
        return False

    total = cantidad * precio
    costo_total = cantidad * costo_promedio
    nuevo_stock = stock - cantidad

    try:
        venta = supabase.table("ventas").insert(
            {
                "total": total,
                "metodo": metodo,
                "usuario_id": None,
                "fecha": ahora(),
            }
        ).execute()

        venta_id = venta.data[0]["id"]

        supabase.table("detalle_venta").insert(
            {
                "venta_id": venta_id,
                "producto_id": producto_id,
                "cantidad": cantidad,
                "precio": precio,
                "costo": costo_total,
            }
        ).execute()

        supabase.table("productos").update(
            {"stock": nuevo_stock, "fecha": ahora()}
        ).eq("id", producto_id).execute()

        registrar_movimiento(producto_id, "salida", cantidad, costo_promedio)
        insertar_auditoria(
            "insertar",
            "ventas",
            USUARIO_ACTUAL,
            f"Venta_id={venta_id} | producto_id={producto_id} | cantidad={cantidad} | total={total}",
        )
        leer_tabla.clear()
        return True
    except Exception as e:
        st.error(f"Error al registrar la venta: {e}")
        return False


# =========================================================
# REPORTES
# =========================================================
def suma_segura(df: pd.DataFrame, columna: str) -> float:
    if df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())


def generar_estado_resultados() -> dict:
    ventas = leer_tabla("ventas")
    detalle = leer_tabla("detalle_venta")
    gastos = leer_tabla("gastos")

    total_ventas = suma_segura(ventas, "total")
    costo_ventas = suma_segura(detalle, "costo")
    total_gastos = suma_segura(gastos, "monto")
    utilidad_bruta = total_ventas - costo_ventas
    utilidad_neta = utilidad_bruta - total_gastos

    return {
        "ventas": total_ventas,
        "costo_ventas": costo_ventas,
        "utilidad_bruta": utilidad_bruta,
        "gastos": total_gastos,
        "utilidad_neta": utilidad_neta,
    }


def guardar_snapshot_estado_resultados():
    er = generar_estado_resultados()
    return insertar(
        "estado_resultados",
        {
            "fecha": ahora(),
            "ventas": er["ventas"],
            "costo_ventas": er["costo_ventas"],
            "utilidad_bruta": er["utilidad_bruta"],
            "gastos": er["gastos"],
            "utilidad_neta": er["utilidad_neta"],
        },
        detalle_auditoria="Snapshot de estado de resultados",
    )


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("💼 Sistema Negocio PRO")
st.sidebar.write(f"Usuario: {USUARIO_ACTUAL}")
menu = st.sidebar.selectbox(
    "Menú",
    [
        "Dashboard",
        "Productos",
        "Compras",
        "Ventas",
        "Gastos",
        "Estado de Resultados",
        "Auditoría",
    ],
)

if st.sidebar.button("🔄 Recargar nube", use_container_width=True):
    leer_tabla.clear()
    st.rerun()

if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
    st.session_state.clear()
    st.rerun()


# =========================================================
# DASHBOARD
# =========================================================
if menu == "Dashboard":
    st.title("📊 Dashboard")

    productos = leer_tabla("productos")
    ventas = leer_tabla("ventas")
    compras = leer_tabla("compras")
    gastos = leer_tabla("gastos")
    er = generar_estado_resultados()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Productos", len(productos))
    c2.metric("Ventas", f"RD$ {suma_segura(ventas, 'total'):,.2f}")
    c3.metric("Compras", f"RD$ {suma_segura(compras, 'costo'):,.2f}")
    c4.metric("Gastos", f"RD$ {suma_segura(gastos, 'monto'):,.2f}")

    c5, c6, c7 = st.columns(3)
    c5.metric("Costo de ventas", f"RD$ {er['costo_ventas']:,.2f}")
    c6.metric("Utilidad bruta", f"RD$ {er['utilidad_bruta']:,.2f}")
    c7.metric("Utilidad neta", f"RD$ {er['utilidad_neta']:,.2f}")

    if not productos.empty:
        st.subheader("Inventario actual")
        ver = productos.copy()
        cols = [c for c in ["nombre", "costo", "precio", "stock", "costo_promedio", "fecha"] if c in ver.columns]
        st.dataframe(ver[cols], use_container_width=True)


# =========================================================
# PRODUCTOS
# =========================================================
elif menu == "Productos":
    st.title("📦 Productos")

    with st.expander("➕ Crear producto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre del producto")
            costo = st.number_input("Costo inicial", min_value=0.0, step=1.0)
        with c2:
            precio = st.number_input("Precio de venta", min_value=0.0, step=1.0)
            stock = st.number_input("Stock inicial", min_value=0.0, step=1.0)

        if st.button("Guardar producto"):
            if not limpiar_texto(nombre):
                st.error("Debes escribir el nombre del producto.")
            elif buscar_producto_por_nombre(nombre) is not None:
                st.error("Ese producto ya existe.")
            else:
                ok = insertar(
                    "productos",
                    {
                        "nombre": limpiar_texto(nombre),
                        "costo": costo,
                        "precio": precio,
                        "stock": stock,
                        "costo_promedio": costo,
                        "fecha": ahora(),
                        "created_at": ahora(),
                    },
                    detalle_auditoria=f"Producto creado: {nombre}",
                )
                if ok:
                    st.success("Producto guardado correctamente.")
                    st.rerun()

    st.subheader("Listado de productos")
    df = leer_tabla("productos")
    if not df.empty:
        texto = st.text_input("Buscar producto")
        if texto:
            df = df[df.astype(str).apply(lambda s: s.str.contains(texto, case=False, na=False)).any(axis=1)]
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay productos registrados.")


# =========================================================
# COMPRAS
# =========================================================
elif menu == "Compras":
    st.title("🧾 Compras")
    productos = leer_tabla("productos")

    if productos.empty:
        st.warning("Primero debes crear productos.")
    else:
        nombres = productos["nombre"].astype(str).tolist()
        nombre_sel = st.selectbox("Producto", nombres)
        cantidad = st.number_input("Cantidad comprada", min_value=0.0, step=1.0)
        costo = st.number_input("Costo unitario de compra", min_value=0.0, step=1.0)

        fila = productos[productos["nombre"] == nombre_sel].iloc[0]
        if st.button("Registrar compra"):
            if cantidad <= 0 or costo <= 0:
                st.error("La cantidad y el costo deben ser mayores que cero.")
            else:
                ok = registrar_compra(str(fila["id"]), cantidad, costo)
                if ok:
                    st.success("Compra registrada correctamente.")
                    st.rerun()

    st.subheader("Historial de compras")
    df = leer_tabla("compras")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay compras registradas.")


# =========================================================
# VENTAS
# =========================================================
elif menu == "Ventas":
    st.title("💰 Ventas")
    productos = leer_tabla("productos")

    if productos.empty:
        st.warning("Primero debes crear productos.")
    else:
        disponibles = productos[productos["stock"].fillna(0).astype(float) > 0] if "stock" in productos.columns else productos
        if disponibles.empty:
            st.warning("No hay productos con stock disponible.")
        else:
            nombres = disponibles["nombre"].astype(str).tolist()
            nombre_sel = st.selectbox("Producto a vender", nombres)
            cantidad = st.number_input("Cantidad vendida", min_value=0.0, step=1.0)
            metodo = st.selectbox("Método de cobro", ["efectivo", "transferencia", "tarjeta"])

            fila = disponibles[disponibles["nombre"] == nombre_sel].iloc[0]
            st.info(f"Stock disponible: {limpiar_numero(fila.get('stock', 0))}")
            st.info(f"Precio: RD$ {limpiar_numero(fila.get('precio', 0)):,.2f}")

            if st.button("Registrar venta"):
                ok = registrar_venta(str(fila["id"]), cantidad, metodo)
                if ok:
                    st.success("Venta registrada correctamente.")
                    st.rerun()

    st.subheader("Historial de ventas")
    df = leer_tabla("ventas")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay ventas registradas.")


# =========================================================
# GASTOS
# =========================================================
elif menu == "Gastos":
    st.title("💸 Gastos")

    nombre = st.text_input("Nombre del gasto")
    monto = st.number_input("Monto", min_value=0.0, step=1.0)
    tipo = st.selectbox("Tipo de gasto", ["fijo", "variable"])

    if st.button("Guardar gasto"):
        if not limpiar_texto(nombre):
            st.error("Debes escribir el nombre del gasto.")
        elif monto <= 0:
            st.error("El monto debe ser mayor que cero.")
        else:
            ok = insertar(
                "gastos",
                {
                    "nombre": limpiar_texto(nombre),
                    "monto": monto,
                    "tipo": tipo,
                    "fecha": ahora(),
                },
                detalle_auditoria=f"Gasto registrado: {nombre} | monto={monto}",
            )
            if ok:
                st.success("Gasto guardado correctamente.")
                st.rerun()

    st.subheader("Listado de gastos")
    df = leer_tabla("gastos")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay gastos registrados.")


# =========================================================
# ESTADO DE RESULTADOS
# =========================================================
elif menu == "Estado de Resultados":
    st.title("📈 Estado de Resultados")

    er = generar_estado_resultados()

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Ventas", f"RD$ {er['ventas']:,.2f}")
        st.metric("Costo de ventas", f"RD$ {er['costo_ventas']:,.2f}")
        st.metric("Utilidad bruta", f"RD$ {er['utilidad_bruta']:,.2f}")
    with c2:
        st.metric("Gastos", f"RD$ {er['gastos']:,.2f}")
        st.metric("Utilidad neta", f"RD$ {er['utilidad_neta']:,.2f}")

    if st.button("Guardar snapshot en Supabase"):
        ok = guardar_snapshot_estado_resultados()
        if ok:
            st.success("Snapshot guardado en la tabla estado_resultados.")
            st.rerun()

    st.subheader("Historial guardado")
    df = leer_tabla("estado_resultados")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Todavía no hay snapshots guardados.")


# =========================================================
# AUDITORIA
# =========================================================
elif menu == "Auditoría":
    st.title("📋 Auditoría")
    df = leer_tabla("auditoria")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No hay datos de auditoría todavía.")

