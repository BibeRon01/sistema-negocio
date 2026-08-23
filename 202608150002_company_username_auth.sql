-- AIS: usuarios empresariales sin correo personal visible.
-- La contraseña permanece exclusivamente en Supabase Auth.

begin;

lock table public.usuarios in share row exclusive mode;

do $$
begin
    if exists (
        select 1
        from public.usuarios
        where empresa_id is not null
          and usuario is not null
          and btrim(usuario) <> ''
        group by empresa_id, lower(btrim(usuario))
        having count(*) > 1
    ) then
        raise exception 'DUPLICATE_TENANT_USERNAME_REQUIRES_REVIEW';
    end if;
end;
$$;

create unique index if not exists uq_usuarios_empresa_usuario_ci
    on public.usuarios (empresa_id, lower(btrim(usuario)))
    where empresa_id is not null
      and usuario is not null
      and btrim(usuario) <> '';

comment on column public.usuarios.usuario is
    'Usuario visible dentro de una empresa; no contiene ni valida contraseñas.';
comment on column public.usuarios.email_login is
    'Identificador técnico privado de Supabase Auth; no debe mostrarse al usuario empresarial.';

revoke insert, update, delete on public.usuarios from anon, authenticated;
revoke select on public.usuarios from anon;

-- Debe devolver cero filas antes de confirmar la migración.
select empresa_id, lower(btrim(usuario)) as usuario_normalizado, count(*) as cantidad
from public.usuarios
where empresa_id is not null
  and usuario is not null
  and btrim(usuario) <> ''
group by empresa_id, lower(btrim(usuario))
having count(*) > 1;

commit;
