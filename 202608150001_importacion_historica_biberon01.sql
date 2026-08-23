-- AIS: importacion historica controlada y exclusiva para BIBE RON 01.
-- Ejecutar despues de 202607250003_maintenance_and_accounting_api.sql.
-- No contiene datos del negocio ni credenciales.

begin;

create extension if not exists pgcrypto;

-- Columnas que el importador necesita y que las instalaciones antiguas no
-- siempre tenian. Se agregan sin borrar ni transformar datos existentes.
alter table public.productos add column if not exists categoria text;
alter table public.productos add column if not exists precio_mayorista numeric(18,2);
alter table public.productos add column if not exists precio_especial numeric(18,2);
alter table public.productos add column if not exists fecha_agregado date;

alter table public.ventas_pagos add column if not exists fecha timestamptz;

alter table public.proveedores add column if not exists nombre text;
alter table public.proveedores add column if not exists rnc text;
alter table public.proveedores add column if not exists activo boolean not null default true;

alter table public.compras add column if not exists rnc text;
alter table public.compras add column if not exists estado text;
alter table public.compras add column if not exists impuesto numeric(18,2) not null default 0;

alter table public.gastos add column if not exists fecha date;
alter table public.gastos add column if not exists nombre text;
alter table public.gastos add column if not exists tipo text;
alter table public.gastos add column if not exists categoria text;
alter table public.gastos add column if not exists monto numeric(18,2) not null default 0;
alter table public.gastos add column if not exists metodo_pago text;
alter table public.gastos add column if not exists impuesto numeric(18,2) not null default 0;
alter table public.gastos add column if not exists responsable text;
alter table public.gastos add column if not exists detalle text;

alter table public.gastos_dueno add column if not exists fecha date;
alter table public.gastos_dueno add column if not exists concepto text;
alter table public.gastos_dueno add column if not exists monto numeric(18,2) not null default 0;
alter table public.gastos_dueno add column if not exists metodo_pago text;
alter table public.gastos_dueno add column if not exists detalle text;
alter table public.gastos_dueno add column if not exists tipo_movimiento text;

alter table public.empleados add column if not exists fecha date;
alter table public.empleados add column if not exists nombre text;
alter table public.empleados add column if not exists puesto text;
alter table public.empleados add column if not exists tipo_salario text;
alter table public.empleados add column if not exists frecuencia_pago text;
alter table public.empleados add column if not exists observacion text;

alter table public.perdidas add column if not exists fecha date;
alter table public.perdidas add column if not exists producto text;
alter table public.perdidas add column if not exists cantidad numeric(18,4) not null default 0;
alter table public.perdidas add column if not exists costo_unitario numeric(18,4) not null default 0;
alter table public.perdidas add column if not exists valor numeric(18,2) not null default 0;
alter table public.perdidas add column if not exists tipo_perdida text;
alter table public.perdidas add column if not exists observacion text;
alter table public.perdidas add column if not exists estado text;
alter table public.perdidas add column if not exists reportado_por text;

-- Trazabilidad por fila. Las columnas quedan nulas para operaciones normales.
do $$
declare
    v_table text;
begin
    foreach v_table in array array[
        'productos','clientes','proveedores','ventas','ventas_pagos',
        'cuentas_por_cobrar','compras','gastos','gastos_dueno','empleados',
        'pagos_empleados','perdidas'
    ]
    loop
        execute format(
            'alter table public.%I add column if not exists migracion_paquete_id text',
            v_table
        );
        execute format(
            'alter table public.%I add column if not exists migracion_clave_origen text',
            v_table
        );
        execute format(
            'alter table public.%I add column if not exists migracion_hash_origen text',
            v_table
        );
    end loop;
end
$$;

