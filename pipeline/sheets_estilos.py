"""Estilos y formato condicional para las hojas de Google Sheets (Fase 5 del plan:

"Formato condicional en el Sheet (verde/amarillo/rojo)").
"""
import gspread
import gspread_formatting as gf

_VERDE = gf.Color(0.80, 0.94, 0.80)
_AMARILLO = gf.Color(1.0, 0.95, 0.70)
_ROJO = gf.Color(0.96, 0.80, 0.80)
_GRIS_ENCABEZADO = gf.Color(0.85, 0.85, 0.85)

_ANCHO_COLUMNA_ANGOSTA = 110  # fechas, SI/NO, cumplimientos cortos
_ANCHO_COLUMNA_LARGA = 320  # nombres de entidad, observaciones, funciones


def _es_columna_de_texto_largo(encabezado: str) -> bool:
    claves = ("observ", "funcion", "motivo", "entidad", "nombre", "causal", "cargo")
    return any(clave in encabezado.lower() for clave in claves)


def aplicar_estilo_encabezado(worksheet: gspread.Worksheet, num_columnas: int) -> None:
    """Fila 1 en negrita con fondo gris, y congelada para que no se pierda al hacer scroll."""
    rango = f"A1:{gspread.utils.rowcol_to_a1(1, num_columnas)}"
    gf.format_cell_range(worksheet, rango, gf.CellFormat(
        backgroundColor=_GRIS_ENCABEZADO,
        textFormat=gf.TextFormat(bold=True),
        wrapStrategy="WRAP",
        verticalAlignment="MIDDLE",
    ))
    gf.set_frozen(worksheet, rows=1)


def ajustar_anchos_columnas(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]]) -> None:
    """Columnas de texto largo (observaciones, funciones, nombres) más anchas que

    las de valores cortos (fechas, SI/NO) — así no se ven cortados los valores
    largos ni se desperdicia espacio en los cortos.
    """
    rangos = []
    for i, (_clave, encabezado) in enumerate(esquema, start=1):
        letra = gspread.utils.rowcol_to_a1(1, i).rstrip("0123456789")
        ancho = _ANCHO_COLUMNA_LARGA if _es_columna_de_texto_largo(encabezado) else _ANCHO_COLUMNA_ANGOSTA
        rangos.append((f"{letra}:{letra}", ancho))
    gf.set_column_widths(worksheet, rangos)


def aplicar_wrap_a_datos(worksheet: gspread.Worksheet, num_columnas: int, num_filas: int = 500) -> None:
    """Ajuste de texto en las celdas de datos, para que las filas altas se lean

    completas en vez de cortarse (Google Sheets no ajusta el alto de fila solo).
    """
    rango = f"A2:{gspread.utils.rowcol_to_a1(num_filas, num_columnas)}"
    gf.format_cell_range(worksheet, rango, gf.CellFormat(wrapStrategy="WRAP", verticalAlignment="TOP"))


def aplicar_formato_condicional_estado(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]], clave_columna: str = "estado_sugerido") -> None:
    """Colorea toda la fila según Estado_sugerido: verde=ADMITIDO, amarillo=PENDIENTE

    DE REVISIÓN, rojo=NO ADMITIDO. Compara toda la fila contra la columna de
    estado con una fórmula, para que el color no quede solo en una celda suelta.
    """
    claves = [c for c, _ in esquema]
    col_estado = claves.index(clave_columna) + 1
    letra_estado = gspread.utils.rowcol_to_a1(1, col_estado).rstrip("0123456789")
    ultima_letra = gspread.utils.rowcol_to_a1(1, len(esquema)).rstrip("0123456789")
    rango_datos = f"A2:{ultima_letra}1000"

    reglas_por_valor = [
        ("ADMITIDO", _VERDE),
        ("PENDIENTE DE REVISIÓN", _AMARILLO),
        ("NO ADMITIDO", _ROJO),
    ]

    reglas_existentes = gf.get_conditional_format_rules(worksheet)
    reglas_existentes.clear()
    for valor, color in reglas_por_valor:
        formula = f'=${letra_estado}2="{valor}"'
        regla = gf.ConditionalFormatRule(
            ranges=[gf.GridRange.from_a1_range(rango_datos, worksheet)],
            booleanRule=gf.BooleanRule(
                condition=gf.BooleanCondition("CUSTOM_FORMULA", [formula]),
                format=gf.CellFormat(backgroundColor=color),
            ),
        )
        reglas_existentes.append(regla)
    reglas_existentes.save()


def aplicar_estilos_maestro(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]]) -> None:
    """Aplica todos los estilos de la hoja Maestro de una vez."""
    aplicar_estilo_encabezado(worksheet, len(esquema))
    ajustar_anchos_columnas(worksheet, esquema)
    aplicar_wrap_a_datos(worksheet, len(esquema))
    aplicar_formato_condicional_estado(worksheet, esquema)


def aplicar_estilos_basicos(worksheet: gspread.Worksheet, esquema: list[tuple[str, str]]) -> None:
    """Para las hojas sin columna de estado (Auditoría, Documentos por candidato,

    Documentos adicionales, Formación y Experiencia Detallada): encabezado +
    ancho de columnas + ajuste de texto, sin formato condicional por color.
    """
    aplicar_estilo_encabezado(worksheet, len(esquema))
    ajustar_anchos_columnas(worksheet, esquema)
    aplicar_wrap_a_datos(worksheet, len(esquema))
