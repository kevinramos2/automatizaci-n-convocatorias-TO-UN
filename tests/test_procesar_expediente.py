"""Prueba la lógica de reintento de reclasificación de _extraer_documento_logico

con un cliente Anthropic simulado (sin costo de API). El resto de procesar_expediente()
se valida con una corrida real contra el expediente de ejemplo (ver scripts/).
"""
import json
import sys
import tempfile
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.procesar_expediente import _extraer_documento_logico, _mejor_candidato
from pipeline.validacion_admision import validar_evaluacion_medica


class _BloqueTexto:
    type = "text"

    def __init__(self, texto):
        self.text = texto


class _Uso:
    def __init__(self):
        self.input_tokens = 100
        self.output_tokens = 50


class _RespuestaFalsa:
    def __init__(self, texto_json):
        self.content = [_BloqueTexto(texto_json)]
        self.usage = _Uso()
        self.stop_reason = "end_turn"


class _ClienteSecuencial:
    """Devuelve una respuesta distinta en cada llamada, en el orden dado."""

    def __init__(self, respuestas_json: list[str]):
        self._respuestas = list(respuestas_json)
        self.llamadas = 0

        class _Messages:
            def create(inner_self, **kwargs):
                self.llamadas += 1
                return _RespuestaFalsa(self._respuestas[self.llamadas - 1])

        self.messages = _Messages()


def _pdf_de_una_pagina() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    doc = fitz.open()
    doc.new_page()
    doc.save(tmp.name)
    doc.close()
    return tmp.name


def test_extraccion_correcta_a_la_primera_no_reintenta():
    pdf = _pdf_de_una_pagina()
    respuesta = json.dumps({"clasificacion_correcta": True, "aportado": True, "entidad_emisora": "ALISO"})
    client = _ClienteSecuencial([respuesta])
    resultado = _extraer_documento_logico(pdf, {"tipo": "certificado_alturas", "paginas": [1]}, client)
    assert resultado["tipo_final"] == "certificado_alturas"
    assert resultado["reclasificado_automaticamente"] is False
    assert client.llamadas == 1


def test_reclasificacion_automatica_cuando_el_segundo_intento_confirma():
    # Simula el caso real: certificado_alturas -> en realidad constancia_estudio.
    r1 = json.dumps({"clasificacion_correcta": False, "tipo_real_sugerido": "constancia_estudio", "motivo_discrepancia": "..."})
    r2 = json.dumps({"clasificacion_correcta": True, "institucion": "SENA", "nivel": "curso_capacitacion"})
    pdf = _pdf_de_una_pagina()
    client = _ClienteSecuencial([r1, r2])
    resultado = _extraer_documento_logico(pdf, {"tipo": "certificado_alturas", "paginas": [1]}, client)
    assert resultado["tipo_final"] == "constancia_estudio"
    assert resultado["reclasificado_automaticamente"] is True
    assert resultado["datos"]["institucion"] == "SENA"
    assert client.llamadas == 2


def test_si_el_segundo_intento_tambien_falla_queda_para_revision_manual():
    r1 = json.dumps({"clasificacion_correcta": False, "tipo_real_sugerido": "constancia_estudio", "motivo_discrepancia": "..."})
    r2 = json.dumps({"clasificacion_correcta": False, "tipo_real_sugerido": "otro_no_identificado", "motivo_discrepancia": "..."})
    pdf = _pdf_de_una_pagina()
    client = _ClienteSecuencial([r1, r2])
    resultado = _extraer_documento_logico(pdf, {"tipo": "certificado_alturas", "paginas": [1]}, client)
    assert resultado["tipo_final"] is None
    assert resultado["requiere_revision_tipo"] is True
    assert resultado["datos"] is None
    assert client.llamadas == 2  # nunca reintenta una tercera vez


def test_tipo_sin_prompt_de_extraccion_no_llama_a_la_api():
    pdf = _pdf_de_una_pagina()
    client = _ClienteSecuencial([])
    resultado = _extraer_documento_logico(pdf, {"tipo": "libreta_militar", "paginas": [7]}, client)
    assert resultado["tipo_final"] == "libreta_militar"
    assert client.llamadas == 0


def test_mejor_candidato_prefiere_el_que_cumple_sobre_el_primero_de_la_lista():
    # Caso real: el clasificador partió una sola evaluación médica en dos
    # documentos lógicos — uno incompleto (sin concepto claro) que salió primero,
    # y el completo (con concepto de aptitud) después. Antes de este fix, el
    # código tomaba ciegamente el primero encontrado.
    incompleto = {"aportado": True, "concepto_aptitud_alturas": None, "fecha_expedicion": "2026-09-08"}
    completo = {"aportado": True, "concepto_aptitud_alturas": True, "fecha_expedicion": "2026-09-08"}
    cfg = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))

    datos, resultado = _mejor_candidato([incompleto, completo], validar_evaluacion_medica, cfg)
    assert resultado.estado == "cumple"
    assert datos is completo


def test_mejor_candidato_sin_ninguno_que_cumpla_devuelve_el_primero():
    cfg = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))
    a = {"aportado": True, "concepto_aptitud_alturas": False}
    b = {"aportado": True, "concepto_aptitud_alturas": False}
    datos, resultado = _mejor_candidato([a, b], validar_evaluacion_medica, cfg)
    assert resultado.estado == "no_cumple"
    assert datos is a


def test_mejor_candidato_sin_candidatos():
    cfg = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))
    datos, resultado = _mejor_candidato([], validar_evaluacion_medica, cfg)
    assert datos is None
    assert resultado.estado == "no_cumple"


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
