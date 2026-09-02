# Acceso empresarial sin correo personal

## Modelo final

- La pantalla muestra únicamente `Usuario o correo electrónico` y `Contraseña`.
- El superadministrador de plataforma A&M entra con correo, contraseña y MFA.
- El propietario de cada empresa recibe un usuario global único, su contraseña
  y MFA; no escribe ni selecciona la empresa al entrar.
- Cajeros y demás empleados entran solo con su usuario único y contraseña.
- Cada persona conserva una identidad individual en Supabase Auth.
- El sistema obtiene la empresa únicamente del perfil y la membresía autorizada;
  el usuario no puede elegir otro `tenant_id`.
- La aplicación no almacena ni compara contraseñas.
- Una sesión de empleado con actividad se revalida en cada ejecución y se
  cierra después de una hora completa sin interacción; cada acción reinicia
  ese contador.
- Una sesión administrativa que Supabase ya confirmó como `aal2` puede
  permanecer abierta hasta 24 horas en el mismo navegador. Al cumplir ese
  plazo se exige nuevamente el autenticador, aunque haya actividad.
- Durante esas 24 horas la aplicación sincroniza los access/refresh tokens que
  Supabase rota; crear, desactivar o eliminar usuarios no debe solicitar otro
  código mientras la misma sesión `aal2` continúe válida.
- Para sobrevivir una reconexión o reinicio de Streamlit, la pareja de tokens
  se conserva cifrada en el almacenamiento del mismo navegador durante el plazo
  permitido. Se usa un componente Streamlit v2 integrado en la página, sin el
  iframe que podía bloquear las cookies en la vista compartida. Requiere
  `SESSION_COOKIE_SECRET` en los secretos de Streamlit. El valor guardado nunca
  autoriza por sí solo: al recuperarlo se vuelven a consultar Supabase Auth y
  `api_my_session`, y los administradores deben seguir en `aal2`. Un rechazo
  real cierra y elimina la sesión; una demora, desconexión o HTTP 5xx bloquea
  temporalmente la aplicación y permite reintentar sin revocar el `aal2`.
- Un navegador, dispositivo o ventana privada nuevos no tienen esa sesión y
  deben completar contraseña y MFA. La aplicación no confía en IP, ubicación,
  huellas del dispositivo ni datos locales que sustituyan `aal2`.

## Orden de publicación

1. Ejecute los bloques 4, 5 y 6 de `SQL_APLICAR_EN_SUPABASE.md` en Supabase SQL
   Editor. Deben terminar correctamente y no informar usuarios duplicados.
2. Despliegue las Edge Functions `invite-user`, `manage-user` y `resolve-login`.
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
   - usuario: `propietario`;
   - la contraseña empresarial asignada;
   - MFA.

La cuenta central A&M nunca debe convertirse en un usuario empresarial.

## Crear la cajera

Dentro de BIBE RON, abra **Usuarios → Crear usuario** y use, por ejemplo:

- usuario: `cajera01`;
- rol: `cajera`;
- contraseña inicial: mínimo 4 caracteres y un símbolo como `.`, `@`, `!`, `_`
  o `-`, entregada por un canal seguro;
- permisos: vender, abrir caja y ver sus propias ventas;
- cierre de caja: actívelo solo si la política del negocio lo permite.

La cajera entrará con `cajera01 + contraseña`. No podrá entrar en otra empresa
porque Supabase Auth, `api_my_session` y RLS validan la membresía. Si `cajera01`
ya pertenece a cualquier empresa, la creación se rechaza y muestra alternativas
como `cajera02`, `cajera03` o `cajera04`.

Si el mensaje indica que el usuario **ya está creado en la misma empresa**, no
pruebe nombres sucesivos: abra **Usuarios → Lista de Usuarios**. Es posible que
un intento anterior terminara correctamente aunque la pantalla tardara en
mostrar la confirmación. Si desconoce la clave, asígnele una nueva desde
**Editar / Eliminar Usuario**. Las alternativas se usan solamente cuando el
nombre pertenece realmente a otra empresa de la plataforma.

## Eliminar cuentas creadas por error

1. Abra **Usuarios → Editar / Eliminar Usuario**.
2. Seleccione la cuenta equivocada y pulse **Desactivar Usuario**.
3. Selecciónela nuevamente, confirme la advertencia y pulse
   **Eliminar definitivamente y liberar usuario**.

La eliminación definitiva exige MFA `aal2` y solo funciona cuando Supabase
confirma que la cuenta no tiene ventas, cajas, compras, gastos, movimientos,
nómina, auditoría ni ninguna otra tabla con su `usuario_id`. Si existe historial,
la cuenta permanece desactivada para conservar la trazabilidad contable. Cuando
la eliminación termina correctamente se borran la identidad de Supabase Auth,
el perfil y la membresía; el alias global queda disponible para otra persona.
Si un intento antiguo ya borró Auth pero dejó el perfil visible, el bloque 6
también elimina ese perfil huérfano y su membresía en una sola transacción,
siempre después de confirmar que están inactivos y no tienen historial.
Repetir la eliminación de una cuenta que ya desapareció se considera un éxito
idempotente y no vuelve a mostrar un falso `HTTP_404`.

## Recuperación de acceso

- A&M recupera su cuenta por correo; el enlace con `token_hash` se valida en la
  propia aplicación y permite fijar una contraseña nueva.
- El administrador de una empresa restablece la contraseña de sus empleados
  desde **Usuarios**.
- A&M restablece la contraseña del propietario si este pierde el acceso.
- No existe contraseña maestra ni recuperación local.
