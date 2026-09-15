"""Pruebas de la salvaguarda 'clasificacion_correcta' con un cliente Anthropic simulado
(sin llamar a la API). Encontrada necesaria con datos reales: un certificado SENA
rotado fue mal clasificado como certificado_alturas con confianza alta por Haiku;
Sonnet, al extraer de cerca, debe poder frenar esa clasificación en vez de heredarla.
"""
import json
import sys
import tempfile
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.extractor_documentos import extraer_documento


class _BloqueTexto:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class _Uso:
    def __init__(self, input_tokens=100, output_tokens=50):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _RespuestaFalsa:
    def __init__(self, texto_json, stop_reason="end_turn"):
        self.content = [_BloqueTexto(texto_json)]
        self.usage = _Uso()
        self.stop_reason = stop_reason


class _MessagesFalso:
    def __init__(self, texto_json, stop_reason="end_turn"):
        self._texto_json = texto_json
        self._stop_reason = stop_reason

    def create(self, **kwargs):
        return _RespuestaFalsa(self._texto_json, self._stop_reason)


class _ClienteFalso:
    def __init__(self, texto_json, stop_reason="end_turn"):
        self.messages = _MessagesFalso(texto_json, stop_reason)


def _pdf_de_una_pagina() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()  # en Windows, fitz no puede escribir en un archivo todavía abierto
    doc = fitz.open()
    doc.new_page()
    doc.save(tmp.name)
    doc.close()
    return tmp.name


def test_deteccion_de_clasificacion_incorrecta():
    pdf_path = _pdf_de_una_pagina()
    respuesta = json.dumps({
        "clasificacion_correcta": False,
        "tipo_real_sugerido": "constancia_estudio",
        "motivo_discrepancia": "Es un certificado de curso SENA, no de alturas.",
    })
    r = extraer_documento(pdf_path, "certificado_alturas", [1], client=_ClienteFalso(respuesta))
    assert r["requiere_reclasificacion"] is True
    assert r["datos"]["tipo_real_sugerido"] == "constancia_estudio"


def test_clasificacion_correcta_no_marca_reclasificacion():
    pdf_path = _pdf_de_una_pagina()
    respuesta = json.dumps({
        "clasificacion_correcta": True,
        "aportado": True,
        "entidad_emisora": "ALISO",
        "fecha_expedicion": "2026-05-29",
        "fecha_vencimiento": "2027-04-09",
    })
    r = extraer_documento(pdf_path, "certificado_alturas", [1], client=_ClienteFalso(respuesta))
    assert r["requiere_reclasificacion"] is False
    assert r["datos"]["entidad_emisora"] == "ALISO"


def test_respuesta_truncada_lanza_error_claro():
    pdf_path = _pdf_de_una_pagina()
    json_incompleto = '{"aportado": true, "entidad_emisora": "ALISO", "fecha_expedicion": "2026-05'
    cliente = _ClienteFalso(json_incompleto, stop_reason="max_tokens")
    try:
        extraer_documento(pdf_path, "certificado_alturas", [1], client=cliente)
        assert False, "debía lanzar ValueError por respuesta truncada"
    except ValueError as exc:
        assert "cortó por límite de tokens" in str(exc)


if __name__ == "__main__":
    fallos = 0
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        try:
            t()
        except AssertionError:
            fallos += 1
            print(f"FALLO: {t.__name__}")
    print(f"{len(tests) - fallos}/{len(tests)} pruebas pasaron")
