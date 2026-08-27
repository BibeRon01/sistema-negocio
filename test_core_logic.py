from pathlib import Path
import ast
from datetime import datetime
from types import SimpleNamespace

import pytest

from nomina_view import calcular_nomina_completa
from utils import (
    correo_tecnico_acceso,
    html_escape,
    normalizar_tenant_acceso,
    normalizar_usuario_acceso,
    password_usuario_valida,
)


ROOT = Path(__file__).resolve().parents[1]
IGNORED_SOURCE_DIRS = {"tests", "__pycache__", ".venv", "venv", ".git"}


def project_python_files():
    return [
        path for path in ROOT.rglob("*.py")
        if not (set(path.relative_to(ROOT).parts) & IGNORED_SOURCE_DIRS)
    ]


def test_nomina_mensual_2026():
    result = calcular_nomina_completa(50_000, "mensual", 2026)
    assert result["sueldo_bruto"] == 50_000
    assert result["sfs_empleado"] == 1_520
    assert result["afp_empleado"] == 1_435
    assert result["isr"] == 1_854
    assert result["neto_pagar"] == 45_191


def test_password_empresarial_exige_minimo_cuatro_y_simbolo():
    assert password_usuario_valida("a1.@")
    assert password_usuario_valida("123@")
    assert password_usuario_valida("a12?")
    assert not password_usuario_valida("a.@")
    assert not password_usuario_valida("a123")
    assert not password_usuario_valida("a12 ")


def test_nomina_quincenal_prorratea_todas_las_deducciones():
    result = calcular_nomina_completa(50_000, "quincenal", 2026)
    assert result["sueldo_bruto"] == 25_000
    assert result["sfs_empleado"] == 760
    assert result["afp_empleado"] == 717.5
    assert result["isr"] == 927
    assert result["neto_pagar"] == 22_595.5
    assert result["sueldo_bruto"] - result["neto_pagar"] == pytest.approx(
        result["sfs_empleado"] + result["afp_empleado"] + result["isr"]
    )


def test_nomina_rechaza_ano_sin_parametros_verificados():
    with pytest.raises(ValueError):
        calcular_nomina_completa(50_000, "mensual", 2025)


def test_nomina_rechaza_arl_fuera_del_rango_configurable():
    with pytest.raises(ValueError):
        calcular_nomina_completa(50_000, "mensual", 2026, arl_tasa=0.02)


def test_nomina_usa_escala_isr_2026_verificada():
    result = calcular_nomina_completa(100_000, "mensual", 2026)
    assert result["isr"] == 12_105.44
    assert result["neto_pagar"] == 81_984.56


def test_no_hay_credenciales_maestras_en_codigo():
    forbidden = [
        "APP_PASSWORD",
        "active_session",
        "master_pin",
        "PIN Maestro",
        "str(clave_guardada).strip() ==",
    ]
    forbidden_in_helpers = [
        "_legacy_login_desactivado",
        "verificar_codigo_totp",
        "mfa_requerido_para_admin",
        "totp_secret",
    ]
    files = project_python_files()
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    for marker in forbidden:
        assert marker.lower() not in combined.lower()
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    for marker in forbidden_in_helpers:
        assert marker.lower() not in helpers.lower()


def test_no_hay_comparaciones_de_password_con_literales_ni_perfiles_fabricados():
    sensitive_names = {
        "password", "passwd", "clave", "contrasena", "contraseña",
        "pass_clean", "pwd_in_clean",
    }
    for path in project_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                has_literal = any(
                    isinstance(item, ast.Constant)
                    and isinstance(item.value, str)
                    and bool(item.value)
                    for item in operands
                )
                names = {
                    item.id.lower()
                    for item in operands
                    if isinstance(item, ast.Name)
                }
                assert not (has_literal and names & sensitive_names), path

            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
                for target in node.targets:
                    if not isinstance(target, ast.Subscript):
                        continue
                    key = target.slice
                    if isinstance(key, ast.Constant) and key.value == "usuario_data":
                        raise AssertionError(f"Perfil local fabricado en {path}")


def test_sesion_exige_supabase_auth_api_my_session_y_cierre_ante_error():
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    secure_login = helpers[helpers.index("def login_simple()") :]
    assert 'client.auth.get_user(access_token)' in helpers
    assert 'client.rpc("api_my_session", params)' in helpers
    assert "ahora - ultima_validacion" not in helpers
    assert "limpiar_estado_sesion(cerrar_auth=True)" in helpers
    assert 'str(profile.get("aal") or "").lower() != "aal2"' in helpers
    assert "active_session" not in secure_login
    assert 'profile["aal"] = "aal2"' not in secure_login
    assert "otorgando paso a perfil verificado" not in secure_login
    assert "accediendo con perfil verificado" not in secure_login
    invalid_code = helpers.index('if not factor_id or len(str(code).strip()) != 6')
    assert "limpiar_estado_sesion(cerrar_auth=True)" in helpers[invalid_code:invalid_code + 350]


