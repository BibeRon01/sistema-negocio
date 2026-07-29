# Subir AIS a Streamlit Community Cloud

## Antes de comenzar

- Suba **esta carpeta completa** a un repositorio privado de GitHub. `app.py`
  no funciona solo: necesita los módulos, `requirements.txt`, la imagen y la
  configuración incluidos aquí.
- No suba `.streamlit/secrets.toml`, archivos `.env`, respaldos ni llaves.
- Use `app.py` como archivo principal.

## Configuración del despliegue

1. En Streamlit Community Cloud, seleccione el repositorio privado y la rama.
2. En **Main file path**, escriba `app.py`.
3. Abra **Advanced settings** y seleccione **Python 3.12**.
4. En **Secrets**, pegue únicamente:

```toml
SUPABASE_URL = "https://SU-PROYECTO.supabase.co"
SUPABASE_KEY = "SU_LLAVE_PUBLISHABLE_O_ANON"
```

`SUPABASE_KEY` debe ser la llave **Publishable** (`sb_publishable_...`) o la
llave pública `anon` heredada. Nunca coloque `service_role`, `sb_secret_`, una
contraseña de base de datos ni una llave de respaldo.

## Comprobación inicial

Al abrir la aplicación debe aparecer el formulario con:

- Correo electrónico;
- Contraseña;
- recuperación de contraseña.

No introduzca operaciones reales hasta completar las pruebas de acceso, caja,
venta, inventario, crédito, nómina y contabilidad. Para administración, AIS
exigirá MFA.

Documentación oficial:

- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
