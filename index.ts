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

const normalizeUsername = (value: unknown) => String(value ?? "").trim().toLowerCase();

const technicalEmail = async (tenantId: string, username: string) => {
  const source = new TextEncoder().encode(`${tenantId}\n${username}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", source));
  const hex = Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `u${hex.slice(0, 48)}@access.ais.invalid`;
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

  const admin = createClient(url, serviceKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const callerClient = createClient(url, anonKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: callerData, error: callerError } = await callerClient.auth.getUser(token);
  if (callerError || !callerData.user) return json(401, { success: false, error: "INVALID_SESSION" });
  if (verifiedAal(token) !== "aal2") {
    return json(403, { success: false, error: "MFA_AAL2_REQUIRED" });
  }

  let input: Record<string, unknown>;
  try {
    input = await request.json();
  } catch {
    return json(400, { success: false, error: "INVALID_JSON" });
  }

  const profileId = String(input.profile_id ?? "");
  const tenantId = String(input.tenant_id ?? "").trim();
  const username = normalizeUsername(input.username);
  const nombre = String(input.nombre ?? "").trim();
  const role = String(input.rol ?? "").trim().toLowerCase();
  const active = input.activo === true;
  const password = input.new_password ? String(input.new_password) : "";
  const permissions =
    input.permissions && typeof input.permissions === "object" ? input.permissions : {};
  const validRoles = new Set(["admin", "gerente", "supervisor", "cajero", "cajera", "consulta"]);
  if (
    !profileId ||
    !/^[a-z0-9][a-z0-9_-]{2,49}$/.test(tenantId) ||
    tenantId === "global" ||
    !/^[a-z0-9][a-z0-9._-]{2,31}$/.test(username) ||
    !nombre ||
    !validRoles.has(role) ||
    (password && password.length < 12)
  ) {
    return json(400, { success: false, error: "INVALID_USER_DATA" });
  }

  const isPlatformSuperadmin = callerData.user.app_metadata?.role === "superadmin";
  if (!isPlatformSuperadmin) {
    const { data: membership } = await admin
      .from("tenant_memberships")
      .select("role,permissions,active")
      .eq("user_id", callerData.user.id)
      .eq("tenant_id", tenantId)
      .maybeSingle();
    const canManage =
      membership?.active === true &&
      membership.role === "admin";
    if (!canManage) return json(403, { success: false, error: "USER_MANAGEMENT_PERMISSION_DENIED" });
  }

  const { data: target, error: targetError } = await admin
    .from("usuarios")
    .select("id,user_id,empresa_id,usuario,email_login,nombre,rol,activo,permissions")
    .eq("id", profileId)
    .eq("empresa_id", tenantId)
    .maybeSingle();
  if (targetError || !target?.user_id) return json(404, { success: false, error: "USER_NOT_FOUND" });
  const { data: targetAuth, error: targetAuthError } = await admin.auth.admin.getUserById(target.user_id);
  if (targetAuthError || !targetAuth?.user) {
    return json(404, { success: false, error: "AUTH_USER_NOT_FOUND" });
  }
  if (targetAuth?.user?.app_metadata?.role === "superadmin" && !isPlatformSuperadmin) {
    return json(403, { success: false, error: "PLATFORM_SUPERADMIN_PROTECTED" });
  }
  if (targetAuth?.user?.app_metadata?.role === "superadmin") {
    return json(403, { success: false, error: "PLATFORM_SUPERADMIN_USES_EMAIL" });
  }

  const { data: usernameOwner } = await admin
    .from("usuarios")
    .select("id")
    .eq("empresa_id", tenantId)
    .ilike("usuario", username)
    .neq("id", profileId)
    .maybeSingle();
  if (usernameOwner) {
    return json(409, { success: false, error: "USERNAME_ALREADY_EXISTS" });
  }
  if (target.user_id === callerData.user.id && (!active || role !== "admin") && !isPlatformSuperadmin) {
    return json(400, { success: false, error: "CANNOT_REMOVE_OWN_ADMIN_ACCESS" });
  }
  const { data: oldMembership, error: oldMembershipError } = await admin
    .from("tenant_memberships")
    .select("role,active,permissions")
    .eq("user_id", target.user_id)
    .eq("tenant_id", tenantId)
    .maybeSingle();
  if (oldMembershipError || !oldMembership) {
    return json(400, { success: false, error: "MEMBERSHIP_NOT_FOUND" });
  }
  if (oldMembership.role === "admin" && oldMembership.active && (!active || role !== "admin")) {
    const { count } = await admin
      .from("tenant_memberships")
      .select("user_id", { count: "exact", head: true })
      .eq("tenant_id", tenantId)
      .eq("role", "admin")
      .eq("active", true)
      .neq("user_id", target.user_id);
    if ((count ?? 0) < 1) {
      return json(400, { success: false, error: "TENANT_MUST_KEEP_ONE_ACTIVE_ADMIN" });
    }
  }

  const loginEmail = await technicalEmail(tenantId, username);
  const { error: profileError } = await admin
    .from("usuarios")
    .update({
      usuario: username,
      email_login: loginEmail,
      nombre,
      rol: role,
      activo: active,
      permissions,
      updated_at: new Date().toISOString(),
    })
    .eq("id", profileId);
  if (profileError) return json(400, { success: false, error: "PROFILE_NOT_UPDATED" });

  const { error: membershipError } = await admin
    .from("tenant_memberships")
    .update({ role, active, permissions, updated_at: new Date().toISOString() })
    .eq("user_id", target.user_id)
    .eq("tenant_id", tenantId);
  if (membershipError) {
    await admin.from("usuarios").update({
      usuario: target.usuario,
      email_login: target.email_login,
      nombre: target.nombre,
      rol: target.rol,
      activo: target.activo,
      permissions: target.permissions,
    }).eq("id", profileId);
    return json(400, { success: false, error: "MEMBERSHIP_NOT_UPDATED" });
  }

  const authUpdate: Record<string, unknown> = {
    ban_duration: active ? "none" : "876000h",
    email: loginEmail,
    email_confirm: true,
  };
  if (password) authUpdate.password = password;
  const { error: authError } = await admin.auth.admin.updateUserById(target.user_id, authUpdate);
  if (authError) {
    await admin.from("usuarios").update({
      usuario: target.usuario,
      email_login: target.email_login,
      nombre: target.nombre,
      rol: target.rol,
      activo: target.activo,
      permissions: target.permissions,
    }).eq("id", profileId);
    await admin.from("tenant_memberships").update({
      role: oldMembership.role,
      active: oldMembership.active,
      permissions: oldMembership.permissions,
    }).eq("user_id", target.user_id).eq("tenant_id", tenantId);
    return json(400, { success: false, error: "AUTH_USER_NOT_UPDATED" });
  }

  await admin.from("auditoria_eventos").insert({
    empresa_id: tenantId,
    usuario_id: callerData.user.id,
    accion: active ? "usuario_actualizado" : "usuario_desactivado",
    modulo: "Usuarios",
    tabla: "usuarios",
    registro_id: profileId,
    detalle: "Cambio administrativo de perfil y membresía",
    metadata: { username, role, active },
  });

  return json(200, { success: true, profile_id: profileId, username, active, role });
});
