import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.scoring_hoja_vida import (
    APROBADO,
    calcular_puntaje_educacion,
    calcular_puntaje_experiencia,
    calcular_puntaje_hoja_vida,
    puede_calcularse_puntaje,
)

CFG = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))


def test_dos_certificados_de_200h_suman_50_no_25():
    # Caso que resuelve la ambigüedad del plan: puntaje por certificado, luego se suma.
    certificados = [
        {"horas": 200, "relacionado": "SI"},
        {"horas": 250, "relacionado": "SI"},
    ]
    r = calcular_puntaje_educacion(certificados, CFG)
    assert r["puntaje"] == 50


def test_un_solo_certificado_de_200h_da_25():
    certificados = [{"horas": 200, "relacionado": "SI"}]
    r = calcular_puntaje_educacion(certificados, CFG)
    assert r["puntaje"] == 25


def test_certificados_no_relacionados_no_puntuan():
    certificados = [{"horas": 300, "relacionado": "NO"}]
    r = calcular_puntaje_educacion(certificados, CFG)
    assert r["puntaje"] == 0


def test_maximo_5_certificados_considerados():
    certificados = [{"horas": 200, "relacionado": "SI"} for _ in range(7)]
    r = calcular_puntaje_educacion(certificados, CFG)
    assert r["certificados_considerados"] == 5
    assert r["certificados_excedentes_no_contados"] == 2
    assert r["puntaje"] == 50  # 5 x 25 = 125, topado en 50


def test_horas_por_debajo_de_8_no_puntuan():
    certificados = [{"horas": 5, "relacionado": "SI"}]
    r = calcular_puntaje_educacion(certificados, CFG)
    assert r["puntaje"] == 0


def test_experiencia_exactamente_en_el_minimo_no_da_puntos_adicionales():
    experiencias = [{"fecha_inicio": "2020-01-01", "fecha_fin": "2021-01-01", "relacionado": "SI"}]  # 12 meses
    r = calcular_puntaje_experiencia(experiencias, CFG)
    assert r["puntaje"] == 0


def test_experiencia_adicional_al_minimo_da_un_punto_por_mes():
    experiencias = [{"fecha_inicio": "2020-01-01", "fecha_fin": "2021-03-01", "relacionado": "SI"}]  # 14 meses
    r = calcular_puntaje_experiencia(experiencias, CFG)
    assert r["puntaje"] == 2  # 14 - 12 minimo = 2 adicionales


def test_experiencia_topada_en_50_puntos():
    experiencias = [{"fecha_inicio": "2010-01-01", "fecha_fin": "2020-01-01", "relacionado": "SI"}]  # 120 meses
    r = calcular_puntaje_experiencia(experiencias, CFG)
    assert r["puntaje"] == 50


def test_puntaje_total_suma_educacion_y_experiencia():
    certificados = [{"horas": 200, "relacionado": "SI"}]
    experiencias = [{"fecha_inicio": "2020-01-01", "fecha_fin": "2021-03-01", "relacionado": "SI"}]
    r = calcular_puntaje_hoja_vida(certificados, experiencias, CFG)
    assert r["puntaje_total"] == 25 + 2


def test_gate_no_calcula_si_falta_alguna_prueba():
    assert puede_calcularse_puntaje(APROBADO, None) is False
    assert puede_calcularse_puntaje(None, APROBADO) is False
    assert puede_calcularse_puntaje(None, None) is False


def test_gate_calcula_solo_si_ambas_pruebas_aprobadas():
    assert puede_calcularse_puntaje(APROBADO, APROBADO) is True


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
