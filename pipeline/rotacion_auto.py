"""Detección automática de orientación por página, vía Claude Haiku.

Algunos documentos vienen insertados en orientación horizontal dentro de un
escaneo que por lo demás es vertical (certificados apaisados de SENA/ALySO,
vistos repetidas veces con expedientes reales) y el PDF no trae ningún
metadato que lo delate: cada página reporta `page.rotation == 0` y el mismo
tamaño, sin importar cómo se vea el contenido al renderizarla. Antes esto se
resolvía inspeccionando cada expediente nuevo a mano.

Se probó primero pedirle al modelo que CALCULARA cuántos grados rotar
("responde con la rotación necesaria") — con una página apaisada real, el
modelo reconoció correctamente que estaba de lado pero se equivocó de sentido
(dijo 90° cuando la respuesta correcta era 270°: acertó el eje, erró la
dirección). En vez de eso, se le muestran las 4 rotaciones YA HECHAS
(0°/90°/180°/270°) una junto a otra y se le pide elegir cuál se ve bien —
una tarea de reconocer texto normal, mucho más confiable que calcular una
transformación, sin ambigüedad de sentido horario/antihorario posible.
"""
import re

import anthropic

from pipeline.pdf_utils import pagina_a_imagen_base64

MODEL = "claude-haiku-4-5"

_OPCIONES = (0, 90, 180, 270)
_LETRAS = ("A", "B", "C", "D")

_INSTRUCCION = (
    "Te muestro la MISMA página escaneada en 4 rotaciones distintas, en este "
    f"orden: {', '.join(f'{letra} (rotada {grados}°)' for letra, grados in zip(_LETRAS, _OPCIONES))}.\n\n"
    "Responde ÚNICAMENTE con la letra (A, B, C o D) de la imagen donde el texto "
    "se lee perfectamente horizontal, de arriba hacia abajo, como un documento "
    "normal — ni de lado ni boca abajo. Nada más que la letra."
)


def detectar_rotacion(pdf_path: str, pagina: int, client: anthropic.Anthropic | None = None, dpi: int = 90) -> dict:
    """Devuelve {"rotacion": 0|90|180|270, "uso": {...}} — la rotación ABSOLUTA

    correcta para esa página. Si la respuesta no se puede interpretar, devuelve
    rotacion=0 en vez de fallar — vale más mostrar la página sin corregir que
    romper el procesamiento por esto.
    """
    client = client or anthropic.Anthropic()

    contenido = []
    for letra, grados in zip(_LETRAS, _OPCIONES):
        imagen_b64 = pagina_a_imagen_base64(pdf_path, pagina, dpi=dpi, rotacion=grados)
        contenido.append({"type": "text", "text": f"Opción {letra}:"})
        contenido.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": imagen_b64}})
    contenido.append({"type": "text", "text": _INSTRUCCION})

    response = client.messages.create(
        model=MODEL,
        max_tokens=20,
        messages=[{"role": "user", "content": contenido}],
    )
    uso = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}

    texto = next((b.text for b in response.content if b.type == "text"), "")
    # \b...\b: una letra SUELTA (p. ej. "B" o "Respuesta: B.") — sin límites de
    # palabra, "PUEDO" o "AYUDAR" ya contienen una D/A y disparaban falsos positivos.
    coincidencia = re.search(r"\b[ABCD]\b", texto.strip().upper())
    letra_elegida = coincidencia.group(0) if coincidencia else "A"
    rotacion = _OPCIONES[_LETRAS.index(letra_elegida)]
    return {"rotacion": rotacion, "uso": uso}
