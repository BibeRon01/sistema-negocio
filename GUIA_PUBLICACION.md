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
3. Ejecute `supabase/checks/001_preflight_readonly.sql`.
4. Guarde un respaldo administrado de producción antes de migrar.
5. Si existen filas históricas con `empresa_id` vacío, clasifíquelas antes de
   permitir que usuarios trabajen con ellas.
6. Anote las cuentas históricas que aún no estén vinculadas a `auth.users`.
   La migración invalida claves y TOTP guardados en tablas legadas; esas personas
   deberán recibir una cuenta Supabase Auth o restablecer su contraseña.

## 3. Aplicar el SQL

En el editor SQL de **staging**, abra y ejecute completos, uno por uno y en este
orden:

1. `supabase/migrations/202607250001_secure_foundation.sql`
2. `supabase/migrations/202607250002_transactional_api.sql`
3. `supabase/migrations/202607250003_maintenance_and_accounting_api.sql`

Cada archivo usa una transacción. Si aparece un error, no continúe con el
siguiente: copie el mensaje completo y corrija primero la causa.

Al terminar, ejecute `supabase/checks/002_postdeploy_readonly.sql`.

## 4. Publicar las tres Edge Functions

Las funciones son:

- `invite-user`
- `manage-user`
- `manage-company`

El flujo manual `Desplegar API Supabase` incluido en GitHub las publica. Su
selección predeterminada es `staging`. La opción `production` se detiene si no
se escribe la confirmación exacta solicitada y debe estar protegida por
aprobación en GitHub. Configure, por separado en cada ambiente protegido:

- `SUPABASE_ACCESS_TOKEN`
- `SUPABASE_DB_PASSWORD`
- `SUPABASE_PROJECT_REF`

Supabase entrega a sus Edge Functions las variables internas de URL, anon key y
service-role. La service-role no debe agregarse a Streamlit.

## 5. Crear la primera propietaria

Desde una computadora administrativa, nunca desde Streamlit:

```bash
export SUPABASE_URL="https://PROYECTO-STAGING.supabase.co"
export SUPABASE_SERVICE_KEY="PEGAR_SOLO_EN_LA_TERMINAL_LOCAL"
python scripts/provision_owner.py \
  --email "propietaria@empresa.com" \
  --name "Nombre de la propietaria" \
  --tenant "codigo_empresa"
```

El programa pedirá una contraseña de al menos 12 caracteres y obligará a
registrar MFA en la primera entrada. Use `--platform-superadmin` únicamente para
la cuenta que administrará varias empresas.

## 6. Configurar Streamlit

En los secretos de la aplicación coloque solamente:

```toml
SUPABASE_URL = "https://PROYECTO-STAGING.supabase.co"
SUPABASE_KEY = "LLAVE_PUBLICA_O_ANON"
```

Seleccione `app.py` como archivo principal.

## 7. Pruebas obligatorias en staging

1. Cree Empresa A y Empresa B.
2. Cree un usuario diferente en cada empresa.
3. Configure MFA de los administradores.
4. Configure productos, clientes, un empleado y su tasa ARL.
5. Abra caja, venda, cobre a crédito, abone, anule y cierre caja.
6. Registre una compra y confirme el lote FIFO.
7. Registre nómina y verifique que el asiento esté balanceado.
8. Compruebe que cada usuario solo ve su empresa.
9. Cree una cuenta de permisos mínimos y confirme que no puede leer nómina,
   auditoría, créditos ni reportes financieros.
10. Ejecute las pruebas RLS con las variables indicadas en `tests/test_rls.py`.
11. Cree un respaldo cifrado y restáurelo en otro staging vacío.

## 8. Paso a producción

Repita el proceso solo después de conservar:

- resultado verde de GitHub;
- salida del chequeo posterior;
- evidencia RLS de las dos empresas;
- conciliación de ventas, caja, inventario y contabilidad;
- simulacro de restauración aprobado;
- autorización escrita de la propietaria.

No publique primero y pruebe después.