def test_autorizacion_sql_exige_aal2_a_roles_privilegiados():
    sql = (
        ROOT / "supabase/migrations/202607250001_secure_foundation.sql"
    ).read_text(encoding="utf-8")
    access = sql[sql.index("create or replace function public.has_tenant_access"):
                 sql.index("create or replace function public.has_tenant_permission")]
    permission = sql[sql.index("create or replace function public.has_tenant_permission"):
                     sql.index("-- Compatibilidad con tablas históricas")]
    assert "public.is_platform_superadmin()" in access
    assert "tm.role <> 'admin'" in access
    assert "auth.jwt() ->> 'aal'" in access
    assert "p_permission not in" in permission
    assert "auth.jwt() ->> 'aal'" in permission


def test_selector_multiempresa_solo_usa_tenant_de_sesion_verificada():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    db = (ROOT / "db.py").read_text(encoding="utf-8")
    api = (ROOT / "api_client.py").read_text(encoding="utf-8")
    assert "cambiar_tenant_autorizado(empresa_seleccionada)" in app
    assert "superadmin_tenant_seleccionado" not in app
    assert 'select("propietario, negocio_nombre")' not in app
    assert db.count("def obtener_tenant_actual") == 1
    assert 'tenant_sesion if tenant_sesion in permitidos else ""' in db
    assert 'empresa_id.eq.global' not in db
    assert 'builder.eq("email", tenant)' not in db
    assert 'payload["tenant_id"] = tenant_id' in api
    assert 'payload["empresa_id"] = tenant_id' in api
    assert 'payload.setdefault("tenant_id"' not in api


def test_migracion_invalida_credenciales_heredadas_aunque_sean_obligatorias():
    sql = (
        ROOT / "supabase/migrations/202607250001_secure_foundation.sql"
    ).read_text(encoding="utf-8")
    drop_constraint = (
        "alter table public.configuracion_sistema alter column clave drop not null"
    )
    clear_value = (
        "update public.configuracion_sistema set clave=null where clave is not null"
    )
    assert drop_constraint in sql
    assert clear_value in sql
    assert sql.index(drop_constraint) < sql.index(clear_value)
    assert "alter table public.usuarios alter column %I drop not null" in sql


def test_dgii_no_tiene_emision_operativa():
    ecf = (ROOT / "facturacion_electronica_view.py").read_text(encoding="utf-8")
    credit_notes = (ROOT / "notas_credito_view.py").read_text(encoding="utf-8")
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    assert "pkcs12.load_key_and_certificates" not in ecf
    assert "XML e-CF Oficial" not in ecf
    assert "Producción (Facturación Real)" not in ecf
    assert "TrackID\": \"TRK-" not in ecf
    assert "consumir_ncf_siguiente" not in credit_notes
    assert "consumir_ncf_siguiente" not in helpers
    assert "insertar(" not in credit_notes
    assert "no crea, numera, firma, registra ni" in credit_notes


def test_api_critica_es_transaccional_y_recalcula():
    sql = (ROOT / "supabase/migrations/202607250002_transactional_api.sql").read_text(
        encoding="utf-8"
    )
    assert "api_registrar_venta" in sql
    assert "INVALID_ITEM_QUANTITY" in sql
    assert "PAYMENT_MISMATCH" in sql
    assert "for update" in sql.lower()
    assert "inventario_consumos" in sql
    assert "public.api_anular_venta" in sql
    assert "public.api_abrir_caja" in sql
    assert "public.api_cerrar_caja" in sql
    assert "DGII_EDUCATIONAL_ONLY" in sql


def test_api_mantenimiento_cubre_cuenta_compra_nomina_y_cierre():
    foundation = (
        ROOT / "supabase/migrations/202607250001_secure_foundation.sql"
    ).read_text(encoding="utf-8")
    sql = (
        ROOT / "supabase/migrations/202607250003_maintenance_and_accounting_api.sql"
    ).read_text(encoding="utf-8")
    for function_name in [
        "api_reemplazar_cuenta_abierta",
        "api_registrar_compra_producto",
        "api_registrar_nomina",
        "api_cerrar_periodo",
    ]:
        assert function_name in sql
    assert "EMPLOYEE_ARL_RATE_REQUIRED" in sql
    assert "DUPLICATE_PAYROLL_PAYMENT" in sql
    assert "v_emp.id::text" in sql
    assert "v_compra_id uuid" in sql
    assert "returning id into v_compra_id" in sql
    assert "id bigint generated by default as identity primary key" in foundation
    assert "compra_id uuid" in foundation
    assert "lote_id bigint references public.inventario_lotes(id)" in foundation
    assert "usuario_id text" in foundation
    first_tenant_columns = foundation.index(
        "-- Columnas mínimas requeridas por la API segura"
    )
    first_product_columns = foundation.index(
        "alter table if exists public.productos add column"
    )
    tenant_column_block = foundation[first_tenant_columns:first_product_columns]
    assert "'inventario_lotes'" in tenant_column_block
    assert "update public.inventario_lotes il" in foundation
    assert "set empresa_id=c.empresa_id" in foundation
    assert "set empresa_id=p.empresa_id" in foundation
    assert foundation.count(
        "'alter table public.%I add column if not exists empresa_id text'"
    ) >= 4
    assert "public.has_tenant_access(p_tenant uuid)" in foundation
    assert "public.has_tenant_permission(\n    p_tenant uuid" in foundation
    assert "public.has_tenant_access(p_tenant::text)" in foundation
    assert "public.has_tenant_permission(p_tenant::text, p_permission)" in foundation


