import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "apikey, content-type",
  "Cache-Control": "no-store",
};

const json = (status: number, body: Record<string, unknown>) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

const apiKeysFromEnvironment = (currentName: string, legacyName: string) => {
  const values: string[] = [];
  const current = Deno.env.get(currentName) ?? "";
  if (current) {
    try {
      const parsed = JSON.parse(current) as Record<string, unknown>;
      for (const candidate of Object.values(parsed)) {
        if (typeof candidate === "string" && candidate.trim()) {
          values.push(candidate.trim());
        }
      }
    } catch {
      if (current.trim()) values.push(current.trim());
    }
  }
  const legacy = (Deno.env.get(legacyName) ?? "").trim();
  if (legacy) values.push(legacy);
  return [...new Set(values)];
};

const normalizeUsername = (value: unknown) => String(value ?? "").trim().toLowerCase();
const usernameIsValid = (value: string) => /^[a-z0-9][a-z0-9._-]{2,31}$/.test(value);
const loginHintIsValid = (value: string) =>
  /^u[0-9a-f]{48}@access\.ais\.invalid$/.test(value);

const technicalEmail = async (scope: string, username: string) => {
  const source = new TextEncoder().encode(`${scope}\n${username}`);
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", source));
  const hex = Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `u${hex.slice(0, 48)}@access.ais.invalid`;
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json(405, { success: false, error: "METHOD_NOT_ALLOWED" });

  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const publishableKeys = apiKeysFromEnvironment(
    "SUPABASE_PUBLISHABLE_KEYS",
    "SUPABASE_ANON_KEY",
  );
  const secretKey = apiKeysFromEnvironment(
    "SUPABASE_SECRET_KEYS",
    "SUPABASE_SERVICE_ROLE_KEY",
  )[0] ?? "";
  const requestApiKey = (request.headers.get("apikey") ?? "").trim();
  if (!url || publishableKeys.length === 0 || !secretKey) {
    return json(503, { success: false, error: "SERVER_NOT_CONFIGURED" });
  }
  // La llave pública puede rotarse y Streamlit puede conservar temporalmente
  // una llave pública anterior todavía válida. Este endpoint no autentica ni
  // concede acceso: solo entrega un identificador técnico opaco. La contraseña
  // y la sesión se validan después en Supabase Auth y api_my_session.
  if (!requestApiKey) {
    return json(401, { success: false, error: "INVALID_PROJECT_KEY" });
  }

  let input: Record<string, unknown>;
  try {
    input = await request.json();
  } catch {
    return json(400, { success: false, error: "INVALID_JSON" });
  }

  const username = normalizeUsername(input.username);
  const decoyHint = await technicalEmail("missing", username || "invalid");
  if (!usernameIsValid(username)) {
    return json(200, { success: true, login_hint: decoyHint });
  }

  const admin = createClient(url, secretKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });
  const { data: profiles, error: profileError } = await admin
    .from("usuarios")
    .select("user_id,empresa_id,email_login,activo")
    .ilike("usuario", username)
    .limit(2);
  if (profileError) {
    return json(503, { success: false, error: "LOGIN_RESOLVER_UNAVAILABLE" });
  }

  if (!profiles || profiles.length !== 1 || profiles[0].activo !== true) {
    return json(200, { success: true, login_hint: decoyHint });
  }
  const profile = profiles[0];
  const userId = String(profile.user_id ?? "");
  const tenantId = String(profile.empresa_id ?? "");
  if (!userId || !tenantId || tenantId === "global") {
    return json(200, { success: true, login_hint: decoyHint });
  }

  const [{ data: company }, { data: membership }] = await Promise.all([
    admin.from("empresas").select("activo").eq("tenant_id", tenantId).maybeSingle(),
    admin
      .from("tenant_memberships")
      .select("active")
      .eq("user_id", userId)
      .eq("tenant_id", tenantId)
      .maybeSingle(),
  ]);
  if (company?.activo !== true || membership?.active !== true) {
    return json(200, { success: true, login_hint: decoyHint });
  }

  let loginHint = String(profile.email_login ?? "").trim().toLowerCase();
  if (!loginHintIsValid(loginHint)) {
    loginHint = await technicalEmail(tenantId, username);
  }
  return json(200, { success: true, login_hint: loginHint });
});
