"""Panel de revisión humana (Fase 5 del plan).

Muestra, para un aspirante, el estado de cada ítem del checklist junto a la
página fuente, permite confirmar la firma y la clasificación "relacionado con
el cargo" de cada curso/experiencia, y guarda la revisión en Google Sheets
(Auditoría + Maestro). Nada se publica como ADMITIDO/NO ADMITIDO sin que la
persona revisora guarde explícitamente desde aquí.

Uso: streamlit run app_revision.py
"""
import base64
import json
import os
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from pipeline.cargar_legajo_guardado import cargar_resultado_desde_json
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.esquema_sheets import AUDITORIA, MAESTRO
from pipeline.mapeo_maestro import construir_fila_maestro
from pipeline.pdf_utils import pagina_a_imagen_base64
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


@st.cache_data
def _imagen_pagina(pdf_path: str, pagina: int) -> bytes:
    return base64.standard_b64decode(pagina_a_imagen_base64(pdf_path, pagina, dpi=150))


@st.cache_data
def _cargar_todo():
    cfg = json.load(open(RAIZ / "config" / "parametros.json", encoding="utf-8"))
    extraccion_path = RAIZ / "data-ejemplo" / "extraccion-legajo-01.json"
    relacionado_path = RAIZ / "data-ejemplo" / "relacionado-legajo-01.json"
    resultado = cargar_resultado_desde_json(str(extraccion_path), cfg, str(relacionado_path))
    extracciones_crudas = json.load(open(extraccion_path, encoding="utf-8"))
    return cfg, resultado, extracciones_crudas


def _paginas_de(extracciones_crudas, tipo):
    coincidencias = [e["paginas"] for e in extracciones_crudas if e["tipo"] == tipo]
    return coincidencias[0] if coincidencias else []


def _badge(estado: str, texto: str):
    getattr(st, _COLOR_ESTADO.get(estado, "info"))(texto)


def main():
    cfg, resultado, extracciones_crudas = _cargar_todo()
    pdf_path = str(RAIZ / "data-ejemplo" / "legajo-ejemplo-01.pdf")

    formulario = resultado["formulario"]
    cedula = resultado["cedula"]
    estudios = resultado["estudios"]
    laborales = resultado["laborales"]
    alturas = resultado["alturas"]
    medica = resultado["medica"]

    st.title("Panel de revisión — Proceso TO-02 de 2026")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Aspirante", formulario.get("nombre", "—"))
    col_b.metric("Cédula", cedula.get("numero", "—"))
    col_c.metric("Estado sugerido", resultado["decision"]["estado_sugerido"])

    if resultado["inconsistencias"]:
        with st.expander(f"⚠️ {len(resultado['inconsistencias'])} inconsistencia(s) detectada(s) automáticamente", expanded=True):
            for inc in resultado["inconsistencias"]:
                st.warning(inc["detalle"])

    st.divider()

    # --- Resumen de los 6 ítems ---
    st.subheader("Checklist de admisión")
    for clave, r in resultado["resultados_validacion"].items():
        _badge(r.estado, f"**{_ETIQUETA_ITEM.get(clave, clave)}** — {r.estado.upper()}: {r.motivo}")

    st.divider()

    # --- Confirmación de firma (ítem 1) ---
    st.subheader("Confirmar firma del formulario")
    st.caption("Compara la firma de abajo (formulario) contra la firma de la cédula. Nunca se verifica automáticamente.")
    col_firma_1, col_firma_2 = st.columns(2)
    paginas_formulario = _paginas_de(extracciones_crudas, "formulario_inscripcion")
    paginas_cedula = _paginas_de(extracciones_crudas, "cedula")
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
        options=["Pendiente", "Sí coincide", "No coincide"],
        horizontal=True,
        key="firma_verificada",
    )
    firma_valor = {"Pendiente": None, "Sí coincide": True, "No coincide": False}[firma_verificada]

    st.divider()

    # --- Confirmación de "relacionado con el cargo" ---
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

    # --- Recalcular con las confirmaciones del revisor ---
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
                "id_aspirante": id_aspirante,
                "campo": "firma_verificada",
                "valor_extraido_ia": "pendiente",
                "valor_corregido_humano": firma_verificada,
                "corregido_por": revisado_por,
                "fecha_correccion": date.today().isoformat(),
            }]
            for i, (exp, d) in enumerate(zip(laborales, decisiones_relacionado_laboral)):
                filas_auditoria.append({
                    "id_aspirante": id_aspirante,
                    "campo": f"relacionado_laboral_{i}_{exp.get('entidad', '')}",
                    "valor_extraido_ia": exp.get("relacionado_sugerido", ""),
                    "valor_corregido_humano": d,
                    "corregido_por": revisado_por,
                    "fecha_correccion": date.today().isoformat(),
                })
            agregar_filas(hojas["Auditoría"], AUDITORIA, filas_auditoria)

            st.success(f"Revisión guardada. Estado final: {decision_actualizada['estado_sugerido']}")
            st.link_button("Abrir Google Sheet", spreadsheet.url)
        except Exception as exc:
            st.error(f"No se pudo guardar: {exc}")


if __name__ == "__main__":
    main()
