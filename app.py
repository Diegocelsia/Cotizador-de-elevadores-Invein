import base64
import html
import io
import math
from pathlib import Path
from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from auth_manager import AuthManager
from bucket_catalog import get_bucket_catalog_options
from calculator_engine import CalculatorEngine
from database import SessionLocal
from models import BomTemplate, SheetPrice, UserRole
from technical_capacities import get_capacity_form_config

pdf_gen = None
LOGO_PATH = Path(__file__).parent / "data" / "LogoColorLinea-1.svg"


def get_pdf_generator():
    global pdf_gen
    if pdf_gen is None:
        from pdf_generator import CotizacionPDFGenerator

        pdf_gen = CotizacionPDFGenerator
    return pdf_gen


def build_excel_bytes(sheets):
    """Crea un XLSX en memoria sin pandas."""
    workbook = Workbook()
    first_sheet = True

    for sheet_name, rows in sheets.items():
        worksheet = workbook.active if first_sheet else workbook.create_sheet(title=sheet_name)
        worksheet.title = sheet_name
        first_sheet = False

        if not rows:
            worksheet.append(["Sin datos"])
            continue

        headers = list(rows[0].keys())
        worksheet.append(headers)
        for row in rows:
            worksheet.append([row.get(header, "") for header in headers])

    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def esc(value):
    return html.escape(str(value))


def load_logo_data_uri():
    if not LOGO_PATH.exists():
        return ""
    svg_text = LOGO_PATH.read_text(encoding="utf-8")
    encoded = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def render_table(rows, empty_message="Sin datos"):
    """Renderiza una tabla HTML simple sin pandas ni st.dataframe."""
    if not rows:
        st.info(empty_message)
        return

    headers = list(rows[0].keys())
    table_html = ["<div class='table-shell'><table class='friendly-table'>"]
    table_html.append("<thead><tr>")
    for header in headers:
        table_html.append(f"<th>{esc(header)}</th>")
    table_html.append("</tr></thead><tbody>")

    for row in rows:
        table_html.append("<tr>")
        for header in headers:
            table_html.append(f"<td>{esc(row.get(header, ''))}</td>")
        table_html.append("</tr>")

    table_html.append("</tbody></table></div>")
    st.markdown("".join(table_html), unsafe_allow_html=True)


