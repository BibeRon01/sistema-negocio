-- A&M - Diagnostico integral de Supabase (solo lectura de datos permanentes)
-- Revisión posterior a Caja/Cobrar: 2026-09-17-r4
--
-- Este archivo NO crea, modifica ni elimina tablas o datos de la aplicacion.
-- Solo crea una tabla temporal en la sesion del editor SQL para reunir los
-- resultados. La tabla temporal desaparece automaticamente al cerrar la sesion.

set statement_timeout = '60s';

drop table if exists pg_temp.ais_diagnostico;
create temporary table ais_diagnostico (
    orden integer generated always as identity,
    area text not null,
    prueba text not null,
    estado text not null,
    detalle text not null
) on commit preserve rows;

-- -------------------------------------------------------------------------
-- 1. Inventario de tablas que usa la aplicacion
-- -------------------------------------------------------------------------
with requeridas(tabla) as (
    values
        ('empresas'),('tenant_memberships'),('usuarios'),
        ('configuracion_sistema'),('suscripciones_empresas'),
        ('productos'),('clientes'),('proveedores'),('compras'),
        ('facturas_compra'),('detalle_factura_compra'),('gastos'),
        ('empleados'),('pagos_empleados'),('perdidas'),
        ('ventas'),('detalle_venta'),('ventas_pagos'),
        ('caja'),('cierre_caja'),('movimientos_caja'),
        ('cuentas_por_cobrar'),('abonos_credito'),
        ('inventario_lotes'),('inventario_consumos'),
        ('movimientos_contables'),('periodos_contables'),
        ('auditoria_eventos'),('secuencia_documentos')
)
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '01_TABLAS',
    tabla,
    case when to_regclass('public.' || tabla) is null then 'ERROR' else 'OK' end,
    case when to_regclass('public.' || tabla) is null
         then 'Falta public.' || tabla
         else 'Existe public.' || tabla
    end
from requeridas;

