-- Chequeo posterior de solo lectura. No sustituye las pruebas RLS con usuarios.
select
    c.relname as tabla,
    c.relrowsecurity as rls_activo
from pg_class c
join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public'
  and c.relkind='r'
  and c.relname in (
      'empresas','tenant_memberships','usuarios','productos','clientes',
      'ventas','detalle_venta','ventas_pagos','caja','movimientos_caja',
      'cuentas_por_cobrar','abonos_credito','compras','facturas_compra',
      'detalle_factura_compra','gastos',
      'movimientos_contables','periodos_contables','auditoria_eventos',
      'proveedores','empleados','pagos_empleados','perdidas','gastos_dueno',
      'activos_fijos','capital_base','ajustes_inventario','conteo_inventario',
      'inventario_actual','inventario_lotes','inventario_consumos','sucursales',
      'configuracion_sistema','cierre_caja','abonos_proveedores',
      'adelantos_empleados','catalogo_gastos','configuracion_financiera',
      'cuentas_dinero','depreciacion','depreciaciones',
      'distribucion_beneficios','movimientos','movimientos_dinero',
      'notas_credito','pagos_proveedores','suscripciones_empresas',
      'nomina_parametros','system_test_runs'
  )
order by c.relname;

select
    p.proname as funcion,
    p.prosecdef as security_definer
from pg_proc p
join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public'
  and p.proname like 'api_%'
order by p.proname;

-- Debe quedar vacío: funciones SECURITY DEFINER legadas ejecutables por la
-- aplicación. Las tres funciones de autorización canónicas son la excepción.
select
    p.oid::regprocedure::text as funcion_legada_expuesta
from pg_proc p
join pg_namespace n on n.oid=p.pronamespace
where n.nspname='public'
  and p.prosecdef
  and p.proname not like 'api_%'
  and p.proname not in (
      'is_platform_superadmin','has_tenant_access','has_tenant_permission',
      'enforce_open_period'
  )
  and has_function_privilege('authenticated',p.oid,'EXECUTE');

select table_name, privilege_type
from information_schema.role_table_grants
where table_schema='public'
  and grantee='anon'
order by table_name, privilege_type;

-- Este resultado debe quedar vacío.
select table_name, privilege_type
from information_schema.role_table_grants
where table_schema='public'
  and grantee='authenticated'
  and privilege_type in ('INSERT','UPDATE','DELETE')
  and table_name in (
      'ventas','detalle_venta','ventas_pagos','compras','facturas_compra',
      'detalle_factura_compra','caja',
      'movimientos_caja','cuentas_por_cobrar','abonos_credito',
      'inventario_consumos','movimientos_contables','cierre_caja',
      'periodos_contables','pagos_empleados','usuarios','tenant_memberships',
      'auditoria_eventos','suscripciones_empresas'
  )
order by table_name,privilege_type;

select schemaname,tablename,policyname,cmd,roles,qual,with_check
from pg_policies
where schemaname='public'
order by tablename,policyname;

-- No debe aparecer una política permisiva universal.
select schemaname,tablename,policyname,cmd,qual,with_check
from pg_policies
where schemaname='public'
  and (
      regexp_replace(lower(coalesce(qual,'')),'\s','','g') in ('true','(true)')
      or regexp_replace(lower(coalesce(with_check,'')),'\s','','g') in ('true','(true)')
  );

select
    count(*) filter (where user_id is null) as perfiles_sin_auth,
    count(*) filter (where empresa_id is null or trim(empresa_id)='') as perfiles_sin_empresa
from public.usuarios;

select empresa_id,usuario_id,count(*) as cajas_abiertas
from public.caja
where lower(coalesce(estado,''))='abierta'
group by empresa_id,usuario_id
having count(*)>1;

select
       empresa_id,
       extract(year from fecha)::integer as ano,
       extract(month from fecha)::integer as mes,
       round(coalesce(sum(debito),0),2) as debitos,
       round(coalesce(sum(credito),0),2) as creditos
from public.movimientos_contables
group by
       empresa_id,
       extract(year from fecha)::integer,
       extract(month from fecha)::integer
having abs(round(coalesce(sum(debito),0),2)-round(coalesce(sum(credito),0),2))>0.01;
