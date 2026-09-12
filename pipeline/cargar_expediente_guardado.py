"""Reconstruye el resultado completo de un expediente (validación + consistencia)

a partir de los JSON de clasificación/extracción ya guardados en disco — sin
volver a llamar a la API de Claude. Usado por el panel de revisión (Fase 5).
"""
import json

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


def _por_tipo(extracciones: list[dict], tipo: str) -> list[dict]:
    return [e for e in extracciones if e["tipo"] == tipo]


def cargar_resultado_desde_json(extraccion_path: str, cfg: dict, relacionado_path: str | None = None) -> dict:
    with open(extraccion_path, encoding="utf-8") as f:
        extracciones = json.load(f)

    sugerencias_relacionado = {}
    if relacionado_path:
        with open(relacionado_path, encoding="utf-8") as f:
            sugerencias_relacionado = {r["id"]: r for r in json.load(f)}

    formulario = _por_tipo(extracciones, "formulario_inscripcion")[0]["datos"]
    cedula = _por_tipo(extracciones, "cedula")[0]["datos"]
    estudios = [
        {**e["datos"], "paginas": e["paginas"]}
        for e in _por_tipo(extracciones, "constancia_estudio") if not e.get("requiere_reclasificacion")
    ]
    laborales = [
        {**e["datos"], "paginas": e["paginas"], "relacionado": "PENDIENTE"}
        for e in _por_tipo(extracciones, "constancia_laboral")
    ]
    for i, e in enumerate(laborales):
        sugerencia = sugerencias_relacionado.get(f"laboral_{i}")
        if sugerencia:
            e["relacionado_sugerido"] = sugerencia["relacionado_sugerido"]
            e["justificacion_relacionado"] = sugerencia["justificacion"]
    for e in estudios:
        e.setdefault("relacionado", "PENDIENTE")

    alturas_docs = [
        {**e["datos"], "paginas": e["paginas"]}
        for e in _por_tipo(extracciones, "certificado_alturas") if not e.get("requiere_reclasificacion")
    ]
    alturas = alturas_docs[0] if alturas_docs else None
    medica = _por_tipo(extracciones, "evaluacion_medica")[0]["datos"]

    resultados_validacion = {
        "formulario": validar_formulario(
            {k: formulario.get(k) for k in ("nombre", "cedula", "correo", "celular", "direccion")},
            {"nombre": cedula.get("nombre"), "numero": cedula.get("numero")},
            firma_verificada=None,
        ),
        "cedula": validar_cedula(cedula),
        "estudio": validar_constancia_estudio(estudios),
        "laboral": validar_constancias_laborales(laborales, cfg),
        "alturas": validar_certificado_alturas(alturas, cfg),
        "medica": validar_evaluacion_medica(medica, cfg),
    }
    decision = evaluar_admision(resultados_validacion)
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario.get("experiencia", []), laborales, cfg)

    return {
        "formulario": formulario,
        "cedula": cedula,
        "estudios": estudios,
        "laborales": laborales,
        "alturas": alturas,
        "medica": medica,
        "resultados_validacion": resultados_validacion,
        "decision": decision,
        "inconsistencias": inconsistencias,
    }
