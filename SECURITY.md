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

## Respuesta ante incidente

1. Suspenda el acceso afectado.
2. Revoque tokens, llaves y contraseñas comprometidas.
3. Conserve la auditoría y las evidencias; no las edite.
4. Determine empresas, usuarios y períodos afectados.
5. Restaure únicamente después de validar el respaldo en staging.
6. Documente la causa, corrección y pruebas antes de reabrir.