def test_factura_compra_completa_es_atomica_e_idempotente():
    foundation = (
        ROOT / "supabase/migrations/202607250001_secure_foundation.sql"
    ).read_text(encoding="utf-8")
    sql = (
        ROOT / "supabase/migrations/202607250003_maintenance_and_accounting_api.sql"
    ).read_text(encoding="utf-8")
    inventory = (ROOT / "inventario_view.py").read_text(encoding="utf-8")

    assert "create table if not exists public.facturas_compra" in foundation
    assert "create table if not exists public.detalle_factura_compra" in foundation
    assert "unique (empresa_id, idempotency_key)" in foundation
    assert "api_registrar_factura_compra" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "IDEMPOTENCY_PAYLOAD_MISMATCH" in sql
    assert "for update" in sql.lower()
    assert "factura_compra_id" in sql
    assert "inventario_lotes" in sql
    assert "movimientos_contables" in sql
    assert "auditoria_eventos" in sql

    save_start = inventory.index('if st.button("🖨️ Guardar"')
    save_end = inventory.index("# =====================================================", save_start)
    save_block = inventory[save_start:save_end]
    assert "registrar_factura_compra(payload_factura)" in save_block
    assert "registrar_compra_producto(" not in save_block
    assert "idempotency_key" in save_block


def test_sql_consolidado_contiene_las_fuentes_en_orden_sin_divergencias():
    consolidated = (ROOT / "SQL_APLICAR_EN_SUPABASE.md").read_text(encoding="utf-8")
    blocks = [
        part.split("```", 1)[0].strip()
        for part in consolidated.split("```sql\n")[1:]
    ]
    sources = [
        "supabase/checks/001_preflight_readonly.sql",
        "supabase/migrations/202607250001_secure_foundation.sql",
        "supabase/migrations/202607250002_transactional_api.sql",
            "supabase/migrations/202607250003_maintenance_and_accounting_api.sql",
            "supabase/migrations/202608150002_company_username_auth.sql",
            "supabase/checks/003_global_username_preflight.sql",
            "supabase/migrations/202608220001_global_unique_usernames.sql",
            "supabase/migrations/202608250001_safe_unused_user_deletion.sql",
            "supabase/checks/002_postdeploy_readonly.sql",
    ]
    assert blocks == [
        (ROOT / source).read_text(encoding="utf-8").strip()
        for source in sources
    ]
    obsolete = (ROOT / "SQL_PARA_PEGAR.md").read_text(encoding="utf-8")
    assert "OBSOLETO — NO EJECUTAR" in obsolete[:500]


def test_html_dinamico_usa_escape_seguro():
    assert html_escape('<script>alert("x")</script>') == (
        "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    )
    pos = (ROOT / "pos_view.py").read_text(encoding="utf-8")
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    assert 'usuario_caja = html_escape(caja.get("usuario", ""))' in pos
    assert "logo_url_html = html_escape(logo_url)" in helpers


def test_rls_no_contiene_politica_publica_total():
    sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "supabase/migrations").glob("*.sql")
    ).lower()
    assert "using (true)" not in sql
    assert "with check (true)" not in sql
    assert "from anon" in sql
    assert "has_tenant_access" in sql
    assert "registrar_venta_transaccional" in sql
    assert (
        "revoke all on function %i.%i(%s) from public, anon, authenticated"
        in sql
    )
    assert "usuario_id=auth.uid()" in sql
    assert "la pertenencia a una empresa no concede por sí sola" in sql


def test_copias_de_compatibilidad_son_minimas():
    for folder in ("core", "modules"):
        for path in (ROOT / folder).glob("*.py"):
            if path.name == "__init__.py":
                continue
            assert len(path.read_text(encoding="utf-8").splitlines()) <= 5


def test_modulos_canonicos_no_provocan_importacion_circular():
    for name in ("app.py", "db.py", "auth.py", "utils.py", "helpers.py"):
        code = (ROOT / name).read_text(encoding="utf-8")
        assert "from core.db import" not in code
        assert "from core.auth import" not in code
        assert "from core.utils import" not in code
        assert "from core.helpers import" not in code

    core_db = (ROOT / "core/db.py").read_text(encoding="utf-8")
    assert "from db import _df_actual" not in core_db
    assert "from db import _pii_mask" not in core_db


def test_migraciones_no_contienen_operaciones_destructivas_de_esquema():
    for path in (ROOT / "supabase/migrations").glob("*.sql"):
        sql = path.read_text(encoding="utf-8").lower()
        assert "drop table" not in sql
        assert "truncate " not in sql
        assert sql.count("$$") % 2 == 0
        assert sql.strip().startswith("--")
        assert sql.strip().endswith("commit;")


