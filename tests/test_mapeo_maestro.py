import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.esquema_sheets import MAESTRO, fila_desde_dict
from pipeline.mapeo_maestro import construir_fila_maestro
from pipeline.validacion_admision import (
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

CFG = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))

FORMULARIO = {
    "nombre": "Juan Perez", "cedula": "123", "correo": "juan@x.com", "celular": "300",
    "direccion": "Calle 1", "fecha_inscripcion": "2026-09-10",
    "experiencia": [{"entidad": "ACME", "fecha_desde": "2020-01-01", "fecha_hasta": "2022-01-01"}],
}
CEDULA = {"aportada": True, "legible": True, "nombre": "Juan Perez", "numero": "123"}
ESTUDIOS = [{"institucion": "Colegio X", "titulo": "Bachiller", "nivel": "secundaria", "fecha_terminacion": "2015-01-01", "paginas": [3]}]
LABORALES = [{"entidad": "ACME", "cargo": "Ayudante", "funciones": "Varias", "fecha_inicio": "2020-01-01", "fecha_fin": "2022-01-01", "relacionado": "SI", "paginas": [5]}]
ALTURAS = {"aportado": True, "entidad_emisora": "SENA", "fecha_expedicion": "2026-01-01", "fecha_vencimiento": "2028-01-01", "paginas": [7]}
MEDICA = {"aportado": True, "entidad_emisora": "IPS X", "fecha_expedicion": "2026-09-01", "concepto_aptitud_alturas": True}


def _resultados_y_decision(firma_verificada=True):
    resultados = {
        "formulario": validar_formulario(FORMULARIO, CEDULA, firma_verificada=firma_verificada),
        "cedula": validar_cedula(CEDULA),
        "estudio": validar_constancia_estudio(ESTUDIOS),
        "laboral": validar_constancias_laborales(LABORALES, CFG),
        "alturas": validar_certificado_alturas(ALTURAS, CFG),
        "medica": validar_evaluacion_medica(MEDICA, CFG),
    }
    return resultados, evaluar_admision(resultados)


def test_fila_tiene_la_longitud_del_esquema():
    resultados, decision = _resultados_y_decision()
    fila = construir_fila_maestro(FORMULARIO, CEDULA, ESTUDIOS, LABORALES, ALTURAS, MEDICA, resultados, decision, [], CFG)
    fila_ordenada = fila_desde_dict(MAESTRO, fila)
    assert len(fila_ordenada) == len(MAESTRO)


def test_admitido_si_no_nunca_se_autocompleta():
    # Columnas de decisión oficial: construir_fila_maestro() NUNCA las llena — las
    # llena el panel directamente, solo cuando un humano confirma la revisión.
    resultados, decision = _resultados_y_decision()
    fila = construir_fila_maestro(FORMULARIO, CEDULA, ESTUDIOS, LABORALES, ALTURAS, MEDICA, resultados, decision, [], CFG)
    assert fila.get("admitido_si_no") in (None, "")
    assert fila.get("causal_no_admision") in (None, "")
    assert fila.get("estado_confirmado_por_humano") in (None, "")
    assert decision["estado_sugerido"] == "ADMITIDO"


def test_verificacion_mintrabajo_nunca_se_autocompleta():
    resultados, decision = _resultados_y_decision()
    fila = construir_fila_maestro(FORMULARIO, CEDULA, ESTUDIOS, LABORALES, ALTURAS, MEDICA, resultados, decision, [], CFG)
    assert fila.get("alturas_consulta_mintrabajo") in (None, "")
    assert fila.get("alturas_coincide_mintrabajo") in (None, "")


def test_segundo_bloque_de_experiencia_no_tiene_columna_relacionada():
    # Replica la asimetría real del TO-26.xlsx: solo el bloque 1 tiene "relacionada".
    laborales_dos = LABORALES + [{"entidad": "Otra Empresa", "cargo": "Oficial", "funciones": "X",
                                    "fecha_inicio": "2022-02-01", "fecha_fin": "2023-02-01", "relacionado": "SI", "paginas": [9]}]
    resultados, decision = _resultados_y_decision()
    fila = construir_fila_maestro(FORMULARIO, CEDULA, ESTUDIOS, laborales_dos, ALTURAS, MEDICA, resultados, decision, [], CFG)
    assert "relacionada_2" not in fila
    assert fila["entidad_2"] == "Otra Empresa"


def test_observaciones_incluye_hallazgos_de_consistencia():
    resultados, decision = _resultados_y_decision()
    fila = construir_fila_maestro(
        FORMULARIO, CEDULA, ESTUDIOS, LABORALES, ALTURAS, MEDICA, resultados, decision,
        ["En ACME, la fecha de fin declarada difiere 30 días de la constancia."], CFG,
    )
    assert "ACME" in fila["observaciones"]


def test_alturas_fecha_finalizacion_usa_fecha_expedicion_no_vencimiento():
    resultados, decision = _resultados_y_decision()
    fila = construir_fila_maestro(FORMULARIO, CEDULA, ESTUDIOS, LABORALES, ALTURAS, MEDICA, resultados, decision, [], CFG)
    assert fila["alturas_fecha_finalizacion_curso"] == "2026-01-01"


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
