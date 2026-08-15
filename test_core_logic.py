from pathlib import Path
import ast
import base64

import pytest

from nomina_view import calcular_nomina_completa
from utils import html_escape


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
    assert 'client.auth.get_user(access_token)' in helpers
    assert 'client.rpc("api_my_session", params)' in helpers
    assert "ahora - ultima_validacion" not in helpers
    assert "limpiar_estado_sesion(cerrar_auth=True)" in helpers
    assert 'str(profile.get("aal") or "").lower() != "aal2"' in helpers
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
        assert "MFA_AAL2_REQUIRED" in code
        assert 'Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")' in code
        assert "getUser(token)" in code
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


def test_qr_mfa_se_renderiza_saneado_sin_mostrar_el_secreto():
    source = (ROOT / "helpers.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mfa_qr_svg_markup"
    )
    isolated = ast.Module(body=[function], type_ignores=[])
    namespace = {"base64": base64, "re": __import__("re")}
    exec(
        compile(ast.fix_missing_locations(isolated), "helpers.py", "exec"),
        namespace,
    )
    normalize = namespace["_mfa_qr_svg_markup"]

    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="10"></svg>'
    encoded_svg = base64.b64encode(svg.encode("utf-8")).decode("ascii")

    assert normalize(svg) == svg
    assert normalize(
        "data:image/svg+xml;utf-8,"
        "%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20"
        "width%3D%2210%22%3E%3C/svg%3E"
    ) == svg
    assert normalize(f"data:image/svg+xml;base64,{encoded_svg}") == svg

    with pytest.raises(ValueError, match="MFA_QR_INVALID"):
        normalize("data:image/svg+xml;utf-8,contenido-invalido")

    assert "st.html(_mfa_qr_svg_markup(qr_code), width=220)" in source
    assert '"secret": str(_auth_obj_value(totp' not in source
    assert "st.code(secret" not in source
    assert '"friendly_name": "AIS Administrador"' not in source
    mfa_render = source[source.index("def _render_mfa_nativo"):]
    mfa_render = mfa_render[:mfa_render.index("def login_simple")]
    assert "unsafe_allow_javascript" not in mfa_render


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


def test_login_publicable_exige_correo_y_revalida_la_sesion():
    helpers = (ROOT / "helpers.py").read_text(encoding="utf-8")
    secure_login = helpers[helpers.index("def login_simple()"):]
    assert 'st.text_input("Correo electrónico"' in secure_login
    assert "@empresa.com" not in secure_login
    assert "_last_session_validation" in secure_login
    assert "_cargar_perfil_verificado()" in secure_login


def test_cliente_de_ventas_no_reintenta_otra_rpc():
    code = (ROOT / "api_client.py").read_text(encoding="utf-8")
    function = code[code.index("def registrar_venta"):code.index("def editar_venta")]
    assert "api_registrar_venta" in function
    assert "guardar_venta_rpc" not in function
    assert "except" not in function


def test_cache_de_datos_usa_el_tenant_seleccionado():
    for name in ("db.py", "helpers.py"):
        code = (ROOT / name).read_text(encoding="utf-8")
        assert "t_id = obtener_tenant_actual() or \"anon\"" in code
