import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client, Client

st.set_page_config(page_title="Sistema de Negocio", layout="wide")

# =====================================================
# CONEXIÓN
# =====================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
APP_PASSWORD = st.secrets.get("APP_PASSWORD", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================
# SEGURIDAD SIMPLE
# =====================================================
def login_simple():
    if not APP_PASSWORD:
        return True

    if st.session_state.get("autorizado", False):
        return True

    st.title("🔐 Acceso al sistema")
    clave = st.text_input("Escribe la clave", type="password")

    if st.button("Entrar"):
        if clave == APP_PASSWORD:
            st.session_state["autorizado"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")

    return False


if not login_simple():
    st.stop()

# =====================================================
# FUNCIONES BASE
# =====================================================
def leer_tabla(nombre_tabla: str) -> pd.DataFrame:
    try:
        resp = supabase.table(nombre_tabla).select("*").order("id").execute()
        data = resp.data if resp.data else []
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al leer {nombre_tabla}: {e}")
        return pd.DataFrame()


def insertar_tabla(nombre_tabla: str, datos: dict):
    try:
        supabase.table(nombre_tabla).insert(datos).execute()
        return True
    except Exception as e:
        st.error(f"Error al guardar en {nombre_tabla}: {e}")
        return False


def actualizar_tabla(nombre_tabla: str, fila_id: int, datos: dict):
    try:
        supabase.table(nombre_tabla).update(datos).eq("id", fila_id).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar en {nombre_tabla}: {e}")
        return False


def eliminar_tabla(nombre_tabla: str, fila_id: int):
    try:
        supabase.table(nombre_tabla).delete().eq("id", fila_id).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar en {nombre_tabla}: {e}")
        return False


def convertir_fechas(df: pd.DataFrame, columnas=("fecha",)) -> pd.DataFrame:
    for col in columnas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def suma_segura(df: pd.DataFrame, columna: str) -> float:
    if df.empty or columna not in df.columns:
        return 0.0
    return float(pd.to_numeric(df[columna], errors="coerce").fillna(0).sum())


def descargar_excel(df: pd.DataFrame, nombre_archivo: str):
    if df.empty:
        st.info("No hay datos para descargar.")
        return

    excel_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ Descargar CSV",
        data=excel_bytes,
        file_name=nombre_archivo,
        mime="text/csv"
    )


def filtro_texto(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    busqueda = st.text_input("Buscar")
    if not busqueda:
        return df
    mask = df.astype(str).apply(
        lambda x: x.str.contains(busqueda, case=False, na=False)
    ).any(axis=1)
    return df[mask]


def refrescar():
    st.rerun()

# =====================================================
# CARGA DESDE NUBE
# =====================================================
productos = convertir_fechas(leer_tabla("productos"))
ventas = convertir_fechas(leer_tabla("ventas"))
compras = convertir_fechas(leer_tabla("compras"))
gastos = convertir_fechas(leer_tabla("gastos"))
perdidas = convertir_fechas(leer_tabla("perdidas"))
gastos_dueno = convertir_fechas(leer_tabla("gastos_dueno"))
empleados = convertir_fechas(leer_tabla("empleados"))
cierre_caja = convertir_fechas(leer_tabla("cierre_caja"))
estado_resultados = convertir_fechas(leer_tabla("estado_resultados"))

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.title("💼 Sistema de Negocio")
menu = st.sidebar.selectbox(
    "Menú",
    [
        "Dashboard",
        "Productos",
        "Ventas",
        "Compras",
        "Gastos",
        "Pérdidas",
        "Gastos Dueño",
        "Empleados",
        "Cierre de Caja",
        "Estado de Resultados",
    ],
)

if st.sidebar.button("🔄 Recargar nube"):
    refrescar()

# =====================================================
# DASHBOARD
# =====================================================
if menu == "Dashboard":
    st.title("📊 Dashboard")

    total_ventas = suma_segura(ventas, "total")
    total_compras = suma_segura(compras, "monto")
    total_gastos = suma_segura(gastos, "monto")
    total_perdidas = suma_segura(perdidas, "valor")
    total_dueno = suma_segura(gastos_dueno, "monto")
    utilidad = total_ventas - total_compras - total_gastos - total_perdidas - total_dueno

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas", f"RD$ {total_ventas:,.2f}")
    c2.metric("Compras", f"RD$ {total_compras:,.2f}")
    c3.metric("Gastos", f"RD$ {total_gastos:,.2f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Pérdidas", f"RD$ {total_perdidas:,.2f}")
    c5.metric("Retiros dueño", f"RD$ {total_dueno:,.2f}")
    c6.metric("Utilidad estimada", f"RD$ {utilidad:,.2f}")

    st.subheader("Últimas ventas")
    st.dataframe(ventas.tail(10), use_container_width=True)

    st.subheader("Últimos cierres de caja")
    st.dataframe(cierre_caja.tail(10), use_container_width=True)

# =====================================================
# PRODUCTOS
# =====================================================
elif menu == "Productos":
    st.title("📦 Productos")

    with st.expander("➕ Agregar producto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre")
            costo = st.number_input("Costo", min_value=0.0, step=1.0)
        with c2:
            precio = st.number_input("Precio", min_value=0.0, step=1.0)
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0)

        if st.button("Guardar producto"):
            if not nombre.strip():
                st.warning("Debes escribir el nombre.")
            else:
                ok = insertar_tabla(
                    "productos",
                    {
                        "nombre": nombre.strip(),
                        "costo": float(costo),
                        "precio": float(precio),
                        "cantidad": float(cantidad),
                    },
                )
                if ok:
                    st.success("Producto guardado.")
                    refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not productos.empty:
        opciones = productos["nombre"].fillna("").astype(str)
        producto_sel = st.selectbox("Selecciona un producto", opciones.unique())

        fila = productos[productos["nombre"].astype(str) == str(producto_sel)]
        if not fila.empty:
            row = fila.iloc[0]
            fila_id = int(row["id"])

            c1, c2 = st.columns(2)
            with c1:
                nombre_e = st.text_input("Nombre editado", value=str(row["nombre"]), key="prod_nom")
                costo_e = st.number_input("Costo editado", value=float(row["costo"]), key="prod_cos")
            with c2:
                precio_e = st.number_input("Precio editado", value=float(row["precio"]), key="prod_pre")
                cantidad_e = st.number_input("Cantidad editada", value=float(row["cantidad"]), key="prod_can")

            colb1, colb2 = st.columns(2)
            with colb1:
                if st.button("Actualizar producto"):
                    ok = actualizar_tabla(
                        "productos",
                        fila_id,
                        {
                            "nombre": nombre_e.strip(),
                            "costo": float(costo_e),
                            "precio": float(precio_e),
                            "cantidad": float(cantidad_e),
                        },
                    )
                    if ok:
                        st.success("Producto actualizado.")
                        refrescar()

            with colb2:
                if st.button("Eliminar producto"):
                    ok = eliminar_tabla("productos", fila_id)
                    if ok:
                        st.success("Producto eliminado.")
                        refrescar()

    st.subheader("📋 Listado")
    productos_f = filtro_texto(productos)
    st.dataframe(productos_f, use_container_width=True)
    descargar_excel(productos_f, "productos.csv")

# =====================================================
# VENTAS
# =====================================================
elif menu == "Ventas":
    st.title("💰 Ventas")

    with st.expander("➕ Registrar venta", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="venta_fecha")
        with c2:
            total = st.number_input("Total", min_value=0.0, step=1.0, key="venta_total")
        with c3:
            metodo = st.selectbox("Método", ["Efectivo", "Transferencia", "Tarjeta"], key="venta_metodo")

        if st.button("Guardar venta"):
            ok = insertar_tabla(
                "ventas",
                {
                    "fecha": str(fecha),
                    "total": float(total),
                    "metodo": metodo,
                },
            )
            if ok:
                st.success("Venta guardada.")
                refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not ventas.empty:
        ventas_aux = ventas.copy()
        ventas_aux["texto"] = (
            ventas_aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + ventas_aux["total"].astype(str)
            + " | "
            + ventas_aux["metodo"].astype(str)
        )
        venta_sel = st.selectbox("Selecciona una venta", ventas_aux["texto"].tolist())
        fila = ventas_aux[ventas_aux["texto"] == venta_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="v_ed_f")
        with c2:
            total_e = st.number_input("Total editado", value=float(fila["total"]), key="v_ed_t")
        with c3:
            metodo_e = st.selectbox(
                "Método editado",
                ["Efectivo", "Transferencia", "Tarjeta"],
                index=["Efectivo", "Transferencia", "Tarjeta"].index(str(fila["metodo"])) if str(fila["metodo"]) in ["Efectivo", "Transferencia", "Tarjeta"] else 0,
                key="v_ed_m",
            )

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("Actualizar venta"):
                ok = actualizar_tabla(
                    "ventas",
                    fila_id,
                    {"fecha": str(fecha_e), "total": float(total_e), "metodo": metodo_e},
                )
                if ok:
                    st.success("Venta actualizada.")
                    refrescar()
        with colb2:
            if st.button("Eliminar venta"):
                ok = eliminar_tabla("ventas", fila_id)
                if ok:
                    st.success("Venta eliminada.")
                    refrescar()

    st.subheader("📋 Listado")
    ventas_f = filtro_texto(ventas)
    st.dataframe(ventas_f, use_container_width=True)
    descargar_excel(ventas_f, "ventas.csv")

# =====================================================
# COMPRAS
# =====================================================
elif menu == "Compras":
    st.title("🧾 Compras")

    with st.expander("➕ Registrar compra", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="comp_fecha")
            numero = st.text_input("Número / referencia")
            proveedor = st.text_input("Proveedor")
        with c2:
            descripcion = st.text_input("Descripción")
            monto = st.number_input("Monto", min_value=0.0, step=1.0)
            metodo = st.selectbox("Método", ["Efectivo", "Transferencia", "Tarjeta"], key="comp_metodo")

        if st.button("Guardar compra"):
            ok = insertar_tabla(
                "compras",
                {
                    "fecha": str(fecha),
                    "numero": numero.strip(),
                    "proveedor": proveedor.strip(),
                    "descripcion": descripcion.strip(),
                    "monto": float(monto),
                    "metodo": metodo,
                },
            )
            if ok:
                st.success("Compra guardada.")
                refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not compras.empty:
        compras_aux = compras.copy()
        compras_aux["texto"] = (
            compras_aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + compras_aux["proveedor"].astype(str)
            + " | "
            + compras_aux["monto"].astype(str)
        )

        compra_sel = st.selectbox("Selecciona una compra", compras_aux["texto"].tolist())
        fila = compras_aux[compras_aux["texto"] == compra_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="c_ed_f")
            numero_e = st.text_input("Número editado", value=str(fila["numero"]), key="c_ed_n")
            proveedor_e = st.text_input("Proveedor editado", value=str(fila["proveedor"]), key="c_ed_p")
        with c2:
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="c_ed_d")
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="c_ed_mo")
            metodo_e = st.selectbox(
                "Método editado",
                ["Efectivo", "Transferencia", "Tarjeta"],
                index=["Efectivo", "Transferencia", "Tarjeta"].index(str(fila["metodo"])) if str(fila["metodo"]) in ["Efectivo", "Transferencia", "Tarjeta"] else 0,
                key="c_ed_me",
            )

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("Actualizar compra"):
                ok = actualizar_tabla(
                    "compras",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "numero": numero_e.strip(),
                        "proveedor": proveedor_e.strip(),
                        "descripcion": descripcion_e.strip(),
                        "monto": float(monto_e),
                        "metodo": metodo_e,
                    },
                )
                if ok:
                    st.success("Compra actualizada.")
                    refrescar()
        with colb2:
            if st.button("Eliminar compra"):
                ok = eliminar_tabla("compras", fila_id)
                if ok:
                    st.success("Compra eliminada.")
                    refrescar()

    st.subheader("📋 Listado")
    compras_f = filtro_texto(compras)
    st.dataframe(compras_f, use_container_width=True)
    descargar_excel(compras_f, "compras.csv")

