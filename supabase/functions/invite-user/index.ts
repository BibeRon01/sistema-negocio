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
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (request.method !== "POST") {
    return json(405, { success: false, error: "METHOD_NOT_ALLOWED" });
  }

  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!url || !anonKey || !serviceKey) {
    return json(500, { success: false, error: "SERVER_NOT_CONFIGURED" });
  }

  const bearer = request.headers.get("Authorization") ?? "";
  const token = bearer.replace(/^Bearer\s+/i, "").trim();
  if (!token) {
    return json(401, { success: false, error: "AUTH_REQUIRED" });
  }

  const admin = createClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const callerClient = createClient(url, anonKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { data: userData, error: userError } = await callerClient.auth.getUser(token);
  if (userError || !userData.user) {
    return json(401, { success: false, error: "INVALID_SESSION" });
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

  const email = String(input.email ?? "").trim().toLowerCase();
  const password = String(input.password ?? "");
  const nombre = String(input.nombre ?? "").trim();
  const role = String(input.rol ?? "").trim().toLowerCase();
  const tenantId = String(input.tenant_id ?? "").trim();
  const permissions =
    input.permissions && typeof input.permissions === "object" ? input.permissions : {};
  const validRoles = new Set(["admin", "gerente", "supervisor", "cajero", "cajera", "consulta"]);

  if (!email.includes("@") || password.length < 12 || !nombre || !tenantId || !validRoles.has(role)) {
    return json(400, { success: false, error: "INVALID_USER_DATA" });
  }

  const isPlatformSuperadmin = userData.user.app_metadata?.role === "superadmin";
  if (!isPlatformSuperadmin) {
    const { data: membership } = await admin
      .from("tenant_memberships")
      .select("role,permissions,active")
      .eq("user_id", userData.user.id)
      .eq("tenant_id", tenantId)
      .maybeSingle();
    const canManage =
      membership?.active === true &&
      membership.role === "admin";
    if (!canManage) {
      return json(403, { success: false, error: "USER_MANAGEMENT_PERMISSION_DENIED" });
    }
  }

  const { data: company } = await admin
    .from("empresas")
    .select("tenant_id,activo")
    .eq("tenant_id", tenantId)
    .maybeSingle();
  if (!company?.activo) {
    return json(400, { success: false, error: "TENANT_NOT_ACTIVE" });
  }

  const { data: created, error: createError } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
    user_metadata: { nombre },
  });
  if (createError || !created.user) {
    return json(400, { success: false, error: createError?.message ?? "AUTH_USER_NOT_CREATED" });
  }

  const authUserId = created.user.id;
  try {
    const { error: profileError } = await admin.from("usuarios").insert({
      id: authUserId,
      user_id: authUserId,
      empresa_id: tenantId,
      email_login: email,
      usuario: email.split("@")[0],
      nombre,
      rol: role,
      permissions,
      activo: true,
      legacy_login_disabled: true,
    });
    if (profileError) throw profileError;

    const { error: membershipError } = await admin.from("tenant_memberships").insert({
      user_id: authUserId,
      tenant_id: tenantId,
      role,
      permissions,
      active: true,
    });
    if (membershipError) throw membershipError;
  } catch (error) {
    await admin
      .from("usuarios")
      .delete()
      .eq("user_id", authUserId);
    await admin
      .from("tenant_memberships")
      .delete()
      .eq("user_id", authUserId)
      .eq("tenant_id", tenantId);
    await admin.auth.admin.deleteUser(authUserId);
    return json(400, {
      success: false,
      error: error instanceof Error ? error.message : "PROFILE_NOT_CREATED",
    });
  }

  return json(201, {
    success: true,
    user_id: authUserId,
    email,
    tenant_id: tenantId,
    role,
  });
});
