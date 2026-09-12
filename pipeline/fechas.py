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


def fecha_fin_efectiva(fecha_fin, fecha_cierre_inscripcion) -> date:
    """Fecha de fin a usar para contar experiencia, nunca más allá del cierre de inscripción.

    Cubre dos casos reales encontrados en expedientes: `fecha_fin` nula (la persona
    "sigue laborando a la fecha", sin fecha de terminación en la constancia) y
    `fecha_fin` en el futuro (contrato a término fijo que aún no termina al momento
    de extraer el documento). En ambos casos no se puede contar experiencia que
    todavía no ha ocurrido — se tope en la fecha de cierre de inscripción.
    """
    cierre = parse_fecha(fecha_cierre_inscripcion)
    if fecha_fin is None:
        return cierre
    return min(parse_fecha(fecha_fin), cierre)
