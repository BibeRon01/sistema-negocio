"""Panel seguro de empresas para el superadministrador de plataforma."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from api_client import (
    ApiError,
    gestionar_empresa_seguro,
    invitar_usuario_seguro,
)
from auth import es_superadmin_plataforma
from db import limpiar_cache_datos, supabase
from utils import mostrar_error_seguro


def _cargar_empresas() -> pd.DataFrame:
    response = supabase.table("empresas").select("*").order("tenant_id").execute()
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

    tab_listado, tab_crear, tab_usuario = st.tabs([
        "📋 Empresas", "➕ Nueva empresa", "👤 Crear usuario",
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
                    help="El propietario entrará con empresa, usuario y contraseña; no necesita correo.",
                )
                nombre = st.text_input("Nombre completo")
                password = st.text_input(
                    "Contraseña inicial",
                    type="password",
                    help="Mínimo 12 caracteres. El administrador deberá configurar MFA al entrar.",
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
                            "Usuario creado. Entregue empresa, usuario y contraseña por "
                            "un canal seguro. Los administradores configurarán MFA al entrar."
                        )
                    except ApiError as exc:
                        st.error(str(exc))
