-- A&M: reparación compatible de Caja, Cobrar y cuentas abiertas.
-- Revisión RLS/IDENTITY: 2026-09-16-r2.
-- Basada en el diagnóstico real ejecutado el 5 de septiembre de 2026.
-- Conserva el historial y aborta toda la transacción si encuentra un ID legado inválido.

begin;

create extension if not exists pgcrypto;

-- Columnas que faltaban en la instalación real.
alter table public.inventario_lotes
    add column if not exists created_at timestamptz not null default now();
alter table public.ventas
    add column if not exists descuento numeric(18,2) not null default 0;
alter table public.ventas
    add column if not exists descuento_total numeric(18,2) not null default 0;
alter table public.detalle_venta
    add column if not exists descuento numeric(18,2) not null default 0;
alter table public.productos
    add column if not exists usa_inventario boolean not null default true;
alter table public.productos
    add column if not exists usar_en_inventario boolean not null default true;
alter table public.caja
    add column if not exists total_efectivo numeric(18,2) not null default 0;
alter table public.caja
    add column if not exists total_transferencia numeric(18,2) not null default 0;
alter table public.caja
    add column if not exists total_tarjeta numeric(18,2) not null default 0;
alter table public.caja
    add column if not exists total_credito numeric(18,2) not null default 0;
alter table public.caja
    add column if not exists total_ventas numeric(18,2) not null default 0;

alter table public.cierre_caja
    add column if not exists monto_inicial numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists fondo_inicial numeric(18,2) not null default 0;
alter table public.cierre_caja add column if not exists usuario text;
alter table public.cierre_caja
    add column if not exists estado text not null default 'cerrada';
alter table public.cierre_caja
    add column if not exists dia_operativo date default current_date;
alter table public.cierre_caja
    add column if not exists total_efectivo numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists total_transferencia numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists total_tarjeta numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists total_credito numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists total_ventas numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists faltante numeric(18,2) not null default 0;
alter table public.cierre_caja
    add column if not exists sobrante numeric(18,2) not null default 0;
alter table public.cierre_caja alter column fecha set default current_date;

-- Se conserva BIGINT. Si ya es IDENTITY, PostgreSQL administra su secuencia y
-- no debe cambiarse su propiedad. Solo las columnas realmente no automáticas
-- reciben un DEFAULT de compatibilidad.
do $$
declare
    v_next bigint;
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema='public' and table_name='cierre_caja'
          and column_name='id' and udt_name='int8' and column_default is null
          and coalesce(is_identity,'NO')='NO'
    ) then
        create sequence if not exists public.cierre_caja_id_seq;
        select coalesce(max(id),0)+1 into v_next from public.cierre_caja;
        perform setval('public.cierre_caja_id_seq'::regclass,greatest(v_next,1),false);
        alter table public.cierre_caja
            alter column id set default nextval('public.cierre_caja_id_seq'::regclass);
    end if;
end
$$;

-- Los cuatro campos contienen identificadores de public.caja/auth.users. Se
-- valida antes de convertir; si aparece un valor no UUID, no se cambia nada.
do $$
declare
    v_target record;
    v_bad text;
begin
    for v_target in
        select * from (values
            ('cierre_caja','caja_id'),
            ('cierre_caja','usuario_id'),
            ('movimientos_caja','caja_id'),
            ('ventas_pagos','caja_id')
        ) as x(table_name,column_name)
    loop
        if exists (
            select 1 from information_schema.columns c
            where c.table_schema='public'
              and c.table_name=v_target.table_name
              and c.column_name=v_target.column_name
              and c.udt_name<>'uuid'
        ) then
            execute format(
                'select %1$I::text from public.%2$I '
                'where nullif(trim(%1$I::text),'''') is not null '
                'and trim(%1$I::text) !~* '
                '''^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'' limit 1',
                v_target.column_name,v_target.table_name
            ) into v_bad;
            if v_bad is not null then
                raise exception 'INVALID_LEGACY_UUID %.%=%',
                    v_target.table_name,v_target.column_name,v_bad;
            end if;
        end if;
    end loop;
end
$$;

-- PostgreSQL impide cambiar el tipo de una columna usada por RLS. Las tablas
-- permanecen protegidas por la misma transacción: se retiran sus políticas,
-- se convierte el tipo y se reconstruyen antes del COMMIT.
do $$
declare
    v_policy record;
