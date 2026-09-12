import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias

CFG = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))


def test_fechas_y_entidad_coinciden_sin_inconsistencias():
    formulario = [{"entidad": "Todo en remodelación", "fecha_desde": "2013-01-28", "fecha_hasta": "2024-09-21"}]
    constancias = [{"entidad": "Todo en Remodelación", "fecha_inicio": "2013-01-28", "fecha_fin": "2024-09-21"}]
    assert cruzar_experiencia_formulario_vs_constancias(formulario, constancias, CFG) == []


def test_nombres_de_entidad_con_abreviatura_igual_coinciden():
    # Caso real: formulario "Universidad Nacional de Col." vs constancia con el nombre completo.
    formulario = [{"entidad": "Universidad Nacional de Col.", "fecha_desde": "2024-10-01", "fecha_hasta": "2026-09-07"}]
    constancias = [{"entidad": "Universidad Nacional de Colombia - Sede Medellín", "fecha_inicio": "2024-10-01", "fecha_fin": "2027-02-02"}]
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario, constancias, CFG)
    # Deben emparejar (misma entidad) y SOLO señalar la fecha de fin, no fallar el emparejamiento.
    assert len(inconsistencias) == 1
    assert inconsistencias[0]["tipo"] == "fecha_no_coincide"
    assert inconsistencias[0]["campo"] == "fecha de fin"
    assert "detalle" in inconsistencias[0] and inconsistencias[0]["detalle"]


def test_caso_real_legajo_ejemplo_detecta_discrepancia_de_fecha_fin():
    # Caso real encontrado: formulario dice hasta 2026-09-07, constancia oficial dice 2027-02-02.
    formulario = [{"entidad": "Universidad Nacional de Col.", "fecha_desde": "2024-10-01", "fecha_hasta": "2026-09-07"}]
    constancias = [{"entidad": "Universidad Nacional de Colombia - Sede Medellín", "fecha_inicio": "2024-10-01", "fecha_fin": "2027-02-02"}]
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario, constancias, CFG)
    diferencia_esperada = abs((__import__("datetime").date(2026, 9, 7) - __import__("datetime").date(2027, 2, 2)).days)
    assert inconsistencias[0]["diferencia_dias"] == diferencia_esperada


def test_diferencia_de_pocos_dias_dentro_de_tolerancia_no_marca():
    formulario = [{"entidad": "ACME SAS", "fecha_desde": "2020-01-10", "fecha_hasta": "2021-01-01"}]
    constancias = [{"entidad": "ACME SAS", "fecha_inicio": "2020-01-15", "fecha_fin": "2021-01-01"}]  # 5 dias de diferencia
    assert cruzar_experiencia_formulario_vs_constancias(formulario, constancias, CFG) == []


def test_entidad_sin_constancia_correspondiente_se_marca():
    formulario = [{"entidad": "Empresa Fantasma", "fecha_desde": "2020-01-01", "fecha_hasta": "2021-01-01"}]
    constancias = [{"entidad": "Otra Empresa Real", "fecha_inicio": "2020-01-01", "fecha_fin": "2021-01-01"}]
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario, constancias, CFG)
    assert len(inconsistencias) == 1
    assert inconsistencias[0]["tipo"] == "sin_constancia_correspondiente"


def test_campo_faltante_en_alguno_de_los_dos_no_se_compara():
    formulario = [{"entidad": "ACME SAS", "fecha_desde": "2020-01-01", "fecha_hasta": None}]
    constancias = [{"entidad": "ACME SAS", "fecha_inicio": "2020-01-01", "fecha_fin": "2021-06-01"}]
    assert cruzar_experiencia_formulario_vs_constancias(formulario, constancias, CFG) == []


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
