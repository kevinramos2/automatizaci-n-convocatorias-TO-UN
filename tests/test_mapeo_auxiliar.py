import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.mapeo_auxiliar import (
    construir_filas_auditoria,
    construir_filas_documentos_adicionales,
    construir_filas_documentos_candidato,
    construir_filas_formacion_experiencia,
)

CLASIFICACION = [
    {"pagina": 1, "tipo": "formulario_inscripcion", "confianza": "alta", "motivo": "..."},
    {"pagina": 7, "tipo": "libreta_militar", "confianza": "alta", "motivo": "..."},
    {"pagina": 27, "tipo": "examen_medico_anexo", "confianza": "alta", "motivo": "..."},
]


def test_auditoria_una_fila_por_pagina():
    filas = construir_filas_auditoria(CLASIFICACION, "123")
    assert len(filas) == 3
    assert filas[0]["id_aspirante"] == "123"
    assert filas[0]["confianza"] == "alta"


def test_documentos_candidato_incluye_blancos_por_trazabilidad():
    documentos = [{"tipo": "cedula", "paginas": [5], "confianzas": ["alta"], "motivos": ["..."]}]
    filas = construir_filas_documentos_candidato(documentos, "123", paginas_blancas=[2, 4])
    assert len(filas) == 3  # 1 documento + 2 paginas blancas
    blancos = [f for f in filas if f["blank"]]
    assert len(blancos) == 2


def test_documentos_adicionales_solo_libreta_y_examen_anexo():
    filas = construir_filas_documentos_adicionales(CLASIFICACION, "123")
    assert len(filas) == 2  # libreta_militar y examen_medico_anexo, no el formulario
    assert {f["tipo"] for f in filas} == {"libreta_militar", "examen_medico_anexo"}


def test_formacion_experiencia_combina_estudios_y_laborales():
    estudios = [{"institucion": "Colegio X", "titulo": "Bachiller", "nivel": "secundaria", "fecha_terminacion": "2015-01-01", "paginas": [3]}]
    laborales = [{"entidad": "ACME", "cargo": "Ayudante", "fecha_inicio": "2020-01-01", "fecha_fin": "2021-01-01", "relacionado": "SI", "meses": 12, "paginas": [5]}]
    filas = construir_filas_formacion_experiencia(estudios, laborales, "123")
    assert len(filas) == 2
    assert filas[0]["tipo"] == "Educación formal"
    assert filas[1]["tipo"] == "Experiencia laboral"


def test_curso_capacitacion_se_distingue_de_educacion_formal():
    estudios = [{"institucion": "SENA", "nombre_curso": "Construcción en seco", "nivel": "curso_capacitacion", "horas": 40, "paginas": [15]}]
    filas = construir_filas_formacion_experiencia(estudios, [], "123")
    assert filas[0]["tipo"] == "Curso-capacitación"
    assert filas[0]["duracion_horas_o_meses"] == 40


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
