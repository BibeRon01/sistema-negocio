-- AIS: alias empresarial único en toda la plataforma.
-- La empresa se resuelve internamente después de este alias; la contraseña
-- permanece exclusivamente bajo Supabase Auth.

begin;

lock table public.usuarios in share row exclusive mode;

do $$
begin
    if exists (
        select 1
        from public.usuarios
        where usuario is not null
          and btrim(usuario) <> ''
        group by lower(btrim(usuario))
        having count(*) > 1
    ) then
        raise exception 'DUPLICATE_GLOBAL_USERNAME_REQUIRES_REVIEW';
    end if;
end;
$$;

create unique index if not exists uq_usuarios_usuario_global_ci
    on public.usuarios (lower(btrim(usuario)))
    where usuario is not null
      and btrim(usuario) <> '';

comment on index public.uq_usuarios_usuario_global_ci is
    'Impide repetir el alias de acceso entre empresas; el nombre completo sí puede repetirse.';
comment on column public.usuarios.usuario is
    'Alias global de acceso empresarial; la empresa se obtiene de la membresía validada.';

revoke select on public.usuarios from anon;
revoke insert, update, delete on public.usuarios from anon, authenticated;

commit;
