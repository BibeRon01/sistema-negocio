"""Provisiona una sola cuenta propietaria con Supabase Auth.

Uso local y excepcional. La service-role se lee del ambiente y nunca se guarda.
"""

from __future__ import annotations

import argparse
import getpass
import os
import uuid

from supabase import create_client


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Falta la variable obligatoria {name}.")
    return value


def obj_value(obj, name: str, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--platform-superadmin", action="store_true")
    parser.add_argument(
        "--existing-user-id",
        help=(
            "UUID de una cuenta Auth existente que se conservará. Solo puede "
            "usarse junto con --platform-superadmin."
        ),
    )
    args = parser.parse_args()
    if args.existing_user_id and not args.platform_superadmin:
        raise SystemExit("--existing-user-id requiere --platform-superadmin.")
    if args.existing_user_id:
        try:
            uuid.UUID(args.existing_user_id)
        except ValueError as exc:
            raise SystemExit("--existing-user-id debe ser un UUID válido.") from exc
        password = None
    else:
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

    email = args.email.strip().lower()
    created_new_user = not bool(args.existing_user_id)
    if args.existing_user_id:
        existing_response = client.auth.admin.get_user_by_id(args.existing_user_id)
        existing_user = obj_value(existing_response, "user")
        existing_email = str(obj_value(existing_user, "email", "") or "").strip().lower()
        if not existing_user or existing_email != email:
            raise SystemExit("El UUID no corresponde al correo indicado.")
        app_metadata = dict(obj_value(existing_user, "app_metadata", {}) or {})
        app_metadata["role"] = "superadmin"
        client.auth.admin.update_user_by_id(
            args.existing_user_id,
            {
                "app_metadata": app_metadata,
                "user_metadata": {
                    **dict(obj_value(existing_user, "user_metadata", {}) or {}),
                    "nombre": args.name,
                },
            },
        )
        user_id = args.existing_user_id
    else:
        created = client.auth.admin.create_user({
            "email": email,
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
            "email_login": email,
            "usuario": email.split("@", 1)[0].lower(),
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
        if created_new_user:
            try:
                client.table("usuarios").delete().eq("user_id", user_id).execute()
                client.auth.admin.delete_user(user_id)
            finally:
                raise
        raise
    if created_new_user:
        print("Cuenta de plataforma creada.")
        print("En el primer acceso se exigirá configurar MFA.")
    else:
        print("Cuenta existente configurada como administración central A&M.")
        print("La contraseña y los factores MFA existentes se conservaron.")


if __name__ == "__main__":
    main()
