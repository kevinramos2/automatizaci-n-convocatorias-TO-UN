"""Panel de revisión humana (Fase 5 del plan).

Permite elegir la convocatoria (TO-01/TO-02), adjuntar el expediente (PDF) de un
aspirante, procesarlo con la API de Claude, y revisar/confirmar los ítems que
el sistema nunca decide solo (firma, relacionado con el cargo) antes de
guardar en Google Sheets. Cada expediente se procesa una sola vez — se cachea en
disco por hash del archivo para no volver a cobrar la API en cada recarga.

Uso: streamlit run app_revision.py
"""
import base64
import json
import os
from datetime import date
from pathlib import Path

import anthropic
import streamlit as st
from dotenv import load_dotenv

from pipeline.cache_expedientes import cargar_resultado, existe_en_cache, guardar_pdf, guardar_resultado, hash_archivo, listar_cache, ruta_pdf
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.esquema_sheets import AUDITORIA, MAESTRO
from pipeline.mapeo_maestro import construir_fila_maestro
from pipeline.pdf_utils import pagina_a_imagen_base64
from pipeline.procesar_expediente import procesar_expediente
from pipeline.sheets_client import abrir_spreadsheet, agregar_filas, asegurar_hojas, autenticar, upsert_fila
from pipeline.validacion_admision import (
    CUMPLE,
    NO_CUMPLE,
    ResultadoRegla,
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

RAIZ = Path(__file__).parent
load_dotenv()

st.set_page_config(page_title="Revisión de aspirantes — TO 2026", layout="wide")

_ETIQUETA_ITEM = {
    "formulario": "1. Formulario de inscripción",
    "cedula": "2. Fotocopia de cédula",
    "estudio": "3. Constancia de estudio",
    "laboral": "4. Constancias laborales",
    "alturas": "5. Certificado de alturas",
    "medica": "6. Evaluación médica",
}
_CONVOCATORIAS = {
    "TO-02": {"etiqueta": "TO-02 · Ayudante de Albañilería", "criterios": "criterios/criterios_TO-02.json"},
    "TO-01": {"etiqueta": "TO-01 · Oficial de Jardinería", "criterios": "criterios/criterios_TO-01.json"},
}

# Misma paleta del guión de demo (Sección "Fase 5"), en dos variantes.
_PALETA_CLARA = {
    "bg": "#faf9f5", "surface": "#ffffff", "surface-2": "#f3f1ea", "border": "#e4e0d4",
    "ink": "#21242b", "ink-muted": "#5c6270", "ink-faint": "#8b8f9c",
    "accent": "#1d3557", "accent-tint": "#e9eef5", "accent-tint-border": "#c9d6e8",
    "good": "#2e7d46", "good-bg": "#e8f4ea", "good-border": "#bfe0c8",
    "warn": "#8a6100", "warn-bg": "#fdf3d9", "warn-border": "#f2dda0",
    "bad": "#a3312f", "bad-bg": "#fbe7e7", "bad-border": "#f2c4c3",
}
_PALETA_OSCURA = {
    "bg": "#14161b", "surface": "#1b1e25", "surface-2": "#21242c", "border": "#2e323c",
    "ink": "#e9eaee", "ink-muted": "#a5aab6", "ink-faint": "#767c8a",
    "accent": "#7fa0d1", "accent-tint": "#1e2735", "accent-tint-border": "#2c3c54",
    "good": "#6fbf85", "good-bg": "#1b2c20", "good-border": "#2e4a34",
    "warn": "#e0b84a", "warn-bg": "#332a12", "warn-border": "#55461d",
    "bad": "#e08585", "bad-bg": "#362020", "bad-border": "#55302f",
}
_ETIQUETA_ESTADO = {"cumple": "CUMPLE", "requiere_revision_manual": "REQUIERE REVISIÓN", "no_cumple": "NO CUMPLE"}


def _inyectar_estilos(oscuro: bool):
    paleta = _PALETA_OSCURA if oscuro else _PALETA_CLARA
    variables = "\n".join(f"--to-{clave}: {valor};" for clave, valor in paleta.items())

    # Repinta también el "chrome" propio de Streamlit (fondo, sidebar, inputs)
    # para que el interruptor cambie la app completa, no solo nuestras tarjetas.
    chrome_oscuro = f"""
        [data-testid="stAppViewContainer"], [data-testid="stHeader"], [data-testid="stMain"] {{ background: var(--to-bg) !important; }}
        [data-testid="stSidebar"] {{ background: var(--to-surface-2) !important; border-right: 1px solid var(--to-border); }}
        [data-testid="stSidebar"] * {{ color: var(--to-ink) !important; }}

        /* Texto nativo de Streamlit en el área principal — NUNCA un selector
           amplio tipo "*", porque pisaría los colores propios de nuestros
           badges/pills (.to-badge, .to-pill, .to-ai-box), que viven dentro
           del mismo contenedor de markdown. */
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3,
        [data-testid="stMarkdownContainer"] > p,
        [data-testid="stWidgetLabel"] p,
        [data-testid="stMetricValue"],
        [data-testid="stMetricLabel"] {{ color: var(--to-ink) !important; }}
        [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * {{ color: var(--to-ink-muted) !important; }}

        [data-testid="stTextInput"] input, [data-testid="stFileUploaderDropzone"], [data-baseweb="select"] > div {{
            background: var(--to-surface) !important; color: var(--to-ink) !important; border-color: var(--to-border) !important;
        }}
        [data-baseweb="popover"], [data-baseweb="menu"] {{ background: var(--to-surface) !important; }}
        [data-baseweb="popover"] *, [data-baseweb="menu"] * {{ color: var(--to-ink) !important; }}
        /* El selectbox de Streamlit dejó BaseWeb por React Aria Components — la caja
           cerrada (".react-aria-ComboBox") no la alcanza ningún selector de arriba y
           se queda con el fondo claro por defecto, con texto claro encima (invisible). */
        [data-testid="stSelectbox"] [role="group"] {{
            background: var(--to-surface) !important; border-color: var(--to-border) !important;
        }}
        [data-testid="stSelectbox"] input {{ background: transparent !important; color: var(--to-ink) !important; }}
        hr, [data-testid="stDivider"] {{ border-color: var(--to-border) !important; }}
        [data-testid="stExpander"], [data-testid="stContainer"] {{ background: var(--to-surface) !important; border-color: var(--to-border) !important; }}
        [data-testid="stExpander"] summary, [data-testid="stExpander"] summary * {{
            background: var(--to-surface) !important; color: var(--to-ink) !important;
        }}
    """ if oscuro else ""

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');

        :root {{ {variables} }}

        html, body, [class*="css"] {{ font-family: 'IBM Plex Sans', system-ui, sans-serif; }}
        {chrome_oscuro}

        .to-header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; flex-wrap: wrap; margin-bottom: 4px; }}
        .to-header-info {{ display: flex; flex-direction: column; gap: 4px; min-width: 0; }}
        .to-header-label {{ color: var(--to-ink-faint); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }}
        .to-header-name {{ color: var(--to-ink); font-size: 26px; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere; }}
        .to-header-cedula {{ font-family: 'IBM Plex Mono', ui-monospace, monospace; color: var(--to-ink-muted); font-size: 14.5px; }}

        .to-badge {{ display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 9px 18px; font-size: 13px; font-weight: 700; letter-spacing: 0.02em; white-space: nowrap; border: 1px solid; }}
        .to-badge-dot {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; flex-shrink: 0; }}
        .to-badge-cumple {{ background: var(--to-good-bg); color: var(--to-good); border-color: var(--to-good-border); }}
        .to-badge-requiere_revision_manual {{ background: var(--to-warn-bg); color: var(--to-warn); border-color: var(--to-warn-border); }}
        .to-badge-no_cumple {{ background: var(--to-bad-bg); color: var(--to-bad); border-color: var(--to-bad-border); }}

        .to-checklist-item {{ display: flex; gap: 14px; background: var(--to-surface); border: 1px solid var(--to-border); border-radius: 10px; padding: 14px 18px; margin-bottom: 8px; }}
        .to-checklist-num {{ font-family: 'IBM Plex Mono', ui-monospace, monospace; color: var(--to-ink-faint); font-size: 12.5px; padding-top: 2px; }}
        .to-checklist-body {{ flex: 1; min-width: 0; }}
        .to-checklist-title-row {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
        .to-checklist-title {{ color: var(--to-ink); font-size: 14.5px; font-weight: 600; }}
        .to-checklist-motivo {{ color: var(--to-ink-muted); font-size: 13px; line-height: 1.5; margin-top: 3px; }}
        .to-pill {{ font-size: 10.5px; font-weight: 700; letter-spacing: 0.03em; padding: 3px 10px; border-radius: 999px; white-space: nowrap; }}
        .to-pill-cumple {{ background: var(--to-good-bg); color: var(--to-good); }}
        .to-pill-requiere_revision_manual {{ background: var(--to-warn-bg); color: var(--to-warn); }}
        .to-pill-no_cumple {{ background: var(--to-bad-bg); color: var(--to-bad); }}

        .to-ai-box {{ background: var(--to-accent-tint); border: 1px solid var(--to-accent-tint-border); border-radius: 9px; padding: 11px 14px; margin: 8px 0; font-size: 13px; color: var(--to-ink); }}
        .to-ai-label {{ color: var(--to-accent); font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; display: block; margin-bottom: 2px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _badge_html(estado: str, texto: str) -> str:
    clase = f"to-badge-{estado}" if estado in _ETIQUETA_ESTADO else ""
    return f'<span class="to-badge {clase}"><span class="to-badge-dot"></span>{texto}</span>'


def _pill_html(estado: str) -> str:
    clase = f"to-pill-{estado}" if estado in _ETIQUETA_ESTADO else ""
    etiqueta = _ETIQUETA_ESTADO.get(estado, estado.upper())
    return f'<span class="to-pill {clase}">{etiqueta}</span>'


@st.cache_data
def _imagen_pagina(pdf_path: str, pagina: int, rotacion: int = 0) -> bytes:
    return base64.standard_b64decode(pagina_a_imagen_base64(pdf_path, pagina, dpi=150, rotacion=rotacion))


def _rotacion_de_pagina(resultado: dict, pagina: int) -> int:
    """La rotación del expediente completo (`resultado["rotacion"]`) corrige el caso

    típico (todo el escaneo viene girado igual). Pero a veces una sola página trae
    un documento insertado en orientación horizontal (ej. un certificado apaisado
    entre páginas verticales) y necesita su propia rotación, distinta a la del resto
    — `rotaciones_paginas` guarda esas excepciones por número de página.
    """
    overrides = resultado.get("rotaciones_paginas") or {}
    return overrides.get(str(pagina), resultado.get("rotacion", 0))


@st.cache_data
def _cargar_cfg():
    return json.load(open(RAIZ / "config" / "parametros.json", encoding="utf-8"))


def _normalizar_documentos(documentos_extraidos: list[dict]) -> list[dict]:
    """Uniforma el resultado de procesar_expediente() a la misma forma que se usa

    para buscar páginas fuente por tipo de documento (para mostrar imágenes).
    """
    return [
        {"tipo": d["tipo_final"], "paginas": d["paginas"], "datos": d["datos"]}
        for d in documentos_extraidos if d["tipo_final"] and d["datos"]
    ]


def _paginas_de(documentos: list[dict], tipo: str) -> list[int]:
    coincidencias = [d["paginas"] for d in documentos if d["tipo"] == tipo]
    return coincidencias[0] if coincidencias else []


_OPCIONES_VALIDEZ = ["Según el sistema", "Sí, válido", "No es válido"]


def _aplicar_override_manual(automatico: ResultadoRegla, eleccion: str) -> ResultadoRegla:
    if eleccion == "Sí, válido":
        return ResultadoRegla(CUMPLE, "Confirmado manualmente por el revisor, viendo el documento.")
    if eleccion == "No es válido":
        return ResultadoRegla(NO_CUMPLE, "Marcado manualmente como no válido por el revisor, viendo el documento.")
    return automatico


def _procesar_y_cachear(archivo_subido, criterios: dict, cfg: dict) -> dict:
    contenido = archivo_subido.getvalue()
    hash_ = hash_archivo(contenido)

    if existe_en_cache(hash_):
        st.toast("Este expediente ya se había procesado antes — se cargó del caché, sin costo de API.")
        resultado = cargar_resultado(hash_)
    else:
        ruta = guardar_pdf(hash_, contenido)
        with st.spinner("Procesando expediente (clasificación + extracción + validación)... puede tardar 1-2 minutos."):
            client = anthropic.Anthropic()
            resultado = procesar_expediente(str(ruta), criterios, cfg, client=client)
            guardar_resultado(hash_, resultado)
        uso = resultado["uso_total"]
        costo = uso["input_tokens"] / 1e6 * 2.00 + uso["output_tokens"] / 1e6 * 10.00
        st.toast(f"Expediente procesado. Costo aprox: ${costo:.4f} USD ({uso['input_tokens']} in / {uso['output_tokens']} out tokens).")

    resultado["_hash"] = hash_
    resultado["pdf_path"] = str(ruta_pdf(hash_))
    resultado["documentos"] = _normalizar_documentos(resultado.pop("documentos_extraidos", []))
    return resultado


def _cargar_desde_cache(hash_: str) -> dict:
    resultado = cargar_resultado(hash_)
    resultado["_hash"] = hash_
    resultado["pdf_path"] = str(ruta_pdf(hash_))
    resultado["documentos"] = _normalizar_documentos(resultado.pop("documentos_extraidos", []))
    return resultado


_BUCKETS = {
    "Pendientes de revisión": lambda e: e.get("estado_confirmado_por_humano") not in ("ADMITIDO", "NO ADMITIDO"),
    "Admitidos": lambda e: e.get("estado_confirmado_por_humano") == "ADMITIDO",
    "No admitidos": lambda e: e.get("estado_confirmado_por_humano") == "NO ADMITIDO",
}


def _elegir_expediente_procesado(cfg: dict) -> dict | None:
    todos = listar_cache()

    bucket = st.sidebar.radio("Ver", list(_BUCKETS), key="bucket_aspirantes")
    opciones = sorted((e for e in todos if _BUCKETS[bucket](e)), key=lambda e: e["nombre"].upper())

    if not opciones:
        st.sidebar.info(f"No hay expedientes en «{bucket}» todavía.")
        return None

    etiquetas = {}
    for o in opciones:
        partes = [o["nombre"].upper(), f"C.C. {o['cedula']}"]
        if o["convocatoria"] != "—":
            partes.append(o["convocatoria"])
        etiquetas[o["hash"]] = " — ".join(partes)

    hash_elegido = st.sidebar.selectbox("Aspirante", options=list(etiquetas), format_func=lambda h: etiquetas[h])
    return _cargar_desde_cache(hash_elegido)


def _subir_expediente_nuevo(criterios: dict, cfg: dict) -> dict | None:
    archivo_subido = st.sidebar.file_uploader("PDF del expediente del aspirante", type="pdf")
    if archivo_subido is None:
        st.sidebar.info("Adjunta un PDF para procesarlo.")
        return None

    hash_actual = hash_archivo(archivo_subido.getvalue())
    resultado_en_sesion = st.session_state.get("resultado_expediente")
    if resultado_en_sesion and resultado_en_sesion.get("_hash") != hash_actual:
        # Es un archivo distinto al ya cargado — no reutilizar sin procesar explícitamente.
        st.session_state.pop("resultado_expediente", None)
        resultado_en_sesion = None

    if resultado_en_sesion is None:
        aviso = (
            "Este expediente ya fue procesado antes — se cargará del caché, sin costo."
            if existe_en_cache(hash_actual)
            else "Procesar un expediente nuevo llama a la API de Claude (~$0.15-0.25 USD por expediente)."
        )
        st.sidebar.caption(aviso)
        if st.sidebar.button("Procesar expediente", type="primary"):
            st.session_state["resultado_expediente"] = _procesar_y_cachear(archivo_subido, criterios, cfg)

    return st.session_state.get("resultado_expediente")


def _barra_lateral(cfg: dict) -> dict | None:
    st.sidebar.title("Proceso de selección TO 2026")
    fuente = st.sidebar.radio("Expediente a revisar", ["Elegir un expediente ya procesado", "Subir un expediente nuevo"])
    st.sidebar.divider()

    if fuente == "Elegir un expediente ya procesado":
        return _elegir_expediente_procesado(cfg)

    convocatoria_id = st.sidebar.selectbox(
        "Convocatoria", options=list(_CONVOCATORIAS), format_func=lambda k: _CONVOCATORIAS[k]["etiqueta"],
    )
    criterios = json.load(open(RAIZ / _CONVOCATORIAS[convocatoria_id]["criterios"], encoding="utf-8"))
    return _subir_expediente_nuevo(criterios, cfg)


def main():
    oscuro = st.sidebar.toggle("Tema oscuro", key="modo_oscuro")
    _inyectar_estilos(oscuro)
    st.sidebar.divider()
    cfg = _cargar_cfg()
    resultado = _barra_lateral(cfg)

    if resultado is None:
        st.title("Panel de revisión — Proceso de selección TO 2026")
        st.info("Elige la convocatoria y un expediente en la barra lateral para comenzar.")
        return

    hash_ = resultado["_hash"]
    pdf_path = resultado["pdf_path"]
    documentos = resultado["documentos"]
    formulario = resultado["formulario"]
    cedula = resultado["cedula"]
    estudios = resultado["estudios"]
    laborales = resultado["laborales"]
    alturas = resultado["alturas"]
    medica = resultado["medica"]

    st.title("Panel de revisión — Proceso de selección TO 2026")

    estado_decision = resultado["decision"]["estado_sugerido"]
    estado_clave = {"ADMITIDO": "cumple", "NO ADMITIDO": "no_cumple"}.get(estado_decision, "requiere_revision_manual")
    st.markdown(
        f"""
        <div class="to-header">
          <div class="to-header-info">
            <span class="to-header-label">Aspirante</span>
            <span class="to-header-name">{(formulario.get("nombre") or "—").upper()}</span>
            <span class="to-header-cedula">C.C. {cedula.get("numero", "—")}</span>
          </div>
          {_badge_html(estado_clave, estado_decision)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if resultado["inconsistencias"]:
        with st.expander(f"{len(resultado['inconsistencias'])} inconsistencia(s) detectada(s) automáticamente", expanded=True):
            for inc in resultado["inconsistencias"]:
                st.warning(inc["detalle"])

    st.divider()
    st.subheader("Checklist de admisión")
    for i, (clave, r) in enumerate(resultado["resultados_validacion"].items(), start=1):
        etiqueta = _ETIQUETA_ITEM.get(clave, clave).split(". ", 1)[-1]
        st.markdown(
            f"""
            <div class="to-checklist-item">
              <span class="to-checklist-num">{i:02d}</span>
              <div class="to-checklist-body">
                <div class="to-checklist-title-row">
                  <span class="to-checklist-title">{etiqueta}</span>
                  {_pill_html(r.estado)}
                </div>
                <div class="to-checklist-motivo">{r.motivo}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("Confirmar firma del formulario")
    st.caption("Compara la firma de abajo (formulario) contra la firma de la cédula. Nunca se verifica automáticamente.")
    col_firma_1, col_firma_2 = st.columns(2)
    paginas_formulario = _paginas_de(documentos, "formulario_inscripcion")
    paginas_cedula = _paginas_de(documentos, "cedula")
    with col_firma_1:
        st.caption("Formulario (última página, donde firma)")
        if paginas_formulario:
            p = paginas_formulario[-1]
            st.image(_imagen_pagina(pdf_path, p, _rotacion_de_pagina(resultado, p)))
    with col_firma_2:
        st.caption("Cédula")
        if paginas_cedula:
            p = paginas_cedula[0]
            st.image(_imagen_pagina(pdf_path, p, _rotacion_de_pagina(resultado, p)))

    firma_verificada = st.radio(
        "¿La firma del formulario coincide con la de la cédula?",
        options=["Pendiente", "Sí coincide", "No coincide"], horizontal=True, key=f"firma_verificada_{hash_}",
    )
    firma_valor = {"Pendiente": None, "Sí coincide": True, "No coincide": False}[firma_verificada]

    st.divider()
    st.subheader("Confirmar experiencia y educación relacionada con el cargo")
    st.caption("El sistema sugiere SI/NO, pero nunca decide solo — confirma o corrige cada una.")

    decisiones_relacionado_laboral = []
    for i, exp in enumerate(laborales):
        with st.container(border=True):
            col_txt, col_img = st.columns([2, 1])
            with col_txt:
                st.markdown(f"**{exp.get('cargo', '—')}** en *{exp.get('entidad', '—')}*")
                st.caption(exp.get("funciones", ""))
                st.caption(f"{exp.get('fecha_inicio', '?')} → {exp.get('fecha_fin') or 'a la fecha'}")
                sugerido = exp.get("relacionado_sugerido")
                if sugerido:
                    st.markdown(
                        f'<div class="to-ai-box"><span class="to-ai-label">Sugerencia de la IA</span>'
                        f'<strong>{sugerido}</strong> — <em>{exp.get("justificacion_relacionado", "")}</em></div>',
                        unsafe_allow_html=True,
                    )
                opciones = ["PENDIENTE", "SI", "NO"]
                indice_defecto = opciones.index(sugerido) if sugerido in opciones else 0
                eleccion = st.radio("¿Relacionada con el cargo?", opciones, index=indice_defecto, horizontal=True, key=f"laboral_rel_{hash_}_{i}")
                decisiones_relacionado_laboral.append(eleccion)
            with col_img:
                if exp.get("paginas"):
                    p = exp["paginas"][0]
                    st.image(_imagen_pagina(pdf_path, p, _rotacion_de_pagina(resultado, p)))

    decisiones_relacionado_estudio = []
    for i, e in enumerate(estudios):
        if (e.get("nivel") or "").lower() != "curso_capacitacion":
            decisiones_relacionado_estudio.append(e.get("relacionado", "PENDIENTE"))
            continue
        with st.container(border=True):
            col_txt, col_img = st.columns([2, 1])
            with col_txt:
                st.markdown(f"**Curso:** {e.get('nombre_curso', '—')} — *{e.get('institucion', '—')}*")
                sugerido = e.get("relacionado_sugerido")
                if sugerido:
                    st.markdown(
                        f'<div class="to-ai-box"><span class="to-ai-label">Sugerencia de la IA</span>'
                        f'<strong>{sugerido}</strong> — <em>{e.get("justificacion_relacionado", "")}</em></div>',
                        unsafe_allow_html=True,
                    )
                opciones = ["PENDIENTE", "SI", "NO"]
                indice_defecto = opciones.index(sugerido) if sugerido in opciones else 0
                eleccion = st.radio("¿Relacionado con el cargo?", opciones, index=indice_defecto, horizontal=True, key=f"estudio_rel_{hash_}_{i}")
                decisiones_relacionado_estudio.append(eleccion)
            with col_img:
                if e.get("paginas"):
                    p = e["paginas"][0]
                    st.image(_imagen_pagina(pdf_path, p, _rotacion_de_pagina(resultado, p)))

    st.divider()
    st.subheader("Confirmar certificado de alturas y evaluación médica")
    st.caption("El sistema calcula esto de las fechas extraídas, y a veces se equivoca leyendo el documento — revisa la imagen antes de confirmar.")

    alturas_override = "Según el sistema"
    if alturas and alturas.get("aportado"):
        with st.container(border=True):
            col_txt, col_img = st.columns([2, 1])
            with col_txt:
                st.markdown(f"**Certificado de alturas** — *{alturas.get('entidad_emisora', '—')}*")
                st.caption(f"Expedición: {alturas.get('fecha_expedicion') or '—'}  ·  Vencimiento: {alturas.get('fecha_vencimiento') or '—'}")
                resultado_sistema = resultado["resultados_validacion"]["alturas"]
                st.markdown(
                    f'<div class="to-ai-box"><span class="to-ai-label">Resultado del sistema</span>'
                    f'<strong>{_ETIQUETA_ESTADO.get(resultado_sistema.estado, resultado_sistema.estado)}</strong> — <em>{resultado_sistema.motivo}</em></div>',
                    unsafe_allow_html=True,
                )
                alturas_override = st.radio("¿Es válido el certificado de alturas al cierre de inscripción?", _OPCIONES_VALIDEZ, horizontal=True, key=f"alturas_val_{hash_}")
            with col_img:
                for p in alturas.get("paginas", []):
                    st.image(_imagen_pagina(pdf_path, p, _rotacion_de_pagina(resultado, p)))

    medica_override = "Según el sistema"
    if medica and medica.get("aportado"):
        with st.container(border=True):
            col_txt, col_img = st.columns([2, 1])
            with col_txt:
                st.markdown(f"**Evaluación médica** — *{medica.get('entidad_emisora', '—')}*")
                st.caption(f"Expedición: {medica.get('fecha_expedicion') or '—'}  ·  Concepto de aptitud en alturas: {medica.get('concepto_aptitud_alturas')}")
                resultado_sistema = resultado["resultados_validacion"]["medica"]
                st.markdown(
                    f'<div class="to-ai-box"><span class="to-ai-label">Resultado del sistema</span>'
                    f'<strong>{_ETIQUETA_ESTADO.get(resultado_sistema.estado, resultado_sistema.estado)}</strong> — <em>{resultado_sistema.motivo}</em></div>',
                    unsafe_allow_html=True,
                )
                medica_override = st.radio("¿Es válida la evaluación médica?", _OPCIONES_VALIDEZ, horizontal=True, key=f"medica_val_{hash_}")
            with col_img:
                for p in medica.get("paginas", []):
                    st.image(_imagen_pagina(pdf_path, p, _rotacion_de_pagina(resultado, p)))

    st.divider()

    laborales_confirmadas = [{**e, "relacionado": d} for e, d in zip(laborales, decisiones_relacionado_laboral)]
    estudios_confirmados = [{**e, "relacionado": d} for e, d in zip(estudios, decisiones_relacionado_estudio)]

    resultados_actualizados = {
        "formulario": validar_formulario(
            {k: formulario.get(k) for k in ("nombre", "cedula", "correo", "celular", "direccion")},
            {"nombre": cedula.get("nombre"), "numero": cedula.get("numero")},
            firma_verificada=firma_valor,
        ),
        "cedula": validar_cedula(cedula),
        "estudio": validar_constancia_estudio(estudios_confirmados),
        "laboral": validar_constancias_laborales(laborales_confirmadas, cfg),
        "alturas": _aplicar_override_manual(validar_certificado_alturas(alturas, cfg), alturas_override),
        "medica": _aplicar_override_manual(validar_evaluacion_medica(medica, cfg), medica_override),
    }
    decision_actualizada = evaluar_admision(resultados_actualizados)

    st.subheader("Decisión con tu revisión")
    estado_final = decision_actualizada["estado_sugerido"]
    clave_final = {"ADMITIDO": "cumple", "NO ADMITIDO": "no_cumple"}.get(estado_final, "requiere_revision_manual")
    texto_final = estado_final + (f" — {decision_actualizada['causal_sugerida']}" if decision_actualizada.get("causal_sugerida") else "")
    st.markdown(_badge_html(clave_final, texto_final), unsafe_allow_html=True)

    st.divider()
    st.subheader("Guardar revisión")
    decision_final = estado_final in ("ADMITIDO", "NO ADMITIDO")
    if not decision_final:
        st.caption("Todavía hay ítems pendientes de confirmar arriba (firma, relacionado, alturas, médica) — resuélvelos para poder guardar una decisión final.")
    revisado_por = st.text_input("Tu nombre (queda registrado en la auditoría)")
    guardar = st.button("Guardar revisión en Google Sheets", type="primary", disabled=not revisado_por or not decision_final)

    if guardar:
        try:
            with st.spinner("Guardando en Google Sheets... si la red está lenta puede tardar; no hagas doble clic ni cambies de aspirante mientras tanto."):
                client = autenticar(str(RAIZ / "service-account.json"))
                spreadsheet = abrir_spreadsheet(client, os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])
                hojas = asegurar_hojas(spreadsheet)

                inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario.get("experiencia", []), laborales_confirmadas, cfg)
                fila_maestro = construir_fila_maestro(
                    formulario, cedula, estudios_confirmados, laborales_confirmadas, alturas, medica,
                    resultados_actualizados, decision_actualizada, [i["detalle"] for i in inconsistencias], cfg,
                )
                # Se llenan directamente las columnas oficiales de decisión — no hay
                # una versión "sugerida" aparte: esto se escribe solo cuando un
                # humano ya confirmó la revisión completa en el panel.
                fila_maestro["admitido_si_no"] = "SI" if decision_actualizada["estado_sugerido"] == "ADMITIDO" else "NO"
                fila_maestro["causal_no_admision"] = decision_actualizada.get("causal_sugerida") or ""
                fila_maestro["estado_confirmado_por_humano"] = decision_actualizada["estado_sugerido"]
                fila_maestro["revisado_por"] = revisado_por
                fila_maestro["fecha_revision"] = date.today().isoformat()

                id_aspirante = cedula.get("numero", "")
                upsert_fila(hojas["Maestro"], MAESTRO, "id_aspirante", id_aspirante, fila_maestro)

                filas_auditoria = [{
                    "id_aspirante": id_aspirante, "campo": "firma_verificada",
                    "valor_extraido_ia": "pendiente", "valor_corregido_humano": firma_verificada,
                    "corregido_por": revisado_por, "fecha_correccion": date.today().isoformat(),
                }]
                if alturas and alturas.get("aportado"):
                    filas_auditoria.append({
                        "id_aspirante": id_aspirante, "campo": "validez_certificado_alturas",
                        "valor_extraido_ia": resultado["resultados_validacion"]["alturas"].estado,
                        "valor_corregido_humano": alturas_override,
                        "corregido_por": revisado_por, "fecha_correccion": date.today().isoformat(),
                    })
                if medica and medica.get("aportado"):
                    filas_auditoria.append({
                        "id_aspirante": id_aspirante, "campo": "validez_evaluacion_medica",
                        "valor_extraido_ia": resultado["resultados_validacion"]["medica"].estado,
                        "valor_corregido_humano": medica_override,
                        "corregido_por": revisado_por, "fecha_correccion": date.today().isoformat(),
                    })
                for i, (exp, d) in enumerate(zip(laborales, decisiones_relacionado_laboral)):
                    filas_auditoria.append({
                        "id_aspirante": id_aspirante, "campo": f"relacionado_laboral_{i}_{exp.get('entidad', '')}",
                        "valor_extraido_ia": exp.get("relacionado_sugerido", ""), "valor_corregido_humano": d,
                        "corregido_por": revisado_por, "fecha_correccion": date.today().isoformat(),
                    })
                agregar_filas(hojas["Auditoría"], AUDITORIA, filas_auditoria)

                # También en la caché local: es lo que usa el selector "Ver" para
                # separar pendientes de admitidos/no admitidos, sin depender de leer
                # Sheets. Se guarda aparte de `resultado` (que ya trae claves propias
                # del panel, como "documentos") para no corromper la caché en disco.
                resultado_cache = cargar_resultado(hash_)
                resultado_cache["estado_confirmado_por_humano"] = decision_actualizada["estado_sugerido"]
                resultado_cache["revisado_por"] = revisado_por
                resultado_cache["fecha_revision"] = date.today().isoformat()
                guardar_resultado(hash_, resultado_cache)

            st.success(f"Revisión guardada. Estado final: {decision_actualizada['estado_sugerido']}")
            st.link_button("Abrir Google Sheet", spreadsheet.url)
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")


if __name__ == "__main__":
    main()
