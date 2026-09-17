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
from pipeline.sheets_estilos import aplicar_estilos_basicos, aplicar_estilos_maestro

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


def asegurar_hojas(spreadsheet: gspread.Spreadsheet, esquemas: dict = TODAS_LAS_HOJAS, aplicar_estilos: bool = True) -> dict:
    """Crea cada pestaña que falte y escribe sus encabezados en la fila 1 si está vacía.

    Nunca borra ni reordena columnas existentes — si una hoja ya existe con datos,
    se deja intacta (para no pisar trabajo de Personal Administrativo). El estilo
    (encabezado, ancho de columnas, y en Maestro el color verde/amarillo/rojo según
    Estado_confirmado_por_humano) se aplica UNA sola vez, solo a una pestaña recién
    creada — es formato condicional puro (una fórmula, nunca toca los valores de las
    celdas), así que colorea automáticamente cualquier fila que se agregue después,
    sin necesidad de volver a aplicarlo. `aplicar_estilos=False` es solo para pruebas
    con hojas simuladas, que no soportan las llamadas de gspread_formatting.
    """
    hojas_existentes = {ws.title: ws for ws in spreadsheet.worksheets()}
    resultado = {}

    for nombre_hoja, esquema in esquemas.items():
        ws = hojas_existentes.get(nombre_hoja)
        recien_creada = ws is None
        if recien_creada:
            ws = spreadsheet.add_worksheet(title=nombre_hoja, rows=_FILAS_INICIALES, cols=len(esquema) + _COLUMNAS_EXTRA)

        primera_fila = ws.row_values(1)
        if not primera_fila:
            ws.update("A1", [encabezados(esquema)])

        if recien_creada and aplicar_estilos:
            if nombre_hoja == "Maestro":
                aplicar_estilos_maestro(ws, esquema)
            else:
                aplicar_estilos_basicos(ws, esquema)

        resultado[nombre_hoja] = ws

    return resultado


def _escribir_al_final(worksheet: gspread.Worksheet, filas: list[list], num_columnas: int) -> None:
    """Calcula la fila destino con una lectura fresca de la hoja y escribe ahí

    con update() en vez de append_row()/append_rows(). Confirmado con datos
    reales: el endpoint values.append de Sheets (lo que usa append_row) "adivina"
    dónde termina la tabla, y esa detección no es confiable cuando se le pide
    agregar varias veces seguidas en poco tiempo — un lote de 3 guardados
    distintos terminó con solo el último sobreviviendo, cada uno "creado"
    correctamente según la respuesta de la API, pero todos aterrizando en la
    misma fila. update() con un rango explícito no depende de esa detección:
    nosotros decidimos la fila a partir de una lectura propia, justo antes de
    escribir.
    """
    filas_actuales = len(worksheet.get_all_values())
    primera_fila_destino = filas_actuales + 1
    ultima_fila_destino = primera_fila_destino + len(filas) - 1
    ultima_columna = gspread.utils.rowcol_to_a1(1, num_columnas).rstrip("0123456789")
    worksheet.update(f"A{primera_fila_destino}:{ultima_columna}{ultima_fila_destino}", filas, value_input_option="USER_ENTERED")


def upsert_fila(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]], clave_id: str, valor_id: str, datos: dict) -> str:
    """Inserta o actualiza (por `clave_id`) una fila. Devuelve "creada" o "actualizada".

    Evita duplicar la fila de un aspirante si su expediente se reprocesa.
    """
    if not valor_id or not str(valor_id).strip():
        raise ValueError(f"'{clave_id}' está vacío — no se puede identificar a qué aspirante corresponde esta fila. No se guarda nada.")

    col_id = claves(esquema).index(clave_id) + 1
    fila = fila_desde_dict(esquema, datos)

    celda = worksheet.find(str(valor_id), in_column=col_id)  # None si no existe (gspread >= 6)

    if celda is None:
        _escribir_al_final(worksheet, [fila], len(esquema))
        return "creada"

    # Salvaguarda contra condiciones de carrera: entre el find() de arriba y este
    # punto, otra sesión (u otra pestaña) pudo haber escrito en la hoja — se
    # confirma justo antes de sobrescribir que la fila encontrada TODAVÍA
    # corresponde a este mismo aspirante. Con la red tan inestable que hemos visto
    # (reintentos de hasta 120s), mejor fallar ruidosamente aquí que arriesgarse a
    # pisar la fila de otro aspirante en silencio.
    valor_actual = worksheet.cell(celda.row, col_id).value
    if valor_actual != str(valor_id):
        raise RuntimeError(
            f"La fila {celda.row} ya no corresponde a '{valor_id}' (ahora tiene '{valor_actual}') — "
            "se detuvo el guardado para no sobrescribir a otro aspirante. Vuelve a intentar."
        )

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
    _escribir_al_final(worksheet, valores, len(esquema))
