# Migración privada de BIBE RON 01

Este paquete carga la operación histórica hasta el **15 de agosto de 2026** y está bloqueado al tenant `biberon01`.

## Archivos públicos que sí van a GitHub

- `migracion_biberon_view.py`
- `modules/migracion_biberon_view.py`
- `supabase/migrations/202608150001_importacion_historica_biberon01.sql`
- Las modificaciones de `app.py`, `api_client.py`, `db.py`, `inventario_view.py` y `tests/test_core_logic.py` incluidas en el parche.

El SQL contiene únicamente estructura y funciones. No contiene ventas, clientes, inventario ni credenciales.

## Archivo privado que nunca va a GitHub

`PAQUETE_MIGRACION_BIBERON01_HASTA_2026-08-15.xlsx`

Este libro contiene información real del negocio. Guárdelo fuera del repositorio y súbalo solamente desde la pantalla privada **Migración Bibe Ron** de Streamlit.

## Orden de ejecución

1. Haga un respaldo de Supabase.
2. Suba a GitHub el código del parche y espere que Streamlit termine de desplegar.
3. En Supabase SQL Editor ejecute completo `202608150001_importacion_historica_biberon01.sql`.
4. Compruebe que el SQL terminó con `Success` y sin mensajes de error.
5. Inicie sesión en Streamlit como administrador de BIBE RON 01 y complete MFA.
6. Cierre cualquier caja abierta y evite ventas durante la carga.
7. Abra **Administración y Nómina → Migración Bibe Ron**.
8. Seleccione el libro privado y confirme la importación.
9. Espere el mensaje de conciliación final. Puede reintentar si se corta la conexión: las filas ya confirmadas no se duplican.

## Resultado esperado

- La pantalla informa y concilia la última factura histórica y la siguiente disponible, calculadas desde el libro privado.
- El stock final proviene del reporte actual de productos.
- Las ventas, compras, gastos, nómina y pérdidas históricas no vuelven a mover la caja ni el inventario actual.
- Ninguna fila se carga en otra empresa.

No importe ventas nuevas hasta que la pantalla muestre la conciliación completa. El archivo adicional del mismo día debe prepararse como un paquete incremental empezando en la factura histórica siguiente indicada por el sistema, sin repetir las ya cargadas.