# =====================================================
# GASTOS
# =====================================================
elif menu == "Gastos":
    st.title("💸 Gastos")

    with st.expander("➕ Registrar gasto", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="g_fecha")
            descripcion = st.text_input("Descripción")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="g_monto")

        if st.button("Guardar gasto"):
            ok = insertar_tabla(
                "gastos",
                {
                    "fecha": str(fecha),
                    "descripcion": descripcion.strip(),
                    "monto": float(monto),
                },
            )
            if ok:
                st.success("Gasto guardado.")
                refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not gastos.empty:
        gastos_aux = gastos.copy()
        gastos_aux["texto"] = (
            gastos_aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + gastos_aux["descripcion"].astype(str)
            + " | "
            + gastos_aux["monto"].astype(str)
        )
        gasto_sel = st.selectbox("Selecciona un gasto", gastos_aux["texto"].tolist())
        fila = gastos_aux[gastos_aux["texto"] == gasto_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="g_ed_f")
        with c2:
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="g_ed_m")

        descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="g_ed_d")

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("Actualizar gasto"):
                ok = actualizar_tabla(
                    "gastos",
                    fila_id,
                    {"fecha": str(fecha_e), "descripcion": descripcion_e.strip(), "monto": float(monto_e)},
                )
                if ok:
                    st.success("Gasto actualizado.")
                    refrescar()
        with colb2:
            if st.button("Eliminar gasto"):
                ok = eliminar_tabla("gastos", fila_id)
                if ok:
                    st.success("Gasto eliminado.")
                    refrescar()

    st.subheader("📋 Listado")
    gastos_f = filtro_texto(gastos)
    st.dataframe(gastos_f, use_container_width=True)
    descargar_excel(gastos_f, "gastos.csv")