def test_edge_functions_exigen_mfa_y_service_role_solo_en_servidor():
    for path in (ROOT / "supabase/functions").glob("*/index.ts"):
        code = path.read_text(encoding="utf-8")
        assert '"SUPABASE_PUBLISHABLE_KEYS"' in code
        assert '"SUPABASE_SECRET_KEYS"' in code
        assert '"SUPABASE_ANON_KEY"' in code
        assert '"SUPABASE_SERVICE_ROLE_KEY"' in code
        assert "createClient(url, secretKey" in code
        if path.parent.name == "resolve-login":
            assert "MFA_AAL2_REQUIRED" not in code
            assert "getUser(token)" not in code
            assert '"Cache-Control": "no-store"' in code
            assert "profiles.length !== 1" in code
            assert "login_hint" in code
        else:
            assert "MFA_AAL2_REQUIRED" in code
            assert "getUser(token)" in code
        if path.parent.name in {"invite-user", "manage-user"}:
            assert "PASSWORD_MIN_LENGTH = 4" in code
            assert "passwordIsValid" in code
            assert "PASSWORD_POLICY_INVALID" in code
            assert "AUTH_PASSWORD_POLICY_REJECTED" in code
    application_code = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ["app.py", "db.py", "auth.py", "helpers.py", "api_client.py"]
    )
    assert "SUPABASE_SERVICE_ROLE_KEY" not in application_code
    assert "SUPABASE_SERVICE_KEY" not in application_code
    invite = (
        ROOT / "supabase/functions/invite-user/index.ts"
    ).read_text(encoding="utf-8")
    provision = (ROOT / "scripts/provision_owner.py").read_text(encoding="utf-8")
    assert "id: authUserId" in invite
    assert '"id": user_id' in provision


def test_documentacion_declara_staging_y_limite_dgii():
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    guide = (ROOT / "GUIA_PUBLICACION.md").read_text(encoding="utf-8").lower()
    assert "publicación controlada en **staging**" in readme
    assert "no debe\n> conectarse primero a producción" in readme
    assert "no genera, firma, valida ni envía" in readme
    assert "empresa a y empresa b" in guide


def test_helpers_no_ejecuta_login_durante_importacion():
    tree = ast.parse((ROOT / "helpers.py").read_text(encoding="utf-8"))
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Call)
        and isinstance(node.test.operand.func, ast.Name)
        and node.test.operand.func.id == "login_simple"
    ]
    assert top_level_calls == []


def test_qr_mfa_usa_uri_totp_validada_sin_mostrar_el_secreto():
    source = (ROOT / "helpers.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_validar_uri_totp"
    )
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {}
    exec(
        compile(ast.fix_missing_locations(isolated), "helpers.py", "exec"),
        namespace,
    )
    validate = namespace["_validar_uri_totp"]
    valid_uri = "otpauth://totp/AIS:usuario?secret=TESTONLY&issuer=AIS"

    assert validate(valid_uri) == valid_uri

    with pytest.raises(ValueError, match="MFA_QR_INVALID"):
        validate("https://example.com/?secret=TESTONLY")
    with pytest.raises(ValueError, match="MFA_QR_INVALID"):
        validate("otpauth://totp/AIS:usuario?issuer=AIS")

    assert 'otpauth_uri = str(_auth_obj_value(totp, "uri", "") or "")' in source
    assert '"qr_png": _mfa_qr_png(otpauth_uri)' in source
    assert "st.image(qr_png, width=220)" in source
    assert "_mfa_qr_svg_markup" not in source
    assert '"qr_code": str(_auth_obj_value(totp' not in source
    assert '"secret": str(_auth_obj_value(totp' not in source
    assert "st.code(secret" not in source
    assert '"friendly_name": "AIS Administrador"' not in source
    assert 'factors_response, "all"' in source
    assert '== "unverified"' in source
    assert "_descartar_factores_totp_no_verificados(unverified)" in source
    assert 'supabase.auth.mfa.unenroll({"factor_id": pending_id})' in source
    mfa_render = source[source.index("def _render_mfa_nativo"):]
    mfa_render = mfa_render[:mfa_render.index("def login_simple")]
    assert "unsafe_allow_javascript" not in mfa_render


def test_mfa_pendiente_conserva_inscripcion_entre_recargas():
    source = (ROOT / "helpers.py").read_text(encoding="utf-8")
    secure_login = source[source.index("def login_simple"):]

    assert 'pending_mfa = st.session_state.get("login_pending_mfa")' in secure_login
    assert 'pending_mfa["profile"] = profile' in secure_login
    assert secure_login.count(
        'st.session_state["login_pending_mfa"] = {"profile": profile}'
    ) == 1
    assert "active_session" not in secure_login


def test_permisos_sql_coinciden_con_la_aplicacion():
    sql = (ROOT / "supabase/migrations/202607250001_secure_foundation.sql").read_text(
        encoding="utf-8"
    )
    for permission in [
        "puede_editar_productos",
        "puede_registrar_compras",
        "puede_registrar_gastos",
    ]:
        assert permission in sql
    assert (
        "pagos_empleados add column if not exists empleado_id text"
        in sql
    )


def test_no_hay_rutas_privadas_de_la_computadora_en_la_aplicacion():
    application_code = "\n".join(
        path.read_text(encoding="utf-8")
        for path in project_python_files()
    )
    assert "/Users/user/Desktop/" not in application_code


