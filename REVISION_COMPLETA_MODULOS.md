# Revisión completa de módulos — A&M v3.0.5-secure

Fecha de revisión: 16 de septiembre de 2026.

## Alcance y evidencia

La revisión se hizo primero contra el diagnóstico SQL de solo lectura ejecutado
en la base real y después contra el código Python, las migraciones, las Edge
Functions y las pruebas automatizadas. No se modificaron datos de producción.

Resultados locales finales:

- 60 pruebas superadas;
- 4 pruebas RLS omitidas porque requieren credenciales de staging;
- todos los módulos Python compilan;
- Ruff no encontró errores;
- `pip check` no encontró dependencias rotas;
- todas las migraciones tienen delimitadores SQL balanceados y terminan en
  `commit;`.

## Hallazgos confirmados en la base real

1. `cierre_caja.caja_id`, `cierre_caja.usuario_id`,
   `movimientos_caja.caja_id` y `ventas_pagos.caja_id` estaban como texto,
   aunque las operaciones actuales usan UUID.
2. `cierre_caja.id` es una identidad BIGINT administrada por PostgreSQL aunque
   `column_default` aparezca vacío; faltaba `cierre_caja.monto_inicial`.
3. Faltaba `inventario_lotes.created_at`, pero la venta FIFO intentaba ordenar
   por esa columna.
4. La venta no comprobaba que la caja abierta perteneciera a la cajera actual.
5. El reemplazo de una cuenta abierta exigía MFA y reutilizaba la caja antigua
   en lugar de la caja actual de quien estaba cobrando.
6. El cobro de abonos guardaba `current_date::text` en una columna `date` y no
   comprobaba el dueño de la caja.
7. Existían siete membresías cuyo usuario ya no estaba en Supabase Auth.
8. Existe un producto con existencia negativa. Ese dato no se corrige
   automáticamente: debe compararse con un conteo físico.
9. La empresa `amcontable` estaba activa sin licencia vigente. BIBE RON y
   `demo01` sí tenían licencia.

## Correcciones incluidas

- Compatibilidad no destructiva del esquema de caja y cierres.
- Conversión validada de identificadores de caja a UUID. Si encuentra un valor
  legado inválido, la transacción se detiene sin dejar cambios parciales.
- Respeto de la secuencia `IDENTITY` existente de `cierre_caja`; solo se crea
  un valor automático si una instalación antigua realmente no tiene ninguno.
- Limpieza únicamente de membresías realmente huérfanas.
- Venta, inventario FIFO, pagos, movimientos de caja y contabilidad dentro de
  una sola transacción.
- Validación de que cada cajera use su propia caja abierta.
- Precio, stock y costo compatibles con las columnas legadas duplicadas.
- Descuento global recalculado por el servidor.
- Precios del catálogo tratados como precios finales; el servidor desglosa el
  ITBIS sin aumentar el total cobrado.
- Edición y cobro de cuentas abiertas sin exigir MFA a cajeros, pero respetando
  permisos y caja actual.
- Cierre de caja con totales por método y restricción para no cerrar la caja de
  otra persona sin permiso administrativo.
- Abonos de crédito con fecha correcta y caja del usuario actual.

## Estado por área

| Área | Estado de código | Validación pendiente |
| --- | --- | --- |
| Acceso, sesión y MFA | Pruebas aprobadas | Probar en navegador real y staging |
| Empresas y separación de datos | Estructura/RLS aprobadas | Ejecutar pruebas RLS con dos usuarios reales |
| Usuarios y eliminación | Pruebas aprobadas | Probar alta, desactivación y eliminación en staging |
| Productos e inventario | Reparación incluida | Corregir manualmente el único stock negativo después de contar |
| Caja | Reparación incluida | Aplicar SQL y abrir/cerrar una caja demo |
| POS y Cobrar | Reparación incluida | Venta demo en efectivo, tarjeta, transferencia y crédito |
| Cuentas abiertas | Reparación incluida | Abrir, editar y cobrar una cuenta demo |
| Créditos y abonos | Reparación incluida | Registrar un abono demo y comprobar saldo/caja |
| Compras y lotes FIFO | Pruebas estructurales aprobadas | Factura demo con dos productos |
| Gastos | Compila y respeta permisos | Registrar un gasto demo |
| Nómina | Pruebas de cálculo aprobadas | Nómina demo con tasa ARL configurada |
| Contabilidad | Pruebas estructurales aprobadas | Conciliar débitos y créditos tras pruebas demo |
| Auditoría | Compatibilidad incluida | Confirmar eventos generados en staging |
| Exportación Excel | Prueba aprobada | Descargar desde la aplicación publicada |

## Aplicación en la base existente

Ejecutar únicamente, en este orden:

1. `supabase/migrations/202609050002_pos_cash_open_account_repair.sql`;
2. `supabase/checks/004_pos_cash_repair_readonly.sql`.

No volver a ejecutar toda la instalación sobre producción. El primer archivo es
transaccional: ante cualquier error, PostgreSQL revierte el bloque completo.

## Resultados que deben revisarse después

- `membresias_sin_auth` debe quedar en `0`;
- no deben aparecer cajas abiertas duplicadas;
- las cinco comprobaciones de funciones deben mostrar `true`;
- la lista de empresas sin licencia indicará si todavía falta registrar la
  cortesía de `amcontable`;
- la consulta de stock negativo mostrará el producto que requiere conteo físico.

## Prueba funcional segura

Usar exclusivamente `demo01` hasta completar la validación:

1. entrar como administrador demo y crear un producto de prueba;
2. entrar como cajera demo y abrir caja con un fondo pequeño;
3. vender en efectivo y comprobar venta, pago, movimiento y stock;
4. crear una cuenta abierta, editarla y cobrarla;
5. hacer una venta a crédito y registrar un abono;
6. cerrar caja y comparar efectivo esperado, contado y diferencia;
7. confirmar que BIBE RON no muestra ninguno de esos datos;
8. ejecutar la verificación general y las pruebas RLS antes de usar producción.