# =====================================================
# PÉRDIDAS
# =====================================================
elif menu == "Pérdidas":
    st.title("📉 Pérdidas")

    with st.expander("➕ Registrar pérdida", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="p_fecha")
            productos_op = productos["nombre"].astype(str).tolist() if not productos.empty else []
            producto = st.selectbox("Producto", productos_op if productos_op else [""], key="p_prod")
        with c2:
            cantidad = st.number_input("Cantidad", min_value=0.0, step=1.0, key="p_cant")
            valor = st.number_input("Valor", min_value=0.0, step=1.0, key="p_val")

        if st.button("Guardar pérdida"):
            ok = insertar_tabla(
                "perdidas",
                {
                    "fecha": str(fecha),
                    "producto": str(producto),
                    "cantidad": float(cantidad),
                    "valor": float(valor),
                },
            )
            if ok:
                st.success("Pérdida guardada.")
                refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not perdidas.empty:
        perd_aux = perdidas.copy()
        perd_aux["texto"] = (
            perd_aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + perd_aux["producto"].astype(str)
            + " | "
            + perd_aux["valor"].astype(str)
        )
        perd_sel = st.selectbox("Selecciona una pérdida", perd_aux["texto"].tolist())
        fila = perd_aux[perd_aux["texto"] == perd_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="p_ed_f")
            productos_op = productos["nombre"].astype(str).tolist() if not productos.empty else [""]
            idx_prod = productos_op.index(str(fila["producto"])) if str(fila["producto"]) in productos_op else 0
            producto_e = st.selectbox("Producto editado", productos_op, index=idx_prod, key="p_ed_pr")
        with c2:
            cantidad_e = st.number_input("Cantidad editada", value=float(fila["cantidad"]), key="p_ed_ca")
            valor_e = st.number_input("Valor editado", value=float(fila["valor"]), key="p_ed_va")

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("Actualizar pérdida"):
                ok = actualizar_tabla(
                    "perdidas",
                    fila_id,
                    {
                        "fecha": str(fecha_e),
                        "producto": str(producto_e),
                        "cantidad": float(cantidad_e),
                        "valor": float(valor_e),
                    },
                )
                if ok:
                    st.success("Pérdida actualizada.")
                    refrescar()
        with colb2:
            if st.button("Eliminar pérdida"):
                ok = eliminar_tabla("perdidas", fila_id)
                if ok:
                    st.success("Pérdida eliminada.")
                    refrescar()

    st.subheader("📋 Listado")
    perdidas_f = filtro_texto(perdidas)
    st.dataframe(perdidas_f, use_container_width=True)
    descargar_excel(perdidas_f, "perdidas.csv")

