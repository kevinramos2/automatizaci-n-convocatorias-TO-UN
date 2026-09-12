"""Arma las filas de las hojas auxiliares (Auditoría, Documentos por candidato,

Documentos adicionales, Formación y Experiencia Detallada) a partir de los
resultados de clasificación y extracción ya guardados. Pura transformación de
datos, sin llamadas a la API.
"""
import json

_TIPOS_ADICIONALES = {"libreta_militar", "examen_medico_anexo"}


def construir_filas_auditoria(resultados_clasificacion: list[dict], id_aspirante: str) -> list[dict]:
    """Una fila por página clasificada: qué extrajo la IA y con qué confianza (Sección 4)."""
    return [
        {
            "id_aspirante": id_aspirante,
            "campo": "tipo_documento (página)",
            "valor_extraido_ia": r["tipo"],
            "confianza": r["confianza"],
            "folio_fuente": r["pagina"],
        }
        for r in resultados_clasificacion
    ]


def construir_filas_documentos_candidato(documentos_logicos: list[dict], id_aspirante: str, paginas_blancas: list[int]) -> list[dict]:
    """Una fila por documento lógico (grupo de páginas ya agrupadas), más las páginas

    descartadas como blank=true (trazabilidad — nunca se eliminan del expediente, Sección 2.3).
    """
    filas = [
        {
            "id_aspirante": id_aspirante,
            "paginas": ", ".join(str(p) for p in d["paginas"]),
            "tipo_documento": d.get("tipo_final", d["tipo"]),
            "confianza": ", ".join(d.get("confianzas", [])) if "confianzas" in d else d.get("confianza", ""),
            "motivo": " / ".join(d.get("motivos", [])) if "motivos" in d else d.get("motivo", ""),
            "requiere_reclasificacion": d.get("requiere_reclasificacion", False),
            "tipo_real_sugerido": d.get("tipo_real_sugerido", ""),
            "blank": False,
        }
        for d in documentos_logicos
    ]
    filas += [
        {"id_aspirante": id_aspirante, "paginas": str(p), "tipo_documento": "", "confianza": "", "motivo": "página en blanco (reverso)", "requiere_reclasificacion": False, "tipo_real_sugerido": "", "blank": True}
        for p in paginas_blancas
    ]
    return filas


def construir_filas_documentos_adicionales(resultados_clasificacion: list[dict], id_aspirante: str) -> list[dict]:
    """Páginas clasificadas como libreta militar o exámenes médicos anexos —

    fuera del checklist de admisión, se guardan aparte (Sección 2.2 del plan).
    """
    return [
        {
            "id_aspirante": id_aspirante,
            "tipo": r["tipo"],
            "paginas": r["pagina"],
            "datos_extraidos": "",  # sin prompt de extracción propio todavía — fuera del checklist
        }
        for r in resultados_clasificacion
        if r["tipo"] in _TIPOS_ADICIONALES
    ]


def construir_filas_formacion_experiencia(estudios: list[dict], laborales: list[dict], id_aspirante: str) -> list[dict]:
    """Una fila por cada certificado/curso y cada experiencia laboral (Sección 4:

    'no resumida, no truncada'). Usa los documentos ya verificados (constancia_estudio
    / constancia_laboral extraídos), no el autorreporte del formulario, porque son
    la fuente más confiable de fechas y datos ya validados contra el soporte físico.
    """
    filas = []
    for e in estudios:
        tipo = "Curso-capacitación" if (e.get("nivel") or "").lower() == "curso_capacitacion" else "Educación formal"
        filas.append({
            "id_aspirante": id_aspirante,
            "tipo": tipo,
            "nombre_institucion_o_entidad": e.get("institucion", ""),
            "nombre_curso_o_cargo": e.get("nombre_curso") or e.get("titulo", ""),
            "fecha_inicio": e.get("fecha_inicio", ""),
            "fecha_fin": e.get("fecha_fin") or e.get("fecha_terminacion", ""),
            "duracion_horas_o_meses": e.get("horas", ""),
            "relacionado_con_el_cargo": e.get("relacionado", "PENDIENTE"),
            "folio_fuente": ", ".join(str(p) for p in e.get("paginas", [])),
        })
    for exp in laborales:
        filas.append({
            "id_aspirante": id_aspirante,
            "tipo": "Experiencia independiente" if exp.get("es_declaracion_jurada_independiente") else "Experiencia laboral",
            "nombre_institucion_o_entidad": exp.get("entidad", ""),
            "nombre_curso_o_cargo": exp.get("cargo", ""),
            "fecha_inicio": exp.get("fecha_inicio", ""),
            "fecha_fin": exp.get("fecha_fin", ""),
            "duracion_horas_o_meses": exp.get("meses", ""),
            "relacionado_con_el_cargo": exp.get("relacionado", "PENDIENTE"),
            "folio_fuente": ", ".join(str(p) for p in exp.get("paginas", [])),
        })
    return filas