-- -------------------------------------------------------------------------
-- 2. Contrato exacto de columnas usadas por Caja y Cobrar
-- -------------------------------------------------------------------------
with esperadas(tabla,columna,tipos_aceptados,obligatoria) as (
    values
        ('empresas','tenant_id','text',true),
        ('empresas','activo','bool,boolean',true),
        ('tenant_memberships','user_id','uuid',true),
        ('tenant_memberships','tenant_id','text',true),
        ('tenant_memberships','role','text',true),
        ('tenant_memberships','permissions','jsonb',true),
        ('tenant_memberships','active','bool,boolean',true),
        ('usuarios','user_id','uuid',true),
        ('usuarios','empresa_id','text',true),
        ('usuarios','usuario','text',true),
        ('usuarios','nombre','text',true),
        ('suscripciones_empresas','empresa_id','text',true),
        ('suscripciones_empresas','fecha_inicio','date',true),
        ('suscripciones_empresas','fecha_vencimiento','date',true),
        ('suscripciones_empresas','monto_pagado','numeric',true),
        ('suscripciones_empresas','periodo','text',true),
        ('suscripciones_empresas','metodo_pago','text',true),
        ('suscripciones_empresas','dias_gracia','int4,integer',true),
        ('caja','id','uuid',true),
        ('caja','empresa_id','text',true),
        ('caja','usuario_id','uuid',true),
        ('caja','usuario','text',true),
        ('caja','estado','text',true),
        ('caja','fecha_apertura','timestamp,timestamptz',true),
        ('caja','fecha_cierre','timestamp,timestamptz',true),
        ('caja','monto_inicial','numeric',true),
        ('caja','efectivo_inicial','numeric',true),
        ('caja','efectivo_contado','numeric',true),
        ('caja','efectivo_esperado','numeric',true),
        ('caja','diferencia','numeric',true),
        ('caja','faltante','numeric',true),
        ('caja','sobrante','numeric',true),
        ('caja','dia_operativo','date',true),
        ('caja','observacion','text',true),
        ('caja','anulado','bool,boolean',true),
        ('cierre_caja','id','uuid,int8,bigint',true),
        ('cierre_caja','empresa_id','text',true),
        ('cierre_caja','caja_id','uuid',true),
        ('cierre_caja','usuario_id','uuid',true),
        ('cierre_caja','monto_inicial','numeric',true),
        ('cierre_caja','efectivo_esperado','numeric',true),
        ('cierre_caja','efectivo_contado','numeric',true),
        ('cierre_caja','diferencia','numeric',true),
        ('ventas','id','uuid',true),
        ('ventas','empresa_id','text',true),
        ('ventas','fecha','timestamp,timestamptz',true),
        ('ventas','total','numeric',true),
        ('ventas','subtotal','numeric',true),
        ('ventas','subtotal_gravado','numeric',true),
        ('ventas','subtotal_exento','numeric',true),
        ('ventas','itbis_total','numeric',true),
        ('ventas','ganancia_bruta','numeric',true),
        ('ventas','estado','text',true),
        ('ventas','anulado','bool,boolean',true),
        ('ventas','numero_factura','text',true),
        ('ventas','cliente_id','int8,bigint',true),
        ('ventas','cliente_nombre','text',true),
        ('ventas','usuario','text',true),
        ('ventas','usuario_id','uuid',true),
        ('ventas','dia_operativo','date',true),
        ('ventas','caja_id','uuid',true),
        ('ventas','metodo_pago','text',true),
        ('ventas','observacion','text',true),
        ('ventas','updated_at','timestamp,timestamptz',true),
        ('detalle_venta','id','uuid',true),
        ('detalle_venta','empresa_id','text',true),
        ('detalle_venta','venta_id','uuid',true),
        ('detalle_venta','producto_id','uuid',true),
        ('detalle_venta','cantidad','numeric',true),
        ('detalle_venta','precio_unitario','numeric',true),
        ('detalle_venta','subtotal','numeric',true),
        ('detalle_venta','total_linea','numeric',true),
        ('detalle_venta','costo_unitario','numeric',true),
        ('detalle_venta','costo_total','numeric',true),
        ('detalle_venta','anulado','bool,boolean',true),
        ('ventas_pagos','empresa_id','text',true),
        ('ventas_pagos','venta_id','uuid',true),
        ('ventas_pagos','metodo','text',true),
        ('ventas_pagos','monto','numeric',true),
        ('ventas_pagos','usuario_id','uuid',true),
        ('ventas_pagos','caja_id','uuid',true),
        ('ventas_pagos','dia_operativo','date',true),
        ('ventas_pagos','anulado','bool,boolean',true),
        ('movimientos_caja','empresa_id','text',true),
        ('movimientos_caja','caja_id','uuid',true),
        ('movimientos_caja','tipo_movimiento','text',true),
        ('movimientos_caja','metodo_pago','text',true),
        ('movimientos_caja','monto','numeric',true),
        ('movimientos_caja','anulado','bool,boolean',true),
        ('productos','id','uuid',true),
        ('productos','empresa_id','text',true),
        ('productos','nombre','text',true),
        ('productos','stock','numeric',true),
        ('productos','existencia','numeric',true),
        ('productos','cantidad','numeric',true),
        ('productos','precio_venta','numeric',true),
        ('productos','precio','numeric',true),
        ('productos','precio_minimo','numeric',true),
        ('productos','precio_descuento','numeric',true),
        ('productos','costo_unitario','numeric',true),
        ('productos','costo','numeric',true),
        ('productos','itbis_gravado','bool,boolean',true),
        ('productos','itbis_tasa','numeric',true),
        ('productos','activo','bool,boolean',true),
        ('productos','anulado','bool,boolean',true),
        ('productos','updated_at','timestamp,timestamptz',true),
        ('clientes','id','int8,bigint',true),
        ('clientes','empresa_id','text',true),
        ('clientes','nombre','text',true),
        ('clientes','limite_credito','numeric',true),
        ('clientes','activo','bool,boolean',true),
        ('inventario_lotes','id','int8,bigint',true),
        ('inventario_lotes','empresa_id','text',true),
        ('inventario_lotes','producto_id','uuid',true),
        ('inventario_lotes','cantidad_restante','numeric',true),
        ('inventario_lotes','costo_unitario','numeric',true),
        ('inventario_lotes','fecha_compra','date,timestamp,timestamptz',true),
        ('inventario_lotes','created_at','timestamp,timestamptz',true),
        ('inventario_lotes','activo','bool,boolean',true),
        ('inventario_consumos','empresa_id','text',true),
        ('inventario_consumos','venta_id','uuid',true),
        ('inventario_consumos','detalle_id','uuid',true),
        ('inventario_consumos','producto_id','uuid',true),
        ('inventario_consumos','lote_id','int8,bigint',true),
        ('inventario_consumos','cantidad','numeric',true),
        ('inventario_consumos','costo_unitario','numeric',true),
        ('cuentas_por_cobrar','id','int8,bigint',true),
        ('cuentas_por_cobrar','empresa_id','text',true),
        ('cuentas_por_cobrar','cliente_id','int8,bigint',true),
        ('cuentas_por_cobrar','venta_id','uuid',true),
        ('cuentas_por_cobrar','saldo_pendiente','numeric',true),
        ('cuentas_por_cobrar','anulado','bool,boolean',true),
        ('movimientos_contables','empresa_id','text',true),
        ('movimientos_contables','referencia_id','text',true),
        ('movimientos_contables','debito','numeric',true),
        ('movimientos_contables','credito','numeric',true),
        ('auditoria_eventos','empresa_id','text',true),
        ('auditoria_eventos','usuario_id','text',true),
        ('auditoria_eventos','accion','text',true),
        ('auditoria_eventos','metadata','jsonb',true),
        ('secuencia_documentos','empresa_id','text',true),
        ('secuencia_documentos','sucursal_id','text',true),
        ('secuencia_documentos','tipo','text',true),
        ('secuencia_documentos','siguiente','int8,bigint',true)
), actuales as (
    select
        c.table_name as tabla,
        c.column_name as columna,
        c.udt_name,
        c.data_type,
        c.is_nullable,
        c.column_default
    from information_schema.columns c
    where c.table_schema='public'
)
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '02_COLUMNAS_CAJA_COBRO',
    e.tabla || '.' || e.columna,
    case
        when a.columna is null then 'ERROR'
        when not (a.udt_name = any(string_to_array(e.tipos_aceptados,','))) then 'ERROR'
        else 'OK'
    end,
    case
        when a.columna is null then 'Columna faltante; tipo esperado: ' || e.tipos_aceptados
        else format(
            'tipo=%s; nullable=%s; default=%s; esperado=%s',
            a.udt_name,
            a.is_nullable,
            coalesce(a.column_default,'SIN DEFAULT'),
            e.tipos_aceptados
        )
    end
