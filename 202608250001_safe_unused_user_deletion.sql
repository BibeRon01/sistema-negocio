-- AIS: eliminación permanente únicamente de usuarios inactivos sin historial.

begin;

create or replace function public.api_prepare_delete_unused_user(
    p_profile_id uuid,
    p_tenant_id text
)
returns jsonb
language plpgsql
security definer
set search_path = public, auth, pg_catalog
as $$
declare
    v_actor uuid := auth.uid();
    v_target_user_id uuid;
    v_username text;
    v_profile_active boolean;
    v_membership_active boolean;
    v_table record;
    v_has_history boolean;
begin
    if v_actor is null then
        raise exception 'AUTH_REQUIRED';
    end if;
    if coalesce(auth.jwt() ->> 'aal', 'aal1') <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    if nullif(btrim(coalesce(p_tenant_id, '')), '') is null
       or p_tenant_id = 'global' then
        raise exception 'INVALID_USER_DATA';
    end if;

    if not public.is_platform_superadmin() and not exists (
        select 1
        from public.tenant_memberships tm
        where tm.user_id = v_actor
          and tm.tenant_id = p_tenant_id
          and tm.role = 'admin'
          and tm.active
    ) then
        raise exception 'USER_MANAGEMENT_PERMISSION_DENIED';
    end if;

    select u.user_id, u.usuario, coalesce(u.activo, true), coalesce(tm.active, true)
      into v_target_user_id, v_username, v_profile_active, v_membership_active
    from public.usuarios u
    join public.tenant_memberships tm
      on tm.user_id = u.user_id
     and tm.tenant_id = u.empresa_id
    where u.id = p_profile_id
      and u.empresa_id = p_tenant_id
    for update of u, tm;

    if not found or v_target_user_id is null then
        raise exception 'USER_NOT_FOUND';
    end if;
    if v_target_user_id = v_actor then
        raise exception 'CANNOT_DELETE_SELF';
    end if;
    if v_profile_active or v_membership_active then
        return jsonb_build_object(
            'success', false,
            'error', 'USER_MUST_BE_INACTIVE'
        );
    end if;
    if exists (
        select 1
        from auth.users au
        where au.id = v_target_user_id
          and coalesce(au.raw_app_meta_data ->> 'role', '') = 'superadmin'
    ) then
        raise exception 'PLATFORM_SUPERADMIN_PROTECTED';
    end if;

    -- Descubre todas las tablas físicas actuales y futuras que registren el
    -- UUID del responsable. No depende de una lista manual que pueda quedar
    -- obsoleta cuando se agreguen módulos contables.
    for v_table in
        select
            n.nspname as schema_name,
            c.relname as table_name,
            exists (
                select 1
                from pg_attribute tenant_column
                where tenant_column.attrelid = c.oid
                  and tenant_column.attname = 'empresa_id'
                  and tenant_column.attnum > 0
                  and not tenant_column.attisdropped
            ) as has_tenant_column
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public'
          and c.relkind in ('r', 'p')
          and c.relname not in ('usuarios', 'tenant_memberships')
          and exists (
              select 1
              from pg_attribute user_column
              where user_column.attrelid = c.oid
                and user_column.attname = 'usuario_id'
                and user_column.attnum > 0
                and not user_column.attisdropped
          )
        order by c.relname
    loop
        if v_table.has_tenant_column then
            execute format(
                'select exists (select 1 from %I.%I where usuario_id::text = $1 and empresa_id::text = $2)',
                v_table.schema_name,
                v_table.table_name
            )
            into v_has_history
            using v_target_user_id::text, p_tenant_id;
        else
            execute format(
                'select exists (select 1 from %I.%I where usuario_id::text = $1)',
                v_table.schema_name,
                v_table.table_name
            )
            into v_has_history
            using v_target_user_id::text;
        end if;

        if v_has_history then
            return jsonb_build_object(
                'success', false,
                'error', 'USER_HAS_OPERATIONAL_HISTORY',
                'source', v_table.table_name
            );
        end if;
    end loop;

    return jsonb_build_object(
        'success', true,
        'user_id', v_target_user_id,
        'username', v_username
    );
end;
$$;

revoke all on function public.api_prepare_delete_unused_user(uuid, text)
    from public, anon;
grant execute on function public.api_prepare_delete_unused_user(uuid, text)
    to authenticated;

commit;
