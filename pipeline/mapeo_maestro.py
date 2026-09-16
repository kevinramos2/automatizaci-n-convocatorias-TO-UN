"""Arma la fila de la hoja 'Maestro' a partir de los datos ya extraídos/validados.

No llama a la API — es pura transformación de datos. Deliberadamente deja en
blanco cualquier campo que el plan marca como decisión o verificación humana
(ADMITIDO SI/NO, causal oficial, verificación en MinTrabajo, coincidencia con
MinTrabajo, confirmación de revisión): la fila que escribe el pipeline sugiere,
nunca decide ni publica (Sección 1 del plan).
"""
from pipeline.fechas import fecha_fin_efectiva, meses_entre, parse_fecha

_NIVELES_PRIMARIA = {"primaria"}
_NIVELES_BACHILLER_O_SUPERIOR = {"secundaria", "tecnico", "tecnologo", "profesional", "especializacion", "maestria", "doctorado"}


def _si_no(valor: bool) -> str:
    return "SI" if valor else "NO"


def _folios(paginas: list[int]) -> str:
    return ", ".join(str(p) for p in paginas) if paginas else ""


def construir_fila_maestro(
    formulario: dict,
    cedula: dict,
    estudios: list[dict],  # cada uno con "paginas" agregado por el llamador
    laborales: list[dict],  # cada uno con "paginas" y "relacionado" agregados por el llamador
    alturas: dict | None,  # ya filtrado al certificado válido, con "paginas"
    medica: dict,
    resultados_validacion: dict,  # el dict de ResultadoRegla por ítem, de evaluar_admision
    decision: dict,  # el resultado de evaluar_admision
    consistencia_observaciones: list[str],
    cfg: dict,
) -> dict:
    fila = {}

    # --- Identificación ---
    fila["fecha_inscripcion"] = formulario.get("fecha_inscripcion", "")
    fila["nombre_aspirante"] = cedula.get("nombre") or formulario.get("nombre", "")
    fila["id_aspirante"] = cedula.get("numero") or formulario.get("cedula", "")
    fila["correo_electronico"] = formulario.get("correo", "")
    fila["celular"] = formulario.get("celular", "")
    fila["observaciones"] = " | ".join(consistencia_observaciones) if consistencia_observaciones else ""

    # --- Educación (RM = requisito mínimo) ---
    tiene_primaria = any((e.get("nivel") or "").lower() in _NIVELES_PRIMARIA for e in estudios)
    entrada_bachiller_o_superior = next((e for e in estudios if (e.get("nivel") or "").lower() in _NIVELES_BACHILLER_O_SUPERIOR), None)
    fila["aporta_cert_primaria"] = _si_no(tiene_primaria)
    fila["fecha_terminacion_primaria"] = next(
        (e.get("fecha_terminacion") or e.get("fecha_fin") for e in estudios if (e.get("nivel") or "").lower() in _NIVELES_PRIMARIA), ""
    )
    fila["aporta_cert_bachiller_o_primaria"] = _si_no(tiene_primaria or entrada_bachiller_o_superior is not None)
    fila["fecha_grado_bachiller"] = (entrada_bachiller_o_superior or {}).get("fecha_terminacion") or (entrada_bachiller_o_superior or {}).get("fecha_fin", "")
    fila["folio_rm_educacion"] = _folios([p for e in estudios for p in e.get("paginas", [])])
    resultado_estudio = resultados_validacion.get("estudio")
    if resultado_estudio:
        fila["cumplimiento_rm_educacion"] = resultado_estudio.estado
        fila["observaciones_rm_educacion"] = resultado_estudio.motivo

    # --- Experiencia: hasta 4 bloques, igual estructura que TO-26.xlsx ---
    for i, exp in enumerate(laborales[:4], start=1):
        meses = meses_entre(parse_fecha(exp["fecha_inicio"]), fecha_fin_efectiva(exp.get("fecha_fin"), cfg["fecha_cierre_inscripcion"])) if exp.get("fecha_inicio") else ""
        fila[f"entidad_{i}"] = exp.get("entidad", "")
        fila[f"cargo_{i}"] = exp.get("cargo", "")
        fila[f"funciones_{i}"] = exp.get("funciones", "")
        fila[f"fecha_inicio_{i}"] = exp.get("fecha_inicio", "")
        fila[f"fecha_fin_{i}"] = exp.get("fecha_fin", "")
        fila[f"meses_{i}"] = meses
        fila[f"folio_{i}"] = _folios(exp.get("paginas", []))
        if i == 1:
            fila["relacionada_1"] = exp.get("relacionado", "")
            fila["observaciones_experiencia_1"] = exp.get("motivo_relacionado", "")

    resultado_laboral = resultados_validacion.get("laboral")
    if resultado_laboral and not laborales:
        fila["observaciones_experiencia_1"] = resultado_laboral.motivo

    # --- Alturas ---
    if alturas:
        resultado_alturas = resultados_validacion.get("alturas")
        fila["alturas_vigente"] = _si_no(resultado_alturas.estado == "cumple") if resultado_alturas else ""
        fila["alturas_empresa_emisora"] = alturas.get("entidad_emisora", "")
        fila["alturas_fecha_finalizacion_curso"] = alturas.get("fecha_expedicion") or alturas.get("fecha_vencimiento", "")
        fila["alturas_cumplimiento"] = resultado_alturas.estado if resultado_alturas else ""
        fila["alturas_observaciones"] = resultado_alturas.motivo if resultado_alturas else ""
    # alturas_consulta_mintrabajo y alturas_coincide_mintrabajo: SIEMPRE en blanco — verificación manual (Sección 1 del plan)

    # --- Evaluación médica ---
    if medica:
        resultado_medica = resultados_validacion.get("medica")
        fila["medica_aporta"] = _si_no(bool(medica.get("aportado")))
        fila["medica_fecha_examen"] = medica.get("fecha_expedicion", "")
        fila["medica_cumplimiento"] = resultado_medica.estado if resultado_medica else ""
        fila["medica_observaciones"] = resultado_medica.motivo if resultado_medica else ""

    # --- ADMITIDO SI/NO, CAUSAL DE NO ADMISIÓN y demás columnas de decisión ---
    # SIEMPRE en blanco aquí: esta función solo arma los datos ya extraídos del
    # expediente, nunca decide. Las columnas de decisión oficial (admitido_si_no,
    # causal_no_admision, estado_confirmado_por_humano, revisado_por,
    # fecha_revision) las llena el panel directamente al momento en que un humano
    # confirma la revisión — no existe una versión "sugerida" intermedia.
    # resultado_prueba_practica, resultado_prueba_teorica, puntajes: en blanco (Fase 9, meses después)

    return fila
