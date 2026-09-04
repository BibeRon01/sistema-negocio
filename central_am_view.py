"""Panel seguro de empresas para el superadministrador de plataforma."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from api_client import (
    ApiError,
    gestionar_empresa_seguro,
    invitar_usuario_seguro,
    registrar_licencia_empresa_seguro,
)
from auth import es_superadmin_plataforma
from db import limpiar_cache_datos, supabase
from utils import mostrar_error_seguro


def _cargar_empresas() -> pd.DataFrame:
    response = supabase.table("empresas").select("*").order("tenant_id").execute()
    return pd.DataFrame(response.data or [])


def _cargar_suscripciones(tenant_id: str) -> pd.DataFrame:
    response = (
        supabase.table("suscripciones_empresas")
        .select(
            "id,empresa_id,fecha_inicio,fecha_vencimiento,monto_pagado,"
            "periodo,metodo_pago,dias_gracia,observacion,created_at"
        )
        .eq("empresa_id", str(tenant_id))
        .order("fecha_vencimiento", desc=True)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def render_gestion_empresas():
    if not es_superadmin_plataforma():
        st.error("🔒 Acceso reservado al superadministrador de plataforma.")
        st.stop()

    st.title("🏢 Gestión de Empresas")
    st.caption("Crea, configura o suspende empresas sin borrar su historial contable.")

    try:
        empresas = _cargar_empresas()
    except Exception as exc:
        mostrar_error_seguro("No se pudo consultar el catálogo de empresas.", exc)
        return

    total = len(empresas)
    activas = int(empresas["activo"].fillna(False).sum()) if not empresas.empty else 0
    k1, k2, k3 = st.columns(3)
    k1.metric("Empresas", total)
    k2.metric("Activas", activas)
    k3.metric("Suspendidas", total - activas)

    tab_listado, tab_crear, tab_usuario, tab_licencias = st.tabs([
        "📋 Empresas", "➕ Nueva empresa", "👤 Crear usuario", "💳 Licencias y pagos",
    ])

    with tab_listado:
        if empresas.empty:
            st.info("No hay empresas registradas.")
        else:
            st.dataframe(empresas, use_container_width=True, hide_index=True)
            tenant_id = st.selectbox(
                "Empresa que desea administrar",
                empresas["tenant_id"].astype(str).tolist(),
                key="secure_company_select",
            )
            row = empresas[empresas["tenant_id"].astype(str) == tenant_id].iloc[0]
            with st.form("secure_company_update"):
                nombre = st.text_input("Nombre", value=str(row.get("nombre") or tenant_id))
                activa = st.checkbox("Empresa activa", value=bool(row.get("activo", True)))
                st.info(
                    "Suspender impide nuevas operaciones. No elimina ventas, auditoría, "
                    "usuarios ni información contable."
                )
                if st.form_submit_button("Guardar cambios", type="primary"):
                    try:
                        gestionar_empresa_seguro(
                            action="update",
                            tenant_id=tenant_id,
                            nombre=nombre,
                            activo=activa,
                        )
                        limpiar_cache_datos()
                        st.success("Empresa actualizada.")
                        st.rerun()
                    except ApiError as exc:
                        st.error(str(exc))

    with tab_licencias:
        if empresas.empty:
            st.info("Primero cree una empresa.")
        else:
            st.subheader("Registrar licencia o renovación")
            st.caption(
                "Este registro pertenece a la facturación de la plataforma A&M. "
                "No se mezcla con ventas, caja, gastos ni contabilidad de la empresa seleccionada."
            )
            company_names = {
                str(row["tenant_id"]): str(row.get("nombre") or row["tenant_id"])
                for _, row in empresas.iterrows()
            }
            tenant_license = st.selectbox(
                "Empresa",
                list(company_names),
                format_func=lambda value: f"{company_names[value]} ({value})",
                key="secure_license_company",
            )

            period_options = {
                "Demostración": "demostracion",
                "Cortesía": "cortesia",
                "Mensual": "mensual",
                "Trimestral": "trimestral",
                "Anual": "anual",
                "Personalizado": "personalizado",
            }
            method_options = {
                "Cortesía / sin cobro": "cortesia",
                "Efectivo": "efectivo",
                "Transferencia": "transferencia",
                "Tarjeta": "tarjeta",
                "Otro": "otro",
            }
            with st.form("secure_company_license"):
                c1, c2 = st.columns(2)
                period_label = c1.selectbox("Tipo de licencia", list(period_options))
                payment_label = c2.selectbox("Método de pago", list(method_options))
                start_date = c1.date_input("Fecha de inicio", value=date.today())
                end_date = c2.date_input(
                    "Fecha de vencimiento",
                    value=date.today() + timedelta(days=30),
                )
                amount = c1.number_input(
                    "Monto pagado (RD$)",
                    min_value=0.0,
                    max_value=1_000_000_000.0,
                    value=0.0,
                    step=100.0,
                    format="%.2f",
                )
                grace_days = c2.number_input(
                    "Días de gracia",
                    min_value=0,
                    max_value=60,
                    value=5,
                    step=1,
                )
                observation = st.text_area(
                    "Observación",
                    placeholder="Ejemplo: licencia demo de 30 días",
                    max_chars=500,
                )
                register_license = st.form_submit_button(
                    "Registrar licencia y activar acceso",
                    type="primary",
                    use_container_width=True,
                )

            if register_license:
                if end_date < start_date:
                    st.error("La fecha de vencimiento no puede ser anterior a la fecha de inicio.")
                elif period_options[period_label] in {"demostracion", "cortesia"} and amount != 0:
                    st.error("Una licencia de demostración o cortesía debe registrarse con monto RD$0.00.")
                elif period_options[period_label] not in {"demostracion", "cortesia"} and method_options[payment_label] == "cortesia":
                    st.error("Seleccione el método utilizado para recibir el pago.")
                else:
                    try:
                        registrar_licencia_empresa_seguro(
                            tenant_id=tenant_license,
                            fecha_inicio=start_date.isoformat(),
                            fecha_vencimiento=end_date.isoformat(),
                            monto_pagado=float(amount),
                            periodo=period_options[period_label],
                            metodo_pago=method_options[payment_label],
                            dias_gracia=int(grace_days),
                            observacion=observation,
                        )
                        limpiar_cache_datos()
                        st.success(
                            f"Licencia registrada para {company_names[tenant_license]} "
                            f"hasta el {end_date.strftime('%d/%m/%Y')}."
                        )
                    except ApiError as exc:
                        st.error(str(exc))

            st.divider()
            st.subheader("Historial de licencias y pagos")
            try:
                subscriptions = _cargar_suscripciones(tenant_license)
            except Exception as exc:
                mostrar_error_seguro("No se pudo consultar el historial de licencias.", exc)
                subscriptions = pd.DataFrame()
            if subscriptions.empty:
                st.info("Esta empresa todavía no tiene licencias registradas.")
            else:
                today = pd.Timestamp(date.today())
                expiry = pd.to_datetime(
                    subscriptions["fecha_vencimiento"],
                    errors="coerce",
                )
                grace = pd.to_numeric(
                    subscriptions.get("dias_gracia", 0),
                    errors="coerce",
                ).fillna(0)
                subscriptions.insert(
                    0,
                    "estado",
                    [
                        "Activa" if pd.notna(value) and value + pd.Timedelta(days=int(days)) >= today else "Vencida"
                        for value, days in zip(expiry, grace)
                    ],
                )
                st.dataframe(
                    subscriptions,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "monto_pagado": st.column_config.NumberColumn(
                            "Monto pagado",
                            format="RD$ %.2f",
                        ),
                        "fecha_inicio": "Inicio",
                        "fecha_vencimiento": "Vencimiento",
                        "metodo_pago": "Método",
                        "dias_gracia": "Gracia",
                        "observacion": "Observación",
                    },
                )

    with tab_crear:
        with st.form("secure_company_create"):
            c1, c2 = st.columns(2)
            tenant_id = c1.text_input(
                "ID único",
                placeholder="mi_empresa",
                help="Solo letras minúsculas, números, guion y guion bajo.",
            )
            nombre = c2.text_input("Nombre comercial")
            telefono = c1.text_input("Teléfono")
            rnc = c2.text_input("RNC")
            direccion = c1.text_input("Dirección")
            slogan = c2.text_input("Slogan")
            if st.form_submit_button("Crear empresa", type="primary"):
                try:
                    gestionar_empresa_seguro(
                        action="create",
                        tenant_id=tenant_id,
                        nombre=nombre,
                        activo=True,
                        configuracion={
                            "telefono": telefono,
                            "rnc": rnc,
                            "direccion": direccion,
                            "slogan": slogan,
                        },
                    )
                    limpiar_cache_datos()
                    st.success("Empresa creada. Ahora cree su primer administrador.")
                    st.rerun()
                except ApiError as exc:
                    st.error(str(exc))

    with tab_usuario:
        if empresas.empty:
            st.info("Primero cree una empresa.")
        else:
            with st.form("secure_company_user"):
                tenant = st.selectbox(
                    "Empresa",
                    empresas[empresas["activo"].fillna(False)]["tenant_id"].astype(str).tolist(),
                )
                username = st.text_input(
                    "Usuario de acceso",
                    placeholder="propietario",
                    help=(
                        "Debe ser único en toda la plataforma. El propietario entrará "
                        "solo con este usuario y su contraseña; no necesita correo."
                    ),
                )
                nombre = st.text_input("Nombre completo")
                password = st.text_input(
                    "Contraseña inicial",
                    type="password",
                    help=(
                        "Mínimo 4 caracteres y al menos un símbolo como ., @, !, _ o -. "
                        "El administrador deberá configurar MFA al entrar."
                    ),
                )
                rol = st.selectbox(
                    "Rol",
                    ["admin", "gerente", "supervisor", "cajero", "cajera", "consulta"],
                )
                if st.form_submit_button("Crear usuario", type="primary"):
                    permisos = {
                        "puede_vender": rol in {"admin", "gerente", "cajero", "cajera"},
                        "puede_abrir_caja": rol in {"admin", "gerente", "cajero", "cajera"},
                        "puede_cerrar_caja": rol in {"admin", "gerente"},
                        "puede_ver_reportes": rol in {"admin", "gerente", "consulta"},
                        "puede_configurar": rol == "admin",
                        "puede_registrar_compras": rol in {"admin", "gerente"},
                        "puede_registrar_gastos": rol in {"admin", "gerente"},
                        "puede_anular": rol in {"admin", "gerente"},
                        "ver_credito": rol in {"admin", "gerente", "cajero", "cajera"},
                    }
                    try:
                        invitar_usuario_seguro(
                            usuario=username,
                            password=password,
                            nombre=nombre,
                            rol=rol,
                            tenant_id=tenant,
                            permisos=permisos,
                        )
                        st.success(
                            "Usuario creado. Entregue el acceso "
                            f"{str(username).strip().lower()} y la contraseña "
                            "por un canal seguro. Los administradores configurarán MFA al entrar."
                        )
                    except ApiError as exc:
                        st.error(str(exc))
