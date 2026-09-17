"""Orquestador del pipeline completo (Sección 7 del plan): de un PDF crudo a

resultados de validación de admisión, listos para escribir en Google Sheets.
No asume orden ni cantidad de páginas — solo que el formulario de inscripción
va primero (regla real del proceso, Sección 2 del plan).
"""
import anthropic

from pipeline.agrupador_documentos import agrupar_en_documentos
from pipeline.blank_detector import clasificar_paginas_pdf
from pipeline.clasificador_paginas import clasificar_paginas
from pipeline.clasificador_relacionado import clasificar_relacionado
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.extractor_documentos import extraer_documento
from pipeline.rotacion_auto import detectar_rotacion
from pipeline.validacion_admision import (
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

TIPOS_EXTRAIBLES = {
    "formulario_inscripcion", "cedula", "constancia_estudio",
    "constancia_laboral", "certificado_alturas", "evaluacion_medica",
}


def _uso_vacio():
    return {"input_tokens": 0, "output_tokens": 0}


def _sumar_uso(total: dict, *usos: dict) -> None:
    for uso in usos:
        total["input_tokens"] += uso["input_tokens"]
        total["output_tokens"] += uso["output_tokens"]


def _extraer_documento_logico(pdf_path: str, documento: dict, client: anthropic.Anthropic, rotacion: int = 0) -> dict:
    """Extrae un documento lógico; si la extracción detecta que el tipo asignado

    por el clasificador está mal, reintenta UNA vez con el tipo sugerido. Si
    tampoco se resuelve, queda para revisión manual — nunca se fuerza un tipo.
    """
    tipo_original = documento["tipo"]
    paginas = documento["paginas"]
    uso = _uso_vacio()

    if tipo_original not in TIPOS_EXTRAIBLES:
        return {"tipo_final": tipo_original, "paginas": paginas, "datos": None,
                "reclasificado_automaticamente": False, "requiere_revision_tipo": False, "uso": uso}

    r1 = extraer_documento(pdf_path, tipo_original, paginas, client=client, rotacion=rotacion)
    _sumar_uso(uso, r1["uso"])

    if not r1["requiere_reclasificacion"]:
        return {"tipo_final": tipo_original, "paginas": paginas, "datos": r1["datos"],
                "reclasificado_automaticamente": False, "requiere_revision_tipo": False, "uso": uso}

    tipo_sugerido = r1["datos"].get("tipo_real_sugerido")
    if tipo_sugerido in TIPOS_EXTRAIBLES and tipo_sugerido != tipo_original:
        r2 = extraer_documento(pdf_path, tipo_sugerido, paginas, client=client, rotacion=rotacion)
        _sumar_uso(uso, r2["uso"])
        if not r2["requiere_reclasificacion"]:
            return {"tipo_final": tipo_sugerido, "paginas": paginas, "datos": r2["datos"],
                    "reclasificado_automaticamente": True, "requiere_revision_tipo": False, "uso": uso}

    return {"tipo_final": None, "paginas": paginas, "datos": None,
            "reclasificado_automaticamente": False, "requiere_revision_tipo": True, "uso": uso,
            "motivo_discrepancia": r1["datos"].get("motivo_discrepancia")}


def _mejor_candidato(candidatos: list[dict], validar_fn, cfg: dict):
    """Para ítems donde puede haber más de un documento del mismo tipo final

    (ej. dos certificados de alturas, o una evaluación médica que el clasificador
    partió en dos documentos lógicos distintos) — valida TODOS los candidatos y
    devuelve (datos, resultado) del primero que CUMPLE. Si ninguno cumple, del
    primero de la lista (para que el motivo mostrado sea el de un caso real, no
    un genérico "no se aportó" cuando sí se aportó algo).
    """
    if not candidatos:
        return None, validar_fn(None, cfg)
    evaluados = [(c, validar_fn(c, cfg)) for c in candidatos]
    for datos, resultado in evaluados:
        if resultado.estado == "cumple":
            return datos, resultado
    return evaluados[0]


def _detectar_rotaciones_paginas(pdf_path: str, grupos_paginas: list[list[int]], client: anthropic.Anthropic) -> tuple[dict, dict]:
    """Detecta automáticamente la orientación correcta de cada documento que se

    va a mostrar en el panel (formulario, cédula, cada constancia de estudio,
    cada constancia laboral, alturas, médica) — una llamada por documento, a su
    primera página, aplicada a TODAS sus páginas (un mismo documento físico
    siempre trae la misma orientación en todas sus hojas, confirmado con datos
    reales). No depende de ninguna rotación "base": cada valor es absoluto, así
    que un documento insertado de lado dentro de un escaneo por lo demás
    correcto (visto repetidas veces con certificados apaisados de SENA/ALySO)
    queda bien igual que el resto, sin intervención manual.
    """
    rotaciones: dict[str, int] = {}
    uso_total = _uso_vacio()
    for paginas in grupos_paginas:
        if not paginas:
            continue
        resultado = detectar_rotacion(pdf_path, paginas[0], client=client)
        _sumar_uso(uso_total, resultado["uso"])
        for p in paginas:
            rotaciones[str(p)] = resultado["rotacion"]
    return rotaciones, uso_total


def _items_para_relacionado(estudios: list[dict], laborales: list[dict]) -> list[dict]:
    items = []
    for i, e in enumerate(estudios):
        if (e.get("nivel") or "").lower() == "curso_capacitacion":
            items.append({"id": f"estudio_{i}", "descripcion": f"Curso: {e.get('nombre_curso')}, institución: {e.get('institucion')}"})
    for i, e in enumerate(laborales):
        items.append({"id": f"laboral_{i}", "descripcion": f"Cargo: {e.get('cargo')}. Funciones: {e.get('funciones')}"})
    return items


def procesar_expediente(pdf_path: str, criterios: dict, cfg: dict, client: anthropic.Anthropic | None = None, rotacion: int | None = None) -> dict:
    """`rotacion` (0/90/180/270): corrige expedientes escaneados girados. Se aplica

    al RENDERIZADO de imágenes enviadas a Claude para clasificación y extracción
    (la detección de páginas en blanco es insensible a rotación — mide varianza
    de píxeles, no orientación — así que no la necesita). Si se deja en `None`
    (el caso normal: subir un expediente nuevo desde el panel), se detecta
    automáticamente con un modelo de visión barato en vez de asumir 0°.

    Al final, independientemente de `rotacion`, también se detecta la
    orientación de cada documento individual que el panel va a mostrar
    (formulario, cédula, cada constancia, alturas, médica) — un documento
    insertado de lado dentro de un escaneo por lo demás correcto (visto
    repetidas veces con certificados apaisados de SENA/ALySO) queda bien
    igual que el resto, para cualquier aspirante, sin inspección manual.
    El resultado incluye "rotacion" (la usada para clasificar/extraer) y
    "rotaciones_paginas" (por documento, para mostrar en el panel).
    """
    client = client or anthropic.Anthropic()
    uso_total = _uso_vacio()

    if rotacion is None:
        deteccion_base = detectar_rotacion(pdf_path, 1, client=client)
        _sumar_uso(uso_total, deteccion_base["uso"])
        rotacion = deteccion_base["rotacion"]

    # 1-2: detección de páginas en blanco (local, sin API) + clasificación (Haiku)
    analisis_paginas = clasificar_paginas_pdf(pdf_path)
    paginas_blancas = [r["pagina"] for r in analisis_paginas if r["clasificacion"] == "blank"]
    paginas_a_clasificar = [r["pagina"] for r in analisis_paginas if r["clasificacion"] != "blank"]

    resultado_clasificacion = clasificar_paginas(pdf_path, paginas_a_clasificar, client=client, rotacion=rotacion)
    _sumar_uso(uso_total, resultado_clasificacion["uso"])
    clasificacion = resultado_clasificacion["resultados"]

    # 3: agrupación en documentos lógicos
    documentos_logicos = agrupar_en_documentos(clasificacion)

    # 4: extracción por documento (Sonnet), con reintento de reclasificación
    documentos_extraidos = []
    for doc in documentos_logicos:
        resultado = _extraer_documento_logico(pdf_path, doc, client, rotacion=rotacion)
        _sumar_uso(uso_total, resultado["uso"])
        documentos_extraidos.append(resultado)

    def por_tipo_final(tipo):
        return [d for d in documentos_extraidos if d["tipo_final"] == tipo and d["datos"]]

    formulario_docs = por_tipo_final("formulario_inscripcion")
    formulario = formulario_docs[0]["datos"] if formulario_docs else {}
    cedula_docs = por_tipo_final("cedula")
    cedula = cedula_docs[0]["datos"] if cedula_docs else {}
    estudios = [{**d["datos"], "paginas": d["paginas"]} for d in por_tipo_final("constancia_estudio")]
    laborales = [{**d["datos"], "paginas": d["paginas"]} for d in por_tipo_final("constancia_laboral")]
    alturas_candidatos = [{**d["datos"], "paginas": d["paginas"]} for d in por_tipo_final("certificado_alturas")]
    medica_candidatos = [{**d["datos"], "paginas": d["paginas"]} for d in por_tipo_final("evaluacion_medica")]

    # 5: clasificación "relacionado con el cargo" (Sección 6.1) — SOLO informativa.
    # El valor que entra a validación/scoring siempre es PENDIENTE hasta confirmación
    # humana (Fase 5); la sugerencia se guarda aparte para que el revisor la vea.
    items_relacionado = _items_para_relacionado(estudios, laborales)
    sugerencias = {}
    if items_relacionado:
        resultado_rel = clasificar_relacionado(items_relacionado, criterios, client=client)
        _sumar_uso(uso_total, resultado_rel["uso"])
        sugerencias = {r["id"]: r for r in resultado_rel["resultados"]}

    for i, e in enumerate(estudios):
        sugerencia = sugerencias.get(f"estudio_{i}")
        e["relacionado_sugerido"] = sugerencia.get("relacionado_sugerido") if sugerencia else None
        e["justificacion_relacionado"] = sugerencia.get("justificacion") if sugerencia else None
        e["relacionado"] = "PENDIENTE" if (e.get("nivel") or "").lower() == "curso_capacitacion" else e.get("relacionado", "PENDIENTE")
    for i, e in enumerate(laborales):
        sugerencia = sugerencias.get(f"laboral_{i}")
        e["relacionado_sugerido"] = sugerencia.get("relacionado_sugerido") if sugerencia else None
        e["justificacion_relacionado"] = sugerencia.get("justificacion") if sugerencia else None
        e["relacionado"] = "PENDIENTE"

    # 6: motor de validación de admisión (Sección 5)
    alturas, resultado_alturas = _mejor_candidato(alturas_candidatos, validar_certificado_alturas, cfg)
    medica, resultado_medica = _mejor_candidato(medica_candidatos, validar_evaluacion_medica, cfg)
    medica = medica or {}

    resultados_validacion = {
        "formulario": validar_formulario(
            {k: formulario.get(k) for k in ("nombre", "cedula", "correo", "celular", "direccion")},
            {"nombre": cedula.get("nombre"), "numero": cedula.get("numero")},
            firma_verificada=None,
        ),
        "cedula": validar_cedula(cedula),
        "estudio": validar_constancia_estudio(estudios),
        "laboral": validar_constancias_laborales(laborales, cfg),
        "alturas": resultado_alturas,
        "medica": resultado_medica,
    }
    decision = evaluar_admision(resultados_validacion)

    # 7: cruce de consistencia formulario vs. constancias laborales
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario.get("experiencia", []), laborales, cfg)

    # 8: orientación de cada documento que el panel va a mostrar (ver docstring)
    grupos_para_mostrar = []
    if formulario_docs:
        grupos_para_mostrar.append(formulario_docs[0]["paginas"])
    if cedula_docs:
        grupos_para_mostrar.append(cedula_docs[0]["paginas"])
    grupos_para_mostrar += [e.get("paginas", []) for e in estudios]
    grupos_para_mostrar += [e.get("paginas", []) for e in laborales]
    if alturas:
        grupos_para_mostrar.append(alturas.get("paginas", []))
    if medica.get("paginas"):
        grupos_para_mostrar.append(medica["paginas"])
    rotaciones_paginas, uso_rotaciones = _detectar_rotaciones_paginas(pdf_path, grupos_para_mostrar, client)
    _sumar_uso(uso_total, uso_rotaciones)

    return {
        "paginas_blancas": paginas_blancas,
        "clasificacion": clasificacion,
        "documentos_logicos": documentos_logicos,
        "documentos_extraidos": documentos_extraidos,
        "formulario": formulario,
        "cedula": cedula,
        "estudios": estudios,
        "laborales": laborales,
        "alturas": alturas,
        "medica": medica,
        "resultados_validacion": resultados_validacion,
        "decision": decision,
        "inconsistencias": inconsistencias,
        "rotacion": rotacion,
        "rotaciones_paginas": rotaciones_paginas,
        "uso_total": uso_total,
    }
