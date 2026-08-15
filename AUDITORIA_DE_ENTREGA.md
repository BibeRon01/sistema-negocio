# Auditoría de entrega — A&M v3 segura

Fecha de revisión local: 8 de agosto de 2026.

## Dictamen

El proyecto definitivo incorpora controles estructurales para los hallazgos
críticos de autenticación, aislamiento multiempresa, privilegios, integridad del
POS, auditoría, respaldo, caja, crédito, compras, nómina y alcance DGII. El
código está preparado para su publicación controlada en staging.

No se emite una certificación de producción. En esta revisión no se proporcionó
acceso a un proyecto staging ni dos tokens de empresas diferentes, por lo que las
pruebas RLS vivas y el simulacro de restauración siguen siendo puertas
obligatorias.

## Evidencia local

- `helpers.py` fue restaurado primero desde la copia segura indicada: se
  verificaron sus 5,594 líneas, el SHA-256 suministrado, su compilación y sus
  importaciones antes de continuar con correcciones pequeñas;
- 48 archivos Python analizados sin errores de sintaxis;
- 33 pruebas locales de lógica, seguridad y controles estáticos aprobadas;
- 4 pruebas RLS omitidas de forma explícita porque requieren dos cuentas y
  tokens reales de un proyecto staging;
- dependencias instaladas desde cero con Python 3.12 sin conflictos;
- `pip-audit` sin vulnerabilidades conocidas en dependencias de ejecución ni de
  desarrollo;
- `ruff check` aprobado y Bandit sin hallazgos de severidad media o alta;
- escaneo de secretos sin candidatos en los archivos publicables;
- los cinco bloques de `SQL_APLICAR_EN_SUPABASE.md` coinciden exactamente con
  sus fuentes y pasan el parser PostgreSQL;
- `app.py` ejecutado mediante AppTest sin excepciones y servidor Streamlit con
  endpoint de salud correcto;
- pruebas RLS preparadas en modo solo lectura;
- las pruebas RLS se omiten si no existen credenciales staging, para no fabricar
  resultados;
- no se modificó Supabase, no se publicó, no se hizo commit ni push.

## Controles implementados

1. Supabase Auth como única entrada y revalidación obligatoria con
   `api_my_session` en cada ejecución de Streamlit.
2. MFA nativo AAL2 para administradores, superadministradores y permisos de alto
   riesgo, aplicado también en las funciones SQL canónicas de autorización.
3. Eliminación de claves maestras y acceso alternativo.
4. Cliente Supabase aislado por sesión.
5. RLS canónico basado en `auth.uid()` y membresías activas.
6. Superadministrador derivado solo de `app_metadata`.
7. Empresas suspendidas bloqueadas para usuarios normales.
8. Service-role fuera de Streamlit.
9. Alta y mantenimiento de usuarios mediante Edge Functions protegidas.
10. Ventas recalculadas y numeradas por el servidor.
11. Pagos conciliados contra el total calculado.
12. Inventario FIFO bloqueado durante la venta.
13. Cuentas abiertas reemplazadas o cobradas atómicamente.
14. Anulación sin borrado, con restauración de inventario y reverso contable.
15. Abonos FIFO con bloqueo y límite de saldo.
16. Apertura y cierre de caja transaccionales.
17. Factura de compra completa con idempotencia: cabecera, todas las líneas,
    compras históricas, stock, lotes, cuentas por pagar, asiento y auditoría en
    una sola transacción con rollback total.
18. Períodos cerrados protegidos por trigger.
19. Cierre permitido solo con libro balanceado e inventario no negativo.
20. Nómina basada en salario mensual y parámetros versionados.
21. ARL configurable; no se presenta 1.10% como universal.
22. Auditoría persistente y append-only.
23. Datos sensibles retirados de metadatos de auditoría.
24. Respaldo cifrado completo y restauración staging no destructiva.
25. DGII/e-CF limitado a educación, sin formularios ni emisión simulada.
26. Recibos identificados siempre como internos y sin valor fiscal.
27. Secuencias NCF y notas de crédito fiscales retiradas de los flujos.
28. Despliegue GitHub con staging predeterminado y confirmación reforzada para
    producción.
29. Permisos de lectura por módulo aplicados también en RLS, no solo en el menú.
30. Protección concurrente para conservar al menos una administración activa
    por empresa.
31. Selector multiempresa construido solo con tenants devueltos por
    `api_my_session`; el cliente sobrescribe cualquier `tenant_id` manipulable.
32. Escape de datos dinámicos en HTML, recibos y cuadre de caja.
33. Excepciones completas limitadas al registro interno; la interfaz muestra
    mensajes controlados.
34. Dependencias vulnerables actualizadas y verificadas en un entorno limpio.

## Funciones desactivadas deliberadamente

- edición o eliminación directa de ventas completadas;
- edición o eliminación directa de compras;
- división y fusión de cuentas;
- cobro individual de participantes;
- corrección manual de cuentas por cobrar;
- generación, firma o envío de documentos DGII/e-CF.

Estas funciones solo deben regresar cuando dispongan de una API transaccional,
pruebas de concurrencia, auditoría y autorización explícita.

## Pendientes para aprobación real

1. Ejecutar en staging los bloques 0 a 4 de
   `SQL_APLICAR_EN_SUPABASE.md`, en orden, y no usar el SQL obsoleto.
2. Resolver filas históricas sin `empresa_id`.
3. Ejecutar el chequeo posterior sin errores.
4. Desplegar y probar las Edge Functions.
5. Ejecutar RLS con Empresa A y Empresa B.
6. Probar concurrencia de dos ventas del mismo producto.
7. Conciliar caja, inventario y libro mayor con datos de prueba.
8. Restaurar un respaldo cifrado en staging vacío.
9. Revisión contable profesional de los resultados de nómina.
10. Autorizar por escrito el despliegue de producción.
11. Probar con una cuenta de permisos mínimos que nómina, auditoría, créditos y
    reportes financieros permanezcan ocultos.
