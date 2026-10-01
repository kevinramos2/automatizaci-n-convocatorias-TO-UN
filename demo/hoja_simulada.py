"""Reemplazo de Google Sheets solo para DEMO_MODE=1.

En el demo público no hay ninguna hoja de cálculo real ni credencial de Google:
al guardar una revisión, la fila que normalmente se escribiría en la pestaña
"Maestro" se agrega acá, a un JSON local — para que se vea la automatización
("al guardar, la fila aparece sola") sin depender de ninguna cuenta de Google.
Se reinicia solo si el proceso del backend se reinicia (comportamiento esperado
en un demo: cada visita empieza limpia).
"""
import json
from pathlib import Path
from threading import Lock

_RUTA = Path(__file__).parent / "hoja_simulada.json"
_CANDADO = Lock()


def agregar_fila(fila: dict) -> None:
    with _CANDADO:
        filas = _leer_archivo()
        filas.append(fila)
        _RUTA.write_text(json.dumps(filas, ensure_ascii=False, indent=2), encoding="utf-8")


def leer_filas() -> list[dict]:
    with _CANDADO:
        return _leer_archivo()


def _leer_archivo() -> list[dict]:
    if not _RUTA.exists():
        return []
    return json.loads(_RUTA.read_text(encoding="utf-8"))
