"""Pruebas de rotacion_auto.py con un cliente Anthropic simulado (sin costo de API)."""
import sys
import tempfile
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.rotacion_auto import detectar_rotacion


class _BloqueTexto:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class _Uso:
    def __init__(self):
        self.input_tokens = 800
        self.output_tokens = 5


class _RespuestaFalsa:
    def __init__(self, texto):
        self.content = [_BloqueTexto(texto)]
        self.usage = _Uso()


class _ClienteFalso:
    def __init__(self, texto_respuesta):
        self._texto_respuesta = texto_respuesta

        class _Messages:
            def create(inner_self, **kwargs):
                return _RespuestaFalsa(self._texto_respuesta)

        self.messages = _Messages()


def _pdf_de_una_pagina() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()  # en Windows, fitz no puede escribir en un archivo todavía abierto
    doc = fitz.open()
    doc.new_page()
    doc.save(tmp.name)
    doc.close()
    return tmp.name


def test_opcion_a_es_cero_grados():
    pdf = _pdf_de_una_pagina()
    r = detectar_rotacion(pdf, 1, client=_ClienteFalso("A"))
    assert r["rotacion"] == 0
    assert r["uso"]["input_tokens"] == 800


def test_opcion_c_es_180_grados():
    pdf = _pdf_de_una_pagina()
    r = detectar_rotacion(pdf, 1, client=_ClienteFalso("C"))
    assert r["rotacion"] == 180


def test_opcion_d_es_270_grados():
    pdf = _pdf_de_una_pagina()
    r = detectar_rotacion(pdf, 1, client=_ClienteFalso("D"))
    assert r["rotacion"] == 270


def test_respuesta_con_texto_extra_igual_encuentra_la_letra():
    pdf = _pdf_de_una_pagina()
    r = detectar_rotacion(pdf, 1, client=_ClienteFalso("La respuesta correcta es B."))
    assert r["rotacion"] == 90


def test_respuesta_sin_letra_valida_no_rompe_devuelve_cero():
    pdf = _pdf_de_una_pagina()
    r = detectar_rotacion(pdf, 1, client=_ClienteFalso("no puedo ayudar con eso"))
    assert r["rotacion"] == 0


if __name__ == "__main__":
    fallos = 0
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fallos += 1
            print(f"FALLO: {t.__name__}: {e}")
    print(f"{len(tests) - fallos}/{len(tests)} pruebas pasaron")
