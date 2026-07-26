"""Pruebas RLS de solo lectura.

Se omiten localmente si no se proporcionan dos tokens de staging.
Nunca aceptan una URL de producción.
"""

import os
from urllib.parse import urlparse

import pytest
from supabase import create_client


URL = os.environ.get("TEST_STAGING_SUPABASE_URL", "")
KEY = os.environ.get("TEST_STAGING_SUPABASE_KEY", "")
TOKEN_A = os.environ.get("TEST_TENANT_A_ACCESS_TOKEN", "")
TOKEN_B = os.environ.get("TEST_TENANT_B_ACCESS_TOKEN", "")
TENANT_A = os.environ.get("TEST_TENANT_A_ID", "")
TENANT_B = os.environ.get("TEST_TENANT_B_ID", "")
PRODUCTION_URL = os.environ.get("SUPABASE_URL", "")


def _configured():
    return all([URL, KEY, TOKEN_A, TOKEN_B, TENANT_A, TENANT_B])


def _client(token=None):
    client = create_client(URL, KEY)
    if token:
        client.postgrest.auth(token)
    return client


@pytest.fixture(scope="module", autouse=True)
def staging_only():
    if not _configured():
        pytest.skip("Credenciales RLS de staging no configuradas.")
    assert urlparse(URL).hostname != urlparse(PRODUCTION_URL).hostname


def test_anon_no_lee_periodos_ni_auditoria():
    client = _client()
    for table in ("periodos_contables", "auditoria_eventos", "usuarios"):
        try:
            data = client.table(table).select("*").limit(1).execute().data or []
        except Exception:
            data = []
        assert data == []


@pytest.mark.parametrize(
    ("token", "tenant"),
    [(TOKEN_A, TENANT_A), (TOKEN_B, TENANT_B)],
)
def test_cada_usuario_solo_ve_su_empresa(token, tenant):
    data = _client(token).table("productos").select("empresa_id").limit(1000).execute().data or []
    assert all(row.get("empresa_id") == tenant for row in data)


def test_los_resultados_de_empresas_no_se_mezclan():
    data_a = _client(TOKEN_A).table("productos").select("id").limit(1000).execute().data or []
    data_b = _client(TOKEN_B).table("productos").select("id").limit(1000).execute().data or []
    assert {row["id"] for row in data_a}.isdisjoint({row["id"] for row in data_b})
