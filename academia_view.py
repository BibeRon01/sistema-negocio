import streamlit as st
import pandas as pd
from datetime import date
try:
    try:
        from core.helpers import normalizar_texto
    except ModuleNotFoundError:
        from helpers import normalizar_texto
except ModuleNotFoundError:
    from helpers import normalizar_texto

def render_academia_dgii():
    st.title("🎓 Academia DGII - Capacitación Integrada")
    st.caption("Aprende el funcionamiento tributario de la DGII de la República Dominicana sin salir del sistema.")

    # Base de conocimientos estructurada
    LECCIONES = {
        "📚 Introducción a la DGII": {
            "titulo": "Lección 1: ¿Qué es la DGII y obligaciones del negocio?",
            "contenido": """
            ### 🏛️ ¿Qué es la DGII?
            La **Dirección General de Impuestos Internos (DGII)** es la institución gubernamental dominicana encargada de recaudar y administrar los impuestos nacionales. Su objetivo es financiar los servicios públicos e infraestructura del país.

            ### 💰 ¿Por qué existen los impuestos?
            Los impuestos son aportes obligatorios para sostener el presupuesto general del Estado: educación, salud, seguridad ciudadana y obras de transporte.

            ### 📋 Obligaciones de un Negocio (como un Liquor Store):
            1. **Registro Nacional de Contribuyentes (RNC):** Identificación tributaria única.
            2. **Emisión de Comprobantes Fiscales:** Documentar cada transacción con su debido NCF o e-NCF.
            3. **Retenciones de Impuestos:** Si pagas a terceros (ej. alquiler o servicios profesionales).
            4. **Declaración Jurada Mensual:** Presentar informes exactos de compras (606) y ventas (607) a más tardar el día 15 de cada mes.
            """,
            "alert": "⚠️ **¡IMPORTANTE!** Omitir o retrasarse en la declaración de comprobantes genera recargos por mora y sanciones de la DGII."
        },
        "📋 Comprobantes Fiscales": {
            "titulo": "Lección 2: Comprobantes Fiscales y Facturación Electrónica",
            "contenido": """
            ### 🧾 ¿Qué es un NCF?
            El **Número de Comprobante Fiscal (NCF)** es una secuencia alfanumérica autorizada por la DGII que identifica las facturas y da validez a los ingresos, costos y gastos.
            *   *Formato tradicional:* Empieza con la letra **B** seguida de 10 caracteres (ej: `B0100000001`).

            ### ⚡ ¿Qué es un e-CF?
            El **Comprobante Fiscal Electrónico (e-CF)** es el documento tributario electrónico firmado digitalmente que sustituye el papel y tiene la misma validez legal.
            *   *Formato electrónico:* Empieza con la letra **E** seguida de 12 caracteres (ej: `E310000000058`).

            ### ⚖️ Diferencias Claves:
            *   **Tradicional (B):** Requiere solicitud de secuencias impresas. Al agotarse, se debe solicitar otro bloque.
            *   **Electrónico (E):** Se valida en tiempo real con la DGII mediante un archivo XML y firma digital. El formato secuencial tiene 10 dígitos (13 caracteres en total).
            """,
            "alert": "💡 **TIP:** El sistema AIM ya formatea automáticamente las secuencias a 10 dígitos si detecta un comprobante que empieza por **E**."
        },
        "🧾 Facturación Electrónica": {
            "titulo": "Lección 3: Todos los tipos de comprobantes dominicanos Fichas y Ejemplos",
            "contenido": """
            A continuación, el detalle y las fichas técnicas de los comprobantes fiscales soportados en el POS de **AIM**:

            ---
            ### 📌 E31 / B01 - Factura de Crédito Fiscal
            *   **¿Para qué sirve?** Sustenta costos, gastos o crédito fiscal para el ITBIS del comprador.
            *   **¿Quién la solicita?** Clientes registrados (Empresas o profesionales independientes).
            *   **¿Cuándo usarla?** Cuando el cliente pide factura con valor fiscal y proporciona su RNC o Cédula.
            *   **Regla obligatoria:** Guardar RNC y Razón Social válidos en el sistema.

            ---
            ### 📌 E32 / B02 - Factura de Consumo
            *   **¿Para qué sirve?** Sustenta la transferencia de bienes o servicios a consumidores finales.
            *   **¿Quién la solicita?** Clientes particulares (personas físicas).
            *   **¿Cuándo usarla?** En ventas corrientes del día donde no se necesita deducir gastos. No exige RNC obligatoriamente.

            ---
            ### 📌 E33 - Nota de Débito
            *   Sube el valor facturado originalmente para corregir errores de facturación de menos.

            ---
            ### 📌 E34 - Nota de Crédito
            *   Reduce el valor facturado o anula facturas previas debido a devoluciones o errores de facturación de más.
            *   *Ejemplo real:* Vendiste una botella de Whisky. El cliente devolvió el Whisky. **No elimines la factura en el sistema.** En su lugar, emite una **Nota de Crédito E34** para regresar el stock y descontar contablemente la venta.

            ---
            ### 📌 E45 - Factura Gubernamental
            *   **¿Para qué sirve?** Facturación exclusiva a instituciones del Estado dominicano.
            *   **¿Quién la solicita?** Ministerios, ayuntamientos, direcciones generales y entes autónomos del gobierno.
            *   **Campos requeridos:** Institución, RNC público, Dependencia, Orden de Compra (OC).
            """,
            "alert": "🚨 **ATENCIÓN:** El POS de AIM bloquea transacciones de Crédito Fiscal (E31/B01) si no ingresas el RNC del cliente."
        },
        "💰 ITBIS": {
            "titulo": "Lección 4: ITBIS (Impuesto sobre Transferencia de Bienes Industrializados y Servicios)",
            "contenido": """
            ### 🧮 ¿Qué es el ITBIS?
            Es un impuesto al consumo tipo valor agregado (IVA) que se aplica a las transferencias e importaciones de bienes industrializados y servicios. La tasa general es de **18%**.

            ### 🏷️ ¿Cómo se calcula?
            *   **Si el precio YA incluye ITBIS (Desglose):**
                *   `Base Imponible = Precio Total / 1.18`
                *   `ITBIS = Precio Total - Base Imponible`
                *   *Ejemplo:* Un ron de RD$ 1,180.
                    *   `Base = 1,180 / 1.18 = RD$ 1,000`
                    *   `ITBIS = 1,180 - 1,000 = RD$ 180`
            *   **Si el precio NO incluye ITBIS (Adición):**
                *   `ITBIS = Precio Base * 0.18`
                *   `Total = Precio Base + ITBIS`
                *   *Ejemplo:* Un producto de RD$ 1,000.
                    *   `ITBIS = 1,000 * 0.18 = RD$ 180`
                    *   `Total = RD$ 1,180`
            """,
            "alert": "🛡️ **Seguridad:** En AIM, solo usuarios con roles de Gerente o Administrador pueden cambiar si el POS aplica o desglosa ITBIS."
        },
        "🥃 Impuestos de bebidas alcohólicas": {
            "titulo": "Lección 5: Impuesto Selectivo al Consumo (ISC)",
            "contenido": """
            ### 🍾 El ISC en Bebidas Alcohólicas
            El **Impuesto Selectivo al Consumo (ISC)** grava mercancías específicas cuya producción o consumo se desea desincentivar (como alcohol y tabaco).

            ### 💡 Diferencia clave para un Liquor Store:
            *   **El ISC no lo calculas tú en la caja.** Este impuesto ya está incorporado en el costo del producto cuando se lo compras al distribuidor autorizado (ej. Brugal, Presidente).
            *   **El ITBIS sí se calcula y desglosa en la caja** sobre la venta al cliente.
            *   Por lo tanto, en tu inventario, el **Costo de Adquisición** ya incluye el ISC pagado en origen.
            """,
            "alert": "📈 **Margen de Ganancia:** Recuerda que tu costo de adquisición incluye el ISC, por lo que debes fijar tus precios de venta de manera que recuperes este costo y apliques el ITBIS encima."
        },
        "📦 Compras y Ventas": {
            "titulo": "Lección 6: Formato de Envíos DGII (606, 607 y 608)",
            "contenido": """
            ### 📁 Formato 606 - Envío de Compras
            Reporta mensualmente todas las compras y gastos del negocio (operativos, inventario). Sirve para reclamar el ITBIS adelantado y deducir gastos del Impuesto sobre la Renta.

            ### 📁 Formato 607 - Envío de Ventas
            Reporta todas las ventas mensuales con comprobantes fiscales (E31, E32, E45, B01, B02).

            ### 📁 Formato 608 - Comprobantes Anulados
            Reporta los números de comprobantes que fueron emitidos pero cancelados o dañados por errores antes de entregarse.
            """,
            "alert": "📅 **Fecha Límite:** Los formatos 606 y 607 deben ser enviados a la oficina virtual de la DGII antes de los **días 15** de cada mes."
        },
        "📊 Declaraciones": {
            "titulo": "Lección 7: Conceptos de Facturación Electrónica e Integridad de Datos",
            "contenido": """
            ### 💻 El Flujo Tecnológico de e-CF:
            1. **XML:** La factura se convierte en un archivo de datos estructurado en formato XML.
            2. **Firma Digital:** Se firma digitalmente con el certificado de la empresa para garantizar autenticidad e inmutabilidad.
            3. **Track ID:** Es el código de seguimiento único que devuelve la DGII cuando recibe el lote de e-CF para procesar.
            4. **Estado de la DGII:**
               *   **Aceptado:** La factura es válida y legal.
               *   **Rechazado:** Hubo un error de RNC o firma. Se debe anular mediante Nota de Crédito.
            """,
            "alert": "🔒 **Inmutabilidad:** Una vez emitido un comprobante fiscal, **no se permite borrarlo** de la base de datos de AIM. Se debe corregir con una Nota de Crédito (E34)."
        },
        "🏛 Ventas al Estado": {
            "titulo": "Lección 8: Ventas al Estado y Retenciones Gubernamentales",
            "contenido": """
            Al vender a una entidad gubernamental dominicana:
            *   Se emite una **Factura Gubernamental (E45 / B15)**.
            *   El Estado dominicano realiza retenciones de ITBIS automáticas. En muchos casos, retienen el **100% del ITBIS** facturado.
            *   Debes registrar en el sistema que el ITBIS fue retenido para evitar pagarlo doble en tu declaración mensual de IT-1.
            """,
            "alert": "📄 **Documentación:** Recuerda solicitar siempre la **Orden de Compra oficial** y el Certificado de Registro del Proveedor del Estado (RPE) antes de despachar."
        },
        "❌ Anulaciones y Notas de Crédito": {
            "titulo": "Lección 9: Notas de Crédito (E34 / B04)",
            "contenido": """
            ### 🧾 ¿Para qué sirve una Nota de Crédito?
            Es el documento fiscal emitido para **anular o modificar** de forma parcial o total un comprobante previamente entregado.

            ### 🥃 Ejemplo Práctico:
            1. Vendiste una botella de Whisky con comprobante fiscal.
            2. El cliente regresa porque la botella tiene un defecto o decide cambiar el producto.
            3. **No elimines ni alteres la venta original.**
            4. Emitimos una **Nota de Crédito E34** vinculada a esa factura.
            5. El stock regresa al inventario y el monto del crédito reduce tus ingresos netos y balance de ITBIS a pagar del mes.
            """,
            "alert": "🚫 **Prohibido:** Eliminar facturas registradas en el diario de ventas altera la contabilidad y puede provocar auditorías desfavorables de la DGII."
        },
        "📝 Glosario Tributario": {
            "titulo": "Glosario de Términos Rápidos",
            "contenido": """
            *   **NCF:** Número de Comprobante Fiscal.
            *   **e-NCF / e-CF:** Comprobante Fiscal Electrónico.
            *   **ITBIS:** Impuesto sobre Transferencia de Bienes Industrializados y Servicios.
            *   **ISC:** Impuesto Selectivo al Consumo.
            *   **RNC:** Registro Nacional de Contribuyentes (9 dígitos para empresas, 11 para cédulas).
            *   **606 / 607:** Reportes oficiales de envío a la DGII de Compras y Ventas.
            *   **IT-1:** Declaración mensual jurada de ITBIS.
            *   **IR-2:** Declaración jurada anual de Impuesto sobre la Renta para sociedades.
            """,
            "alert": "💡 Usa el buscador de arriba para encontrar cualquiera de estos términos rápidamente."
        }
    }

    # 1. BUSCADOR INTEGRADO
    buscar_academia = st.text_input("🔍 Buscar término o lección en la Academia (ej. E31, ITBIS, 607)...", key="pos_bus_acad")
    
    if buscar_academia:
        st.markdown(f"#### Resultados de búsqueda para: *'{buscar_academia}'*")
        encontrado = False
        query = normalizar_texto(buscar_academia)
        
        for k, v in LECCIONES.items():
            if query in normalizar_texto(k) or query in normalizar_texto(v["titulo"]) or query in normalizar_texto(v["contenido"]):
                encontrado = True
                with st.expander(f"📖 {v['titulo']}", expanded=True):
                    st.markdown(v["contenido"])
                    st.warning(v["alert"])
        
        if not encontrado:
            st.info("No se encontraron coincidencias. Intenta buscando términos como 'ITBIS', 'RNC' o 'E34'.")
        st.markdown("---")

    # 2. CONTENIDO PRINCIPAL
    tabs_nombres = list(LECCIONES.keys()) + ["🤖 Simulador Fiscal", "🎓 Evaluaciones"]
    tabs = st.tabs(tabs_nombres)

    for i, key in enumerate(LECCIONES.keys()):
        with tabs[i]:
            v = LECCIONES[key]
            st.subheader(v["titulo"])
            st.markdown(v["contenido"])
            st.warning(v["alert"])

    # TAB DE SIMULADOR
    with tabs[len(LECCIONES)]:
        st.subheader("🤖 Simulador de Decisiones Fiscales")
        st.write("Responde las preguntas del simulador interactivo para saber qué tipo de comprobante corresponde a tu transacción:")

        if "sim_paso" not in st.session_state:
            st.session_state["sim_paso"] = 0
            st.session_state["sim_respuestas"] = {}

        def reset_simulador():
            st.session_state["sim_paso"] = 0
            st.session_state["sim_respuestas"] = {}

        if st.session_state["sim_paso"] == 0:
            st.write("**Pregunta 1: ¿La venta es para una institución del Estado dominicano?**")
            c1, c2 = st.columns(2)
            if c1.button("Sí, es gubernamental", key="sim_p1_si"):
                st.session_state["sim_respuestas"]["es_gob"] = True
                st.session_state["sim_paso"] = 99  # Fin gubernamental
                st.rerun()
            if c2.button("No, es un particular o empresa privada", key="sim_p1_no"):
                st.session_state["sim_respuestas"]["es_gob"] = False
                st.session_state["sim_paso"] = 1
                st.rerun()

        elif st.session_state["sim_paso"] == 1:
            st.write("**Pregunta 2: ¿El cliente solicitó factura con RNC/Cédula para registrar gastos o usar crédito fiscal?**")
            c1, c2 = st.columns(2)
            if c1.button("Sí, solicitó comprobante fiscal", key="sim_p2_si"):
                st.session_state["sim_respuestas"]["quiere_fiscal"] = True
                st.session_state["sim_paso"] = 2
                st.rerun()
            if c2.button("No, es una venta a consumidor final común", key="sim_p2_no"):
                st.session_state["sim_respuestas"]["quiere_fiscal"] = False
                st.session_state["sim_paso"] = 3
                st.rerun()

        elif st.session_state["sim_paso"] == 2:
            st.write("**Pregunta 3: ¿Estás emitiendo un e-CF electrónico (inicia con E) o un NCF tradicional (inicia con B)?**")
            c1, c2 = st.columns(2)
            if c1.button("Comprobante Electrónico (e-CF)", key="sim_p3_e"):
                st.session_state["sim_respuestas"]["tipo_ncf"] = "E"
                st.session_state["sim_paso"] = 100  # Resultado E31
                st.rerun()
            if c2.button("Comprobante Tradicional (NCF)", key="sim_p3_b"):
                st.session_state["sim_respuestas"]["tipo_ncf"] = "B"
                st.session_state["sim_paso"] = 101  # Resultado B01
                st.rerun()

        elif st.session_state["sim_paso"] == 3:
            st.write("**Pregunta 4: ¿Deseas emitir comprobante de consumo electrónico (E) o tradicional (B)?**")
            c1, c2 = st.columns(2)
            if c1.button("Consumo Electrónico", key="sim_p4_e"):
                st.session_state["sim_respuestas"]["tipo_ncf"] = "E"
                st.session_state["sim_paso"] = 102  # Resultado E32
                st.rerun()
            if c2.button("Consumo Tradicional", key="sim_p4_b"):
                st.session_state["sim_respuestas"]["tipo_ncf"] = "B"
                st.session_state["sim_paso"] = 103  # Resultado B02
                st.rerun()

        # Resultados finales
        elif st.session_state["sim_paso"] == 99:
            st.success("✅ **Resultado del simulador:** Debes emitir una **Factura Gubernamental (E45 o B15)**.")
            st.markdown("""
            *   **Explicación:** Las ventas al Estado dominicano requieren de comprobantes específicos (E45/B15). Debes solicitar el RNC público de la institución, la dependencia y la Orden de Compra física o digital antes de procesar el pago.
            """)
            if st.button("🔄 Reiniciar Simulador", key="btn_reset_sim_99"):
                reset_simulador()
                st.rerun()

        elif st.session_state["sim_paso"] == 100:
            st.success("✅ **Resultado del simulador:** Debes emitir una **Factura de Crédito Fiscal Electrónica (E31)**.")
            st.markdown("""
            *   **Explicación:** Se requiere RNC y datos de cliente registrados de forma obligatoria en la base de datos de AIM. Sirve para que tu cliente sustente gastos y reclame el ITBIS pagado.
            """)
            if st.button("🔄 Reiniciar Simulador", key="btn_reset_sim_100"):
                reset_simulador()
                st.rerun()

        elif st.session_state["sim_paso"] == 101:
            st.success("✅ **Resultado del simulador:** Debes emitir una **Factura de Crédito Fiscal Tradicional (B01)**.")
            st.markdown("""
            *   **Explicación:** Corresponde al NCF tradicional para crédito fiscal. Requiere RNC y Razón social, con longitud secuencial a 8 dígitos.
            """)
            if st.button("🔄 Reiniciar Simulador", key="btn_reset_sim_101"):
                reset_simulador()
                st.rerun()

        elif st.session_state["sim_paso"] == 102:
            st.success("✅ **Resultado del simulador:** Debes emitir una **Factura de Consumo Electrónica (E32)**.")
            st.markdown("""
            *   **Explicación:** Para ventas a consumidor final. No requiere registrar RNC ni Cédula obligatoriamente en el POS.
            """)
            if st.button("🔄 Reiniciar Simulador", key="btn_reset_sim_102"):
                reset_simulador()
                st.rerun()

        elif st.session_state["sim_paso"] == 103:
            st.success("✅ **Resultado del simulador:** Debes emitir una **Factura de Consumo Tradicional (B02)**.")
            st.markdown("""
            *   **Explicación:** Consumidor final tradicional. No requiere RNC ni identificación tributaria obligatoria.
            """)
            if st.button("🔄 Reiniciar Simulador", key="btn_reset_sim_103"):
                reset_simulador()
                st.rerun()

    # TAB DE EVALUACIONES
    with tabs[len(LECCIONES) + 1]:
        st.subheader("🎓 Evaluación de Conocimiento Fiscal")
        st.write("Demuestra tus conocimientos fiscales y prepárate para administrar un negocio seguro:")

        if "eval_pregunta" not in st.session_state:
            st.session_state["eval_pregunta"] = 1
            st.session_state["eval_aciertos"] = 0
            st.session_state["eval_feedback"] = None

        def contestar_eval(correcto: bool, feedback_text: str):
            if correcto:
                st.session_state["eval_aciertos"] += 1
                st.session_state["eval_feedback"] = f"🟢 **¡CORRECTO!** {feedback_text}"
            else:
                st.session_state["eval_feedback"] = f"🔴 **¡INCORRECTO!** {feedback_text}"

        def siguiente_pregunta():
            st.session_state["eval_pregunta"] += 1
            st.session_state["eval_feedback"] = None

        def reset_eval():
            st.session_state["eval_pregunta"] = 1
            st.session_state["eval_aciertos"] = 0
            st.session_state["eval_feedback"] = None

        # PREGUNTA 1
        if st.session_state["eval_pregunta"] == 1:
            st.write("### Pregunta 1: Una empresa te compra RD$ 80,000 en insumos y te pide RNC para registrar gastos. ¿Qué comprobante debes emitir?")
            
            op1 = st.button("A) Factura de Consumo (E32 / B02)", key="ev_q1_a")
            op2 = st.button("B) Factura de Crédito Fiscal (E31 / B01)", key="ev_q1_b")
            op3 = st.button("C) Nota de Crédito (E34 / B04)", key="ev_q1_c")

            if op1:
                contestar_eval(False, "Las facturas de consumo no sirven para sustentar gastos comerciales ni reclamar ITBIS.")
            if op2:
                contestar_eval(True, "Correcto. El Crédito Fiscal (E31/B01) es obligatorio cuando una empresa necesita justificar un gasto operativo y deducir ITBIS.")
            if op3:
                contestar_eval(False, "Las Notas de Crédito sirven únicamente para anular o modificar facturas previas.")

            if st.session_state["eval_feedback"]:
                st.markdown(st.session_state["eval_feedback"])
                if st.button("Siguiente Pregunta ➡️", key="btn_next_q1"):
                    siguiente_pregunta()
                    st.rerun()

        # PREGUNTA 2
        elif st.session_state["eval_pregunta"] == 2:
            st.write("### Pregunta 2: Un cliente te devuelve una botella de ron que compró ayer por error. ¿Qué acción debes realizar en el sistema?")
            
            op1 = st.button("A) Eliminar físicamente la venta de la base de datos", key="ev_q2_a")
            op2 = st.button("B) Modificar el total de la venta original restando la botella", key="ev_q2_b")
            op3 = st.button("C) Mantener la venta intacta y emitir una Nota de Crédito (E34 / B04)", key="ev_q2_c")

            if op1:
                contestar_eval(False, "Eliminar registros de venta es una práctica contable ilegal y prohibida por la DGII.")
            if op2:
                contestar_eval(False, "Modificar transacciones ya cerradas altera las secuencias y la integridad fiscal.")
            if op3:
                contestar_eval(True, "Correcto. La única vía válida y legal para modificar una venta emitida es emitir una Nota de Crédito (E34/B04), la cual regresa el stock y ajusta el ITBIS de forma automática.")

            if st.session_state["eval_feedback"]:
                st.markdown(st.session_state["eval_feedback"])
                if st.button("Siguiente Pregunta ➡️", key="btn_next_q2"):
                    siguiente_pregunta()
                    st.rerun()

        # PREGUNTA 3
        elif st.session_state["eval_pregunta"] == 3:
            st.write("### Pregunta 3: ¿Qué es el Impuesto Selectivo al Consumo (ISC) y cómo se maneja en un Liquor Store?")
            
            op1 = st.button("A) Es un impuesto del 18% que se calcula al cliente en caja sobre cada botella", key="ev_q3_a")
            op2 = st.button("B) Es un impuesto específico que ya viene incorporado en el costo del producto cuando le compras al distribuidor", key="ev_q3_b")
            op3 = st.button("C) Es un impuesto anual que se presenta en el formulario IR-2", key="ev_q3_c")

            if op1:
                contestar_eval(False, "El impuesto del 18% cobrado en caja es el ITBIS. El ISC tiene otras tasas y métodos.")
            if op2:
                contestar_eval(True, "¡Excelente! El ISC es un arancel específico ya cobrado por el fabricante/distribuidor de bebidas alcohólicas e incorporado en tu costo de adquisición. No debes sumarlo de nuevo en la caja.")
            if op3:
                contestar_eval(False, "El IR-2 es la declaración jurada anual del Impuesto Sobre la Renta de empresas, no tiene relación con el ISC de productos.")

            if st.session_state["eval_feedback"]:
                st.markdown(st.session_state["eval_feedback"])
                if st.button("Ver Resultados 🏆", key="btn_next_q3"):
                    siguiente_pregunta()
                    st.rerun()

        # RESULTADOS EVALUACION
        else:
            st.success("🎉 **Evaluación completada**")
            st.metric("Preguntas Acertadas", f"{st.session_state['eval_aciertos']} de 3")
            
            if st.session_state['eval_aciertos'] == 3:
                st.balloons()
                st.write("🏆 **¡Felicidades, eres un experto fiscal de la DGII!** Conoces los comprobantes correctos, el tratamiento de notas de crédito y la diferencia del ISC.")
            else:
                st.info("Sigue leyendo el material de la Academia para lograr una puntuación perfecta.")

            if st.button("🔄 Intentar de nuevo", key="btn_reset_eval"):
                reset_eval()
                st.rerun()