def test_hay_una_sola_entrada_activa_para_login_y_academia_dgii():
    helpers_tree = ast.parse((ROOT / "helpers.py").read_text(encoding="utf-8"))
    accounting_tree = ast.parse(
        (ROOT / "contabilidad_view.py").read_text(encoding="utf-8")
    )
    helper_names = [
        node.name for node in helpers_tree.body if isinstance(node, ast.FunctionDef)
    ]
    accounting_names = [
        node.name for node in accounting_tree.body if isinstance(node, ast.FunctionDef)
    ]
    assert helper_names.count("login_simple") == 1
    assert accounting_names.count("render_reportes_dgii") == 1


def test_no_se_puede_retirar_el_ultimo_admin_de_una_empresa():
    sql = (ROOT / "supabase/migrations/202607250001_secure_foundation.sql").read_text(
        encoding="utf-8"
    )
    assert "protect_last_tenant_admin" in sql
    assert "TENANT_MUST_KEEP_ONE_ACTIVE_ADMIN" in sql


def test_edicion_de_permisos_conserva_flags_no_visibles():
    auth_code = (ROOT / "auth.py").read_text(encoding="utf-8")
    assert "permisos = dict(defaults_dict)" in auth_code
    for permission in [
        "puede_ver_dashboard",
        "puede_ver_reportes",
        "puede_ver_utilidad",
        "puede_configurar",
    ]:
        assert f'permisos["{permission}"]' in auth_code


def test_publicacion_rechaza_llaves_privadas_y_sanea_la_marca():
    db_code = (ROOT / "db.py").read_text(encoding="utf-8")
    app_code = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "sb_secret_" in db_code
    assert "jwt_role != \"anon\"" in db_code
    assert "_texto_html_seguro" in app_code
    assert "_logo_html_seguro" in app_code
    assert 'menu = "POS"' not in app_code


def test_login_publicable_unifica_identificador_y_revalida_la_sesion():
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    secure_login = helpers[helpers.index("def login_simple()"):] 
    assert '"Usuario o correo electrónico"' in secure_login
    assert 'placeholder="usuario o correo@ejemplo.com"' in secure_login
    assert 'key="secure_login_identifier"' in secure_login
    assert 'key="secure_login_tenant"' not in secure_login
    assert 'st.text_input(\n        "Empresa"' not in secure_login
    assert '"Administrador A&M"' not in secure_login
    assert "normalizar_usuario_acceso(identifier)" in secure_login
    assert "_resolver_email_login_usuario(username)" in secure_login
    assert "separar_identificador_usuario_empresa" not in secure_login
    assert "correo_tecnico_acceso" not in secure_login
    assert 'access_kind == "username"' in secure_login
    assert 'profile.get("es_superadmin") is not True' in secure_login
    assert "sign_in_with_password" in secure_login
    assert "_last_session_validation" in secure_login
    assert "profile = _cargar_perfil_verificado()" in secure_login
    assert "active_session" not in secure_login
    assert "SESSION_INACTIVITY_SECONDS" in secure_login
    assert "1 hora de inactividad" in secure_login
    assert "PRIVILEGED_SESSION_INACTIVITY_SECONDS = 24 * 60 * 60" in helpers
    assert "MFA_REAUTHENTICATION_SECONDS = 24 * 60 * 60" in helpers
    assert "mfa_verified_at" in secure_login


def test_mfa_diario_conserva_aal2_sin_confiar_en_dispositivo_o_ubicacion():
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    auth = (ROOT / "auth.py").read_text(encoding="utf-8")
    cookie = (ROOT / "session_cookie.py").read_text(encoding="utf-8")
    guide = (ROOT / "GUIA_ACCESO_EMPRESAS.md").read_text(encoding="utf-8")
    mfa_flow = helpers[
        helpers.index("def _render_mfa_nativo"):
        helpers.index("_LOGIN_HINT_RE")
    ]
    secure_login = helpers[helpers.index("def login_simple()") :]

    assert mfa_flow.index("challenge_and_verify") < mfa_flow.index('["mfa_verified_at"]')
    assert "ahora - mfa_verified_at > MFA_REAUTHENTICATION_SECONDS" in secure_login
    assert "_cargar_perfil_verificado(tenant)" in secure_login
    assert "_restaurar_sesion_navegador()" in secure_login
    restore = helpers[
        helpers.index("def _restaurar_sesion_navegador"):
        helpers.index("def _resolver_email_login_usuario")
    ]
    assert restore.index("_guardar_tokens_auth") < restore.index("_cargar_perfil_verificado")
    assert 'profile.get("aal")' in restore
    assert "MFA_REAUTHENTICATION_SECONDS" in restore
    assert "limpiar_estado_sesion(cerrar_auth=True)" in restore
    assert '"mfa_verified_at"' in auth
    assert "24 horas" in guide
    assert "no confía en IP, ubicación" in guide
    assert "Fernet" in cookie
    assert "SESSION_COOKIE_SECRET" in cookie
    assert 'secure=_request_is_https()' in cookie
    assert 'same_site="strict"' in cookie
    assert "borrar_sesion_navegador" in auth
    assert "extra-streamlit-components==0.1.81" in (
        ROOT / "requirements.txt"
    ).read_text(encoding="utf-8")
    assert "trusted_device" not in helpers
    assert "active_session" not in helpers