from esperadas e
left join actuales a using(tabla,columna);

-- -------------------------------------------------------------------------
-- 3. Funciones RPC y permisos de ejecucion
-- -------------------------------------------------------------------------
with requeridas(nombre,firma) as (
    values
        ('api_my_session','public.api_my_session(text)'),
        ('api_abrir_caja','public.api_abrir_caja(numeric,text)'),
        ('api_cerrar_caja','public.api_cerrar_caja(text,numeric,text)'),
        ('api_registrar_venta','public.api_registrar_venta(jsonb)'),
        ('api_editar_venta','public.api_editar_venta(text,jsonb,text)'),
        ('api_reemplazar_cuenta_abierta','public.api_reemplazar_cuenta_abierta(text,jsonb)'),
        ('api_anular_venta','public.api_anular_venta(text,text)'),
        ('api_registrar_abono','public.api_registrar_abono(bigint,bigint,numeric,text,text,text)'),
        ('api_registrar_compra_producto','public.api_registrar_compra_producto(jsonb)'),
        ('api_registrar_factura_compra','public.api_registrar_factura_compra(jsonb)'),
        ('api_cerrar_periodo','public.api_cerrar_periodo(integer,integer,text)'),
        ('api_registrar_nomina','public.api_registrar_nomina(text,text,text,text,text)'),
        ('api_update_my_profile','public.api_update_my_profile(text)'),
        ('api_audit_event','public.api_audit_event(text,text,text,text,text,jsonb)'),
        ('api_prepare_delete_unused_user','public.api_prepare_delete_unused_user(uuid,text)'),
        ('api_prevalidar_migracion_biberon','public.api_prevalidar_migracion_biberon()'),
        ('api_importar_historial_biberon','public.api_importar_historial_biberon(jsonb)'),
        ('api_validar_importacion_biberon','public.api_validar_importacion_biberon(text)'),
        ('has_tenant_access','public.has_tenant_access(text)'),
        ('has_tenant_permission','public.has_tenant_permission(text,text)'),
        ('is_platform_superadmin','public.is_platform_superadmin()')
), funciones as (
    select
        r.nombre,
        r.firma,
        to_regprocedure(r.firma) as oid
    from requeridas r
)
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    f.firma,
    case
        when f.oid is null then 'ERROR'
        when not p.prosecdef then 'ERROR'
        when not has_function_privilege('authenticated',f.oid,'EXECUTE') then 'ERROR'
        when has_function_privilege('anon',f.oid,'EXECUTE') then 'ERROR'
        else 'OK'
    end,
    case
        when f.oid is null then 'Funcion o firma exacta faltante'
        else format(
            'security_definer=%s; authenticated_execute=%s; anon_execute=%s; owner=%s; config=%s',
            p.prosecdef,
            has_function_privilege('authenticated',f.oid,'EXECUTE'),
            has_function_privilege('anon',f.oid,'EXECUTE'),
            pg_get_userbyid(p.proowner),
            coalesce(array_to_string(p.proconfig,','),'SIN CONFIG')
        )
    end
from funciones f
left join pg_proc p on p.oid=f.oid;

-- Confirma que la version activa de apertura usa DATE y el contrato nuevo de auditoria.
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    'api_abrir_caja_contrato_activo',
    case
        when to_regprocedure('public.api_abrir_caja(numeric,text)') is null then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_abrir_caja(numeric,text)')) ilike '%current_date::text%' then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_abrir_caja(numeric,text)')) not ilike '%''abierta'',current_date,%' then 'REVISAR'
        when pg_get_functiondef(to_regprocedure('public.api_abrir_caja(numeric,text)')) not ilike '%auditoria_eventos%' then 'ERROR'
        else 'OK'
    end,
    'Debe insertar dia_operativo como current_date y registrar auditoria_eventos'
