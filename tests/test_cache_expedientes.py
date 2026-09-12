import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.cache_expedientes import CARPETA_CACHE, cargar_resultado, existe_en_cache, guardar_resultado, hash_archivo
from pipeline.validacion_admision import ResultadoRegla

RESULTADO_FALSO = {
    "formulario": {"nombre": "Juan Perez"},
    "cedula": {"numero": "123"},
    "estudios": [],
    "laborales": [],
    "alturas": None,
    "medica": {},
    "resultados_validacion": {
        "cedula": ResultadoRegla(estado="cumple", motivo="Cédula aportada y legible"),
        "laboral": ResultadoRegla(estado="requiere_revision_manual", motivo="pendiente"),
    },
    "decision": {"estado_sugerido": "PENDIENTE DE REVISIÓN", "causal_sugerida": None},
    "inconsistencias": [],
    "uso_total": {"input_tokens": 100, "output_tokens": 50},
}


def test_hash_es_determinista():
    assert hash_archivo(b"contenido") == hash_archivo(b"contenido")
    assert hash_archivo(b"contenido") != hash_archivo(b"otro contenido")


def test_no_existe_en_cache_antes_de_guardar():
    h = hash_archivo(b"expediente de prueba unico 12345")
    assert not existe_en_cache(h)


def test_guardar_y_cargar_reconstruye_resultadoregla():
    h = hash_archivo(b"expediente de prueba unico 67890")
    try:
        guardar_resultado(h, RESULTADO_FALSO)
        assert existe_en_cache(h)
        cargado = cargar_resultado(h)
        assert isinstance(cargado["resultados_validacion"]["cedula"], ResultadoRegla)
        assert cargado["resultados_validacion"]["cedula"].estado == "cumple"
        assert cargado["decision"]["estado_sugerido"] == "PENDIENTE DE REVISIÓN"
        assert cargado["formulario"]["nombre"] == "Juan Perez"
    finally:
        if CARPETA_CACHE.exists():
            shutil.rmtree(CARPETA_CACHE)


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
