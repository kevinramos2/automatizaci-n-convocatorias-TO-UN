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

from pipeline.cache_expedientes import cargar_resultado, existe_en_cache, guardar_pdf, guardar_resultado, hash_archivo, ruta_pdf
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.esquema_sheets import AUDITORIA, MAESTRO
from pipeline.mapeo_maestro import construir_fila_maestro
from pipeline.pdf_utils import pagina_a_imagen_base64
from pipeline.procesar_expediente import procesar_expediente
from pipeline.sheets_client import abrir_spreadsheet, agregar_filas, asegurar_hojas, autenticar, upsert_fila
from pipeline.validacion_admision import (
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

_COLOR_ESTADO = {"cumple": "success", "requiere_revision_manual": "warning", "no_cumple": "error"}
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


@st.cache_data
def _imagen_pagina(pdf_path: str, pagina: int) -> bytes:
    return base64.standard_b64decode(pagina_a_imagen_base64(pdf_path, pagina, dpi=150))


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


def _badge(estado: str, texto: str):
    getattr(st, _COLOR_ESTADO.get(estado, "info"))(texto)


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


def _barra_lateral(cfg: dict) -> dict | None:
    st.sidebar.title("Proceso de selección TO 2026")
    convocatoria_id = st.sidebar.selectbox(
        "Convocatoria", options=list(_CONVOCATORIAS), format_func=lambda k: _CONVOCATORIAS[k]["etiqueta"],
    )
    criterios = json.load(open(RAIZ / _CONVOCATORIAS[convocatoria_id]["criterios"], encoding="utf-8"))

    st.sidebar.divider()
    fuente = st.sidebar.radio("Expediente a revisar", ["Subir un expediente nuevo", "Expediente de ejemplo (ya procesado, gratis)"])

    if fuente == "Expediente de ejemplo (ya procesado, gratis)":
        from pipeline.cargar_expediente_guardado import cargar_resultado_desde_json
        extraccion_path = RAIZ / "data-ejemplo" / "extraccion-expediente-01.json"
        if not extraccion_path.exists():
            st.sidebar.warning("No hay expediente de ejemplo guardado en este equipo.")
            return None
        resultado = cargar_resultado_desde_json(str(extraccion_path), cfg, str(RAIZ / "data-ejemplo" / "relacionado-expediente-01.json"))
        extracciones_crudas = json.load(open(extraccion_path, encoding="utf-8"))
        resultado["pdf_path"] = str(RAIZ / "data-ejemplo" / "expediente-ejemplo-01.pdf")
        resultado["documentos"] = [{"tipo": e["tipo"], "paginas": e["paginas"], "datos": e["datos"]} for e in extracciones_crudas if not e.get("requiere_reclasificacion")]
        return resultado

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


def main():
    cfg = _cargar_cfg()
    resultado = _barra_lateral(cfg)

    if resultado is None:
        st.title("Panel de revisión — Proceso de selección TO 2026")
        st.info("Elige la convocatoria y un expediente en la barra lateral para comenzar.")
        return

    pdf_path = resultado["pdf_path"]
    documentos = resultado["documentos"]
    formulario = resultado["formulario"]
    cedula = resultado["cedula"]
    estudios = resultado["estudios"]
    laborales = resultado["laborales"]
    alturas = resultado["alturas"]
    medica = resultado["medica"]

    st.title("Panel de revisión — Proceso de selección TO 2026")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Aspirante", formulario.get("nombre", "—"))
    col_b.metric("Cédula", cedula.get("numero", "—"))
    col_c.metric("Estado sugerido", resultado["decision"]["estado_sugerido"])

    if resultado["inconsistencias"]:
        with st.expander(f"{len(resultado['inconsistencias'])} inconsistencia(s) detectada(s) automáticamente", expanded=True):
            for inc in resultado["inconsistencias"]:
                st.warning(inc["detalle"])

    st.divider()
    st.subheader("Checklist de admisión")
    for clave, r in resultado["resultados_validacion"].items():
        _badge(r.estado, f"**{_ETIQUETA_ITEM.get(clave, clave)}** — {r.estado.upper()}: {r.motivo}")

    st.divider()
    st.subheader("Confirmar firma del formulario")
    st.caption("Compara la firma de abajo (formulario) contra la firma de la cédula. Nunca se verifica automáticamente.")
    col_firma_1, col_firma_2 = st.columns(2)
    paginas_formulario = _paginas_de(documentos, "formulario_inscripcion")
    paginas_cedula = _paginas_de(documentos, "cedula")
    with col_firma_1:
        st.caption("Formulario (última página, donde firma)")
        if paginas_formulario:
            st.image(_imagen_pagina(pdf_path, paginas_formulario[-1]))
    with col_firma_2:
        st.caption("Cédula")
        if paginas_cedula:
            st.image(_imagen_pagina(pdf_path, paginas_cedula[0]))

    firma_verificada = st.radio(
        "¿La firma del formulario coincide con la de la cédula?",
        options=["Pendiente", "Sí coincide", "No coincide"], horizontal=True, key="firma_verificada",
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
                    st.info(f"Sugerencia de la IA: **{sugerido}** — {exp.get('justificacion_relacionado', '')}")
                opciones = ["PENDIENTE", "SI", "NO"]
                indice_defecto = opciones.index(sugerido) if sugerido in opciones else 0
                eleccion = st.radio("¿Relacionada con el cargo?", opciones, index=indice_defecto, horizontal=True, key=f"laboral_rel_{i}")
                decisiones_relacionado_laboral.append(eleccion)
            with col_img:
                if exp.get("paginas"):
                    st.image(_imagen_pagina(pdf_path, exp["paginas"][0]))

    decisiones_relacionado_estudio = []
    for i, e in enumerate(estudios):
        if (e.get("nivel") or "").lower() != "curso_capacitacion":
            decisiones_relacionado_estudio.append(e.get("relacionado", "PENDIENTE"))
            continue
        with st.container(border=True):
            st.markdown(f"**Curso:** {e.get('nombre_curso', '—')} — *{e.get('institucion', '—')}*")
            sugerido = e.get("relacionado_sugerido")
            if sugerido:
                st.info(f"Sugerencia de la IA: **{sugerido}** — {e.get('justificacion_relacionado', '')}")
            opciones = ["PENDIENTE", "SI", "NO"]
            indice_defecto = opciones.index(sugerido) if sugerido in opciones else 0
            eleccion = st.radio("¿Relacionado con el cargo?", opciones, index=indice_defecto, horizontal=True, key=f"estudio_rel_{i}")
            decisiones_relacionado_estudio.append(eleccion)

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
        "alturas": validar_certificado_alturas(alturas, cfg),
        "medica": validar_evaluacion_medica(medica, cfg),
    }
    decision_actualizada = evaluar_admision(resultados_actualizados)

    st.subheader("Decisión con tu revisión")
    _badge(
        "cumple" if decision_actualizada["estado_sugerido"] == "ADMITIDO"
        else "no_cumple" if decision_actualizada["estado_sugerido"] == "NO ADMITIDO"
        else "requiere_revision_manual",
        f"**{decision_actualizada['estado_sugerido']}**" + (f" — {decision_actualizada['causal_sugerida']}" if decision_actualizada.get("causal_sugerida") else ""),
    )

    st.divider()
    st.subheader("Guardar revisión")
    revisado_por = st.text_input("Tu nombre (queda registrado en la auditoría)")
    guardar = st.button("Guardar revisión en Google Sheets", type="primary", disabled=not revisado_por)

    if guardar:
        try:
            client = autenticar(str(RAIZ / "service-account.json"))
            spreadsheet = abrir_spreadsheet(client, os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])
            hojas = asegurar_hojas(spreadsheet)

            inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario.get("experiencia", []), laborales_confirmadas, cfg)
            fila_maestro = construir_fila_maestro(
                formulario, cedula, estudios_confirmados, laborales_confirmadas, alturas, medica,
                resultados_actualizados, decision_actualizada, [i["detalle"] for i in inconsistencias], cfg,
            )
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
            for i, (exp, d) in enumerate(zip(laborales, decisiones_relacionado_laboral)):
                filas_auditoria.append({
                    "id_aspirante": id_aspirante, "campo": f"relacionado_laboral_{i}_{exp.get('entidad', '')}",
                    "valor_extraido_ia": exp.get("relacionado_sugerido", ""), "valor_corregido_humano": d,
                    "corregido_por": revisado_por, "fecha_correccion": date.today().isoformat(),
                })
            agregar_filas(hojas["Auditoría"], AUDITORIA, filas_auditoria)

            st.success(f"Revisión guardada. Estado final: {decision_actualizada['estado_sugerido']}")
            st.link_button("Abrir Google Sheet", spreadsheet.url)
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")


if __name__ == "__main__":
    main()
