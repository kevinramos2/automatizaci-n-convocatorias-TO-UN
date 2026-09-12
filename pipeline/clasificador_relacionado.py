"""Clasificación 'relacionado con el cargo' (Sección 6.1 del plan).

Es un juicio semántico, no un dato objetivo: la sugerencia del modelo NUNCA se
usa directamente como valor confirmado de `relacionado` en validacion_admision.py
ni en scoring_hoja_vida.py — siempre queda como PENDIENTE hasta que un humano la
confirme (igual criterio que la firma del formulario). Este módulo solo produce
la sugerencia + justificación para que el revisor decida más rápido.
"""
import json

import anthropic

MODEL = "claude-sonnet-5"

_SYSTEM_PROMPT_TEMPLATE = (
    "Evalúas si cursos de capacitación o experiencias laborales de un aspirante están "
    "relacionados con un cargo específico, para un proceso de selección de la "
    "Universidad Nacional de Colombia.\n\n"
    "Cargo: {cargo}\n"
    "Propósito principal: {proposito_principal}\n"
    "Funciones esenciales:\n{funciones}\n"
    "Conocimientos básicos o esenciales:\n{conocimientos}\n\n"
    "Para cada ítem que recibas, decide si está relacionado con este cargo según su "
    "propósito, funciones o conocimientos básicos. Responde ÚNICAMENTE con un array JSON:\n"
    '[{{"id": "<id del item>", "relacionado_sugerido": "SI"|"NO", "justificacion": "<breve, 1 frase>"}}]\n'
    "Usa \"NO\" cuando el ítem sea claramente ajeno al cargo (ej. un curso de sistemas para un "
    "cargo de albañilería). Usa \"SI\" solo cuando haya una relación clara con el propósito, "
    "las funciones o los conocimientos básicos listados arriba."
)


def _construir_system_prompt(criterios: dict) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        cargo=criterios["cargo"],
        proposito_principal=criterios["proposito_principal"],
        funciones="\n".join(f"- {f}" for f in criterios["funciones_esenciales"]),
        conocimientos="\n".join(f"- {c}" for c in criterios["conocimientos_basicos_o_esenciales"]),
    )


def _extraer_json_array(texto: str) -> list:
    inicio = texto.find("[")
    fin = texto.rfind("]")
    if inicio == -1 or fin == -1:
        raise ValueError(f"No se encontró un array JSON en la respuesta: {texto[:200]!r}")
    return json.loads(texto[inicio:fin + 1])


def clasificar_relacionado(items: list[dict], criterios: dict, client: anthropic.Anthropic | None = None) -> dict:
    """items: [{"id": "<identificador>", "descripcion": "<cargo/funciones o nombre del curso>"}]

    Devuelve {"resultados": [{"id", "relacionado_sugerido", "justificacion"}], "uso": {...}}.
    `relacionado_sugerido` es SOLO informativo para el revisor — nunca se usa como valor
    confirmado en los motores de validación/scoring (ver docstring del módulo).
    """
    if not items:
        return {"resultados": [], "uso": {"input_tokens": 0, "output_tokens": 0}}

    client = client or anthropic.Anthropic()
    texto_items = "\n".join(f'- id="{it["id"]}": {it["descripcion"]}' for it in items)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=_construir_system_prompt(criterios),
        messages=[{"role": "user", "content": f"Ítems a evaluar:\n{texto_items}"}],
    )

    texto = next((b.text for b in response.content if b.type == "text"), "")
    resultados = _extraer_json_array(texto)

    return {
        "resultados": resultados,
        "uso": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
    }