where to_regprocedure('public.api_abrir_caja(numeric,text)') is not null;

-- La cajera debe poder cobrar una cuenta abierta sin MFA y usando SU caja
-- actualmente abierta, no la caja historica en la que se creo la cuenta.
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    'api_reemplazar_cuenta_abierta_flujo_cobro',
    case
        when to_regprocedure('public.api_reemplazar_cuenta_abierta(text,jsonb)') is null then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_reemplazar_cuenta_abierta(text,jsonb)')) ilike '%MFA_AAL2_REQUIRED%' then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_reemplazar_cuenta_abierta(text,jsonb)')) ilike '%''caja_id'',v_old.caja_id%' then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_reemplazar_cuenta_abierta(text,jsonb)')) not ilike '%puede_vender%' then 'ERROR'
        else 'OK'
    end,
    'No debe exigir MFA a empleados; debe autorizar puede_vender y usar la caja activa enviada en el cobro'
where to_regprocedure('public.api_reemplazar_cuenta_abierta(text,jsonb)') is not null;

-- Una venta no puede atribuirse a la caja abierta de otro usuario.
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    'api_registrar_venta_caja_del_actor',
    case
        when to_regprocedure('public.api_registrar_venta(jsonb)') is null then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_registrar_venta(jsonb)')) not ilike '%v_caja_owner is distinct from v_uid%' then 'ERROR'
        else 'OK'
    end,
    'La venta debe leer el dueño de la caja y rechazarlo cuando difiere de auth.uid()'
where to_regprocedure('public.api_registrar_venta(jsonb)') is not null;

insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    'api_registrar_venta_descuento_global',
    case
        when to_regprocedure('public.api_registrar_venta(jsonb)') is null then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_registrar_venta(jsonb)')) not ilike '%v_descuento_global%' then 'ERROR'
        else 'OK'
    end,
    'El servidor debe recalcular y distribuir el descuento sin confiar en el navegador'
where to_regprocedure('public.api_registrar_venta(jsonb)') is not null;

insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    'api_registrar_abono_caja_y_fecha',
    case
        when to_regprocedure('public.api_registrar_abono(bigint,bigint,numeric,text,text,text)') is null then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_registrar_abono(bigint,bigint,numeric,text,text,text)')) not ilike '%v_caja_owner is distinct from v_uid%' then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_registrar_abono(bigint,bigint,numeric,text,text,text)')) ilike '%current_date::text%' then 'ERROR'
        else 'OK'
    end,
    'El abono debe usar la caja del actor y conservar dia_operativo como DATE'
where to_regprocedure('public.api_registrar_abono(bigint,bigint,numeric,text,text,text)') is not null;

insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '03_FUNCIONES_RPC',
    'api_cerrar_caja_totales_y_propietario',
    case
        when to_regprocedure('public.api_cerrar_caja(text,numeric,text)') is null then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_cerrar_caja(text,numeric,text)')) not ilike '%CLOSE_OTHER_CASH_PERMISSION_DENIED%' then 'ERROR'
        when pg_get_functiondef(to_regprocedure('public.api_cerrar_caja(text,numeric,text)')) not ilike '%total_transferencia%' then 'ERROR'
        else 'OK'
    end,
    'El cierre debe proteger cajas ajenas y persistir totales por método'
where to_regprocedure('public.api_cerrar_caja(text,numeric,text)') is not null;

-- -------------------------------------------------------------------------
-- 4. RLS, politicas y privilegios de tablas
-- -------------------------------------------------------------------------
with criticas(tabla) as (
    values
        ('empresas'),('tenant_memberships'),('usuarios'),
        ('configuracion_sistema'),('suscripciones_empresas'),
        ('productos'),('clientes'),('ventas'),('detalle_venta'),
        ('ventas_pagos'),('caja'),('cierre_caja'),('movimientos_caja'),
        ('cuentas_por_cobrar'),('abonos_credito'),
        ('inventario_lotes'),('inventario_consumos'),
        ('movimientos_contables'),('periodos_contables'),('auditoria_eventos')
)
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '04_RLS',
    c.tabla,
    case
        when pc.oid is null then 'ERROR'
        when not pc.relrowsecurity then 'ERROR'
        when coalesce(pol.cantidad,0)=0 then 'ERROR'
        else 'OK'
    end,
    case
        when pc.oid is null then 'Tabla faltante'
        else format('rls=%s; politicas=%s',pc.relrowsecurity,coalesce(pol.cantidad,0))
    end
from criticas c
left join pg_class pc
  on pc.relnamespace='public'::regnamespace and pc.relname=c.tabla and pc.relkind in ('r','p')
left join lateral (
    select count(*) as cantidad
    from pg_policies pp
    where pp.schemaname='public' and pp.tablename=c.tabla
) pol on true;

insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '04_RLS',
    'politica_universal:' || tablename || ':' || policyname,
    'ERROR',
    format('cmd=%s; qual=%s; with_check=%s',cmd,coalesce(qual,''),coalesce(with_check,''))
