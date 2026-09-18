"""Pruebas de api/main.py con Sheets y caché local simulados (sin tocar datos

reales ni gastar API de Claude). Verifica la orquestación nueva (endpoints) —
las reglas de negocio que llama (validacion_admision, mapeo_maestro, etc.) ya
tienen su propia suite.
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi.testclient import TestClient

import api.main as api_main
from pipeline.validacion_admision import CUMPLE, REQUIERE_REVISION, ResultadoRegla

client = TestClient(api_main.app)

_HASH = "test0000deadbeef"


def _resultado_base() -> dict:
    return {
        "formulario": {
            "nombre": "Juan Pérez", "cedula": "123", "correo": "j@x.com",
            "celular": "3000000000", "direccion": "Calle 1", "experiencia": [],
        },
        "cedula": {"nombre": "Juan Pérez", "numero": "123", "aportada": True, "legible": True},
        "estudios": [
            {"nivel": "primaria", "institucion": "Escuela X", "titulo": None, "ultimo_anio_cursado": "2000", "paginas": [2]},
        ],
        "laborales": [
            {"entidad": "ACME", "cargo": "Obrero", "fecha_inicio": "2020-01-01", "fecha_fin": "2026-01-01",
             "formato_valido": True, "relacionado_sugerido": "SI", "paginas": [3]},
        ],
        "alturas": {"aportado": True, "fecha_vencimiento": "2027-01-01", "entidad_emisora": "X"},
        "medica": {"aportado": True, "concepto_aptitud_alturas": True, "fecha_expedicion": "2026-09-10", "entidad_emisora": "Y"},
        "resultados_validacion": {
            "formulario": ResultadoRegla(REQUIERE_REVISION, "pendiente entrega"),
            "cedula": ResultadoRegla(CUMPLE, "ok"),
            "estudio": ResultadoRegla(CUMPLE, "ok"),
            "laboral": ResultadoRegla(REQUIERE_REVISION, "pendiente relacionado"),
            "alturas": ResultadoRegla(CUMPLE, "ok"),
            "medica": ResultadoRegla(CUMPLE, "ok"),
        },
        "decision": {"estado_sugerido": "PENDIENTE DE REVISIÓN", "causal_sugerida": None},
        "inconsistencias": [], "documentos_extraidos": [], "rotacion": 0, "rotaciones_paginas": {},
        "uso_total": {"input_tokens": 0, "output_tokens": 0},
    }


class _WorksheetFalso:
    def __init__(self):
        self.filas = []
        self.actualizaciones = []

    def get_all_values(self):
        return [[]] + self.filas

    def find(self, texto, in_column=None):
        return None

    def update(self, rango, valores, value_input_option=None):
        self.actualizaciones.append((rango, valores))
        self.filas.extend(valores)


def test_listar_expedientes_lee_cache_real():
    r = client.get("/api/expedientes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_obtener_expediente_404_si_no_existe():
    r = client.get("/api/expedientes/no-existe-este-hash")
    assert r.status_code == 404


def test_revision_rechaza_si_quedan_pendientes():
    with patch.object(api_main, "cargar_resultado", return_value=_resultado_base()):
        r = client.post(f"/api/expedientes/{_HASH}/revision", json={"revisado_por": "Tester"})
    assert r.status_code == 400


def test_revision_guarda_cuando_queda_todo_confirmado():
    guardados = {}

    def _guardar_resultado_falso(hash_, resultado):
        guardados["ultimo"] = resultado

    ws_maestro = _WorksheetFalso()
    ws_auditoria = _WorksheetFalso()

    with patch.object(api_main, "cargar_resultado", return_value=_resultado_base()), \
         patch.object(api_main, "guardar_resultado", side_effect=_guardar_resultado_falso), \
         patch.object(api_main, "autenticar", return_value=None), \
         patch.object(api_main, "abrir_spreadsheet", return_value=None), \
         patch.object(api_main, "asegurar_hojas", return_value={"Maestro": ws_maestro, "Auditoría": ws_auditoria}), \
         patch.dict("os.environ", {"GOOGLE_SHEETS_SPREADSHEET_ID": "fake-id"}):
        r = client.post(f"/api/expedientes/{_HASH}/revision", json={
            "revisado_por": "Tester",
            "entrega_verificada": "Sí, entregó ambos",
            "overrides_academicos": {"0": "Sí, válido"},
            "decisiones_relacionado_laboral": {"0": "SI"},
            "alturas_override": "Según el sistema",
            "medica_override": "Según el sistema",
        })

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado_final"] == "ADMITIDO"

    # Se escribió una fila en Maestro y al menos una en Auditoría.
    assert len(ws_maestro.filas) == 1
    assert len(ws_auditoria.filas) >= 1

    # La caché local quedó con "revision_humana" — no solo el estado final.
    cache_guardada = guardados["ultimo"]
    assert cache_guardada["estado_confirmado_por_humano"] == "ADMITIDO"
    assert cache_guardada["revision_humana"]["entrega_verificada"] == "Sí, entregó ambos"
    assert cache_guardada["revision_humana"]["overrides_academicos"] == {"0": "Sí, válido"}
    assert cache_guardada["revision_humana"]["revisado_por"] == "Tester"


def test_revision_valida_estado_entrega():
    with patch.object(api_main, "cargar_resultado", return_value=_resultado_base()):
        r = client.post(f"/api/expedientes/{_HASH}/revision", json={
            "revisado_por": "Tester", "entrega_verificada": "valor-invalido",
        })
    assert r.status_code == 400


def test_procesar_rechaza_convocatoria_invalida():
    r = client.post(
        "/api/expedientes/procesar",
        data={"convocatoria": "TO-99"},
        files={"archivo": ("x.pdf", b"contenido falso", "application/pdf")},
    )
    assert r.status_code == 400


def test_procesar_expediente_ya_cacheado_no_llama_a_claude():
    # El caso más importante para no gastar de más: si el hash del archivo ya
    # está procesado, ni pipeline.procesar_expediente ni anthropic.Anthropic()
    # deben llamarse — el endpoint tiene que cortar camino ANTES de eso.
    with patch.object(api_main, "existe_en_cache", return_value=True), \
         patch.object(api_main, "procesar_expediente") as mock_procesar, \
         patch("anthropic.Anthropic") as mock_cliente:
        r = client.post(
            "/api/expedientes/procesar",
            data={"convocatoria": "TO-01"},
            files={"archivo": ("x.pdf", b"contenido falso", "application/pdf")},
        )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ya_procesado"] is True
    assert cuerpo["costo_usd"] == 0.0
    mock_procesar.assert_not_called()
    mock_cliente.assert_not_called()


def test_revision_exige_nombre_de_revisor():
    # revisado_por vacío: rechazado explícitamente en /revision (400), pero el
    # esquema en sí lo permite vacío — /revision/preview reusa la misma forma y
    # se llama en vivo con cada clic, antes de que el revisor escriba su nombre.
    with patch.object(api_main, "cargar_resultado", return_value=_resultado_base()):
        r = client.post(f"/api/expedientes/{_HASH}/revision", json={"revisado_por": ""})
        assert r.status_code == 400

        r_preview = client.post(f"/api/expedientes/{_HASH}/revision/preview", json={"revisado_por": ""})
        assert r_preview.status_code == 200


if __name__ == "__main__":
    fallos = 0
    tests = [obj for name, obj in list(globals().items()) if name.startswith("test_") and callable(obj)]
    for t in tests:
        try:
            t()
        except AssertionError as e:
            fallos += 1
            print(f"FALLO: {t.__name__}: {e}")
        except Exception as e:
            fallos += 1
            print(f"ERROR: {t.__name__}: {type(e).__name__}: {e}")
    print(f"{len(tests) - fallos}/{len(tests)} pruebas pasaron")
