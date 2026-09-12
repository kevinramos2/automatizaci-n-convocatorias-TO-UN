"""Extracción estructurada por tipo de documento (Sección 7, paso 6 del plan).

Usa Sonnet (más preciso que Haiku) para extracción fina de campos. Un prompt
por tipo de documento impreso; el formulario manuscrito se aborda aparte
(Fase 1: "empezar por los impresos, luego el formulario manuscrito").
"""
import json

import anthropic

from pipeline.clasificador_paginas import TAXONOMIA
from pipeline.pdf_utils import paginas_a_imagenes_base64

MODEL = "claude-sonnet-5"

_TIPOS_VALIDOS = ", ".join(t for t, _ in TAXONOMIA)

# Salvaguarda contra errores de clasificación (Haiku, baja resolución) que Sonnet
# puede detectar al mirar el documento de cerca para extraer campos. Encontrado con
# datos reales: un certificado de curso SENA rotado 90° fue clasificado como
# "certificado_alturas" con confianza alta cuando en realidad era un curso de
# capacitación sin relación con alturas — el clasificador "adivinó" en vez de leer
# el texto rotado. La extracción, al mirar el documento más de cerca, debe frenar
# esa clasificación en vez de heredarla ciegamente.
_VERIFICACION_INSTRUCCION = (
    "\n\nIMPORTANTE: antes de extraer los campos de abajo, verifica que este documento "
    "realmente corresponde al tipo indicado. Si el contenido real es claramente de otro "
    f"tipo (uno de: {_TIPOS_VALIDOS}), NO extraigas los campos del tipo original — en su "
    'lugar responde SOLO con: {"clasificacion_correcta": false, "tipo_real_sugerido": '
    '"<tipo real>", "motivo_discrepancia": "<qué es realmente el documento y por qué no '
    'corresponde al tipo indicado>"}.\n'
    'Si el documento SÍ corresponde al tipo indicado, agrega el campo "clasificacion_correcta": true '
    "a los campos normales de abajo y extráelos todos."
)

_INSTRUCCIONES_POR_TIPO = {
    "cedula": (
        "Esta es una fotocopia de cédula de ciudadanía colombiana. Extrae:\n"
        '{"aportada": true, "numero": "<solo dígitos>", "nombre": "<nombres y apellidos completos>", '
        '"legible": true|false}\n'
        'Si algún campo no se puede leer con certeza, usa null para ese campo (no inventes datos).'
    ),
    "constancia_estudio": (
        "Este es un documento de estudios: puede ser diploma, acta de grado, certificado de "
        "educación formal, o certificado de curso/capacitación (CAP/CAO/curso corto). Extrae:\n"
        '{"institucion": "<nombre de la institución que expide>", "titulo": "<título obtenido, o null si es un curso corto>", '
        '"ultimo_anio_cursado": "<año, si aplica, o null>", '
        '"nivel": "<uno de: primaria, secundaria, tecnico, tecnologo, profesional, especializacion, maestria, doctorado, curso_capacitacion>", '
        '"es_boletin": true|false, '
        '"nombre_curso": "<nombre del curso si es curso_capacitacion, si no null>", '
        '"horas": <numero de horas si el documento lo indica explícitamente, si no null>, '
        '"fecha_inicio": "<AAAA-MM-DD o null>", "fecha_fin": "<AAAA-MM-DD o null>"}\n'
        "es_boletin=true SOLO si es un boletín/informe de calificaciones (no cuenta como constancia válida). "
        "Si algún campo no se puede leer con certeza, usa null (no inventes datos)."
    ),
    "constancia_laboral": (
        "Este es un certificado laboral, constancia de una entidad empleadora, o una declaración "
        "juramentada de experiencia independiente. Puede tener varias páginas. Extrae UN solo objeto "
        "para todo el documento:\n"
        '{"entidad": "<nombre de la entidad o lugar donde laboró>", "cargo": "<cargo desempeñado>", '
        '"jornada": "<jornada de trabajo, o null>", "fecha_inicio": "<AAAA-MM-DD>", "fecha_fin": "<AAAA-MM-DD>", '
        '"funciones": "<resumen breve de funciones>", "firmada_jefe": true|false, '
        '"es_declaracion_jurada_independiente": true|false, "notariada": true|false|null, '
        '"formato_valido": true|false}\n'
        "formato_valido=false si es una constancia informal (sin membrete/firma de representante legal) "
        "que NO está notariada, o si es una declaración de experiencia independiente que NO es juramentada. "
        "Si algún campo no se puede leer con certeza, usa null (no inventes datos)."
    ),
    "certificado_alturas": (
        "Este es un certificado de curso de trabajo seguro en alturas o de reentrenamiento. Extrae:\n"
        '{"aportado": true, "entidad_emisora": "<nombre del centro de entrenamiento>", '
        '"fecha_expedicion": "<AAAA-MM-DD o null>", "fecha_vencimiento": "<AAAA-MM-DD, la fecha de vigencia '
        'indicada explícitamente en el certificado; si el documento no indica vencimiento, usa null>"}\n'
        "Si algún campo no se puede leer con certeza, usa null (no inventes datos)."
    ),
    "evaluacion_medica": (
        "Esta es una evaluación médica ocupacional. Puede tener varias páginas. Extrae UN solo objeto:\n"
        '{"aportado": true, "entidad_emisora": "<entidad o médico que expide>", '
        '"fecha_expedicion": "<AAAA-MM-DD>", '
        '"concepto_aptitud_alturas": true|false, '
        '"es_certificado_preingreso_general": true|false}\n'
        "concepto_aptitud_alturas=true SOLO si el documento da explícitamente un concepto de aptitud "
        "para trabajo en alturas (no basta con ser un examen médico general). "
        "es_certificado_preingreso_general=true si es un certificado de preingreso ocupacional general "
        "que NO incluye concepto específico de aptitud en alturas (ese es un documento distinto, ver "
        "Sección 2.2 del plan). Si algún campo no se puede leer con certeza, usa null."
    ),
}

_INSTRUCCIONES_POR_TIPO = {tipo: instr + _VERIFICACION_INSTRUCCION for tipo, instr in _INSTRUCCIONES_POR_TIPO.items()}


def _extraer_json_objeto(texto: str) -> dict:
    inicio = texto.find("{")
    fin = texto.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError(f"No se encontró un objeto JSON en la respuesta: {texto[:200]!r}")
    return json.loads(texto[inicio:fin + 1])


def extraer_documento(pdf_path: str, tipo: str, paginas: list[int], client: anthropic.Anthropic | None = None, dpi: int = 150) -> dict:
    if tipo not in _INSTRUCCIONES_POR_TIPO:
        raise ValueError(f"No hay prompt de extracción definido para el tipo '{tipo}'")

    client = client or anthropic.Anthropic()
    imagenes = paginas_a_imagenes_base64(pdf_path, paginas, dpi=dpi)

    contenido = [{"type": "text", "text": _INSTRUCCIONES_POR_TIPO[tipo]}]
    for img in imagenes:
        contenido.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": img["base64"]},
        })
    contenido.append({"type": "text", "text": "Responde ÚNICAMENTE con el objeto JSON, sin texto antes ni después."})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": contenido}],
    )

    texto = next((b.text for b in response.content if b.type == "text"), "")
    datos = _extraer_json_objeto(texto)

    return {
        "tipo": tipo,
        "paginas": paginas,
        "datos": datos,
        "requiere_reclasificacion": datos.get("clasificacion_correcta") is False,
        "uso": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
    }
