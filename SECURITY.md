# Política de seguridad

## Reporte privado

No publique vulnerabilidades, datos personales, tokens o capturas con información
real en una incidencia pública. Informe al propietario del repositorio por un
canal privado y revoque inmediatamente cualquier credencial expuesta.

## Secretos prohibidos en el repositorio

- service-role de Supabase;
- contraseñas de usuarios;
- tokens de sesión;
- certificados o contraseñas e-CF;
- llaves Fernet de respaldo;
- archivos de respaldo o exportaciones de producción.

## Separación de ambientes

Staging y producción deben ser proyectos Supabase distintos. Los scripts de
restauración verifican el hostname y se detienen si el destino contiene datos.

## Operaciones económicas

Ventas, pagos, caja, inventario FIFO, compras, nómina y cierres se modifican
mediante funciones SQL autorizadas. No se deben reintroducir escrituras directas
desde Streamlit a las tablas económicas protegidas.

La factura de compra completa se guarda mediante
`api_registrar_factura_compra`: usa una clave de idempotencia y una sola
transacción PostgreSQL. Una línea inválida debe revertir cabecera, líneas,
compras históricas, stock, lotes, cuentas por pagar, contabilidad y auditoría.

## Sesiones y MFA

AIS acepta únicamente sesiones verificadas por Supabase Auth y
`api_my_session`. El perfil guardado en Streamlit no autoriza por sí mismo y
cualquier fallo de revalidación elimina tokens, perfil, tenant y estado MFA.
Administradores, superadministradores y permisos de alto riesgo requieren el
nivel real `aal2` de Supabase.

## Interfaz y errores

Los valores dinámicos deben escaparse antes de insertarlos en HTML. Las
excepciones completas se registran internamente; la interfaz solo presenta
mensajes controlados que no exponen consultas, rutas, tokens ni detalles del
servidor.

## Respuesta ante incidente

1. Suspenda el acceso afectado.
2. Revoque tokens, llaves y contraseñas comprometidas.
3. Conserve la auditoría y las evidencias; no las edite.
4. Determine empresas, usuarios y períodos afectados.
5. Restaure únicamente después de validar el respaldo en staging.
6. Documente la causa, corrección y pruebas antes de reabrir.
