-- Chequeo previo de solo lectura. Ejecutar primero en STAGING.
select current_database() as base, current_user as usuario, now() as ejecutado_en;

with required(table_name) as (
    values
        ('usuarios'),('configuracion_sistema'),('productos'),('clientes'),
        ('ventas'),('detalle_venta'),('ventas_pagos'),('caja'),
        ('movimientos_caja'),('cuentas_por_cobrar'),('abonos_credito'),
        ('compras'),('gastos'),('empleados'),('pagos_empleados')
)
select
    table_name,
    to_regclass('public.' || table_name) is not null as existe
from required
order by table_name;

-- Contratos de tipos que utiliza la API. Si un tipo difiere, detenga la
-- migración y adapte primero el contrato en staging.
select
    table_name,
    column_name,
    data_type,
    udt_name,
    is_nullable
from information_schema.columns
where table_schema='public'
  and (table_name,column_name) in (
      ('productos','id'),('ventas','id'),('detalle_venta','id'),
      ('detalle_venta','producto_id'),('detalle_venta','venta_id'),
      ('caja','id'),('clientes','id'),('cuentas_por_cobrar','id'),
      ('compras','id'),('empleados','id'),('pagos_empleados','empleado_id')
  )
order by table_name,column_name;

do $$
declare
    v_count bigint;
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema='public' and table_name='usuarios' and column_name='user_id'
    ) then
        execute 'select count(*) from public.usuarios where user_id is null' into v_count;
        raise notice 'Perfiles sin vínculo auth.users: %',v_count;
    else
        raise notice 'FALTA usuarios.user_id: todas las cuentas requieren migración a Supabase Auth';
    end if;
    if exists (
        select 1 from information_schema.columns
        where table_schema='public' and table_name='usuarios' and column_name='empresa_id'
    ) then
        execute 'select count(*) from public.usuarios where empresa_id is null or trim(empresa_id)='''''
        into v_count;
        raise notice 'Perfiles sin empresa_id: %',v_count;
    else
        raise notice 'FALTA usuarios.empresa_id';
    end if;
end
$$;

do $$
declare
    v_table text;
    v_count bigint;
begin
    foreach v_table in array array[
        'usuarios','configuracion_sistema','productos','clientes','ventas',
        'detalle_venta','ventas_pagos','caja','movimientos_caja',
        'cuentas_por_cobrar','abonos_credito','compras','gastos','empleados',
        'pagos_empleados'
    ]
    loop
        if to_regclass('public.'||v_table) is null then
            raise notice 'FALTA TABLA: %',v_table;
            continue;
        end if;
        execute format('select count(*) from public.%I',v_table) into v_count;
        raise notice '%: % filas',v_table,v_count;
    end loop;
end
$$;

-- Filas sin empresa y cajas abiertas duplicadas deben resolverse antes de dar
-- acceso a usuarios.
do $$
declare
    v_table text;
    v_count bigint;
begin
    foreach v_table in array array[
        'productos','clientes','proveedores','compras','gastos','empleados',
        'ventas','detalle_venta','ventas_pagos','caja','movimientos_caja',
        'cuentas_por_cobrar','abonos_credito','pagos_empleados'
    ]
    loop
        if to_regclass('public.'||v_table) is null then continue; end if;
        if exists (
            select 1 from information_schema.columns
            where table_schema='public' and table_name=v_table and column_name='empresa_id'
        ) then
            execute format(
                'select count(*) from public.%I where empresa_id is null or trim(empresa_id)=''''',
                v_table
            ) into v_count;
            raise notice '%: % filas sin empresa_id',v_table,v_count;
        end if;
    end loop;
end
$$;

do $$
declare
    r record;
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema='public' and table_name='caja'
          and column_name in ('empresa_id','usuario_id','estado')
        group by table_name
        having count(*)=3
    ) then
        for r in execute $query$
            select empresa_id,usuario_id,count(*) as cantidad
            from public.caja
            where lower(coalesce(estado,''))='abierta'
            group by empresa_id,usuario_id
            having count(*)>1
        $query$
        loop
            raise notice 'Cajas abiertas duplicadas: empresa %, usuario %, cantidad %',
                r.empresa_id,r.usuario_id,r.cantidad;
        end loop;
    end if;
end
$$;
