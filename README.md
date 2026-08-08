# Sistema de negocio A&M — edición segura v3

Esta carpeta es la reconstrucción del sistema existente. Conserva su interfaz y
sus módulos principales, pero mueve las operaciones críticas a una API
transaccional dentro de PostgreSQL/Supabase.

> Estado: candidato para **staging**. No debe conectarse primero a producción.
> La aprobación final requiere ejecutar las migraciones, las pruebas RLS con dos
> empresas y un simulacro de respaldo/restauración en un proyecto staging.

## Cambios principales

- acceso únicamente con Supabase Auth;
- MFA obligatorio para administradores y cualquier cuenta con permisos de alto
  riesgo;
- cliente Supabase aislado por sesión de Streamlit;
- separación por empresa y permisos de lectura por módulo mediante RLS;
- service-role únicamente en Edge Functions y scripts locales;
- ventas, cuentas abiertas, anulaciones, abonos, caja, compras y nómina mediante
  funciones transaccionales;
- inventario FIFO y asientos contables creados por el servidor;
- facturas completadas y registros de auditoría no se eliminan;
- módulo DGII/e-CF exclusivamente educativo;
- respaldo de datos cifrado y restauración permitida solo en staging vacío;
- pruebas y flujos de GitHub Actions incluidos.

## Inicio local

1. Cree un ambiente virtual con Python 3.12.
2. Instale `requirements.txt`.
3. Copie `.streamlit/secrets.example.toml` como `.streamlit/secrets.toml`.
4. Coloque solo la URL de Supabase y la llave pública/anon.
5. Ejecute `streamlit run app.py`.

Nunca coloque la service-role, una contraseña, un certificado fiscal o una llave
de respaldo en Streamlit, GitHub o el código fuente.

Para publicar la aplicación en Streamlit Community Cloud, siga
`SUBIR_A_STREAMLIT.md` y suba siempre el proyecto completo, no solamente
`app.py`.

## Migraciones

La única fuente autorizada es `supabase/migrations/`. Deben ejecutarse en orden:

1. `202607250001_secure_foundation.sql`
2. `202607250002_transactional_api.sql`
3. `202607250003_maintenance_and_accounting_api.sql`

Consulte `GUIA_PUBLICACION.md` antes de aplicarlas.
Los parámetros 2026 y el alcance educativo DGII se documentan en
`REFERENCIAS_OFICIALES.md`.

## Punto de entrada

Use `app.py`. El archivo `aplicación.py` se conserva solo como alias compatible.

## Límites deliberados

- El sistema no genera, firma, valida ni envía formularios DGII o e-CF.
- Dividir/fusionar cuentas y cobrar participantes están desactivados hasta tener
  un flujo transaccional específico.
- Las compras ya registradas no se editan o eliminan directamente.
- La tasa ARL debe configurarse y confirmarse para cada empleado.
- Los parámetros de nómina distintos de 2026 se bloquean hasta cargarlos y
  verificarlos.
