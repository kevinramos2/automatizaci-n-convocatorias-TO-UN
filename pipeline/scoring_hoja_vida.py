"""Motor de scoring de hoja de vida (10% final) — Sección 6 del plan.

Se construye desde ya (mismos datos extraídos en la admisión) pero solo se
EJECUTA cuando el aspirante ya superó prueba práctica y prueba teórica
(gate de la Sección 6.3). El cálculo es una fórmula determinística, sin
costo de API — la clasificación semántica "relacionado con el cargo" ya
debe venir resuelta en los datos de entrada (Sección 6.1, prompt aparte).

Interpretación de la fórmula de educación (confirmada con el usuario el
2026-09-11, ver nota en el plan Sección 6.2): cada certificado se puntúa
individualmente por sus propias horas contra la tabla de bandas, y esos
puntajes se SUMAN con tope en 50 — no se suman las horas primero. Es la
única lectura consistente con "máximo 50 puntos", ya que la tabla de
bandas por sí sola solo llega a 25.
"""
from pipeline.fechas import meses_entre, parse_fecha

APROBADO = "aprobado"


def _puntos_por_horas(horas: float, bandas: list[dict]) -> int:
    for banda in sorted(bandas, key=lambda b: b["horas_min"], reverse=True):
        if horas >= banda["horas_min"] and (banda["horas_max"] is None or horas <= banda["horas_max"]):
            return banda["puntos"]
    return 0


def calcular_puntaje_educacion(certificados: list[dict], cfg: dict) -> dict:
    """certificados: [{institucion, nombre_curso, horas, relacionado: 'SI'/'NO'/'PENDIENTE'}, ...]"""
    relacionados = [c for c in certificados if c.get("relacionado") == "SI"]
    max_cert = cfg["max_certificados_educacion_relacionada"]
    considerados = relacionados[:max_cert]

    puntos_por_certificado = [_puntos_por_horas(c["horas"], cfg["bandas_puntaje_educacion"]) for c in considerados]
    total = min(sum(puntos_por_certificado), cfg["tope_puntos_educacion"])

    return {
        "puntaje": total,
        "certificados_considerados": len(considerados),
        "certificados_excedentes_no_contados": max(len(relacionados) - max_cert, 0),
        "detalle_por_certificado": puntos_por_certificado,
    }


def calcular_puntaje_experiencia(experiencias: list[dict], cfg: dict) -> dict:
    """experiencias: [{fecha_inicio, fecha_fin, relacionado: 'SI'/'NO'/'PENDIENTE'}, ...]

    1 punto por cada mes completo de experiencia relacionada ADICIONAL al
    mínimo ya exigido para admisión (Sección 6.2, Nota "adicional al requisito mínimo").
    """
    relacionadas = [e for e in experiencias if e.get("relacionado") == "SI"]
    meses_totales = sum(meses_entre(parse_fecha(e["fecha_inicio"]), parse_fecha(e["fecha_fin"])) for e in relacionadas)

    meses_adicionales = max(meses_totales - cfg["experiencia_minima_meses"], 0)
    puntos = min(meses_adicionales * cfg["puntos_por_mes_experiencia_adicional"], cfg["tope_puntos_experiencia"])

    return {
        "puntaje": puntos,
        "meses_relacionados_totales": meses_totales,
        "meses_adicionales_al_minimo": meses_adicionales,
    }


def calcular_puntaje_hoja_vida(certificados: list[dict], experiencias: list[dict], cfg: dict) -> dict:
    educacion = calcular_puntaje_educacion(certificados, cfg)
    experiencia = calcular_puntaje_experiencia(experiencias, cfg)
    return {
        "puntaje_educacion": educacion["puntaje"],
        "puntaje_experiencia": experiencia["puntaje"],
        "puntaje_total": educacion["puntaje"] + experiencia["puntaje"],
        "detalle_educacion": educacion,
        "detalle_experiencia": experiencia,
    }


def puede_calcularse_puntaje(resultado_prueba_practica: str | None, resultado_prueba_teorica: str | None) -> bool:
    """Gate de la Sección 6.3: el cálculo no corre al admitir, solo cuando ambas pruebas están aprobadas."""
    return resultado_prueba_practica == APROBADO and resultado_prueba_teorica == APROBADO
