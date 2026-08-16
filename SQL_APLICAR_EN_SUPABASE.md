# SQL único para aplicar AIS en Supabase

Este documento es la única guía de ejecución SQL para esta versión. Úselo primero en un proyecto **staging**, con un respaldo verificado. Ejecute cada bloque completo y por separado, en el orden numerado. No continúe si el bloque 0 informa tablas faltantes, tipos incompatibles, perfiles sin vínculo con Auth, filas sin `empresa_id` o cajas abiertas duplicadas.

Los bloques 1, 2 y 3 son transaccionales: cada uno finaliza con `COMMIT`; cualquier error antes de ese punto revierte por completo ese bloque. El bloque 4 es de solo lectura y debe revisarse antes de habilitar usuarios.

## 0. Preflight de solo lectura

```sql
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
```

## 1. Base segura, Auth, tenants, RLS y tablas canónicas

```sql
-- A&M v3.0 — Base de seguridad, RLS y API transaccional
-- Ejecutar primero en STAGING. Esta migración conserva los datos operativos,
-- pero invalida material de acceso legado que ya fue sustituido por Supabase Auth.

begin;

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Identidad y empresas
-- ---------------------------------------------------------------------------
create table if not exists public.empresas (
    tenant_id text primary key,
    nombre text not null,
    activo boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.tenant_memberships (
    user_id uuid not null references auth.users(id) on delete cascade,
    tenant_id text not null references public.empresas(tenant_id) on delete cascade,
    role text not null check (role in ('admin','gerente','supervisor','cajero','cajera','consulta')),
    permissions jsonb not null default '{}'::jsonb,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, tenant_id)
);

-- Las instalaciones anteriores ya tenían esta tabla con menos columnas.
alter table public.tenant_memberships add column if not exists permissions jsonb not null default '{}'::jsonb;
alter table public.tenant_memberships add column if not exists active boolean not null default true;
alter table public.tenant_memberships add column if not exists updated_at timestamptz not null default now();

-- Incluso la service-role debe conservar por lo menos una administración
-- activa por empresa. El bloqueo evita que dos cambios simultáneos retiren a
-- los dos últimos administradores.
create or replace function public.protect_last_tenant_admin()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_removing_admin boolean := false;
begin
    if old.role='admin' and old.active then
        if tg_op='DELETE' then
            v_removing_admin := true;
        else
            v_removing_admin := new.role<>'admin' or not new.active;
        end if;
    end if;
    if v_removing_admin then
        perform pg_advisory_xact_lock(hashtext('tenant-admin:' || old.tenant_id));
        if not exists (
            select 1
            from public.tenant_memberships tm
            where tm.tenant_id=old.tenant_id
              and tm.user_id<>old.user_id
              and tm.role='admin'
              and tm.active
        ) then
            raise exception 'TENANT_MUST_KEEP_ONE_ACTIVE_ADMIN';
        end if;
    end if;
    return case when tg_op='DELETE' then old else new end;
end;
$$;

drop trigger if exists trg_protect_last_tenant_admin on public.tenant_memberships;
create trigger trg_protect_last_tenant_admin
before update or delete on public.tenant_memberships
for each row execute function public.protect_last_tenant_admin();
revoke all on function public.protect_last_tenant_admin() from public, anon, authenticated;

create table if not exists public.usuarios (
    id uuid primary key default gen_random_uuid(),
    user_id uuid unique references auth.users(id) on delete cascade,
    empresa_id text references public.empresas(tenant_id),
    email text,
    email_login text,
    usuario text,
    nombre text,
    rol text,
    permissions jsonb not null default '{}'::jsonb,
    activo boolean not null default true,
    legacy_login_disabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table if exists public.usuarios add column if not exists user_id uuid;
alter table if exists public.usuarios add column if not exists empresa_id text;
alter table if exists public.usuarios add column if not exists email text;
alter table if exists public.usuarios add column if not exists email_login text;
alter table if exists public.usuarios add column if not exists permissions jsonb not null default '{}'::jsonb;
alter table if exists public.usuarios add column if not exists legacy_login_disabled boolean not null default true;
alter table if exists public.usuarios add column if not exists updated_at timestamptz not null default now();
create unique index if not exists uq_usuarios_user_id on public.usuarios(user_id) where user_id is not null;
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid='public.usuarios'::regclass
          and conname='usuarios_user_id_fkey'
    ) then
        alter table public.usuarios
            add constraint usuarios_user_id_fkey
            foreign key (user_id) references auth.users(id)
            on delete cascade not valid;
    end if;
end
$$;
alter table public.usuarios validate constraint usuarios_user_id_fkey;

-- Instalaciones que ya usaban auth.uid() como usuarios.id se enlazan sin
-- inventar identidades. Si el id legado no es UUID, el perfil queda pendiente
-- de provisión explícita.
do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema='public'
          and table_name='usuarios'
          and column_name='id'
          and udt_name='uuid'
    ) then
        execute $link$
            update public.usuarios u
            set user_id=u.id
            where u.user_id is null
              and exists (select 1 from auth.users au where au.id=u.id)
        $link$;
    end if;
end
$$;

-- Las credenciales pertenecen exclusivamente a auth.users. Se invalidan copias
-- heredadas para que ningún administrador de empresa pueda leer hashes o TOTP
-- desde PostgREST. Esto obliga a provisionar/restablecer las cuentas históricas.
do $$
declare
    v_column text;
begin
    foreach v_column in array array['clave','password','password_hash','totp_secret']
    loop
        if exists (
            select 1
            from information_schema.columns
        where table_schema='public'
              and table_name='usuarios'
              and column_name=v_column
        ) then
            execute format(
                'alter table public.usuarios alter column %I drop not null',
                v_column
            );
            execute format(
                'alter table public.usuarios alter column %I drop default',
                v_column
            );
            execute format('update public.usuarios set %I = null where %I is not null', v_column, v_column);
        end if;
    end loop;
    if exists (
        select 1
        from information_schema.columns
        where table_schema='public'
          and table_name='configuracion_sistema'
          and column_name='clave'
    ) then
        execute 'alter table public.configuracion_sistema alter column clave drop not null';
        execute 'alter table public.configuracion_sistema alter column clave drop default';
        execute 'update public.configuracion_sistema set clave=null where clave is not null';
    end if;
end
$$;

alter table if exists public.configuracion_sistema add column if not exists empresa_id text;
do $$
begin
    if to_regclass('public.configuracion_sistema') is not null then
        update public.configuracion_sistema
        set empresa_id = nullif(trim(propietario),'')
        where empresa_id is null and propietario is not null;
    end if;
end
$$;

-- Conserva la relación histórica email=empresa solo para ayudar a la migración.
update public.usuarios
set empresa_id = nullif(trim(email), '')
where empresa_id is null
  and email is not null
  and position('@' in email) = 0
  and trim(email) <> 'global';

insert into public.empresas(tenant_id, nombre)
select distinct empresa_id, initcap(empresa_id)
from public.usuarios
where empresa_id is not null and trim(empresa_id) <> ''
on conflict (tenant_id) do nothing;

insert into public.empresas(tenant_id, nombre)
select distinct tm.tenant_id, initcap(tm.tenant_id)
from public.tenant_memberships tm
where tm.tenant_id is not null and trim(tm.tenant_id)<>''
on conflict (tenant_id) do nothing;

insert into public.empresas(tenant_id, nombre)
select distinct cs.empresa_id, coalesce(nullif(trim(cs.negocio_nombre),''),initcap(cs.empresa_id))
from public.configuracion_sistema cs
where cs.empresa_id is not null and trim(cs.empresa_id)<>''
on conflict (tenant_id) do nothing;

-- ---------------------------------------------------------------------------
-- Columnas mínimas requeridas por la API segura
-- ---------------------------------------------------------------------------
-- Todas las tablas multiempresa deben tener una clave de empresa. Las filas
-- históricas sin empresa quedan deliberadamente invisibles hasta clasificarlas.
do $$
declare
    v_table text;
begin
    foreach v_table in array array[
        'productos','clientes','proveedores','compras','facturas_compra',
        'detalle_factura_compra','gastos','empleados',
        'pagos_empleados','perdidas','gastos_dueno','activos_fijos','capital_base',
        'ajustes_inventario','conteo_inventario','inventario_actual','inventario_lotes','sucursales',
        'configuracion_sistema','ventas','detalle_venta','ventas_pagos',
        'movimientos_caja','caja','cuentas_por_cobrar','abonos_credito',
        'abonos_proveedores','adelantos_empleados','catalogo_gastos',
        'configuracion_financiera','cuentas_dinero','depreciacion','depreciaciones',
        'distribucion_beneficios','movimientos','movimientos_dinero',
        'notas_credito','pagos_proveedores','secuencia_ncf',
        'suscripciones_empresas'
    ]
    loop
        if to_regclass('public.' || v_table) is not null then
            execute format(
                'alter table public.%I add column if not exists empresa_id text',
                v_table
            );
        end if;
    end loop;
end
$$;

alter table if exists public.productos add column if not exists empresa_id text;
alter table if exists public.productos add column if not exists nombre text;
alter table if exists public.productos add column if not exists codigo text;
alter table if exists public.productos add column if not exists codigo_barra text;
alter table if exists public.productos add column if not exists activo boolean not null default true;
alter table if exists public.productos add column if not exists anulado boolean not null default false;
alter table if exists public.productos add column if not exists stock numeric(18,4) not null default 0;
alter table if exists public.productos add column if not exists existencia numeric(18,4) not null default 0;
alter table if exists public.productos add column if not exists cantidad numeric(18,4) not null default 0;
alter table if exists public.productos add column if not exists precio numeric(18,2);
alter table if exists public.productos add column if not exists precio_venta numeric(18,2);
alter table if exists public.productos add column if not exists precio_descuento numeric(18,2);
alter table if exists public.productos add column if not exists costo numeric(18,4);
alter table if exists public.productos add column if not exists costo_unitario numeric(18,4);
alter table if exists public.productos add column if not exists itbis_gravado boolean not null default true;
alter table if exists public.productos add column if not exists itbis_tasa numeric(6,3) not null default 18;
alter table if exists public.productos add column if not exists precio_minimo numeric(18,2);
alter table if exists public.productos add column if not exists updated_at timestamptz not null default now();

alter table if exists public.ventas add column if not exists empresa_id text;
alter table if exists public.ventas add column if not exists fecha timestamptz not null default now();
alter table if exists public.ventas add column if not exists total numeric(18,2) not null default 0;
alter table if exists public.ventas add column if not exists subtotal numeric(18,2) not null default 0;
alter table if exists public.ventas add column if not exists subtotal_gravado numeric(18,2) not null default 0;
alter table if exists public.ventas add column if not exists subtotal_exento numeric(18,2) not null default 0;
alter table if exists public.ventas add column if not exists itbis_total numeric(18,2) not null default 0;
alter table if exists public.ventas add column if not exists numero_factura text;
alter table if exists public.ventas add column if not exists cliente_id bigint;
alter table if exists public.ventas add column if not exists cliente_nombre text;
alter table if exists public.ventas add column if not exists usuario text;
alter table if exists public.ventas add column if not exists dia_operativo text;
alter table if exists public.ventas add column if not exists caja_id uuid;
alter table if exists public.ventas add column if not exists tipo_venta text;
alter table if exists public.ventas add column if not exists metodo_pago text;
alter table if exists public.ventas add column if not exists observacion text;
alter table if exists public.ventas add column if not exists estado text;
alter table if exists public.ventas add column if not exists anulado boolean not null default false;
alter table if exists public.ventas add column if not exists motivo_anulacion text;
alter table if exists public.ventas add column if not exists ncf text;
alter table if exists public.ventas add column if not exists ganancia_bruta numeric(18,2) not null default 0;
alter table if exists public.ventas add column if not exists tipo_documento text;
alter table if exists public.ventas add column if not exists es_factura_fiscal boolean not null default false;
alter table if exists public.ventas add column if not exists usuario_id uuid;
alter table if exists public.ventas add column if not exists anulada_por uuid;
alter table if exists public.ventas add column if not exists anulada_at timestamptz;
alter table if exists public.ventas add column if not exists updated_at timestamptz not null default now();

alter table if exists public.detalle_venta add column if not exists empresa_id text;
alter table if exists public.detalle_venta add column if not exists venta_id uuid;
alter table if exists public.detalle_venta add column if not exists producto_id uuid;
alter table if exists public.detalle_venta add column if not exists codigo text;
alter table if exists public.detalle_venta add column if not exists producto text;
alter table if exists public.detalle_venta add column if not exists cantidad numeric(18,4) not null default 0;
alter table if exists public.detalle_venta add column if not exists precio numeric(18,2) not null default 0;
alter table if exists public.detalle_venta add column if not exists precio_unitario numeric(18,2) not null default 0;
alter table if exists public.detalle_venta add column if not exists total_linea numeric(18,2) not null default 0;
alter table if exists public.detalle_venta add column if not exists costo numeric(18,4) not null default 0;
alter table if exists public.detalle_venta add column if not exists costo_unitario numeric(18,4) not null default 0;
alter table if exists public.detalle_venta add column if not exists ganancia_linea numeric(18,2) not null default 0;
alter table if exists public.detalle_venta add column if not exists usuario text;
alter table if exists public.detalle_venta add column if not exists fecha timestamptz not null default now();
alter table if exists public.detalle_venta add column if not exists anulado boolean not null default false;
alter table if exists public.detalle_venta add column if not exists motivo_anulacion text;
alter table if exists public.detalle_venta add column if not exists subtotal numeric(18,2) not null default 0;
alter table if exists public.detalle_venta add column if not exists itbis_gravado boolean not null default true;
alter table if exists public.detalle_venta add column if not exists itbis_tasa numeric(6,3) not null default 18;
alter table if exists public.detalle_venta add column if not exists itbis_monto numeric(18,2) not null default 0;
alter table if exists public.detalle_venta add column if not exists costo_total numeric(18,2) not null default 0;

alter table if exists public.ventas_pagos add column if not exists empresa_id text;
alter table if exists public.ventas_pagos add column if not exists venta_id uuid;
alter table if exists public.ventas_pagos add column if not exists metodo text;
alter table if exists public.ventas_pagos add column if not exists monto numeric(18,2) not null default 0;
alter table if exists public.ventas_pagos add column if not exists usuario text;
alter table if exists public.ventas_pagos add column if not exists usuario_id uuid;
alter table if exists public.ventas_pagos add column if not exists caja_id uuid;
alter table if exists public.ventas_pagos add column if not exists dia_operativo text;
alter table if exists public.ventas_pagos add column if not exists anulado boolean not null default false;

alter table if exists public.movimientos_caja add column if not exists empresa_id text;
alter table if exists public.movimientos_caja add column if not exists fecha timestamptz not null default now();
alter table if exists public.movimientos_caja add column if not exists dia_operativo text;
alter table if exists public.movimientos_caja add column if not exists caja_id uuid;
alter table if exists public.movimientos_caja add column if not exists tipo_movimiento text;
alter table if exists public.movimientos_caja add column if not exists origen text;
alter table if exists public.movimientos_caja add column if not exists referencia_id text;
alter table if exists public.movimientos_caja add column if not exists metodo_pago text;
alter table if exists public.movimientos_caja add column if not exists monto numeric(18,2) not null default 0;
alter table if exists public.movimientos_caja add column if not exists descripcion text;
alter table if exists public.movimientos_caja add column if not exists usuario text;
alter table if exists public.movimientos_caja add column if not exists usuario_id uuid;
alter table if exists public.movimientos_caja add column if not exists anulado boolean not null default false;

alter table if exists public.caja add column if not exists empresa_id text;
alter table if exists public.caja add column if not exists usuario_id uuid;
alter table if exists public.caja add column if not exists usuario text;
alter table if exists public.caja add column if not exists fecha_apertura timestamptz not null default now();
alter table if exists public.caja add column if not exists fecha_cierre timestamptz;
alter table if exists public.caja add column if not exists dia_operativo text;
alter table if exists public.caja add column if not exists monto_inicial numeric(18,2) not null default 0;
alter table if exists public.caja add column if not exists efectivo_inicial numeric(18,2) not null default 0;
alter table if exists public.caja add column if not exists efectivo_contado numeric(18,2);
alter table if exists public.caja add column if not exists efectivo_esperado numeric(18,2);
alter table if exists public.caja add column if not exists diferencia numeric(18,2);
alter table if exists public.caja add column if not exists faltante numeric(18,2);
alter table if exists public.caja add column if not exists sobrante numeric(18,2);
alter table if exists public.caja add column if not exists estado text not null default 'abierta';
alter table if exists public.caja add column if not exists observacion text;
alter table if exists public.caja add column if not exists anulado boolean not null default false;

alter table if exists public.clientes add column if not exists nombre text;
alter table if exists public.clientes add column if not exists limite_credito numeric(18,2) not null default 0;
alter table if exists public.clientes add column if not exists activo boolean not null default true;

alter table if exists public.cuentas_por_cobrar add column if not exists empresa_id text;
alter table if exists public.cuentas_por_cobrar add column if not exists anulado boolean not null default false;
alter table if exists public.cuentas_por_cobrar add column if not exists cliente_id bigint;
alter table if exists public.cuentas_por_cobrar add column if not exists cliente_nombre text;
alter table if exists public.cuentas_por_cobrar add column if not exists venta_id uuid;
alter table if exists public.cuentas_por_cobrar add column if not exists monto_original numeric(18,2) not null default 0;
alter table if exists public.cuentas_por_cobrar add column if not exists monto_abonado numeric(18,2) not null default 0;
alter table if exists public.cuentas_por_cobrar add column if not exists saldo_pendiente numeric(18,2) not null default 0;
alter table if exists public.cuentas_por_cobrar add column if not exists estado text not null default 'pendiente';
alter table if exists public.cuentas_por_cobrar add column if not exists fecha timestamptz not null default now();
alter table if exists public.cuentas_por_cobrar add column if not exists usuario text;
alter table if exists public.cuentas_por_cobrar add column if not exists usuario_id uuid;

alter table if exists public.abonos_credito add column if not exists empresa_id text;
alter table if exists public.abonos_credito add column if not exists cuenta_id bigint;
alter table if exists public.abonos_credito add column if not exists cliente_id bigint;
alter table if exists public.abonos_credito add column if not exists cliente_nombre text;
alter table if exists public.abonos_credito add column if not exists monto numeric(18,2) not null default 0;
alter table if exists public.abonos_credito add column if not exists metodo_pago text;
alter table if exists public.abonos_credito add column if not exists fecha timestamptz not null default now();
alter table if exists public.abonos_credito add column if not exists usuario text;
alter table if exists public.abonos_credito add column if not exists observacion text;
alter table if exists public.abonos_credito add column if not exists usuario_id uuid;
alter table if exists public.abonos_credito add column if not exists caja_id uuid;

alter table if exists public.compras add column if not exists empresa_id text;
alter table if exists public.compras add column if not exists fecha timestamptz not null default now();
alter table if exists public.compras add column if not exists numero text;
alter table if exists public.compras add column if not exists proveedor text;
alter table if exists public.compras add column if not exists descripcion text;
alter table if exists public.compras add column if not exists monto numeric(18,2) not null default 0;
alter table if exists public.compras add column if not exists total numeric(18,2) not null default 0;
alter table if exists public.compras add column if not exists metodo text;
alter table if exists public.compras add column if not exists producto_id uuid;
alter table if exists public.compras add column if not exists producto text;
alter table if exists public.compras add column if not exists cantidad numeric(18,4) not null default 0;
alter table if exists public.compras add column if not exists costo_unitario numeric(18,4) not null default 0;
alter table if exists public.compras add column if not exists costo numeric(18,4) not null default 0;
alter table if exists public.compras add column if not exists usuario text;
alter table if exists public.compras add column if not exists usuario_id uuid;
alter table if exists public.compras add column if not exists anulado boolean not null default false;
alter table if exists public.compras add column if not exists monto_abonado numeric(18,2) not null default 0;
alter table if exists public.compras add column if not exists saldo_pendiente numeric(18,2) not null default 0;
alter table if exists public.compras add column if not exists factura_compra_id uuid;

-- Cabecera y detalle canónicos de una factura de compra. La tabla histórica
-- compras continúa recibiendo una fila por producto para conservar reportes.
create table if not exists public.facturas_compra (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    idempotency_key uuid not null,
    request_hash text not null,
    fecha timestamptz not null default now(),
    numero text not null,
    referencia text,
    proveedor text not null,
    descripcion text,
    metodo text not null,
    total numeric(18,2) not null check (total >= 0),
    monto_abonado numeric(18,2) not null default 0,
    saldo_pendiente numeric(18,2) not null default 0,
    usuario text,
    usuario_id uuid not null,
    created_at timestamptz not null default now(),
    unique (empresa_id, idempotency_key)
);

create table if not exists public.detalle_factura_compra (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    factura_id uuid not null references public.facturas_compra(id),
    compra_id uuid,
    producto_id uuid not null,
    producto text not null,
    cantidad numeric(18,4) not null check (cantidad > 0),
    costo_unitario numeric(18,4) not null check (costo_unitario >= 0),
    total_linea numeric(18,2) not null check (total_linea >= 0),
    created_at timestamptz not null default now(),
    unique (factura_id, producto_id)
);

create index if not exists idx_facturas_compra_empresa_fecha
    on public.facturas_compra(empresa_id, fecha desc);
create index if not exists idx_detalle_factura_compra_factura
    on public.detalle_factura_compra(factura_id);

create table if not exists public.movimientos_contables (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    fecha timestamptz not null default now(),
    modulo text,
    referencia_id text,
    cuenta_codigo text,
    cuenta_nombre text,
    tipo_cuenta text,
    debito numeric(18,2) not null default 0,
    credito numeric(18,2) not null default 0,
    descripcion text,
    usuario text,
    usuario_id uuid,
    created_at timestamptz not null default now()
);
alter table if exists public.movimientos_contables add column if not exists empresa_id text;
alter table if exists public.movimientos_contables add column if not exists modulo text;
alter table if exists public.movimientos_contables add column if not exists referencia_id text;
alter table if exists public.movimientos_contables add column if not exists cuenta_codigo text;
alter table if exists public.movimientos_contables add column if not exists cuenta_nombre text;
alter table if exists public.movimientos_contables add column if not exists tipo_cuenta text;
alter table if exists public.movimientos_contables add column if not exists debito numeric(18,2) not null default 0;
alter table if exists public.movimientos_contables add column if not exists credito numeric(18,2) not null default 0;
alter table if exists public.movimientos_contables add column if not exists descripcion text;
alter table if exists public.movimientos_contables add column if not exists fecha timestamptz not null default now();
alter table if exists public.movimientos_contables add column if not exists usuario text;
alter table if exists public.movimientos_contables add column if not exists usuario_id uuid;
alter table if exists public.empleados add column if not exists empresa_id text;
alter table if exists public.empleados add column if not exists salario_mensual numeric(18,2);
alter table if exists public.empleados add column if not exists sueldo numeric(18,2);
alter table if exists public.empleados add column if not exists arl_tasa numeric(8,6);
alter table if exists public.empleados add column if not exists activo boolean not null default true;
alter table if exists public.pagos_empleados add column if not exists empresa_id text;
-- La instalación auditada relaciona empleados BIGINT con pagos mediante TEXT.
-- Se conserva ese contrato para no convertir ni perder identificadores históricos.
alter table if exists public.pagos_empleados add column if not exists empleado_id text;
alter table if exists public.pagos_empleados add column if not exists empleado text;
alter table if exists public.pagos_empleados add column if not exists fecha date not null default current_date;
alter table if exists public.pagos_empleados add column if not exists periodo text;
alter table if exists public.pagos_empleados add column if not exists sueldo_bruto numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists sfs_empleado numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists afp_empleado numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists isr numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists neto_pagar numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists sfs_empleador numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists afp_empleador numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists arl_empleador numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists infotep_empleador numeric(18,2) not null default 0;
alter table if exists public.pagos_empleados add column if not exists metodo_pago text;
alter table if exists public.pagos_empleados add column if not exists observacion text;
alter table if exists public.pagos_empleados add column if not exists usuario text;
alter table if exists public.pagos_empleados add column if not exists usuario_id uuid;
alter table if exists public.pagos_empleados add column if not exists monto numeric(18,2) not null default 0;

create table if not exists public.inventario_lotes (
    id bigint generated by default as identity primary key,
    empresa_id text not null,
    producto_id uuid not null,
    compra_id uuid,
    producto text,
    cantidad_inicial numeric(18,4) not null check (cantidad_inicial > 0),
    cantidad_restante numeric(18,4) not null check (cantidad_restante >= 0),
    costo_unitario numeric(18,4) not null check (costo_unitario >= 0),
    fecha_compra timestamptz not null default now(),
    activo boolean not null default true,
    created_at timestamptz not null default now()
);
-- Tipos verificados en la instalación objetivo:
-- inventario_lotes.id=BIGINT y compras.id/inventario_lotes.compra_id=UUID.
alter table public.inventario_lotes add column if not exists compra_id uuid;
alter table public.inventario_lotes add column if not exists producto text;
do $$
begin
    -- Primero se hereda la empresa de la compra relacionada.
    if to_regclass('public.compras') is not null then
        update public.inventario_lotes il
        set empresa_id=c.empresa_id
        from public.compras c
        where il.empresa_id is null
          and il.compra_id=c.id
          and c.empresa_id is not null;
    end if;

    -- Los lotes sin compra (por ejemplo, inventario inicial) se clasifican
    -- usando el producto al que pertenecen.
    if to_regclass('public.productos') is not null then
        update public.inventario_lotes il
        set empresa_id=p.empresa_id
        from public.productos p
        where il.empresa_id is null
          and il.producto_id=p.id
          and p.empresa_id is not null;
    end if;
end
$$;

create table if not exists public.inventario_consumos (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    venta_id uuid not null,
    detalle_id uuid,
    producto_id uuid not null,
    lote_id bigint references public.inventario_lotes(id),
    cantidad numeric(18,4) not null check (cantidad > 0),
    costo_unitario numeric(18,4) not null check (costo_unitario >= 0),
    restaurado boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.secuencia_documentos (
    empresa_id text not null,
    sucursal_id text not null default '',
    tipo text not null,
    siguiente bigint not null default 1 check (siguiente > 0),
    updated_at timestamptz not null default now(),
    primary key (empresa_id, sucursal_id, tipo)
);

create table if not exists public.cierre_caja (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    caja_id uuid not null,
    usuario_id uuid not null,
    fecha timestamptz not null default now(),
    monto_inicial numeric(18,2) not null default 0,
    efectivo_esperado numeric(18,2) not null default 0,
    efectivo_contado numeric(18,2) not null default 0,
    diferencia numeric(18,2) not null default 0,
    observacion text,
    unique (caja_id)
);

create table if not exists public.periodos_contables (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    ano integer not null check (ano between 2000 and 2200),
    mes integer not null check (mes between 1 and 12),
    estado text not null default 'cerrado' check (estado in ('abierto','cerrado','reabierto')),
    cerrado_por uuid,
    cerrado_at timestamptz,
    observacion text,
    resumen jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (empresa_id, ano, mes)
);

-- Compatibilidad con la tabla histórica, que solo guardaba "periodo=YYYY-MM".
alter table public.periodos_contables add column if not exists ano integer;
alter table public.periodos_contables add column if not exists mes integer;
alter table public.periodos_contables add column if not exists cerrado_por uuid;
alter table public.periodos_contables add column if not exists cerrado_at timestamptz;
alter table public.periodos_contables add column if not exists observacion text;
alter table public.periodos_contables add column if not exists resumen jsonb not null default '{}'::jsonb;
alter table public.periodos_contables add column if not exists updated_at timestamptz not null default now();
do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema='public' and table_name='periodos_contables' and column_name='periodo'
    ) then
        update public.periodos_contables
        set ano = coalesce(ano, split_part(periodo,'-',1)::integer),
            mes = coalesce(mes, split_part(periodo,'-',2)::integer)
        where periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
          and (ano is null or mes is null);
    end if;
end
$$;
create unique index if not exists uq_periodos_empresa_ano_mes
    on public.periodos_contables(empresa_id, ano, mes)
    where ano is not null and mes is not null;

create table if not exists public.auditoria_eventos (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null,
    usuario_id text,
    usuario text,
    accion text not null,
    modulo text,
    tabla text,
    registro_id text,
    detalle text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

-- La versión anterior usaba tabla_afectada/descripcion y usuario_id TEXT.
-- Se conservan esas columnas y se agregan las canónicas sin borrar evidencia.
alter table public.auditoria_eventos add column if not exists tabla text;
alter table public.auditoria_eventos add column if not exists detalle text;
alter table public.auditoria_eventos add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table public.auditoria_eventos add column if not exists created_at timestamptz not null default now();

create table if not exists public.system_test_runs (
    id uuid primary key default gen_random_uuid(),
    empresa_id text not null default 'global',
    commit_sha text not null,
    environment text not null check (environment in ('ci','staging','production-readonly')),
    suite text not null,
    passed integer not null default 0,
    failed integer not null default 0,
    status text not null check (status in ('passed','failed','error')),
    report_url text,
    runner text not null,
    created_at timestamptz not null default now()
);

create table if not exists public.nomina_parametros (
    ano integer primary key,
    tope_sfs numeric(18,2) not null,
    tope_afp numeric(18,2) not null,
    tope_arl numeric(18,2) not null,
    sfs_empleado numeric(8,6) not null,
    afp_empleado numeric(8,6) not null,
    sfs_empleador numeric(8,6) not null,
    afp_empleador numeric(8,6) not null,
    arl_empleador numeric(8,6) not null,
    infotep_empleador numeric(8,6) not null,
    isr_tramos jsonb not null,
    fuente text not null,
    vigente_desde date not null,
    updated_at timestamptz not null default now()
);

insert into public.nomina_parametros(
    ano, tope_sfs, tope_afp, tope_arl,
    sfs_empleado, afp_empleado, sfs_empleador, afp_empleador,
    arl_empleador, infotep_empleador, isr_tramos, fuente, vigente_desde
) values (
    2026, 232230.00, 464460.00, 92892.00,
    0.0304, 0.0287, 0.0709, 0.0710,
    0.0110, 0.0100,
    '[{"desde":72260.25,"fijo":6648.00,"tasa":0.25},{"desde":52027.42,"fijo":2601.33,"tasa":0.20},{"desde":34685.00,"fijo":0,"tasa":0.15}]'::jsonb,
    'TSS/DGII 2026 — topes TSS efectivos desde febrero; validar anualmente',
    date '2026-02-01'
) on conflict (ano) do update set
    tope_sfs=excluded.tope_sfs, tope_afp=excluded.tope_afp, tope_arl=excluded.tope_arl,
    sfs_empleado=excluded.sfs_empleado,afp_empleado=excluded.afp_empleado,
    sfs_empleador=excluded.sfs_empleador,afp_empleador=excluded.afp_empleador,
    arl_empleador=excluded.arl_empleador,infotep_empleador=excluded.infotep_empleador,
    isr_tramos=excluded.isr_tramos,fuente=excluded.fuente,
    vigente_desde=excluded.vigente_desde,updated_at=now();

-- ---------------------------------------------------------------------------
-- Funciones de autorización. El JWT ya fue verificado por Supabase antes de
-- llegar a PostgreSQL; nunca se confía en nombres ni en user_metadata.
-- ---------------------------------------------------------------------------
create or replace function public.is_platform_superadmin()
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
    select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', '') = 'superadmin'
$$;

create or replace function public.has_tenant_access(p_tenant text)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
    select auth.uid() is not null and (
        (
            public.is_platform_superadmin()
            and coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2'
        )
        or exists (
            select 1
            from public.tenant_memberships tm
            join public.empresas e on e.tenant_id=tm.tenant_id and e.activo
            where tm.user_id = auth.uid()
              and tm.tenant_id = p_tenant
              and tm.active
              and (
                  tm.role <> 'admin'
                  or coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2'
              )
        )
    )
$$;

create or replace function public.has_tenant_permission(p_tenant text, p_permission text)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
    select auth.uid() is not null and (
        (
            public.is_platform_superadmin()
            and coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2'
        )
        or exists (
            select 1
            from public.tenant_memberships tm
            join public.empresas e on e.tenant_id=tm.tenant_id and e.activo
            where tm.user_id = auth.uid()
              and tm.tenant_id = p_tenant
              and tm.active
              and (
                  tm.role = 'admin'
                  or coalesce(tm.permissions -> p_permission, 'false'::jsonb) = 'true'::jsonb
              )
              and (
                  (
                      tm.role <> 'admin'
                      and p_permission not in (
                          'puede_configurar','puede_editar_todo',
                          'puede_editar_ventas','puede_anular',
                          'puede_cerrar_periodo'
                      )
                  )
                  or coalesce(auth.jwt() ->> 'aal', 'aal1') = 'aal2'
              )
        )
    )
$$;

-- Compatibilidad con tablas históricas cuyo empresa_id fue creado como UUID.
-- La autorización sigue usando tenant_id TEXT como fuente canónica y convierte
-- únicamente el identificador recibido, sin modificar datos existentes.
create or replace function public.has_tenant_access(p_tenant uuid)
returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
    select public.has_tenant_access(p_tenant::text)
$$;

create or replace function public.has_tenant_permission(
    p_tenant uuid,
    p_permission text
) returns boolean
language sql
stable
security definer
set search_path = public, auth
as $$
    select public.has_tenant_permission(p_tenant::text, p_permission)
$$;

revoke all on function public.is_platform_superadmin() from public, anon;
revoke all on function public.has_tenant_access(text) from public, anon;
revoke all on function public.has_tenant_access(uuid) from public, anon;
revoke all on function public.has_tenant_permission(text,text) from public, anon;
revoke all on function public.has_tenant_permission(uuid,text) from public, anon;
grant execute on function public.is_platform_superadmin() to authenticated;
grant execute on function public.has_tenant_access(text) to authenticated;
grant execute on function public.has_tenant_access(uuid) to authenticated;
grant execute on function public.has_tenant_permission(text,text) to authenticated;
grant execute on function public.has_tenant_permission(uuid,text) to authenticated;

create or replace function public.api_my_session(p_tenant_id text default null)
returns jsonb
language plpgsql
stable
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_super boolean := public.is_platform_superadmin();
    v_tenant text;
    v_role text;
    v_permissions jsonb := '{}'::jsonb;
    v_profile jsonb;
    v_tenants jsonb := '[]'::jsonb;
begin
    if v_uid is null then
        raise exception 'AUTH_REQUIRED';
    end if;

    select coalesce(jsonb_agg(jsonb_build_object(
        'tenant_id', tm.tenant_id,
        'nombre', e.nombre,
        'role', tm.role,
        'permissions', tm.permissions
    ) order by tm.tenant_id), '[]'::jsonb)
    into v_tenants
    from public.tenant_memberships tm
    join public.empresas e on e.tenant_id=tm.tenant_id and e.activo
    where tm.user_id = v_uid and tm.active;

    if v_super then
        v_tenant := coalesce(nullif(trim(p_tenant_id), ''), 'global');
        if v_tenant <> 'global' and not exists (
            select 1 from public.empresas e
            where e.tenant_id=v_tenant and e.activo
        ) then
            raise exception 'TENANT_NOT_ACTIVE_OR_NOT_FOUND';
        end if;
        v_role := 'superadmin';
        select coalesce(jsonb_agg(jsonb_build_object(
            'tenant_id', e.tenant_id,
            'nombre', e.nombre,
            'role', 'superadmin',
            'permissions', '{}'::jsonb
        ) order by e.tenant_id), '[]'::jsonb)
        into v_tenants
        from public.empresas e
        where e.activo;
    else
        select tm.tenant_id, tm.role, tm.permissions
        into v_tenant, v_role, v_permissions
        from public.tenant_memberships tm
        join public.empresas e on e.tenant_id=tm.tenant_id and e.activo
        where tm.user_id = v_uid
          and tm.active
          and (p_tenant_id is null or tm.tenant_id = p_tenant_id)
        order by tm.created_at
        limit 1;
        if v_tenant is null then
            raise exception 'NO_ACTIVE_MEMBERSHIP';
        end if;
    end if;

    select to_jsonb(u) - 'clave' - 'password' - 'totp_secret'
    into v_profile
    from public.usuarios u
    where u.user_id = v_uid and coalesce(u.activo, true)
    limit 1;

    if v_profile is null then
        raise exception 'PROFILE_NOT_LINKED';
    end if;

    return v_profile
        || coalesce(v_permissions, '{}'::jsonb)
        || jsonb_build_object(
            'tenant_id', v_tenant,
            'empresa_id', v_tenant,
            'rol', v_role,
            'permissions', coalesce(v_permissions, '{}'::jsonb),
            'es_superadmin', v_super,
            'aal', coalesce(auth.jwt() ->> 'aal', 'aal1'),
            'tenants', v_tenants,
            'activo', true
        );
end;
$$;

revoke all on function public.api_my_session(text) from public, anon;
grant execute on function public.api_my_session(text) to authenticated;

-- ---------------------------------------------------------------------------
-- RLS canónico.
-- ---------------------------------------------------------------------------
-- Las tablas enumeradas quedan bajo una única política canónica. Las políticas
-- antiguas se retiran dentro de esta misma transacción y se recrean enseguida.
do $$
declare
    v_table text;
    r record;
begin
    foreach v_table in array array[
        'productos','clientes','proveedores','compras','facturas_compra',
        'detalle_factura_compra','gastos','empleados',
        'pagos_empleados','perdidas','gastos_dueno','activos_fijos','capital_base',
        'ajustes_inventario','conteo_inventario','inventario_actual','inventario_lotes',
        'sucursales','configuracion_sistema','ventas','detalle_venta','ventas_pagos',
        'caja','movimientos_caja','cuentas_por_cobrar','abonos_credito','inventario_consumos',
        'movimientos_contables','cierre_caja','periodos_contables','tenant_memberships',
        'usuarios','auditoria_eventos','system_test_runs','abonos_proveedores',
        'adelantos_empleados','catalogo_gastos','configuracion_financiera',
        'cuentas_dinero','depreciacion','depreciaciones','distribucion_beneficios',
        'movimientos','movimientos_dinero','notas_credito','pagos_proveedores',
        'secuencia_ncf','suscripciones_empresas'
    ]
    loop
        if to_regclass('public.' || v_table) is null then continue; end if;
        for r in
            select policyname from pg_policies
            where schemaname='public' and tablename=v_table
        loop
            execute format('drop policy if exists %I on public.%I',r.policyname,v_table);
        end loop;
    end loop;
end;
$$;

do $$
declare
    r record;
    v_permission text;
begin
    for r in
        select *
        from (values
            ('productos','puede_editar_productos'),
            ('clientes','ver_clientes'),
            ('proveedores','puede_registrar_compras'),
            ('compras','puede_registrar_compras'),
            ('facturas_compra','puede_registrar_compras'),
            ('detalle_factura_compra','puede_registrar_compras'),
            ('gastos','puede_registrar_gastos'),
            ('empleados','puede_configurar'),
            ('pagos_empleados','puede_configurar'),
            ('perdidas','puede_reportar_perdidas'),
            ('gastos_dueno','puede_configurar'),
            ('activos_fijos','puede_configurar'),
            ('capital_base','puede_configurar'),
            ('ajustes_inventario','puede_editar_inventario'),
            ('conteo_inventario','puede_registrar_conteo'),
            ('inventario_actual','puede_editar_inventario'),
            ('inventario_lotes','puede_editar_inventario'),
            ('sucursales','puede_configurar'),
            ('configuracion_sistema','puede_configurar'),
            ('caja','puede_abrir_caja'),
            ('abonos_proveedores','puede_registrar_compras'),
            ('adelantos_empleados','puede_configurar'),
            ('catalogo_gastos','puede_registrar_gastos'),
            ('configuracion_financiera','puede_configurar'),
            ('cuentas_dinero','puede_configurar'),
            ('depreciacion','puede_configurar'),
            ('depreciaciones','puede_configurar'),
            ('distribucion_beneficios','puede_configurar'),
            ('movimientos','puede_editar_inventario'),
            ('movimientos_dinero','puede_configurar'),
            ('notas_credito','puede_anular'),
            ('pagos_proveedores','puede_registrar_compras')
        ) as x(table_name, permission_name)
    loop
        if to_regclass('public.' || r.table_name) is null then
            continue;
        end if;
        execute format(
            'alter table public.%I add column if not exists empresa_id text',
            r.table_name
        );
        execute format('alter table public.%I enable row level security', r.table_name);
        execute format(
            'grant select, insert, update, delete on public.%I to authenticated',
            r.table_name
        );
        execute format('drop policy if exists ais_select on public.%I', r.table_name);
        execute format('drop policy if exists ais_insert on public.%I', r.table_name);
        execute format('drop policy if exists ais_update on public.%I', r.table_name);
        execute format('drop policy if exists ais_delete on public.%I', r.table_name);
        execute format(
            'create policy ais_select on public.%I for select to authenticated using (public.has_tenant_access(empresa_id))',
            r.table_name
        );
        execute format(
            'create policy ais_insert on public.%I for insert to authenticated with check (public.has_tenant_permission(empresa_id, %L))',
            r.table_name, r.permission_name
        );
        execute format(
            'create policy ais_update on public.%I for update to authenticated using (public.has_tenant_permission(empresa_id, %L)) with check (public.has_tenant_permission(empresa_id, %L))',
            r.table_name, r.permission_name, r.permission_name
        );
        execute format(
            'create policy ais_delete on public.%I for delete to authenticated using (public.has_tenant_permission(empresa_id, %L))',
            r.table_name, r.permission_name
        );
    end loop;
end;
$$;

-- Tablas económicas: lectura directa; mutaciones únicamente por API SECURITY DEFINER.
do $$
declare
    v_table text;
begin
    foreach v_table in array array[
        'ventas','detalle_venta','ventas_pagos','compras','facturas_compra',
        'detalle_factura_compra','caja','movimientos_caja','cuentas_por_cobrar',
        'abonos_credito','inventario_consumos','movimientos_contables','cierre_caja',
        'periodos_contables','pagos_empleados'
    ]
    loop
        if to_regclass('public.' || v_table) is null then
            continue;
        end if;
        execute format(
            'alter table public.%I add column if not exists empresa_id text',
            v_table
        );
        execute format('alter table public.%I enable row level security', v_table);
        execute format('grant select on public.%I to authenticated', v_table);
        execute format('drop policy if exists ais_select on public.%I', v_table);
        execute format(
            'create policy ais_select on public.%I for select to authenticated using (public.has_tenant_access(empresa_id))',
            v_table
        );
        execute format('revoke insert, update, delete on public.%I from authenticated', v_table);
    end loop;
end;
$$;

-- La pertenencia a una empresa no concede por sí sola acceso a todos sus
-- datos. Estas políticas refuerzan en PostgreSQL los permisos que muestra la
-- interfaz y evitan que un usuario salte el menú llamando PostgREST.
do $$
declare
    r record;
    v_expression text;
begin
    for r in
        select *
        from (values
            ('productos', array[
                'puede_ver_productos','puede_vender','puede_ver_inventario',
                'puede_editar_productos','puede_editar_inventario','puede_ver_reportes'
            ]::text[]),
            ('clientes', array[
                'ver_clientes','puede_vender','ver_credito','puede_ver_reportes'
            ]::text[]),
            ('proveedores', array[
                'puede_ver_compras','puede_registrar_compras','puede_ver_reportes'
            ]::text[]),
            ('compras', array[
                'puede_ver_compras','puede_registrar_compras','puede_ver_reportes'
            ]::text[]),
            ('facturas_compra', array[
                'puede_ver_compras','puede_registrar_compras','puede_ver_reportes'
            ]::text[]),
            ('detalle_factura_compra', array[
                'puede_ver_compras','puede_registrar_compras','puede_ver_reportes'
            ]::text[]),
            ('abonos_proveedores', array[
                'puede_ver_compras','puede_registrar_compras','puede_ver_reportes'
            ]::text[]),
            ('pagos_proveedores', array[
                'puede_ver_compras','puede_registrar_compras','puede_ver_reportes'
            ]::text[]),
            ('gastos', array[
                'puede_ver_gastos','puede_registrar_gastos','puede_ver_reportes'
            ]::text[]),
            ('catalogo_gastos', array[
                'puede_ver_gastos','puede_registrar_gastos','puede_ver_reportes'
            ]::text[]),
            ('empleados', array['puede_configurar']::text[]),
            ('pagos_empleados', array['puede_configurar']::text[]),
            ('adelantos_empleados', array['puede_configurar']::text[]),
            ('perdidas', array[
                'puede_ver_perdidas','puede_reportar_perdidas','puede_ver_reportes'
            ]::text[]),
            ('ajustes_inventario', array[
                'puede_ver_inventario','puede_editar_inventario',
                'puede_aplicar_ajuste_inventario','puede_ver_reportes'
            ]::text[]),
            ('conteo_inventario', array[
                'puede_ver_inventario','puede_registrar_conteo','puede_ver_reportes'
            ]::text[]),
            ('inventario_actual', array[
                'puede_ver_inventario','puede_editar_inventario',
                'puede_vender','puede_ver_reportes'
            ]::text[]),
            ('inventario_lotes', array[
                'puede_ver_inventario','puede_editar_inventario',
                'puede_vender','puede_ver_reportes'
            ]::text[]),
            ('movimientos', array[
                'puede_ver_inventario','puede_editar_inventario',
                'puede_vender','puede_ver_reportes'
            ]::text[]),
            ('sucursales', array['puede_vender','puede_configurar']::text[]),
            ('gastos_dueno', array['puede_configurar','puede_ver_reportes']::text[]),
            ('activos_fijos', array['puede_configurar','puede_ver_reportes']::text[]),
            ('capital_base', array['puede_configurar','puede_ver_reportes']::text[]),
            ('configuracion_financiera', array['puede_configurar','puede_ver_reportes']::text[]),
            ('cuentas_dinero', array['puede_configurar','puede_ver_reportes']::text[]),
            ('depreciacion', array['puede_configurar','puede_ver_reportes']::text[]),
            ('depreciaciones', array['puede_configurar','puede_ver_reportes']::text[]),
            ('distribucion_beneficios', array['puede_configurar','puede_ver_reportes']::text[]),
            ('movimientos_dinero', array['puede_configurar','puede_ver_reportes']::text[])
        ) as x(table_name, permissions)
    loop
        if to_regclass('public.' || r.table_name) is null then
            continue;
        end if;
        execute format(
            'alter table public.%I add column if not exists empresa_id text',
            r.table_name
        );
        select string_agg(
            format('public.has_tenant_permission(empresa_id,%L)', permission_name),
            ' or '
        )
        into v_expression
        from unnest(r.permissions) as permission_name;
        execute format('drop policy if exists ais_select on public.%I', r.table_name);
        execute format(
            'create policy ais_select on public.%I for select to authenticated using (public.has_tenant_access(empresa_id) and (%s))',
            r.table_name,
            v_expression
        );
    end loop;
end;
$$;

drop policy if exists ais_select on public.ventas;
create policy ais_select on public.ventas
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'puede_ver_todas_ventas')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
        or public.has_tenant_permission(empresa_id,'ver_credito')
        or public.has_tenant_permission(empresa_id,'puede_editar_ventas')
        or public.has_tenant_permission(empresa_id,'puede_anular')
        or (
            (
                public.has_tenant_permission(empresa_id,'puede_ver_ventas_propias')
                or public.has_tenant_permission(empresa_id,'puede_vender')
            )
            and (
                usuario_id=auth.uid()
                or lower(coalesce(estado,''))='abierta'
            )
        )
    )
);

drop policy if exists ais_select on public.detalle_venta;
create policy ais_select on public.detalle_venta
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and exists (
        select 1 from public.ventas v
        where v.id=detalle_venta.venta_id
          and v.empresa_id=detalle_venta.empresa_id
    )
);

drop policy if exists ais_select on public.ventas_pagos;
create policy ais_select on public.ventas_pagos
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and exists (
        select 1 from public.ventas v
        where v.id=ventas_pagos.venta_id
          and v.empresa_id=ventas_pagos.empresa_id
    )
);

drop policy if exists ais_select on public.inventario_consumos;
create policy ais_select on public.inventario_consumos
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and exists (
        select 1 from public.ventas v
        where v.id=inventario_consumos.venta_id
          and v.empresa_id=inventario_consumos.empresa_id
    )
);

drop policy if exists ais_select on public.caja;
create policy ais_select on public.caja
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        usuario_id=auth.uid()
        or public.has_tenant_permission(empresa_id,'puede_cerrar_caja')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
    )
);

drop policy if exists ais_select on public.movimientos_caja;
create policy ais_select on public.movimientos_caja
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'puede_cerrar_caja')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
        or exists (
            select 1 from public.caja c
            where c.id=movimientos_caja.caja_id
              and c.empresa_id=movimientos_caja.empresa_id
        )
    )
);

drop policy if exists ais_select on public.cuentas_por_cobrar;
create policy ais_select on public.cuentas_por_cobrar
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'ver_credito')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
    )
);

drop policy if exists ais_select on public.abonos_credito;
create policy ais_select on public.abonos_credito
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'ver_credito')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
    )
);

drop policy if exists ais_select on public.movimientos_contables;
create policy ais_select on public.movimientos_contables
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'puede_ver_reportes')
        or public.has_tenant_permission(empresa_id,'puede_configurar')
    )
);

drop policy if exists ais_select on public.periodos_contables;
create policy ais_select on public.periodos_contables
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'puede_ver_reportes')
        or public.has_tenant_permission(empresa_id,'puede_configurar')
    )
);

drop policy if exists ais_select on public.cierre_caja;
create policy ais_select on public.cierre_caja
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        usuario_id=auth.uid()
        or public.has_tenant_permission(empresa_id,'puede_cerrar_caja')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
    )
);

alter table public.tenant_memberships enable row level security;
drop policy if exists ais_membership_select on public.tenant_memberships;
create policy ais_membership_select on public.tenant_memberships
for select to authenticated
using (user_id = auth.uid() or public.is_platform_superadmin());
grant select on public.tenant_memberships to authenticated;
revoke insert, update, delete on public.tenant_memberships from authenticated;

alter table public.usuarios enable row level security;
drop policy if exists ais_usuarios_select on public.usuarios;
drop policy if exists ais_usuarios_update on public.usuarios;
create policy ais_usuarios_select on public.usuarios
for select to authenticated
using (
    user_id = auth.uid()
    or public.is_platform_superadmin()
    or public.has_tenant_permission(empresa_id, 'puede_configurar')
);
grant select on public.usuarios to authenticated;
revoke insert, update, delete on public.usuarios from authenticated;

alter table public.auditoria_eventos enable row level security;
drop policy if exists ais_auditoria_select on public.auditoria_eventos;
create policy ais_auditoria_select on public.auditoria_eventos
for select to authenticated
using (
    public.has_tenant_access(empresa_id)
    and (
        public.has_tenant_permission(empresa_id,'puede_configurar')
        or public.has_tenant_permission(empresa_id,'puede_ver_reportes')
    )
);
grant select on public.auditoria_eventos to authenticated;
revoke insert, update, delete on public.auditoria_eventos from authenticated;

alter table public.system_test_runs enable row level security;
drop policy if exists ais_test_runs_select on public.system_test_runs;
create policy ais_test_runs_select on public.system_test_runs
for select to authenticated
using (public.is_platform_superadmin() or public.has_tenant_access(empresa_id));
grant select on public.system_test_runs to authenticated;
revoke insert, update, delete on public.system_test_runs from authenticated;

-- La configuración puede editarse dentro de la empresa, pero su creación,
-- reasignación y plan comercial pertenecen al servicio administrativo.
drop policy if exists ais_insert on public.configuracion_sistema;
drop policy if exists ais_delete on public.configuracion_sistema;
revoke insert, delete on public.configuracion_sistema from authenticated;

create or replace function public.protect_configuration_ownership()
returns trigger
language plpgsql
set search_path = public, auth
as $$
begin
    if auth.role()='service_role' or public.is_platform_superadmin() then
        return new;
    end if;
    if tg_op='INSERT' then
        raise exception 'CONFIGURATION_CREATION_REQUIRES_PLATFORM_ADMIN';
    end if;
    if new.empresa_id is distinct from old.empresa_id
       or new.propietario is distinct from old.propietario
       or to_jsonb(new)->'plan' is distinct from to_jsonb(old)->'plan'
       or to_jsonb(new)->'clave' is distinct from to_jsonb(old)->'clave' then
        raise exception 'PROTECTED_CONFIGURATION_FIELD';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_protect_configuration_ownership on public.configuracion_sistema;
create trigger trg_protect_configuration_ownership
before insert or update on public.configuracion_sistema
for each row execute function public.protect_configuration_ownership();

alter table public.empresas enable row level security;
drop policy if exists ais_empresas_select on public.empresas;
create policy ais_empresas_select on public.empresas
for select to authenticated
using (public.is_platform_superadmin() or public.has_tenant_access(tenant_id));
grant select on public.empresas to authenticated;
revoke insert, update, delete on public.empresas from authenticated;

do $$
begin
    if to_regclass('public.suscripciones_empresas') is not null then
        execute 'alter table public.suscripciones_empresas enable row level security';
        execute 'drop policy if exists ais_suscripciones_select on public.suscripciones_empresas';
        execute $policy$
            create policy ais_suscripciones_select on public.suscripciones_empresas
            for select to authenticated
            using (
                public.is_platform_superadmin()
                or public.has_tenant_access(empresa_id)
            )
        $policy$;
        execute 'grant select on public.suscripciones_empresas to authenticated';
        execute 'revoke insert,update,delete on public.suscripciones_empresas from authenticated';
    end if;
end
$$;

alter table public.nomina_parametros enable row level security;
drop policy if exists ais_nomina_parametros_select on public.nomina_parametros;
create policy ais_nomina_parametros_select on public.nomina_parametros
for select to authenticated
using (auth.uid() is not null);
grant select on public.nomina_parametros to authenticated;
revoke insert, update, delete on public.nomina_parametros from authenticated;

alter table public.secuencia_documentos enable row level security;
revoke all on public.secuencia_documentos from anon, authenticated;

-- Tablas legadas que ya no forman parte de un flujo autorizado.
do $$
declare
    v_table text;
begin
    foreach v_table in array array[
        'auditoria','login_intentos','secuencia_ncf','auditoria_alertas',
        'auditoria_mejoras','auditoria_salud','estado_resultados','notas_credito'
    ]
    loop
        if to_regclass('public.'||v_table) is null then continue; end if;
        execute format('alter table public.%I enable row level security',v_table);
        execute format('revoke all on public.%I from anon, authenticated',v_table);
    end loop;
end
$$;

-- Revoca las superficies SQL de versiones anteriores. En particular, el RPC
-- legado de venta confiaba en totales y secuencias enviados por el cliente.
-- Las funciones de trigger pueden seguir ejecutándose como triggers sin
-- conceder EXECUTE a usuarios de PostgREST.
do $$
declare
    r record;
begin
    for r in
        select
            n.nspname,
            p.proname,
            pg_get_function_identity_arguments(p.oid) as identity_args
        from pg_proc p
        join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='public'
          and p.proname in (
              'registrar_venta_transaccional',
              'obtener_tenant_solicitante',
              'fn_is_superadmin',
              'fn_ventas_ncf_immutable',
              'fn_auditoria_append_only',
              'fn_auditoria_legacy_append_only',
              'fn_sync_auditoria_eventos_cols',
              'fn_sync_detalle_venta_cols',
              'fn_sync_ventas_cols',
              'fn_sync_ventas_pagos_cols',
              'fn_prevent_closed_period_modification'
          )
    loop
        execute format(
            'revoke all on function %I.%I(%s) from public, anon, authenticated',
            r.nspname,r.proname,r.identity_args
        );
    end loop;
end
$$;

-- Anon nunca accede a tablas de negocio.
do $$
declare
    r record;
begin
    for r in
        select schemaname, tablename
        from pg_tables
        where schemaname = 'public'
    loop
        execute format('revoke all on table public.%I from anon', r.tablename);
    end loop;
end;
$$;

-- ---------------------------------------------------------------------------
-- Auditoría inmutable y con limpieza de campos sensibles
-- ---------------------------------------------------------------------------
create or replace function public.api_audit_event(
    p_accion text,
    p_modulo text default null,
    p_tabla text default null,
    p_registro_id text default null,
    p_detalle text default null,
    p_metadata jsonb default '{}'::jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_tenant text;
    v_user text;
    v_clean jsonb;
begin
    select tm.tenant_id into v_tenant
    from public.tenant_memberships tm
    where tm.user_id = auth.uid() and tm.active
    order by tm.created_at limit 1;
    if public.is_platform_superadmin() then
        v_tenant := coalesce(nullif(p_metadata ->> 'tenant_id',''), v_tenant, 'global');
        if v_tenant <> 'global' and not exists (
            select 1 from public.empresas e
            where e.tenant_id=v_tenant and e.activo
        ) then
            raise exception 'TENANT_NOT_ACTIVE_OR_NOT_FOUND';
        end if;
    end if;
    if v_tenant is null then raise exception 'NO_ACTIVE_MEMBERSHIP'; end if;

    v_clean := coalesce(p_metadata, '{}'::jsonb)
        - 'password' - 'clave' - 'token' - 'access_token' - 'refresh_token'
        - 'totp_secret' - 'secret' - 'hash';
    select coalesce(u.nombre, u.usuario, auth.uid()::text) into v_user
    from public.usuarios u where u.user_id = auth.uid() limit 1;

    insert into public.auditoria_eventos(
        empresa_id, usuario_id, usuario, accion, modulo, tabla,
        registro_id, detalle, metadata
    ) values (
        v_tenant, auth.uid()::text, v_user, left(p_accion,100), left(p_modulo,100),
        left(p_tabla,100), left(p_registro_id,200), left(p_detalle,2000), v_clean
    );
    return jsonb_build_object('success',true);
end;
$$;

revoke all on function public.api_audit_event(text,text,text,text,text,jsonb) from public, anon;
grant execute on function public.api_audit_event(text,text,text,text,text,jsonb) to authenticated;

create or replace function public.prevent_audit_mutation()
returns trigger language plpgsql as $$
begin
    raise exception 'AUDIT_APPEND_ONLY';
end;
$$;

drop trigger if exists trg_auditoria_append_only on public.auditoria_eventos;
create trigger trg_auditoria_append_only
before update or delete on public.auditoria_eventos
for each row execute function public.prevent_audit_mutation();

-- ---------------------------------------------------------------------------
-- Bloqueo contable por empresa y periodo
-- ---------------------------------------------------------------------------
create or replace function public.enforce_open_period()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    v_tenant text;
    v_fecha date;
begin
    if tg_op = 'DELETE' then
        v_tenant := old.empresa_id;
        v_fecha := coalesce(
            nullif(to_jsonb(old)->>'fecha','')::timestamptz::date,
            current_date
        );
    else
        v_tenant := new.empresa_id;
        v_fecha := coalesce(
            nullif(to_jsonb(new)->>'fecha','')::timestamptz::date,
            current_date
        );
    end if;
    if exists (
        select 1 from public.periodos_contables pc
        where pc.empresa_id = v_tenant
          and pc.ano = extract(year from v_fecha)::int
          and pc.mes = extract(month from v_fecha)::int
          and pc.estado = 'cerrado'
    ) then
        raise exception 'PERIODO_CERRADO';
    end if;
    return case when tg_op = 'DELETE' then old else new end;
end;
$$;
revoke all on function public.enforce_open_period() from public, anon, authenticated;

do $$
declare
    v_table text;
begin
    foreach v_table in array array[
        'ventas','detalle_venta','ventas_pagos','compras','facturas_compra',
        'detalle_factura_compra','gastos','movimientos_caja',
        'movimientos_contables','pagos_empleados','abonos_credito','inventario_lotes'
    ]
    loop
        if to_regclass('public.' || v_table) is null then continue; end if;
        execute format('drop trigger if exists trg_open_period on public.%I', v_table);
        execute format(
            'drop trigger if exists %I on public.%I',
            'tg_prevent_closed_' || v_table,
            v_table
        );
        execute format(
            'create trigger trg_open_period before insert or update or delete on public.%I for each row execute function public.enforce_open_period()',
            v_table
        );
    end loop;
end;
$$;

commit;
```

