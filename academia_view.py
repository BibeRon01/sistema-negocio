"""Academia DGII: orientación general, sin preparación de documentos oficiales."""

import streamlit as st

from contabilidad_view import render_reportes_dgii
from facturacion_electronica_view import render_facturacion_electronica


def render_academia_dgii():
    st.title("🎓 Academia DGII")
    st.caption("Conocimientos básicos para conversar con su contador y organizar la información.")
    st.warning(
        "La Academia no sustituye a la DGII ni a un profesional tributario. "
        "No emite documentos, no elige comprobantes por usted y no prepara declaraciones."
    )

    area = st.radio(
        "Seleccione un área",
        ["Conceptos y reportes", "Facturación electrónica", "Glosario y checklist"],
        horizontal=True,
    )
    if area == "Conceptos y reportes":
        render_reportes_dgii()
    elif area == "Facturación electrónica":
        render_facturacion_electronica()
    else:
        st.subheader("Glosario básico")
        st.markdown(
            """
            - **RNC:** identificación tributaria del contribuyente.
            - **NCF / e-NCF:** numeración de comprobantes conforme al proceso aplicable.
            - **ITBIS:** impuesto sobre transferencias de bienes industrializados y servicios.
            - **ISC:** impuesto selectivo que aplica a determinados bienes y servicios.
            - **606/607/608/609:** formatos informativos con finalidades distintas.
            - **IT-1 / IR-2:** declaraciones con reglas, anexos y fechas que deben verificarse.
            """
        )
        st.subheader("Checklist para la reunión con su contador")
        for label in [
            "Ventas y recibos internos conciliados",
            "Compras y gastos con documentos de soporte",
            "Inventario y costo de ventas revisados",
            "Caja y bancos conciliados",
            "Créditos y pagos pendientes revisados",
            "Nómina, TSS y retenciones organizadas",
            "Anulaciones y devoluciones documentadas",
        ]:
            st.checkbox(label, key=f"dgii_check_{label}", disabled=True)
        st.link_button("Portal oficial DGII", "https://dgii.gov.do/")
        st.caption("Revise siempre la fecha y versión de la información oficial.")
