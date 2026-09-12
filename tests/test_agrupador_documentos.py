import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.agrupador_documentos import agrupar_en_documentos


def _pagina(pagina, tipo, inicia, confianza="alta", motivo=""):
    return {"pagina": pagina, "tipo": tipo, "inicia_documento_nuevo": inicia, "confianza": confianza, "motivo": motivo}


def test_paginas_del_mismo_documento_se_agrupan():
    resultados = [
        _pagina(19, "constancia_laboral", True, motivo="Certificado UNAL, pagina inicial"),
        _pagina(20, "constancia_laboral", False, motivo="Continuacion"),
        _pagina(21, "constancia_laboral", False, motivo="Continuacion"),
        _pagina(22, "constancia_laboral", False, motivo="Pagina final"),
    ]
    documentos = agrupar_en_documentos(resultados)
    assert len(documentos) == 1
    assert documentos[0]["paginas"] == [19, 20, 21, 22]


def test_dos_documentos_mismo_tipo_consecutivos_no_se_fusionan():
    # Caso real del legajo de ejemplo: pag 17 (empresa A) y 19-23 (empresa B, 5 pags)
    # y 23 sigue siendo otro documento nuevo de nuevo (Centro ALISO).
    resultados = [
        _pagina(17, "constancia_laboral", True, motivo="Empresa Todo en Remodelacion"),
        _pagina(19, "constancia_laboral", True, motivo="Certificado UNAL, pagina inicial"),
        _pagina(20, "constancia_laboral", False, motivo="Continuacion UNAL"),
        _pagina(21, "constancia_laboral", False, motivo="Continuacion UNAL"),
        _pagina(22, "constancia_laboral", False, motivo="Pagina final UNAL"),
        _pagina(23, "constancia_laboral", True, motivo="Centro ALISO, documento nuevo"),
    ]
    documentos = agrupar_en_documentos(resultados)
    assert len(documentos) == 3
    assert documentos[0]["paginas"] == [17]
    assert documentos[1]["paginas"] == [19, 20, 21, 22]
    assert documentos[2]["paginas"] == [23]


def test_cambio_de_tipo_siempre_inicia_documento_nuevo_aunque_diga_continuacion():
    # Salvaguarda: si el modelo se equivoca y marca inicia_documento_nuevo=false
    # pero el tipo cambió, igual se separa (dos tipos distintos nunca son un documento).
    resultados = [
        _pagina(11, "constancia_estudio", True),
        _pagina(12, "certificado_alturas", False),  # inconsistente a propósito
    ]
    documentos = agrupar_en_documentos(resultados)
    assert len(documentos) == 2


def test_documento_de_una_sola_pagina():
    resultados = [_pagina(5, "cedula", True)]
    documentos = agrupar_en_documentos(resultados)
    assert len(documentos) == 1
    assert documentos[0]["paginas"] == [5]


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