from pg_policies
where schemaname='public'
  and (
      regexp_replace(lower(coalesce(qual,'')),'\s','','g') in ('true','(true)')
      or regexp_replace(lower(coalesce(with_check,'')),'\s','','g') in ('true','(true)')
  );

insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '04_RLS',
    'anon:' || table_name || ':' || privilege_type,
    'ERROR',
    'El rol anon tiene un privilegio directo sobre una tabla public'
from information_schema.role_table_grants
where table_schema='public' and grantee='anon';

insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '04_RLS',
    'dml_directo_authenticated:' || table_name || ':' || privilege_type,
    'ERROR',
    'Las escrituras críticas deben pasar por RPC SECURITY DEFINER, no por privilegios directos'
from information_schema.role_table_grants
where table_schema='public'
  and grantee='authenticated'
  and privilege_type in ('INSERT','UPDATE','DELETE')
  and table_name in (
      'ventas','detalle_venta','ventas_pagos','caja','cierre_caja',
      'movimientos_caja','cuentas_por_cobrar','abonos_credito',
      'inventario_consumos','movimientos_contables','periodos_contables',
      'tenant_memberships','usuarios','auditoria_eventos'
  );

with esperadas(tabla,fragmento) as (
    values
        ('cierre_caja','auth.uid()'),
        ('movimientos_caja','auth.uid()'),
        ('ventas_pagos','has_tenant_access')
)
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '04_RLS',
    'politica_reparada:' || e.tabla,
    case
        when p.policyname is null then 'ERROR'
        when upper(p.cmd)<>'SELECT' then 'ERROR'
        when p.qual not ilike '%' || e.fragmento || '%' then 'ERROR'
        else 'OK'
    end,
    case
        when p.policyname is null then 'Falta ais_select'
        else format('cmd=%s; roles=%s; qual=%s',p.cmd,p.roles::text,p.qual)
    end
from esperadas e
left join pg_policies p
  on p.schemaname='public' and p.tablename=e.tabla and p.policyname='ais_select';

-- -------------------------------------------------------------------------
-- 5. Todas las tablas multiempresa deben tener empresa_id
-- -------------------------------------------------------------------------
with multiempresa(tabla) as (
    values
        ('usuarios'),('configuracion_sistema'),('suscripciones_empresas'),
        ('productos'),('clientes'),('proveedores'),('compras'),
        ('facturas_compra'),('detalle_factura_compra'),('gastos'),
        ('empleados'),('pagos_empleados'),('perdidas'),
        ('ventas'),('detalle_venta'),('ventas_pagos'),
        ('caja'),('cierre_caja'),('movimientos_caja'),
        ('cuentas_por_cobrar'),('abonos_credito'),
        ('inventario_lotes'),('inventario_consumos'),
        ('movimientos_contables'),('periodos_contables'),('auditoria_eventos')
)
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '05_AISLAMIENTO_EMPRESAS',
    m.tabla || '.empresa_id',
    case
        when to_regclass('public.'||m.tabla) is null then 'ERROR'
        when c.column_name is null then 'ERROR'
        when c.udt_name <> 'text' then 'ERROR'
        else 'OK'
    end,
    case
        when to_regclass('public.'||m.tabla) is null then 'Tabla faltante'
        when c.column_name is null then 'Falta empresa_id'
        else format('tipo=%s; nullable=%s; default=%s',c.udt_name,c.is_nullable,coalesce(c.column_default,'SIN DEFAULT'))
    end
from multiempresa m
left join information_schema.columns c
  on c.table_schema='public' and c.table_name=m.tabla and c.column_name='empresa_id';

-- -------------------------------------------------------------------------
-- 6. Comprobaciones de datos. Cada una devuelve solamente una cantidad.
-- Si una tabla/columna difiere, la comprobacion se marca ERROR sin detener todo.
-- -------------------------------------------------------------------------
do $$
declare
    r record;
    v_cantidad bigint;
