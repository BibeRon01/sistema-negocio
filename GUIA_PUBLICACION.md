# Guía sencilla para GitHub, Supabase y Streamlit

## 1. Subir el código

1. Cree un repositorio **privado** en GitHub.
2. Suba el contenido completo de esta carpeta, no la carpeta original.
3. Confirme que GitHub no muestra `.env`, `secrets.toml`, respaldos, archivos
   `.p12`, `.pfx`, `.pem` o `.key`.
4. Espere el resultado del flujo **Validación**. No continúe si está rojo.

## 2. Preparar staging

1. Cree un proyecto Supabase separado para pruebas.
2. Nunca reutilice la URL de producción.
3. Abra `SQL_APLICAR_EN_SUPABASE.md` y ejecute únicamente su bloque 0
   (preflight de solo lectura).
4. Guarde un respaldo administrado de producción antes de migrar.
5. Si existen filas históricas con `empresa_id` vacío, clasifíquelas antes de
   permitir que usuarios trabajen con ellas.
6. Anote las cuentas históricas que aún no estén vinculadas a `auth.users`.
   La migración invalida claves y TOTP guardados en tablas legadas; esas personas
   deberán recibir una cuenta Supabase Auth o restablecer su contraseña.

## 3. Aplicar el SQL

En el editor SQL de **staging**, use exclusivamente
`SQL_APLICAR_EN_SUPABASE.md`. No ejecute `SQL_PARA_PEGAR.md`. Ejecute completos,
uno por uno y en este orden:

0. Preflight de solo lectura; revise sus resultados antes de continuar.
1. Base segura, Supabase Auth, tenants, RLS y tablas canónicas.
2. API transaccional de ventas, caja, créditos e inventario.
3. Mantenimiento, contabilidad, nómina y factura de compra atómica.
4. Usuario empresarial único por empresa.
5. Usuario único en toda la plataforma.
6. Validación para eliminar usuarios inactivos sin historial y limpiar de forma
   transaccional perfiles huérfanos heredados.
7. Verificación posterior de solo lectura.

Los bloques 1 al 6 usan transacciones. Si aparece un error, no continúe con el
siguiente: conserve el mensaje en un canal privado y corrija primero la causa.
El bloque 7 no reemplaza las pruebas RLS con usuarios reales.

## 4. Publicar las cuatro Edge Functions

Las funciones son:

- `invite-user`
- `manage-user`
- `manage-company`
- `resolve-login`

El flujo manual `Desplegar API Supabase` incluido en GitHub las publica. Su
selección predeterminada es `staging`. La opción `production` se detiene si no
se escribe la confirmación exacta solicitada y debe estar protegida por
aprobación en GitHub. Configure, por separado en cada ambiente protegido:

- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_PROJECT_REF`

Supabase entrega a sus Edge Functions las variables internas de URL, anon key y
service-role. La service-role no debe agregarse a Streamlit.

## 5. Crear el superadministrador A&M y las cuentas empresariales

Desde una computadora administrativa, nunca desde Streamlit, cree solamente la
cuenta de plataforma A&M con correo real:

```bash
export SUPABASE_URL="https://PROYECTO-STAGING.supabase.co"
export SUPABASE_SERVICE_KEY="PEGAR_SOLO_EN_LA_TERMINAL_LOCAL"  # pragma: allowlist secret
python scripts/provision_owner.py \
  --email "administrador@am.example" \
  --name "Administrador A&M" \
  --tenant "biberon01" \
  --platform-superadmin
```

El programa pedirá una contraseña de al menos 4 caracteres y un símbolo como
`.`, `@`, `!`, `_` o `-`. En la primera
entrada deberá registrar y verificar el MFA nativo de Supabase hasta alcanzar
`aal2`. Use `--platform-superadmin` únicamente para la cuenta A&M que administra
la plataforma.

Si el correo A&M ya existe en **Authentication → Users**, no cree otra cuenta.
Copie su UUID y promueva esa misma identidad con:

```bash
export SUPABASE_URL="https://PROYECTO.supabase.co"
export SUPABASE_SERVICE_KEY="PEGAR_SOLO_EN_LA_TERMINAL_LOCAL"  # pragma: allowlist secret
python scripts/provision_owner.py \
  --email "CORREO_A&M_EXISTENTE" \
  --name "Administrador A&M" \
  --tenant "EMPRESA_INICIAL" \
  --platform-superadmin \
  --existing-user-id "UUID_DE_AUTH_USERS"
