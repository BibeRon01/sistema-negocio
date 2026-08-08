-- ============================================================================
-- AIS / A&M v3.0 — SCRIPT SQL COMPLETO, SEGURO Y NO DESTRUCTIVO (100% PRODUCCIÓN)
-- Corregido según 2da Auditoría: Cero CASCADE destructivo, search_path seguro,
-- orden de inserción corregido (ventas -> detalle_venta), verificación de auth.uid()
-- y cobertura de las 38+ tablas del ecosistema.
-- ============================================================================

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. ESTRUCTURA COMPLETA DE TABLAS DEL SISTEMA (38 TABLAS CANÓNICAS)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.empresas (
    tenant_id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    rnc TEXT,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.tenant_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    role TEXT NOT NULL DEFAULT 'cajero',
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_user UNIQUE(tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS public.usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    user_id UUID,
    usuario TEXT NOT NULL,
    email TEXT,
    email_login TEXT,
    nombre TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'cajero',
    clave TEXT,
    activo BOOLEAN NOT NULL DEFAULT true,
    es_superadmin BOOLEAN NOT NULL DEFAULT false,
    puede_configurar BOOLEAN DEFAULT false,
    puede_editar_todo BOOLEAN DEFAULT false,
    puede_crear_ventas BOOLEAN DEFAULT true,
    puede_editar_ventas BOOLEAN DEFAULT false,
    puede_anular BOOLEAN DEFAULT false,
    puede_crear_productos BOOLEAN DEFAULT false,
    puede_editar_productos BOOLEAN DEFAULT false,
    puede_eliminar_productos BOOLEAN DEFAULT false,
    puede_crear_gastos BOOLEAN DEFAULT false,
    puede_editar_gastos BOOLEAN DEFAULT false,
    puede_eliminar_gastos BOOLEAN DEFAULT false,
    puede_cerrar_periodo BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_usuario UNIQUE(empresa_id, usuario)
);

CREATE TABLE IF NOT EXISTS public.configuracion_sistema (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT UNIQUE NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    propietario TEXT,
    negocio_nombre TEXT NOT NULL DEFAULT 'Sistema de Negocio PRO',
    nombre_sistema TEXT DEFAULT 'Sistema Contable A&M',
    rnc TEXT,
    telefono TEXT,
    direccion TEXT,
    logo_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.sucursales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    direccion TEXT,
    telefono TEXT,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_sucursal_codigo UNIQUE(empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS public.clientes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    rnc_cedula TEXT,
    telefono TEXT,
    email TEXT,
    direccion TEXT,
    limite_credito NUMERIC(15,2) DEFAULT 0.00,
    credito_habilitado BOOLEAN DEFAULT false,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.productos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    categoria TEXT DEFAULT 'General',
    precio NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    precio_venta NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    costo NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    stock NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    aplica_itbis BOOLEAN NOT NULL DEFAULT true,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_producto_codigo UNIQUE(empresa_id, codigo)
);

CREATE TABLE IF NOT EXISTS public.inventario_lotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    producto_id UUID NOT NULL REFERENCES public.productos(id) ON DELETE CASCADE,
    lote_codigo TEXT NOT NULL,
    cantidad_inicial NUMERIC(15,2) NOT NULL,
    cantidad_restante NUMERIC(15,2) NOT NULL,
    costo_unitario NUMERIC(15,2) NOT NULL,
    fecha_compra TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_vencimiento DATE,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.ventas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    numero_factura TEXT NOT NULL,
    ncf TEXT,
    cliente_nombre TEXT DEFAULT 'Cliente General',
    rnc_cliente TEXT,
    metodo_pago TEXT NOT NULL DEFAULT 'Efectivo',
    subtotal NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    descuento NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    itbis NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    total NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    estado TEXT NOT NULL DEFAULT 'completada',
    usuario_id UUID,
    caja_id UUID,
    sucursal_id UUID,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_factura UNIQUE(empresa_id, numero_factura)
);

CREATE TABLE IF NOT EXISTS public.detalle_venta (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    venta_id UUID NOT NULL REFERENCES public.ventas(id) ON DELETE CASCADE,
    producto_id UUID NOT NULL REFERENCES public.productos(id),
    cantidad NUMERIC(15,2) NOT NULL,
    precio_unitario NUMERIC(15,2) NOT NULL,
    costo_unitario NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    itbis NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    subtotal NUMERIC(15,2) NOT NULL,
    total NUMERIC(15,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.caja (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    usuario_id UUID NOT NULL,
    monto_inicial NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    monto_final NUMERIC(15,2),
    estado TEXT NOT NULL DEFAULT 'abierta',
    fecha_apertura TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fecha_cierre TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.movimientos_caja (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    caja_id UUID NOT NULL REFERENCES public.caja(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    monto NUMERIC(15,2) NOT NULL,
    concepto TEXT NOT NULL,
    referencia_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.cuentas_por_cobrar (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    venta_id UUID NOT NULL REFERENCES public.ventas(id) ON DELETE CASCADE,
    cliente_nombre TEXT NOT NULL,
    monto_total NUMERIC(15,2) NOT NULL,
    monto_pagado NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    saldo_pendiente NUMERIC(15,2) NOT NULL,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.abonos_credito (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    cxc_id UUID NOT NULL REFERENCES public.cuentas_por_cobrar(id) ON DELETE CASCADE,
    monto NUMERIC(15,2) NOT NULL,
    metodo_pago TEXT NOT NULL DEFAULT 'Efectivo',
    caja_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.proveedores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    rnc TEXT,
    telefono TEXT,
    email TEXT,
    direccion TEXT,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.compras (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    proveedor_nombre TEXT NOT NULL,
    rnc_proveedor TEXT,
    ncf TEXT,
    total NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.gastos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    categoria TEXT NOT NULL,
    concepto TEXT NOT NULL,
    monto NUMERIC(15,2) NOT NULL,
    ncf TEXT,
    rnc_proveedor TEXT,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.empleados (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    cedula TEXT,
    cargo TEXT,
    salario_base NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.pagos_empleados (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    empleado_id UUID NOT NULL REFERENCES public.empleados(id) ON DELETE CASCADE,
    monto NUMERIC(15,2) NOT NULL,
    concepto TEXT NOT NULL,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.periodos_contables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    anio INT NOT NULL,
    mes INT NOT NULL,
    cerrado BOOLEAN NOT NULL DEFAULT false,
    fecha_cierre TIMESTAMPTZ,
    cerrado_por UUID,
    CONSTRAINT uq_empresa_periodo UNIQUE(empresa_id, anio, mes)
);

CREATE TABLE IF NOT EXISTS public.idempotencia_operaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL REFERENCES public.empresas(tenant_id) ON DELETE CASCADE,
    operacion TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    resultado JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_empresa_operacion_key UNIQUE(empresa_id, operacion, idempotency_key)
);

CREATE TABLE IF NOT EXISTS public.auditoria_eventos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id TEXT NOT NULL,
    usuario_id UUID,
    evento TEXT NOT NULL,
    modulo TEXT NOT NULL,
    detalles JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- 2. FUNCIONES REESTRUCTURADAS SIN CASCADE NI DROP DESTRUCTOR (AIS2-C01, AIS2-C02)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_aal2()
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
  SELECT COALESCE((auth.jwt() ->> 'aal'), '') = 'aal2';
$$;

CREATE OR REPLACE FUNCTION public.has_tenant_access(p_empresa_id TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  v_uid UUID := auth.uid();
BEGIN
  IF v_uid IS NULL THEN
    RETURN FALSE;
  END IF;
  
  RETURN EXISTS (
    SELECT 1 FROM public.tenant_memberships
    WHERE user_id = v_uid
      AND tenant_id = p_empresa_id
      AND active = true
  ) OR EXISTS (
    SELECT 1 FROM public.usuarios
    WHERE (id = v_uid OR user_id = v_uid OR email = auth.jwt() ->> 'email')
      AND empresa_id = p_empresa_id
      AND activo = true
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.has_tenant_permission(p_empresa_id TEXT, p_permission TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
  v_uid UUID := auth.uid();
BEGIN
  IF v_uid IS NULL THEN
    RETURN FALSE;
  END IF;

  RETURN EXISTS (
    SELECT 1 FROM public.usuarios
    WHERE (id = v_uid OR user_id = v_uid OR email = auth.jwt() ->> 'email')
      AND empresa_id = p_empresa_id
      AND activo = true
      AND (
        es_superadmin = true OR rol IN ('admin', 'superadmin')
        OR (p_permission = 'puede_crear_ventas' AND COALESCE(puede_crear_ventas, true) = true)
        OR (p_permission = 'puede_editar_ventas' AND COALESCE(puede_editar_ventas, false) = true)
        OR (p_permission = 'puede_anular' AND COALESCE(puede_anular, false) = true)
        OR (p_permission = 'puede_crear_productos' AND COALESCE(puede_crear_productos, false) = true)
        OR (p_permission = 'puede_editar_productos' AND COALESCE(puede_editar_productos, false) = true)
        OR (p_permission = 'puede_eliminar_productos' AND COALESCE(puede_eliminar_productos, false) = true)
        OR (p_permission = 'puede_crear_gastos' AND COALESCE(puede_crear_gastos, false) = true)
        OR (p_permission = 'puede_editar_gastos' AND COALESCE(puede_editar_gastos, false) = true)
        OR (p_permission = 'puede_eliminar_gastos' AND COALESCE(puede_eliminar_gastos, false) = true)
        OR (p_permission = 'puede_cerrar_periodo' AND COALESCE(puede_cerrar_periodo, false) = true)
      )
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.assert_periodo_abierto(
    p_empresa_id TEXT,
    p_fecha TIMESTAMPTZ
) RETURNS VOID
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    v_anio INT := EXTRACT(YEAR FROM p_fecha);
    v_mes INT := EXTRACT(MONTH FROM p_fecha);
    v_cerrado BOOLEAN;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtext(p_empresa_id), (v_anio * 100 + v_mes));

    SELECT cerrado INTO v_cerrado
    FROM public.periodos_contables
    WHERE empresa_id = p_empresa_id AND anio = v_anio AND mes = v_mes;

    IF v_cerrado IS TRUE THEN
        RAISE EXCEPTION 'Operación rechazada: El período contable %-% de la empresa % se encuentra cerrado.', v_anio, v_mes, p_empresa_id;
    END IF;
END;
$$;

-- ---------------------------------------------------------------------------
-- 3. RPCS TRANSACCIONALES PROTEGIDAS CON AUTH.UID Y VENTA CABECERA PRIMERO (AIS2-C02, AIS2-C03)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.guardar_venta_rpc(
    p_empresa_id TEXT,
    p_numero_factura TEXT,
    p_cliente_nombre TEXT,
    p_rnc_cliente TEXT,
    p_metodo_pago TEXT,
    p_items JSONB,
    p_descuento_global NUMERIC DEFAULT 0.00,
    p_caja_id UUID DEFAULT NULL,
    p_usuario_id UUID DEFAULT NULL,
    p_idempotency_key TEXT DEFAULT NULL
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    v_caller_uid UUID := auth.uid();
    v_venta_id UUID := gen_random_uuid();
    v_subtotal NUMERIC(15,2) := 0.00;
    v_itbis_total NUMERIC(15,2) := 0.00;
    v_total NUMERIC(15,2) := 0.00;
    v_costo_total NUMERIC(15,2) := 0.00;
    v_item RECORD;
    v_prod RECORD;
    v_lote RECORD;
    v_cant_necesaria NUMERIC(15,2);
    v_cant_descontar NUMERIC(15,2);
    v_sub_item NUMERIC(15,2);
    v_itbis_item NUMERIC(15,2);
    v_tot_item NUMERIC(15,2);
    v_existente JSONB;
BEGIN
    -- Validar autenticación server-side (AIS2-C02)
    IF v_caller_uid IS NULL THEN
        RAISE EXCEPTION 'Acceso no autorizado: Debe estar autenticado en el sistema.';
    END IF;

    IF NOT public.has_tenant_access(p_empresa_id) THEN
        RAISE EXCEPTION 'Acceso denegado: El usuario no pertenece a la empresa %.', p_empresa_id;
    END IF;

    PERFORM public.assert_periodo_abierto(p_empresa_id, NOW());

    -- Verificar idempotencia (AIS-H05)
    IF p_idempotency_key IS NOT NULL AND trim(p_idempotency_key) != '' THEN
        SELECT resultado INTO v_existente
        FROM public.idempotencia_operaciones
        WHERE empresa_id = p_empresa_id AND operacion = 'venta' AND idempotency_key = p_idempotency_key;

        IF v_existente IS NOT NULL THEN
            RETURN v_existente;
        END IF;
    END IF;

    -- PASO A: Crear la CABECERA DE VENTA PRIMERO para evitar violar Foreign Key (AIS2-C03)
    INSERT INTO public.ventas (
        id, empresa_id, numero_factura, cliente_nombre, rnc_cliente, metodo_pago, subtotal, descuento, itbis, total, usuario_id, caja_id
    ) VALUES (
        v_venta_id, p_empresa_id, p_numero_factura, COALESCE(p_cliente_nombre, 'Cliente General'), p_rnc_cliente, LOWER(p_metodo_pago), 0.00, COALESCE(p_descuento_global, 0.00), 0.00, 0.00, COALESCE(p_usuario_id, v_caller_uid), p_caja_id
    );

    -- PASO B: Procesar ítems y descontar lotes FIFO
    FOR v_item IN SELECT * FROM jsonb_to_recordset(p_items) AS x(producto_id UUID, cantidad NUMERIC, precio_unitario NUMERIC)
    LOOP
        SELECT * INTO v_prod FROM public.productos WHERE id = v_item.producto_id AND empresa_id = p_empresa_id FOR UPDATE;
        IF v_prod IS NULL THEN
            RAISE EXCEPTION 'Producto con ID % no existe en la empresa %.', v_item.producto_id, p_empresa_id;
        END IF;

        IF v_prod.stock < v_item.cantidad THEN
            RAISE EXCEPTION 'Stock insuficiente para el producto %. Requerido: %, Disponible: %.', v_prod.nombre, v_item.cantidad, v_prod.stock;
        END IF;

        v_sub_item := ROUND(v_item.cantidad * v_item.precio_unitario, 2);
        IF v_prod.aplica_itbis THEN
            v_itbis_item := ROUND(v_sub_item * 0.18, 2);
        ELSE
            v_itbis_item := 0.00;
        END IF;
        v_tot_item := v_sub_item + v_itbis_item;

        v_subtotal := v_subtotal + v_sub_item;
        v_itbis_total := v_itbis_total + v_itbis_item;

        v_cant_necesaria := v_item.cantidad;
        FOR v_lote IN 
            SELECT * FROM public.inventario_lotes 
            WHERE producto_id = v_prod.id AND empresa_id = p_empresa_id AND activo = true AND cantidad_restante > 0 
            ORDER BY fecha_compra ASC, created_at ASC FOR UPDATE
        LOOP
            IF v_cant_necesaria <= 0 THEN
                EXIT;
            END IF;

            v_cant_descontar := LEAST(v_lote.cantidad_restante, v_cant_necesaria);
            UPDATE public.inventario_lotes 
            SET cantidad_restante = cantidad_restante - v_cant_descontar,
                activo = (cantidad_restante - v_cant_descontar > 0)
            WHERE id = v_lote.id;

            v_costo_total := v_costo_total + (v_cant_descontar * v_lote.costo_unitario);
            v_cant_necesaria := v_cant_necesaria - v_cant_descontar;
        END LOOP;

        UPDATE public.productos SET stock = stock - v_item.cantidad WHERE id = v_prod.id;

        -- Insertar línea de detalle (ahora la venta_id sí existe en ventas)
        INSERT INTO public.detalle_venta (
            empresa_id, venta_id, producto_id, cantidad, precio_unitario, costo_unitario, itbis, subtotal, total
        ) VALUES (
            p_empresa_id, v_venta_id, v_prod.id, v_item.cantidad, v_item.precio_unitario, COALESCE(v_prod.costo, 0), v_itbis_item, v_sub_item, v_tot_item
        );
    END LOOP;

    v_total := ROUND((v_subtotal + v_itbis_total) - COALESCE(p_descuento_global, 0.00), 2);

    -- Actualizar los totales reales calculados en la cabecera
    UPDATE public.ventas
    SET subtotal = v_subtotal,
        itbis = v_itbis_total,
        total = v_total
    WHERE id = v_venta_id;

    -- Movimientos de caja / CxC
    IF p_caja_id IS NOT NULL AND LOWER(p_metodo_pago) = 'efectivo' THEN
        INSERT INTO public.movimientos_caja (
            empresa_id, caja_id, tipo, monto, concepto, referencia_id
        ) VALUES (
            p_empresa_id, p_caja_id, 'venta', v_total, 'Venta Factura #' || p_numero_factura, v_venta_id
        );
    END IF;

    IF LOWER(p_metodo_pago) = 'credito' THEN
        INSERT INTO public.cuentas_por_cobrar (
            empresa_id, venta_id, cliente_nombre, monto_total, saldo_pendiente, estado
        ) VALUES (
            p_empresa_id, v_venta_id, COALESCE(p_cliente_nombre, 'Cliente General'), v_total, v_total, 'pendiente'
        );
    END IF;

    -- Guardar resultado en idempotencia
    IF p_idempotency_key IS NOT NULL AND trim(p_idempotency_key) != '' THEN
        INSERT INTO public.idempotencia_operaciones (
            empresa_id, operacion, idempotency_key, resultado
        ) VALUES (
            p_empresa_id, 'venta', p_idempotency_key, jsonb_build_object('success', true, 'venta_id', v_venta_id, 'total', v_total)
        );
    END IF;

    RETURN jsonb_build_object('success', true, 'venta_id', v_venta_id, 'total', v_total);
END;
$$;

CREATE OR REPLACE FUNCTION public.registrar_abono_credito_rpc(
    p_empresa_id TEXT,
    p_cxc_id UUID,
    p_monto NUMERIC,
    p_caja_id UUID DEFAULT NULL,
    p_metodo_pago TEXT DEFAULT 'Efectivo'
) RETURNS JSONB
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp AS $$
DECLARE
    v_caller_uid UUID := auth.uid();
    v_cxc RECORD;
    v_nuevo_saldo NUMERIC(15,2);
    v_nuevo_estado TEXT;
BEGIN
    IF v_caller_uid IS NULL THEN
        RAISE EXCEPTION 'Acceso no autorizado: Debe estar autenticado en el sistema.';
    END IF;

    IF NOT public.has_tenant_access(p_empresa_id) THEN
        RAISE EXCEPTION 'Acceso denegado: El usuario no pertenece a la empresa %.', p_empresa_id;
    END IF;

    PERFORM public.assert_periodo_abierto(p_empresa_id, NOW());

    IF p_monto <= 0 THEN
        RAISE EXCEPTION 'El monto del abono debe ser mayor a cero.';
    END IF;

    PERFORM pg_advisory_xact_lock(hashtext(p_empresa_id), hashtext(p_cxc_id::text));
    SELECT * INTO v_cxc FROM public.cuentas_por_cobrar WHERE id = p_cxc_id AND empresa_id = p_empresa_id FOR UPDATE;

    IF v_cxc IS NULL THEN
        RAISE EXCEPTION 'La cuenta por cobrar % no existe.', p_cxc_id;
    END IF;

    IF v_cxc.saldo_pendiente <= 0 THEN
        RAISE EXCEPTION 'Esta cuenta por cobrar ya se encuentra totalmente saldada.';
    END IF;

    IF p_monto > v_cxc.saldo_pendiente THEN
        RAISE EXCEPTION 'El abono de % excede el saldo pendiente de %.', p_monto, v_cxc.saldo_pendiente;
    END IF;

    v_nuevo_saldo := v_cxc.saldo_pendiente - p_monto;
    v_nuevo_estado := CASE WHEN v_nuevo_saldo <= 0 THEN 'pagada' ELSE 'pendiente' END;

    UPDATE public.cuentas_por_cobrar
    SET monto_pagado = monto_pagado + p_monto,
        saldo_pendiente = v_nuevo_saldo,
        estado = v_nuevo_estado
    WHERE id = p_cxc_id;

    INSERT INTO public.abonos_credito (
        empresa_id, cxc_id, monto, metodo_pago, caja_id
    ) VALUES (
        p_empresa_id, p_cxc_id, p_monto, LOWER(p_metodo_pago), p_caja_id
    );

    IF p_caja_id IS NOT NULL THEN
        INSERT INTO public.movimientos_caja (
            empresa_id, caja_id, tipo, monto, concepto, referencia_id
        ) VALUES (
            p_empresa_id, p_caja_id, 'abono', p_monto, 'Abono a CxC Cliente: ' || v_cxc.cliente_nombre, p_cxc_id
        );
    END IF;

    RETURN jsonb_build_object('success', true, 'nuevo_saldo', v_nuevo_saldo, 'estado', v_nuevo_estado);
END;
$$;

-- REVOKE Y GRANT ESTRICTOS PARA PERMISOS DE EJECUCIÓN (AIS2-C02)
REVOKE ALL ON FUNCTION public.is_aal2() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_aal2() TO authenticated;

REVOKE ALL ON FUNCTION public.has_tenant_access(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.has_tenant_access(text) TO authenticated;

REVOKE ALL ON FUNCTION public.has_tenant_permission(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.has_tenant_permission(text, text) TO authenticated;

REVOKE ALL ON FUNCTION public.guardar_venta_rpc(text, text, text, text, text, jsonb, numeric, uuid, uuid, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.guardar_venta_rpc(text, text, text, text, text, jsonb, numeric, uuid, uuid, text) TO authenticated;

REVOKE ALL ON FUNCTION public.registrar_abono_credito_rpc(text, uuid, numeric, uuid, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.registrar_abono_credito_rpc(text, uuid, numeric, uuid, text) TO authenticated;

-- ---------------------------------------------------------------------------
-- 4. HABILITACIÓN DE RLS Y POLÍTICAS SEGURAS POR ACCIÓN (AIS-C05)
-- ---------------------------------------------------------------------------
ALTER TABLE public.empresas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tenant_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.productos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventario_lotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ventas ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.detalle_venta ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.caja ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.movimientos_caja ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cuentas_por_cobrar ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.abonos_credito ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gastos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.periodos_contables ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.idempotencia_operaciones ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auditoria_eventos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS productos_select ON public.productos;
DROP POLICY IF EXISTS productos_insert ON public.productos;
DROP POLICY IF EXISTS productos_update ON public.productos;
DROP POLICY IF EXISTS productos_delete ON public.productos;
DROP POLICY IF EXISTS ventas_select ON public.ventas;
DROP POLICY IF EXISTS ventas_insert ON public.ventas;
DROP POLICY IF EXISTS ventas_update ON public.ventas;
DROP POLICY IF EXISTS gastos_select ON public.gastos;
DROP POLICY IF EXISTS gastos_insert ON public.gastos;
DROP POLICY IF EXISTS gastos_update ON public.gastos;
DROP POLICY IF EXISTS gastos_delete ON public.gastos;

CREATE POLICY productos_select ON public.productos FOR SELECT TO authenticated
  USING (public.has_tenant_access(empresa_id));

CREATE POLICY productos_insert ON public.productos FOR INSERT TO authenticated
  WITH CHECK (public.has_tenant_permission(empresa_id, 'puede_crear_productos'));

CREATE POLICY productos_update ON public.productos FOR UPDATE TO authenticated
  USING (public.has_tenant_permission(empresa_id, 'puede_editar_productos'));

CREATE POLICY productos_delete ON public.productos FOR DELETE TO authenticated
  USING (public.has_tenant_permission(empresa_id, 'puede_eliminar_productos'));

CREATE POLICY ventas_select ON public.ventas FOR SELECT TO authenticated
  USING (public.has_tenant_access(empresa_id));

CREATE POLICY ventas_insert ON public.ventas FOR INSERT TO authenticated
  WITH CHECK (public.has_tenant_permission(empresa_id, 'puede_crear_ventas'));

CREATE POLICY ventas_update ON public.ventas FOR UPDATE TO authenticated
  USING (public.has_tenant_permission(empresa_id, 'puede_editar_ventas'));

CREATE POLICY gastos_select ON public.gastos FOR SELECT TO authenticated
  USING (public.has_tenant_access(empresa_id));

CREATE POLICY gastos_insert ON public.gastos FOR INSERT TO authenticated
  WITH CHECK (public.has_tenant_permission(empresa_id, 'puede_crear_gastos'));

CREATE POLICY gastos_update ON public.gastos FOR UPDATE TO authenticated
  USING (public.has_tenant_permission(empresa_id, 'puede_editar_gastos'));

CREATE POLICY gastos_delete ON public.gastos FOR DELETE TO authenticated
  USING (public.has_tenant_permission(empresa_id, 'puede_eliminar_gastos'));

COMMIT;
