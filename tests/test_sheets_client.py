"""Pruebas de sheets_client.py con objetos gspread simulados (sin credenciales reales)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.esquema_sheets import DOCUMENTOS_POR_CANDIDATO, MAESTRO
from pipeline.sheets_client import agregar_filas, asegurar_hojas, upsert_fila


class _CeldaFalsa:
    def __init__(self, row, value=None):
        self.row = row
        self.value = value


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
        # Simula escribir empezando en la fila indicada por el rango (ej. "A3:BP3"
        # o "A3:BP4" para varias filas) — una fila de `valores` por cada fila del rango.
        fila_num = int("".join(c for c in rango.split(":")[0] if c.isdigit()))
        for offset, fila_valores in enumerate(valores):
            destino = fila_num + offset
            while len(self.filas) < destino:
                self.filas.append([])
            self.filas[destino - 1] = fila_valores

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

    def cell(self, row, col):
        valor = self.filas[row - 1][col - 1] if len(self.filas) >= row and len(self.filas[row - 1]) >= col else None
        return _CeldaFalsa(row, value=valor)

    def get_all_values(self):
        return list(self.filas)


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
    # update() con rango explícito, no append_row(): confirmado con datos reales
    # que el endpoint de "agregar" de Sheets no es fiable con escrituras seguidas.
    assert len(ws.llamadas_append) == 0
    assert len(ws.llamadas_update) == 1
    assert len(ws.filas) == 2  # encabezado + la fila nueva


def test_upsert_actualiza_fila_existente_en_vez_de_duplicar():
    ws = _WorksheetFalso("Maestro", filas=[[e for _, e in MAESTRO]])
    upsert_fila(ws, MAESTRO, "id_aspirante", "123", {"id_aspirante": "123", "nombre_aspirante": "Juan"})
    resultado = upsert_fila(ws, MAESTRO, "id_aspirante", "123", {"id_aspirante": "123", "nombre_aspirante": "Juan Actualizado"})
    assert resultado == "actualizada"
    assert len(ws.filas) == 2  # encabezado + 1 sola fila de datos, no 2
    col_nombre = [c for c, _ in MAESTRO].index("nombre_aspirante")
    assert ws.filas[1][col_nombre] == "Juan Actualizado"


def test_upsert_rechaza_id_vacio():
    ws = _WorksheetFalso("Maestro", filas=[[e for _, e in MAESTRO]])
    try:
        upsert_fila(ws, MAESTRO, "id_aspirante", "", {"id_aspirante": "", "nombre_aspirante": "Sin cédula"})
        assert False, "debía lanzar ValueError con id_aspirante vacío"
    except ValueError:
        pass
    assert len(ws.llamadas_append) == 0 and len(ws.llamadas_update) == 0


def test_upsert_no_sobrescribe_si_la_fila_cambio_de_dueno():
    # Simula la condición de carrera: find() ubica la fila 2 para "123", pero para
    # cuando se va a escribir esa fila ya es de otro aspirante (otra sesión la
    # cambió entre medias) — debe abortar en vez de pisarla.
    class _WorksheetConCarrera(_WorksheetFalso):
        def find(self, texto, in_column=None):
            return _CeldaFalsa(2)

        def cell(self, row, col):
            return _CeldaFalsa(row, value="999")

    ws = _WorksheetConCarrera("Maestro", filas=[[e for _, e in MAESTRO], ["", "", "", "999"]])
    try:
        upsert_fila(ws, MAESTRO, "id_aspirante", "123", {"id_aspirante": "123", "nombre_aspirante": "Juan"})
        assert False, "debía lanzar RuntimeError al detectar el cambio de dueño de la fila"
    except RuntimeError:
        pass
    assert len(ws.llamadas_update) == 0  # no se llegó a escribir


def test_agregar_filas_hoja_de_solo_insercion():
    ws = _WorksheetFalso("Documentos por candidato", filas=[[e for _, e in DOCUMENTOS_POR_CANDIDATO]])
    agregar_filas(ws, DOCUMENTOS_POR_CANDIDATO, [
        {"id_aspirante": "123", "tipo_documento": "cedula"},
        {"id_aspirante": "123", "tipo_documento": "constancia_estudio"},
    ])
    assert len(ws.llamadas_append) == 0
    assert len(ws.filas) == 3  # encabezado + 2 filas nuevas


def test_agregar_filas_no_pisa_datos_existentes():
    ws = _WorksheetFalso("Documentos por candidato", filas=[
        [e for _, e in DOCUMENTOS_POR_CANDIDATO],
        ["999", "cedula", "", "", "", "", "", ""],
    ])
    agregar_filas(ws, DOCUMENTOS_POR_CANDIDATO, [{"id_aspirante": "123", "tipo_documento": "constancia_estudio"}])
    assert len(ws.filas) == 3
    assert ws.filas[1][0] == "999"  # la fila que ya estaba, intacta
    assert ws.filas[2][0] == "123"  # la fila nueva, después


def test_upsert_secuencial_no_sobrescribe_candidatos_anteriores():
    # Réplica del caso real reportado: varios aspirantes distintos guardados uno
    # tras otro deben quedar en filas separadas, no todos en la misma.
    ws = _WorksheetFalso("Maestro", filas=[[e for _, e in MAESTRO]])
    ids = ["111", "222", "333"]
    for id_ in ids:
        resultado = upsert_fila(ws, MAESTRO, "id_aspirante", id_, {"id_aspirante": id_, "nombre_aspirante": f"Candidato {id_}"})
        assert resultado == "creada"
    assert len(ws.filas) == 1 + len(ids)
    col_id = [c for c, _ in MAESTRO].index("id_aspirante")
    assert [fila[col_id] for fila in ws.filas[1:]] == ids


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