begin
    for r in
        select * from (values
            ('06_DATOS','usuarios_sin_auth',
             'select count(*) from public.usuarios where user_id is null'),
            ('06_DATOS','usuarios_sin_empresa',
             'select count(*) from public.usuarios where empresa_id is null or trim(empresa_id)='''''),
            ('06_DATOS','membresias_sin_empresa',
             'select count(*) from public.tenant_memberships tm left join public.empresas e on e.tenant_id=tm.tenant_id where e.tenant_id is null'),
            ('06_DATOS','membresias_sin_auth',
             'select count(*) from public.tenant_memberships tm left join auth.users au on au.id=tm.user_id where au.id is null'),
            ('06_DATOS','perfiles_sin_membresia',
             'select count(*) from public.usuarios u left join public.tenant_memberships tm on tm.user_id=u.user_id and tm.tenant_id=u.empresa_id where tm.user_id is null'),
            ('06_DATOS','usuarios_con_multiples_membresias_activas',
             'select count(*) from (select user_id from public.tenant_memberships where active group by user_id having count(*)>1) x'),
            ('06_DATOS','usuarios_de_acceso_duplicados',
             'select count(*) from (select lower(trim(usuario)) from public.usuarios where nullif(trim(usuario),'''') is not null group by lower(trim(usuario)) having count(*)>1) x'),
            ('06_DATOS','empresas_activas_sin_admin_activo',
             'select count(*) from public.empresas e where e.activo and not exists (select 1 from public.tenant_memberships tm where tm.tenant_id=e.tenant_id and tm.active and tm.role=''admin'')'),
            ('06_DATOS','empresas_activas_sin_licencia_vigente',
             'select count(*) from public.empresas e where e.activo and e.tenant_id<>''global'' and not exists (select 1 from public.suscripciones_empresas s where s.empresa_id=e.tenant_id and s.fecha_inicio<=current_date and current_date<=s.fecha_vencimiento+coalesce(s.dias_gracia,0))'),
            ('07_CAJA','cajas_sin_empresa',
             'select count(*) from public.caja where empresa_id is null or trim(empresa_id)='''' or empresa_id=''global'''),
            ('07_CAJA','cajas_sin_usuario_id',
             'select count(*) from public.caja where usuario_id is null'),
            ('07_CAJA','cajas_abiertas_duplicadas',
             'select count(*) from (select empresa_id,usuario_id from public.caja where lower(coalesce(estado,''''))=''abierta'' and not coalesce(anulado,false) group by empresa_id,usuario_id having count(*)>1) x'),
            ('07_CAJA','cajas_abiertas_sin_membresia_activa',
             'select count(*) from public.caja c left join public.tenant_memberships tm on tm.user_id=c.usuario_id and tm.tenant_id=c.empresa_id and tm.active where lower(coalesce(c.estado,''''))=''abierta'' and not coalesce(c.anulado,false) and tm.user_id is null'),
            ('07_CAJA','cajas_con_empresa_inexistente',
             'select count(*) from public.caja c left join public.empresas e on e.tenant_id=c.empresa_id where e.tenant_id is null'),
            ('07_CAJA','cierres_huerfanos',
             'select count(*) from public.cierre_caja cc left join public.caja c on c.id=cc.caja_id where c.id is null'),
            ('07_CAJA','cierres_empresa_diferente',
             'select count(*) from public.cierre_caja cc join public.caja c on c.id=cc.caja_id where cc.empresa_id is distinct from c.empresa_id'),
            ('08_COBRAR','ventas_sin_empresa',
             'select count(*) from public.ventas where empresa_id is null or trim(empresa_id)='''' or empresa_id=''global'''),
            ('08_COBRAR','ventas_sin_usuario_id',
             'select count(*) from public.ventas where usuario_id is null'),
            ('08_COBRAR','ventas_completadas_sin_caja',
             'select count(*) from public.ventas where lower(coalesce(estado,''''))=''completada'' and not coalesce(anulado,false) and caja_id is null'),
            ('08_COBRAR','ventas_caja_empresa_diferente',
             'select count(*) from public.ventas v join public.caja c on c.id=v.caja_id where v.empresa_id is distinct from c.empresa_id'),
            ('08_COBRAR','detalles_huerfanos',
             'select count(*) from public.detalle_venta d left join public.ventas v on v.id=d.venta_id where v.id is null'),
            ('08_COBRAR','detalles_empresa_diferente',
             'select count(*) from public.detalle_venta d join public.ventas v on v.id=d.venta_id where d.empresa_id is distinct from v.empresa_id'),
            ('08_COBRAR','pagos_huerfanos',
             'select count(*) from public.ventas_pagos vp left join public.ventas v on v.id=vp.venta_id where v.id is null'),
            ('08_COBRAR','pagos_empresa_diferente',
             'select count(*) from public.ventas_pagos vp join public.ventas v on v.id=vp.venta_id where vp.empresa_id is distinct from v.empresa_id'),
            ('08_COBRAR','pagos_metodo_invalido',
             'select count(*) from public.ventas_pagos where lower(coalesce(metodo,'''')) not in (''efectivo'',''transferencia'',''tarjeta'',''credito'') or monto<0'),
            ('08_COBRAR','cuentas_abiertas_con_pagos',
             'select count(*) from public.ventas v where lower(coalesce(v.estado,''''))=''abierta'' and exists (select 1 from public.ventas_pagos vp where vp.venta_id=v.id and not coalesce(vp.anulado,false) and vp.monto>0)'),
            ('08_COBRAR','ventas_completadas_pago_no_cuadra',
             'select count(*) from public.ventas v where lower(coalesce(v.estado,''''))=''completada'' and not coalesce(v.anulado,false) and abs(coalesce(v.total,0)-coalesce((select sum(vp.monto) from public.ventas_pagos vp where vp.venta_id=v.id and not coalesce(vp.anulado,false)),0))>0.01'),
            ('08_COBRAR','ventas_total_detalle_no_cuadra',
             'select count(*) from public.ventas v where not coalesce(v.anulado,false) and abs(coalesce(v.total,0)-coalesce((select sum(d.total_linea) from public.detalle_venta d where d.venta_id=v.id and not coalesce(d.anulado,false)),0))>0.01'),
            ('08_COBRAR','productos_stock_negativo',
             'select count(*) from public.productos where least(coalesce(stock,0),coalesce(existencia,0),coalesce(cantidad,0))<0'),
            ('08_COBRAR','consumos_huerfanos',
             'select count(*) from public.inventario_consumos ic left join public.ventas v on v.id=ic.venta_id left join public.productos p on p.id=ic.producto_id where v.id is null or p.id is null'),
            ('08_COBRAR','movimientos_caja_empresa_diferente',
             'select count(*) from public.movimientos_caja mc join public.caja c on c.id=mc.caja_id where mc.empresa_id is distinct from c.empresa_id'),
            ('09_CONTABILIDAD','asientos_descuadrados_por_venta',
             'select count(*) from (select empresa_id,referencia_id from public.movimientos_contables where modulo=''ventas'' group by empresa_id,referencia_id having abs(sum(coalesce(debito,0))-sum(coalesce(credito,0)))>0.01) x'),
            ('09_CONTABILIDAD','asientos_empresa_diferente_venta',
             'select count(*) from public.movimientos_contables mc join public.ventas v on v.id::text=mc.referencia_id and mc.modulo=''ventas'' where mc.empresa_id is distinct from v.empresa_id'),
            ('09_CONTABILIDAD','meses_contables_descuadrados',
             'select count(*) from (select empresa_id,date_trunc(''month'',fecha) mes from public.movimientos_contables group by empresa_id,date_trunc(''month'',fecha) having abs(sum(coalesce(debito,0))-sum(coalesce(credito,0)))>0.01) x')
        ) as q(area,prueba,sql_texto)
    loop
        begin
            execute r.sql_texto into v_cantidad;
            insert into ais_diagnostico(area,prueba,estado,detalle)
            values (
                r.area,
                r.prueba,
                case when v_cantidad=0 then 'OK' else 'ERROR' end,
                'cantidad=' || v_cantidad::text
            );
        exception when others then
            insert into ais_diagnostico(area,prueba,estado,detalle)
            values (r.area,r.prueba,'ERROR','No se pudo comprobar: ' || sqlerrm);
        end;
    end loop;