begin
    for v_policy in
        select schemaname,tablename,policyname
        from pg_policies
        where schemaname='public'
          and tablename in ('cierre_caja','movimientos_caja','ventas_pagos')
    loop
        execute format(
            'drop policy if exists %I on %I.%I',
            v_policy.policyname,v_policy.schemaname,v_policy.tablename
        );
    end loop;
end
$$;

do $$
declare
    v_target record;
begin
    for v_target in
        select * from (values
            ('cierre_caja','caja_id'),
            ('cierre_caja','usuario_id'),
            ('movimientos_caja','caja_id'),
            ('ventas_pagos','caja_id')
        ) as x(table_name,column_name)
    loop
        if exists (
            select 1 from information_schema.columns c
            where c.table_schema='public'
              and c.table_name=v_target.table_name
              and c.column_name=v_target.column_name
              and c.udt_name<>'uuid'
        ) then
            execute format(
                'alter table public.%I alter column %I type uuid '
                'using nullif(trim(%I::text),'''')::uuid',
                v_target.table_name,v_target.column_name,v_target.column_name
            );
        end if;
    end loop;
end
$$;

alter table public.cierre_caja enable row level security;
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

alter table public.movimientos_caja enable row level security;
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
              and c.usuario_id=auth.uid()
        )
    )
);

alter table public.ventas_pagos enable row level security;
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

grant select on public.cierre_caja,public.movimientos_caja,public.ventas_pagos
to authenticated;
revoke insert,update,delete on
    public.cierre_caja,public.movimientos_caja,public.ventas_pagos
from authenticated,anon;

-- Borra solamente membresías que apuntan a identidades ya inexistentes. No
-- toca perfiles, ventas, auditoría ni operaciones contables.
delete from public.tenant_memberships tm
where not exists (select 1 from auth.users au where au.id=tm.user_id);

do $$
begin
    if not exists (
        select 1
        from pg_constraint c
        join pg_attribute a
          on a.attrelid=c.conrelid and a.attnum=any(c.conkey)
        where c.conrelid='public.tenant_memberships'::regclass
          and c.contype='f'
          and c.confrelid='auth.users'::regclass
          and a.attname='user_id'
    ) then
        alter table public.tenant_memberships
            add constraint tenant_memberships_user_id_fkey
            foreign key (user_id) references auth.users(id)
            on delete cascade not valid;
    end if;
end
$$;

do $$
declare
    v_constraint text;
begin
    for v_constraint in
        select c.conname
        from pg_constraint c
        join pg_attribute a
          on a.attrelid=c.conrelid and a.attnum=any(c.conkey)
        where c.conrelid='public.tenant_memberships'::regclass
          and c.contype='f'
          and c.confrelid='auth.users'::regclass
          and a.attname='user_id'
    loop
        execute format(
            'alter table public.tenant_memberships validate constraint %I',
            v_constraint
        );
    end loop;
end
$$;

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
    v_caja_owner uuid;
    v_dia_operativo date;
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
    v_linea_bruta numeric(18,2);
    v_linea_subtotal numeric(18,2);
    v_linea_itbis numeric(18,2);
    v_linea_costo numeric(18,4);
    v_precio numeric(18,2);
    v_precio_catalogo numeric(18,2);
    v_precio_minimo numeric(18,2);
    v_costo_catalogo numeric(18,4);
    v_cantidad numeric(18,4);
    v_stock numeric(18,4);
    v_usa_inventario boolean;
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
    v_descuento_global numeric(18,2) := 0;
    v_descuento_linea numeric(18,2) := 0;
    v_descuento_asignado numeric(18,2) := 0;
    v_total_bruto numeric(18,2) := 0;
    v_item_index integer := 0;
    v_item_count integer := 0;
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

    begin
        v_dia_operativo := coalesce(
            nullif(trim(p ->> 'dia_operativo'),'')::timestamptz::date,
            current_date
        );
    exception when others then
        raise exception 'INVALID_OPERATION_DATE';
    end;

    v_caja_id := nullif(p ->> 'caja_id','')::uuid;
    if v_caja_id is null then raise exception 'OPEN_CASH_REGISTER_REQUIRED'; end if;
    select c.usuario_id into v_caja_owner
    from public.caja c
    where c.id = v_caja_id and c.empresa_id = v_tenant and lower(c.estado) = 'abierta'
    for update;
    if not found then raise exception 'OPEN_CASH_REGISTER_REQUIRED'; end if;
    if v_caja_owner is distinct from v_uid then
        raise exception 'CASH_REGISTER_NOT_OWNED';
    end if;

    begin
        v_descuento_global := round(
            coalesce(nullif(trim(p ->> 'descuento_global'),'')::numeric,0),
            2
        );
    exception when others then
        raise exception 'INVALID_GLOBAL_DISCOUNT';
    end;
    if v_descuento_global < 0 then raise exception 'INVALID_GLOBAL_DISCOUNT'; end if;

    -- Primera pasada: el servidor valida los precios y calcula el bruto real.
    -- Esto permite repartir el descuento sin confiar en totales del navegador.
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
        v_precio_catalogo := round(coalesce(
            nullif(v_producto.precio,0),
            nullif(v_producto.precio_venta,0),
            0
        )::numeric,2);
        v_precio_minimo := round(coalesce(
            nullif(v_producto.precio_minimo,0),
            nullif(v_producto.precio_descuento,0),
            v_precio_catalogo
        )::numeric,2);
        v_precio := round(coalesce((v_item ->> 'precio_unitario')::numeric,v_precio_catalogo),2);
        if v_precio <= 0 or v_precio > v_precio_catalogo then raise exception 'INVALID_ITEM_PRICE'; end if;
        if v_precio < v_precio_minimo
           and not (
               public.has_tenant_permission(v_tenant,'puede_aplicar_descuento')
               or public.has_tenant_permission(v_tenant,'puede_editar_todo')
           ) then
            raise exception 'DISCOUNT_PERMISSION_DENIED';
        end if;
        v_total_bruto := v_total_bruto + round(v_cantidad*v_precio,2);
    end loop;
    if v_descuento_global >= v_total_bruto and v_descuento_global > 0 then
        raise exception 'INVALID_GLOBAL_DISCOUNT';
    end if;
    if v_descuento_global > 0
       and not (
           public.has_tenant_permission(v_tenant,'puede_aplicar_descuento')
           or public.has_tenant_permission(v_tenant,'puede_editar_todo')
       ) then
        raise exception 'DISCOUNT_PERMISSION_DENIED';
    end if;
    v_item_count := jsonb_array_length(p -> 'items');

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
        v_usuario, v_uid, v_dia_operativo,
        v_caja_id, 'POS', case when v_estado='abierta' then 'abierta' else 'pendiente' end,
        left(coalesce(p ->> 'observacion',''),2000)
    ) returning id into v_venta_id;

    for v_item in select value from jsonb_array_elements(p -> 'items')
    loop
        v_item_index := v_item_index + 1;
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

        v_usa_inventario := coalesce(
            v_producto.usa_inventario,
            v_producto.usar_en_inventario,
            true
        );
        v_stock := coalesce(
            nullif(v_producto.cantidad,0),
            nullif(v_producto.stock,0),
            nullif(v_producto.existencia,0),
            0
        );
        if v_usa_inventario and v_stock < v_cantidad then
            raise exception 'INSUFFICIENT_STOCK: % disponible, % solicitado', v_stock, v_cantidad;
        end if;

        v_precio_catalogo := round(coalesce(
            nullif(v_producto.precio,0),
            nullif(v_producto.precio_venta,0),
            0
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
        v_linea_bruta := round(v_cantidad * v_precio,2);
        if v_descuento_global > 0 then
            v_descuento_linea := case
                when v_item_index = v_item_count
                    then v_descuento_global-v_descuento_asignado
                else round(v_descuento_global*v_linea_bruta/v_total_bruto,2)
            end;
        else
            v_descuento_linea := 0;
        end if;
        v_descuento_asignado := v_descuento_asignado+v_descuento_linea;
        v_linea_total := round(v_linea_bruta-v_descuento_linea,2);
        if v_tasa > 0 then
            v_linea_subtotal := round(v_linea_total / (1 + v_tasa / 100),2);
            v_linea_itbis := v_linea_total - v_linea_subtotal;
            v_subtotal_gravado := v_subtotal_gravado + v_linea_subtotal;
        else
            v_linea_subtotal := v_linea_total;
            v_linea_itbis := 0;
            v_subtotal_exento := v_subtotal_exento + v_linea_subtotal;
        end if;

        v_costo_catalogo := coalesce(
            nullif(v_producto.costo_unitario,0),
            nullif(v_producto.costo,0),
            0
        );
        v_linea_costo := 0;
        v_restante := v_cantidad;

        if v_usa_inventario then
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
        else
            v_linea_costo := v_cantidad*v_costo_catalogo;
        end if;

        insert into public.detalle_venta(
            empresa_id, venta_id, producto_id, codigo, producto, cantidad,
            precio_unitario, precio, itbis_gravado, itbis_tasa, itbis_monto,
            subtotal, total_linea, descuento, costo_unitario, costo, costo_total,
            ganancia_linea, usuario, fecha, anulado
        ) values (
            v_tenant, v_venta_id, v_producto.id,
            coalesce(v_producto.codigo, v_producto.codigo_barra, v_producto.id::text),
            v_producto.nombre, v_cantidad, v_precio, v_precio, v_gravado, v_tasa,
            v_linea_itbis, v_linea_subtotal, v_linea_total, v_descuento_linea,
            case when v_cantidad > 0 then round(v_linea_costo / v_cantidad,4) else 0 end,
            case when v_cantidad > 0 then round(v_linea_costo / v_cantidad,4) else 0 end,
            round(v_linea_costo,2), round(v_linea_total - v_linea_costo,2),
            v_usuario, now(), false
        ) returning id into v_detalle_id;

        update public.inventario_consumos
        set detalle_id = v_detalle_id
        where venta_id = v_venta_id and producto_id = v_producto.id and detalle_id is null;

        if v_usa_inventario then
            update public.productos
            set stock = v_stock - v_cantidad,
                existencia = v_stock - v_cantidad,
                cantidad = v_stock - v_cantidad,
                updated_at = now()
            where id = v_producto.id;
        end if;

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
                v_caja_id, v_dia_operativo
            );
            if v_metodo <> 'credito' then
                insert into public.movimientos_caja(
                    empresa_id, fecha, dia_operativo, caja_id, tipo_movimiento,
                    origen, referencia_id, metodo_pago, monto, descripcion,
                    usuario, usuario_id, anulado
                ) values (
                    v_tenant, now(), v_dia_operativo,
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
        descuento = v_descuento_global,
        descuento_total = v_descuento_global,
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
        'total',round(v_total,2), 'descuento',v_descuento_global,
        'costo_total',round(v_costo_total,2)
    );
end;
$$;

revoke all on function public.api_registrar_venta(jsonb) from public, anon;
grant execute on function public.api_registrar_venta(jsonb) to authenticated;

-- El cobro de créditos usa la caja abierta del propio usuario y conserva DATE.
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
    v_caja_owner uuid;
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

    select c.empresa_id,c.usuario_id into v_tenant,v_caja_owner
    from public.caja c
    where c.id=v_caja and lower(c.estado)='abierta'
    for update;
    if v_tenant is null or not public.has_tenant_permission(v_tenant,'ver_credito') then
        raise exception 'CREDIT_PAYMENT_PERMISSION_DENIED';
    end if;
    if v_caja_owner is distinct from v_uid then
        raise exception 'CASH_REGISTER_NOT_OWNED';
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
        v_tenant,now(),current_date,v_caja,'entrada','abono_credito',
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
    v_new_caja_id uuid;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    select * into v_old
    from public.ventas
    where id=p_venta_id::uuid
    for update;
    if not found then raise exception 'SALE_NOT_FOUND'; end if;
    if not (
        public.has_tenant_permission(v_old.empresa_id,'puede_vender')
        or public.has_tenant_permission(v_old.empresa_id,'puede_editar_ventas')
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

    begin
        v_new_caja_id := nullif(trim(p_payload ->> 'caja_id'),'')::uuid;
    exception when others then
        raise exception 'OPEN_CASH_REGISTER_REQUIRED';
    end;
    if v_new_caja_id is null then raise exception 'OPEN_CASH_REGISTER_REQUIRED'; end if;
    perform 1
    from public.caja c
    where c.id=v_new_caja_id
      and c.empresa_id=v_old.empresa_id
      and c.usuario_id=v_uid
      and lower(coalesce(c.estado,''))='abierta'
    for update;
    if not found then raise exception 'OPEN_CASH_REGISTER_REQUIRED'; end if;

    v_payload := coalesce(p_payload,'{}'::jsonb) || jsonb_build_object(
        'empresa_id',v_old.empresa_id,
        'caja_id',v_new_caja_id,
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
    v_total_efectivo numeric(18,2) := 0;
    v_total_transferencia numeric(18,2) := 0;
    v_total_tarjeta numeric(18,2) := 0;
    v_total_credito numeric(18,2) := 0;
    v_total_ventas numeric(18,2) := 0;
begin
    if v_uid is null then raise exception 'AUTH_REQUIRED'; end if;
    select * into v_caja from public.caja where id=p_caja_id::uuid for update;
    if not found or lower(v_caja.estado)<>'abierta' then raise exception 'CASH_REGISTER_NOT_OPEN'; end if;
    if not public.has_tenant_permission(v_caja.empresa_id,'puede_cerrar_caja') then
        raise exception 'CLOSE_CASH_PERMISSION_DENIED';
    end if;
    if v_caja.usuario_id is distinct from v_uid
       and not (
           public.has_tenant_permission(v_caja.empresa_id,'puede_editar_todo')
           or exists (
               select 1 from public.tenant_memberships tm
               where tm.user_id=v_uid and tm.tenant_id=v_caja.empresa_id
                 and tm.active and tm.role in ('admin','gerente')
           )
       ) then
        raise exception 'CLOSE_OTHER_CASH_PERMISSION_DENIED';
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

    select
        coalesce(sum(vp.monto) filter (where lower(vp.metodo)='efectivo'),0),
        coalesce(sum(vp.monto) filter (where lower(vp.metodo)='transferencia'),0),
        coalesce(sum(vp.monto) filter (where lower(vp.metodo)='tarjeta'),0),
        coalesce(sum(vp.monto) filter (where lower(vp.metodo)='credito'),0),
        coalesce(sum(vp.monto),0)
    into v_total_efectivo,v_total_transferencia,v_total_tarjeta,v_total_credito,v_total_ventas
    from public.ventas_pagos vp
    where vp.empresa_id=v_caja.empresa_id
      and vp.caja_id=v_caja.id
      and not coalesce(vp.anulado,false);

    update public.caja set
        estado='cerrada',fecha_cierre=now(),efectivo_contado=round(p_efectivo_contado,2),
        efectivo_esperado=v_esperado,diferencia=v_diferencia,
        faltante=greatest(-v_diferencia,0),sobrante=greatest(v_diferencia,0),
        total_efectivo=round(v_total_efectivo,2),
        total_transferencia=round(v_total_transferencia,2),
        total_tarjeta=round(v_total_tarjeta,2),
        total_credito=round(v_total_credito,2),
        total_ventas=round(v_total_ventas,2),
        observacion=left(coalesce(p_observacion,''),1000)
    where id=v_caja.id;
    insert into public.cierre_caja(
        empresa_id,caja_id,usuario_id,usuario,fecha,dia_operativo,estado,
        monto_inicial,fondo_inicial,efectivo_esperado,efectivo_contado,
        diferencia,faltante,sobrante,total_efectivo,total_transferencia,
        total_tarjeta,total_credito,total_ventas,observacion
    ) values (
        v_caja.empresa_id,v_caja.id,v_uid,v_usuario,current_date,
        coalesce(v_caja.dia_operativo,current_date),'cerrada',v_inicial,v_inicial,
        v_esperado,round(p_efectivo_contado,2),v_diferencia,
        greatest(-v_diferencia,0),greatest(v_diferencia,0),
        round(v_total_efectivo,2),round(v_total_transferencia,2),
        round(v_total_tarjeta,2),round(v_total_credito,2),round(v_total_ventas,2),
        left(coalesce(p_observacion,''),1000)
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

-- Verificación final: si una condición crítica no quedó corregida, revierte todo.
do $$
begin
    if not exists (select 1 from information_schema.columns where table_schema='public' and table_name='inventario_lotes' and column_name='created_at') then
        raise exception 'REPAIR_INVENTORY_TIMESTAMP_FAILED';
    end if;
    if exists (select 1 from information_schema.columns where table_schema='public' and table_name in ('cierre_caja','movimientos_caja','ventas_pagos') and column_name in ('caja_id','usuario_id') and ((table_name='cierre_caja' and column_name in ('caja_id','usuario_id')) or (table_name in ('movimientos_caja','ventas_pagos') and column_name='caja_id')) and udt_name<>'uuid') then
        raise exception 'REPAIR_CASH_UUID_FAILED';
    end if;
end
$$;

commit;