def render_metric_cards(cards):
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        col.markdown(
            f"""
            <div class='metric-card'>
                <div class='metric-label'>{esc(card['label'])}</div>
                <div class='metric-value'>{esc(card['value'])}</div>
                <div class='metric-sub'>{esc(card.get('sub', ''))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def normalize_model(modelo):
    return str(modelo).lower().replace("*", "x").replace(" ", "")


def allow_pierna_inspeccion(modelo, altura):
    return normalize_model(modelo) == "5x4" and altura < 15


def check_database_connection():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return True
    except (OperationalError, UnicodeDecodeError, Exception):
        return False
    finally:
        db.close()


def logout():
    st.session_state.user = None
    st.session_state.logged_in = False
    st.session_state.cotizacion_actual = None
    st.session_state.last_rule = None
    st.rerun()


def login_page():
    logo_src = load_logo_data_uri()
    st.markdown(
        """
        <div class='login-title-row'>
            <h1>Cotizador de elevadores</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.02, 0.98], gap="medium")

    with left:
        st.markdown(
            f"""
            <div class='login-panel login-logo-panel'>
                <div class='login-logo-frame'>
                    <img src='{logo_src}' class='login-logo-image' alt='INVEIN logo'/>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <div class='login-panel login-form-panel'>
                <div class='login-form-head'>
                    <h2>Ingresar</h2>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            usuario = st.text_input("Usuario", key="login_user", placeholder="Invein")
            password = st.text_input("Contraseña", type="password", key="login_pass", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            if submitted:
                db = SessionLocal()
                try:
                    auth_manager = AuthManager(db)
                    user = auth_manager.authenticate_user(usuario, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception:
                    st.error("No se pudo conectar o autenticar contra la base de datos.")
                finally:
                    db.close()




def render_topbar(user):
    logo_src = load_logo_data_uri()
    brand, info, action = st.columns([2.6, 1.2, 0.7], vertical_alignment="center")
    with brand:
        st.markdown(
            f"""
            <div class='topbar-brand'>
                <img src='{logo_src}' class='topbar-logo' alt='INVEIN logo'/>
                <div>
                    <div class='topbar-title'>Cotizador Elevador INVEIN</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with info:
        st.markdown(
            f"""
            <div class='user-chip'>
                <div><strong>{esc(user.nombre)}</strong></div>
                <div class='muted'>{esc(user.rol.value)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with action:
        if st.button("Cerrar sesión", use_container_width=True):
            logout()


def render_steps():
    cols = st.columns(3)
    steps = [
        ("1", "Elige", "Modelo, material y altura."),
        ("2", "Ajusta", "Pierna Inspección solo cuando aplique."),
        ("3", "Cotiza", "Revisa costo, ingeniería y exporta."),
    ]
    for col, (num, title, subtitle) in zip(cols, steps):
        with col:
            st.markdown(
                f"""
                <div class='step-card'>
                    <div class='step-number'>{num}</div>
                    <div class='step-title'>{esc(title)}</div>
                    <div class='step-subtitle'>{esc(subtitle)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def get_available_calibres(db: Session, material_sel: str):
    calibres = db.query(SheetPrice.calibre).filter(SheetPrice.material == material_sel).distinct().all()
    valores = sorted({int(c[0]) for c in calibres if c[0] is not None})
    return valores or [12, 14]


def render_cotizador(db: Session, user):
    modelos_disponibles = db.query(BomTemplate.modelo_elevador).distinct().all()
    modelos = [m[0] for m in modelos_disponibles] if modelos_disponibles else ["5x4"]
    materiales = ["HR", "GALV"]
    tipos_banda = ["Con Cubierta Negra", "Sin Cubierta", "Sanitaria", "Alta Temperatura"]
    resistencias_banda = ["ENL 200 - 4 Lonas", "ENL 250 - 4 Lonas", "ENL 315 - 5 Lonas"]

    catalogo_cubetas = get_bucket_catalog_options()
    familias_cubeta = catalogo_cubetas.get("familias") or ["HD-STAX"]

    st.markdown(
        """
        <div class='section-title section-compact'>
            <h2>Cotizador técnico organizado</h2>
            <p>Define equipo y operación por bloques. Luego revisa especificaciones y resumen comercial en formato ejecutivo.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.25, 1.0], gap="large")

    with left:
        with st.form("cotizacion_form"):
            st.markdown(
                """
                <div class='panel panel-dark'>
                    <h3>⚙️ Parámetros del equipo</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            eq1, eq2, eq3 = st.columns(3)
            with eq1:
                modelo = st.selectbox("Modelo del elevador", modelos)
            with eq2:
                material_sel = st.selectbox("Material", materiales)
            with eq3:
                calibre_pre = st.selectbox("Calibre de piernas", [12, 14], index=0)

            eq4, eq5, eq6 = st.columns(3)
            with eq4:
                tipo_banda = st.selectbox("Tipo de banda", tipos_banda)
            with eq5:
                resistencia_banda = st.selectbox("Resistencia de banda", resistencias_banda)
            with eq6:
                modelo_cubeta = st.selectbox("Modelo de cubeta", familias_cubeta)

            perfiles_cubeta = catalogo_cubetas.get("perfiles_por_familia", {}).get(modelo_cubeta) or ["Estandar", "Bajo"]
            materiales_cubeta = catalogo_cubetas.get("materiales_por_familia", {}).get(modelo_cubeta) or ["Polietileno", "Nylon", "Uretano"]
            tamanos_cubeta = catalogo_cubetas.get("tamanos_por_familia", {}).get(modelo_cubeta) or []
            opciones_tamano = tamanos_cubeta if tamanos_cubeta else ["No especificado en página"]

            eq7, eq8, eq9 = st.columns(3)
            with eq7:
                perfil_cubeta = st.selectbox("Perfil de cubeta", perfiles_cubeta)
            with eq8:
                material_cubeta = st.selectbox("Material de cubeta", materiales_cubeta)
            with eq9:
                tamano_cubeta = st.selectbox("Tamaño de cubeta", opciones_tamano)

            escenario_llenado = st.selectbox(
                "Escenario de llenado",
                ["admisible", "agua"],
                index=0,
                help="admisible = operación normal. agua = capacidad total teórica del cuadro técnico.",
            )

            config_excel = get_capacity_form_config(modelo=modelo, escenario_llenado=escenario_llenado)
            editable_map = config_excel.get("editable", {})
            values_map = config_excel.get("values", {})

            st.markdown(
                """
                <div class='panel panel-dark'>
                    <h3>📐 Parámetros operativos</h3>
                </div>
                """,
                unsafe_allow_html=True,
            )

            op1, op2, op3, op4 = st.columns(4)
            with op1:
                eficiencia_pct = st.number_input(
                    "Eficiencia (%)",
                    min_value=40.0,
                    max_value=99.0,
                    value=float(values_map.get("eficiencia", 85.0)),
                    step=1.0,
                    disabled=not editable_map.get("eficiencia", True),
                )
            with op2:
                altura = st.number_input(
                    "Altura total (m)",
                    min_value=1.0,
                    max_value=50.0,
                    value=float(values_map.get("altura_m", 10.0)),
                    step=0.5,
                    disabled=not editable_map.get("altura_m", True),
                )
            with op3:
                rpm = st.number_input(
                    "Velocidad angular (RPM)",
                    min_value=10,
                    max_value=500,
                    value=int(round(values_map.get("rpm", 100.0))),
                    step=1,
                    disabled=not editable_map.get("rpm", True),
                )
            with op4:
                densidad = st.number_input(
                    "Densidad M.P. (kg/m³)",
                    min_value=100.0,
                    max_value=2000.0,
                    value=float(values_map.get("densidad", 800.0)),
                    step=10.0,
                    disabled=not editable_map.get("densidad", True),
                )

            diametro_polea = float(values_map.get("diametro_polea_m", 0.5))

            calibres_disponibles = get_available_calibres(db, material_sel)
            puede_pierna = allow_pierna_inspeccion(modelo, altura)
            opciones_regla = [c for c in [12, 14] if c in calibres_disponibles] or [12]
            calibre_pierna = calibre_pre if calibre_pre in opciones_regla else 12
            if not puede_pierna:
                calibre_pierna = 12

            submitted = st.form_submit_button("Calcular cotización", use_container_width=True)

        if submitted:
            try:
                engine = CalculatorEngine(db)
                calibres_por_parte = {"Pierna Inspeccion": calibre_pierna} if puede_pierna else {}
                cotizacion = engine.calcular_cotizacion(
                    modelo=modelo,
                    material_lamina=material_sel,
                    altura_total=altura,
                    rpm=rpm,
                    densidad_producto=densidad,
                    diametro_polea=diametro_polea,
                    calibres_por_parte=calibres_por_parte,
                    escenario_llenado=escenario_llenado,
                    eficiencia_pct=eficiencia_pct,
                )

                st.session_state.cotizacion_actual = {
                    "cotizacion": cotizacion,
                    "modelo": modelo,
                    "material": material_sel,
                    "escenario_llenado": escenario_llenado,
                    "eficiencia_pct": eficiencia_pct,
                    "altura": altura,
                    "rpm": rpm,
                    "densidad": densidad,
                    "diametro_polea": diametro_polea,
                    "calibre_pierna": calibre_pierna if puede_pierna else 12,
                    "tipo_banda": tipo_banda,
                    "resistencia_banda": resistencia_banda,
                    "modelo_cubeta": modelo_cubeta,
                    "perfil_cubeta": perfil_cubeta,
                    "material_cubeta": material_cubeta,
                    "tamano_cubeta": tamano_cubeta,
                    "puede_pierna": puede_pierna,
                    "calibres_por_parte": calibres_por_parte,
                }
                st.session_state.last_rule = {
                    "modelo": modelo,
                    "escenario_llenado": escenario_llenado,
                    "altura": altura,
                    "calibre": calibre_pierna if puede_pierna else 12,
                    "puede_pierna": puede_pierna,
                }
                st.success("Cotización generada correctamente.")
            except Exception as e:
                st.error(f"Error generando cotización: {e}")

    with right:
        result = st.session_state.get("cotizacion_actual")
        if not result:
            st.markdown(
                """
                <div class='panel big-panel'>
                    <h3>Tu cotización aparecerá aquí</h3>
                    <p class='muted'>Cuando calcules, verás el total, el detalle de materiales, el impacto del calibre y el resumen técnico.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        # Si se modifican parámetros y no se recalcula, evitar mostrar resultados viejos.
        desfasado = (
            result.get("modelo") != modelo
            or result.get("material") != material_sel
            or result.get("escenario_llenado") != escenario_llenado
            or abs(float(result.get("altura", 0)) - float(altura)) > 1e-9
            or abs(float(result.get("rpm", 0)) - float(rpm)) > 1e-9
            or abs(float(result.get("densidad", 0)) - float(densidad)) > 1e-9
            or abs(float(result.get("eficiencia_pct", 0)) - float(eficiencia_pct)) > 1e-9
        )

        if desfasado:
            st.warning(
                "Cambiaste parametros del formulario. Pulsa 'Calcular cotizacion' para actualizar los resultados tecnicos y financieros."
            )
            return

        cotizacion = result["cotizacion"]

        diametro_in = cotizacion.especificaciones.get("diametro_polea_in", result["diametro_polea"] * 39.3701)
        torque_val = cotizacion.especificaciones.get("momento_torsion_tabla")
        torque_unit = cotizacion.especificaciones.get("unidad_torque_inferida", "N*m")
        if torque_val is None:
            torque_val = cotizacion.especificaciones.get("torque_nm", 0)
            torque_unit = "N*m"

        def section_from_part(parte_nombre):
            texto = (parte_nombre or "").lower()
            texto = (
                texto.replace("á", "a")
                .replace("é", "e")
                .replace("í", "i")
                .replace("ó", "o")
                .replace("ú", "u")
            )

            if "pierna inspeccion" in texto:
                return "Pierna Inspección"
            if "piernas elevador" in texto:
                return "Piernas Elevador"
            if "cabeza" in texto:
                return "Cabeza"
            if "base" in texto:
                return "Base"
            return "Otros"

        section_costs = {}
        for item in cotizacion.detalles_bom:
            section = section_from_part(item.get("parte", ""))
            section_costs[section] = section_costs.get(section, 0.0) + float(item.get("costo_venta", 0.0))

        section_rows = []
        for section in ["Cabeza", "Piernas Elevador", "Pierna Inspección", "Base", "Otros"]:
            costo = section_costs.get(section, 0.0)
            if costo > 0 or section != "Otros":
                section_rows.append({"Sección": section, "Valor": f"${costo:,.0f}"})

        spec_cards = [
            ("Diámetro polea", f"{diametro_in:,.1f} in"),
            ("Vel. lineal", f"{cotizacion.especificaciones.get('velocidad_lineal_m_s', 0):,.2f} m/s"),
            ("Capacidad neta", f"{cotizacion.especificaciones.get('capacidad_ton_h', 0):,.2f} Ton/h"),
            ("Capacidad bruta", f"{cotizacion.especificaciones.get('capacidad_ton_h_teorica', cotizacion.especificaciones.get('capacidad_ton_h', 0)):,.2f} Ton/h"),
            ("Torque", f"{torque_val:,.2f} {torque_unit}"),
            ("Potencia", f"{cotizacion.especificaciones.get('potencia_hp', 0):,.2f} HP"),
        ]

        resumen_rows = [
            ("Modelo", f"{result['modelo']} - {result['material']}"),
            ("Calibre", f"Cal. {result['calibre_pierna']}"),
            ("Altura", f"{result['altura']:.1f} m"),
            ("Banda", result["tipo_banda"]),
            ("Resistencia", result["resistencia_banda"]),
            ("Cubeta", f"{result['modelo_cubeta']} / {result['perfil_cubeta']}"),
            ("Material cubeta", result["material_cubeta"]),
            ("Tamano cubeta", result["tamano_cubeta"]),
        ]
        resumen_html = []
        for k, v in resumen_rows:
            resumen_html.append(f"<div class='split-row'><span>{esc(k)}</span><strong>{esc(v)}</strong></div>")

        bom_rows = [
            {
                "Parte": d["parte"],
                "Material": d["material"],
                "Base 2.4m": d.get("cantidad_base_2_4m", "-"),
                "Factor": d.get("factor_altura", "-"),
                "Factor G": d.get("factor_ganancia", "-") if d.get("factor_ganancia") is not None else "-",
                "Cant.": d["cantidad"],
                "Costo unit.": f"${d['costo_unitario']:,.2f}",
                "Costo total": f"${d['costo_total']:,.2f}",
                "Precio venta": f"${d['costo_venta']:,.2f}",
            }
            for d in cotizacion.detalles_bom
        ]
        fin_rows = [
            {"Concepto": "Subtotal Transformación", "Valor": f"${cotizacion.subtotal_transformacion:,.2f}"},
            {"Concepto": "Subtotal Suministros", "Valor": f"${cotizacion.subtotal_suministros:,.2f}"},
            {"Concepto": "Subtotal neto", "Valor": f"${cotizacion.subtotal_neto:,.2f}"},
            {"Concepto": "Total venta", "Valor": f"${cotizacion.total_venta:,.2f}"},
        ]
        spec_rows = [
            {"Parámetro": "Escenario de llenado", "Valor": f"{cotizacion.especificaciones.get('escenario_llenado', '-') }"},
            {"Parámetro": "Velocidad lineal", "Valor": f"{cotizacion.especificaciones.get('velocidad_lineal_m_s', 0):.3f} m/s"},
            {"Parámetro": "Capacidad", "Valor": f"{cotizacion.especificaciones.get('capacidad_ton_h', 0):.2f} Ton/h"},
            {"Parámetro": "Capacidad teórica tabla", "Valor": f"{cotizacion.especificaciones.get('capacidad_ton_h_teorica', cotizacion.especificaciones.get('capacidad_ton_h', 0)):.2f} Ton/h"},
            {"Parámetro": "Potencia HP", "Valor": f"{cotizacion.especificaciones.get('potencia_hp', 0):.2f} HP"},
            {"Parámetro": "Potencia base", "Valor": f"{cotizacion.especificaciones.get('potencia_hp_base', 0):.2f} HP"},
            {"Parámetro": "Torque", "Valor": f"{cotizacion.especificaciones.get('torque_nm', 0):.2f} N·m"},
            {"Parámetro": "Altura elevación", "Valor": f"{cotizacion.especificaciones.get('altura_elevacion_m', 0):.2f} m"},
            {"Parámetro": "RPM operación", "Valor": f"{cotizacion.especificaciones.get('rpm_operacion', 0):.1f}"},
        ]
        if cotizacion.especificaciones.get("potencia_hp_tabla") is not None:
            spec_rows.extend(
                [
                    {"Parámetro": "Altura tabla", "Valor": f"{cotizacion.especificaciones.get('altura_tabla_m', cotizacion.especificaciones.get('altura_elevacion_m', 0)):.2f} m"},
                    {"Parámetro": "RPM tabla", "Valor": f"{cotizacion.especificaciones.get('rpm_tabla', cotizacion.especificaciones.get('rpm_operacion', 0)):.1f}"},
                    {"Parámetro": "Densidad tabla", "Valor": f"{cotizacion.especificaciones.get('densidad_tabla', cotizacion.especificaciones.get('densidad_operacion', 0)):.2f} kg/m³"},
                    {"Parámetro": "Capacidad cubeta", "Valor": f"{cotizacion.especificaciones.get('capacidad_cubeta', 0):.6f} m³"},
                    {"Parámetro": "Cubetas por metro", "Valor": f"{cotizacion.especificaciones.get('cubetas_por_metro', 0):.4f}"},
                    {"Parámetro": "Total cubetas instaladas", "Valor": f"{cotizacion.especificaciones.get('total_cubetas_instaladas', 0):.2f}"},
                    {"Parámetro": "Volumen total", "Valor": f"{cotizacion.especificaciones.get('volumen_m3', 0):.6f} m³"},
                    {"Parámetro": "Capacidad tabla (base)", "Valor": f"{cotizacion.especificaciones.get('capacidad_ton_h_tabla', 0):.2f} Ton/h"},
                    {"Parámetro": "Capacidad tabla (% eficiencia)", "Valor": f"{cotizacion.especificaciones.get('capacidad_ton_h_eficiencia_tabla', 0):.2f} Ton/h"},
                    {"Parámetro": "Potencia tabla", "Valor": f"{cotizacion.especificaciones.get('potencia_hp_tabla', 0):.3f} HP"},
                    {"Parámetro": "Potencia desde torque (N·m)", "Valor": f"{cotizacion.especificaciones.get('potencia_hp_desde_torque_nm', 0):.3f} HP"},
                    {"Parámetro": "Potencia desde torque (lb·in)", "Valor": f"{cotizacion.especificaciones.get('potencia_hp_desde_torque_lbin', 0):.3f} HP"},
                    {"Parámetro": "Error relativo N·m", "Valor": f"{cotizacion.especificaciones.get('error_rel_potencia_nm_pct', 0):.2f}%"},
                    {"Parámetro": "Error relativo lb·in", "Valor": f"{cotizacion.especificaciones.get('error_rel_potencia_lbin_pct', 0):.2f}%"},
                    {"Parámetro": "Unidad torque inferida", "Valor": f"{cotizacion.especificaciones.get('unidad_torque_inferida', '-') }"},
                ]
            )
        tabs = st.tabs(["Resumen", "Materiales", "Técnica", "Exportar"])

        with tabs[0]:
            st.markdown(
                f"""
                <div class='summary-shell'>
                    <div class='panel panel-dark summary-card'>
                        <h3>📦 Secciones del elevador</h3>
                        <div class='summary-note'>Valores unificados por sección, con materiales y láminas ya consolidados.</div>
                        <div class='summary-group-title'>Costo por sección</div>
                        {''.join([f"<div class='split-row'><span>{esc(row['Sección'])}</span><strong>{esc(row['Valor'])}</strong></div>" for row in section_rows])}
                        <div class='split-row split-total'><span>Total unificado</span><strong>${cotizacion.total_venta:,.0f}</strong></div>
                    </div>
                    <div class='panel panel-dark summary-card'>
                        <h3>💰 Resumen de cotización</h3>
                        <div class='quote-total'>${cotizacion.total_venta:,.0f}</div>
                        <div class='quote-sub'>COP - Pesos Colombianos</div>
                        <hr/>
                        {''.join(resumen_html)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with tabs[1]:
            st.markdown("### Materiales unificados por sección")
            render_table(section_rows, empty_message="No hay secciones para mostrar.")
            with st.expander("Ver detalle completo de materiales", expanded=False):
                render_table(bom_rows, empty_message="No hay datos BOM para ese modelo.")

        with tabs[2]:
            cards_html = ["<div class='panel panel-dark'><h3>📊 Especificaciones técnicas calculadas</h3><div class='tech-grid'>"]
            for label, value in spec_cards:
                cards_html.append(
                    f"<div class='tech-card'><div class='tech-label'>{esc(label)}</div><div class='tech-value'>{esc(value)}</div></div>"
                )
            cards_html.append("</div></div>")
            st.markdown("".join(cards_html), unsafe_allow_html=True)

            st.markdown("### Resumen financiero")
            render_table(fin_rows)

            st.markdown("### Especificaciones técnicas")
            render_table(spec_rows)

            conclusion = cotizacion.especificaciones.get("conclusion_validacion_potencia")
            if conclusion:
                st.markdown(
                    f"""
                    <div class='panel'>
                        <h3>Validación técnica de potencia</h3>
                        <p>{esc(conclusion)}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with tabs[3]:
            values = {k: v for k, v in cotizacion.desglose_costos.items() if isinstance(v, (int, float))}
            if values:
                labels = list(values.keys())
                chart_values = list(values.values())
                color_sequence = ["#22346e", "#2776bb", "#58ba48", "#ed1f24", "#f7f281", "#136734", "#cd2027"]
                colors = [color_sequence[i % len(color_sequence)] for i in range(len(labels))]
                fig = go.Figure(
                    data=[
                        go.Pie(
                            labels=labels,
                            values=chart_values,
                            marker={"colors": colors},
                            hole=0.28,
                        )
                    ]
                )
                fig.update_layout(title="Distribución de costos de venta")
                st.plotly_chart(fig, use_container_width=True)

            exp1, exp2 = st.columns(2)
            with exp1:
                excel_bytes = build_excel_bytes(
                    {
                        "BOM": bom_rows,
                        "Resumen": fin_rows,
                        "Especificaciones": spec_rows,
                    }
                )
                st.download_button(
                    "Descargar Excel",
                    data=excel_bytes,
                    file_name=f"Cotizacion_INVEIN_{result['modelo']}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            with exp2:
                PDFGenerator = get_pdf_generator()
                pdf_generator = PDFGenerator(usuario_comercial=user.nombre)
                pdf_bytes = pdf_generator.generar_pdf(
                    cotizacion=cotizacion,
                    modelo=result["modelo"],
                    material_lamina=result["material"],
                    usuario_nombre=user.nombre,
                )
                st.download_button(
                    "Descargar PDF",
                    data=pdf_bytes,
                    file_name=f"Cotizacion_INVEIN_{result['modelo']}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            with st.expander("Ver diagnóstico de cálculo", expanded=False):
                st.write(f"Modelo: {result['modelo']}")
                st.write(f"Material: {result['material']}")
                st.write(f"Altura: {result['altura']:.2f} m")
                st.write(f"Escenario: {result['escenario_llenado']}")
                st.write(f"Pierna Inspección habilitada: {'Sí' if result.get('puede_pierna') else 'No'}")
                st.write(f"RPM: {result['rpm']}")
                st.write(f"Densidad: {result['densidad']}")
                st.write(f"Diámetro polea: {result['diametro_polea']}")
                st.write(f"Pierna Inspección: calibre {result['calibre_pierna']}")
                st.write(f"Cubeta: {result['modelo_cubeta']} / {result['perfil_cubeta']} / {result['material_cubeta']} / {result['tamano_cubeta']}")
                st.write("Solo Pierna Inspección puede variar de calibre; el resto se fija en 12 por regla de negocio.")


def render_admin_panel(db: Session):
    user_rows = st.session_state.get("cotizacion_actual")

    with st.expander("Herramientas de administración", expanded=False):
        st.markdown("### Precios de láminas")
        sheet_prices = db.query(SheetPrice).order_by(SheetPrice.material, SheetPrice.calibre).all()
        if sheet_prices:
            st.caption("Ajusta los precios unitarios y guarda los cambios.")
            for sp in sheet_prices:
                c1, c2, c3 = st.columns([2.2, 1, 2])
                with c1:
                    st.write(f"**{sp.material}** - Calibre {sp.calibre}")
                with c2:
                    st.write(f"Peso: {sp.peso_hoja:.2f}")
                with c3:
                    st.number_input(
                        "Valor unitario",
                        min_value=0.0,
                        value=float(sp.valor_unitario),
                        step=1000.0,
                        key=f"precio_{sp.id}",
                        label_visibility="collapsed",
                    )

            if st.button("Guardar precios", use_container_width=True):
                try:
                    for sp in sheet_prices:
                        nuevo_valor = float(st.session_state.get(f"precio_{sp.id}", sp.valor_unitario))
                        sp.valor_unitario = max(nuevo_valor, 0.0)
                    db.commit()
                    st.success("Precios actualizados.")
                except Exception as e:
                    st.error(f"No se pudieron guardar los cambios: {e}")
        else:
            st.warning("No hay precios cargados. Ejecuta importer.py.")

        st.markdown("### Gestión BOM")
        modelos = [m[0] for m in db.query(BomTemplate.modelo_elevador).distinct().all()] or ["5x4"]
        modelo_bom = st.selectbox("Filtrar por modelo", modelos, key="bom_model_filter")
        bom_templates = db.query(BomTemplate).filter(BomTemplate.modelo_elevador == modelo_bom).all()
        bom_rows = [
            {
                "Modelo": b.modelo_elevador,
                "Parte": b.parte,
                "Material": b.material_referencia,
                "Cant.": b.cantidad,
                "Peso": f"{b.peso_unitario:.2f}",
                "Costo base": f"${b.costo_base_materia_prima:,.2f}",
                "Transformación": "Sí" if b.es_transformacion else "No",
                "Calibre": b.calibre_lamina if b.calibre_lamina is not None else "-",
            }
            for b in bom_templates
        ]
        render_table(bom_rows, empty_message="No hay datos BOM para ese modelo.")


def main():
    st.set_page_config(
        page_title="Cotizador Elevador INVEIN",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
            :root {
                --invein-navy: #22346e;
                --invein-blue: #2776bb;
                --invein-blue-deep: #23346e;
                --invein-green: #58ba48;
                --invein-red: #ed1f24;
                --invein-yellow: #f7f281;
                --invein-bg: #f7fbff;
                --invein-panel: #ffffff;
                --invein-panel-2: #f2f7ff;
                --invein-border: rgba(39, 118, 187, 0.22);
                --invein-text: #16325e;
                --invein-muted: #4f678f;
            }
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(39,118,187,0.16), transparent 33%),
                    radial-gradient(circle at top right, rgba(88,186,72,0.14), transparent 30%),
                    linear-gradient(180deg, #ffffff 0%, #f6fbff 50%, #eef6ff 100%);
                color: var(--invein-text);
            }
            .hero {
                background:
                    linear-gradient(135deg, rgba(35,52,110,0.98), rgba(39,118,187,0.92)),
                    radial-gradient(circle at top right, rgba(247,242,129,0.20), transparent 34%);
                border: 1px solid rgba(35, 52, 110, 0.16);
                border-radius: 24px;
                padding: 28px 30px;
                margin-bottom: 20px;
                box-shadow: 0 18px 50px rgba(35,52,110,0.18);
            }
            .hero-head {
                display: flex;
                align-items: center;
                gap: 18px;
                flex-wrap: wrap;
            }
            .hero-logo-wrap, .topbar-logo-wrap {
                background: rgba(255,255,255,0.92);
                border-radius: 18px;
                padding: 12px 14px;
                box-shadow: 0 10px 24px rgba(35,52,110,0.16);
                display: inline-flex;
                align-items: center;
                justify-content: center;
            }
            .hero-logo {
                display: block;
                width: 170px;
                max-width: 100%;
                height: auto;
            }
            .topbar-logo {
                display: block;
                width: 92px;
                max-width: 100%;
                height: auto;
            }
            .hero-badge {
                display: inline-block;
                padding: 6px 10px;
                border-radius: 999px;
                background: rgba(39,118,187,0.16);
                color: #ecf5ff;
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 12px;
                border: 1px solid rgba(39,118,187,0.24);
            }
            .hero h1 {
                font-size: 2.1rem;
                margin: 0 0 8px 0;
                color: #f8fbff !important;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
            }
            .hero p {
                color: #e3efff !important;
            }
            .login-title-row {
                background: linear-gradient(135deg, rgba(35,52,110,0.08), rgba(39,118,187,0.10), rgba(88,186,72,0.06));
                border: 1px solid rgba(39,118,187,0.16);
                border-radius: 22px;
                padding: 10px 14px;
                margin-bottom: 10px;
            }
            .login-title-row h1 {
                margin: 4px 0;
                color: var(--invein-text) !important;
                font-size: 2rem;
            }
            .login-title-row p {
                margin: 0;
                color: var(--invein-muted) !important;
                font-size: 0.86rem;
                line-height: 1.35;
            }
            .login-panel {
                border-radius: 24px;
                border: 1px solid rgba(39,118,187,0.18);
                box-shadow: 0 18px 44px rgba(35,52,110,0.12);
                overflow: hidden;
            }
            .login-logo-panel {
                min-height: 290px;
                background:
                    radial-gradient(circle at top right, rgba(247,242,129,0.16), transparent 28%),
                    linear-gradient(145deg, var(--invein-blue-deep), var(--invein-blue) 60%, var(--invein-green));
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 12px;
            }
            .login-logo-frame {
                width: 100%;
                min-height: 210px;
                border-radius: 22px;
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.16);
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 12px;
            }
            .login-logo-image {
                max-width: 56%;
                width: 280px;
                height: auto;
                display: block;
                filter: drop-shadow(0 8px 20px rgba(0,0,0,0.12));
            }
            .login-form-panel {
                min-height: auto;
                margin-bottom: 4px;
                background: linear-gradient(180deg, #ffffff, #f8fbff);
                padding: 12px 14px 6px 14px;
            }
            .login-form-head h2 {
                margin: 0 0 4px 0;
                font-size: 1.2rem;
                color: var(--invein-text);
            }
            .login-form-head p {
                margin: 0;
                color: var(--invein-muted);
                line-height: 1.4;
                font-size: 0.84rem;
            }
            .muted {
                color: var(--invein-muted);
            }
            .panel h3, .panel p, .panel li {
                color: #173768;
            }
            .panel {
                background: linear-gradient(180deg, #ffffff, #f8fbff);
                border: 1px solid rgba(39,118,187,0.18);
                border-radius: 18px;
                padding: 18px;
                margin-bottom: 16px;
                box-shadow: 0 8px 22px rgba(35,52,110,0.07);
            }
            .big-panel {
                min-height: 280px;
                display: flex;
                flex-direction: column;
                justify-content: center;
            }
            .section-title h2 {
                margin: 0;
                font-size: 1.5rem;
                color: #173768;
            }
            .section-title p {
                margin-top: 6px;
                color: var(--invein-muted);
            }
            .section-compact {
                margin-bottom: 10px;
            }
            .step-card, .metric-card, .user-chip, .note-chip {
                background: linear-gradient(180deg, #ffffff, #f8fbff);
                border: 1px solid rgba(39,118,187,0.18);
                border-radius: 16px;
                padding: 16px;
            }
            .panel-dark {
                background: linear-gradient(180deg, #10192d, #0d1527);
                border: 1px solid rgba(76, 110, 179, 0.35);
                box-shadow: 0 10px 24px rgba(7, 14, 28, 0.28);
            }
            .panel-dark h3,
            .panel-dark p,
            .panel-dark li,
            .panel-dark strong,
            .panel-dark span {
                color: #e8efff !important;
            }
            .tech-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 10px;
                margin-top: 10px;
            }
            .tech-card {
                background: rgba(5, 10, 20, 0.62);
                border: 1px solid rgba(70, 111, 191, 0.28);
                border-radius: 12px;
                padding: 12px;
            }
            .tech-label {
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: .04em;
                color: #9ab0dd !important;
            }
            .tech-value {
                margin-top: 5px;
                font-size: 1.4rem;
                font-weight: 800;
                color: #ffffff !important;
            }
            .summary-shell {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 12px;
                margin: 10px 0 14px 0;
            }
            .summary-card hr {
                border: none;
                border-top: 1px solid rgba(120, 153, 220, 0.22);
                margin: 12px 0;
            }
            .split-row {
                display: flex;
                justify-content: space-between;
                gap: 10px;
                padding: 6px 0;
                border-bottom: 1px solid rgba(120, 153, 220, 0.14);
                font-size: 13px;
            }
            .summary-group-title {
                margin: 8px 0 4px 0;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: .04em;
                text-transform: uppercase;
                color: #9ab0dd !important;
            }
            .summary-note {
                margin: 4px 0 10px 0;
                font-size: 12px;
                color: #8fa7d6 !important;
            }
            .split-total {
                border-bottom: none;
                font-size: 14px;
                padding-top: 8px;
            }
            .quote-total {
                font-size: 2rem;
                font-weight: 900;
                color: #f7b500 !important;
                margin-top: 8px;
            }
            .quote-sub {
                color: #8fa7d6 !important;
                font-size: 12px;
            }
            .step-number {
                width: 34px;
                height: 34px;
                border-radius: 999px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: 800;
                background: linear-gradient(135deg, rgba(39,118,187,0.28), rgba(88,186,72,0.28));
                color: #d7f3ff;
                margin-bottom: 10px;
            }
            .step-title, .metric-label {
                font-size: 13px;
                color: var(--invein-muted);
                text-transform: uppercase;
                letter-spacing: .04em;
            }
            .step-subtitle {
                margin-top: 8px;
                color: #173768;
                font-size: 14px;
                line-height: 1.5;
            }
            .metric-value {
                margin-top: 8px;
                font-size: 1.55rem;
                font-weight: 800;
                color: #173768;
            }
            .metric-sub {
                margin-top: 4px;
                color: var(--invein-muted);
                font-size: 12px;
            }
            .note-chip {
                margin-top: 12px;
                color: #1e497a;
                background: #eaf3ff;
                border-color: rgba(39,118,187,0.26);
                font-weight: 600;
            }
            .topbar-brand {
                padding: 4px 0;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .topbar-title {
                font-size: 1.1rem;
                font-weight: 800;
                color: #173768;
            }
            .topbar-subtitle {
                font-size: 12px;
                color: var(--invein-muted);
            }
            .user-chip strong { color: #173768; }
            .table-shell {
                overflow-x: auto;
                background: #ffffff;
                border: 1px solid rgba(39,118,187,0.18);
                border-radius: 16px;
                margin-bottom: 14px;
            }
            .friendly-table {
                width: 100%;
                border-collapse: collapse;
                color: #244572;
            }
            .friendly-table thead th {
                text-align: left;
                padding: 12px 14px;
                background: rgba(35,52,110,0.95);
                color: #d7e7ff;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: .04em;
                border-bottom: 1px solid rgba(39,118,187,0.20);
                white-space: nowrap;
            }
            .friendly-table tbody td {
                padding: 12px 14px;
                border-bottom: 1px solid rgba(39,118,187,0.12);
                vertical-align: top;
                font-size: 13px;
            }
            .friendly-table tbody tr:hover {
                background: rgba(39,118,187,0.06);
            }
            .stButton > button {
                background: linear-gradient(135deg, var(--invein-blue-deep), var(--invein-blue) 55%, var(--invein-green));
                color: #fff;
                border: none;
                border-radius: 12px;
                font-weight: 800;
                min-height: 2.15rem;
                font-size: 0.88rem;
            }

            /* Tabs siempre legibles (sin depender de hover) */
            .stTabs [data-baseweb="tab-list"] {
                gap: 0.45rem;
            }
            .stTabs [data-baseweb="tab"] {
                color: #1d3f74 !important;
                background: rgba(255, 255, 255, 0.8);
                border: 1px solid rgba(39,118,187,0.24);
                border-radius: 10px;
                text-shadow: 0 1px 3px rgba(255,255,255,0.85);
                font-weight: 700 !important;
            }
            .stTabs [data-baseweb="tab"] p {
                color: #1d3f74 !important;
                font-weight: 700 !important;
            }
            .stTabs [data-baseweb="tab"]:hover,
            .stTabs [data-baseweb="tab"]:focus {
                color: #142d54 !important;
                background: #ffffff;
            }
            .stTabs [aria-selected="true"] {
                color: #11284b !important;
                background: #ffffff;
                box-shadow: 0 6px 14px rgba(35,52,110,0.12);
            }
            .stTabs [aria-selected="true"] p {
                color: #11284b !important;
            }

            /* Legibilidad de formularios Streamlit */
            div[data-testid="stWidgetLabel"] p,
            .stTextInput label,
            .stNumberInput label,
            .stSelectbox label {
                color: #2b4c7e !important;
                font-weight: 650 !important;
                opacity: 1 !important;
            }

            .stTextInput input,
            .stNumberInput input {
                background: #ffffff !important;
                color: #173768 !important;
                border: 1px solid rgba(39,118,187,0.35) !important;
                min-height: 2.1rem;
                font-size: 0.88rem;
            }

            .stSelectbox div[data-baseweb="select"] > div {
                background: #ffffff !important;
                color: #173768 !important;
                border: 1px solid rgba(39,118,187,0.35) !important;
            }

            .stSelectbox div[data-baseweb="select"] svg {
                fill: #22346e !important;
            }

            .stNumberInput button {
                background: #eef5ff !important;
                color: #22346e !important;
                border: 1px solid rgba(39,118,187,0.25) !important;
            }

            .stTextInput input::placeholder,
            .stNumberInput input::placeholder {
                color: #6f86aa !important;
            }

            .stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] {
                border-radius: 12px !important;
            }

            .login-card div[data-testid="stTextInput"] input {
                font-size: 0.98rem !important;
                padding: 0.55rem 0.75rem !important;
            }
            .login-card div[data-testid="stTextInput"] label,
            .login-card div[data-testid="stWidgetLabel"] p {
                color: var(--invein-text) !important;
                font-weight: 700 !important;
            }
            .login-card .stButton > button {
                margin-top: 10px;
            }

            .login-form-panel + div[data-testid="stForm"] {
                margin-top: -2px;
            }

            /* Ajuste de viewport para evitar scroll en login al 100% */
            div[data-testid="stAppViewContainer"]:has(.login-title-row) .main .block-container {
                padding-top: 0.55rem;
                padding-bottom: 0.25rem;
            }
            div[data-testid="stAppViewContainer"]:has(.login-title-row) div[data-testid="stCaptionContainer"] {
                margin-top: 0.15rem;
            }

            @media (max-width: 900px) {
                .login-title-row,
                .login-panel {
                    min-height: auto;
                    padding: 16px;
                }
                .login-logo-image {
                    max-width: 78%;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "user" not in st.session_state:
        st.session_state.user = None
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "cotizacion_actual" not in st.session_state:
        st.session_state.cotizacion_actual = None
    if "last_rule" not in st.session_state:
        st.session_state.last_rule = None

    if not check_database_connection():
        st.error("No se pudo conectar a la base de datos.")
        st.stop()

    if not st.session_state.logged_in:
        login_page()
        return

    user = st.session_state.user
    render_topbar(user)
    render_steps()

    db: Session = SessionLocal()
    try:
        render_cotizador(db, user)

        if user.rol == UserRole.ADMIN:
            render_admin_panel(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