def test_cookie_de_sesion_cifra_tokens_y_rechaza_manipulacion(monkeypatch):
    import session_cookie

    cookie_jar = {}

    class FakeManager:
        def __init__(self):
            self.cookies = cookie_jar

        def set(self, cookie, value, **_kwargs):
            cookie_jar[cookie] = value

        def delete(self, cookie, **_kwargs):
            cookie_jar.pop(cookie, None)

    manager = FakeManager()
    monkeypatch.setenv("SESSION_COOKIE_SECRET", "s" * 48)
    monkeypatch.setattr(session_cookie, "stx", object())
    monkeypatch.setattr(session_cookie.st, "session_state", {})
    monkeypatch.setattr(session_cookie, "_cookie_manager", lambda: manager)
    monkeypatch.setattr(session_cookie, "_request_cookies", lambda: dict(cookie_jar))
    monkeypatch.setattr(session_cookie, "_request_is_https", lambda: True)

    now = datetime.now().timestamp()
    assert session_cookie.guardar_sesion_navegador(
        access_token="access-token-private",
        refresh_token="refresh-token-private",
        tenant_id="empresa01",
        privileged=True,
        mfa_verified_at=now,
        last_activity=now,
    )
    encoded = cookie_jar[session_cookie.COOKIE_NAME]
    assert "access-token-private" not in encoded
    assert "refresh-token-private" not in encoded
    payload = session_cookie.leer_sesion_navegador()
    assert payload["access_token"] == "access-token-private"
    assert payload["refresh_token"] == "refresh-token-private"

    cookie_jar[session_cookie.COOKIE_NAME] = encoded[:-1] + (
        "A" if encoded[-1] != "A" else "B"
    )
    assert session_cookie.leer_sesion_navegador() is None
    assert session_cookie.COOKIE_NAME not in cookie_jar


def test_token_aal2_rotado_se_sincroniza_antes_de_rpc_y_edge_functions():
    db = (ROOT / "db.py").read_text(encoding="utf-8")
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    client = (ROOT / "api_client.py").read_text(encoding="utf-8")

    sync = db[
        db.index("def sincronizar_tokens_sesion"):
        db.index("def renovar_cliente_sesion")
    ]
    verified_profile = helpers[
        helpers.index("def _cargar_perfil_verificado"):
        helpers.index("def cambiar_tenant_autorizado")
    ]
    assert "client.auth.get_session()" in sync
    assert '_guardar_tokens_sesion_actual(session)' in sync
    assert 'st.session_state["access_token"] = access_token' in db
    assert 'st.session_state["refresh_token"] = refresh_token' in db
    assert verified_profile.index("sincronizar_tokens_sesion()") < verified_profile.index(
        "client.auth.get_user(access_token)"
    )
    assert "def _access_token_vigente" in client
    assert client.count("access_token = _access_token_vigente()") == 4
    assert 'VERSION_SISTEMA = "v3.0.1-secure"' in db
    assert 'Código: {support_code}' in client


def test_sincronizacion_copia_ambos_tokens_rotados(monkeypatch):
    import db

    rotated = SimpleNamespace(
        access_token="jwt-aal2-rotado",
        refresh_token="refresh-rotado",
    )
    fake_client = SimpleNamespace(
        auth=SimpleNamespace(get_session=lambda: rotated),
    )
    session_state = {}
    monkeypatch.setattr(db, "obtener_cliente_sesion", lambda: fake_client)
    monkeypatch.setattr(db.st, "session_state", session_state)

    assert db.sincronizar_tokens_sesion() == "jwt-aal2-rotado"
    assert session_state["access_token"] == "jwt-aal2-rotado"
    assert session_state["refresh_token"] == "refresh-rotado"
    assert session_state["_supabase_session_fingerprint"] != "anon"


def test_recuperacion_password_exige_token_hash_verificado_por_supabase():
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    recovery = helpers[
        helpers.index("def _render_recuperacion_password"):
        helpers.index("def _cargar_perfil_verificado")
    ]
    assert '"token_hash": token_hash' in recovery
    assert '"type": "recovery"' in recovery
    assert "supabase.auth.verify_otp" in recovery
    assert 'client.auth.update_user({"password": nueva_clean})' in recovery
    assert "password_recovery_verified" in recovery
    assert "access_token" not in recovery.split("st.query_params", 1)[0]


def test_aprovisionamiento_promueve_identidad_existente_sin_cambiar_password_o_mfa():
    provision = (ROOT / "scripts/provision_owner.py").read_text(encoding="utf-8")
    assert '"--existing-user-id"' in provision
    assert "get_user_by_id(args.existing_user_id)" in provision
    assert 'app_metadata["role"] = "superadmin"' in provision
    existing_branch = provision[
        provision.index("if args.existing_user_id:", provision.index("client =")):
        provision.index("else:", provision.index("if args.existing_user_id:", provision.index("client =")))
    ]
    assert '"password"' not in existing_branch
    assert "unenroll" not in provision


def test_ventas_y_compras_permiten_filtrar_por_usuario_sin_cambiar_tenant():
    pos = (ROOT / "pos_view.py").read_text(encoding="utf-8")
    compras = (ROOT / "inventario_view.py").read_text(encoding="utf-8")
    assert '"Filtrar por usuario"' in pos
    assert 'key="ventas_filtro_usuario"' in pos
    assert '"Filtrar compras por usuario"' in compras
    assert 'key="compras_filtro_usuario"' in compras
    assert 'mc2.metric("Total comprado"' in compras


