# Auditoría de entrega — A&M v3 segura

Fecha de revisión local: 25 de julio de 2026.

## Dictamen

La copia corregida incorpora controles estructurales para los hallazgos críticos
de autenticación, aislamiento multiempresa, privilegios, integridad del POS,
auditoría, respaldo, caja, crédito, compras, nómina y alcance DGII.

No se emite una certificación de producción. En esta revisión no se proporcionó
acceso a un proyecto staging ni dos tokens de empresas diferentes, por lo que las
pruebas RLS vivas y el simulacro de restauración siguen siendo puertas
obligatorias.

## Evidencia local

- todos los archivos Python parsean sin error;
- 48 archivos Python analizados sin errores de sintaxis;
- 20 pruebas locales de lógica y controles estáticos aprobadas;
- 4 pruebas RLS omitidas de forma explícita porque requieren dos cuentas y
  tokens reales de un proyecto staging;
- los 39 módulos de la aplicación cargan correctamente fuera de Streamlit;
- pruebas RLS preparadas en modo solo lectura;
- las pruebas RLS se omiten si no existen credenciales staging, para no fabricar
  resultados;
- no se copiaron respaldos, secretos, entornos virtuales ni historial Git;
- el sistema original del Escritorio no fue modificado.

## Controles implementados

1. Supabase Auth como única entrada.
2. MFA AAL2 para administradores.
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
17. Compras de producto con lote, stock y asiento en una transacción.
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

1. Ejecutar las tres migraciones en staging.
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
