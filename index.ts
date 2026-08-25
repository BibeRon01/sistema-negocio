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

const normalizeUsername = (value: unknown) => String(value ?? "").trim().toLowerCase();
const PASSWORD_MIN_LENGTH = 4;
const passwordIsValid = (value: string) =>
  value.length >= PASSWORD_MIN_LENGTH &&
  /[^\p{L}\p{N}\s]/u.test(value);

const technicalEmail = async (tenantId: string, username: string) => {
  const source = new TextEncoder().encode(`${tenantId}\n${username}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", source));
  const hex = Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `u${hex.slice(0, 48)}@access.ais.invalid`;
};

const availableUsernameSuggestions = async (
  admin: ReturnType<typeof createClient>,
  username: string,
) => {
  const stem = (username.replace(/\d+$/, "") || "usuario").slice(0, 29);
  const suggestions: string[] = [];
  for (let number = 1; number <= 60 && suggestions.length < 3; number += 1) {
    const candidate = `${stem}${String(number).padStart(2, "0")}`.slice(0, 32);
    const { data } = await admin
      .from("usuarios")
      .select("id")
      .ilike("usuario", candidate)
      .limit(1);
    if (!data?.length) suggestions.push(candidate);
  }
  return suggestions;
};

const usernameConflict = async (
  admin: ReturnType<typeof createClient>,
  username: string,
) => json(409, {
  success: false,
  error: "USERNAME_ALREADY_EXISTS",
  suggestions: await availableUsernameSuggestions(admin, username),
});

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

  const admin = createClient(url, secretKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const callerClient = createClient(url, publishableKey, {
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

  const action = String(input.action ?? "update").trim().toLowerCase();
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
  if (!new Set(["update", "delete"]).has(action)) {
    return json(400, { success: false, error: "INVALID_USER_ACTION" });
  }
  if (action === "update" && password && !passwordIsValid(password)) {
    return json(400, { success: false, error: "PASSWORD_POLICY_INVALID" });
  }
  if (
    !profileId ||
    !/^[a-z0-9][a-z0-9_-]{2,49}$/.test(tenantId) ||
    tenantId === "global"
  ) {
    return json(400, { success: false, error: "INVALID_USER_DATA" });
  }
  if (
    action === "update" &&
    (!/^[a-z0-9][a-z0-9._-]{2,31}$/.test(username) ||
      !nombre ||
      !validRoles.has(role))
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

  const { data: oldMembership, error: oldMembershipError } = await admin
    .from("tenant_memberships")
    .select("role,active,permissions")
    .eq("user_id", target.user_id)
    .eq("tenant_id", tenantId)
    .maybeSingle();
  if (oldMembershipError || !oldMembership) {
    return json(400, { success: false, error: "MEMBERSHIP_NOT_FOUND" });
  }

  if (action === "delete") {
    if (target.user_id === callerData.user.id) {
      return json(400, { success: false, error: "CANNOT_DELETE_SELF" });
    }
    if (target.activo === true || oldMembership.active === true) {
      return json(400, { success: false, error: "USER_MUST_BE_INACTIVE" });
    }

    const { data: preparation, error: preparationError } = await callerClient.rpc(
      "api_prepare_delete_unused_user",
      { p_profile_id: profileId, p_tenant_id: tenantId },
    );
    if (preparationError) {
      const message = String(preparationError.message ?? "");
      const knownError = [
        "AUTH_REQUIRED",
        "MFA_AAL2_REQUIRED",
        "USER_MANAGEMENT_PERMISSION_DENIED",
        "USER_NOT_FOUND",
        "CANNOT_DELETE_SELF",
        "PLATFORM_SUPERADMIN_PROTECTED",
      ].find((code) => message.includes(code));
      return json(400, {
        success: false,
        error: knownError ?? "DELETE_PRECHECK_FAILED",
      });
    }
    if (!preparation || preparation.success !== true) {
      return json(409, {
        success: false,
        error: String(preparation?.error ?? "DELETE_PRECHECK_FAILED"),
      });
    }

    // Auth es la identidad raíz. Sus FK con ON DELETE CASCADE eliminan perfil
    // y membresía únicamente después de que la RPC confirmó que no hay historia.
    const { error: deleteError } = await admin.auth.admin.deleteUser(
      target.user_id,
      false,
    );
    if (deleteError) {
      return json(400, { success: false, error: "AUTH_USER_NOT_DELETED" });
    }

    await admin.from("auditoria_eventos").insert({
      empresa_id: tenantId,
      usuario_id: callerData.user.id,
      accion: "usuario_sin_actividad_eliminado",
      modulo: "Usuarios",
      tabla: "usuarios",
      registro_id: profileId,
      detalle: "Eliminación permanente de cuenta inactiva sin historial",
      metadata: { username: target.usuario, former_role: target.rol },
    });

    return json(200, {
      success: true,
      deleted: true,
      username: target.usuario,
      username_available: true,
    });
  }

  const { data: usernameOwner } = await admin
    .from("usuarios")
    .select("id")
    .ilike("usuario", username)
    .neq("id", profileId)
    .limit(1)
    .maybeSingle();
  if (usernameOwner) {
    return await usernameConflict(admin, username);
  }
  if (target.user_id === callerData.user.id && (!active || role !== "admin") && !isPlatformSuperadmin) {
    return json(400, { success: false, error: "CANNOT_REMOVE_OWN_ADMIN_ACCESS" });
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
  if (profileError) {
    if (String(profileError.code ?? "") === "23505") {
      return await usernameConflict(admin, username);
    }
    return json(400, { success: false, error: "PROFILE_NOT_UPDATED" });
  }

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
    const authCode = String(authError.code ?? "").toLowerCase();
    const authMessage = String(authError.message ?? "").toLowerCase();
    const errorCode =
      authCode === "weak_password" || authMessage.includes("password") || authMessage.includes("weak")
        ? "AUTH_PASSWORD_POLICY_REJECTED"
        : "AUTH_USER_NOT_UPDATED";
    return json(400, { success: false, error: errorCode });
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
