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
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const token = (request.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!url || !anonKey || !serviceKey || !token) {
    return json(401, { success: false, error: "AUTH_REQUIRED" });
  }

  const caller = createClient(url, anonKey, {
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
  if (!/^[a-z0-9][a-z0-9_-]{2,49}$/.test(tenantId) || !["create", "update"].includes(action)) {
    return json(400, { success: false, error: "INVALID_COMPANY_DATA" });
  }
  if (tenantId === "global") {
    return json(400, { success: false, error: "RESERVED_TENANT_ID" });
  }

  const admin = createClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: previousCompany } = await admin
    .from("empresas")
    .select("tenant_id,nombre,activo")
    .eq("tenant_id", tenantId)
    .maybeSingle();
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
