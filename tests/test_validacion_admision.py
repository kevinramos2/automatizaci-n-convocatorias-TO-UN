import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.validacion_admision import (
    ADMITIDO,
    CUMPLE,
    NO_ADMITIDO,
    NO_CUMPLE,
    PENDIENTE_DE_REVISION,
    REQUIERE_REVISION,
    evaluar_admision,
    validar_certificado_alturas,
    validar_cedula,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

CFG = json.load(open(Path(__file__).parent.parent / "config" / "parametros.json", encoding="utf-8"))
# fecha_cierre_inscripcion = 2026-09-18, ventana evaluación médica = 30 días => 2026-08-19 a 2026-09-18


def test_formulario_completo_pendiente_entrega_por_defecto():
    r = validar_formulario(
        {"nombre": "Juan Perez", "cedula": "123", "correo": "a@b.com", "celular": "300", "direccion": "Calle 1"},
        {"nombre": "Juan Perez", "numero": "123"},
    )
    assert r.estado == REQUIERE_REVISION


def test_formulario_incompleto_no_cumple():
    r = validar_formulario({"nombre": "Juan Perez", "cedula": "123"}, {})
    assert r.estado == NO_CUMPLE


def test_formulario_nombre_en_orden_distinto_y_sin_tilde_no_marca_inconsistencia():
    # Caso real: cédula imprime "APELLIDOS NOMBRES", formulario se llena "NOMBRES APELLIDOS",
    # y una de las dos fuentes puede traer o no tildes. Mismo nombre, no debe marcar REQUIERE_REVISION
    # por esta causa (queda pendiente igual por la entrega, pero con el motivo correcto).
    r = validar_formulario(
        {"nombre": "Andrés Felipe Arroyave Rondon", "cedula": "1035870469", "correo": "a@b.com", "celular": "300", "direccion": "Calle 1"},
        {"nombre": "ARROYAVE RONDON ANDRES FELIPE", "numero": "1035870469"},
        entrega_confirmada=True,
    )
    assert r.estado == CUMPLE
    assert "no coincide" not in r.motivo


def test_formulario_cedula_no_coincide_requiere_revision():
    r = validar_formulario(
        {"nombre": "Juan Perez", "cedula": "123", "correo": "a@b.com", "celular": "300", "direccion": "Calle 1"},
        {"nombre": "Juan Perez", "numero": "999"},
    )
    assert r.estado == REQUIERE_REVISION


def test_formulario_entrega_confirmada_cumple():
    r = validar_formulario(
        {"nombre": "Juan Perez", "cedula": "123", "correo": "a@b.com", "celular": "300", "direccion": "Calle 1"},
        {"nombre": "Juan Perez", "numero": "123"},
        entrega_confirmada=True,
    )
    assert r.estado == CUMPLE


def test_cedula_no_aportada():
    assert validar_cedula({"aportada": False}).estado == NO_CUMPLE


def test_cedula_legible_cumple():
    assert validar_cedula({"aportada": True, "legible": True}).estado == CUMPLE


def test_constancia_estudio_solo_boletin_no_cumple():
    r = validar_constancia_estudio([{"es_boletin": True}])
    assert r.estado == NO_CUMPLE


def test_constancia_estudio_valida_cumple():
    r = validar_constancia_estudio([{"institucion": "Colegio X", "titulo": "Bachiller", "nivel": "secundaria"}])
    assert r.estado == CUMPLE


def test_experiencia_con_fecha_fin_nula_se_cuenta_hasta_cierre_inscripcion():
    # Caso real (expediente de ejemplo): "sigue laborando a la fecha", constancia sin fecha de fin.
    experiencias = [
        {"fecha_inicio": "2013-01-28", "fecha_fin": None, "relacionado": "SI", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == CUMPLE  # de 2013-01-28 a 2026-09-18 (cierre) son muchos años, sobra


def test_experiencia_con_fecha_fin_futura_no_cuenta_mas_alla_del_cierre():
    # Caso real: contrato a término fijo con fecha de fin posterior al cierre de inscripción.
    # Debe topar en el cierre (2026-09-18), no contar hasta la fecha futura del contrato.
    experiencias = [
        {"fecha_inicio": "2026-08-01", "fecha_fin": "2027-02-02", "relacionado": "SI", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    # De 2026-08-01 a 2026-09-18 (cierre) es menos de 2 meses completos, muy por debajo del minimo
    assert r.estado == NO_CUMPLE


def test_experiencia_relacionada_confirmada_supera_minimo_cumple():
    experiencias = [
        {"fecha_inicio": "2020-01-01", "fecha_fin": "2021-06-01", "relacionado": "SI", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == CUMPLE


def test_experiencia_no_relacionada_no_cuenta_no_cumple():
    experiencias = [
        {"fecha_inicio": "2020-01-01", "fecha_fin": "2021-06-01", "relacionado": "NO", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == NO_CUMPLE


def test_experiencia_pendiente_pero_insuficiente_incluso_si_cuenta_no_cumple():
    experiencias = [
        {"fecha_inicio": "2024-01-01", "fecha_fin": "2024-03-01", "relacionado": "PENDIENTE", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == NO_CUMPLE  # 2 meses, ni siquiera si se confirma llega a 12


def test_experiencia_pendiente_que_si_alcanzaria_minimo_requiere_revision():
    experiencias = [
        {"fecha_inicio": "2020-01-01", "fecha_fin": "2021-06-01", "relacionado": "PENDIENTE", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == REQUIERE_REVISION


def test_una_experiencia_confirmada_basta_aunque_otras_queden_no_relacionadas():
    # Caso real reportado: 3 certificados, solo 1 relacionado y ya alcanza el
    # mínimo — no debe quedar trabado esperando que se resuelvan los otros.
    experiencias = [
        {"fecha_inicio": "2020-01-01", "fecha_fin": "2021-06-01", "relacionado": "SI", "formato_valido": True},
        {"fecha_inicio": "2019-01-01", "fecha_fin": "2019-03-01", "relacionado": "NO", "formato_valido": True},
        {"fecha_inicio": "2018-01-01", "fecha_fin": "2018-02-01", "relacionado": "NO", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == CUMPLE


def test_una_experiencia_confirmada_basta_aunque_otra_siga_pendiente():
    experiencias = [
        {"fecha_inicio": "2020-01-01", "fecha_fin": "2021-06-01", "relacionado": "SI", "formato_valido": True},
        {"fecha_inicio": "2019-01-01", "fecha_fin": "2019-03-01", "relacionado": "PENDIENTE", "formato_valido": True},
    ]
    r = validar_constancias_laborales(experiencias, CFG)
    assert r.estado == CUMPLE


def test_certificado_alturas_vigente_cumple():
    r = validar_certificado_alturas({"aportado": True, "fecha_vencimiento": "2026-12-01"}, CFG)
    assert r.estado == CUMPLE


def test_certificado_alturas_vencido_antes_del_cierre_no_cumple():
    r = validar_certificado_alturas({"aportado": True, "fecha_vencimiento": "2026-09-01"}, CFG)
    assert r.estado == NO_CUMPLE


def test_evaluacion_medica_dentro_de_ventana_cumple():
    r = validar_evaluacion_medica({"aportado": True, "concepto_aptitud_alturas": True, "fecha_expedicion": "2026-09-01"}, CFG)
    assert r.estado == CUMPLE


def test_evaluacion_medica_fuera_de_ventana_no_cumple():
    r = validar_evaluacion_medica({"aportado": True, "concepto_aptitud_alturas": True, "fecha_expedicion": "2026-07-01"}, CFG)
    assert r.estado == NO_CUMPLE


def test_evaluacion_medica_sin_aptitud_alturas_no_cumple():
    r = validar_evaluacion_medica({"aportado": True, "concepto_aptitud_alturas": False, "fecha_expedicion": "2026-09-01"}, CFG)
    assert r.estado == NO_CUMPLE


def test_decision_final_admitido_cuando_todo_cumple():
    resultados = {"item": validar_formulario(
        {"nombre": "A", "cedula": "1", "correo": "a@b.com", "celular": "3", "direccion": "d"},
        {"nombre": "A", "numero": "1"}, entrega_confirmada=True,
    )}
    decision = evaluar_admision(resultados)
    assert decision["estado_sugerido"] == ADMITIDO


def test_decision_final_no_admitido_si_un_item_falla_aunque_otros_pendan():
    resultados = {
        "cedula": validar_cedula({"aportada": False}),  # NO_CUMPLE
        "estudio": validar_constancia_estudio([]),  # NO_CUMPLE
        "formulario": validar_formulario(
            {"nombre": "A", "cedula": "1", "correo": "a@b.com", "celular": "3", "direccion": "d"},
            {"nombre": "A", "numero": "1"},
        ),  # REQUIERE_REVISION (entrega pendiente)
    }
    decision = evaluar_admision(resultados)
    assert decision["estado_sugerido"] == NO_ADMITIDO
    assert "2.5.3" in decision["causal_sugerida"]


def test_decision_final_pendiente_si_nada_falla_pero_algo_esta_pendiente():
    resultados = {
        "formulario": validar_formulario(
            {"nombre": "A", "cedula": "1", "correo": "a@b.com", "celular": "3", "direccion": "d"},
            {"nombre": "A", "numero": "1"},
        ),  # REQUIERE_REVISION
        "cedula": validar_cedula({"aportada": True, "legible": True}),  # CUMPLE
    }
    decision = evaluar_admision(resultados)
    assert decision["estado_sugerido"] == PENDIENTE_DE_REVISION


if __name__ == "__main__":
    import inspect
    fallos = 0
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fallos += 1
            print(f"FALLO: {t.__name__}")
    print(f"{len(tests) - fallos}/{len(tests)} pruebas pasaron")
