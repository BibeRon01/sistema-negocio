"""Importador privado, reanudable y exclusivo del tenant BIBE RON 01."""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
import streamlit as st

from api_client import (
    ApiError,
    importar_historial_biberon,
    prevalidar_migracion_biberon,
    validar_importacion_biberon,
)
from auth import es_admin
from db import obtener_tenant_actual


LOGGER = logging.getLogger("ais")
TENANT_BIBERON = "biberon01"
PAQUETE_AUTORIZADO = "biberon01-hasta-2026-08-15-v1"
CORTE_AUTORIZADO = "2026-08-15"
MAX_ARCHIVO_BYTES = 15 * 1024 * 1024
TAMANO_LOTE = 250

HOJAS_ENTIDADES = [
    ("PRODUCTOS", "productos"),
    ("CLIENTES", "clientes"),
    ("PROVEEDORES", "proveedores"),
    ("EMPLEADOS", "empleados"),
    ("VENTAS", "ventas"),
    ("VENTAS_PAGOS", "ventas_pagos"),
    ("CUENTAS_COBRAR", "cuentas_por_cobrar"),
    ("COMPRAS", "compras"),
    ("GASTOS", "gastos"),
    ("GASTOS_DUENO", "gastos_dueno"),
    ("PAGOS_EMPLEADOS", "pagos_empleados"),
    ("PERDIDAS", "perdidas"),
    ("VENTAS_PRODUCTO_HIST", "ventas_producto_historico"),
]


def _valor_json(value: Any) -> Any:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.date().isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _leer_control(blob: bytes) -> dict[str, Any]:
    control = pd.read_excel(
        io.BytesIO(blob), sheet_name="CONTROL", header=None, engine="openpyxl"
    )
    result: dict[str, Any] = {}
    for _, row in control.iloc[:10, :2].iterrows():
        key = str(row.iloc[0] or "").strip()
        if key and key.lower() != "nan":
            result[key] = _valor_json(row.iloc[1])
    return result


@st.cache_data(show_spinner=False)
def _leer_paquete(blob: bytes) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    if len(blob) > MAX_ARCHIVO_BYTES:
        raise ValueError("El archivo excede el tamaño permitido para este paquete.")

    control = _leer_control(blob)
    excel = pd.ExcelFile(io.BytesIO(blob), engine="openpyxl")
    requeridas = {"CONTROL", *(sheet for sheet, _ in HOJAS_ENTIDADES)}
    faltantes = sorted(requeridas.difference(excel.sheet_names))
    if faltantes:
        raise ValueError("Faltan hojas obligatorias en el paquete.")

    entities: dict[str, list[dict[str, Any]]] = {}
    for sheet_name, entity_name in HOJAS_ENTIDADES:
        frame = pd.read_excel(excel, sheet_name=sheet_name, engine="openpyxl")
        frame.columns = [str(column).strip() for column in frame.columns]
        if "source_key" not in frame.columns or "source_hash" not in frame.columns:
            raise ValueError(f"La hoja {sheet_name} no tiene trazabilidad de origen.")
        records: list[dict[str, Any]] = []
        for raw in frame.to_dict(orient="records"):
            record = {str(key): _valor_json(value) for key, value in raw.items()}
            if not str(record.get("source_key") or "").strip():
                continue
            if len(str(record.get("source_hash") or "")) != 64:
                raise ValueError(f"La hoja {sheet_name} contiene un hash inválido.")
            records.append(record)
        entities[entity_name] = records
    return control, entities


def _validar_paquete(control: dict[str, Any], entities: dict[str, list[dict[str, Any]]]) -> None:
    if str(control.get("Tenant obligatorio") or "").strip() != TENANT_BIBERON:
        raise ValueError("El paquete no pertenece a BIBE RON 01.")
    if str(control.get("Paquete") or "").strip() != PAQUETE_AUTORIZADO:
        raise ValueError("El identificador del paquete no es el autorizado.")
    cutoff = control.get("Corte")
    if str(cutoff or "")[:10] != CORTE_AUTORIZADO:
        raise ValueError("La fecha de corte del paquete no coincide.")
    for _, entity in HOJAS_ENTIDADES:
        records = entities.get(entity, [])
        if not records:
            raise ValueError(f"La entidad {entity} está vacía.")
        keys = [str(record.get("source_key") or "") for record in records]
        if len(keys) != len(set(keys)):
            raise ValueError(f"La entidad {entity} contiene claves repetidas.")
        for record in records:
            for date_field in ("fecha", "desde", "hasta", "fecha_agregado"):
                value = str(record.get(date_field) or "")[:10]
                if value and value > CORTE_AUTORIZADO:
                    raise ValueError("El paquete contiene fechas posteriores al corte.")


def _suma_decimal(records: list[dict[str, Any]], field: str) -> Decimal:
    return sum(
        (Decimal(str(record.get(field) or 0)) for record in records),
        Decimal("0"),
    ).quantize(Decimal("0.01"))


