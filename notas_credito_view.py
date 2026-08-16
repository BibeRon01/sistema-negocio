"""Orientación sobre notas de crédito; no emite documentos fiscales."""

import streamlit as st


def render_notas_credito():
    st.title("📘 Academia: notas de crédito")
    st.warning(
        "Esta pantalla es educativa. A&M no crea, numera, firma, registra ni "
        "envía notas de crédito E34/B04 y no consume secuencias NCF."
    )
    st.markdown(
        """
        Una nota de crédito puede utilizarse para documentar ajustes de una
        operación previa, pero el tipo de comprobante, los plazos, la referencia
        al documento original y el tratamiento fiscal dependen de las reglas
        vigentes de la DGII.

        Antes de realizar una corrección:

        1. identifique el comprobante original y el motivo;
        2. confirme con su contador el tratamiento contable y tributario;
        3. utilice únicamente el proceso o proveedor autorizado;
        4. conserve la evidencia y la trazabilidad de la operación.

        Las devoluciones internas de inventario y dinero requieren un flujo
        transaccional independiente; no deben confundirse con la emisión de un
        documento fiscal.
        """
    )
    st.link_button(
        "Consultar información oficial DGII",
        "https://dgii.gov.do/cicloContribuyente/facturacion/comprobantesFiscales/",
    )
    st.caption(
        "Verifique directamente en la DGII la versión, vigencia y requisitos "
        "aplicables a su empresa."
    )
