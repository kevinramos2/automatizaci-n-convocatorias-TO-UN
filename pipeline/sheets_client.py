"""Cliente de Google Sheets — Fase 4 del plan.

Permisos mínimos (Sección 1 del plan: "cuenta de servicio compartida solo con
esa hoja, no con toda la carpeta"): se pide únicamente el scope de Sheets, no
de Drive. Por eso este módulo NUNCA crea el spreadsheet — lo abre por ID. El
spreadsheet lo crea el humano (con su propia cuenta de Google) y lo comparte
como Editor con el correo de la cuenta de servicio; solo entonces el pipeline
puede leerlo/escribirlo.
"""
import gspread
from google.oauth2.service_account import Credentials

from pipeline.esquema_sheets import TODAS_LAS_HOJAS, claves, encabezados, fila_desde_dict

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_FILAS_INICIALES = 200
_COLUMNAS_EXTRA = 5  # margen sobre el número de columnas del esquema


def autenticar(ruta_credenciales: str) -> gspread.Client:
    creds = Credentials.from_service_account_file(ruta_credenciales, scopes=_SCOPES)
    return gspread.authorize(creds)


def correo_cuenta_de_servicio(ruta_credenciales: str) -> str:
    """Lee el client_email del JSON de credenciales — es el correo que hay que

    invitar como Editor en el Google Sheet antes de que el pipeline pueda usarlo.
    """
    import json
    with open(ruta_credenciales, encoding="utf-8") as f:
        return json.load(f)["client_email"]


def abrir_spreadsheet(client: gspread.Client, spreadsheet_id: str) -> gspread.Spreadsheet:
    return client.open_by_key(spreadsheet_id)


def asegurar_hojas(spreadsheet: gspread.Spreadsheet, esquemas: dict = TODAS_LAS_HOJAS) -> dict:
    """Crea cada pestaña que falte y escribe sus encabezados en la fila 1 si está vacía.

    Nunca borra ni reordena columnas existentes — si una hoja ya existe con datos,
    se deja intacta (para no pisar trabajo de Personal Administrativo).
    """
    hojas_existentes = {ws.title: ws for ws in spreadsheet.worksheets()}
    resultado = {}

    for nombre_hoja, esquema in esquemas.items():
        ws = hojas_existentes.get(nombre_hoja)
        if ws is None:
            ws = spreadsheet.add_worksheet(title=nombre_hoja, rows=_FILAS_INICIALES, cols=len(esquema) + _COLUMNAS_EXTRA)

        primera_fila = ws.row_values(1)
        if not primera_fila:
            ws.update("A1", [encabezados(esquema)])

        resultado[nombre_hoja] = ws

    return resultado


def upsert_fila(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]], clave_id: str, valor_id: str, datos: dict) -> str:
    """Inserta o actualiza (por `clave_id`) una fila. Devuelve "creada" o "actualizada".

    Evita duplicar la fila de un aspirante si su legajo se reprocesa.
    """
    col_id = claves(esquema).index(clave_id) + 1
    fila = fila_desde_dict(esquema, datos)

    celda = worksheet.find(str(valor_id), in_column=col_id)  # None si no existe (gspread >= 6)

    if celda is None:
        worksheet.append_row(fila, value_input_option="USER_ENTERED")
        return "creada"

    ultima_columna = gspread.utils.rowcol_to_a1(celda.row, len(esquema)).rstrip("0123456789")
    worksheet.update(f"A{celda.row}:{ultima_columna}{celda.row}", [fila], value_input_option="USER_ENTERED")
    return "actualizada"


def agregar_filas(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]], filas: list[dict]) -> None:
    """Agrega varias filas de una vez (para hojas sin upsert por ID: Auditoría,

    Documentos por candidato, Formación y Experiencia Detallada — son de solo
    inserción, una fila nueva por evento/documento, no "una fila por aspirante").
    """
    if not filas:
        return
    valores = [fila_desde_dict(esquema, d) for d in filas]
    worksheet.append_rows(valores, value_input_option="USER_ENTERED")