create unique index if not exists ux_productos_migracion_origen
    on public.productos(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_clientes_migracion_origen
    on public.clientes(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_proveedores_migracion_origen
    on public.proveedores(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_ventas_migracion_origen
    on public.ventas(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_ventas_pagos_migracion_origen
    on public.ventas_pagos(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_cxc_migracion_origen
    on public.cuentas_por_cobrar(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_compras_migracion_origen
    on public.compras(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_gastos_migracion_origen
    on public.gastos(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_gastos_dueno_migracion_origen
    on public.gastos_dueno(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_empleados_migracion_origen
    on public.empleados(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_pagos_empleados_migracion_origen
    on public.pagos_empleados(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;
create unique index if not exists ux_perdidas_migracion_origen
    on public.perdidas(empresa_id,migracion_paquete_id,migracion_clave_origen)
    where migracion_paquete_id is not null;

create table if not exists public.importaciones_historicas (
    empresa_id text not null,
    paquete_id text not null,
    entidad text not null,
    clave_origen text not null,
    hash_origen text not null,
    registro_id text,
    importado_por uuid not null,
    created_at timestamptz not null default now(),
    primary key (empresa_id,paquete_id,entidad,clave_origen),
    check (empresa_id='biberon01'),
    check (hash_origen ~ '^[0-9a-f]{64}$')
);

create table if not exists public.ventas_producto_historico (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    paquete_id text not null,
    clave_origen text not null,
    hash_origen text not null,
    codigo text,
    producto text not null,
    cantidad numeric(18,4) not null default 0,
    costo_unitario numeric(18,4) not null default 0,
    costo_total numeric(18,2) not null default 0,
    descuento numeric(18,2) not null default 0,
    total_vendido numeric(18,2) not null default 0,
    utilidad numeric(18,2) not null default 0,
    desde date,
    hasta date,
    created_at timestamptz not null default now(),
    unique (empresa_id,paquete_id,clave_origen),
    check (empresa_id='biberon01'),
    check (hash_origen ~ '^[0-9a-f]{64}$')
);

alter table public.importaciones_historicas enable row level security;
alter table public.ventas_producto_historico enable row level security;

drop policy if exists ais_select on public.ventas_producto_historico;
create policy ais_select on public.ventas_producto_historico
    for select to authenticated
    using (public.has_tenant_access(empresa_id));

revoke all on public.importaciones_historicas from public, anon, authenticated;
revoke all on public.ventas_producto_historico from public, anon, authenticated;
grant select on public.ventas_producto_historico to authenticated;

create or replace function public.biberon_import_actor()
returns uuid
language plpgsql
security definer
set search_path=public,auth,pg_temp
as $$
declare
    v_uid uuid := auth.uid();
begin
    if v_uid is null then
        raise exception 'AUTH_REQUIRED';
    end if;
    if lower(coalesce(auth.jwt() ->> 'aal','')) <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    if not exists (
        select 1
        from public.tenant_memberships tm
        where tm.user_id=v_uid
          and tm.tenant_id='biberon01'
          and tm.active
          and lower(tm.role) in ('admin','superadmin')
    ) then
        raise exception 'BIBERON_IMPORT_FORBIDDEN';
    end if;
    if not exists (
        select 1
        from public.usuarios u
        where u.user_id=v_uid
          and u.empresa_id='biberon01'
          and coalesce(u.activo,true)
    ) then
        raise exception 'BIBERON_IMPORT_FORBIDDEN';
    end if;
    return v_uid;
end
$$;

revoke all on function public.biberon_import_actor() from public,anon,authenticated;

create or replace function public.api_prevalidar_migracion_biberon()
returns jsonb
language plpgsql
security definer
set search_path=public,auth,pg_temp
as $$
declare
    v_uid uuid;
    v_importados bigint;
    v_existentes bigint;
begin
    v_uid := public.biberon_import_actor();

    select count(*) into v_importados
    from public.importaciones_historicas
    where empresa_id='biberon01';

    select
        (select count(*) from public.productos where empresa_id='biberon01' and migracion_paquete_id is null) +
        (select count(*) from public.ventas where empresa_id='biberon01' and migracion_paquete_id is null) +
        (select count(*) from public.compras where empresa_id='biberon01' and migracion_paquete_id is null) +
        (select count(*) from public.gastos where empresa_id='biberon01' and migracion_paquete_id is null) +
        (select count(*) from public.gastos_dueno where empresa_id='biberon01' and migracion_paquete_id is null) +
        (select count(*) from public.pagos_empleados where empresa_id='biberon01' and migracion_paquete_id is null) +
        (select count(*) from public.perdidas where empresa_id='biberon01' and migracion_paquete_id is null)
    into v_existentes;

    return jsonb_build_object(
        'success',true,
        'tenant_id','biberon01',
        'already_imported',v_importados,
        'unmanaged_business_rows',v_existentes,
        'ready',(v_importados>0 or v_existentes=0)
    );
end
$$;

create or replace function public.api_importar_historial_biberon(p jsonb)
returns jsonb
language plpgsql
security definer
set search_path=public,auth,pg_temp
as $$
declare
    v_uid uuid;
    v_package text;
    v_entity text;
    v_records jsonb;
    v_record jsonb;
    v_key text;
    v_hash text;
    v_existing_hash text;
    v_record_id text;
    v_venta_id uuid;
    v_cliente_id bigint;
    v_empleado_id text;
    v_inserted integer := 0;
    v_skipped integer := 0;
    v_unmanaged bigint;
begin
    v_uid := public.biberon_import_actor();
    if jsonb_typeof(p) <> 'object' then
        raise exception 'INVALID_IMPORT_PAYLOAD';
    end if;
    if coalesce(p ->> 'tenant_id','') <> 'biberon01' then
        raise exception 'BIBERON_TENANT_MISMATCH';
    end if;

    v_package := left(coalesce(p ->> 'package_id',''),120);
    if v_package !~ '^biberon01-hasta-[0-9]{4}-[0-9]{2}-[0-9]{2}-v[0-9]+$' then
        raise exception 'INVALID_IMPORT_PACKAGE';
    end if;
    v_entity := lower(coalesce(p ->> 'entity',''));
    if v_entity not in (
        'productos','clientes','proveedores','ventas','ventas_pagos',
        'cuentas_por_cobrar','compras','gastos','gastos_dueno','empleados',
        'pagos_empleados','perdidas','ventas_producto_historico'
    ) then
        raise exception 'INVALID_IMPORT_ENTITY';
    end if;
    v_records := p -> 'records';
    if jsonb_typeof(v_records) <> 'array'
       or jsonb_array_length(v_records)<1
       or jsonb_array_length(v_records)>500 then
        raise exception 'INVALID_IMPORT_BATCH';
    end if;

    perform pg_advisory_xact_lock(hashtextextended('biberon01:'||v_package,0));

    if not exists (
        select 1 from public.importaciones_historicas
        where empresa_id='biberon01'
    ) then
        select
            (select count(*) from public.productos where empresa_id='biberon01' and migracion_paquete_id is null) +
            (select count(*) from public.ventas where empresa_id='biberon01' and migracion_paquete_id is null) +
            (select count(*) from public.compras where empresa_id='biberon01' and migracion_paquete_id is null) +
            (select count(*) from public.gastos where empresa_id='biberon01' and migracion_paquete_id is null) +
            (select count(*) from public.gastos_dueno where empresa_id='biberon01' and migracion_paquete_id is null) +
            (select count(*) from public.pagos_empleados where empresa_id='biberon01' and migracion_paquete_id is null) +
            (select count(*) from public.perdidas where empresa_id='biberon01' and migracion_paquete_id is null)
        into v_unmanaged;
        if v_unmanaged>0 then
            raise exception 'BIBERON_TARGET_NOT_EMPTY';
        end if;
    end if;

    for v_record in select value from jsonb_array_elements(v_records)
    loop
        v_key := left(trim(coalesce(v_record ->> 'source_key','')),220);
        v_hash := lower(trim(coalesce(v_record ->> 'source_hash','')));
        if v_key='' or v_hash !~ '^[0-9a-f]{64}$' then
            raise exception 'INVALID_IMPORT_RECORD';
        end if;

        select ih.hash_origen into v_existing_hash
        from public.importaciones_historicas ih
        where ih.empresa_id='biberon01'
          and ih.paquete_id=v_package
          and ih.entidad=v_entity
          and ih.clave_origen=v_key;
        if found then
            if v_existing_hash<>v_hash then
                raise exception 'IMPORT_IDEMPOTENCY_MISMATCH';
            end if;
            v_skipped := v_skipped+1;
            continue;
        end if;

        v_record_id := null;

        if v_entity='productos' then
            select p0.id::text into v_record_id
            from public.productos p0
            where p0.empresa_id='biberon01'
              and (
                  (nullif(trim(v_record ->> 'codigo'),'') is not null and p0.codigo=trim(v_record ->> 'codigo'))
                  or lower(trim(coalesce(p0.nombre,'')))=lower(trim(v_record ->> 'nombre'))
              )
            order by case when p0.codigo=trim(v_record ->> 'codigo') then 0 else 1 end
            limit 1 for update;

            if v_record_id is null then
                insert into public.productos(
                    empresa_id,codigo,nombre,categoria,stock,existencia,cantidad,
                    costo,costo_unitario,precio,precio_venta,precio_mayorista,
                    precio_especial,activo,anulado,fecha_agregado,
                    migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
                ) values (
                    'biberon01',nullif(left(trim(v_record ->> 'codigo'),120),''),
                    left(trim(v_record ->> 'nombre'),240),left(coalesce(v_record ->> 'categoria',''),120),
                    coalesce((v_record ->> 'stock')::numeric,0),coalesce((v_record ->> 'stock')::numeric,0),
                    coalesce((v_record ->> 'stock')::numeric,0),coalesce((v_record ->> 'costo')::numeric,0),
                    coalesce((v_record ->> 'costo')::numeric,0),coalesce((v_record ->> 'precio_venta')::numeric,0),
                    coalesce((v_record ->> 'precio_venta')::numeric,0),coalesce((v_record ->> 'precio_mayorista')::numeric,0),
                    coalesce((v_record ->> 'precio_especial')::numeric,0),coalesce((v_record ->> 'activo')::boolean,true),
                    false,nullif(v_record ->> 'fecha_agregado','')::date,v_package,v_key,v_hash
                ) returning id::text into v_record_id;
            else
                update public.productos set
                    codigo=nullif(left(trim(v_record ->> 'codigo'),120),''),
                    nombre=left(trim(v_record ->> 'nombre'),240),
                    categoria=left(coalesce(v_record ->> 'categoria',''),120),
                    stock=coalesce((v_record ->> 'stock')::numeric,0),
                    existencia=coalesce((v_record ->> 'stock')::numeric,0),
                    cantidad=coalesce((v_record ->> 'stock')::numeric,0),
                    costo=coalesce((v_record ->> 'costo')::numeric,0),
                    costo_unitario=coalesce((v_record ->> 'costo')::numeric,0),
                    precio=coalesce((v_record ->> 'precio_venta')::numeric,0),
                    precio_venta=coalesce((v_record ->> 'precio_venta')::numeric,0),
                    precio_mayorista=coalesce((v_record ->> 'precio_mayorista')::numeric,0),
                    precio_especial=coalesce((v_record ->> 'precio_especial')::numeric,0),
                    activo=coalesce((v_record ->> 'activo')::boolean,true),
                    migracion_paquete_id=v_package,migracion_clave_origen=v_key,
                    migracion_hash_origen=v_hash,updated_at=now()
                where id::text=v_record_id and empresa_id='biberon01';
            end if;

        elsif v_entity='clientes' then
            select c.id into v_cliente_id
            from public.clientes c
            where c.empresa_id='biberon01'
              and lower(trim(coalesce(c.nombre,'')))=lower(trim(v_record ->> 'nombre'))
            limit 1 for update;
            if v_cliente_id is null then
                insert into public.clientes(
                    empresa_id,nombre,activo,limite_credito,
                    migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
                ) values (
                    'biberon01',left(trim(v_record ->> 'nombre'),240),
                    coalesce((v_record ->> 'activo')::boolean,true),
                    coalesce((v_record ->> 'limite_credito')::numeric,0),v_package,v_key,v_hash
                ) returning id into v_cliente_id;
            else
                update public.clientes set
                    activo=coalesce((v_record ->> 'activo')::boolean,true),
                    limite_credito=coalesce((v_record ->> 'limite_credito')::numeric,0),
                    migracion_paquete_id=v_package,migracion_clave_origen=v_key,
                    migracion_hash_origen=v_hash
                where id=v_cliente_id and empresa_id='biberon01';
            end if;
            v_record_id := v_cliente_id::text;

        elsif v_entity='proveedores' then
            select pr.id::text into v_record_id
            from public.proveedores pr
            where pr.empresa_id='biberon01'
              and lower(trim(coalesce(pr.nombre,'')))=lower(trim(v_record ->> 'nombre'))
            limit 1 for update;
            if v_record_id is null then
                insert into public.proveedores(
                    empresa_id,nombre,rnc,activo,
                    migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
                ) values (
                    'biberon01',left(trim(v_record ->> 'nombre'),240),
                    nullif(left(trim(coalesce(v_record ->> 'rnc','')),40),''),
                    coalesce((v_record ->> 'activo')::boolean,true),v_package,v_key,v_hash
                ) returning id::text into v_record_id;
            else
                update public.proveedores set
                    rnc=nullif(left(trim(coalesce(v_record ->> 'rnc','')),40),''),
                    activo=coalesce((v_record ->> 'activo')::boolean,true),
                    migracion_paquete_id=v_package,migracion_clave_origen=v_key,
                    migracion_hash_origen=v_hash
                where id::text=v_record_id and empresa_id='biberon01';
            end if;

        elsif v_entity='ventas' then
            if exists (
                select 1 from public.ventas vv
                where vv.empresa_id='biberon01'
                  and vv.numero_factura=trim(v_record ->> 'numero_factura')
            ) then
                raise exception 'DUPLICATE_HISTORICAL_INVOICE';
            end if;
            select c.id into v_cliente_id
            from public.clientes c
            where c.empresa_id='biberon01'
              and lower(trim(coalesce(c.nombre,'')))=lower(trim(coalesce(v_record ->> 'cliente_nombre','')))
            limit 1;
            insert into public.ventas(
                empresa_id,fecha,total,subtotal,subtotal_exento,subtotal_gravado,itbis_total,
                numero_factura,cliente_id,cliente_nombre,usuario,usuario_id,dia_operativo,
                tipo_venta,metodo_pago,observacion,estado,anulado,ganancia_bruta,
                tipo_documento,es_factura_fiscal,
                migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',(v_record ->> 'fecha')::date,coalesce((v_record ->> 'total')::numeric,0),
                coalesce((v_record ->> 'total')::numeric,0),coalesce((v_record ->> 'total')::numeric,0),0,0,
                left(trim(v_record ->> 'numero_factura'),80),v_cliente_id,
                left(coalesce(v_record ->> 'cliente_nombre','CONTADO'),240),
                left(coalesce(v_record ->> 'usuario','Migracion historica'),160),v_uid,
                v_record ->> 'fecha','MIGRACION_HISTORICA',left(coalesce(v_record ->> 'metodo_pago','sin_clasificar'),60),
                left(coalesce(v_record ->> 'observacion',''),500),
                left(coalesce(v_record ->> 'estado','completada'),40),false,
                coalesce((v_record ->> 'ganancia_bruta')::numeric,0),'HISTORICA_NO_FISCAL',false,
                v_package,v_key,v_hash
            ) returning id,id::text into v_venta_id,v_record_id;

        elsif v_entity='ventas_pagos' then
            select vv.id into v_venta_id
            from public.ventas vv
            where vv.empresa_id='biberon01'
              and vv.numero_factura=trim(v_record ->> 'numero_factura')
            limit 1 for update;
            if v_venta_id is null then raise exception 'HISTORICAL_SALE_NOT_FOUND'; end if;
            insert into public.ventas_pagos(
                empresa_id,venta_id,metodo,monto,fecha,usuario,usuario_id,
                dia_operativo,anulado,migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',v_venta_id,left(coalesce(v_record ->> 'metodo','sin_clasificar'),60),
                coalesce((v_record ->> 'monto')::numeric,0),(v_record ->> 'fecha')::date,
                left(coalesce(v_record ->> 'usuario','Migracion historica'),160),v_uid,
                v_record ->> 'fecha',false,v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='cuentas_por_cobrar' then
            select vv.id,vv.cliente_id into v_venta_id,v_cliente_id
            from public.ventas vv
            where vv.empresa_id='biberon01'
              and vv.numero_factura=trim(v_record ->> 'numero_factura')
            limit 1 for update;
            if v_venta_id is null then raise exception 'HISTORICAL_SALE_NOT_FOUND'; end if;
            insert into public.cuentas_por_cobrar(
                empresa_id,cliente_id,cliente_nombre,venta_id,monto_original,monto_abonado,
                saldo_pendiente,estado,fecha,usuario,usuario_id,anulado,
                migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',v_cliente_id,left(coalesce(v_record ->> 'cliente_nombre','CONTADO'),240),v_venta_id,
                coalesce((v_record ->> 'monto_original')::numeric,0),0,
                coalesce((v_record ->> 'saldo_pendiente')::numeric,0),
                left(coalesce(v_record ->> 'estado','pendiente'),40),(v_record ->> 'fecha')::date,
                left(coalesce(v_record ->> 'usuario','Migracion historica'),160),v_uid,false,
                v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='compras' then
            insert into public.compras(
                empresa_id,fecha,numero,proveedor,rnc,descripcion,monto,total,metodo,
                cantidad,costo_unitario,costo,usuario,usuario_id,anulado,impuesto,estado,
                migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',(v_record ->> 'fecha')::date,left(coalesce(v_record ->> 'numero',''),100),
                left(coalesce(v_record ->> 'proveedor',''),240),left(coalesce(v_record ->> 'rnc',''),40),
                left(coalesce(v_record ->> 'descripcion','Compra historica'),500),
                coalesce((v_record ->> 'total')::numeric,0),coalesce((v_record ->> 'total')::numeric,0),
                left(coalesce(v_record ->> 'metodo','sin_clasificar'),60),0,0,0,
                left(coalesce(v_record ->> 'usuario','Migracion historica'),160),v_uid,false,
                coalesce((v_record ->> 'impuesto')::numeric,0),left(coalesce(v_record ->> 'estado','pagada'),40),
                v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='gastos' then
            insert into public.gastos(
                empresa_id,fecha,nombre,tipo,categoria,monto,metodo_pago,impuesto,
                responsable,detalle,migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',(v_record ->> 'fecha')::date,left(coalesce(v_record ->> 'nombre',''),240),
                left(coalesce(v_record ->> 'tipo','variable'),40),left(coalesce(v_record ->> 'categoria',''),120),
                coalesce((v_record ->> 'monto')::numeric,0),left(coalesce(v_record ->> 'metodo_pago','sin_clasificar'),60),
                coalesce((v_record ->> 'impuesto')::numeric,0),left(coalesce(v_record ->> 'responsable','Migracion historica'),160),
                left(coalesce(v_record ->> 'detalle',''),1000),v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='gastos_dueno' then
            insert into public.gastos_dueno(
                empresa_id,fecha,concepto,monto,metodo_pago,detalle,tipo_movimiento,
                migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',(v_record ->> 'fecha')::date,left(coalesce(v_record ->> 'concepto',''),300),
                coalesce((v_record ->> 'monto')::numeric,0),left(coalesce(v_record ->> 'metodo_pago','sin_clasificar'),60),
                left(coalesce(v_record ->> 'detalle',''),1000),left(coalesce(v_record ->> 'tipo_movimiento','retiro_dueño'),80),
                v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='empleados' then
            select e.id::text into v_empleado_id
            from public.empleados e
            where e.empresa_id='biberon01'
              and lower(trim(coalesce(e.nombre,'')))=lower(trim(v_record ->> 'nombre'))
            limit 1 for update;
            if v_empleado_id is null then
                insert into public.empleados(
                    empresa_id,fecha,nombre,puesto,sueldo,salario_mensual,tipo_salario,
                    frecuencia_pago,activo,observacion,
                    migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
                ) values (
                    'biberon01',current_date,left(trim(v_record ->> 'nombre'),240),
                    left(coalesce(v_record ->> 'puesto',''),120),coalesce((v_record ->> 'sueldo')::numeric,0),
                    coalesce((v_record ->> 'salario_mensual')::numeric,0),
                    left(coalesce(v_record ->> 'tipo_salario','fijo'),40),
                    left(coalesce(v_record ->> 'frecuencia_pago','quincenal'),40),
                    coalesce((v_record ->> 'activo')::boolean,true),left(coalesce(v_record ->> 'observacion',''),1000),
                    v_package,v_key,v_hash
                ) returning id::text into v_empleado_id;
            else
                update public.empleados set
                    puesto=left(coalesce(v_record ->> 'puesto',''),120),
                    sueldo=coalesce((v_record ->> 'sueldo')::numeric,0),
                    salario_mensual=coalesce((v_record ->> 'salario_mensual')::numeric,0),
                    tipo_salario=left(coalesce(v_record ->> 'tipo_salario','fijo'),40),
                    frecuencia_pago=left(coalesce(v_record ->> 'frecuencia_pago','quincenal'),40),
                    activo=coalesce((v_record ->> 'activo')::boolean,true),
                    observacion=left(coalesce(v_record ->> 'observacion',''),1000),
                    migracion_paquete_id=v_package,migracion_clave_origen=v_key,migracion_hash_origen=v_hash
                where id::text=v_empleado_id and empresa_id='biberon01';
            end if;
            v_record_id := v_empleado_id;

        elsif v_entity='pagos_empleados' then
            select e.id::text into v_empleado_id
            from public.empleados e
            where e.empresa_id='biberon01'
              and lower(trim(coalesce(e.nombre,'')))=lower(trim(v_record ->> 'empleado'))
            limit 1;
            if v_empleado_id is null then raise exception 'HISTORICAL_EMPLOYEE_NOT_FOUND'; end if;
            insert into public.pagos_empleados(
                empresa_id,empleado_id,empleado,fecha,periodo,sueldo_bruto,neto_pagar,monto,
                metodo_pago,observacion,usuario,usuario_id,
                migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',v_empleado_id,left(coalesce(v_record ->> 'empleado',''),240),
                (v_record ->> 'fecha')::date,left(coalesce(v_record ->> 'periodo','historico'),80),
                coalesce((v_record ->> 'sueldo_bruto')::numeric,0),coalesce((v_record ->> 'neto_pagar')::numeric,0),
                coalesce((v_record ->> 'monto')::numeric,0),left(coalesce(v_record ->> 'metodo_pago','sin_clasificar'),60),
                left(coalesce(v_record ->> 'observacion',''),1000),
                left(coalesce(v_record ->> 'usuario','Migracion historica'),160),v_uid,
                v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='perdidas' then
            insert into public.perdidas(
                empresa_id,fecha,producto,cantidad,costo_unitario,valor,tipo_perdida,
                observacion,estado,reportado_por,
                migracion_paquete_id,migracion_clave_origen,migracion_hash_origen
            ) values (
                'biberon01',(v_record ->> 'fecha')::date,left(coalesce(v_record ->> 'producto',''),240),
                coalesce((v_record ->> 'cantidad')::numeric,0),coalesce((v_record ->> 'costo_unitario')::numeric,0),
                coalesce((v_record ->> 'valor')::numeric,0),left(coalesce(v_record ->> 'tipo_perdida','merma'),80),
                left(coalesce(v_record ->> 'observacion',''),1000),left(coalesce(v_record ->> 'estado','aprobada'),40),
                left(coalesce(v_record ->> 'reportado_por','Migracion historica'),160),
                v_package,v_key,v_hash
            ) returning id::text into v_record_id;

        elsif v_entity='ventas_producto_historico' then
            insert into public.ventas_producto_historico(
                empresa_id,paquete_id,clave_origen,hash_origen,codigo,producto,cantidad,
                costo_unitario,costo_total,descuento,total_vendido,utilidad,desde,hasta
            ) values (
                'biberon01',v_package,v_key,v_hash,left(coalesce(v_record ->> 'codigo',''),120),
                left(coalesce(v_record ->> 'producto',''),240),coalesce((v_record ->> 'cantidad')::numeric,0),
                coalesce((v_record ->> 'costo_unitario')::numeric,0),coalesce((v_record ->> 'costo_total')::numeric,0),
                coalesce((v_record ->> 'descuento')::numeric,0),coalesce((v_record ->> 'total_vendido')::numeric,0),
                coalesce((v_record ->> 'utilidad')::numeric,0),nullif(v_record ->> 'desde','')::date,
                nullif(v_record ->> 'hasta','')::date
            ) returning id::text into v_record_id;
        end if;

        insert into public.importaciones_historicas(
            empresa_id,paquete_id,entidad,clave_origen,hash_origen,registro_id,importado_por
        ) values ('biberon01',v_package,v_entity,v_key,v_hash,v_record_id,v_uid);
        v_inserted := v_inserted+1;
    end loop;

    if v_entity='ventas' then
        insert into public.secuencia_documentos(empresa_id,sucursal_id,tipo,siguiente)
        select 'biberon01','','factura_historica_cff',
               coalesce(max(substring(numero_factura from '([0-9]+)$')::bigint),0)+1
        from public.ventas
        where empresa_id='biberon01' and numero_factura ~ '^CFF-[0-9]+$'
        on conflict (empresa_id,sucursal_id,tipo) do update
        set siguiente=greatest(public.secuencia_documentos.siguiente,excluded.siguiente),
            updated_at=now();
    end if;

    return jsonb_build_object(
        'success',true,'tenant_id','biberon01','package_id',v_package,
        'entity',v_entity,'inserted',v_inserted,'skipped',v_skipped
    );
end
$$;

create or replace function public.api_validar_importacion_biberon(p_package_id text)
returns jsonb
language plpgsql
security definer
set search_path=public,auth,pg_temp
as $$
declare
    v_uid uuid;
    v_entities jsonb;
    v_max_invoice text;
    v_next bigint;
begin
    v_uid := public.biberon_import_actor();
    if coalesce(p_package_id,'') !~ '^biberon01-hasta-[0-9]{4}-[0-9]{2}-[0-9]{2}-v[0-9]+$' then
        raise exception 'INVALID_IMPORT_PACKAGE';
    end if;

    select coalesce(jsonb_object_agg(entidad,cantidad),'{}'::jsonb)
    into v_entities
    from (
        select entidad,count(*) as cantidad
        from public.importaciones_historicas
        where empresa_id='biberon01' and paquete_id=p_package_id
        group by entidad
        order by entidad
    ) s;

    select numero_factura,
           substring(numero_factura from '([0-9]+)$')::bigint+1
    into v_max_invoice,v_next
    from public.ventas
    where empresa_id='biberon01' and numero_factura ~ '^CFF-[0-9]+$'
    order by substring(numero_factura from '([0-9]+)$')::bigint desc
    limit 1;

    return jsonb_build_object(
        'success',true,
        'tenant_id','biberon01',
        'package_id',p_package_id,
        'entities',v_entities,
        'sales_total',coalesce((select round(sum(total),2) from public.ventas where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'payments_total',coalesce((select round(sum(monto),2) from public.ventas_pagos where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'receivables_total',coalesce((select round(sum(saldo_pendiente),2) from public.cuentas_por_cobrar where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'purchases_total',coalesce((select round(sum(total),2) from public.compras where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'expenses_total',coalesce((select round(sum(monto),2) from public.gastos where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'owner_expenses_total',coalesce((select round(sum(monto),2) from public.gastos_dueno where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'payroll_total',coalesce((select round(sum(monto),2) from public.pagos_empleados where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'losses_total',coalesce((select round(sum(valor),2) from public.perdidas where empresa_id='biberon01' and migracion_paquete_id=p_package_id),0),
        'max_historical_invoice',v_max_invoice,
        'next_historical_invoice',coalesce(v_next,1)
    );
end
$$;

revoke all on function public.api_prevalidar_migracion_biberon() from public,anon;
revoke all on function public.api_importar_historial_biberon(jsonb) from public,anon;
revoke all on function public.api_validar_importacion_biberon(text) from public,anon;
grant execute on function public.api_prevalidar_migracion_biberon() to authenticated;
grant execute on function public.api_importar_historial_biberon(jsonb) to authenticated;
grant execute on function public.api_validar_importacion_biberon(text) to authenticated;

commit;