## 2. API transaccional de ventas, caja, créditos e inventario

```sql
-- A&M v3.0 — API transaccional de ventas, créditos, caja y auditoría

begin;

create or replace function public.api_registrar_venta(p jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text;
    v_role text;
    v_estado text := lower(coalesce(p ->> 'estado', 'completada'));
    v_caja_id uuid;
    v_venta_id uuid;
    v_detalle_id uuid;
    v_numero bigint;
    v_numero_factura text;
    v_subtotal numeric(18,2) := 0;
    v_subtotal_gravado numeric(18,2) := 0;
    v_subtotal_exento numeric(18,2) := 0;
    v_itbis numeric(18,2) := 0;
    v_total numeric(18,2) := 0;
    v_costo_total numeric(18,2) := 0;
    v_pago_total numeric(18,2) := 0;
    v_credito_total numeric(18,2) := 0;
    v_credito_actual numeric(18,2) := 0;
    v_limite_credito numeric(18,2) := 0;
    v_cliente_id bigint;
    v_cliente_nombre text;
    v_usuario text;
    v_linea_total numeric(18,2);
    v_linea_subtotal numeric(18,2);
    v_linea_itbis numeric(18,2);
    v_linea_costo numeric(18,4);
    v_precio numeric(18,2);
    v_precio_catalogo numeric(18,2);
    v_precio_minimo numeric(18,2);
    v_costo_catalogo numeric(18,4);
    v_cantidad numeric(18,4);
    v_stock numeric(18,4);
    v_gravado boolean;
    v_tasa numeric(6,3);
    v_restante numeric(18,4);
    v_tomar numeric(18,4);
    v_producto record;
    v_lote record;
    v_item jsonb;
    v_pay jsonb;
    v_metodo text;
    v_monto numeric(18,2);
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if jsonb_typeof(p -> 'items') <> 'array' or jsonb_array_length(p -> 'items') = 0 then
        raise exception 'SALE_ITEMS_REQUIRED';
    end if;
    if v_estado not in ('abierta','completada') then raise exception 'INVALID_SALE_STATUS'; end if;
    if coalesce((p ->> 'es_factura_fiscal')::boolean, false) then
        raise exception 'DGII_EDUCATIONAL_ONLY: el sistema no emite documentos fiscales';
    end if;

    if public.is_platform_superadmin() then
        v_tenant := nullif(trim(p ->> 'empresa_id'), '');
        if v_tenant is not null and not exists (
            select 1 from public.empresas e
            where e.tenant_id=v_tenant and e.activo
        ) then
            raise exception 'TENANT_NOT_ACTIVE_OR_NOT_FOUND';
        end if;
    else
        select tm.tenant_id, tm.role
        into v_tenant, v_role
        from public.tenant_memberships tm
        where tm.user_id = v_uid and tm.active
          and (p ->> 'empresa_id' is null or tm.tenant_id = p ->> 'empresa_id')
        order by tm.created_at limit 1;
    end if;
    if v_tenant is null or not public.has_tenant_permission(v_tenant, 'puede_vender') then
        raise exception 'SALE_PERMISSION_DENIED';
    end if;

    v_caja_id := nullif(p ->> 'caja_id','')::uuid;
    if v_caja_id is null then raise exception 'OPEN_CASH_REGISTER_REQUIRED'; end if;
    perform 1 from public.caja c
    where c.id = v_caja_id and c.empresa_id = v_tenant and lower(c.estado) = 'abierta'
    for update;
    if not found then raise exception 'OPEN_CASH_REGISTER_REQUIRED'; end if;

    select coalesce(u.nombre, u.usuario, v_uid::text)
    into v_usuario from public.usuarios u where u.user_id = v_uid limit 1;

    insert into public.secuencia_documentos(empresa_id, sucursal_id, tipo, siguiente)
    select
        v_tenant,
        coalesce(p ->> 'sucursal_id',''),
        'factura_interna',
        coalesce(max(
            case
                when v.numero_factura ~ '^INT-[0-9]{4}-[0-9]{8}$'
                then right(v.numero_factura,8)::bigint
                else 0
            end
        ),0)+1
    from public.ventas v
    where v.empresa_id=v_tenant
    on conflict (empresa_id, sucursal_id, tipo) do nothing;

    select siguiente into v_numero
    from public.secuencia_documentos
    where empresa_id = v_tenant
      and sucursal_id = coalesce(p ->> 'sucursal_id','')
      and tipo = 'factura_interna'
    for update;

    update public.secuencia_documentos
    set siguiente = siguiente + 1, updated_at = now()
    where empresa_id = v_tenant
      and sucursal_id = coalesce(p ->> 'sucursal_id','')
      and tipo = 'factura_interna';

    v_numero_factura := format('INT-%s-%s', to_char(current_date,'YYYY'), lpad(v_numero::text,8,'0'));
    v_cliente_id := nullif(p ->> 'cliente_id','')::bigint;
    if v_cliente_id is null then
        v_cliente_nombre := 'Venta general';
    else
        select left(c.nombre,200), coalesce(c.limite_credito,0)
        into v_cliente_nombre, v_limite_credito
        from public.clientes c
        where c.id=v_cliente_id
          and c.empresa_id=v_tenant
          and coalesce(c.activo,true)
        for update;
        if not found then raise exception 'CUSTOMER_NOT_FOUND_OR_FORBIDDEN'; end if;
    end if;

    insert into public.ventas(
        empresa_id, fecha, total, subtotal, subtotal_gravado, subtotal_exento,
        itbis_total, es_factura_fiscal, tipo_documento, estado, anulado,
        numero_factura, cliente_id, cliente_nombre, usuario, usuario_id,
        dia_operativo, caja_id, tipo_venta, metodo_pago, observacion
    ) values (
        v_tenant, now(), 0, 0, 0, 0, 0, false, 'Recibo interno',
        v_estado, false, v_numero_factura, v_cliente_id, v_cliente_nombre,
        v_usuario, v_uid, coalesce(p ->> 'dia_operativo', current_date::text),
        v_caja_id, 'POS', case when v_estado='abierta' then 'abierta' else 'pendiente' end,
        left(coalesce(p ->> 'observacion',''),2000)
    ) returning id into v_venta_id;

    for v_item in select value from jsonb_array_elements(p -> 'items')
    loop
        v_cantidad := round(coalesce((v_item ->> 'cantidad')::numeric,0),4);
        if v_cantidad <= 0 then raise exception 'INVALID_ITEM_QUANTITY'; end if;

        select pr.* into v_producto
        from public.productos pr
        where pr.id = nullif(v_item ->> 'producto_id','')::uuid
          and pr.empresa_id = v_tenant
          and coalesce(pr.activo,true)
          and not coalesce(pr.anulado,false)
        for update;
        if not found then raise exception 'PRODUCT_NOT_FOUND_OR_FORBIDDEN'; end if;

        v_stock := coalesce(v_producto.stock, v_producto.existencia, v_producto.cantidad, 0);
        if v_stock < v_cantidad then
            raise exception 'INSUFFICIENT_STOCK: % disponible, % solicitado', v_stock, v_cantidad;
        end if;

        v_precio_catalogo := round(coalesce(
            v_producto.precio_venta, v_producto.precio, 0
        )::numeric,2);
        v_precio_minimo := round(coalesce(
            nullif(v_producto.precio_minimo,0),
            nullif(v_producto.precio_descuento,0),
            v_precio_catalogo
        )::numeric,2);
        v_precio := round(coalesce((v_item ->> 'precio_unitario')::numeric, v_precio_catalogo),2);
        if v_precio <= 0 or v_precio > v_precio_catalogo then
            raise exception 'INVALID_ITEM_PRICE';
        end if;
        if v_precio < v_precio_minimo
           and not (
               public.has_tenant_permission(v_tenant, 'puede_aplicar_descuento')
               or public.has_tenant_permission(v_tenant, 'puede_editar_todo')
           ) then
            raise exception 'DISCOUNT_PERMISSION_DENIED';
        end if;

        v_gravado := coalesce(v_producto.itbis_gravado, true);
        v_tasa := case when v_gravado then coalesce(v_producto.itbis_tasa,18) else 0 end;
        v_linea_total := round(v_cantidad * v_precio,2);
        if v_tasa > 0 then
            v_linea_subtotal := round(v_linea_total / (1 + v_tasa / 100),2);
            v_linea_itbis := v_linea_total - v_linea_subtotal;
            v_subtotal_gravado := v_subtotal_gravado + v_linea_subtotal;
        else
            v_linea_subtotal := v_linea_total;
            v_linea_itbis := 0;
            v_subtotal_exento := v_subtotal_exento + v_linea_subtotal;
        end if;

        v_costo_catalogo := coalesce(v_producto.costo_unitario, v_producto.costo, 0);
        v_linea_costo := 0;
        v_restante := v_cantidad;

        for v_lote in
            select il.*
            from public.inventario_lotes il
            where il.empresa_id = v_tenant
              and il.producto_id = v_producto.id
              and il.activo
              and il.cantidad_restante > 0
            order by il.fecha_compra, il.created_at, il.id
            for update
        loop
            exit when v_restante <= 0;
            v_tomar := least(v_restante, v_lote.cantidad_restante);
            v_linea_costo := v_linea_costo + v_tomar * v_lote.costo_unitario;
            update public.inventario_lotes
            set cantidad_restante = cantidad_restante - v_tomar,
                activo = (cantidad_restante - v_tomar) > 0
            where id = v_lote.id;
            insert into public.inventario_consumos(
                empresa_id, venta_id, producto_id, lote_id, cantidad, costo_unitario
            ) values (
                v_tenant, v_venta_id, v_producto.id, v_lote.id, v_tomar, v_lote.costo_unitario
            );
            v_restante := v_restante - v_tomar;
        end loop;
        if v_restante > 0 then
            v_linea_costo := v_linea_costo + v_restante * v_costo_catalogo;
            insert into public.inventario_consumos(
                empresa_id, venta_id, producto_id, lote_id, cantidad, costo_unitario
            ) values (
                v_tenant, v_venta_id, v_producto.id, null, v_restante, v_costo_catalogo
            );
        end if;

        insert into public.detalle_venta(
            empresa_id, venta_id, producto_id, codigo, producto, cantidad,
            precio_unitario, precio, itbis_gravado, itbis_tasa, itbis_monto,
            subtotal, total_linea, costo_unitario, costo, costo_total,
            ganancia_linea, usuario, fecha, anulado
        ) values (
            v_tenant, v_venta_id, v_producto.id,
            coalesce(v_producto.codigo, v_producto.codigo_barra, v_producto.id::text),
            v_producto.nombre, v_cantidad, v_precio, v_precio, v_gravado, v_tasa,
            v_linea_itbis, v_linea_subtotal, v_linea_total,
            case when v_cantidad > 0 then round(v_linea_costo / v_cantidad,4) else 0 end,
            case when v_cantidad > 0 then round(v_linea_costo / v_cantidad,4) else 0 end,
            round(v_linea_costo,2), round(v_linea_total - v_linea_costo,2),
            v_usuario, now(), false
        ) returning id into v_detalle_id;

        update public.inventario_consumos
        set detalle_id = v_detalle_id
        where venta_id = v_venta_id and producto_id = v_producto.id and detalle_id is null;

        update public.productos
        set stock = v_stock - v_cantidad,
            existencia = v_stock - v_cantidad,
            cantidad = v_stock - v_cantidad,
            updated_at = now()
        where id = v_producto.id;

        v_total := v_total + v_linea_total;
        v_subtotal := v_subtotal + v_linea_subtotal;
        v_itbis := v_itbis + v_linea_itbis;
        v_costo_total := v_costo_total + v_linea_costo;
    end loop;

    if v_estado = 'completada' then
        if jsonb_typeof(p -> 'pagos') <> 'array' then raise exception 'PAYMENTS_REQUIRED'; end if;
        for v_pay in select value from jsonb_array_elements(p -> 'pagos')
        loop
            v_metodo := lower(trim(v_pay ->> 'metodo'));
            v_monto := round(coalesce((v_pay ->> 'monto')::numeric,0),2);
            if v_monto = 0 then continue; end if;
            if v_monto < 0 or v_metodo not in ('efectivo','transferencia','tarjeta','credito') then
                raise exception 'INVALID_PAYMENT';
            end if;
            v_pago_total := v_pago_total + v_monto;
            if v_metodo = 'credito' then v_credito_total := v_credito_total + v_monto; end if;
        end loop;
        if abs(v_pago_total - v_total) > 0.01 then
            raise exception 'PAYMENT_MISMATCH: total %, pagos %', v_total, v_pago_total;
        end if;
        if v_credito_total > 0 and v_cliente_id is null then
            raise exception 'REGISTERED_CUSTOMER_REQUIRED_FOR_CREDIT';
        end if;
        if v_credito_total > 0 and v_limite_credito > 0 then
            select coalesce(sum(cxc.saldo_pendiente),0)
            into v_credito_actual
            from public.cuentas_por_cobrar cxc
            where cxc.empresa_id=v_tenant
              and cxc.cliente_id=v_cliente_id
              and not coalesce(cxc.anulado,false)
              and cxc.saldo_pendiente>0;
            if v_credito_actual + v_credito_total > v_limite_credito then
                raise exception 'CUSTOMER_CREDIT_LIMIT_EXCEEDED';
            end if;
        end if;

        for v_pay in select value from jsonb_array_elements(p -> 'pagos')
        loop
            v_metodo := lower(trim(v_pay ->> 'metodo'));
            v_monto := round(coalesce((v_pay ->> 'monto')::numeric,0),2);
            if v_monto <= 0 then continue; end if;
            insert into public.ventas_pagos(
                empresa_id, venta_id, metodo, monto, usuario, usuario_id,
                caja_id, dia_operativo
            ) values (
                v_tenant, v_venta_id, v_metodo, v_monto, v_usuario, v_uid,
                v_caja_id, coalesce(p ->> 'dia_operativo',current_date::text)
            );
            if v_metodo <> 'credito' then
                insert into public.movimientos_caja(
                    empresa_id, fecha, dia_operativo, caja_id, tipo_movimiento,
                    origen, referencia_id, metodo_pago, monto, descripcion,
                    usuario, usuario_id, anulado
                ) values (
                    v_tenant, now(), coalesce(p ->> 'dia_operativo',current_date::text),
                    v_caja_id, 'entrada', 'venta', v_venta_id::text, v_metodo,
                    v_monto, 'Cobro de ' || v_numero_factura, v_usuario, v_uid, false
                );
            end if;
        end loop;

        if v_credito_total > 0 then
            insert into public.cuentas_por_cobrar(
                empresa_id, fecha, cliente_id, cliente_nombre, venta_id,
                monto_original, monto_abonado, saldo_pendiente, estado,
                usuario, anulado
            ) values (
                v_tenant, now(), v_cliente_id, v_cliente_nombre, v_venta_id,
                v_credito_total, 0, v_credito_total, 'pendiente', v_usuario, false
            );
        end if;
    end if;

    update public.ventas
    set total = round(v_total,2), subtotal = round(v_subtotal,2),
        subtotal_gravado = round(v_subtotal_gravado,2),
        subtotal_exento = round(v_subtotal_exento,2),
        itbis_total = round(v_itbis,2),
        ganancia_bruta = round(v_total - v_costo_total,2),
        metodo_pago = case
            when v_estado='abierta' then 'abierta'
            when (select count(*) from public.ventas_pagos where venta_id=v_venta_id and monto>0) > 1 then 'mixto'
            else coalesce((select metodo from public.ventas_pagos where venta_id=v_venta_id and monto>0 limit 1),'pendiente')
        end,
        updated_at = now()
    where id = v_venta_id;

    if v_estado = 'completada' then
        for v_pay in
            select to_jsonb(vp) from public.ventas_pagos vp where vp.venta_id = v_venta_id
        loop
            v_metodo := v_pay ->> 'metodo';
            v_monto := (v_pay ->> 'monto')::numeric;
            insert into public.movimientos_contables(
                empresa_id, fecha, modulo, referencia_id, cuenta_codigo,
                cuenta_nombre, tipo_cuenta, debito, credito, descripcion,
                usuario, usuario_id
            ) values (
                v_tenant, now(), 'ventas', v_venta_id::text,
                case v_metodo when 'efectivo' then '1101' when 'credito' then '1201' else '1102' end,
                case v_metodo when 'efectivo' then 'Efectivo / Caja' when 'credito' then 'Cuentas por Cobrar' else 'Banco / Depósito' end,
                'activo', v_monto, 0, 'Cobro ' || v_numero_factura, v_usuario, v_uid
            );
        end loop;
        insert into public.movimientos_contables(
            empresa_id, fecha, modulo, referencia_id, cuenta_codigo,
            cuenta_nombre, tipo_cuenta, debito, credito, descripcion, usuario, usuario_id
        ) values
            (v_tenant,now(),'ventas',v_venta_id::text,'4101','Ingresos por Ventas','ingreso',0,round(v_subtotal,2),'Venta '||v_numero_factura,v_usuario,v_uid),
            (v_tenant,now(),'ventas',v_venta_id::text,'2102','ITBIS por Pagar','pasivo',0,round(v_itbis,2),'ITBIS '||v_numero_factura,v_usuario,v_uid),
            (v_tenant,now(),'ventas',v_venta_id::text,'5101','Costo de Ventas','gasto',round(v_costo_total,2),0,'Costo '||v_numero_factura,v_usuario,v_uid),
            (v_tenant,now(),'ventas',v_venta_id::text,'1301','Inventario','activo',0,round(v_costo_total,2),'Salida inventario '||v_numero_factura,v_usuario,v_uid);
    end if;

    insert into public.auditoria_eventos(
        empresa_id, usuario_id, usuario, accion, modulo, tabla,
        registro_id, detalle, metadata
    ) values (
        v_tenant, v_uid::text, v_usuario, 'venta_registrada', 'POS', 'ventas',
        v_venta_id::text, 'Venta interna registrada',
        jsonb_build_object('numero_factura',v_numero_factura,'total',round(v_total,2),'estado',v_estado)
    );

    return jsonb_build_object(
        'success',true, 'venta_id',v_venta_id, 'numero_factura',v_numero_factura,
        'ncf',null, 'subtotal',round(v_subtotal,2), 'itbis_total',round(v_itbis,2),
        'total',round(v_total,2), 'costo_total',round(v_costo_total,2)
    );
end;
$$;

revoke all on function public.api_registrar_venta(jsonb) from public, anon;
grant execute on function public.api_registrar_venta(jsonb) to authenticated;

-- Anulación completa. Una venta completada se conserva y se revierte; nunca se borra.
create or replace function public.api_anular_venta(p_venta_id text, p_motivo text)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_venta public.ventas%rowtype;
    v_det record;
    v_cons record;
    v_usuario text;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if coalesce(auth.jwt()->>'aal','aal1') <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    if length(trim(coalesce(p_motivo,''))) < 10 then raise exception 'VOID_REASON_REQUIRED'; end if;

    select * into v_venta from public.ventas
    where id = p_venta_id::uuid for update;
    if not found then raise exception 'SALE_NOT_FOUND'; end if;
    if not (
        public.has_tenant_permission(v_venta.empresa_id,'puede_anular')
        or public.has_tenant_permission(v_venta.empresa_id,'puede_editar_todo')
    ) then
        raise exception 'VOID_PERMISSION_DENIED';
    end if;
    if coalesce(v_venta.anulado,false) then
        return jsonb_build_object('success',true,'already_voided',true,'venta_id',v_venta.id);
    end if;
    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;

    for v_cons in
        select * from public.inventario_consumos
        where venta_id=v_venta.id and not restaurado
        for update
    loop
        if v_cons.lote_id is not null then
            update public.inventario_lotes
            set cantidad_restante=cantidad_restante+v_cons.cantidad, activo=true
            where id=v_cons.lote_id;
        end if;
        update public.productos
        set stock=coalesce(stock,0)+v_cons.cantidad,
            existencia=coalesce(existencia,stock,0)+v_cons.cantidad,
            cantidad=coalesce(cantidad,stock,0)+v_cons.cantidad,
            updated_at=now()
        where id=v_cons.producto_id and empresa_id=v_venta.empresa_id;
        update public.inventario_consumos set restaurado=true where id=v_cons.id;
    end loop;

    -- Compatibilidad con ventas históricas sin asignaciones FIFO: restaurar detalle una sola vez.
    if not exists(select 1 from public.inventario_consumos where venta_id=v_venta.id) then
        for v_det in
            select * from public.detalle_venta where venta_id=v_venta.id and not coalesce(anulado,false)
        loop
            update public.productos
            set stock=coalesce(stock,0)+v_det.cantidad,
                existencia=coalesce(existencia,stock,0)+v_det.cantidad,
                cantidad=coalesce(cantidad,stock,0)+v_det.cantidad,
                updated_at=now()
            where id=v_det.producto_id and empresa_id=v_venta.empresa_id;
        end loop;
    end if;

    update public.ventas_pagos set anulado=true where venta_id=v_venta.id;
    update public.movimientos_caja set anulado=true
    where empresa_id=v_venta.empresa_id and origen='venta' and referencia_id=v_venta.id::text;
    update public.cuentas_por_cobrar
    set anulado=true, estado='anulada', saldo_pendiente=0
    where empresa_id=v_venta.empresa_id and venta_id=v_venta.id;
    update public.detalle_venta
    set anulado=true, motivo_anulacion=left(trim(p_motivo),1000)
    where venta_id=v_venta.id;

    insert into public.movimientos_contables(
        empresa_id,fecha,modulo,referencia_id,cuenta_codigo,cuenta_nombre,
        tipo_cuenta,debito,credito,descripcion,usuario,usuario_id
    )
    select empresa_id,now(),'anulacion_venta',v_venta.id::text,cuenta_codigo,cuenta_nombre,
           tipo_cuenta,credito,debito,'Reverso: '||left(coalesce(descripcion,''),400),v_usuario,v_uid
    from public.movimientos_contables
    where empresa_id=v_venta.empresa_id and modulo='ventas' and referencia_id=v_venta.id::text;

    perform set_config('app.ais_authorized_ncf_transition','1',true);
    update public.ventas
    set anulado=true, estado='anulada', motivo_anulacion=left(trim(p_motivo),1000),
        anulada_por=v_uid, anulada_at=now(), updated_at=now()
    where id=v_venta.id;

    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_venta.empresa_id,v_uid::text,v_usuario,'venta_anulada','POS','ventas',
        v_venta.id::text,left(trim(p_motivo),2000),
        jsonb_build_object('total',v_venta.total,'numero_factura',v_venta.numero_factura,'ncf',v_venta.ncf)
    );
    return jsonb_build_object('success',true,'venta_id',v_venta.id);
end;
$$;

revoke all on function public.api_anular_venta(text,text) from public, anon;
grant execute on function public.api_anular_venta(text,text) to authenticated;

-- Permite únicamente la transición controlada de anulación; el contenido fiscal
-- de una venta con NCF sigue siendo inmutable.
create or replace function public.protect_ncf_sale()
returns trigger language plpgsql as $$
begin
    if old.ncf is not null and trim(old.ncf) <> '' then
        if current_setting('app.ais_authorized_ncf_transition',true) = '1'
           and old.anulado is distinct from true and new.anulado is true
           and new.ncf is not distinct from old.ncf
           and new.total is not distinct from old.total
           and new.empresa_id is not distinct from old.empresa_id then
            return new;
        end if;
        raise exception 'NCF_IMMUTABLE';
    end if;
    return new;
end;
$$;

drop trigger if exists trg_ventas_ncf_immutable on public.ventas;
drop trigger if exists trg_ncf_immutable on public.ventas;
create trigger trg_ventas_ncf_immutable
before update or delete on public.ventas
for each row execute function public.protect_ncf_sale();

-- Abonos: distribuye de forma FIFO con bloqueo y registra caja/contabilidad.
create or replace function public.api_registrar_abono(
    p_cuenta_id bigint,
    p_cliente_id bigint,
    p_monto numeric,
    p_metodo_pago text,
    p_caja_id text,
    p_observacion text default ''
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text;
    v_usuario text;
    v_restante numeric(18,2) := round(p_monto,2);
    v_aplicar numeric(18,2);
    v_total_saldo numeric(18,2);
    v_caja uuid := p_caja_id::uuid;
    v_cuenta record;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if v_restante <= 0 then raise exception 'INVALID_PAYMENT_AMOUNT'; end if;
    if p_cuenta_id is null and p_cliente_id is null then
        raise exception 'ACCOUNT_OR_CUSTOMER_REQUIRED';
    end if;
    if lower(trim(p_metodo_pago)) not in ('efectivo','transferencia','tarjeta') then
        raise exception 'INVALID_PAYMENT_METHOD';
    end if;

    select c.empresa_id into v_tenant from public.caja c
    where c.id=v_caja and lower(c.estado)='abierta' for update;
    if v_tenant is null or not public.has_tenant_permission(v_tenant,'ver_credito') then
        raise exception 'CREDIT_PAYMENT_PERMISSION_DENIED';
    end if;
    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;

    select coalesce(sum(cxc.saldo_pendiente),0) into v_total_saldo
    from public.cuentas_por_cobrar cxc
    where cxc.empresa_id=v_tenant and not coalesce(cxc.anulado,false)
      and cxc.saldo_pendiente>0
      and (p_cuenta_id is null or cxc.id=p_cuenta_id)
      and (p_cliente_id is null or cxc.cliente_id=p_cliente_id);
    if v_total_saldo < v_restante then raise exception 'PAYMENT_EXCEEDS_BALANCE'; end if;

    for v_cuenta in
        select * from public.cuentas_por_cobrar cxc
        where cxc.empresa_id=v_tenant and not coalesce(cxc.anulado,false)
          and cxc.saldo_pendiente>0
          and (p_cuenta_id is null or cxc.id=p_cuenta_id)
          and (p_cliente_id is null or cxc.cliente_id=p_cliente_id)
        order by cxc.fecha,cxc.id for update
    loop
        exit when v_restante<=0;
        v_aplicar := least(v_restante,v_cuenta.saldo_pendiente);
        insert into public.abonos_credito(
            empresa_id,cuenta_id,cliente_id,cliente_nombre,monto,metodo_pago,
            fecha,usuario,usuario_id,caja_id,observacion
        ) values (
            v_tenant,v_cuenta.id,v_cuenta.cliente_id,v_cuenta.cliente_nombre,
            v_aplicar,lower(trim(p_metodo_pago)),now(),v_usuario,v_uid,v_caja,
            left(coalesce(p_observacion,''),1000)
        );
        update public.cuentas_por_cobrar
        set monto_abonado=coalesce(monto_abonado,0)+v_aplicar,
            saldo_pendiente=saldo_pendiente-v_aplicar,
            estado=case when saldo_pendiente-v_aplicar<=0.01 then 'saldada' else 'pendiente' end
        where id=v_cuenta.id;
        v_restante := v_restante-v_aplicar;
    end loop;

    insert into public.movimientos_caja(
        empresa_id,fecha,dia_operativo,caja_id,tipo_movimiento,origen,
        referencia_id,metodo_pago,monto,descripcion,usuario,usuario_id,anulado
    ) values (
        v_tenant,now(),current_date::text,v_caja,'entrada','abono_credito',
        coalesce(p_cuenta_id::text,p_cliente_id::text),lower(trim(p_metodo_pago)),
        round(p_monto,2),'Abono de cuenta por cobrar',v_usuario,v_uid,false
    );
    insert into public.movimientos_contables(
        empresa_id,fecha,modulo,referencia_id,cuenta_codigo,cuenta_nombre,
        tipo_cuenta,debito,credito,descripcion,usuario,usuario_id
    ) values
        (v_tenant,now(),'abono_credito',coalesce(p_cuenta_id::text,p_cliente_id::text),
         case when lower(trim(p_metodo_pago))='efectivo' then '1101' else '1102' end,
         case when lower(trim(p_metodo_pago))='efectivo' then 'Efectivo / Caja' else 'Banco / Depósito' end,
         'activo',round(p_monto,2),0,'Cobro de cuenta por cobrar',v_usuario,v_uid),
        (v_tenant,now(),'abono_credito',coalesce(p_cuenta_id::text,p_cliente_id::text),
         '1201','Cuentas por Cobrar','activo',0,round(p_monto,2),
         'Reducción de cuenta por cobrar',v_usuario,v_uid);

    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_tenant,v_uid::text,v_usuario,'abono_registrado','Créditos','cuentas_por_cobrar',
        coalesce(p_cuenta_id::text,p_cliente_id::text),'Abono transaccional',
        jsonb_build_object('monto',round(p_monto,2),'metodo',lower(trim(p_metodo_pago)))
    );
    return jsonb_build_object('success',true,'monto_aplicado',round(p_monto,2));
end;
$$;

revoke all on function public.api_registrar_abono(bigint,bigint,numeric,text,text,text) from public, anon;
grant execute on function public.api_registrar_abono(bigint,bigint,numeric,text,text,text) to authenticated;

-- Apertura de caja única por usuario y empresa.
create or replace function public.api_abrir_caja(
    p_monto_inicial numeric,
    p_observacion text default ''
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text;
    v_usuario text;
    v_caja_id uuid;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if p_monto_inicial < 0 then raise exception 'INVALID_INITIAL_CASH'; end if;
    select tm.tenant_id into v_tenant
    from public.tenant_memberships tm
    where tm.user_id=v_uid and tm.active
      and (
          tm.role='admin'
          or coalesce(tm.permissions->'puede_abrir_caja','false'::jsonb)='true'::jsonb
          or coalesce(tm.permissions->'puede_vender','false'::jsonb)='true'::jsonb
      )
    order by tm.created_at limit 1;
    if v_tenant is null then raise exception 'OPEN_CASH_PERMISSION_DENIED'; end if;
    perform pg_advisory_xact_lock(hashtext(v_tenant||':'||v_uid::text||':caja'));
    if exists (
        select 1 from public.caja c
        where c.empresa_id=v_tenant and c.usuario_id=v_uid
          and lower(coalesce(c.estado,''))='abierta'
    ) then
        raise exception 'CASH_REGISTER_ALREADY_OPEN';
    end if;
    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;
    insert into public.caja(
        empresa_id,usuario_id,usuario,fecha_apertura,monto_inicial,
        efectivo_inicial,estado,dia_operativo,observacion,anulado
    ) values (
        v_tenant,v_uid,v_usuario,now(),round(p_monto_inicial,2),
        round(p_monto_inicial,2),'abierta',current_date::text,
        left(coalesce(p_observacion,''),1000),false
    ) returning id into v_caja_id;
    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_tenant,v_uid::text,v_usuario,'caja_abierta','Caja','caja',v_caja_id::text,
        'Apertura transaccional',
        jsonb_build_object('monto_inicial',round(p_monto_inicial,2))
    );
    return jsonb_build_object('success',true,'caja_id',v_caja_id);
end;
$$;

revoke all on function public.api_abrir_caja(numeric,text) from public, anon;
grant execute on function public.api_abrir_caja(numeric,text) to authenticated;

-- Cierre de caja calculado desde movimientos persistidos.
create or replace function public.api_cerrar_caja(
    p_caja_id text,
    p_efectivo_contado numeric,
    p_observacion text default ''
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_caja public.caja%rowtype;
    v_inicial numeric(18,2);
    v_efectivo numeric(18,2);
    v_esperado numeric(18,2);
    v_diferencia numeric(18,2);
    v_usuario text;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    select * into v_caja from public.caja where id=p_caja_id::uuid for update;
    if not found or lower(v_caja.estado)<>'abierta' then raise exception 'CASH_REGISTER_NOT_OPEN'; end if;
    if not public.has_tenant_permission(v_caja.empresa_id,'puede_cerrar_caja') then
        raise exception 'CLOSE_CASH_PERMISSION_DENIED';
    end if;
    if p_efectivo_contado<0 then raise exception 'INVALID_COUNTED_CASH'; end if;
    v_inicial := coalesce(v_caja.monto_inicial,v_caja.efectivo_inicial,0);
    select coalesce(sum(case when mc.tipo_movimiento='salida' then -mc.monto else mc.monto end),0)
    into v_efectivo
    from public.movimientos_caja mc
    where mc.empresa_id=v_caja.empresa_id and mc.caja_id=v_caja.id
      and lower(mc.metodo_pago)='efectivo' and not coalesce(mc.anulado,false);
    v_esperado := round(v_inicial+v_efectivo,2);
    v_diferencia := round(p_efectivo_contado-v_esperado,2);
    if abs(v_diferencia)>0.01 and length(trim(coalesce(p_observacion,'')))<10 then
        raise exception 'CASH_DIFFERENCE_REASON_REQUIRED';
    end if;
    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;

    update public.caja set
        estado='cerrada',fecha_cierre=now(),efectivo_contado=round(p_efectivo_contado,2),
        efectivo_esperado=v_esperado,diferencia=v_diferencia,
        faltante=greatest(-v_diferencia,0),sobrante=greatest(v_diferencia,0),
        observacion=left(coalesce(p_observacion,''),1000)
    where id=v_caja.id;
    insert into public.cierre_caja(
        empresa_id,caja_id,usuario_id,monto_inicial,efectivo_esperado,
        efectivo_contado,diferencia,observacion
    ) values (
        v_caja.empresa_id,v_caja.id,v_uid,v_inicial,v_esperado,
        round(p_efectivo_contado,2),v_diferencia,left(coalesce(p_observacion,''),1000)
    );
    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_caja.empresa_id,v_uid::text,v_usuario,'caja_cerrada','Caja','caja',v_caja.id::text,
        'Cierre transaccional',
        jsonb_build_object('esperado',v_esperado,'contado',round(p_efectivo_contado,2),'diferencia',v_diferencia)
    );
    return jsonb_build_object('success',true,'efectivo_esperado',v_esperado,'diferencia',v_diferencia);
end;
$$;

revoke all on function public.api_cerrar_caja(text,numeric,text) from public, anon;
grant execute on function public.api_cerrar_caja(text,numeric,text) to authenticated;

commit;
```

