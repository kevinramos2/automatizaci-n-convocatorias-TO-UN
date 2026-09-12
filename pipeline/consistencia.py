"""Cruce de consistencia entre el formulario y los soportes aportados (Sección 7, paso 7).

El cruce de nombre/cédula (formulario vs. fotocopia de cédula) ya vive dentro de
`validar_formulario` en validacion_admision.py, porque es parte del ítem 1 del
checklist. Este módulo cubre cruces que NO corresponden a un solo ítem del
checklist sino que comparan el formulario contra otros documentos — hoy: las
fechas de experiencia declaradas por el aspirante contra las que dicen las
constancias laborales oficiales.

No cambia ningún estado cumple/no_cumple por sí mismo: solo produce banderas de
inconsistencia para que el revisor humano las vea (igual criterio que el resto
del pipeline — nunca se descarta ni se decide en silencio).
"""
import re
import unicodedata

from pipeline.fechas import parse_fecha

_STOPWORDS_ENTIDAD = {
    "DE", "LA", "EL", "LOS", "LAS", "Y", "EN", "SEDE", "SAS", "S", "A", "LTDA", "LTD",
    "EMPRESA", "COMPANIA", "CIA", "ENTIDAD", "",
}


def _tokens_entidad(nombre: str) -> set[str]:
    sin_tildes = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode("ascii")
    palabras = re.split(r"[^A-Za-z0-9]+", sin_tildes.upper())
    return {p for p in palabras if p and p not in _STOPWORDS_ENTIDAD}


def _entidades_coinciden(a: str, b: str, umbral: float) -> bool:
    ta, tb = _tokens_entidad(a), _tokens_entidad(b)
    if not ta or not tb:
        return False
    interseccion = ta & tb
    return len(interseccion) / min(len(ta), len(tb)) >= umbral


def cruzar_experiencia_formulario_vs_constancias(
    experiencia_formulario: list[dict],
    constancias_laborales: list[dict],
    cfg: dict,
) -> list[dict]:
    """Compara cada fila de experiencia del formulario contra la constancia laboral

    de la misma entidad (emparejadas por nombre de entidad, no por posición —
    el orden en el formulario y el orden de las constancias en el legajo no
    tienen por qué coincidir). Devuelve una lista de inconsistencias encontradas;
    lista vacía significa que todo coincidió dentro de la tolerancia configurada.
    """
    cfg_cruce = cfg["cruce_consistencia"]
    tolerancia_dias = cfg_cruce["tolerancia_dias_fechas_experiencia"]
    umbral_entidad = cfg_cruce["umbral_coincidencia_entidad"]

    inconsistencias = []
    for exp in experiencia_formulario:
        entidad_form = exp.get("entidad") or ""
        candidatos = [c for c in constancias_laborales if _entidades_coinciden(entidad_form, c.get("entidad") or "", umbral_entidad)]

        if not candidatos:
            inconsistencias.append({
                "tipo": "sin_constancia_correspondiente",
                "entidad_formulario": entidad_form,
                "detalle": f"El formulario declara experiencia en '{entidad_form}' pero ninguna "
                           "constancia laboral aportada corresponde a esa entidad.",
            })
            continue

        constancia = candidatos[0]
        for campo_form, campo_const, etiqueta in (
            ("fecha_desde", "fecha_inicio", "fecha de inicio"),
            ("fecha_hasta", "fecha_fin", "fecha de fin"),
        ):
            val_form = exp.get(campo_form)
            val_const = constancia.get(campo_const)
            if val_form is None or val_const is None:
                continue  # no se puede comparar si falta alguno de los dos lados

            diferencia_dias = abs((parse_fecha(val_form) - parse_fecha(val_const)).days)
            if diferencia_dias > tolerancia_dias:
                inconsistencias.append({
                    "tipo": "fecha_no_coincide",
                    "entidad_formulario": entidad_form,
                    "entidad_constancia": constancia.get("entidad"),
                    "campo": etiqueta,
                    "valor_formulario": val_form,
                    "valor_constancia": val_const,
                    "diferencia_dias": diferencia_dias,
                    "detalle": f"En '{entidad_form}', la {etiqueta} declarada en el formulario ({val_form}) "
                               f"difiere {diferencia_dias} días de la constancia laboral ({val_const}).",
                })

    return inconsistencias
