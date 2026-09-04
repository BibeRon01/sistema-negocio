import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type",
};
const json = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

const apiKeyFromEnvironment = (currentName: string, legacyName: string) => {
  const current = Deno.env.get(currentName) ?? "";
  if (current) {
    try {
      const values = JSON.parse(current) as Record<string, unknown>;
      const candidate = values.default ?? Object.values(values)[0];
      if (typeof candidate === "string" && candidate.trim()) return candidate.trim();
    } catch {
      // Continúa con la clave heredada cuando el mapa actual no es válido.
    }
  }
  return (Deno.env.get(legacyName) ?? "").trim();
};

const verifiedAal = (token: string) => {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = part.padEnd(Math.ceil(part.length / 4) * 4, "=");
    return String(JSON.parse(atob(padded)).aal ?? "aal1");
  } catch {
    return "aal1";
  }
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json(405, { success: false, error: "METHOD_NOT_ALLOWED" });

  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const publishableKey = apiKeyFromEnvironment(
    "SUPABASE_PUBLISHABLE_KEYS",
    "SUPABASE_ANON_KEY",
  );
  const secretKey = apiKeyFromEnvironment(
    "SUPABASE_SECRET_KEYS",
    "SUPABASE_SERVICE_ROLE_KEY",
  );
  const token = (request.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!token) {
    return json(401, { success: false, error: "AUTH_REQUIRED" });
  }
  if (!url || !publishableKey || !secretKey) {
    return json(500, { success: false, error: "SERVER_NOT_CONFIGURED" });
  }

  const caller = createClient(url, publishableKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: callerData, error: callerError } = await caller.auth.getUser(token);
  if (
    callerError ||
    !callerData.user ||
    callerData.user.app_metadata?.role !== "superadmin"
  ) {
    return json(403, { success: false, error: "PLATFORM_SUPERADMIN_REQUIRED" });
  }
  if (verifiedAal(token) !== "aal2") {
    return json(403, { success: false, error: "MFA_AAL2_REQUIRED" });
  }

  let input: Record<string, unknown>;
  try {
    input = await request.json();
  } catch {
    return json(400, { success: false, error: "INVALID_JSON" });
  }

  const action = String(input.action ?? "").trim().toLowerCase();
  const tenantId = String(input.tenant_id ?? "").trim().toLowerCase();
  const nombre = String(input.nombre ?? "").trim();
  const active = input.activo !== false;
  const config =
    input.configuracion && typeof input.configuracion === "object"
      ? (input.configuracion as Record<string, unknown>)
      : {};
  if (
    !/^[a-z0-9][a-z0-9_-]{2,49}$/.test(tenantId) ||
    !["create", "update", "register_license"].includes(action)
  ) {
    return json(400, { success: false, error: "INVALID_COMPANY_DATA" });
  }
  if (tenantId === "global") {
    return json(400, { success: false, error: "RESERVED_TENANT_ID" });
  }

  const admin = createClient(url, secretKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: previousCompany, error: companyLookupError } = await admin
    .from("empresas")
    .select("tenant_id,nombre,activo")
    .eq("tenant_id", tenantId)
    .maybeSingle();
  if (companyLookupError) {
    return json(400, { success: false, error: "COMPANY_LOOKUP_FAILED" });
  }

  if (action === "register_license") {
    if (!previousCompany) {
      return json(404, { success: false, error: "COMPANY_NOT_FOUND" });
    }
    const license =
      input.licencia && typeof input.licencia === "object"
        ? (input.licencia as Record<string, unknown>)
        : {};
    const startDate = String(license.fecha_inicio ?? "").trim();
    const endDate = String(license.fecha_vencimiento ?? "").trim();
    const amount = Number(license.monto_pagado);
    const period = String(license.periodo ?? "").trim().toLowerCase();
    const paymentMethod = String(license.metodo_pago ?? "").trim().toLowerCase();
    const graceDays = Number(license.dias_gracia ?? 5);
    const observation = String(license.observacion ?? "").trim();
    const datePattern = /^\d{4}-\d{2}-\d{2}$/;
    const allowedPeriods = ["demostracion", "cortesia", "mensual", "trimestral", "anual", "personalizado"];
    const allowedMethods = ["cortesia", "efectivo", "transferencia", "tarjeta", "otro"];
    if (
      !datePattern.test(startDate) ||
      !datePattern.test(endDate) ||
      Number.isNaN(Date.parse(`${startDate}T00:00:00Z`)) ||
      Number.isNaN(Date.parse(`${endDate}T00:00:00Z`)) ||
      endDate < startDate ||
      !Number.isFinite(amount) ||
      amount < 0 ||
      amount > 1000000000 ||
      !allowedPeriods.includes(period) ||
      !allowedMethods.includes(paymentMethod) ||
      !Number.isInteger(graceDays) ||
      graceDays < 0 ||
      graceDays > 60 ||
      observation.length > 500
    ) {
      return json(400, { success: false, error: "INVALID_LICENSE_DATA" });
    }

    // La tabla histórica recibida por AIS usa bigint sin valor por defecto.
    // Solo la superadministradora A&M llega a esta ruta; calculamos el próximo
    // identificador y reintentamos una vez si otro registro se adelantó.
    const { data: latestLicense, error: latestError } = await admin
      .from("suscripciones_empresas")
      .select("id")
      .order("id", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (latestError) {
      const errorCode = String(latestError.code ?? "");
      return json(400, {
        success: false,
        error: errorCode === "42P01" ? "LICENSE_TABLE_NOT_AVAILABLE" : "LICENSE_NOT_CREATED",
      });
    }

    let nextId = Math.trunc(Number(latestLicense?.id ?? 0)) + 1;
    const licensePayload = {
      empresa_id: tenantId,
      fecha_inicio: startDate,
      fecha_vencimiento: endDate,
      monto_pagado: Math.round(amount * 100) / 100,
      periodo: period,
      metodo_pago: paymentMethod,
      dias_gracia: graceDays,
      observacion: observation || null,
    };
    let insertedLicense: Record<string, unknown> | null = null;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const { data, error } = await admin
        .from("suscripciones_empresas")
        .insert({ id: nextId, ...licensePayload })
        .select("id,empresa_id,fecha_inicio,fecha_vencimiento,monto_pagado,periodo,metodo_pago,dias_gracia,observacion,created_at")
        .single();
      if (!error) {
        insertedLicense = data as Record<string, unknown>;
        break;
      }
      if (String(error.code ?? "") !== "23505" || attempt > 0) {
        return json(400, { success: false, error: "LICENSE_NOT_CREATED" });
      }
      nextId += 1;
    }
    if (!insertedLicense) {
      return json(400, { success: false, error: "LICENSE_NOT_CREATED" });
    }

    await admin.from("auditoria_eventos").insert({
      empresa_id: tenantId,
      usuario_id: callerData.user.id,
      accion: "licencia_registrada",
      modulo: "Licencias",
      tabla: "suscripciones_empresas",
      registro_id: String(insertedLicense.id ?? nextId),
      detalle: "Licencia registrada por la superadministradora A&M",
      metadata: {
        fecha_inicio: startDate,
        fecha_vencimiento: endDate,
        monto_pagado: licensePayload.monto_pagado,
        periodo: period,
        metodo_pago: paymentMethod,
        dias_gracia: graceDays,
      },
    });

    return json(200, {
      success: true,
      tenant_id: tenantId,
      licencia: insertedLicense,
    });
  }

  if (action === "update" && !previousCompany) {
    return json(404, { success: false, error: "COMPANY_NOT_FOUND" });
  }
  if (action === "create" && previousCompany) {
    return json(409, { success: false, error: "COMPANY_ALREADY_EXISTS" });
  }
  const companyPayload = {
    tenant_id: tenantId,
    nombre: nombre || tenantId,
    activo: active,
  };
  const { error: companyError } =
    action === "create"
      ? await admin.from("empresas").insert(companyPayload)
      : await admin.from("empresas").update(companyPayload).eq("tenant_id", tenantId);
  if (companyError) return json(400, { success: false, error: companyError.message });

  const allowedConfig = {
    empresa_id: tenantId,
    propietario: tenantId,
    negocio_nombre: nombre || tenantId,
    telefono: String(config.telefono ?? ""),
    rnc: String(config.rnc ?? ""),
    direccion: String(config.direccion ?? ""),
    slogan: String(config.slogan ?? ""),
  };
  const { data: existingConfig, error: lookupError } = await admin
    .from("configuracion_sistema")
    .select("id")
    .eq("empresa_id", tenantId)
    .limit(1)
    .maybeSingle();
  if (lookupError) return json(400, { success: false, error: lookupError.message });
  const { error: configError } = existingConfig?.id
    ? await admin.from("configuracion_sistema").update(allowedConfig).eq("id", existingConfig.id)
    : await admin.from("configuracion_sistema").insert(allowedConfig);
  if (configError) {
    if (action === "create" && !previousCompany) {
      await admin.from("empresas").delete().eq("tenant_id", tenantId);
    } else if (previousCompany) {
      await admin.from("empresas").update({
        nombre: previousCompany.nombre,
        activo: previousCompany.activo,
      }).eq("tenant_id", tenantId);
    }
    return json(400, { success: false, error: configError.message });
  }

  await admin.from("auditoria_eventos").insert({
    empresa_id: tenantId,
    usuario_id: callerData.user.id,
    accion: action === "create" ? "empresa_creada" : active ? "empresa_actualizada" : "empresa_suspendida",
    modulo: "Empresas",
    tabla: "empresas",
    registro_id: tenantId,
    detalle: "Operación administrativa de empresa",
    metadata: { nombre: companyPayload.nombre, active },
  });

  return json(200, { success: true, tenant_id: tenantId, active });
});
