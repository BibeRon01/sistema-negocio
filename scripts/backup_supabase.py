"""Respaldo cifrado de datos de aplicación.

No sustituye el respaldo administrado de PostgreSQL/Supabase y no exporta
contraseñas de Auth. Las credenciales y la llave se leen solo del ambiente.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet
from supabase import create_client


TABLES = [
    "empresas", "tenant_memberships", "usuarios", "configuracion_sistema",
    "sucursales", "productos", "inventario_lotes", "inventario_consumos",
    "inventario_actual", "movimientos", "ajustes_inventario", "conteo_inventario",
    "clientes", "proveedores", "compras", "gastos", "ventas", "detalle_venta",
    "ventas_pagos", "caja", "cierre_caja", "movimientos_caja",
    "cuentas_por_cobrar", "abonos_credito", "pagos_proveedores",
    "abonos_proveedores", "empleados", "pagos_empleados", "adelantos_empleados",
    "movimientos_contables", "periodos_contables", "capital_base", "activos_fijos",
    "distribucion_beneficios", "perdidas", "gastos_dueno", "auditoria_eventos",
    "nomina_parametros", "secuencia_documentos",
    "catalogo_gastos", "configuracion_financiera", "cuentas_dinero",
    "depreciacion", "depreciaciones", "movimientos_dinero", "notas_credito",
    "suscripciones_empresas",
]


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Falta la variable obligatoria {name}.")
    return value


def read_all(client, table: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        response = client.table(table).select("*").range(start, start + 999).execute()
        chunk = response.data or []
        rows.extend(chunk)
        if len(chunk) < 1000:
            return rows
        start += 1000


def main() -> None:
    url = required("SUPABASE_URL")
    service_key = required("SUPABASE_SERVICE_KEY")
    encryption_key = required("BACKUP_ENCRYPTION_KEY")
    cipher = Fernet(encryption_key.encode("ascii"))
    client = create_client(url, service_key)

    project_root = Path(__file__).resolve().parents[1]
    output_root = Path(os.environ.get("BACKUP_DIR", project_root / "backups")).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    destination = output_root / f"backup_{timestamp}"
    destination.mkdir(parents=True, exist_ok=False)

    manifest = {
        "format": 2,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_host": url.split("//", 1)[-1].split("/", 1)[0],
        "tables": {},
        "errors": {},
    }

    for table in TABLES:
        try:
            rows = read_all(client, table)
            plaintext = json.dumps(
                rows, ensure_ascii=False, separators=(",", ":"), default=str
            ).encode("utf-8")
            ciphertext = cipher.encrypt(plaintext)
            file_name = f"{table}.json.enc"
            (destination / file_name).write_bytes(ciphertext)
            manifest["tables"][table] = {
                "rows": len(rows),
                "file": file_name,
                "sha256": hashlib.sha256(ciphertext).hexdigest(),
            }
        except Exception as exc:
            manifest["errors"][table] = str(exc)

    if manifest["errors"]:
        raise SystemExit(
            "Respaldo incompleto; no se escribió manifiesto final. Errores: "
            + ", ".join(manifest["errors"])
        )

    manifest_bytes = json.dumps(
        manifest, ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8")
    (destination / "manifest.json").write_bytes(manifest_bytes)
    print(f"Respaldo completo: {destination}")
    print(f"Tablas: {len(manifest['tables'])}")


if __name__ == "__main__":
    main()