end
$$;

-- -------------------------------------------------------------------------
-- 7. Detalle de anomalias importantes (sin exponer correos ni contrasenas)
-- -------------------------------------------------------------------------
do $$
declare
    r record;
begin
    for r in
        select e.tenant_id, e.nombre
        from public.empresas e
        where e.activo
          and e.tenant_id <> 'global'
          and not exists (
              select 1
              from public.suscripciones_empresas s
              where s.empresa_id=e.tenant_id
                and s.fecha_inicio<=current_date
                and current_date<=s.fecha_vencimiento+coalesce(s.dias_gracia,0)
          )
        order by e.tenant_id
    loop
        insert into ais_diagnostico(area,prueba,estado,detalle)
        values (
            '06_DATOS_DETALLE',
            'empresa_activa_sin_licencia:' || r.tenant_id,
            'REVISAR',
            'empresa=' || coalesce(r.nombre,'SIN NOMBRE')
        );
    end loop;
exception when others then
    insert into ais_diagnostico(area,prueba,estado,detalle)
    values ('06_DATOS_DETALLE','empresas_sin_licencia','ERROR','No se pudo detallar: ' || sqlerrm);
end
$$;

do $$
declare
    r record;
begin
    for r in
        select c.id, c.empresa_id, c.usuario_id, c.fecha_apertura
        from public.caja c
        where lower(coalesce(c.estado,''))='abierta'
          and not coalesce(c.anulado,false)
        order by c.empresa_id,c.fecha_apertura
    loop
        insert into ais_diagnostico(area,prueba,estado,detalle)
        values (
            '07_CAJA_DETALLE',
            'caja_abierta:' || r.id::text,
            'INFO',
            format('empresa=%s; usuario_id=%s; apertura=%s',r.empresa_id,r.usuario_id,r.fecha_apertura)
        );
    end loop;
exception when others then
    insert into ais_diagnostico(area,prueba,estado,detalle)
    values ('07_CAJA_DETALLE','cajas_abiertas','ERROR','No se pudo detallar: ' || sqlerrm);
end
$$;

do $$
declare
    r record;
