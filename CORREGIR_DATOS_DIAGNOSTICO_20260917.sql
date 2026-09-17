-- A&M - Correccion puntual de los dos datos detectados por el diagnostico r4
-- Fecha: 2026-09-17
--
-- Alcance exacto:
--   1. Registra una licencia interna de cortesia para amcontable solamente si
--      no existe ya una licencia vigente.
--   2. Lleva a cero el inventario negativo del producto identificado de demo01
--      solamente si nunca ha participado en ventas ni consumos de inventario.
--   3. Corrige el texto mal codificado PIÃ‘A -> PIÑA.
--
-- No modifica Bibe Ron, ventas, cajas, cobros ni contabilidad.

begin;
set local statement_timeout = '60s';

-- Evita que dos ejecuciones simultaneas calculen el mismo ID de licencia.
select pg_advisory_xact_lock(hashtextextended('ais:correccion-diagnostico-20260917', 0));

do $$
declare
    v_next_license_id bigint;
    v_product record;
begin
    if not exists (
        select 1
        from public.empresas e
        where e.tenant_id='amcontable' and e.activo
    ) then
        raise exception 'AMCONTABLE_ACTIVE_COMPANY_NOT_FOUND';
    end if;

    if not exists (
        select 1
        from public.suscripciones_empresas s
        where s.empresa_id='amcontable'
          and s.fecha_inicio<=current_date
          and current_date<=s.fecha_vencimiento+coalesce(s.dias_gracia,0)
    ) then
        lock table public.suscripciones_empresas in share row exclusive mode;

        select coalesce(max(s.id),0)+1
        into v_next_license_id
        from public.suscripciones_empresas s;

        insert into public.suscripciones_empresas(
            id,empresa_id,fecha_inicio,fecha_vencimiento,monto_pagado,
            periodo,metodo_pago,dias_gracia,observacion
        ) values (
            v_next_license_id,
            'amcontable',
            current_date,
            date '2099-12-31',
            0,
            'cortesia',
            'cortesia',
            0,
            'Licencia interna A&M; no representa una venta ni un ingreso.'
        );

        insert into public.auditoria_eventos(
            empresa_id,usuario_id,usuario,accion,modulo,tabla,
            registro_id,detalle,metadata
        ) values (
            'amcontable',auth.uid()::text,'SQL Editor',
            'licencia_interna_registrada','Licencias','suscripciones_empresas',
            v_next_license_id::text,
            'Correccion controlada posterior al diagnostico integral',
            jsonb_build_object(
                'fecha_inicio',current_date,
                'fecha_vencimiento','2099-12-31',
                'monto_pagado',0,
                'motivo','licencia interna sin ingreso'
            )
        );
    end if;

    select
        p.id,p.empresa_id,p.nombre,p.stock,p.existencia,p.cantidad
    into v_product
    from public.productos p
    where p.id='22e84ac0-004e-46ec-8776-77b5f983e0bf'::uuid
      and p.empresa_id='demo01'
    for update;

    if not found then
        raise exception 'DEMO_PRODUCT_NOT_FOUND_OR_TENANT_MISMATCH';
    end if;

    if least(
        coalesce(v_product.stock,0),
        coalesce(v_product.existencia,0),
        coalesce(v_product.cantidad,0)
    ) < 0 or v_product.nombre like '%PIÃ‘A%' then
        if exists (
            select 1
            from public.detalle_venta d
            where d.producto_id=v_product.id
        ) or exists (
            select 1
            from public.inventario_consumos ic
            where ic.producto_id=v_product.id
        ) then
            raise exception 'DEMO_PRODUCT_HAS_OPERATIONAL_HISTORY';
        end if;

        update public.productos p
        set nombre=replace(p.nombre,'PIÃ‘A','PIÑA'),
            stock=greatest(coalesce(p.stock,0),0),
            existencia=greatest(coalesce(p.existencia,0),0),
            cantidad=greatest(coalesce(p.cantidad,0),0),
            updated_at=now()
        where p.id=v_product.id
          and p.empresa_id='demo01';

        insert into public.auditoria_eventos(
            empresa_id,usuario_id,usuario,accion,modulo,tabla,
            registro_id,detalle,metadata
        ) values (
            'demo01',auth.uid()::text,'SQL Editor',
            'inventario_negativo_corregido','Inventario','productos',
            v_product.id::text,
            'Producto de demostracion sin historial llevado a existencia cero',
            jsonb_build_object(
                'nombre_anterior',v_product.nombre,
                'stock_anterior',v_product.stock,
                'existencia_anterior',v_product.existencia,
                'cantidad_anterior',v_product.cantidad,
                'stock_nuevo',0,
                'existencia_nueva',0,
                'cantidad_nueva',0
            )
        );
    end if;
end
$$;

commit;

-- Resultado esperado: ambas filas deben decir OK.
select
    'licencia_interna_amcontable' as prueba,
    case when exists (
        select 1
        from public.suscripciones_empresas s
        where s.empresa_id='amcontable'
          and s.fecha_inicio<=current_date
          and current_date<=s.fecha_vencimiento+coalesce(s.dias_gracia,0)
    ) then 'OK' else 'ERROR' end as estado,
    'Debe existir una licencia vigente con monto RD$0.00' as detalle
union all
select
    'inventario_producto_demo01',
    case when exists (
        select 1
        from public.productos p
        where p.id='22e84ac0-004e-46ec-8776-77b5f983e0bf'::uuid
          and p.empresa_id='demo01'
          and least(coalesce(p.stock,0),coalesce(p.existencia,0),coalesce(p.cantidad,0))>=0
          and p.nombre not like '%PIÃ‘A%'
    ) then 'OK' else 'ERROR' end,
    'Debe quedar en cero y con el nombre PIÑA correctamente escrito';
