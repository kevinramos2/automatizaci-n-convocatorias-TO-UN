"""Pruebas de sheets_client.py con objetos gspread simulados (sin credenciales reales)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.esquema_sheets import DOCUMENTOS_POR_CANDIDATO, MAESTRO
from pipeline.sheets_client import agregar_filas, asegurar_hojas, upsert_fila


class _CeldaFalsa:
    def __init__(self, row):
        self.row = row


class _WorksheetFalso:
    def __init__(self, title, filas=None):
        self.title = title
        self.filas = filas or []  # lista de listas, incluye encabezado si se le puso
        self.llamadas_update = []
        self.llamadas_append = []

    def row_values(self, n):
        if len(self.filas) < n:
            return []
        return self.filas[n - 1]

    def update(self, rango, valores, value_input_option=None):
        self.llamadas_update.append((rango, valores))
        # Simula escribir en la fila indicada por el rango tipo "A3:BP3"
        fila_num = int("".join(c for c in rango.split(":")[0] if c.isdigit()))
        while len(self.filas) < fila_num:
            self.filas.append([])
        self.filas[fila_num - 1] = valores[0]

    def append_row(self, valores, value_input_option=None):
        self.llamadas_append.append(valores)
        self.filas.append(valores)

    def append_rows(self, valores, value_input_option=None):
        for v in valores:
            self.llamadas_append.append(v)
            self.filas.append(v)

    def find(self, texto, in_column=None):
        for i, fila in enumerate(self.filas, start=1):
            if len(fila) >= in_column and fila[in_column - 1] == texto:
                return _CeldaFalsa(i)
        return None


class _SpreadsheetFalso:
    def __init__(self):
        self._hojas = {}

    def worksheets(self):
        return list(self._hojas.values())

    def add_worksheet(self, title, rows, cols):
        ws = _WorksheetFalso(title)
        self._hojas[title] = ws
        return ws


def test_asegurar_hojas_crea_las_que_faltan_con_encabezados():
    ss = _SpreadsheetFalso()
    hojas = asegurar_hojas(ss, {"Maestro": MAESTRO})
    assert "Maestro" in hojas
    assert hojas["Maestro"].row_values(1)[:4] == ["Recibió", "Fecha Inscripción", "Nombre Aspirante", "ID Aspirante"]


def test_asegurar_hojas_no_pisa_encabezados_existentes():
    ss = _SpreadsheetFalso()
    ws_existente = _WorksheetFalso("Maestro", filas=[["YA HABIA DATOS AQUI"]])
    ss._hojas["Maestro"] = ws_existente
    hojas = asegurar_hojas(ss, {"Maestro": MAESTRO})
    assert hojas["Maestro"].row_values(1) == ["YA HABIA DATOS AQUI"]


def test_upsert_crea_fila_nueva_si_no_existe_el_id():
    ws = _WorksheetFalso("Maestro", filas=[[e for _, e in MAESTRO]])
    resultado = upsert_fila(ws, MAESTRO, "id_aspirante", "123", {"id_aspirante": "123", "nombre_aspirante": "Juan"})
    assert resultado == "creada"
    assert len(ws.llamadas_append) == 1


def test_upsert_actualiza_fila_existente_en_vez_de_duplicar():
    ws = _WorksheetFalso("Maestro", filas=[[e for _, e in MAESTRO]])
    upsert_fila(ws, MAESTRO, "id_aspirante", "123", {"id_aspirante": "123", "nombre_aspirante": "Juan"})
    resultado = upsert_fila(ws, MAESTRO, "id_aspirante", "123", {"id_aspirante": "123", "nombre_aspirante": "Juan Actualizado"})
    assert resultado == "actualizada"
    assert len(ws.filas) == 2  # encabezado + 1 sola fila de datos, no 2
    col_nombre = [c for c, _ in MAESTRO].index("nombre_aspirante")
    assert ws.filas[1][col_nombre] == "Juan Actualizado"


def test_agregar_filas_hoja_de_solo_insercion():
    ws = _WorksheetFalso("Documentos por candidato", filas=[[e for _, e in DOCUMENTOS_POR_CANDIDATO]])
    agregar_filas(ws, DOCUMENTOS_POR_CANDIDATO, [
        {"id_aspirante": "123", "tipo_documento": "cedula"},
        {"id_aspirante": "123", "tipo_documento": "constancia_estudio"},
    ])
    assert len(ws.llamadas_append) == 2


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
