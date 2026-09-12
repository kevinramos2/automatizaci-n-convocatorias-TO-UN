"""Utilidades de fecha compartidas entre el motor de validación y el de scoring."""
from datetime import date


def parse_fecha(valor) -> date:
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor))


def meses_entre(inicio: date, fin: date) -> int:
    """Meses completos entre dos fechas (Sección 6.2: '1 punto por cada mes completo')."""
    meses = (fin.year - inicio.year) * 12 + (fin.month - inicio.month)
    if fin.day < inicio.day:
        meses -= 1
    return max(meses, 0)
