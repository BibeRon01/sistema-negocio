"""Contenido educativo sobre facturación electrónica de República Dominicana.

Este módulo no genera, firma, valida ni transmite documentos fiscales.
"""

import streamlit as st


def render_facturacion_electronica():
    st.title("📘 Academia: Facturación Electrónica e-CF")
    st.warning(
        "Módulo exclusivamente educativo. El sistema A&M no genera, firma, "
        "valida ni envía e-CF y nunca solicita su certificado digital."
    )

    tab_que_es, tab_requisitos, tab_proceso, tab_seguridad = st.tabs([
        "¿Qué es?", "Qué necesita", "Proceso general", "Seguridad",
    ])

    with tab_que_es:
        st.subheader("Concepto básico")
        st.write(
            "Un comprobante fiscal electrónico es un documento estructurado que "
            "debe cumplir las especificaciones, validaciones y procedimientos "
            "vigentes de la DGII. No es simplemente un PDF ni un XML creado por la aplicación."
        )
        st.markdown(
            """
            - **Emisor electrónico:** contribuyente autorizado para emitir.
            - **e-NCF:** número fiscal electrónico autorizado.
            - **XML:** formato estructurado definido por la DGII.
            - **Firma digital:** mecanismo aplicado con un certificado bajo control del contribuyente.
            - **TrackID:** referencia entregada por los servicios oficiales cuando corresponda.
            """
        )

    with tab_requisitos:
        st.subheader("Lista orientativa")
        st.checkbox("RNC y obligaciones tributarias actualizadas", disabled=True)
        st.checkbox("Autorización o incorporación al modelo e-CF", disabled=True)
        st.checkbox("Certificado digital válido y custodiado de forma segura", disabled=True)
        st.checkbox("Proveedor o desarrollo certificado según el proceso aplicable", disabled=True)
        st.checkbox("Pruebas y aprobación en los ambientes indicados por DGII", disabled=True)
        st.checkbox("Procedimiento de contingencia y conservación documental", disabled=True)
        st.info("Confirme cada requisito con su contador y directamente con la DGII.")

    with tab_proceso:
        st.subheader("Flujo conceptual")
        st.markdown(
            """
            1. El contribuyente confirma su situación y requisitos con DGII.
            2. Se prepara el certificado y la solución autorizada fuera de este módulo.
            3. Se realizan las pruebas oficiales exigidas.
            4. La solución autorizada construye, firma y transmite el documento.
            5. Se conserva la respuesta oficial y se atienden rechazos o contingencias.
            """
        )
        st.error(
            "Este sistema no simula aceptación, no muestra TrackID de demostración "
            "y no posee un modo de “producción DGII”."
        )

    with tab_seguridad:
        st.subheader("Proteja el certificado")
        st.markdown(
            """
            - No cargue archivos `.p12` o `.pfx` en esta aplicación.
            - No guarde la contraseña del certificado en GitHub o Streamlit Secrets.
            - Limite el acceso al certificado al proveedor fiscal autorizado.
            - Documente renovación, revocación y respuesta ante incidentes.
            """
        )

    st.markdown("### Enlaces oficiales")
    st.link_button(
        "Documentación e-CF — DGII",
        "https://dgii.gov.do/cicloContribuyente/facturacion/comprobantesFiscalesElectronicosE-CF/Paginas/documentacionSobreE-CF.aspx",
    )
    st.caption("Contenido orientativo. Verifique siempre la versión y fecha publicadas por la DGII.")
