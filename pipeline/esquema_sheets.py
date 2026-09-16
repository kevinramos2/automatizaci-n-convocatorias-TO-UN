"""Esquema de columnas de las hojas de Google Sheets (Sección 4 y Fase 4 del plan).

Cada hoja se define como una lista de (clave_interna, encabezado_para_mostrar).
La clave interna es lo que usa el código; el encabezado es lo que se escribe
literalmente en la fila 1 de la hoja (y por tanto lo que ve Personal Administrativo).

Para "Maestro", las primeras 58 columnas replican EXACTAMENTE — mismo texto,
mismo orden, incluida la asimetría entre bloques de experiencia (el bloque 1
tiene "¿relacionada?" y "Observaciones"; los bloques 2-4 no) — el TO-26.xlsx
que ya usa Personal Administrativo, para que el .xlsx exportado se vea igual a
lo que ya conocen. Las columnas nuevas del plan (Sección 4) van al final.
"""

# --- Bloque 1: idéntico a TO-26.xlsx, columnas 1-58 -------------------------
_MAESTRO_EXISTENTE = [
    ("recibido", "Recibió"),
    ("fecha_inscripcion", "Fecha Inscripción"),
    ("nombre_aspirante", "Nombre Aspirante"),
    ("id_aspirante", "ID Aspirante"),
    ("correo_electronico", "Correo electrónico"),
    ("celular", "Celular"),
    ("carpeta_drive", "Carpeta Drive"),
    ("observaciones", "Observaciones"),
    ("aporta_cert_primaria", "Aporta certificación de terminación de Primaria"),
    ("fecha_terminacion_primaria", "Fecha de terminación"),
    ("aporta_cert_bachiller_o_primaria", "Aporta Certificación Título Bachiller  o Primaria"),
    ("fecha_grado_bachiller", "Fecha de grado de bachiller"),
    ("folio_rm_educacion", "Folio que valida el RM de educación (primaria o bachillerato)"),
    ("cumplimiento_rm_educacion", "Cumplimiento RM educación:"),
    ("observaciones_rm_educacion", "Observaciones RM educación:"),
    # Bloque de experiencia 1 (9 columnas: incluye relacionada + observaciones)
    ("entidad_1", "Nombre de la Entidad"),
    ("cargo_1", "Cargo desempeñado"),
    ("funciones_1", "Descripción de las funciones del cargo "),
    ("fecha_inicio_1", "Fecha de inicio de labores: "),
    ("fecha_fin_1", "Fecha de finalización de labores:"),
    ("relacionada_1", "\nExperiencia relacionada?"),
    ("meses_1", "Tiempo total en meses"),
    ("folio_1", "Folio que valida el RM de experiencia (12 meses de experiencia):"),
    ("observaciones_experiencia_1", "Observaciones RM Experiencia"),
    # Bloques de experiencia 2-4 (7 columnas cada uno, sin relacionada/observaciones)
    ("entidad_2", "Nombre de la Entidad 2"),
    ("cargo_2", "Cargo desempeñado 2"),
    ("funciones_2", "Descripción de las funciones del cargo  2"),
    ("fecha_inicio_2", "Fecha de inicio de labores:  2"),
    ("fecha_fin_2", "Fecha de finalización de labores: 2"),
    ("meses_2", "Tiempo total en meses 2"),
    ("folio_2", "Folio que valida el RM de experiencia (12 meses de experiencia): 2"),
    ("entidad_3", "Nombre de la Entidad 3"),
    ("cargo_3", "Cargo desempeñado 3"),
    ("funciones_3", "Descripción de las funciones del cargo  3"),
    ("fecha_inicio_3", "Fecha de inicio de labores:  3"),
    ("fecha_fin_3", "Fecha de finalización de labores: 3"),
    ("meses_3", "Tiempo total en meses 3"),
    ("folio_3", "Folio que valida el RM de experiencia (12 meses de experiencia): 3"),
    ("entidad_4", "Nombre de la Entidad 4"),
    ("cargo_4", "Cargo desempeñado 4"),
    ("funciones_4", "Descripción de las funciones del cargo  4"),
    ("fecha_inicio_4", "Fecha de inicio de labores:  4"),
    ("fecha_fin_4", "Fecha de finalización de labores: 4"),
    ("meses_4", "Tiempo total en meses 4"),
    ("folio_4", "Folio que valida el RM de experiencia (12 meses de experiencia): 4"),
    # Alturas
    ("alturas_vigente", "El certificado de alturas está vigente:"),
    ("alturas_empresa_emisora", "Empresa emisora del certificado de alturas: "),
    ("alturas_fecha_finalizacion_curso", "Fecha de finalización del curso de alturas):"),
    ("alturas_consulta_mintrabajo", "Consulta del certificado de alturas en https://app2.mintrabajo.gov.co/CentrosEntrenamiento/consulta_ext.aspx "),
    ("alturas_coincide_mintrabajo", "Coincide el certificado aportado con lo consultado en la página de MinTrabajo:"),
    ("alturas_observaciones", "Observaciones Certificado de alturas:"),
    ("alturas_cumplimiento", "Cumplimiento del certificado de alturas:"),
    # Evaluación médica
    ("medica_aporta", "Aporta examen médico ocupacional con aptitud en alturas:"),
    ("medica_fecha_examen", "Fecha examen:"),
    ("medica_observaciones", "Observaciones exámen médico:"),
    ("medica_cumplimiento", "Cumplimiento Exan médico"),
    # Decisión (columnas existentes — el humano confirma aquí, igual que hoy)
    ("admitido_si_no", "ADMITIDO SI/NO"),
    ("causal_no_admision", "CAUSAL DE NO ADMISIÓN"),
]