def test_identidad_tecnica_empresarial_es_determinista_y_no_expone_datos():
    first = correo_tecnico_acceso("biberon01", "cajera01")
    second = correo_tecnico_acceso("BIBERON01", "CAJERA01")
    other = correo_tecnico_acceso("biberon01", "cajera02")
    assert first == second
    assert first != other
    assert first.endswith("@access.ais.invalid")
    assert "biberon" not in first
    assert "cajera" not in first
    assert normalizar_tenant_acceso(" BIBERON01 ") == "biberon01"
    assert normalizar_usuario_acceso(" CAJERA01 ") == "cajera01"
    with pytest.raises(ValueError):
        normalizar_tenant_acceso("global")
    with pytest.raises(ValueError):
        normalizar_usuario_acceso("usuario@correo.com")


def test_alta_empresarial_no_acepta_correo_personal_ni_credencial_local():
    client = (ROOT / "api_client.py").read_text(encoding="utf-8")
    invite = (ROOT / "supabase/functions/invite-user/index.ts").read_text(
        encoding="utf-8"
    )
    manage = (ROOT / "supabase/functions/manage-user/index.ts").read_text(
        encoding="utf-8"
    )
    migration = (
        ROOT / "supabase/migrations/202608220001_global_unique_usernames.sql"
    ).read_text(encoding="utf-8")

    invite_client = client[
        client.index("def invitar_usuario_seguro"):
        client.index("def gestionar_usuario_seguro")
    ]
    assert '"username": username' in invite_client
    assert '"email":' not in invite_client
    assert "input.email" not in invite
    assert "technicalEmail(tenantId, username)" in invite
    assert "admin.auth.admin.createUser" in invite
    assert "email_confirm: true" in invite
    assert "USERNAME_ALREADY_EXISTS" in invite
    assert "USERNAME_ALREADY_IN_TENANT" in invite
    assert "email: loginEmail" in manage
    assert "email_confirm: true" in manage
    assert "USERNAME_ALREADY_EXISTS" in manage
    assert "uq_usuarios_usuario_global_ci" in migration
    assert "revoke select on public.usuarios from anon" in migration.lower()


def test_usuario_es_global_y_el_resolvedor_no_autentica_por_sustitucion():
    invite = (ROOT / "supabase/functions/invite-user/index.ts").read_text(encoding="utf-8")
    manage = (ROOT / "supabase/functions/manage-user/index.ts").read_text(encoding="utf-8")
    resolver = (ROOT / "supabase/functions/resolve-login/index.ts").read_text(encoding="utf-8")
    sql = (ROOT / "SQL_APLICAR_EN_SUPABASE.md").read_text(encoding="utf-8")

    invite_conflict = invite[invite.index("existingProfile"):invite.index("const email =")]
    manage_conflict = manage[manage.index("usernameOwner"):manage.index("if (target.user_id")]
    assert '.eq("empresa_id", tenantId)' not in invite_conflict
    assert '.eq("empresa_id", tenantId)' not in manage_conflict
    assert "availableUsernameSuggestions" in invite
    assert "availableUsernameSuggestions" in manage
    assert "USERNAME_ALREADY_EXISTS" in invite
    assert "USERNAME_ALREADY_EXISTS" in manage
    assert "USERNAME_ALREADY_IN_TENANT" in invite
    assert "signInWithPassword" not in resolver
    assert "createUser" not in resolver
    assert "tenant_memberships" in resolver
    assert "login_hint: decoyHint" in resolver
    assert "publishableKeys.includes(requestApiKey)" not in resolver
    assert "if (!requestApiKey)" in resolver
    assert "uq_usuarios_usuario_global_ci" in sql


