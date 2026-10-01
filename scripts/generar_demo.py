"""Genera los 2-3 expedientes 100% inventados que usa el modo demo (DEMO_MODE=1).

No llama a la API de Claude (cero costo): construye a mano los datos "ya
extraídos" (lo que normalmente hace Claude leyendo el PDF) y los hace pasar
por las mismas funciones reales de pipeline/validacion_admision.py, para que
el resultado sea internamente consistente con las reglas reales — no un
mockup aparte que se pueda desincronizar.

El PDF de cada aspirante es generado con PyMuPDF: páginas en blanco con un
rótulo grande tipo "DOCUMENTO DE PRUEBA — FORMULARIO DE INSCRIPCIÓN", nunca
un intento de parecerse a un documento real escaneado.

Uso: python scripts/generar_demo.py
Escribe en demo/cache_demo/ (se commitea: no hay ningún dato real aquí).
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.cache_expedientes import hash_archivo
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.validacion_admision import (
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

RAIZ = Path(__file__).parent.parent
CARPETA_DEMO = RAIZ / "demo" / "cache_demo"
CFG = json.load(open(RAIZ / "config" / "parametros.json", encoding="utf-8"))


def _pdf_de_prueba(etiquetas: list[str]) -> bytes:
    """Una página en blanco por etiqueta, con el texto grande centrado — un marcador de
    posición, nunca un intento de simular un documento real escaneado."""
    doc = fitz.open()
    for etiqueta in etiquetas:
        page = doc.new_page(width=595, height=842)  # tamaño carta
        page.draw_rect(fitz.Rect(20, 20, 575, 822), color=(0.75, 0.75, 0.75), width=2)
        page.insert_textbox(
            fitz.Rect(60, 340, 535, 500),
            f"DOCUMENTO DE PRUEBA\n\n{etiqueta}\n\n(dato inventado, demo pública)",
            fontsize=20, align=1, color=(0.25, 0.25, 0.25),
        )
    datos = doc.tobytes()
    doc.close()
    return datos


def _construir(nombre: str, cedula_num: str, convocatoria: str, formulario_extra: dict,
               cedula_extra: dict, estudios: list[dict], laborales: list[dict],
               alturas: dict, medica: dict, etiquetas_paginas: list[str]) -> dict:
    formulario = {
        "clasificacion_correcta": True,
        "numero_proceso_declarado": convocatoria,
        "cargo_declarado_encabezado": convocatoria,
        "cargo_declarado_requisitos": convocatoria,
        "fecha_inscripcion": "2026-09-10",
        "nombre": nombre,
        "cedula": cedula_num,
        "correo": "aspirante.prueba@ejemplo.test",
        "celular": "3000000000",
        "telefono_fijo": None,
        "direccion": "Calle de prueba # 0-00, Yopal",
        "discapacidad": "No",
        "tipo_discapacidad": None,
        "certificado_alturas_fecha_declarada": alturas.get("fecha_expedicion"),
        "evaluacion_medica_fecha_declarada": medica.get("fecha_expedicion"),
        "educacion_formal": [],
        "educacion_relacionada": [],
        "experiencia": [
            {
                "numero_fila": i + 1,
                "cargo_desempenado": l["cargo"],
                "entidad": l["entidad"],
                "funcion_principal": l["funciones"],
                "fecha_desde": l["fecha_inicio"],
                "fecha_hasta": l["fecha_fin"],
                "total_meses_declarado": None,
            }
            for i, l in enumerate(laborales)
        ],
        "firma_presente": True,
        **formulario_extra,
    }
    cedula = {
        "clasificacion_correcta": True,
        "aportada": True,
        "numero": cedula_num,
        "nombre": nombre,
        "legible": True,
        **cedula_extra,
    }

    resultados = {
        "formulario": validar_formulario(
            {k: formulario.get(k) for k in ("nombre", "cedula", "correo", "celular", "direccion")},
            {"nombre": cedula.get("nombre"), "numero": cedula.get("numero")},
        ),
        "cedula": validar_cedula(cedula),
        "estudio": validar_constancia_estudio([e for e in estudios if (e.get("nivel") or "").lower() in {"primaria", "secundaria"}]),
        "laboral": validar_constancias_laborales(laborales, CFG),
        "alturas": validar_certificado_alturas(alturas, CFG),
        "medica": validar_evaluacion_medica(medica, CFG),
    }
    decision = evaluar_admision(resultados)
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario["experiencia"], laborales, CFG)

    pdf_bytes = _pdf_de_prueba(etiquetas_paginas)
    hash_ = hash_archivo(pdf_bytes)

    documentos_extraidos = [
        {"tipo_final": "formulario_inscripcion", "paginas": [1], "datos": dict(formulario),
         "reclasificado_automaticamente": False, "requiere_revision_tipo": False, "uso": {"input_tokens": 0, "output_tokens": 0}},
        {"tipo_final": "cedula", "paginas": [2], "datos": dict(cedula),
         "reclasificado_automaticamente": False, "requiere_revision_tipo": False, "uso": {"input_tokens": 0, "output_tokens": 0}},
    ]

    resultado = {
        "paginas_blancas": [],
        "clasificacion": [],
        "documentos_logicos": [],
        "documentos_extraidos": documentos_extraidos,
        "formulario": formulario,
        "cedula": cedula,
        "estudios": estudios,
        "laborales": laborales,
        "alturas": alturas,
        "medica": medica,
        "resultados_validacion": resultados,
        "decision": decision,
        "inconsistencias": inconsistencias,
        "uso_total": {"input_tokens": 0, "output_tokens": 0},
        "convocatoria": convocatoria,
        "rotacion": 0,
        "rotaciones_paginas": {},
    }
    return hash_, pdf_bytes, resultado


def _guardar(hash_: str, pdf_bytes: bytes, resultado: dict) -> None:
    CARPETA_DEMO.mkdir(parents=True, exist_ok=True)
    (CARPETA_DEMO / f"{hash_}.pdf").write_bytes(pdf_bytes)
    serializable = dict(resultado)
    serializable["resultados_validacion"] = {k: asdict(v) for k, v in resultado["resultados_validacion"].items()}
    with open(CARPETA_DEMO / f"{hash_}_resultado.json", "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def main():
    for f in CARPETA_DEMO.glob("*"):
        f.unlink()

    # --- Aspirante 1: todo en regla → si el revisor confirma cada ítem, ADMITIDO.
    hash_, pdf_bytes, resultado = _construir(
        nombre="ASPIRANTE DE PRUEBA UNO", cedula_num="1000000001", convocatoria="TO-01",
        formulario_extra={}, cedula_extra={},
        estudios=[
            {"clasificacion_correcta": True, "institucion": "Institución Educativa de Prueba", "titulo": "Bachiller Académico",
             "ultimo_anio_cursado": "11", "nivel": "secundaria", "es_boletin": False, "nombre_curso": None, "horas": None,
             "fecha_inicio": None, "fecha_fin": "2010-12-01", "paginas": [3],
             "relacionado_sugerido": None, "justificacion_relacionado": None, "relacionado": "PENDIENTE"},
            {"clasificacion_correcta": True, "institucion": "SENA (de prueba)", "titulo": None,
             "ultimo_anio_cursado": None, "nivel": "curso_capacitacion", "es_boletin": False, "nombre_curso": "Jardinería y paisajismo",
             "horas": 220, "fecha_inicio": "2024-01-10", "fecha_fin": "2024-03-10", "paginas": [4],
             "relacionado_sugerido": "SI", "justificacion_relacionado": "El curso es de jardinería, directamente relacionado con el cargo.",
             "relacionado": "PENDIENTE"},
        ],
        laborales=[
            {"clasificacion_correcta": True, "entidad": "Vivero de Prueba S.A.S.", "cargo": "Auxiliar de jardinería",
             "jornada": None, "fecha_inicio": "2023-01-15", "fecha_fin": "2024-12-15",
             "funciones": "Siembra, poda y mantenimiento de zonas verdes (dato de prueba).",
             "firmada_jefe": True, "es_declaracion_jurada_independiente": False, "notariada": None, "formato_valido": True,
             "paginas": [5], "relacionado_sugerido": "SI",
             "justificacion_relacionado": "Cargo y funciones directamente relacionados con jardinería.", "relacionado": "PENDIENTE"},
        ],
        alturas={"clasificacion_correcta": True, "aportado": True, "entidad_emisora": "Centro de Prueba de Alturas",
                 "fecha_expedicion": "2026-06-01", "fecha_vencimiento": "2027-06-01", "paginas": [6]},
        medica={"clasificacion_correcta": True, "aportado": True, "entidad_emisora": "IPS de Prueba",
                "fecha_expedicion": "2026-09-01", "concepto_aptitud_alturas": True,
                "es_certificado_preingreso_general": False, "paginas": [7]},
        etiquetas_paginas=[
            "Formulario de inscripción", "Fotocopia de cédula", "Diploma de bachiller",
            "Certificado curso SENA (jardinería)", "Constancia laboral — Vivero de Prueba",
            "Certificado de alturas", "Evaluación médica ocupacional",
        ],
    )
    _guardar(hash_, pdf_bytes, resultado)
    print(f"Aspirante 1 (todo en regla)        -> {hash_}")

    # --- Aspirante 2: sin certificado de alturas y con poca experiencia → NO ADMITIDO
    #     pase lo que pase en la revisión (demuestra que el sistema no deja admitir
    #     por debajo del mínimo, aunque el revisor confirme todo lo demás).
    hash_, pdf_bytes, resultado = _construir(
        nombre="ASPIRANTE DE PRUEBA DOS", cedula_num="1000000002", convocatoria="TO-02",
        formulario_extra={}, cedula_extra={},
        estudios=[
            {"clasificacion_correcta": True, "institucion": "Colegio de Prueba", "titulo": "Bachiller Técnico",
             "ultimo_anio_cursado": "11", "nivel": "secundaria", "es_boletin": False, "nombre_curso": None, "horas": None,
             "fecha_inicio": None, "fecha_fin": "2015-12-01", "paginas": [3],
             "relacionado_sugerido": None, "justificacion_relacionado": None, "relacionado": "PENDIENTE"},
        ],
        laborales=[
            {"clasificacion_correcta": True, "entidad": "Constructora de Prueba Ltda.", "cargo": "Ayudante de obra",
             "jornada": None, "fecha_inicio": "2026-01-01", "fecha_fin": "2026-08-30",
             "funciones": "Apoyo general en obra (dato de prueba).",
             "firmada_jefe": True, "es_declaracion_jurada_independiente": False, "notariada": None, "formato_valido": True,
             "paginas": [4], "relacionado_sugerido": "SI",
             "justificacion_relacionado": "Cargo relacionado, pero no alcanza el mínimo de 12 meses.", "relacionado": "PENDIENTE"},
        ],
        alturas={"clasificacion_correcta": True, "aportado": False, "entidad_emisora": None,
                 "fecha_expedicion": None, "fecha_vencimiento": None, "paginas": []},
        medica={"clasificacion_correcta": True, "aportado": False, "entidad_emisora": None,
                "fecha_expedicion": None, "concepto_aptitud_alturas": None,
                "es_certificado_preingreso_general": False, "paginas": []},
        etiquetas_paginas=[
            "Formulario de inscripción", "Fotocopia de cédula", "Diploma de bachiller",
            "Constancia laboral — Constructora de Prueba",
        ],
    )
    _guardar(hash_, pdf_bytes, resultado)
    print(f"Aspirante 2 (alturas sin aportar)   -> {hash_}")

    # --- Aspirante 3: el mínimo de experiencia depende de que el revisor marque como
    #     relacionada o no la segunda constancia — el resultado final queda en sus manos.
    hash_, pdf_bytes, resultado = _construir(
        nombre="ASPIRANTE DE PRUEBA TRES", cedula_num="1000000003", convocatoria="TO-01",
        formulario_extra={}, cedula_extra={},
        estudios=[
            {"clasificacion_correcta": True, "institucion": "Institución Educativa de Prueba 2", "titulo": "Bachiller Académico",
             "ultimo_anio_cursado": "11", "nivel": "secundaria", "es_boletin": False, "nombre_curso": None, "horas": None,
             "fecha_inicio": None, "fecha_fin": "2012-12-01", "paginas": [3],
             "relacionado_sugerido": None, "justificacion_relacionado": None, "relacionado": "PENDIENTE"},
        ],
        laborales=[
            {"clasificacion_correcta": True, "entidad": "Jardines de Prueba", "cargo": "Jardinero",
             "jornada": None, "fecha_inicio": "2025-01-01", "fecha_fin": "2025-09-01",
             "funciones": "Mantenimiento de zonas verdes (dato de prueba).",
             "firmada_jefe": True, "es_declaracion_jurada_independiente": False, "notariada": None, "formato_valido": True,
             "paginas": [4], "relacionado_sugerido": "SI",
             "justificacion_relacionado": "Cargo igual al del cargo al que aspira.", "relacionado": "PENDIENTE"},
            {"clasificacion_correcta": True, "entidad": "Servicios Generales de Prueba", "cargo": "Operario de aseo general",
             "jornada": None, "fecha_inicio": "2024-06-01", "fecha_fin": "2024-12-01",
             "funciones": "Aseo y mantenimiento locativo general, incluye zonas verdes ocasionalmente (dato de prueba).",
             "firmada_jefe": True, "es_declaracion_jurada_independiente": False, "notariada": None, "formato_valido": True,
             "paginas": [5], "relacionado_sugerido": "PENDIENTE",
             "justificacion_relacionado": "Las funciones mencionan zonas verdes solo de forma ocasional — no está claro que sea el foco del cargo; conviene que lo confirme el revisor.",
             "relacionado": "PENDIENTE"},
        ],
        alturas={"clasificacion_correcta": True, "aportado": True, "entidad_emisora": "Centro de Prueba de Alturas",
                 "fecha_expedicion": "2026-07-01", "fecha_vencimiento": "2027-07-01", "paginas": [6]},
        medica={"clasificacion_correcta": True, "aportado": True, "entidad_emisora": "IPS de Prueba 2",
                "fecha_expedicion": "2026-09-05", "concepto_aptitud_alturas": True,
                "es_certificado_preingreso_general": False, "paginas": [7]},
        etiquetas_paginas=[
            "Formulario de inscripción", "Fotocopia de cédula", "Diploma de bachiller",
            "Constancia laboral — Jardines de Prueba", "Constancia laboral — Servicios Generales de Prueba",
            "Certificado de alturas", "Evaluación médica ocupacional",
        ],
    )
    _guardar(hash_, pdf_bytes, resultado)
    print(f"Aspirante 3 (depende del revisor)  -> {hash_}")

    print(f"\nListo: {CARPETA_DEMO}")


if __name__ == "__main__":
    main()
