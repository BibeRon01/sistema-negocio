-- Verificación de solo lectura después de aplicar
-- 202609050002_pos_cash_open_account_repair.sql.

select
    c.table_name,
    c.column_name,
    c.udt_name,
    c.is_nullable,
    c.is_identity,
    c.identity_generation,
    coalesce(c.column_default,'SIN DEFAULT') as column_default
from information_schema.columns c
where c.table_schema='public'
  and (c.table_name,c.column_name) in (
      ('inventario_lotes','created_at'),
      ('cierre_caja','id'),
      ('cierre_caja','caja_id'),
      ('cierre_caja','usuario_id'),
      ('cierre_caja','monto_inicial'),
      ('movimientos_caja','caja_id'),
      ('ventas_pagos','caja_id')
  )
order by c.table_name,c.column_name;

select
    count(*) filter (
        where not exists (
            select 1 from auth.users au where au.id=tm.user_id
        )
    ) as membresias_sin_auth,
    count(*) filter (where not tm.active) as membresias_inactivas
from public.tenant_memberships tm;

select
    p.id,
    p.empresa_id,
    p.nombre,
    p.cantidad,
    p.stock,
    p.existencia
from public.productos p
where coalesce(p.cantidad,0)<0
   or coalesce(p.stock,0)<0
   or coalesce(p.existencia,0)<0
order by p.empresa_id,p.nombre;

select
    e.tenant_id,
    e.nombre
from public.empresas e
where e.activo
  and not exists (
      select 1
      from public.suscripciones_empresas s
      where s.empresa_id=e.tenant_id
        and current_date<=s.fecha_vencimiento+coalesce(s.dias_gracia,0)
  )
order by e.tenant_id;

select
    c.empresa_id,
    c.usuario_id,
    count(*) as cajas_abiertas
from public.caja c
where lower(coalesce(c.estado,''))='abierta'
group by c.empresa_id,c.usuario_id
having count(*)>1;

select
    p.oid::regprocedure::text as funcion,
    p.prosecdef as security_definer,
    has_function_privilege('authenticated',p.oid,'EXECUTE') as authenticated_execute,
    has_function_privilege('anon',p.oid,'EXECUTE') as anon_execute
from pg_proc p
join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public'
  and p.proname in (
      'api_registrar_venta',
      'api_registrar_abono',
      'api_reemplazar_cuenta_abierta',
      'api_abrir_caja',
      'api_cerrar_caja'
  )
order by p.proname;

select
    position('v_caja_owner is distinct from v_uid' in lower(pg_get_functiondef(
        'public.api_registrar_venta(jsonb)'::regprocedure
    )))>0 as venta_exige_caja_del_usuario,
    position('v_descuento_global' in pg_get_functiondef(
        'public.api_registrar_venta(jsonb)'::regprocedure
    ))>0 as venta_soporta_descuento_global,
    position('MFA_AAL2_REQUIRED' in pg_get_functiondef(
        'public.api_reemplazar_cuenta_abierta(text,jsonb)'::regprocedure
    ))=0 as cuenta_abierta_no_exige_mfa,
    position('c.usuario_id=v_uid' in pg_get_functiondef(
        'public.api_reemplazar_cuenta_abierta(text,jsonb)'::regprocedure
    ))>0 as cuenta_abierta_usa_caja_actual,
    position('v_caja_owner is distinct from v_uid' in pg_get_functiondef(
        'public.api_registrar_abono(bigint,bigint,numeric,text,text,text)'::regprocedure
    ))>0 as abono_exige_caja_del_usuario,
    position('current_date::text' in pg_get_functiondef(
        'public.api_registrar_abono(bigint,bigint,numeric,text,text,text)'::regprocedure
    ))=0 as abono_conserva_fecha_date;