def test_documentacion_y_vistas_entregan_solo_usuario_sin_empresa_visible():
    files = [
        ROOT / "README.md",
        ROOT / "GUIA_ACCESO_EMPRESAS.md",
        ROOT / "GUIA_PUBLICACION.md",
        ROOT / "central_am_view.py",
        ROOT / "admin_view.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "empresa/usuario" not in combined
    assert "identificador_usuario_empresa(" not in combined


def test_alta_de_usuario_empresarial_evitar_reintentos_lentos_y_refresca_conflictos():
    admin_view = (ROOT / "admin_view.py").read_text(encoding="utf-8")
    client = (ROOT / "api_client.py").read_text(encoding="utf-8")
    invite = (ROOT / "supabase/functions/invite-user/index.ts").read_text(encoding="utf-8")

    create_block = admin_view[
        admin_view.index('with st.form("form_crear_usuario_empresa"'):
        admin_view.index("with tab_edit:")
    ]
    assert "st.form_submit_button" in create_block
    assert 'invalidar_cache_tabla("usuarios")' in create_block
    assert "USERNAME_ALREADY_IN_TENANT" in client
    assert '.select("id,empresa_id")' in invite
    assert 'error: "USERNAME_ALREADY_IN_TENANT"' in invite


def test_eliminacion_permanente_solo_admite_usuarios_inactivos_sin_historial():
    sql = (
        ROOT / "supabase/migrations/202608250001_safe_unused_user_deletion.sql"
    ).read_text(encoding="utf-8")
    consolidated = (ROOT / "SQL_APLICAR_EN_SUPABASE.md").read_text(encoding="utf-8")
    edge = (ROOT / "supabase/functions/manage-user/index.ts").read_text(encoding="utf-8")
    client = (ROOT / "api_client.py").read_text(encoding="utf-8")
    view = (ROOT / "admin_view.py").read_text(encoding="utf-8")

    assert "api_prepare_delete_unused_user" in sql
    assert "MFA_AAL2_REQUIRED" in sql
    assert "USER_MUST_BE_INACTIVE" in sql
    assert "USER_HAS_OPERATIONAL_HISTORY" in sql
    assert "v_auth_user_exists" in sql
    assert "orphan_cleaned" in sql
    assert "delete from public.tenant_memberships" in sql.lower()
    assert "delete from public.usuarios" in sql.lower()
    assert "ORPHAN_PROFILE_NOT_DELETED" in sql
    assert "pg_attribute" in sql
    assert "usuario_id::text = $1" in sql
    assert "for update of u, tm" in sql.lower()
    assert "grant execute" in sql.lower()
    assert "to authenticated" in sql.lower()
    assert "api_prepare_delete_unused_user" in consolidated
    assert "orphan_cleaned" in consolidated

    delete_branch = edge[edge.index('if (action === "delete")'):]
    assert "target.activo === true || oldMembership.active === true" in delete_branch
    assert delete_branch.index("api_prepare_delete_unused_user") < delete_branch.index("deleteUser(")
    assert delete_branch.index("preparation.orphan_cleaned === true") < delete_branch.index("deleteUser(")
    assert "false," in delete_branch[delete_branch.index("deleteUser("):]
    assert "username_available: true" in delete_branch
    assert 'targetAuthMissing && action !== "delete"' in edge
    assert 'error: "AUTH_USER_STATE_INCONSISTENT"' in delete_branch
    assert 'error: "PROFILE_LOOKUP_FAILED"' in edge
    assert 'action === "delete"' in edge
    assert "already_deleted: true" in edge
    assert '"action": "delete"' in client
    assert "def eliminar_usuario_seguro" in client
    assert '"USER_NOT_FOUND"' in client
    assert '"PROFILE_LOOKUP_FAILED"' in client
    assert '"AUTH_USER_NOT_FOUND"' in client
    assert '"ORPHAN_PROFILE_NOT_DELETED"' in client
    assert "confirm_hard_delete_user" in view
    assert "Eliminar definitivamente y liberar usuario" in view
    assert 'df = leer_tabla("usuarios").copy()' in view
    assert 'invalidar_cache_tabla("usuarios")' in view
    assert '"_reset_user_editor_widgets"' in view
    assert 'key="usuarios_tabs"' in view
    assert 'on_change="rerun"' in view
    assert '"_usuarios_tab_destino"' in view
    assert '"_reset_user_editor_selection"' in view


def test_cliente_de_ventas_no_reintenta_otra_rpc():
    code = (ROOT / "api_client.py").read_text(encoding="utf-8")
    function = code[code.index("def registrar_venta"):code.index("def editar_venta")]
    assert "api_registrar_venta" in function
    assert "guardar_venta_rpc" not in function
    assert "except" not in function


def test_importador_historico_esta_bloqueado_a_biberon_y_mfa():
    sql = (
        ROOT / "supabase/migrations/202608150001_importacion_historica_biberon01.sql"
    ).read_text(encoding="utf-8")
    view = (ROOT / "migracion_biberon_view.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "auth.jwt() ->> 'aal'" in sql
    assert "MFA_AAL2_REQUIRED" in sql
    assert "tm.tenant_id='biberon01'" in sql
    assert "BIBERON_TENANT_MISMATCH" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "IMPORT_IDEMPOTENCY_MISMATCH" in sql
    assert "MAX_ARCHIVO_BYTES" in view
    assert "_expectativas_paquete" in view
    assert "_resultado_correcto" in view
    assert '_tenant_actual == "biberon01"' in app


def test_importador_historico_no_mueve_caja_ni_stock_por_ventas():
    sql = (
        ROOT / "supabase/migrations/202608150001_importacion_historica_biberon01.sql"
    ).read_text(encoding="utf-8")
    sales_branch = sql[
        sql.index("elsif v_entity='ventas'"):
        sql.index("elsif v_entity='ventas_pagos'")
    ]
    losses_branch = sql[
        sql.index("elsif v_entity='perdidas'"):
        sql.index("elsif v_entity='ventas_producto_historico'")
    ]
    assert "movimientos_caja" not in sales_branch
    assert "detalle_venta" not in sales_branch
    assert "update public.productos" not in sales_branch
    assert "update public.productos" not in losses_branch
    assert "factura_historica_cff" in sql
    assert "CFF-[0-9]+" in sql


def test_cache_de_datos_usa_el_tenant_seleccionado():
    for name in ("db.py", "helpers.py"):
        code = (ROOT / name).read_text(encoding="utf-8")
        assert "t_id = obtener_tenant_actual() or \"anon\"" in code
