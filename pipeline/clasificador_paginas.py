"""Clasificación de páginas por tipo de documento (Sección 2 y Fase 1 del plan).

Usa Haiku (barato) porque es una tarea de clasificación, no de extracción fina.
Envía todas las páginas de un legajo en una sola llamada para minimizar costo
y latencia (en vez de una llamada por página).
"""
import json

import anthropic

from pipeline.pdf_utils import paginas_a_imagenes_base64

MODEL = "claude-haiku-4-5"

TAXONOMIA = [
    ("formulario_inscripcion", "Formulario de inscripción / hoja de vida manuscrita: nombre, cédula, correo, celular, dirección, discapacidad, tablas de educación formal, educación relacionada (cursos) y experiencia laboral. Suele tener varias páginas y letra a mano."),
    ("cedula", "Fotocopia de la cédula de ciudadanía del aspirante (documento oficial impreso, no manuscrito)."),
    ("constancia_estudio", "Diploma de bachillerato, acta de grado, certificado SENA o de centro de formación para el trabajo, o certificado de curso/capacitación. Impreso, con institución, título/curso y fechas."),
    ("constancia_laboral", "Certificado laboral o constancia de una entidad empleadora (cargo, jornada, fechas, funciones, firma del jefe), o declaración juramentada de experiencia independiente ante notario."),
    ("certificado_alturas", "Certificado de curso de trabajo seguro en alturas o de reentrenamiento, emitido por un Centro de Entrenamiento Autorizado."),
    ("evaluacion_medica", "Evaluación médica ocupacional con concepto de aptitud para trabajo en alturas."),
    ("libreta_militar", "Libreta militar (documento de situación militar definida)."),
    ("examen_medico_anexo", "Exámenes médicos anexos distintos a la evaluación de aptitud en alturas: audiometría, visiometría, glucosa, triglicéridos/colesterol, certificado de preingreso ocupacional general."),
    ("otro_no_identificado", "Cualquier página que no calce claramente en ninguna categoría anterior. Nunca se descarta silenciosamente."),
]

_SYSTEM_PROMPT = (
    "Eres un clasificador de documentos para un proceso de selección de personal de la "
    "Universidad Nacional de Colombia. Vas a recibir una o más imágenes, cada una es una "
    "página escaneada de un legajo de un aspirante. Clasifica CADA página en exactamente "
    "uno de estos tipos:\n\n"
    + "\n".join(f"- {tipo}: {desc}" for tipo, desc in TAXONOMIA)
    + "\n\nADEMÁS, para cada página indica si `inicia_documento_nuevo`:\n"
    "- true: esta página es la PRIMERA hoja de un documento físico distinto (aunque sea "
    "del mismo tipo que la página anterior — ej. dos certificados laborales de dos "
    "entidades distintas son DOS documentos, aunque ambos sean 'constancia_laboral').\n"
    "- false: esta página es una hoja ADICIONAL del mismo documento físico que la página "
    "inmediatamente anterior (ej. página 2 de 3 de un mismo certificado largo).\n"
    "La primera página que recibas en cada mensaje siempre es true, EXCEPTO si el mensaje "
    "indica explícitamente que continúa un documento del lote anterior.\n\n"
    "Responde ÚNICAMENTE con un array JSON, sin texto antes ni después, con un objeto "
    "por página en el mismo orden en que se presentan las imágenes:\n"
    '[{"pagina": <numero de pagina indicado>, "tipo": "<uno de los tipos de arriba>", '
    '"inicia_documento_nuevo": true|false, '
    '"confianza": "alta"|"media"|"baja", "motivo": "<breve justificación>"}]'
)


def _construir_mensaje(imagenes: list[dict], contexto_pagina_anterior: dict | None) -> list[dict]:
    contenido = []
    if contexto_pagina_anterior:
        contenido.append({
            "type": "text",
            "text": (
                f"Contexto: la página inmediatamente anterior a este lote (página "
                f"{contexto_pagina_anterior['pagina']}, fuera de este mensaje) fue "
                f"clasificada como tipo '{contexto_pagina_anterior['tipo']}'. Si la primera "
                "imagen de este mensaje es una continuación física de ese mismo documento, "
                "márcala con inicia_documento_nuevo=false; si es un documento distinto "
                "(aunque sea del mismo tipo), márcala true."
            ),
        })
    for img in imagenes:
        contenido.append({"type": "text", "text": f"Página {img['pagina']}:"})
        contenido.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img["base64"]},
        })
    contenido.append({"type": "text", "text": "Clasifica todas las páginas anteriores según las instrucciones."})
    return contenido


def _extraer_json_array(texto: str) -> list:
    inicio = texto.find("[")
    fin = texto.rfind("]")
    if inicio == -1 or fin == -1:
        raise ValueError(f"No se encontró un array JSON en la respuesta: {texto[:200]!r}")
    return json.loads(texto[inicio:fin + 1])


def _clasificar_lote(
    pdf_path: str,
    numeros_pagina: list[int],
    client: anthropic.Anthropic,
    dpi: int,
    contexto_pagina_anterior: dict | None,
) -> dict:
    imagenes = paginas_a_imagenes_base64(pdf_path, numeros_pagina, dpi=dpi)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _construir_mensaje(imagenes, contexto_pagina_anterior)}],
    )

    texto = next((b.text for b in response.content if b.type == "text"), "")
    resultados = _extraer_json_array(texto)

    return {
        "resultados": resultados,
        "uso": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
    }


def clasificar_paginas(
    pdf_path: str,
    numeros_pagina: list[int],
    client: anthropic.Anthropic | None = None,
    tamano_lote: int = 8,
    dpi: int = 100,
) -> dict:
    """Clasifica en lotes de `tamano_lote` páginas por llamada (evita exceder el límite
    de tamaño de request de la API cuando el legajo tiene muchas páginas con contenido).

    Pasa el tipo de la última página del lote anterior como contexto al siguiente lote,
    para que `inicia_documento_nuevo` sea correcto también en los bordes de lote.
    """
    client = client or anthropic.Anthropic()
    resultados = []
    uso_total = {"input_tokens": 0, "output_tokens": 0}
    contexto_pagina_anterior = None

    for i in range(0, len(numeros_pagina), tamano_lote):
        lote = numeros_pagina[i:i + tamano_lote]
        resultado_lote = _clasificar_lote(pdf_path, lote, client, dpi, contexto_pagina_anterior)
        resultados.extend(resultado_lote["resultados"])
        uso_total["input_tokens"] += resultado_lote["uso"]["input_tokens"]
        uso_total["output_tokens"] += resultado_lote["uso"]["output_tokens"]
        if resultado_lote["resultados"]:
            ultima = resultado_lote["resultados"][-1]
            contexto_pagina_anterior = {"pagina": ultima["pagina"], "tipo": ultima["tipo"]}

    return {"resultados": resultados, "uso": uso_total}