# =====================================================
# GASTOS DUEÑO
# =====================================================
elif menu == "Gastos Dueño":
    st.title("🏦 Gastos del dueño / retiros")

    with st.expander("➕ Registrar retiro", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            fecha = st.date_input("Fecha", value=date.today(), key="gd_fecha")
            descripcion = st.text_input("Descripción", key="gd_desc")
        with c2:
            monto = st.number_input("Monto", min_value=0.0, step=1.0, key="gd_mon")

        if st.button("Guardar gasto del dueño"):
            ok = insertar_tabla(
                "gastos_dueno",
                {
                    "fecha": str(fecha),
                    "descripcion": descripcion.strip(),
                    "monto": float(monto),
                },
            )
            if ok:
                st.success("Retiro guardado.")
                refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not gastos_dueno.empty:
        gd_aux = gastos_dueno.copy()
        gd_aux["texto"] = (
            gd_aux["fecha"].dt.strftime("%Y-%m-%d").fillna("")
            + " | "
            + gd_aux["descripcion"].astype(str)
            + " | "
            + gd_aux["monto"].astype(str)
        )
        gd_sel = st.selectbox("Selecciona un retiro", gd_aux["texto"].tolist())
        fila = gd_aux[gd_aux["texto"] == gd_sel].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            fecha_e = st.date_input("Fecha editada", value=pd.to_datetime(fila["fecha"]).date(), key="gd_ed_f")
            descripcion_e = st.text_input("Descripción editada", value=str(fila["descripcion"]), key="gd_ed_d")
        with c2:
            monto_e = st.number_input("Monto editado", value=float(fila["monto"]), key="gd_ed_m")

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("Actualizar retiro"):
                ok = actualizar_tabla(
                    "gastos_dueno",
                    fila_id,
                    {"fecha": str(fecha_e), "descripcion": descripcion_e.strip(), "monto": float(monto_e)},
                )
                if ok:
                    st.success("Retiro actualizado.")
                    refrescar()
        with colb2:
            if st.button("Eliminar retiro"):
                ok = eliminar_tabla("gastos_dueno", fila_id)
                if ok:
                    st.success("Retiro eliminado.")
                    refrescar()

    st.subheader("📋 Listado")
    gd_f = filtro_texto(gastos_dueno)
    st.dataframe(gd_f, use_container_width=True)
    descargar_excel(gd_f, "gastos_dueno.csv")

# =====================================================
# EMPLEADOS
# =====================================================
elif menu == "Empleados":
    st.title("👥 Empleados")

    with st.expander("➕ Agregar empleado", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre")
            cargo = st.text_input("Cargo")
            sueldo = st.number_input("Sueldo", min_value=0.0, step=1.0)
        with c2:
            tipo_pago = st.selectbox("Tipo de pago", ["Quincenal", "Mensual", "Variable"])
            metodo_pago = st.selectbox("Método de pago", ["Efectivo", "Transferencia", "Cheque"])

        if st.button("Guardar empleado"):
            ok = insertar_tabla(
                "empleados",
                {
                    "nombre": nombre.strip(),
                    "cargo": cargo.strip(),
                    "sueldo": float(sueldo),
                    "tipo_pago": tipo_pago,
                    "metodo_pago": metodo_pago,
                },
            )
            if ok:
                st.success("Empleado guardado.")
                refrescar()

    st.subheader("✏️ Editar o eliminar")
    if not empleados.empty:
        emp_sel = st.selectbox("Selecciona un empleado", empleados["nombre"].astype(str).tolist())
        fila = empleados[empleados["nombre"].astype(str) == str(emp_sel)].iloc[0]
        fila_id = int(fila["id"])

        c1, c2 = st.columns(2)
        with c1:
            nombre_e = st.text_input("Nombre editado", value=str(fila["nombre"]), key="e_nom")
            cargo_e = st.text_input("Cargo editado", value=str(fila["cargo"]), key="e_car")
            sueldo_e = st.number_input("Sueldo editado", value=float(fila["sueldo"]), key="e_sue")
        with c2:
            tipo_pago_e = st.selectbox(
                "Tipo de pago editado",
                ["Quincenal", "Mensual", "Variable"],
                index=["Quincenal", "Mensual", "Variable"].index(str(fila["tipo_pago"])) if str(fila["tipo_pago"]) in ["Quincenal", "Mensual", "Variable"] else 0,
                key="e_tip"
            )
            metodo_pago_e = st.selectbox(
                "Método de pago editado",
                ["Efectivo", "Transferencia", "Cheque"],
                index=["Efectivo", "Transferencia", "Cheque"].index(str(fila["metodo_pago"])) if str(fila["metodo_pago"]) in ["Efectivo", "Transferencia", "Cheque"] else 0,
                key="e_met"
            )

        colb1, colb2 = st.columns(2)
        with colb1:
            if st.button("Actualizar empleado"):
                ok = actualizar_tabla(
                    "empleados",
                    fila_id,
                    {
                        "nombre": nombre_e.strip(),
                        "cargo": cargo_e.strip(),
                        "sueldo": float(sueldo_e),
                        "tipo_pago": tipo_pago_e,
                        "metodo_pago": metodo_pago_e,
                    },
                )
                if ok:
                    st.success("Empleado actualizado.")
                    refrescar()
        with colb2:
            if st.button("Eliminar empleado"):
                ok = eliminar_tabla("empleados", fila_id)
                if ok:
                    st.success("Empleado eliminado.")
                    refrescar()

    st.subheader("📋 Listado")
    empleados_f = filtro_texto(empleados)
    st.dataframe(empleados_f, use_container_width=True)
    descargar_excel(empleados_f, "empleados.csv")

# =====================================================
# CIERRE DE CAJA
# =====================================================
elif menu == "Cierre de Caja":
    st.title("💵 Cierre de Caja")

    fecha_cierre = st.date_input("Fecha del cierre", value=date.today())
    fecha_dt = pd.to_datetime(fecha_cierre)

    ventas_dia = ventas[ventas["fecha"].dt.date == fecha_dt.date()] if not ventas.empty else pd.DataFrame()
    compras_dia = compras[compras["fecha"].dt.date == fecha_dt.date()] if not compras.empty else pd.DataFrame()
    gastos_dia = gastos[gastos["fecha"].dt.date == fecha_dt.date()] if not gastos.empty else pd.DataFrame()
    perdidas_dia = perdidas[perdidas["fecha"].dt.date == fecha_dt.date()] if not perdidas.empty else pd.DataFrame()
    dueno_dia = gastos_dueno[gastos_dueno["fecha"].dt.date == fecha_dt.date()] if not gastos_dueno.empty else pd.DataFrame()

    monto_sistema = (
        suma_segura(ventas_dia, "total")
        - suma_segura(compras_dia, "monto")
        - suma_segura(gastos_dia, "monto")
        - suma_segura(perdidas_dia, "valor")
        - suma_segura(dueno_dia, "monto")
    )

    st.metric("Monto sistema", f"RD$ {monto_sistema:,.2f}")

    monto_real = st.number_input("Monto real contado", min_value=0.0, step=1.0)
    diferencia = float(monto_real) - float(monto_sistema)

    st.metric("Diferencia", f"RD$ {diferencia:,.2f}")

    if st.button("Guardar cierre de caja"):
        ok = insertar_tabla(
            "cierre_caja",
            {
                "fecha": str(fecha_cierre),
                "monto_sistema": float(monto_sistema),
                "monto_real": float(monto_real),
                "diferencia": float(diferencia),
            },
        )
        if ok:
            st.success("Cierre de caja guardado.")
            refrescar()

    st.subheader("📋 Historial")
    cierre_f = filtro_texto(cierre_caja)
    st.dataframe(cierre_f, use_container_width=True)
    descargar_excel(cierre_f, "cierre_caja.csv")

# =====================================================
# ESTADO DE RESULTADOS
# =====================================================
elif menu == "Estado de Resultados":
    st.title("📈 Estado de Resultados")

    c1, c2 = st.columns(2)
    with c1:
        fecha_desde = st.date_input("Desde", value=date.today().replace(day=1), key="er_desde")
    with c2:
        fecha_hasta = st.date_input("Hasta", value=date.today(), key="er_hasta")

    f_desde = pd.to_datetime(fecha_desde)
    f_hasta = pd.to_datetime(fecha_hasta)

    def filtrar_rango(df: pd.DataFrame):
        if df.empty or "fecha" not in df.columns:
            return pd.DataFrame()
        return df[(df["fecha"] >= f_desde) & (df["fecha"] <= f_hasta)]

    ventas_r = filtrar_rango(ventas)
    compras_r = filtrar_rango(compras)
    gastos_r = filtrar_rango(gastos)
    perdidas_r = filtrar_rango(perdidas)

    total_ventas = suma_segura(ventas_r, "total")
    total_compras = suma_segura(compras_r, "monto")
    total_gastos = suma_segura(gastos_r, "monto")
    total_perdidas = suma_segura(perdidas_r, "valor")
    utilidad = total_ventas - total_compras - total_gastos - total_perdidas

    c1, c2, c3 = st.columns(3)
    c1.metric("Ventas", f"RD$ {total_ventas:,.2f}")
    c2.metric("Compras", f"RD$ {total_compras:,.2f}")
    c3.metric("Gastos", f"RD$ {total_gastos:,.2f}")

    c4, c5 = st.columns(2)
    c4.metric("Pérdidas", f"RD$ {total_perdidas:,.2f}")
    c5.metric("Utilidad", f"RD$ {utilidad:,.2f}")

    if st.button("Guardar estado de resultados"):
        ok = insertar_tabla(
            "estado_resultados",
            {
                "fecha": str(fecha_hasta),
                "ventas": float(total_ventas),
                "compras": float(total_compras),
                "gastos": float(total_gastos),
                "perdidas": float(total_perdidas),
                "utilidad": float(utilidad),
            },
        )
        if ok:
            st.success("Estado de resultados guardado.")
            refrescar()

    st.subheader("📋 Historial guardado")
    er_f = filtro_texto(estado_resultados)
    st.dataframe(er_f, use_container_width=True)
    descargar_excel(er_f, "estado_resultados.csv")
