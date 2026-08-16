"""Valida que staging sea una instancia distinta y muestra conteos sin escribir."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from supabase import create_client

from backup_supabase import TABLES


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Falta la variable obligatoria {name}.")
    return value


def project_host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def validate_distinct_environment() -> tuple[str, str]:
    production = required("SUPABASE_URL")
    staging = required("STAGING_SUPABASE_URL")
    if project_host(production) == project_host(staging):
        raise SystemExit("STAGING_SUPABASE_URL apunta a producción. Operación abortada.")
    return production, staging


def main() -> None:
    _, staging = validate_distinct_environment()
    key = required("STAGING_SUPABASE_SERVICE_KEY")
    client = create_client(staging, key)
    print(f"Staging validado: {project_host(staging)}")
    for table in TABLES:
        try:
            response = client.table(table).select("*", count="exact").limit(1).execute()
            print(f"{table}: {response.count or 0}")
        except Exception:
            print(f"{table}: ERROR DE LECTURA (detalle omitido)")


if __name__ == "__main__":
    main()
