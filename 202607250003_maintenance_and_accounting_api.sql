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
