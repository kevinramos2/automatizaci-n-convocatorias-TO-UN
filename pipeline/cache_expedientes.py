"""Caché en disco de expedientes ya procesados, por hash del PDF.

Streamlit vuelve a ejecutar todo el script en cada interacción del usuario —
sin esto, cada clic en el panel podría volver a llamar a la API de Claude y
cobrar de nuevo por el mismo expediente. Solo se procesa (y se cobra) la primera
vez que se ve un PDF; después se reutiliza el resultado guardado.
"""
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from pipeline.validacion_admision import ResultadoRegla

CARPETA_CACHE = Path(__file__).parent.parent / "expedientes_procesados"


def hash_archivo(contenido_bytes: bytes) -> str:
    return hashlib.sha256(contenido_bytes).hexdigest()[:16]


def ruta_pdf(hash_: str) -> Path:
    return CARPETA_CACHE / f"{hash_}.pdf"


def _ruta_resultado(hash_: str) -> Path:
    return CARPETA_CACHE / f"{hash_}_resultado.json"


def existe_en_cache(hash_: str) -> bool:
    return _ruta_resultado(hash_).exists()


def guardar_pdf(hash_: str, contenido_bytes: bytes) -> Path:
    CARPETA_CACHE.mkdir(exist_ok=True)
    ruta = ruta_pdf(hash_)
    ruta.write_bytes(contenido_bytes)
    return ruta


def guardar_resultado(hash_: str, resultado_procesar_expediente: dict) -> None:
    """resultado_procesar_expediente: el dict que devuelve pipeline.procesar_expediente.procesar_expediente()."""
    CARPETA_CACHE.mkdir(exist_ok=True)
    serializable = dict(resultado_procesar_expediente)
    serializable["resultados_validacion"] = {k: asdict(r) for k, r in resultado_procesar_expediente["resultados_validacion"].items()}
    with open(_ruta_resultado(hash_), "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def cargar_resultado(hash_: str) -> dict | None:
    ruta = _ruta_resultado(hash_)
    if not ruta.exists():
        return None
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    datos["resultados_validacion"] = {k: ResultadoRegla(**v) for k, v in datos["resultados_validacion"].items()}
    return datos


def listar_cache() -> list[dict]:
    """Resumen de todos los expedientes ya procesados (para el selector del panel):

    hash, nombre, cédula, convocatoria (si se guardó) y estado sugerido. No carga
    el detalle completo de cada uno — solo lo necesario para mostrar la lista.
    """
    if not CARPETA_CACHE.exists():
        return []
    resumen = []
    for ruta in sorted(CARPETA_CACHE.glob("*_resultado.json")):
        hash_ = ruta.name.removesuffix("_resultado.json")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        resumen.append({
            "hash": hash_,
            "nombre": datos.get("formulario", {}).get("nombre", "—"),
            "cedula": datos.get("cedula", {}).get("numero", "—"),
            "convocatoria": datos.get("convocatoria", "—"),
            "estado_sugerido": datos.get("decision", {}).get("estado_sugerido", "—"),
        })
    return resumen
