"""Provisiona una sola cuenta propietaria con Supabase Auth.

Uso local y excepcional. La service-role se lee del ambiente y nunca se guarda.
"""

from __future__ import annotations

import argparse
import getpass
import os

from supabase import create_client


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Falta la variable obligatoria {name}.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--platform-superadmin", action="store_true")
    args = parser.parse_args()
    password = getpass.getpass("Contraseña inicial (mínimo 12 caracteres): ")
    if len(password) < 12:
        raise SystemExit("La contraseña debe tener al menos 12 caracteres.")

    client = create_client(required("SUPABASE_URL"), required("SUPABASE_SERVICE_KEY"))
    client.table("empresas").upsert({
        "tenant_id": args.tenant,
        "nombre": args.tenant,
        "activo": True,
    }).execute()
    existing_config = (
        client.table("configuracion_sistema")
        .select("id")
        .eq("empresa_id", args.tenant)
        .limit(1)
        .execute()
        .data
        or []
    )
    config_payload = {
        "empresa_id": args.tenant,
        "propietario": args.tenant,
        "negocio_nombre": args.tenant,
    }
    if existing_config:
        client.table("configuracion_sistema").update(config_payload).eq(
            "id", existing_config[0]["id"]
        ).execute()
    else:
        client.table("configuracion_sistema").insert(config_payload).execute()

    created = client.auth.admin.create_user({
        "email": args.email.strip().lower(),
        "password": password,
        "email_confirm": True,
        "app_metadata": {"role": "superadmin"} if args.platform_superadmin else {},
        "user_metadata": {"nombre": args.name},
    })
    user_id = created.user.id
    try:
        client.table("usuarios").upsert({
            "id": user_id,
            "user_id": user_id,
            "empresa_id": args.tenant,
            "email_login": args.email.strip().lower(),
            "usuario": args.email.split("@", 1)[0].lower(),
            "nombre": args.name,
            "rol": "admin",
            "permissions": {"puede_configurar": True},
            "activo": True,
            "legacy_login_disabled": True,
        }, on_conflict="user_id").execute()
        client.table("tenant_memberships").upsert({
            "user_id": user_id,
            "tenant_id": args.tenant,
            "role": "admin",
            "permissions": {"puede_configurar": True},
            "active": True,
        }).execute()
    except Exception:
        try:
            client.table("usuarios").delete().eq("user_id", user_id).execute()
            client.auth.admin.delete_user(user_id)
        finally:
            raise
    print(f"Cuenta creada: {args.email} / {args.tenant}")
    print("En el primer acceso se exigirá configurar MFA.")


if __name__ == "__main__":
    main()
