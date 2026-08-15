# Sistema de negocio A&M — edición segura v3

Esta carpeta es la reconstrucción del sistema existente. Conserva su interfaz y
sus módulos principales, pero mueve las operaciones críticas a una API
transaccional dentro de PostgreSQL/Supabase.

> Estado: código preparado para publicación controlada en **staging**. No debe
> conectarse primero a producción. La aprobación final requiere aplicar el SQL,
> ejecutar las pruebas RLS con dos empresas y completar un simulacro de
> respaldo/restauración en un proyecto staging.

## Cambios principales

- acceso únicamente con Supabase Auth;
- validación obligatoria de cada sesión mediante Supabase Auth y
  `api_my_session`, cerrándola ante cualquier error;
- MFA nativo de Supabase con nivel `aal2` obligatorio para administradores,
  superadministradores y cuentas con permisos de alto riesgo;
- cliente Supabase aislado por sesión de Streamlit;
- separación por empresa y permisos de lectura por módulo mediante RLS;
- service-role únicamente en Edge Functions y scripts locales;
- ventas, cuentas abiertas, anulaciones, abonos, caja, compras y nómina mediante
  funciones transaccionales;
- factura de compra completa atómica e idempotente: cabecera, productos, lotes,
  stock, cuentas por pagar, contabilidad y auditoría se confirman o revierten
  juntos;
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

Para desarrollo y auditoría instale también `requirements-dev.txt` y ejecute
`pytest -q`.

## SQL de Supabase

Use únicamente `SQL_APLICAR_EN_SUPABASE.md`. Contiene estos bloques, que deben
ejecutarse completos y por separado en el orden indicado:

0. preflight de solo lectura;
1. base segura, Supabase Auth, tenants, RLS y tablas;
2. API transaccional de ventas, caja, créditos e inventario;
3. mantenimiento, contabilidad, nómina y factura de compra atómica;
4. verificación posterior de solo lectura.

`SQL_PARA_PEGAR.md` es histórico y está obsoleto: no lo ejecute. Los archivos de
`supabase/migrations/` y `supabase/checks/` se conservan como fuentes trazables
del archivo consolidado, no como una segunda guía de ejecución.

Consulte `GUIA_PUBLICACION.md` antes de aplicar cualquier bloque.
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
