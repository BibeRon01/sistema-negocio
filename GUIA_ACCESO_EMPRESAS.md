# Acceso empresarial sin correo personal

## Modelo final

- El superadministrador de plataforma A&M entra con correo, contraseña y MFA.
- El propietario de cada empresa entra con empresa, usuario, contraseña y MFA.
- Cajeros y demás empleados entran con empresa, usuario y contraseña.
- Cada persona conserva una identidad individual en Supabase Auth.
- La aplicación no almacena ni compara contraseñas.

## Orden de publicación

1. Ejecute `supabase/migrations/202608150002_company_username_auth.sql` en
   Supabase SQL Editor. Debe terminar correctamente y no informar usuarios
   duplicados.
2. Despliegue las Edge Functions actualizadas `invite-user` y `manage-user`.
3. Publique los archivos Python y de documentación incluidos en este cambio.
4. Espere el reinicio de Streamlit y pruebe primero con la empresa BIBE RON.

## Convertir la cuenta existente de BIBE RON

La compatibilidad temporal impide bloquear la cuenta que actualmente usa
correo:

1. Seleccione **Empresa** en el inicio de sesión.
2. Escriba `biberon01` como empresa.
3. En **Usuario**, escriba temporalmente el correo actual de esa cuenta.
4. Ingrese la contraseña y confirme MFA.
5. Abra **Administración y Nómina → Usuarios**.
6. Seleccione la cuenta propietaria y cambie **Usuario de acceso** a
   `propietario`.
7. Guarde, cierre sesión y vuelva a entrar con:
   - empresa: `biberon01`;
   - usuario: `propietario`;
   - su misma contraseña;
   - MFA.

Al guardar el usuario, `manage-user` sustituye el correo de autenticación por
una identidad técnica privada. El correo anterior deja de iniciar sesión, pero
el UUID, el historial y los factores MFA de la cuenta se conservan.

## Crear la cajera

Dentro de BIBE RON, abra **Usuarios → Crear usuario** y use, por ejemplo:

- usuario: `cajera01`;
- rol: `cajera`;
- contraseña inicial: mínimo 12 caracteres, entregada por un canal seguro;
- permisos: vender, abrir caja y ver sus propias ventas;
- cierre de caja: actívelo solo si la política del negocio lo permite.

La cajera entrará con `biberon01 + cajera01 + contraseña`. No podrá entrar en
otra empresa porque Supabase Auth, `api_my_session` y RLS validan la membresía.

## Recuperación de acceso

- A&M recupera su cuenta por correo.
- El administrador de una empresa restablece la contraseña de sus empleados
  desde **Usuarios**.
- A&M restablece la contraseña del propietario si este pierde el acceso.
- No existe contraseña maestra ni recuperación local.
