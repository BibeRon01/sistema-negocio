# Acceso empresarial sin correo personal

## Modelo final

- La pantalla muestra únicamente `Usuario o correo electrónico` y `Contraseña`.
- El superadministrador de plataforma A&M entra con correo, contraseña y MFA.
- El propietario de cada empresa recibe un acceso `empresa/usuario`, además de
  su contraseña y MFA.
- Cajeros y demás empleados entran con su acceso `empresa/usuario` y contraseña.
- Cada persona conserva una identidad individual en Supabase Auth.
- La aplicación no almacena ni compara contraseñas.

## Orden de publicación

1. Ejecute `supabase/migrations/202608150002_company_username_auth.sql` en
   Supabase SQL Editor. Debe terminar correctamente y no informar usuarios
   duplicados.
2. Despliegue las Edge Functions actualizadas `invite-user` y `manage-user`.
3. Publique los archivos Python y de documentación incluidos en este cambio.
4. Espere el reinicio de Streamlit y pruebe primero con la empresa BIBE RON.

## Separar A&M de BIBE RON

La cuenta con correo de quien administra toda la plataforma debe conservarse
como identidad central A&M; no debe convertirse en el usuario de BIBE RON.
Promueva esa identidad existente con el modo `--existing-user-id` descrito en
`GUIA_PUBLICACION.md`. La operación conserva contraseña, UUID y MFA.

Después:

1. A&M entra usando su correo, contraseña y MFA.
2. Desde **Gestión de Empresas**, A&M crea para BIBE RON una cuenta separada,
   por ejemplo `propietario`, con rol `admin`.
3. El propietario de BIBE RON entra con:
   - usuario: `biberon01/propietario`;
   - la contraseña empresarial asignada;
   - MFA.

La cuenta central A&M nunca debe convertirse en un usuario empresarial.

## Crear la cajera

Dentro de BIBE RON, abra **Usuarios → Crear usuario** y use, por ejemplo:

- usuario: `cajera01`;
- rol: `cajera`;
- contraseña inicial: mínimo 12 caracteres, entregada por un canal seguro;
- permisos: vender, abrir caja y ver sus propias ventas;
- cierre de caja: actívelo solo si la política del negocio lo permite.

La cajera entrará con `biberon01/cajera01 + contraseña`. No podrá entrar en
otra empresa porque Supabase Auth, `api_my_session` y RLS validan la membresía.

## Recuperación de acceso

- A&M recupera su cuenta por correo; el enlace con `token_hash` se valida en la
  propia aplicación y permite fijar una contraseña nueva.
- El administrador de una empresa restablece la contraseña de sus empleados
  desde **Usuarios**.
- A&M restablece la contraseña del propietario si este pierde el acceso.
- No existe contraseña maestra ni recuperación local.