begin
    for r in
        select p.id, p.empresa_id, p.nombre,
               coalesce(p.stock,0) stock,
               coalesce(p.existencia,0) existencia,
               coalesce(p.cantidad,0) cantidad
        from public.productos p
        where least(coalesce(p.stock,0),coalesce(p.existencia,0),coalesce(p.cantidad,0))<0
        order by p.empresa_id,p.nombre
    loop
        insert into ais_diagnostico(area,prueba,estado,detalle)
        values (
            '08_COBRAR_DETALLE',
            'stock_negativo:' || r.id::text,
            'REVISAR',
            format('empresa=%s; producto=%s; stock=%s; existencia=%s; cantidad=%s',
                   r.empresa_id,r.nombre,r.stock,r.existencia,r.cantidad)
        );
    end loop;
exception when others then
    insert into ais_diagnostico(area,prueba,estado,detalle)
    values ('08_COBRAR_DETALLE','productos_stock_negativo','ERROR','No se pudo detallar: ' || sqlerrm);
end
$$;

-- -------------------------------------------------------------------------
-- 8. Esquema real completo de las tablas que intervienen en Caja y Cobrar
-- -------------------------------------------------------------------------
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '10_ESQUEMA_REAL_CAJA_COBRO',
    c.table_name || '.' || c.column_name,
    'INFO',
    format(
        'pos=%s; data_type=%s; udt=%s; nullable=%s; default=%s; identity=%s/%s',
        c.ordinal_position,c.data_type,c.udt_name,c.is_nullable,
        coalesce(c.column_default,'SIN DEFAULT'),c.is_identity,
        coalesce(c.identity_generation,'NO')
    )
from information_schema.columns c
where c.table_schema='public'
  and c.table_name in (
      'caja','cierre_caja','ventas','detalle_venta','ventas_pagos',
      'movimientos_caja','productos','clientes','inventario_lotes',
      'inventario_consumos','cuentas_por_cobrar','movimientos_contables',
      'auditoria_eventos','secuencia_documentos','tenant_memberships','usuarios'
  );

-- -------------------------------------------------------------------------
-- 9. Resumen por empresa para comprobar que A&M y Bibe Ron no se mezclan
-- -------------------------------------------------------------------------
do $$
declare
    r record;
begin
    for r in execute $consulta$
        select
            e.tenant_id,
            e.activo,
            (select count(*) from public.tenant_memberships tm where tm.tenant_id=e.tenant_id and tm.active) as usuarios_activos,
            (select count(*) from public.caja c where c.empresa_id=e.tenant_id) as cajas,
            (select count(*) from public.caja c where c.empresa_id=e.tenant_id and lower(coalesce(c.estado,''))='abierta' and not coalesce(c.anulado,false)) as cajas_abiertas,
            (select count(*) from public.ventas v where v.empresa_id=e.tenant_id and not coalesce(v.anulado,false)) as ventas,
            (select round(coalesce(sum(v.total),0),2) from public.ventas v where v.empresa_id=e.tenant_id and not coalesce(v.anulado,false)) as total_ventas,
            (select count(*) from public.suscripciones_empresas s where s.empresa_id=e.tenant_id) as licencias
        from public.empresas e
        order by e.tenant_id
    $consulta$
    loop
        insert into ais_diagnostico(area,prueba,estado,detalle)
        values (
            '11_RESUMEN_EMPRESAS',
            r.tenant_id,
            'INFO',
            format(
                'activa=%s; usuarios_activos=%s; cajas=%s; cajas_abiertas=%s; ventas=%s; total_ventas=%s; licencias=%s',
                r.activo,r.usuarios_activos,r.cajas,r.cajas_abiertas,r.ventas,r.total_ventas,r.licencias
            )
        );
    end loop;
exception when others then
    insert into ais_diagnostico(area,prueba,estado,detalle)
    values ('11_RESUMEN_EMPRESAS','resumen_por_empresa','ERROR','No se pudo comprobar: ' || sqlerrm);
end
$$;

-- -------------------------------------------------------------------------
-- 10. Veredicto global (calculado despues de todas las comprobaciones)
-- -------------------------------------------------------------------------
insert into ais_diagnostico(area,prueba,estado,detalle)
select
    '00_RESUMEN',
    'resultado_general',
    case
        when count(*) filter (where estado='ERROR')=0
         and count(*) filter (where estado='REVISAR')=0 then 'OK'
        else 'REVISAR'
    end,
    format(
        'errores=%s; revisar=%s; ok=%s; info=%s',
        count(*) filter (where estado='ERROR'),
        count(*) filter (where estado='REVISAR'),
        count(*) filter (where estado='OK'),
        count(*) filter (where estado='INFO')
    )
from ais_diagnostico;

-- -------------------------------------------------------------------------
-- Resultado final. Copiar o descargar esta unica tabla.
-- -------------------------------------------------------------------------
select area,prueba,estado,detalle
from ais_diagnostico
order by
    case estado when 'ERROR' then 1 when 'REVISAR' then 2 when 'OK' then 3 else 4 end,
    area,
    prueba,
    orden;
