# SQL que debe pegar

No existe una sola línea suelta que corrija el sistema completo. Los tres
archivos siguientes forman una migración ordenada y deben pegarse **completos**:

1. `supabase/migrations/202607250001_secure_foundation.sql`
2. `supabase/migrations/202607250002_transactional_api.sql`
3. `supabase/migrations/202607250003_maintenance_and_accounting_api.sql`

Antes:

- use un proyecto staging;
- ejecute `supabase/checks/001_preflight_readonly.sql`;
- tenga un respaldo real;
- confirme que staging y producción tienen URL distintas.

Después:

- ejecute `supabase/checks/002_postdeploy_readonly.sql`;
- publique las tres Edge Functions;
- ejecute las pruebas RLS con dos empresas;
- no declare producción aprobada mientras existan pruebas omitidas.

`central_am_schema.sql` y la carpeta `migrations/` solo se conservan como
referencias de compatibilidad; no son la fuente autorizada.