## 3. Mantenimiento, contabilidad, nómina y factura de compra atómica

```sql
-- A&M v3.0 — Edición segura, cierre contable y nómina

begin;

-- Las ventas completadas nunca se editan: se anulan y se registra una nueva.
-- Una cuenta abierta sí puede reemplazarse de forma atómica.
create or replace function public.api_editar_venta(
    p_venta_id text,
    p_items jsonb,
    p_metodo_pago text default 'abierta'
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_old public.ventas%rowtype;
    v_cons record;
    v_result jsonb;
    v_payload jsonb;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if coalesce(auth.jwt()->>'aal','aal1') <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    select * into v_old from public.ventas where id=p_venta_id::uuid for update;
    if not found then raise exception 'SALE_NOT_FOUND'; end if;
    if not (
        public.has_tenant_permission(v_old.empresa_id,'puede_editar_ventas')
        or public.has_tenant_permission(v_old.empresa_id,'puede_editar_todo')
    ) then
        raise exception 'EDIT_SALE_PERMISSION_DENIED';
    end if;
    if coalesce(v_old.anulado,false) then raise exception 'SALE_ALREADY_VOIDED'; end if;
    if lower(coalesce(v_old.estado,'')) <> 'abierta' then
        raise exception 'COMPLETED_SALE_CANNOT_BE_EDITED: anule y registre una nueva venta';
    end if;
    if v_old.ncf is not null and trim(v_old.ncf)<>'' then raise exception 'NCF_IMMUTABLE'; end if;
    if jsonb_typeof(p_items)<>'array' or jsonb_array_length(p_items)=0 then
        raise exception 'SALE_ITEMS_REQUIRED';
    end if;

    for v_cons in
        select * from public.inventario_consumos
        where venta_id=v_old.id and not restaurado for update
    loop
        if v_cons.lote_id is not null then
            update public.inventario_lotes
            set cantidad_restante=cantidad_restante+v_cons.cantidad, activo=true
            where id=v_cons.lote_id;
        end if;
        update public.productos
        set stock=coalesce(stock,0)+v_cons.cantidad,
            existencia=coalesce(existencia,stock,0)+v_cons.cantidad,
            cantidad=coalesce(cantidad,stock,0)+v_cons.cantidad,
            updated_at=now()
        where id=v_cons.producto_id and empresa_id=v_old.empresa_id;
        update public.inventario_consumos set restaurado=true where id=v_cons.id;
    end loop;

    v_payload := jsonb_build_object(
        'empresa_id',v_old.empresa_id,
        'estado','abierta',
        'caja_id',v_old.caja_id,
        'cliente_id',v_old.cliente_id,
        'cliente_nombre',v_old.cliente_nombre,
        'dia_operativo',v_old.dia_operativo,
        'observacion',coalesce(v_old.observacion,'') || ' | Reemplaza ' || v_old.id::text,
        'es_factura_fiscal',false,
        'items',p_items,
        'pagos','[]'::jsonb
    );
    v_result := public.api_registrar_venta(v_payload);
    if coalesce((v_result->>'success')::boolean,false) is not true then
        raise exception 'REPLACEMENT_SALE_FAILED';
    end if;

    update public.detalle_venta
    set anulado=true,motivo_anulacion='Cuenta abierta reemplazada'
    where venta_id=v_old.id;
    update public.ventas
    set anulado=true,estado='reemplazada',
        motivo_anulacion='Reemplazada por '||(v_result->>'venta_id'),
        anulada_por=v_uid,anulada_at=now(),updated_at=now()
    where id=v_old.id;

    insert into public.auditoria_eventos(
        empresa_id,usuario_id,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_old.empresa_id,v_uid::text,'cuenta_abierta_reemplazada','POS','ventas',v_old.id::text,
        'Edición atómica de cuenta abierta',
        jsonb_build_object('venta_nueva',v_result->>'venta_id')
    );
    return v_result || jsonb_build_object('replaced_sale_id',v_old.id);
end;
$$;

revoke all on function public.api_editar_venta(text,jsonb,text) from public, anon;
grant execute on function public.api_editar_venta(text,jsonb,text) to authenticated;

-- Reemplaza o cobra una cuenta abierta usando el mismo motor transaccional del
-- POS. Si algo falla, PostgreSQL revierte inventario, venta y pagos completos.
create or replace function public.api_reemplazar_cuenta_abierta(
    p_venta_id text,
    p_payload jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_old public.ventas%rowtype;
    v_cons record;
    v_det record;
    v_result jsonb;
    v_payload jsonb;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if coalesce(auth.jwt()->>'aal','aal1') <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    select * into v_old
    from public.ventas
    where id=p_venta_id::uuid
    for update;
    if not found then raise exception 'SALE_NOT_FOUND'; end if;
    if not (
        public.has_tenant_permission(v_old.empresa_id,'puede_editar_ventas')
        or public.has_tenant_permission(v_old.empresa_id,'puede_editar_todo')
    ) then
        raise exception 'EDIT_SALE_PERMISSION_DENIED';
    end if;
    if coalesce(v_old.anulado,false) then raise exception 'SALE_ALREADY_VOIDED'; end if;
    if lower(coalesce(v_old.estado,'')) <> 'abierta' then
        raise exception 'ONLY_OPEN_SALES_CAN_BE_REPLACED';
    end if;
    if coalesce(trim(v_old.ncf),'')<>'' then raise exception 'NCF_IMMUTABLE'; end if;
    if exists (
        select 1 from public.ventas_pagos vp
        where vp.venta_id=v_old.id and not coalesce(vp.anulado,false)
    ) then
        raise exception 'OPEN_SALE_HAS_PAYMENTS: anule los pagos mediante un flujo autorizado';
    end if;

    for v_cons in
        select * from public.inventario_consumos
        where venta_id=v_old.id and not restaurado
        for update
    loop
        if v_cons.lote_id is not null then
            update public.inventario_lotes
            set cantidad_restante=cantidad_restante+v_cons.cantidad, activo=true
            where id=v_cons.lote_id;
        end if;
        update public.productos
        set stock=coalesce(stock,0)+v_cons.cantidad,
            existencia=coalesce(existencia,stock,0)+v_cons.cantidad,
            cantidad=coalesce(cantidad,stock,0)+v_cons.cantidad,
            updated_at=now()
        where id=v_cons.producto_id and empresa_id=v_old.empresa_id;
        update public.inventario_consumos set restaurado=true where id=v_cons.id;
    end loop;

    if not exists (
        select 1 from public.inventario_consumos where venta_id=v_old.id
    ) then
        for v_det in
            select * from public.detalle_venta
            where venta_id=v_old.id and not coalesce(anulado,false)
        loop
            update public.productos
            set stock=coalesce(stock,0)+v_det.cantidad,
                existencia=coalesce(existencia,stock,0)+v_det.cantidad,
                cantidad=coalesce(cantidad,stock,0)+v_det.cantidad,
                updated_at=now()
            where id=v_det.producto_id and empresa_id=v_old.empresa_id;
        end loop;
    end if;

    v_payload := coalesce(p_payload,'{}'::jsonb) || jsonb_build_object(
        'empresa_id',v_old.empresa_id,
        'caja_id',v_old.caja_id,
        'es_factura_fiscal',false
    );
    v_result := public.api_registrar_venta(v_payload);

    update public.detalle_venta
    set anulado=true,motivo_anulacion='Cuenta abierta reemplazada'
    where venta_id=v_old.id;
    update public.ventas
    set anulado=true,estado='reemplazada',
        motivo_anulacion='Reemplazada por '||(v_result->>'venta_id'),
        anulada_por=v_uid,anulada_at=now(),updated_at=now()
    where id=v_old.id;
    insert into public.auditoria_eventos(
        empresa_id,usuario_id,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_old.empresa_id,v_uid::text,'cuenta_abierta_reemplazada','POS','ventas',v_old.id::text,
        'Cuenta abierta reemplazada o cobrada de forma atómica',
        jsonb_build_object(
            'venta_nueva',v_result->>'venta_id',
            'estado_nuevo',v_payload->>'estado'
        )
    );
    return v_result || jsonb_build_object('replaced_sale_id',v_old.id);
end;
$$;

revoke all on function public.api_reemplazar_cuenta_abierta(text,jsonb) from public, anon;
grant execute on function public.api_reemplazar_cuenta_abierta(text,jsonb) to authenticated;

-- Factura de compra completa: cabecera, líneas, compras históricas, stock,
-- lotes FIFO, contabilidad y auditoría se confirman o revierten juntas.
create or replace function public.api_registrar_factura_compra(p jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text := nullif(trim(p->>'tenant_id'),'');
    v_idempotency_key uuid;
    v_request_hash text;
    v_existing public.facturas_compra%rowtype;
    v_factura_id uuid;
    v_compra_id uuid;
    v_usuario text;
    v_fecha timestamptz := coalesce(nullif(p->>'fecha','')::timestamptz,now());
    v_numero text := trim(coalesce(p->>'numero',''));
    v_referencia text := trim(coalesce(p->>'referencia',''));
    v_proveedor text := trim(coalesce(p->>'proveedor',''));
    v_descripcion text := trim(coalesce(p->>'descripcion',''));
    v_metodo text := lower(trim(coalesce(p->>'metodo','efectivo')));
    v_items jsonb := coalesce(p->'items','[]'::jsonb);
    v_item jsonb;
    v_producto public.productos%rowtype;
    v_producto_id uuid;
    v_cantidad numeric(18,4);
    v_costo numeric(18,4);
    v_total_linea numeric(18,2);
    v_total numeric(18,2) := 0;
    v_stock numeric(18,4);
    v_costo_anterior numeric(18,4);
    v_costo_promedio numeric(18,4);
    v_productos_validos integer;
    v_item_count integer;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if v_tenant is null then raise exception 'TENANT_REQUIRED'; end if;
    if not public.has_tenant_permission(v_tenant,'puede_registrar_compras') then
        raise exception 'PURCHASE_PERMISSION_DENIED';
    end if;

    begin
        v_idempotency_key := nullif(p->>'idempotency_key','')::uuid;
    exception when others then
        raise exception 'INVALID_IDEMPOTENCY_KEY';
    end;
    if v_idempotency_key is null then raise exception 'IDEMPOTENCY_KEY_REQUIRED'; end if;
    if jsonb_typeof(v_items) <> 'array' then raise exception 'INVALID_PURCHASE_ITEMS'; end if;
    v_item_count := jsonb_array_length(v_items);
    if v_item_count < 1 or v_item_count > 500 then raise exception 'INVALID_PURCHASE_ITEM_COUNT'; end if;
    if v_numero = '' then raise exception 'PURCHASE_NUMBER_REQUIRED'; end if;
    if v_proveedor = '' then raise exception 'PURCHASE_SUPPLIER_REQUIRED'; end if;
    if v_metodo not in ('efectivo','transferencia','tarjeta','credito') then
        raise exception 'INVALID_PURCHASE_METHOD';
    end if;

    v_request_hash := encode(
        digest(convert_to((p - 'idempotency_key')::text,'UTF8'),'sha256'),
        'hex'
    );
    perform pg_advisory_xact_lock(
        hashtextextended(v_tenant || ':' || v_idempotency_key::text,0)
    );

    select * into v_existing
    from public.facturas_compra fc
    where fc.empresa_id=v_tenant and fc.idempotency_key=v_idempotency_key;
    if found then
        if v_existing.request_hash <> v_request_hash then
            raise exception 'IDEMPOTENCY_PAYLOAD_MISMATCH';
        end if;
        return jsonb_build_object(
            'success',true,'idempotent',true,'factura_id',v_existing.id,
            'total',v_existing.total,'items',v_item_count
        );
    end if;

    if exists (
        select 1
        from jsonb_array_elements(v_items) item
        group by item->>'producto_id'
        having count(*) > 1
    ) then
        raise exception 'DUPLICATE_PURCHASE_PRODUCT';
    end if;

    -- Validar tipos antes de bloquear; ningún cambio se realiza en esta fase.
    for v_item in select value from jsonb_array_elements(v_items)
    loop
        begin
            v_producto_id := nullif(v_item->>'producto_id','')::uuid;
            v_cantidad := round(coalesce((v_item->>'cantidad')::numeric,0),4);
            v_costo := round(coalesce((v_item->>'costo_unitario')::numeric,0),4);
        exception when others then
            raise exception 'INVALID_PURCHASE_ITEM';
        end;
        if v_producto_id is null then raise exception 'PURCHASE_PRODUCT_REQUIRED'; end if;
        if v_cantidad <= 0 then raise exception 'INVALID_PURCHASE_QUANTITY'; end if;
        if v_costo < 0 then raise exception 'INVALID_PURCHASE_COST'; end if;
    end loop;

    -- Orden estable de bloqueo para impedir interbloqueos entre facturas.
    perform 1
    from public.productos pr
    where pr.empresa_id=v_tenant
      and pr.id in (
        select (item->>'producto_id')::uuid
        from jsonb_array_elements(v_items) item
    )
    order by pr.id
    for update;

    select count(*) into v_productos_validos
    from public.productos pr
    where pr.empresa_id=v_tenant
      and coalesce(pr.activo,true)
      and not coalesce(pr.anulado,false)
      and pr.id in (
          select (item->>'producto_id')::uuid
          from jsonb_array_elements(v_items) item
      );
    if v_productos_validos <> v_item_count then
        raise exception 'PRODUCT_NOT_FOUND_OR_FORBIDDEN';
    end if;

    for v_item in select value from jsonb_array_elements(v_items)
    loop
        v_cantidad := round((v_item->>'cantidad')::numeric,4);
        v_costo := round((v_item->>'costo_unitario')::numeric,4);
        v_total := v_total + round(v_cantidad*v_costo,2);
    end loop;
    v_total := round(v_total,2);

    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;

    insert into public.facturas_compra(
        empresa_id,idempotency_key,request_hash,fecha,numero,referencia,
        proveedor,descripcion,metodo,total,monto_abonado,saldo_pendiente,
        usuario,usuario_id
    ) values (
        v_tenant,v_idempotency_key,v_request_hash,v_fecha,left(v_numero,100),
        left(v_referencia,200),left(v_proveedor,200),left(v_descripcion,2000),
        v_metodo,v_total,case when v_metodo='credito' then 0 else v_total end,
        case when v_metodo='credito' then v_total else 0 end,v_usuario,v_uid
    ) returning id into v_factura_id;

    for v_item in select value from jsonb_array_elements(v_items)
    loop
        v_producto_id := (v_item->>'producto_id')::uuid;
        v_cantidad := round((v_item->>'cantidad')::numeric,4);
        v_costo := round((v_item->>'costo_unitario')::numeric,4);
        v_total_linea := round(v_cantidad*v_costo,2);
        select * into strict v_producto
        from public.productos pr where pr.id=v_producto_id and pr.empresa_id=v_tenant;

        v_stock := coalesce(v_producto.stock,v_producto.existencia,v_producto.cantidad,0);
        v_costo_anterior := coalesce(v_producto.costo_unitario,v_producto.costo,0);
        v_costo_promedio := case
            when v_stock+v_cantidad>0 then round(
                ((v_stock*v_costo_anterior)+(v_cantidad*v_costo))/(v_stock+v_cantidad),4
            )
            else v_costo
        end;

        insert into public.compras(
            empresa_id,fecha,numero,proveedor,descripcion,monto,total,metodo,
            producto_id,producto,cantidad,costo_unitario,costo,usuario,usuario_id,
            anulado,monto_abonado,saldo_pendiente,factura_compra_id
        ) values (
            v_tenant,v_fecha,left(v_numero,100),left(v_proveedor,200),
            left(coalesce(nullif(trim(v_item->>'descripcion'),''),nullif(v_descripcion,''),'Compra de '||v_producto.nombre),2000),
            v_total_linea,v_total_linea,v_metodo,v_producto.id,v_producto.nombre,
            v_cantidad,v_costo,v_costo,v_usuario,v_uid,false,
            case when v_metodo='credito' then 0 else v_total_linea end,
            case when v_metodo='credito' then v_total_linea else 0 end,v_factura_id
        ) returning id into v_compra_id;

        update public.productos
        set stock=v_stock+v_cantidad,existencia=v_stock+v_cantidad,
            cantidad=v_stock+v_cantidad,costo=v_costo_promedio,
            costo_unitario=v_costo_promedio,updated_at=now()
        where id=v_producto.id and empresa_id=v_tenant;

        insert into public.inventario_lotes(
            empresa_id,producto_id,producto,compra_id,cantidad_inicial,
            cantidad_restante,costo_unitario,fecha_compra,activo
        ) values (
            v_tenant,v_producto.id,v_producto.nombre,v_compra_id,v_cantidad,
            v_cantidad,v_costo,v_fecha,true
        );

        insert into public.detalle_factura_compra(
            empresa_id,factura_id,compra_id,producto_id,producto,cantidad,
            costo_unitario,total_linea
        ) values (
            v_tenant,v_factura_id,v_compra_id,v_producto.id,v_producto.nombre,
            v_cantidad,v_costo,v_total_linea
        );
    end loop;

    insert into public.movimientos_contables(
        empresa_id,fecha,modulo,referencia_id,cuenta_codigo,cuenta_nombre,
        tipo_cuenta,debito,credito,descripcion,usuario,usuario_id
    ) values
        (v_tenant,v_fecha,'compras',v_factura_id::text,'1301','Inventario',
         'activo',v_total,0,'Factura de compra '||left(v_numero,100),v_usuario,v_uid),
        (v_tenant,v_fecha,'compras',v_factura_id::text,
         case when v_metodo='credito' then '2101' when v_metodo='efectivo' then '1101' else '1102' end,
         case when v_metodo='credito' then 'Cuentas por Pagar' when v_metodo='efectivo' then 'Efectivo / Caja' else 'Banco / Depósito' end,
         case when v_metodo='credito' then 'pasivo' else 'activo' end,
         0,v_total,'Contrapartida factura de compra',v_usuario,v_uid);

    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_tenant,v_uid::text,v_usuario,'factura_compra_registrada','Compras',
        'facturas_compra',v_factura_id::text,
        'Factura, inventario y contabilidad registrados atómicamente',
        jsonb_build_object('numero',left(v_numero,100),'items',v_item_count,'total',v_total)
    );

    return jsonb_build_object(
        'success',true,'idempotent',false,'factura_id',v_factura_id,
        'total',v_total,'items',v_item_count
    );
end;
$$;

revoke all on function public.api_registrar_factura_compra(jsonb) from public, anon;
grant execute on function public.api_registrar_factura_compra(jsonb) to authenticated;

-- Entrada de mercancía: compra, stock, lote FIFO, saldo y asiento en una sola
-- transacción. Los totales enviados por el cliente no se utilizan.
create or replace function public.api_registrar_compra_producto(p jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text := nullif(trim(p->>'tenant_id'),'');
    v_usuario text;
    v_producto public.productos%rowtype;
    v_producto_id uuid := nullif(p->>'producto_id','')::uuid;
    v_cantidad numeric(18,4) := round(coalesce((p->>'cantidad')::numeric,0),4);
    v_costo numeric(18,4) := round(coalesce((p->>'costo_unitario')::numeric,0),4);
    v_total numeric(18,2);
    v_stock numeric(18,4);
    v_costo_anterior numeric(18,4);
    v_costo_promedio numeric(18,4);
    v_metodo text := lower(trim(coalesce(p->>'metodo','efectivo')));
    v_fecha timestamptz := coalesce(nullif(p->>'fecha','')::timestamptz,now());
    v_compra_id uuid;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if v_cantidad<=0 then raise exception 'INVALID_PURCHASE_QUANTITY'; end if;
    if v_costo<0 then raise exception 'INVALID_PURCHASE_COST'; end if;
    if v_metodo not in ('efectivo','transferencia','tarjeta','credito') then
        raise exception 'INVALID_PURCHASE_METHOD';
    end if;
    if v_tenant is null then
        select tm.tenant_id into v_tenant
        from public.tenant_memberships tm
        where tm.user_id=v_uid and tm.active
          and (
              tm.role='admin'
              or coalesce(tm.permissions->'puede_registrar_compras','false'::jsonb)='true'::jsonb
          )
        order by tm.created_at limit 1;
    end if;
    if v_tenant is null
       or not public.has_tenant_permission(v_tenant,'puede_registrar_compras') then
        raise exception 'PURCHASE_PERMISSION_DENIED';
    end if;
    select * into v_producto
    from public.productos pr
    where pr.id=v_producto_id and pr.empresa_id=v_tenant
      and coalesce(pr.activo,true) and not coalesce(pr.anulado,false)
    for update;
    if not found then raise exception 'PRODUCT_NOT_FOUND_OR_FORBIDDEN'; end if;

    v_total := round(v_cantidad*v_costo,2);
    v_stock := coalesce(v_producto.stock,v_producto.existencia,v_producto.cantidad,0);
    v_costo_anterior := coalesce(v_producto.costo_unitario,v_producto.costo,0);
    v_costo_promedio := case
        when v_stock+v_cantidad>0
        then round(((v_stock*v_costo_anterior)+(v_cantidad*v_costo))/(v_stock+v_cantidad),4)
        else v_costo end;
    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;

    insert into public.compras(
        empresa_id,fecha,numero,proveedor,descripcion,monto,total,metodo,
        producto_id,producto,cantidad,costo_unitario,costo,usuario,usuario_id,
        anulado,monto_abonado,saldo_pendiente
    ) values (
        v_tenant,v_fecha,left(coalesce(p->>'numero',''),100),
        left(coalesce(p->>'proveedor',''),200),
        left(coalesce(p->>'descripcion','Compra de '||v_producto.nombre),2000),
        v_total,v_total,v_metodo,v_producto.id,v_producto.nombre,v_cantidad,
        v_costo,v_costo,v_usuario,v_uid,false,
        case when v_metodo='credito' then 0 else v_total end,
        case when v_metodo='credito' then v_total else 0 end
    ) returning id into v_compra_id;

    update public.productos
    set stock=v_stock+v_cantidad,existencia=v_stock+v_cantidad,
        cantidad=v_stock+v_cantidad,costo=v_costo_promedio,
        costo_unitario=v_costo_promedio,updated_at=now()
    where id=v_producto.id;
    insert into public.inventario_lotes(
        empresa_id,producto_id,producto,compra_id,cantidad_inicial,
        cantidad_restante,costo_unitario,fecha_compra,activo
    ) values (
        v_tenant,v_producto.id,v_producto.nombre,v_compra_id,v_cantidad,
        v_cantidad,v_costo,v_fecha,true
    );
    insert into public.movimientos_contables(
        empresa_id,fecha,modulo,referencia_id,cuenta_codigo,cuenta_nombre,
        tipo_cuenta,debito,credito,descripcion,usuario,usuario_id
    ) values
        (v_tenant,v_fecha,'compras',v_compra_id::text,'1301','Inventario',
         'activo',v_total,0,'Entrada de inventario',v_usuario,v_uid),
        (v_tenant,v_fecha,'compras',v_compra_id::text,
         case when v_metodo='credito' then '2101' when v_metodo='efectivo' then '1101' else '1102' end,
         case when v_metodo='credito' then 'Cuentas por Pagar' when v_metodo='efectivo' then 'Efectivo / Caja' else 'Banco / Depósito' end,
         case when v_metodo='credito' then 'pasivo' else 'activo' end,
         0,v_total,'Contrapartida de compra',v_usuario,v_uid);
    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_tenant,v_uid::text,v_usuario,'compra_registrada','Compras','compras',
        v_compra_id::text,'Compra e inventario registrados atómicamente',
        jsonb_build_object('producto_id',v_producto.id,'cantidad',v_cantidad,'total',v_total)
    );
    return jsonb_build_object(
        'success',true,'compra_id',v_compra_id,'total',v_total,
        'stock_nuevo',v_stock+v_cantidad,'costo_promedio',v_costo_promedio
    );
end;
$$;

revoke all on function public.api_registrar_compra_producto(jsonb) from public, anon;
grant execute on function public.api_registrar_compra_producto(jsonb) to authenticated;

-- Cierre contable: solo congela un periodo balanceado. No calcula una utilidad
-- simplificada ni crea asientos de cero.
create or replace function public.api_cerrar_periodo(
    p_ano integer,
    p_mes integer,
    p_observacion text default ''
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text;
    v_desde date;
    v_hasta date;
    v_debito numeric(18,2);
    v_credito numeric(18,2);
    v_ventas numeric(18,2);
    v_itbis numeric(18,2);
    v_costo numeric(18,2);
    v_gastos numeric(18,2);
    v_periodo uuid;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if coalesce(auth.jwt()->>'aal','aal1') <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    if p_ano not between 2000 and 2200 or p_mes not between 1 and 12 then
        raise exception 'INVALID_PERIOD';
    end if;
    select tm.tenant_id into v_tenant
    from public.tenant_memberships tm
    where tm.user_id=v_uid and tm.active
      and (
          tm.role='admin'
          or coalesce(tm.permissions->'puede_cerrar_periodo','false'::jsonb)='true'::jsonb
      )
    order by tm.created_at limit 1;
    if public.is_platform_superadmin() then
        raise exception 'SELECT_A_COMPANY_BEFORE_CLOSING';
    end if;
    if v_tenant is null then raise exception 'CLOSE_PERIOD_PERMISSION_DENIED'; end if;

    v_desde := make_date(p_ano,p_mes,1);
    v_hasta := (v_desde + interval '1 month')::date;
    perform pg_advisory_xact_lock(hashtext(v_tenant||':'||p_ano||':'||p_mes));

    if exists(
        select 1 from public.periodos_contables
        where empresa_id=v_tenant and ano=p_ano and mes=p_mes and estado='cerrado'
    ) then raise exception 'PERIOD_ALREADY_CLOSED'; end if;

    select round(coalesce(sum(mc.debito),0),2),round(coalesce(sum(mc.credito),0),2)
    into v_debito,v_credito
    from public.movimientos_contables mc
    where mc.empresa_id=v_tenant and mc.fecha>=v_desde and mc.fecha<v_hasta;
    if abs(v_debito-v_credito)>0.01 then
        raise exception 'UNBALANCED_LEDGER: debito %, credito %',v_debito,v_credito;
    end if;
    if exists(
        select 1 from public.productos p
        where p.empresa_id=v_tenant and coalesce(p.stock,p.existencia,p.cantidad,0)<0
    ) then raise exception 'NEGATIVE_INVENTORY_EXISTS'; end if;

    select round(coalesce(sum(v.total),0),2),round(coalesce(sum(v.itbis_total),0),2)
    into v_ventas,v_itbis from public.ventas v
    where v.empresa_id=v_tenant and v.fecha>=v_desde and v.fecha<v_hasta
      and not coalesce(v.anulado,false) and lower(v.estado)='completada';
    select round(coalesce(sum(dv.costo_total),0),2) into v_costo
    from public.detalle_venta dv join public.ventas v on v.id=dv.venta_id
    where v.empresa_id=v_tenant and v.fecha>=v_desde and v.fecha<v_hasta
      and not coalesce(v.anulado,false) and not coalesce(dv.anulado,false);
    select round(coalesce(sum(g.monto),0),2) into v_gastos
    from public.gastos g
    where g.empresa_id=v_tenant and g.fecha>=v_desde and g.fecha<v_hasta
      and not coalesce(g.anulado,false);

    insert into public.periodos_contables(
        empresa_id,ano,mes,estado,cerrado_por,cerrado_at,observacion,resumen
    ) values (
        v_tenant,p_ano,p_mes,'cerrado',v_uid,now(),left(coalesce(p_observacion,''),1000),
        jsonb_build_object(
            'ventas',v_ventas,'itbis_ventas',v_itbis,'costo_ventas',v_costo,
            'gastos',v_gastos,'margen_operativo_no_fiscal',v_ventas-v_itbis-v_costo-v_gastos,
            'debitos',v_debito,'creditos',v_credito
        )
    ) returning id into v_periodo;
    insert into public.auditoria_eventos(
        empresa_id,usuario_id,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_tenant,v_uid::text,'periodo_cerrado','Contabilidad','periodos_contables',v_periodo::text,
        'Periodo cerrado después de validar balance e inventario',
        jsonb_build_object('ano',p_ano,'mes',p_mes,'debitos',v_debito,'creditos',v_credito)
    );
    return jsonb_build_object(
        'success',true,'periodo_id',v_periodo,'ano',p_ano,'mes',p_mes,
        'resumen',jsonb_build_object(
            'ventas',v_ventas,'itbis_ventas',v_itbis,'costo_ventas',v_costo,
            'gastos',v_gastos,'margen_operativo_no_fiscal',v_ventas-v_itbis-v_costo-v_gastos
        )
    );
end;
$$;

revoke all on function public.api_cerrar_periodo(integer,integer,text) from public, anon;
grant execute on function public.api_cerrar_periodo(integer,integer,text) to authenticated;

-- Nómina calculada desde salario mensual y parámetros versionados.
create or replace function public.api_registrar_nomina(
    p_empleado_id text,
    p_periodo text,
    p_fecha text,
    p_metodo_pago text,
    p_observacion text default ''
) returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
    v_tenant text;
    v_emp public.empleados%rowtype;
    v_params public.nomina_parametros%rowtype;
    v_fecha date := p_fecha::date;
    v_factor numeric;
    v_bruto_mes numeric(18,2);
    v_bruto numeric(18,2);
    v_sfs_mes numeric(18,2);
    v_afp_mes numeric(18,2);
    v_isr_mes numeric(18,2) := 0;
    v_sfs numeric(18,2);
    v_afp numeric(18,2);
    v_isr numeric(18,2);
    v_neto numeric(18,2);
    v_sfs_pat numeric(18,2);
    v_afp_pat numeric(18,2);
    v_arl numeric(18,2);
    v_arl_tasa numeric(8,6);
    v_infotep numeric(18,2);
    v_base_isr numeric(18,2);
    v_tramo jsonb;
    v_pago_id text;
    v_usuario text;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if coalesce(auth.jwt()->>'aal','aal1') <> 'aal2' then
        raise exception 'MFA_AAL2_REQUIRED';
    end if;
    v_factor := case lower(trim(p_periodo))
        when 'mensual' then 1
        when 'quincenal' then 0.5
        when 'semanal' then 12.0/52.0
        else null end;
    if v_factor is null then raise exception 'INVALID_PAYROLL_PERIOD'; end if;
    if lower(trim(p_metodo_pago)) not in ('efectivo','transferencia') then
        raise exception 'INVALID_PAYROLL_PAYMENT_METHOD';
    end if;

    select tm.tenant_id into v_tenant
    from public.tenant_memberships tm
    where tm.user_id=v_uid and tm.active
      and (
          tm.role='admin'
          or coalesce(tm.permissions->'puede_configurar','false'::jsonb)='true'::jsonb
      )
    order by tm.created_at limit 1;
    if v_tenant is null then raise exception 'PAYROLL_PERMISSION_DENIED'; end if;

    select * into v_emp from public.empleados
    where id::text=p_empleado_id and empresa_id=v_tenant and coalesce(activo,true)
    for update;
    if not found then raise exception 'EMPLOYEE_NOT_FOUND'; end if;
    v_bruto_mes := round(coalesce(v_emp.salario_mensual,v_emp.sueldo,0),2);
    if v_bruto_mes<=0 then raise exception 'EMPLOYEE_MONTHLY_SALARY_REQUIRED'; end if;
    v_arl_tasa := v_emp.arl_tasa;
    if v_arl_tasa is null or v_arl_tasa<0.01 or v_arl_tasa>0.016 then
        raise exception 'EMPLOYEE_ARL_RATE_REQUIRED: configure la tasa aprobada entre 1.00% y 1.60%';
    end if;
    select * into v_params from public.nomina_parametros where ano=extract(year from v_fecha)::int;
    if not found then raise exception 'PAYROLL_PARAMETERS_NOT_CONFIGURED_FOR_YEAR'; end if;
    if v_fecha<v_params.vigente_desde then
        raise exception 'PAYROLL_PARAMETERS_NOT_EFFECTIVE_FOR_DATE';
    end if;
    if exists (
        select 1 from public.pagos_empleados pe
        where pe.empresa_id=v_tenant
          and pe.empleado_id::text=p_empleado_id
          and pe.fecha::date=v_fecha
          and lower(coalesce(pe.periodo,''))=lower(trim(p_periodo))
    ) then
        raise exception 'DUPLICATE_PAYROLL_PAYMENT';
    end if;

    v_bruto := round(v_bruto_mes*v_factor,2);
    v_sfs_mes := round(least(v_bruto_mes,v_params.tope_sfs)*v_params.sfs_empleado,2);
    v_afp_mes := round(least(v_bruto_mes,v_params.tope_afp)*v_params.afp_empleado,2);
    v_base_isr := v_bruto_mes-v_sfs_mes-v_afp_mes;
    for v_tramo in select value from jsonb_array_elements(v_params.isr_tramos)
    loop
        if v_base_isr>(v_tramo->>'desde')::numeric then
            v_isr_mes := round(
                (v_tramo->>'fijo')::numeric+
                (v_base_isr-(v_tramo->>'desde')::numeric)*(v_tramo->>'tasa')::numeric,2
            );
            exit;
        end if;
    end loop;
    v_sfs := round(v_sfs_mes*v_factor,2);
    v_afp := round(v_afp_mes*v_factor,2);
    v_isr := round(v_isr_mes*v_factor,2);
    v_neto := round(v_bruto-v_sfs-v_afp-v_isr,2);
    v_sfs_pat := round(least(v_bruto_mes,v_params.tope_sfs)*v_params.sfs_empleador*v_factor,2);
    v_afp_pat := round(least(v_bruto_mes,v_params.tope_afp)*v_params.afp_empleador*v_factor,2);
    v_arl := round(least(v_bruto_mes,v_params.tope_arl)*v_arl_tasa*v_factor,2);
    v_infotep := round(v_bruto_mes*v_params.infotep_empleador*v_factor,2);
    select coalesce(u.nombre,u.usuario,v_uid::text) into v_usuario
    from public.usuarios u where u.user_id=v_uid limit 1;

    insert into public.pagos_empleados(
        empresa_id,empleado_id,empleado,fecha,periodo,sueldo_bruto,
        sfs_empleado,afp_empleado,isr,neto_pagar,sfs_empleador,
        afp_empleador,arl_empleador,infotep_empleador,metodo_pago,
        observacion,usuario,usuario_id,monto
    ) values (
        v_tenant,v_emp.id::text,v_emp.nombre,v_fecha,lower(trim(p_periodo)),v_bruto,
        v_sfs,v_afp,v_isr,v_neto,v_sfs_pat,v_afp_pat,v_arl,v_infotep,
        lower(trim(p_metodo_pago)),left(coalesce(p_observacion,''),1000),v_usuario,v_uid,v_neto
    ) returning id::text into v_pago_id;

    insert into public.movimientos_contables(
        empresa_id,fecha,modulo,referencia_id,cuenta_codigo,cuenta_nombre,
        tipo_cuenta,debito,credito,descripcion,usuario,usuario_id
    ) values
        (v_tenant,v_fecha,'nomina',v_pago_id,'5201','Sueldos y Salarios','gasto',v_bruto,0,'Nómina '||v_emp.nombre,v_usuario,v_uid),
        (v_tenant,v_fecha,'nomina',v_pago_id,'2105','Retenciones TSS por Pagar','pasivo',0,v_sfs+v_afp,'TSS empleado',v_usuario,v_uid),
        (v_tenant,v_fecha,'nomina',v_pago_id,'2106','ISR Retenido por Pagar','pasivo',0,v_isr,'ISR empleado',v_usuario,v_uid),
        (v_tenant,v_fecha,'nomina',v_pago_id,case when lower(trim(p_metodo_pago))='efectivo' then '1101' else '1102' end,
         case when lower(trim(p_metodo_pago))='efectivo' then 'Efectivo / Caja' else 'Banco / Depósito' end,
         'activo',0,v_neto,'Pago neto nómina',v_usuario,v_uid),
        (v_tenant,v_fecha,'nomina',v_pago_id,'5202','Cargas Sociales Empleador','gasto',v_sfs_pat+v_afp_pat+v_arl+v_infotep,0,'Aportes empleador',v_usuario,v_uid),
        (v_tenant,v_fecha,'nomina',v_pago_id,'2107','Aportes Patronales por Pagar','pasivo',0,v_sfs_pat+v_afp_pat+v_arl+v_infotep,'Aportes empleador',v_usuario,v_uid);

    insert into public.auditoria_eventos(
        empresa_id,usuario_id,usuario,accion,modulo,tabla,registro_id,detalle,metadata
    ) values (
        v_tenant,v_uid::text,v_usuario,'nomina_registrada','Nómina','pagos_empleados',v_pago_id,
        'Nómina calculada con parámetros versionados',
        jsonb_build_object('periodo',lower(trim(p_periodo)),'bruto',v_bruto,'neto',v_neto,'ano',extract(year from v_fecha)::int)
    );
    return jsonb_build_object(
        'success',true,'pago_id',v_pago_id,'bruto',v_bruto,'sfs_empleado',v_sfs,
        'afp_empleado',v_afp,'isr',v_isr,'neto',v_neto,
        'sfs_empleador',v_sfs_pat,'afp_empleador',v_afp_pat,'arl',v_arl,'infotep',v_infotep
    );
end;
$$;

revoke all on function public.api_registrar_nomina(text,text,text,text,text) from public, anon;
grant execute on function public.api_registrar_nomina(text,text,text,text,text) to authenticated;

create or replace function public.api_update_my_profile(p_nombre text)
returns jsonb
language plpgsql
security definer
set search_path = public, auth
as $$
declare
    v_uid uuid := auth.uid();
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    if length(trim(coalesce(p_nombre,'')))<2 then raise exception 'INVALID_NAME'; end if;
    update public.usuarios
    set nombre=left(trim(p_nombre),200),updated_at=now()
    where user_id=v_uid and coalesce(activo,true);
    if not found then raise exception 'PROFILE_NOT_FOUND'; end if;
    return jsonb_build_object('success',true,'nombre',left(trim(p_nombre),200));
end;
$$;

revoke all on function public.api_update_my_profile(text) from public, anon;
grant execute on function public.api_update_my_profile(text) to authenticated;

commit;
```

## 4. Usuario empresarial sin correo personal

Este bloque garantiza que el usuario visible sea único dentro de cada empresa.
Deténgase si informa usuarios duplicados.

```sql
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
```

## 5. Verificación posterior de solo lectura

```sql
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
```
