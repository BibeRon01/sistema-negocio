# Modularized view for A&M ERP v2
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit.components.v1 as components
from datetime import datetime, date, timedelta
from typing import Any

try:
    try:
        from core.db import *
    except ModuleNotFoundError:
        from db import *
    try:
        from core.auth import *
    except ModuleNotFoundError:
        from auth import *
    try:
        from core.utils import *
    except ModuleNotFoundError:
        from utils import *
    try:
        from core.helpers import *
    except ModuleNotFoundError:
        from helpers import *
except ModuleNotFoundError:
    from db import *
    from auth import *
    from utils import *
    from helpers import *

def render_gestion_empresas():
    if obtener_tenant_actual() != "global":
        st.error("🔒 Acceso denegado. Solo el Super-Admin puede acceder a este panel.")
        st.stop()

    st.markdown("""
<style>
.emp-kpi{background:linear-gradient(135deg,#0d0d0d,#1a1a2e);border:1px solid rgba(212,175,55,0.3);border-radius:16px;padding:20px 18px;text-align:center;margin-bottom:10px;}
.emp-kpi .emp-kpi-label{font-size:11px;font-weight:700;letter-spacing:2px;color:#d4af37;text-transform:uppercase;}
.emp-kpi .emp-kpi-val{font-size:28px;font-weight:900;color:#fff;margin:6px 0 2px 0;}
.emp-kpi .emp-kpi-sub{font-size:12px;color:#9ca3af;}
</style>
""", unsafe_allow_html=True)

    st.markdown("""
<div style='background:linear-gradient(135deg,#13783b,#0a5a2b);border-radius:16px;padding:20px 24px;margin-bottom:18px;'>
<h2 style='color:#fff;margin:0;font-size:26px;'>🏢 Gestión de Empresas</h2>
<p style='color:#a7f3d0;margin:4px 0 0 0;font-size:14px;'>Panel exclusivo Super-Admin &middot; Control total del ecosistema A&amp;M</p>
</div>
""", unsafe_allow_html=True)

    try:
        todas_cfg = supabase.table("configuracion_sistema").select("*").execute().data or []
    except Exception:
        todas_cfg = []

    # Organizar el panel de control exclusivo en pestañas elegantes
    tab_dashboard, tab_planes, tab_kpi, tab_licencias, tab_config = st.tabs([
        "📊 Dashboard A&M", "📋 Planes de Servicio", "🏢 Resumen Ecosistema",
        "💳 Licencias y Cobros", "🛠️ Configurar Empresas y Usuarios"
    ])

    # ── Cargar historial de suscripciones para el dashboard ───────────────
    try:
        todas_subs = supabase.table("suscripciones_empresas").select("*").order("created_at", desc=True).execute().data or []
    except Exception:
        todas_subs = []

    hoy_am = datetime.now().date()

    # ── TAB 1: DASHBOARD FINANCIERO A&M ─────────────────────────────────
    with tab_dashboard:
        st.markdown("""
<style>
.am-kpi{background:linear-gradient(135deg,#0d0d0d,#111827);border:1px solid rgba(16,185,129,0.25);border-radius:16px;padding:22px 18px;text-align:center;margin-bottom:12px;}
.am-kpi .am-label{font-size:10px;font-weight:700;letter-spacing:2px;color:#10b981;text-transform:uppercase;margin-bottom:4px;}
.am-kpi .am-val{font-size:30px;font-weight:900;color:#fff;margin:4px 0;}
.am-kpi .am-sub{font-size:11px;color:#9ca3af;}
.plan-card{background:linear-gradient(135deg,#111827,#1f2937);border-radius:14px;padding:18px 16px;margin-bottom:8px;border-left:4px solid;}
</style>
""", unsafe_allow_html=True)

        st.markdown("### 💼 Dashboard Financiero A&M — Ingresos de Licencias")

        # KPIs financieros
        empresas_activas = 0
        empresas_suspendidas = 0
        mrr = 0.0
        arr = 0.0
        ingresos_totales = sum(float(s.get("monto_pagado") or 0) for s in todas_subs)
        cobros_proximos_30 = []

        for cfg_e in todas_cfg:
            prop = cfg_e.get("propietario") or "global"
            if prop == "global":
                continue
            subs_e = [s for s in todas_subs if s.get("empresa_id") == prop]
            if subs_e:
                ultima = max(subs_e, key=lambda s: s.get("fecha_vencimiento") or "")
                fv_str = ultima.get("fecha_vencimiento")
                dg = int(ultima.get("dias_gracia") or 5)
                if fv_str:
                    fv = datetime.strptime(fv_str, "%Y-%m-%d").date()
                    dias_rest = (fv - hoy_am).days
                    if dias_rest + dg >= 0:
                        empresas_activas += 1
                    else:
                        empresas_suspendidas += 1

                    # Proyección de cobros próximos 30 días
                    if -5 <= dias_rest <= 30:
                        plan_id = cfg_e.get("plan") or "premium"
                        plan_info = PLANES_AM.get(plan_id, PLANES_AM["premium"])
                        cobros_proximos_30.append({
                            "Empresa": (cfg_e.get("negocio_nombre") or prop).upper(),
                            "Plan": plan_info["emoji"] + " " + plan_info["nombre"],
                            "Vence": fv.strftime("%d/%m/%Y"),
                            "Días": dias_rest,
                            "Estimado (RD$)": f"RD$ {plan_info['precio_mensual']:,.0f}",
                            "Estado": "⚠️ Período gracia" if dias_rest < 0 else ("🔴 Hoy!" if dias_rest == 0 else f"📅 {dias_rest}d"),
                        })

                    # MRR desde plan asignado
                    plan_id = cfg_e.get("plan") or "premium"
                    plan_info = PLANES_AM.get(plan_id, PLANES_AM["premium"])
                    mrr += plan_info["precio_mensual"]

        arr = mrr * 12

        k1, k2, k3, k4, k5 = st.columns(5)
        def _am_kpi(col, label, val, sub=""):
            col.markdown(f"<div class='am-kpi'><div class='am-label'>{label}</div><div class='am-val'>{val}</div><div class='am-sub'>{sub}</div></div>", unsafe_allow_html=True)

        _am_kpi(k1, "Empresas Activas", empresas_activas, "con licencia vigente")
        _am_kpi(k2, "Suspendidas", empresas_suspendidas, "licencia vencida")
        _am_kpi(k3, "MRR", f"RD$ {mrr:,.0f}", "ingreso mensual recurrente")
        _am_kpi(k4, "ARR", f"RD$ {arr:,.0f}", "ingreso anual proyectado")
        _am_kpi(k5, "Total Cobrado", f"RD$ {ingresos_totales:,.0f}", "desde el inicio")

        st.markdown("---")
        st.markdown("#### 📅 Cobros Proyectados — Próximos 30 Días")
        if cobros_proximos_30:
            df_proj = pd.DataFrame(cobros_proximos_30).sort_values("Días")
            st.dataframe(df_proj, use_container_width=True)
        else:
            st.info("No hay cobros pendientes en los próximos 30 días.")

        st.markdown("---")
        st.markdown("#### 📊 Distribución de Planes por Empresa")
        plan_counts = {}
        for cfg_e in todas_cfg:
            prop = cfg_e.get("propietario")
            if prop == "global":
                continue
            plan_id = cfg_e.get("plan") or "premium"
            plan_info = PLANES_AM.get(plan_id, PLANES_AM["premium"])
            lbl = f"{plan_info['emoji']} {plan_info['nombre']}"
            plan_counts[lbl] = plan_counts.get(lbl, 0) + 1
        if plan_counts:
            rows_pc = [{"Plan": k, "Empresas": v, "MRR (RD$)": v * PLANES_AM.get(k.split(" ",1)[1].lower() if " " in k else "premium", PLANES_AM["premium"])["precio_mensual"]}
                       for k, v in plan_counts.items()]
            st.dataframe(pd.DataFrame(rows_pc), use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🧾 Historial Completo de Cobros")
        if todas_subs:
            rows_h = []
            for s in todas_subs:
                rows_h.append({
                    "Empresa": (s.get("empresa_id") or "").upper(),
                    "Período": s.get("periodo"),
                    "Fecha Pago": s.get("fecha_inicio"),
                    "Vencimiento": s.get("fecha_vencimiento"),
                    "Monto": f"RD$ {float(s.get('monto_pagado') or 0):,.2f}",
                    "Método": (s.get("metodo_pago") or "").upper(),
                    "Obs.": s.get("observacion") or "",
                })
            st.dataframe(pd.DataFrame(rows_h), use_container_width=True)
        else:
            st.info("No hay cobros registrados aún.")

    # ── TAB 2: PLANES DE SERVICIO ────────────────────────────────────────
    with tab_planes:
        st.markdown("### 📋 Planes de Servicio A&M")
        st.caption("Define qué plan tiene cada empresa. El plan determina los módulos y usuarios disponibles.")

        # Mostrar tarjetas de planes
        cols_plan = st.columns(4)
        for idx, (plan_key, plan_info) in enumerate(PLANES_AM.items()):
            with cols_plan[idx]:
                modulos_txt = ", ".join(plan_info["modulos"][:5]) + "..." if plan_info["modulos"] else "Todo incluido"
                precio_txt = f"RD$ {plan_info['precio_mensual']:,.0f}/mes" if plan_info["precio_mensual"] > 0 else "Gratis"
                st.markdown(f"""
<div style='background:linear-gradient(135deg,#111827,#1f2937);border:2px solid {plan_info["color"]};border-radius:14px;padding:16px;text-align:center;'>
  <div style='font-size:28px;'>{plan_info["emoji"]}</div>
  <div style='font-size:16px;font-weight:800;color:{plan_info["color"]};margin:4px 0;'>{plan_info["nombre"]}</div>
  <div style='font-size:20px;font-weight:900;color:#fff;'>{precio_txt}</div>
  <div style='font-size:11px;color:#9ca3af;margin-top:6px;'>{plan_info["descripcion"]}</div>
  <div style='margin-top:8px;font-size:10px;color:#6b7280;'>👥 Hasta {plan_info["max_usuarios"]} usuario(s)</div>
</div>
""", unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("🏢 Asignar Plan a Empresa")

        empresas_lista = [e for e in todas_cfg if e.get("propietario") != "global"]
        if not empresas_lista:
            st.info("No hay empresas registradas.")
        else:
            emp_opts_plan = [f"{e.get('negocio_nombre') or e.get('propietario')} [{e.get('propietario')}]" for e in empresas_lista]
            sel_emp_plan = st.selectbox("Seleccionar Empresa", range(len(emp_opts_plan)), format_func=lambda i: emp_opts_plan[i], key="plan_sel_emp")
            if sel_emp_plan is not None and sel_emp_plan < len(empresas_lista):
                emp_cfg_plan = empresas_lista[sel_emp_plan]
                plan_actual_id = emp_cfg_plan.get("plan") or "premium"
                plan_actual_info = PLANES_AM.get(plan_actual_id, PLANES_AM["premium"])

            st.info(f"**Plan actual:** {plan_actual_info['emoji']} {plan_actual_info['nombre']} — RD$ {plan_actual_info['precio_mensual']:,.0f}/mes")

            nuevo_plan = st.selectbox(
                "Cambiar a Plan:",
                list(PLANES_AM.keys()),
                format_func=lambda k: f"{PLANES_AM[k]['emoji']} {PLANES_AM[k]['nombre']} — RD$ {PLANES_AM[k]['precio_mensual']:,.0f}/mes",
                index=list(PLANES_AM.keys()).index(plan_actual_id) if plan_actual_id in PLANES_AM else 2,
                key="plan_nuevo_sel"
            )

            # Mostrar diferencia de módulos
            plan_nuevo_info = PLANES_AM[nuevo_plan]
            if nuevo_plan != plan_actual_id:
                if plan_nuevo_info["modulos"] is None:
                    st.success("✅ Plan Enterprise: Acceso a **todos** los módulos del sistema.")
                else:
                    modulos_actuales = set(plan_actual_info["modulos"] or [])
                    modulos_nuevos = set(plan_nuevo_info["modulos"] or [])
                    ganados = modulos_nuevos - modulos_actuales
                    perdidos = modulos_actuales - modulos_nuevos
                    if ganados:
                        st.success(f"✅ **Módulos que se añaden:** {', '.join(sorted(ganados))}")
                    if perdidos:
                        st.warning(f"⚠️ **Módulos que se pierden:** {', '.join(sorted(perdidos))}")

            if st.button("💾 Aplicar Plan a esta Empresa", key="btn_aplicar_plan", type="primary"):
                try:
                    supabase.table("configuracion_sistema").update({
                        "plan": nuevo_plan
                    }).eq("propietario", emp_cfg_plan["propietario"]).execute()
                    _obtener_configuracion_interna.clear()
                    st.success(f"✅ Plan '{plan_nuevo_info['nombre']}' asignado correctamente a '{emp_cfg_plan.get('negocio_nombre')}'.")
                    st.rerun()
                except Exception as exc_plan:
                    st.error(f"Error al asignar plan: {exc_plan}")

            st.markdown("---")
            st.subheader("📋 Resumen de Planes Asignados")
            rows_emp_plan = []
            for cfg_e in todas_cfg:
                prop = cfg_e.get("propietario")
                if prop == "global":
                    continue
                pid = cfg_e.get("plan") or "premium"
                pi = PLANES_AM.get(pid, PLANES_AM["premium"])
                # Estado licencia
                subs_e = [s for s in todas_subs if s.get("empresa_id") == prop]
                if subs_e:
                    ultima_e = max(subs_e, key=lambda s: s.get("fecha_vencimiento") or "")
                    fv_e = datetime.strptime(ultima_e["fecha_vencimiento"], "%Y-%m-%d").date()
                    dias_e = (fv_e - hoy_am).days
                    estado_e = "🟢 Activa" if dias_e > 5 else ("⚠️ Vence pronto" if dias_e >= 0 else "🔴 Vencida")
                else:
                    estado_e = "❓ Sin licencia"

                rows_emp_plan.append({
                    "Empresa": (cfg_e.get("negocio_nombre") or prop).upper(),
                    "ID": prop,
                    "Plan": f"{pi['emoji']} {pi['nombre']}",
                    "Precio/mes": f"RD$ {pi['precio_mensual']:,.0f}",
                    "Usuarios máx.": pi["max_usuarios"],
                    "Estado": estado_e,
                })
            if rows_emp_plan:
                st.dataframe(pd.DataFrame(rows_emp_plan), use_container_width=True)



    with tab_kpi:
        total_empresas = len(todas_cfg)
        st.markdown(f"### 📋 Empresas registradas ({total_empresas})")

        if not todas_cfg:
            st.info("No hay empresas registradas aún.")
        else:
            cols_emp = st.columns(min(total_empresas, 4))
            for i, cfg_e in enumerate(todas_cfg):
                prop = cfg_e.get("propietario") or "global"
                nombre_e = cfg_e.get("negocio_nombre") or prop.capitalize()
                slogan_e = cfg_e.get("slogan") or ""
                
                # Determinar si está suspendida revisando slogan o la tabla de suscripciones
                es_susp = False
                try:
                    resp_l = supabase.table("suscripciones_empresas").select("*").eq("empresa_id", prop).order("fecha_vencimiento", desc=True).limit(1).execute()
                    if resp_l.data:
                        fv = datetime.strptime(resp_l.data[0]["fecha_vencimiento"], "%Y-%m-%d").date()
                        h = datetime.now().date()
                        dg = int(resp_l.data[0].get("dias_gracia") or 5)
                        if (fv - h).days + dg < 0:
                            es_susp = True
                except Exception:
                    pass
                
                if "[SUSPENDIDO]" in slogan_e:
                    es_susp = True
                
                status_tag = " <span style='color:#ff4b4b;font-weight:bold;font-size:9px;'>[SUSPENDIDA]</span>" if es_susp else " <span style='color:#09ab3b;font-weight:bold;font-size:9px;'>[ACTIVA]</span>"
                
                try:
                    v_resp = supabase.table("ventas").select("total").eq("empresa_id", prop).execute()
                    ventas_data = v_resp.data or []
                    total_ventas_e = sum(float(r.get("total") or 0) for r in ventas_data)
                    n_ventas = len(ventas_data)
                except Exception:
                    total_ventas_e = 0.0
                    n_ventas = 0
                    
                with cols_emp[i % 4]:
                    st.markdown(f"""
<div class='emp-kpi'>
<div class='emp-kpi-label'>{nombre_e}{status_tag}</div>
<div class='emp-kpi-val'>{n_ventas}</div>
<div class='emp-kpi-sub'>ventas &middot; RD$ {total_ventas_e:,.2f}</div>
<div style='margin-top:8px;font-size:10px;color:#6b7280;font-weight:600;'>{prop}</div>
</div>
""", unsafe_allow_html=True)

    with tab_licencias:
        st.subheader("💳 Control y Registro de Licencias y Cobros")
        
        # 1. Registrar Nuevo Pago
        st.markdown("#### ➕ Registrar Pago / Suscripción de Licencia")
        c1, c2, c3 = st.columns(3)
        with c1:
            opciones_emp_list = [e.get("propietario") for e in todas_cfg if e.get("propietario") != "global"]
            emp_cobrar = st.selectbox("Seleccione la Empresa:", opciones_emp_list, key="lic_emp_cobrar")
            fecha_ini = st.date_input("Fecha de Pago/Inicio:", value=datetime.now().date(), key="lic_fecha_ini")
        with c2:
            meses_sel = st.selectbox("Meses Contratados:", list(range(1, 13)), index=0, key="lic_meses")
            periodo_sel = f"{meses_sel} mes" if meses_sel == 1 else f"{meses_sel} meses"
            
            metodo_cobro = st.selectbox("Método de Pago:", ["Transferencia", "Efectivo", "Tarjeta", "Mixto"], key="lic_metodo")
        with c3:
            obs_cobro = st.text_input("Observación:", placeholder="Pago completo / Descuento especial", key="lic_obs")
            
        # Interfaz de cobro mixto dinámica
        if metodo_cobro == "Mixto":
            st.markdown("##### 💰 Desglose de Pago Mixto")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                monto_efectivo = st.number_input("Monto en Efectivo (RD$):", min_value=0.0, step=100.0, value=0.0, key="lic_monto_efectivo")
            with col_m2:
                monto_banco = st.number_input("Monto en Transf / Tarjeta (RD$):", min_value=0.0, step=100.0, value=1500.0, key="lic_monto_banco")
            monto_cobrado = monto_efectivo + monto_banco
            st.info(f"💰 **Total Cobrado (Mixto)**: RD$ {monto_cobrado:,.2f}")
        else:
            monto_cobrado = st.number_input("Monto Cobrado (RD$):", min_value=0.0, step=100.0, value=1500.0, key="lic_monto")
            
        if st.button("💳 Registrar Cobro y Activar Licencia", key="btn_registrar_cobro", use_container_width=True):
            if not emp_cobrar:
                st.error("Por favor seleccione una empresa válida.")
            else:
                try:
                    # Calcular fecha de vencimiento usando calendario exacto
                    import calendar
                    meses_sumar = meses_sel
                        
                    month = fecha_ini.month - 1 + meses_sumar
                    year = fecha_ini.year + month // 12
                    month = month % 12 + 1
                    day = min(fecha_ini.day, calendar.monthrange(year, month)[1])
                    fecha_venc = date(year, month, day)
                    
                    # Formatear la observación del pago mixto
                    obs_final = obs_cobro
                    if metodo_cobro == "Mixto":
                        desglose = f"[PAGO MIXTO] Efectivo: RD$ {monto_efectivo:,.2f} | Banco: RD$ {monto_banco:,.2f}"
                        obs_final = f"{desglose}. {obs_cobro}" if obs_cobro else desglose
                    
                    # Insertar en public.suscripciones_empresas
                    supabase.table("suscripciones_empresas").insert({
                        "empresa_id": emp_cobrar,
                        "fecha_inicio": str(fecha_ini),
                        "fecha_vencimiento": str(fecha_venc),
                        "monto_pagado": float(monto_cobrado),
                        "periodo": periodo_sel,
                        "metodo_pago": metodo_cobro.lower(),
                        "dias_gracia": 5,
                        "observacion": obs_final
                    }).execute()
                    
                    # Reactivar automáticamente la empresa en configuracion_sistema quitando [SUSPENDIDO]
                    cfg_emp = next((e for e in todas_cfg if e.get("propietario") == emp_cobrar), None)
                    if cfg_emp:
                        slogan_act = str(cfg_emp.get("slogan") or "")
                        slogan_new = slogan_act.replace("[SUSPENDIDO]", "").strip()
                        supabase.table("configuracion_sistema").update({
                            "slogan": slogan_new
                        }).eq("propietario", emp_cobrar).execute()
                    
                    # Limpiar caché e informar éxito
                    _obtener_configuracion_interna.clear()
                    st.success(f"🎉 Licencia registrada con éxito para '{emp_cobrar}'. Vence el {fecha_venc.strftime('%d/%m/%Y')} (más 5 días de gracia).")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error al registrar cobro: {exc}")
                    
        st.markdown("---")
        st.markdown("#### 📋 Historial de Pagos y Estado de Licencias")
        
        # Cargar licencias registradas
        try:
            resp_subs = supabase.table("suscripciones_empresas").select("*").order("created_at", desc=True).execute()
            subs_data = resp_subs.data or []
        except Exception:
            subs_data = []
            
        if not subs_data:
            st.info("No hay pagos de suscripción registrados aún.")
        else:
            rows_lic = []
            hoy = datetime.now().date()
            for row in subs_data:
                emp = row.get("empresa_id")
                ini = datetime.strptime(row.get("fecha_inicio"), "%Y-%m-%d").date()
                venc = datetime.strptime(row.get("fecha_vencimiento"), "%Y-%m-%d").date()
                dg = int(row.get("dias_gracia") or 5)
                monto = float(row.get("monto_pagado") or 0.0)
                per = row.get("periodo")
                met = row.get("metodo_pago")
                
                dias_rest = (venc - hoy).days
                
                # Calcular estado dinámico
                if dias_rest + dg < 0:
                    status_text = "🔴 Suspendida (Excedió gracia)"
                elif dias_rest < 0:
                    status_text = f"🟠 Período Gracia ({dg + dias_rest} días)"
                elif dias_rest <= 5:
                    status_text = f"⚠️ Vence Pronto ({dias_rest} días)"
                else:
                    status_text = f"🟢 Al corriente ({dias_rest} días)"
                    
                rows_lic.append({
                    "Empresa": emp.upper(),
                    "Fecha Pago": ini.strftime("%d/%m/%Y"),
                    "Vence El": venc.strftime("%d/%m/%Y"),
                    "Días Restantes": dias_rest,
                    "Estado Licencia": status_text,
                    "Monto Cobrado": f"RD$ {monto:,.2f}",
                    "Período": per,
                    "Método": met.upper()
                })
            st.dataframe(pd.DataFrame(rows_lic), use_container_width=True)

            # Expandible para gestionar/eliminar pagos registrados
            with st.expander("🛠️ Editar / Eliminar pagos de licencias", expanded=False):
                if not subs_data:
                    st.info("No hay pagos para gestionar.")
                else:
                    opciones_c = []
                    mapa_c = {}
                    for row in subs_data:
                        c_id = row.get("id")
                        c_emp = row.get("empresa_id", "").upper()
                        c_ini = row.get("fecha_inicio")
                        c_monto = float(row.get("monto_pagado") or 0.0)
                        etiq = f"ID: {c_id} | {c_emp} | Fecha: {c_ini} | Monto: RD$ {c_monto:,.2f}"
                        opciones_c.append(etiq)
                        mapa_c[etiq] = row
                    
                    sel_pago_etiq = st.selectbox("Seleccione el pago a corregir o eliminar", opciones_c, key="sel_pago_gestionar")
                    pago_sel = mapa_c[sel_pago_etiq]
                    pago_id = pago_sel.get("id")
                    
                    # Campos editables
                    new_monto = st.number_input("Monto pagado", value=float(pago_sel.get("monto_pagado") or 0.0), step=100.0, key=f"edit_monto_pago_{pago_id}")
                    new_venc = st.date_input("Fecha de vencimiento", value=datetime.strptime(pago_sel.get("fecha_vencimiento"), "%Y-%m-%d").date(), key=f"edit_venc_pago_{pago_id}")
                    new_obs = st.text_area("Observación", value=pago_sel.get("observacion") or "", key=f"edit_obs_pago_{pago_id}")
                    
                    c1g, c2g = st.columns(2)
                    with c1g:
                        if st.button("💾 Guardar Cambios en Pago", key=f"btn_save_pago_{pago_id}"):
                            try:
                                supabase.table("suscripciones_empresas").update({
                                    "monto_pagado": float(new_monto),
                                    "fecha_vencimiento": str(new_venc),
                                    "observacion": new_obs
                                }).eq("id", pago_id).execute()
                                _obtener_configuracion_interna.clear()
                                st.success("🎉 Pago de licencia actualizado con éxito.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Error al actualizar el pago: {exc}")
                    with c2g:
                        if st.button("🗑️ Eliminar Registro de Pago", key=f"btn_del_pago_{pago_id}"):
                            try:
                                supabase.table("suscripciones_empresas").delete().eq("id", pago_id).execute()
                                _obtener_configuracion_interna.clear()
                                st.success("🗑️ Registro de pago eliminado correctamente.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Error al eliminar el pago: {exc}")

    with tab_config:
        st.subheader("🛠️ Configuración de Empresas y Usuarios")
        with st.expander("📊 Ver tabla completa de empresas", expanded=False):
            df_empresas = pd.DataFrame(todas_cfg)
            if not df_empresas.empty:
                cols_mostrar = [c for c in ["propietario","negocio_nombre","nombre_sistema","telefono","rnc","direccion"] if c in df_empresas.columns]
                st.dataframe(df_empresas[cols_mostrar], use_container_width=True)
            else:
                st.info("No hay empresas registradas aún.")

        st.markdown("---")
        st.subheader("✏️ Editar empresa existente")
        if not todas_cfg:
            st.info("No hay empresas registradas para editar.")
        else:
            nombres_emp = [f"{e.get('negocio_nombre') or e.get('propietario')} [{e.get('propietario')}]" for e in todas_cfg]
            sel_emp_idx = st.selectbox("Seleccionar empresa", range(len(nombres_emp)), format_func=lambda i: nombres_emp[i], key="sel_edit_emp")
            if sel_emp_idx is not None and sel_emp_idx < len(todas_cfg):
                cfg_sel = todas_cfg[sel_emp_idx]
                
                actual_slogan = str(cfg_sel.get("slogan") or "")
                es_suspendida = "[SUSPENDIDO]" in actual_slogan
                slogan_limpio = actual_slogan.replace("[SUSPENDIDO]", "").strip()
                
                c1e, c2e = st.columns(2)
                with c1e:
                    edit_nombre = st.text_input("Nombre del negocio", value=str(cfg_sel.get("negocio_nombre") or ""), key="edit_emp_nombre_neg")
                    edit_sistema = st.text_input("Nombre del sistema", value=str(cfg_sel.get("nombre_sistema") or ""), key="edit_emp_nom_sis")
                    edit_tel = st.text_input("Teléfono", value=str(cfg_sel.get("telefono") or ""), key="edit_emp_tel")
                with c2e:
                    edit_rnc = st.text_input("RNC", value=str(cfg_sel.get("rnc") or ""), key="edit_emp_rnc")
                    edit_dir = st.text_input("Dirección", value=str(cfg_sel.get("direccion") or ""), key="edit_emp_dir")
                    edit_slogan = st.text_input("Slogan (Lema)", value=slogan_limpio, key="edit_emp_slogan")
                    
                st.markdown("**🔒 Suscripción y Licencia**")
                estado_licencia = st.selectbox("Estado de la Suscripción", ["Activa (Funcionamiento Normal)", "Suspendida (Bloqueo de Acceso)"], index=1 if es_suspendida else 0, key="edit_emp_estado_lic")
                
                if st.button("💾 Guardar cambios empresa", key="btn_guardar_emp_edit"):
                    try:
                        # Calcular slogan final aplicando el bloqueo si corresponde
                        slogan_final = edit_slogan
                        if "Suspendida" in estado_licencia:
                            slogan_final = f"[SUSPENDIDO] {slogan_final}".strip()
                        else:
                            slogan_final = slogan_final.replace("[SUSPENDIDO]", "").strip()
                            
                        supabase.table("configuracion_sistema").update({
                            "negocio_nombre": edit_nombre, "nombre_sistema": edit_sistema,
                            "telefono": edit_tel, "rnc": edit_rnc, "direccion": edit_dir, "slogan": slogan_final
                        }).eq("id", cfg_sel["id"]).execute()
                        _obtener_configuracion_interna.clear()
                        st.success(f"✅ Empresa '{edit_nombre}' actualizada.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Error: {exc}")

        # Check if the company has any user accounts and show helper to create one
        try:
            emp_usrs_data = supabase.table("usuarios").select("id").eq("email", cfg_sel["propietario"]).execute().data or []
            if not emp_usrs_data:
                st.info(f"💡 **Nota:** Esta empresa aún no tiene ningún usuario registrado. Puedes crearle su primer usuario administrador en la sección **Crear usuario/administrador** más abajo, o usar el siguiente acceso rápido:")
                with st.expander("👤 Crear primer usuario administrador para esta empresa", expanded=False):
                    cr_usr_user = st.text_input("Usuario de Acceso:", placeholder="ej. biberon_admin", key=f"quick_usr_{cfg_sel['propietario']}")
                    cr_usr_name = st.text_input("Nombre Completo:", placeholder="ej. Administrador", key=f"quick_name_{cfg_sel['propietario']}")
                    cr_usr_pass = st.text_input("Clave / Contraseña:", placeholder="ej. 123456", key=f"quick_pass_{cfg_sel['propietario']}")
                    if st.button("🚀 Crear Usuario Administrador", key=f"quick_btn_{cfg_sel['propietario']}", use_container_width=True):
                        user_clean = cr_usr_user.strip().lower()
                        name_clean = cr_usr_name.strip()
                        pass_clean = cr_usr_pass.strip()
                        if not user_clean or not pass_clean or not name_clean:
                            st.error("Todos los campos son obligatorios.")
                        else:
                            # Validar si ya existe ese nombre de usuario
                            user_exist = supabase.table("usuarios").select("*").eq("usuario", user_clean).execute().data
                            if user_exist:
                                st.error(f"Ya existe un usuario con el nombre '{user_clean}'.")
                            else:
                                new_user_payload = {
                                    "usuario": user_clean,
                                    "nombre": name_clean,
                                    "clave": hashear_clave(pass_clean),
                                    "rol": "admin",
                                    "activo": True,
                                    "email": cfg_sel["propietario"],
                                    "puede_vender": True,
                                    "puede_ver_reportes": True,
                                    "puede_configurar": True,
                                    "puede_registrar_compras": True,
                                    "puede_registrar_gastos": True,
                                    "puede_editar_ventas": True,
                                    "puede_eliminar": True,
                                    "puede_anular": True
                                }
                                try:
                                    supabase.table("usuarios").insert(new_user_payload).execute()
                                    st.success(f"🎉 ¡Usuario '{user_clean}' creado con éxito para '{cfg_sel.get('negocio_nombre')}'!")
                                    st.rerun()
                                except Exception as exc:
                                    exc_str = str(exc)
                                    if "23505" in exc_str or "unique constraint" in exc_str.lower():
                                        st.error(f"⚠️ El nombre de usuario '{user_clean}' ya está registrado. Por favor, elige uno diferente.")
                                    else:
                                        st.error(f"Error al crear cuenta: {exc}")
        except Exception as exc_usr_chk:
            pass

        st.markdown("---")
        st.markdown("**⚠️ Zona de Peligro**")
        with st.expander("🗑️ Eliminar esta Empresa y Todos sus Datos", expanded=False):
            prop_val = str(cfg_sel.get("propietario") or "").strip()
            st.warning(f"¿Está seguro de que desea eliminar la empresa '{cfg_sel.get('negocio_nombre') or prop_val}'? Esto eliminará la empresa, todos sus usuarios asociados, y sus licencias permanentemente de la base de datos. Esta acción no se puede deshacer.")
            confirm_text = st.text_input("Para confirmar la eliminación, escriba el ID único de la empresa a continuación:", placeholder=prop_val if prop_val else "vacío", key="delete_emp_confirm_id")
            
            if st.button("🚨 Eliminar Empresa Permanentemente", key="btn_eliminar_emp_definitivo", use_container_width=True):
                if confirm_text.strip().lower() == prop_val.lower():
                    try:
                        # 1. Eliminar usuarios asociados a la empresa (campo email = propietario)
                        if prop_val:
                            supabase.table("usuarios").delete().eq("email", prop_val).execute()
                            try:
                                supabase.table("suscripciones_empresas").delete().eq("empresa_id", prop_val).execute()
                            except Exception:
                                pass
                        # 2. Eliminar la configuración de la empresa (tabla configuracion_sistema)
                        supabase.table("configuracion_sistema").delete().eq("id", cfg_sel["id"]).execute()
                        
                        _obtener_configuracion_interna.clear()
                        st.success(f"🗑️ Empresa '{cfg_sel.get('negocio_nombre') or prop_val}' y sus datos asociados han sido eliminados.")
                        st.rerun()
                    except Exception as exc_del:
                        st.error(f"Error al eliminar la empresa: {exc_del}")
                else:
                    st.error("El ID de confirmación no coincide con el ID de la empresa.")
        with st.expander("🔥 Borrado Total del Sistema (Reset de Fábrica)", expanded=False):
            st.error("🚨 ¡ATENCIÓN! Esta acción eliminará permanentemente todos los datos operativos de todas las empresas en la base de datos (Ventas, Compras, Caja, Gastos, Empleados, Insumos, Pérdidas, etc.).")
            st.warning("Se mantendrá únicamente el usuario super-administrador actual 'nelly' para que puedas seguir gestionando el sistema.")
            confirm_reset_code = st.text_input("Para proceder, escribe 'RESET_TOTAL' a continuación:", placeholder="escribe RESET_TOTAL", key="confirm_reset_total_code")
            if st.button("🚨 EJECUTAR RESET DE FÁBRICA", key="btn_reset_fabrica_ejecutar", use_container_width=True):
                if confirm_reset_code.strip() == "RESET_TOTAL":
                    with st.spinner("Borrando base de datos..."):
                        tablas_limpiar = [
                            "ventas", "detalle_venta", "caja", "productos", "clientes", "proveedores",
                            "compras", "gastos", "empleados", "pagos_empleados", "perdidas",
                            "gastos_dueno", "activos_fijos", "capital_base", "cuentas_por_cobrar",
                            "abonos_credito", "distribucion_beneficios", "ventas_pagos",
                            "inventario_actual", "ajustes_inventario", "conteo_inventario",
                            "suscripciones_empresas", "secuencia_ncf"
                        ]
                        for tabla in tablas_limpiar:
                            try:
                                supabase.table(tabla).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
                            except Exception:
                                pass
                            try:
                                supabase.table(tabla).delete().neq("id", -1).execute()
                            except Exception:
                                pass
                        
                        try:
                            supabase.table("usuarios").delete().neq("usuario", "nelly").neq("usuario", "admin").execute()
                        except Exception:
                            pass
                        
                        try:
                            supabase.table("configuracion_sistema").delete().neq("id", 1).execute()
                            supabase.table("configuracion_sistema").update({
                                "negocio_nombre": "A&M ERP Financiero",
                                "nombre_sistema": "SISTEMA CONTABLE A&M",
                                "propietario": "global",
                                "slogan": "Tema: Onyx Carbon (Dark Mode Premium)"
                            }).eq("id", 1).execute()
                        except Exception:
                            pass
                            
                        _obtener_configuracion_interna.clear()
                        st.success("🔥 ¡El sistema ha sido restablecido a fábrica con éxito!")
                        st.rerun()
                else:
                    st.error("Código de confirmación incorrecto.")

        st.markdown("---")
        st.subheader("👥 Usuarios por empresa")
        emp_sel_usr = st.selectbox("Ver usuarios de:", ["TODAS"] + [e.get("propietario","?") for e in todas_cfg], key="sel_emp_usr")
        try:
            # Seleccionamos también la clave para que la Super-Admin pueda verla
            if emp_sel_usr == "TODAS":
                usr_resp = supabase.table("usuarios").select("id,usuario,nombre,rol,activo,email").execute()
            else:
                usr_resp = supabase.table("usuarios").select("id,usuario,nombre,rol,activo,email").eq("email", emp_sel_usr).execute()
            df_usr_emp = pd.DataFrame(usr_resp.data or [])
            if not df_usr_emp.empty:
                df_usr_emp_display = df_usr_emp.rename(columns={"email":"empresa_id"})
                st.dataframe(df_usr_emp_display, use_container_width=True)
                
                st.markdown("#### 🛠️ Editar / Eliminar Cuenta de Usuario")
                opciones_usrs = []
                mapa_usrs = {}
                for _, u_row in df_usr_emp.iterrows():
                    lbl = f"{u_row['usuario']} ({u_row['nombre']}) - Empresa: {u_row['email'] or 'global'}"
                    opciones_usrs.append(lbl)
                    mapa_usrs[lbl] = u_row
                
                usr_a_editar_lbl = st.selectbox("Seleccione el usuario a gestionar:", opciones_usrs, key="super_admin_sel_usr_edit")
                usr_sel = mapa_usrs[usr_a_editar_lbl]
                
                # Sincronizar y forzar reconstrucción de widgets si cambia el usuario seleccionado
                if "sa_prev_selected_user_id" not in st.session_state or st.session_state["sa_prev_selected_user_id"] != usr_sel["id"]:
                    st.session_state["sa_prev_selected_user_id"] = usr_sel["id"]
                    for k in list(st.session_state.keys()):
                        if k.startswith("sa_edit_u_") or k.startswith("sa_edit_u"):
                            st.session_state.pop(k, None)
                
                col_ue1, col_ue2 = st.columns(2)
                with col_ue1:
                    edit_u_username = st.text_input("Usuario de Acceso:", value=usr_sel["usuario"], key="sa_edit_u_user")
                    edit_u_name = st.text_input("Nombre de Persona:", value=usr_sel["nombre"], key="sa_edit_u_name")
                    edit_u_email = st.text_input("Asociar a Empresa ID (email):", value=usr_sel["email"] or "", key="sa_edit_u_email")
                with col_ue2:
                    edit_u_pass = st.text_input("Clave / Contraseña:", type="password", value="", placeholder="Dejar en blanco para no cambiar", key="sa_edit_u_pass")
                    roles_list = ["admin", "gerente", "supervisor", "cajero", "cajera"]
                    try:
                        rol_idx = roles_list.index(usr_sel["rol"])
                    except ValueError:
                        rol_idx = 0
                    edit_u_rol = st.selectbox("Rol:", roles_list, index=rol_idx, key="sa_edit_u_rol")
                    edit_u_activo = st.checkbox("Usuario Activo", value=bool(usr_sel["activo"]), key="sa_edit_u_activo")
                
                with st.expander("🛡️ Configurar Accesos y Permisos", expanded=False):
                    col_p1, col_p2 = st.columns(2)
                    with col_p1:
                        edit_u_pv = st.checkbox("Puede Vender (POS)", value=bool(usr_sel.get("puede_vender", True)), key="sa_edit_u_pv")
                        edit_u_pev = st.checkbox("Puede Editar Ventas/Facturas", value=bool(usr_sel.get("puede_editar_ventas", False)), key="sa_edit_u_pev")
                        edit_u_pel = st.checkbox("Puede Eliminar Registros", value=bool(usr_sel.get("puede_eliminar", False)), key="sa_edit_u_pel")
                        edit_u_pan = st.checkbox("Puede Anular Ventas/Facturas", value=bool(usr_sel.get("puede_anular", False)), key="sa_edit_u_pan")
                    with col_p2:
                        edit_u_pvr = st.checkbox("Puede Ver Reportes/Dashboard", value=bool(usr_sel.get("puede_ver_reportes", False)), key="sa_edit_u_pvr")
                        edit_u_prc = st.checkbox("Puede Registrar Compras", value=bool(usr_sel.get("puede_registrar_compras", False)), key="sa_edit_u_prc")
                        edit_u_prg = st.checkbox("Puede Registrar Gastos", value=bool(usr_sel.get("puede_registrar_gastos", False)), key="sa_edit_u_prg")
                        edit_u_pcf = st.checkbox("Puede Modificar Configuración", value=bool(usr_sel.get("puede_configurar", False)), key="sa_edit_u_pcf")
                
                c_btn_sa1, c_btn_sa2 = st.columns(2)
                with c_btn_sa1:
                    if st.button("💾 Guardar Cambios de Usuario", key="sa_btn_save_user", use_container_width=True):
                        try:
                            payload_upd = {
                                "usuario": edit_u_username.strip().lower(),
                                "nombre": edit_u_name.strip(),
                                "email": edit_u_email.strip() if edit_u_email.strip() else None,
                                "rol": edit_u_rol,
                                "activo": edit_u_activo,
                                "puede_vender": edit_u_pv,
                                "puede_ver_reportes": edit_u_pvr,
                                "puede_configurar": edit_u_pcf,
                                "puede_registrar_compras": edit_u_prc,
                                "puede_registrar_gastos": edit_u_prg,
                                "puede_editar_ventas": edit_u_pev,
                                "puede_eliminar": edit_u_pel,
                                "puede_anular": edit_u_pan
                            }
                            if edit_u_pass.strip():
                                payload_upd["clave"] = hashear_clave(edit_u_pass.strip())
                                
                            supabase.table("usuarios").update(payload_upd).eq("id", usr_sel["id"]).execute()
                            st.success(f"🎉 Usuario '{edit_u_username}' actualizado con éxito.")
                            st.rerun()
                        except Exception as e_sa:
                            st.error(f"Error al actualizar usuario: {e_sa}")
                with c_btn_sa2:
                    if st.button("🗑️ Eliminar Cuenta de Usuario", key="sa_btn_delete_user", use_container_width=True):
                        try:
                            supabase.table("usuarios").delete().eq("id", usr_sel["id"]).execute()
                            st.success(f"🗑️ Cuenta de usuario '{usr_sel['usuario']}' eliminada permanentemente.")
                            st.rerun()
                        except Exception as e_sa_del:
                            st.error(f"Error al eliminar usuario: {e_sa_del}")
            else:
                st.info("No hay usuarios para esta empresa.")
        except Exception as exc:
            st.warning(f"No se pudieron cargar los usuarios: {exc}")

        st.markdown("---")
        st.subheader("👤 Crear usuario/administrador para empresa")
        st.caption("Crea la cuenta inicial de administrador para el dueño de la empresa o empleados de forma visual en segundos.")
        
        c_usr1, c_usr2 = st.columns(2)
        with c_usr1:
            opc_emp_usr = [e.get("propietario") for e in todas_cfg if e.get("propietario") != "global"]
            emp_usr_sel = st.selectbox("Seleccionar Empresa:", opc_emp_usr, key="admin_crear_usr_emp")
            n_usr_usuario = st.text_input("Usuario de Acceso:", placeholder="ej. biberon_admin", key="admin_crear_usr_user")
            n_usr_nombre = st.text_input("Nombre del Dueño/Empleado:", placeholder="ej. Administrador Bibe Ron", key="admin_crear_usr_name")
        with c_usr2:
            n_usr_clave = st.text_input("Clave de Acceso Inicial:", type="password", placeholder="ej. biberon2026", key="admin_crear_usr_pass")
            n_usr_rol = st.selectbox("Rol Asignado:", ["admin", "gerente", "supervisor", "cajero", "cajera"], key="admin_crear_usr_rol")
            
        with st.expander("🛡️ Configurar Accesos Iniciales del Usuario", expanded=False):
            col_cr1, col_cr2 = st.columns(2)
            # Default permissions by role
            is_cajera = n_usr_rol in ["cajera", "cajero"]
            is_gerente = n_usr_rol == "gerente"
            is_admin = n_usr_rol == "admin"
            with col_cr1:
                n_usr_pv = st.checkbox("Puede Vender (POS)", value=True, key="sa_cr_usr_pv")
                n_usr_pev = st.checkbox("Puede Editar Ventas/Facturas", value=is_gerente or is_admin, key="sa_cr_usr_pev")
                n_usr_pel = st.checkbox("Puede Eliminar Registros", value=is_admin, key="sa_cr_usr_pel")
                n_usr_pan = st.checkbox("Puede Anular Ventas/Facturas", value=is_gerente or is_admin, key="sa_cr_usr_pan")
            with col_cr2:
                n_usr_pvr = st.checkbox("Puede Ver Reportes/Dashboard", value=is_gerente or is_admin, key="sa_cr_usr_pvr")
                n_usr_prc = st.checkbox("Puede Registrar Compras", value=is_gerente or is_admin, key="sa_cr_usr_prc")
                n_usr_prg = st.checkbox("Puede Registrar Gastos", value=is_gerente or is_admin, key="sa_cr_usr_prg")
                n_usr_pcf = st.checkbox("Puede Modificar Configuración", value=is_admin, key="sa_cr_usr_pcf")
                
        if st.button("🚀 Registrar Cuenta de Usuario", key="btn_admin_registrar_usr_emp", use_container_width=True):
            user_clean = (n_usr_usuario or "").strip().lower()
            name_clean = (n_usr_nombre or "").strip()
            pass_clean = (n_usr_clave or "").strip()
            
            if not emp_usr_sel:
                st.error("Debe seleccionar una empresa válida.")
            elif not user_clean or not pass_clean or not name_clean:
                st.error("Todos los campos son obligatorios para crear la cuenta.")
            else:
                try:
                    # Validar si ya existe ese nombre de usuario
                    user_exist = supabase.table("usuarios").select("*").eq("usuario", user_clean).execute().data
                    if user_exist:
                        st.error(f"Ya existe un usuario en el sistema con el nombre '{user_clean}'.")
                    else:
                        new_user_payload = {
                            "usuario": user_clean,
                            "nombre": name_clean,
                            "clave": hashear_clave(pass_clean),
                            "rol": n_usr_rol,
                            "activo": True,
                            "email": emp_usr_sel, # Vinculado al propietario (empresa_id)
                            "puede_vender": n_usr_pv,
                            "puede_ver_reportes": n_usr_pvr,
                            "puede_configurar": n_usr_pcf,
                            "puede_registrar_compras": n_usr_prc,
                            "puede_registrar_gastos": n_usr_prg,
                            "puede_editar_ventas": n_usr_pev,
                            "puede_eliminar": n_usr_pel,
                            "puede_anular": n_usr_pan
                        }
                        supabase.table("usuarios").insert(new_user_payload).execute()
                        st.success(f"🎉 ¡Cuenta '{user_clean}' creada con éxito para la empresa '{emp_usr_sel}'!")
                        st.info(f"🔑 **Credenciales**: Usuario: `{user_clean}` | Clave: `{pass_clean}`")
                        limpiar_cache_datos()
                        st.rerun()
                except Exception as exc:
                    st.error(f"Error al registrar usuario: {exc}")

        st.markdown("---")
        st.subheader("➕ Crear nueva empresa")
        
        st.markdown("##### 🏢 Datos de la Empresa")
        nc1, nc2 = st.columns(2)
        with nc1:
            new_prop = st.text_input("ID único (sin espacios, ej: empresa2)", key="new_emp_prop", placeholder="empresa2")
            new_nombre = st.text_input("Nombre del negocio", key="new_emp_nombre")
            new_tel = st.text_input("Teléfono", key="new_emp_tel")
        with nc2:
            new_rnc = st.text_input("RNC", key="new_emp_rnc")
            new_dir = st.text_input("Dirección", key="new_emp_dir")
            new_slogan = st.text_input("Slogan", key="new_emp_slogan")
            new_dias_prueba = st.number_input("Días de prueba gratis de licencia", min_value=0, max_value=365, value=7, step=1, key="new_emp_dias_prueba")
            
        st.markdown("##### 👤 Cuenta de Administrador Inicial (Altamente Recomendado)")
        st.caption("Crea la cuenta de usuario principal para esta empresa de forma automática.")
        nca1, nca2 = st.columns(2)
        with nca1:
            adm_user = st.text_input("Usuario de Acceso:", placeholder="ej. biberon_admin", key="new_emp_adm_user")
            adm_nombre = st.text_input("Nombre del Propietario/Encargado:", placeholder="ej. Administrador Bibe Ron", key="new_emp_adm_nombre")
        with nca2:
            adm_pass = st.text_input("Clave / Contraseña:", placeholder="ej. 123456", key="new_emp_adm_pass")
            
        if st.button("🏢 Crear empresa y usuario administrador", key="btn_crear_emp", use_container_width=True):
            prop_id = (new_prop or "").strip().lower().replace(" ", "_")
            user_clean = (adm_user or "").strip().lower()
            name_clean = (adm_nombre or "").strip()
            pass_clean = (adm_pass or "").strip()
            
            if not prop_id:
                st.error("El ID de empresa es obligatorio.")
            elif any(e.get("propietario") == prop_id for e in todas_cfg):
                st.error(f"Ya existe una empresa con ID '{prop_id}'.")
            elif user_clean and (not name_clean or not pass_clean):
                st.error("Si deseas crear un administrador, debes rellenar su Nombre Completo y Clave.")
            else:
                try:
                    # Validar si el usuario administrador ya existe si se especificó uno
                    if user_clean:
                        user_exist = supabase.table("usuarios").select("*").eq("usuario", user_clean).execute().data
                        if user_exist:
                            st.error(f"Ya existe un usuario con el nombre '{user_clean}' en el sistema.")
                            st.stop()
                            
                    base = supabase.table("configuracion_sistema").select("*").eq("id", 1).execute().data
                    payload = (base[0].copy() if base else {})
                    payload.pop("id", None)
                    
                    # Para evitar el error 'duplicate key value violates unique constraint "configuracion_sistema_clave_idx"',
                    # usamos el prop_id como clave única de esta empresa en configuracion_sistema.
                    payload.update({
                        "propietario": prop_id,
                        "negocio_nombre": new_nombre or f"Empresa {prop_id.capitalize()}",
                        "nombre_sistema": f"A&M · {(new_nombre or prop_id).capitalize()}",
                        "telefono": new_tel, "rnc": new_rnc, "direccion": new_dir,
                        "slogan": new_slogan, "logo_url": None, "clave": prop_id
                    })
                    supabase.table("configuracion_sistema").insert(payload).execute()
                    
                    # Registrar licencia de prueba gratis si es mayor a 0 días
                    if new_dias_prueba > 0:
                        fecha_venc_prueba = datetime.now().date() + timedelta(days=int(new_dias_prueba))
                        supabase.table("suscripciones_empresas").insert({
                            "empresa_id": prop_id,
                            "fecha_inicio": str(datetime.now().date()),
                            "fecha_vencimiento": str(fecha_venc_prueba),
                            "monto_pagado": 0.0,
                            "periodo": f"{new_dias_prueba} días de prueba",
                            "metodo_pago": "prueba",
                            "dias_gracia": 0,
                            "observacion": f"Período de prueba de {new_dias_prueba} días otorgado al crear la empresa"
                        }).execute()
                    
                    # Registrar auditoría de la empresa
                    registrar_auditoria_pro(
                        accion="crear_empresa", modulo="Gestión de Empresas",
                        tabla_afectada="configuracion_sistema",
                        despues_json={"propietario": prop_id, "negocio_nombre": new_nombre},
                        descripcion=f"Nueva empresa creada: {prop_id}"
                    )
                    
                    # Crear automáticamente el usuario si se especificaron los datos
                    user_created_msg = ""
                    if user_clean and pass_clean:
                        new_user_payload = {
                            "usuario": user_clean,
                            "nombre": name_clean,
                            "clave": hashear_clave(pass_clean),
                            "rol": "admin",
                            "activo": True,
                            "email": prop_id, # Vinculado al propietario
                            "puede_vender": True,
                            "puede_ver_reportes": True,
                            "puede_configurar": True,
                            "puede_registrar_compras": True,
                            "puede_registrar_gastos": True,
                            "puede_editar_ventas": True,
                            "puede_eliminar": True,
                            "puede_anular": True
                        }
                        supabase.table("usuarios").insert(new_user_payload).execute()
                        user_created_msg = f" y se creó el usuario administrador '{user_clean}'"
                    
                    _obtener_configuracion_interna.clear()
                    st.success(f"✅ ¡Empresa '{new_nombre or prop_id}' creada con éxito{user_created_msg}! ID: `{prop_id}`")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Error al crear empresa: {exc}")




