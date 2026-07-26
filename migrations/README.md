# Migraciones reemplazadas

Las migraciones antiguas fueron retiradas porque eliminaban políticas RLS,
dependían de un esquema incompleto y no podían aplicarse de forma reproducible.

La única fuente autorizada está en:

`supabase/migrations/`

Ejecute esos archivos en orden y únicamente en staging antes de producción.
