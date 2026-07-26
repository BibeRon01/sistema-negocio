"""Panel de evidencia real. No fabrica eventos, resultados ni certificaciones."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from auth import es_admin
from db import obtener_tenant_actual, supabase


def _leer(tabla: str, limite: int = 1000) -> pd.DataFrame:
    response = (
        supabase.table(tabla)
        .select("*")
        .order("created_at", desc=True)
        .limit(limite)
        .execute()
    )
    return pd.DataFrame(response.data or [])


def render_auditoria_pro():
    st.title("🛡️ Auditoría y Evidencias")
    st.caption(
        "Muestra únicamente eventos persistidos y ejecuciones reales de pruebas. "
        "Este panel no certifica el sistema."
    )

    if not es_admin():
        st.error("Solo un administrador puede consultar la auditoría.")
        return

    try:
        eventos = _leer("auditoria_eventos")
    except Exception as exc:
        st.error(f"No se pudieron cargar los eventos: {exc}")
        eventos = pd.DataFrame()

    try:
        pruebas = _leer("system_test_runs", 200)
    except Exception:
        pruebas = pd.DataFrame()

    total_eventos = len(eventos)
    pruebas_ok = int((pruebas.get("status", pd.Series(dtype=str)) == "passed").sum())
    pruebas_fallidas = int(
        pruebas.get("status", pd.Series(dtype=str)).isin(["failed", "error"]).sum()
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Eventos persistidos", total_eventos)
    k2.metric("Pruebas aprobadas", pruebas_ok)
    k3.metric("Pruebas fallidas", pruebas_fallidas)
    k4.metric("Empresa", obtener_tenant_actual() or "—")

    tab_eventos, tab_pruebas, tab_alcance = st.tabs([
        "Eventos", "Ejecuciones de pruebas", "Qué significa",
    ])
    with tab_eventos:
        if eventos.empty:
            st.info("No hay eventos persistidos para mostrar.")
        else:
            filtros = ["Todos"] + sorted(
                eventos.get("accion", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
            )
            accion = st.selectbox("Filtrar por acción", filtros)
            visibles = eventos if accion == "Todos" else eventos[eventos["accion"] == accion]
            columnas = [
                col for col in [
                    "created_at", "usuario", "accion", "modulo", "tabla",
                    "registro_id", "detalle", "metadata",
                ] if col in visibles.columns
            ]
            st.dataframe(visibles[columnas], use_container_width=True, hide_index=True)

    with tab_pruebas:
        if pruebas.empty:
            st.warning(
                "No existe evidencia de una ejecución automática registrada. "
                "La ausencia de fallos no significa que el sistema esté aprobado."
            )
        else:
            columnas = [
                col for col in [
                    "created_at", "commit_sha", "environment", "suite",
                    "passed", "failed", "status", "runner", "report_url",
                ] if col in pruebas.columns
            ]
            st.dataframe(pruebas[columnas], use_container_width=True, hide_index=True)

    with tab_alcance:
        st.markdown(
            """
            Una evidencia válida debe indicar:

            - versión exacta o `commit_sha`;
            - ambiente donde se ejecutó;
            - nombre de la suite;
            - pruebas aprobadas, fallidas y errores;
            - fecha y ejecutor identificable;
            - enlace al reporte cuando exista.

            Un evento escrito manualmente en la auditoría no equivale a una prueba.
            La aplicación tampoco puede declararse certificada a sí misma.
            """
        )


def render_mejoras_sistema():
    st.title("🧭 Mejoras del Sistema")
    st.info(
        "Las mejoras se gestionan en GitHub mediante incidencias y revisiones. "
        "Esta pantalla no simula publicaciones ni despliegues."
    )
    st.markdown(
        """
        Flujo recomendado:

        1. Documentar el problema con evidencia.
        2. Corregirlo en una rama separada.
        3. Ejecutar pruebas automáticas.
        4. Revisar el cambio.
        5. Probar en staging.
        6. Autorizar el despliegue.
        """
    )
