"""Restaura un respaldo cifrado únicamente en una base staging vacía.

El script nunca borra ni reemplaza registros. Si alguna tabla contiene datos,
se detiene antes de insertar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from supabase import create_client

from staging_validator import project_host, required, validate_distinct_environment


ORDER = [
    "empresas", "tenant_memberships", "usuarios", "configuracion_sistema",
    "sucursales", "clientes", "proveedores", "empleados", "productos",
    "inventario_lotes", "compras", "gastos", "caja", "ventas",
    "detalle_venta", "ventas_pagos", "inventario_consumos", "movimientos_caja",
    "cuentas_por_cobrar", "abonos_credito", "pagos_proveedores",
    "abonos_proveedores", "pagos_empleados", "adelantos_empleados",
    "movimientos_contables", "periodos_contables", "cierre_caja",
    "capital_base", "activos_fijos", "distribucion_beneficios", "perdidas",
    "gastos_dueno", "auditoria_eventos", "nomina_parametros",
    "secuencia_documentos", "inventario_actual", "movimientos",
    "ajustes_inventario", "conteo_inventario",
    "catalogo_gastos", "configuracion_financiera", "cuentas_dinero",
    "depreciacion", "depreciaciones", "movimientos_dinero", "notas_credito",
    "suscripciones_empresas",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument(
        "--confirm-project",
        required=True,
        help="Hostname exacto de STAGING, por ejemplo abc.supabase.co",
    )
    args = parser.parse_args()

    _, staging = validate_distinct_environment()
    if project_host(staging) != args.confirm_project.strip().lower():
        raise SystemExit("La confirmación no coincide con el proyecto staging.")

    key = required("STAGING_SUPABASE_SERVICE_KEY")
    cipher = Fernet(required("BACKUP_ENCRYPTION_KEY").encode("ascii"))
    client = create_client(staging, key)
    backup = args.backup.resolve()
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != 2 or manifest.get("errors"):
        raise SystemExit("El manifiesto no corresponde a un respaldo completo v2.")

    tables = manifest.get("tables") or {}
    for table in tables:
        response = client.table(table).select("*", count="exact").limit(1).execute()
        if (response.count or 0) != 0:
            raise SystemExit(
                f"Staging no está vacío: {table} contiene {response.count} registros."
            )

    existing_auth = client.auth.admin.list_users(page=1, per_page=1)
    auth_users = getattr(existing_auth, "users", existing_auth)
    if auth_users:
        raise SystemExit(
            "Staging Auth contiene cuentas. Use un proyecto staging completamente vacío."
        )

    def load_rows(table: str) -> list[dict]:
        metadata = tables[table]
        ciphertext = (backup / metadata["file"]).read_bytes()
        if hashlib.sha256(ciphertext).hexdigest() != metadata["sha256"]:
            raise SystemExit(f"Hash inválido para {table}.")
        return json.loads(cipher.decrypt(ciphertext).decode("utf-8"))

    # Auth no contiene contraseñas exportables. Se recrean cuentas staging con
    # claves aleatorias y se remapean todas las referencias al nuevo UUID.
    user_map: dict[str, str] = {}
    for profile in load_rows("usuarios") if "usuarios" in tables else []:
        old_id = str(profile.get("user_id") or "")
        email = str(profile.get("email_login") or "").strip().lower()
        if not old_id or "@" not in email:
            continue
        created = client.auth.admin.create_user({
            "email": email,
            "password": secrets.token_urlsafe(32),
            "email_confirm": True,
            "user_metadata": {"nombre": profile.get("nombre") or ""},
        })
        user_map[old_id] = created.user.id

    user_reference_keys = {"user_id", "usuario_id", "anulada_por", "cerrado_por"}

    def remap_users(value):
        if isinstance(value, dict):
            return {
                key: user_map.get(str(item), item)
                if key in user_reference_keys and item is not None
                else remap_users(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [remap_users(item) for item in value]
        return value

    restored = {}
    for table in ORDER:
        metadata = tables.get(table)
        if not metadata:
            continue
        rows = remap_users(load_rows(table))
        for offset in range(0, len(rows), 250):
            client.table(table).insert(rows[offset : offset + 250]).execute()
        restored[table] = len(rows)
        print(f"{table}: {len(rows)}")

    print(f"Restauración staging completada: {sum(restored.values())} registros.")
    print(f"Cuentas Auth recreadas: {len(user_map)}. Solicite restablecimiento de contraseña.")
    print("Ejecute las pruebas de integridad antes de considerar el simulacro aprobado.")


if __name__ == "__main__":
    main()