def _expectativas_paquete(entities: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    invoices: list[tuple[int, str]] = []
    for record in entities["ventas"]:
        invoice = str(record.get("numero_factura") or "")
        match = re.fullmatch(r"CFF-(\d+)", invoice)
        if match:
            invoices.append((int(match.group(1)), invoice))
    if not invoices:
        raise ValueError("El paquete no contiene facturas históricas válidas.")
    max_number, max_invoice = max(invoices)
    return {
        "entities": {entity: len(records) for entity, records in entities.items()},
        "sales_total": _suma_decimal(entities["ventas"], "total"),
        "payments_total": _suma_decimal(entities["ventas_pagos"], "monto"),
        "receivables_total": _suma_decimal(entities["cuentas_por_cobrar"], "saldo_pendiente"),
        "purchases_total": _suma_decimal(entities["compras"], "total"),
        "expenses_total": _suma_decimal(entities["gastos"], "monto"),
        "owner_expenses_total": _suma_decimal(entities["gastos_dueno"], "monto"),
        "payroll_total": _suma_decimal(entities["pagos_empleados"], "monto"),
        "losses_total": _suma_decimal(entities["perdidas"], "valor"),
        "max_historical_invoice": max_invoice,
        "next_historical_invoice": max_number + 1,
    }


def _resultado_correcto(
    result: dict[str, Any], entities: dict[str, list[dict[str, Any]]]
) -> bool:
    if str(result.get("tenant_id") or "") != TENANT_BIBERON:
        return False
    expected = _expectativas_paquete(entities)
    imported = result.get("entities") or {}
    for entity, count in expected["entities"].items():
        if int(imported.get(entity) or 0) != count:
            return False
    for field in (
        "sales_total", "payments_total", "receivables_total", "purchases_total",
        "expenses_total", "owner_expenses_total", "payroll_total", "losses_total",
    ):
        actual = Decimal(str(result.get(field) or 0)).quantize(Decimal("0.01"))
        if actual != expected[field]:
            return False
    return (
        str(result.get("max_historical_invoice") or "")
        == expected["max_historical_invoice"]
        and int(result.get("next_historical_invoice") or 0)
        == expected["next_historical_invoice"]
    )


def render_migracion_biberon() -> None:
    st.title("📥 Migración histórica BIBE RON 01")
    st.caption(
        "Importación privada, reanudable e idempotente. No altera la caja actual "
        "ni vuelve a descontar el inventario actual."
    )

    if obtener_tenant_actual() != TENANT_BIBERON or not es_admin():
        st.error("Este módulo solo está autorizado para el administrador de BIBE RON 01.")
        st.stop()

    try:
        preflight = prevalidar_migracion_biberon()
    except ApiError:
        st.error("No se pudo validar el destino de la migración.")
        st.stop()

    if not preflight.get("ready"):
        st.error(
            "BIBE RON 01 ya contiene movimientos no administrados por este paquete. "
            "No se importará nada hasta revisar esos registros."
        )
        st.metric("Movimientos que requieren revisión", int(preflight.get("unmanaged_business_rows") or 0))
        st.stop()

    if int(preflight.get("already_imported") or 0) > 0:
        st.info("Hay progreso previo. El proceso continuará sin duplicar las filas confirmadas.")

    uploaded = st.file_uploader(
        "Seleccione PAQUETE_MIGRACION_BIBERON01_HASTA_2026-08-15.xlsx",
        type=["xlsx"],
        key="paquete_migracion_biberon01",
    )
    if uploaded is None:
        st.stop()

    try:
        control, entities = _leer_paquete(uploaded.getvalue())
        _validar_paquete(control, entities)
    except (ValueError, KeyError, OSError):
        LOGGER.warning("Paquete de migración rechazado", exc_info=True)
        st.error("El archivo no coincide con el paquete auditado de BIBE RON 01.")
        st.stop()

    summary = pd.DataFrame(
        [
            {"Entidad": entity, "Filas": len(entities[entity])}
            for _, entity in HOJAS_ENTIDADES
        ]
    )
    st.success("Paquete verificado. Tenant, corte, hojas y conteos son correctos.")
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.warning(
        "Cierre las cajas abiertas y no registre ventas mientras se ejecuta la migración."
    )
    confirm = st.checkbox(
        "Confirmo que tengo respaldo y que este archivo corresponde únicamente a BIBE RON 01.",
        key="confirmar_migracion_biberon01",
    )

    if st.button(
        "Importar historial de BIBE RON 01",
        type="primary",
        disabled=not confirm,
        use_container_width=True,
    ):
        total_rows = sum(len(records) for records in entities.values())
        processed = 0
        progress = st.progress(0.0, text="Preparando importación…")
        status = st.empty()
        try:
            for _, entity in HOJAS_ENTIDADES:
                records = entities[entity]
                status.info(f"Importando {entity}…")
                for start in range(0, len(records), TAMANO_LOTE):
                    batch = records[start:start + TAMANO_LOTE]
                    importar_historial_biberon(
                        {
                            "tenant_id": TENANT_BIBERON,
                            "package_id": PAQUETE_AUTORIZADO,
                            "entity": entity,
                            "records": batch,
                        }
                    )
                    processed += len(batch)
                    progress.progress(
                        min(processed / total_rows, 1.0),
                        text=f"{processed:,} de {total_rows:,} filas verificadas",
                    )

            result = validar_importacion_biberon(PAQUETE_AUTORIZADO)
            if not _resultado_correcto(result, entities):
                st.error(
                    "La carga terminó, pero la conciliación final no coincide. "
                    "No continúe operando hasta revisar el resultado."
                )
                st.json(result)
                st.stop()

            st.session_state.pop("session_cache_tablas", None)
            status.success("Migración terminada y conciliada.")
            last_invoice = str(result.get("max_historical_invoice") or "")
            next_invoice = f"CFF-{int(result.get('next_historical_invoice') or 0):06d}"
            st.success(
                "BIBE RON 01 quedó cargada hasta la fecha de corte. "
                f"Última factura histórica: {last_invoice}; siguiente: {next_invoice}."
            )
            st.json(result)
        except ApiError:
            LOGGER.error("La migración de BIBE RON se detuvo", exc_info=True)
            st.error(
                "La importación se detuvo de forma segura. Corrija la causa e intente "
                "de nuevo; las filas ya confirmadas no se duplicarán."
            )
