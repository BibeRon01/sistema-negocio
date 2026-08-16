# Migraciones reemplazadas

Las migraciones antiguas fueron retiradas porque eliminaban políticas RLS,
dependían de un esquema incompleto y no podían aplicarse de forma reproducible.

La fuente SQL trazable está en:

`supabase/migrations/`

Para aplicar el sistema no use estos archivos por separado: abra
`SQL_APLICAR_EN_SUPABASE.md` en la raíz del proyecto y ejecute sus cinco bloques
en orden, únicamente en staging antes de producción. Ese documento incorpora
también los chequeos previo y posterior. `SQL_PARA_PEGAR.md` está obsoleto.
