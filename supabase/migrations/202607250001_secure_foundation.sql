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
