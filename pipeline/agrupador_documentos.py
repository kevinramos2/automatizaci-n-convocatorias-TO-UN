"""Agrupación de páginas clasificadas en 'documentos lógicos' (Sección 7, paso 5 del plan).

Usa el campo `inicia_documento_nuevo` que produce el clasificador (Fase 1) en vez de
asumir que páginas consecutivas del mismo tipo son siempre un solo documento físico:
dos constancias laborales de dos empleadores distintos son dos documentos, aunque
ambas sean del mismo tipo y estén una detrás de la otra en el legajo.
"""


def agrupar_en_documentos(resultados_clasificacion: list[dict]) -> list[dict]:
    """resultados_clasificacion: [{"pagina", "tipo", "inicia_documento_nuevo", "confianza", "motivo"}, ...]

    Devuelve [{"tipo", "paginas": [...], "confianzas": [...], "motivos": [...]}, ...]
    """
    documentos = []
    for r in resultados_clasificacion:
        continua_anterior = (
            documentos
            and not r.get("inicia_documento_nuevo", True)
            and r["tipo"] == documentos[-1]["tipo"]  # nunca fusionar tipos distintos, pase lo que pase
        )
        if continua_anterior:
            documentos[-1]["paginas"].append(r["pagina"])
            documentos[-1]["confianzas"].append(r["confianza"])
            documentos[-1]["motivos"].append(r["motivo"])
        else:
            documentos.append({
                "tipo": r["tipo"],
                "paginas": [r["pagina"]],
                "confianzas": [r["confianza"]],
                "motivos": [r["motivo"]],
            })
    return documentos