# --- Bloque 2: columnas nuevas del plan (Sección 4) --------------------------
# Nota: no hay columnas de "sugerencia" de la IA — el pipeline nunca escribe una
# fila en Maestro por sí solo. Solo se escribe cuando un humano confirma la
# revisión en el panel, y en ese momento se llenan directamente las columnas de
# decisión oficiales de arriba (admitido_si_no, causal_no_admision), no una
# versión "sugerida" aparte.
_MAESTRO_NUEVO = [
    ("estado_confirmado_por_humano", "Estado_confirmado_por_humano"),
    ("revisado_por", "Revisado_por"),
    ("fecha_revision", "Fecha_revisión"),
    ("resultado_prueba_practica", "Resultado_prueba_practica"),
    ("resultado_prueba_teorica", "Resultado_prueba_teorica"),
    ("puntaje_educacion", "Puntaje_educacion"),
    ("puntaje_experiencia", "Puntaje_experiencia"),
    ("puntaje_hoja_de_vida_total", "Puntaje_hoja_de_vida_total"),
]

MAESTRO = _MAESTRO_EXISTENTE + _MAESTRO_NUEVO

AUDITORIA = [
    ("id_aspirante", "ID_Aspirante"),
    ("campo", "Campo"),
    ("valor_extraido_ia", "Valor_extraido_IA"),
    ("confianza", "Confianza"),
    ("valor_corregido_humano", "Valor_corregido_humano"),
    ("corregido_por", "Corregido_por"),
    ("fecha_correccion", "Fecha_correccion"),
    ("folio_fuente", "Folio_fuente"),
]

DOCUMENTOS_POR_CANDIDATO = [
    ("id_aspirante", "ID_Aspirante"),
    ("paginas", "Paginas"),
    ("tipo_documento", "Tipo_documento"),
    ("confianza", "Confianza"),
    ("motivo", "Motivo"),
    ("requiere_reclasificacion", "Requiere_reclasificacion"),
    ("tipo_real_sugerido", "Tipo_real_sugerido"),
    ("blank", "Blank"),
]

DOCUMENTOS_ADICIONALES = [
    ("id_aspirante", "ID_Aspirante"),
    ("tipo", "Tipo"),
    ("paginas", "Paginas"),
    ("datos_extraidos", "Datos_extraidos"),
]

FORMACION_EXPERIENCIA_DETALLADA = [
    ("id_aspirante", "ID_Aspirante"),
    ("tipo", "Tipo"),
    ("nombre_institucion_o_entidad", "Nombre_institucion_o_entidad"),
    ("nombre_curso_o_cargo", "Nombre_curso_o_cargo"),
    ("fecha_inicio", "Fecha_inicio"),
    ("fecha_fin", "Fecha_fin"),
    ("duracion_horas_o_meses", "Duracion_horas_o_meses"),
    ("relacionado_con_el_cargo", "Relacionado_con_el_cargo"),
    ("folio_fuente", "Folio_fuente"),
]

TODAS_LAS_HOJAS = {
    "Maestro": MAESTRO,
    "Auditoría": AUDITORIA,
    "Documentos por candidato": DOCUMENTOS_POR_CANDIDATO,
    "Documentos adicionales": DOCUMENTOS_ADICIONALES,
    "Formación y Experiencia Detallada": FORMACION_EXPERIENCIA_DETALLADA,
}


def encabezados(esquema: list[tuple[str, str]]) -> list[str]:
    """Fila 1 a escribir en la hoja: los encabezados en el orden del esquema."""
    return [encabezado for _clave, encabezado in esquema]


def claves(esquema: list[tuple[str, str]]) -> list[str]:
    return [clave for clave, _encabezado in esquema]


def fila_desde_dict(esquema: list[tuple[str, str]], datos: dict) -> list:
    """Convierte un dict {clave: valor} en una fila en el orden del esquema.

    Claves ausentes en `datos` se escriben como cadena vacía (no None, para que
    Sheets no las muestre como la palabra "None").
    """
    return [datos.get(clave, "") if datos.get(clave) is not None else "" for clave, _ in esquema]