```

Este modo conserva la contraseña, el UUID, el historial y los factores MFA de
la cuenta. La service-role se usa únicamente en la terminal local y no se sube
a GitHub ni se agrega a Streamlit.

Después, desde **Gestión de Empresas**, cree cada empresa y su primer usuario
administrador. Las cuentas empresariales entran únicamente con `usuario +
contraseña`; no necesitan correo personal ni seleccionan empresa. El alias debe
ser único en toda la plataforma. Cada administrador empresarial debe configurar
MFA. Los cajeros y demás empleados se crean desde **Usuarios** dentro de su
empresa.

Desde la pestaña **Licencias y pagos**, la superadministradora registra la
licencia inicial y cada renovación. Para pruebas puede elegir `Demostración`,
monto `RD$0.00`, método `Cortesía / sin cobro` y el vencimiento deseado. Estos
registros se guardan únicamente en `suscripciones_empresas`; no crean ventas,
movimientos de caja ni asientos dentro de la contabilidad del cliente.

### Recuperación de contraseña del correo A&M

En **Supabase → Authentication → URL Configuration**, configure **Site URL** con
la dirección pública de la aplicación Streamlit. Luego, en la plantilla de
correo **Reset Password**, use un enlace con `token_hash`:

```html
<a href="{{ .SiteURL }}?token_hash={{ .TokenHash }}&type=recovery">
  Crear una contraseña nueva
</a>
```

El enlace abrirá una pantalla de Streamlit que valida el token directamente con
Supabase y permite guardar una contraseña nueva de al menos 4 caracteres y un
símbolo. No
coloque access tokens ni contraseñas en la URL.

## 6. Configurar Streamlit

En los secretos de la aplicación coloque solamente:

```toml
SUPABASE_URL = "https://PROYECTO-STAGING.supabase.co"
SUPABASE_KEY = "LLAVE_PUBLICA_O_ANON"
SESSION_COOKIE_SECRET = "VALOR_PRIVADO_ALEATORIO_DE_32_O_MAS_CARACTERES"
```

Genere `SESSION_COOKIE_SECRET` una sola vez en su computadora con
`python -c "import secrets; print(secrets.token_urlsafe(48))"`, péguelo en
**Streamlit → Manage app → Settings → Secrets** y consérvelo sin cambios. No lo
suba a GitHub ni lo configure en Supabase. Este secreto cifra los tokens reales
de Supabase que permiten recuperar en el mismo navegador una sesión todavía
vigente; Auth y `api_my_session` siempre vuelven a validarla.

Seleccione `app.py` como archivo principal.

## 7. Pruebas obligatorias en staging

1. Cree Empresa A y Empresa B.
2. Intente crear el mismo usuario en ambas empresas y confirme que la segunda
   creación se rechaza con sugerencias; cree una alternativa y confirme que
   ninguna cuenta puede ver datos de la otra empresa.
3. Configure MFA de administradores y superadministradores y confirme `aal2`.
4. Configure productos, clientes, un empleado y su tasa ARL.
5. Abra caja, venda, cobre a crédito, abone, anule y cierre caja.
6. Registre una factura con varios productos y confirme cabecera, líneas, lotes
   FIFO, stock y asiento; repita la misma solicitud y confirme idempotencia.
7. Registre nómina y verifique que el asiento esté balanceado.
8. Compruebe que cada usuario solo ve su empresa.
9. Cree una cuenta de permisos mínimos y confirme que no puede leer nómina,
   auditoría, créditos ni reportes financieros.
10. Ejecute las pruebas RLS con las variables indicadas en `tests/test_rls.py`.
11. Cree un respaldo cifrado y restáurelo en otro staging vacío.
12. Fuerce un producto inválido dentro de una factura de prueba y confirme que
    no quedó cabecera, línea, compra, lote, stock ni asiento parcial.
13. Cree una cuenta sin operaciones, desactívela y elimínela definitivamente;
    confirme que el alias queda disponible. Repita con una cuenta que sí tenga
    historial y confirme que solo pueda permanecer desactivada.

## 8. Paso a producción

Repita el proceso solo después de conservar:

- resultado verde de GitHub;
- salida del chequeo posterior;
- evidencia RLS de las dos empresas;
- conciliación de ventas, caja, inventario y contabilidad;
- simulacro de restauración aprobado;
- autorización escrita de la propietaria.

No publique primero y pruebe después.
