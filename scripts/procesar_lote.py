"""Procesa un lote de expedientes reales con procesar_expediente(), guardando cada

uno en la caché de disco (misma que usa el panel) para que quede disponible en el
selector "Expedientes ya procesados". Reporta el costo de cada uno y el total.

Uso: python scripts/procesar_lote.py
"""
import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from pipeline.cache_expedientes import CARPETA_CACHE, cargar_resultado, existe_en_cache, guardar_pdf, guardar_resultado, hash_archivo, listar_cache, ruta_pdf
from pipeline.procesar_expediente import procesar_expediente

RAIZ = Path(__file__).parent.parent

# (archivo, convocatoria, rotacion_grados)
LOTE = [
    ("Escaneo0070.pdf", "TO-01", 180),
    ("Escaneo0071.pdf", "TO-01", 180),
    ("Escaneo0072.pdf", "TO-01", 180),
    ("Escaneo0073.pdf", "TO-02", 180),
    ("Escaneo0074.pdf", "TO-02", 180),
    ("Escaneo0075.pdf", "TO-02", 180),
]

_CRITERIOS_PATH = {
    "TO-01": RAIZ / "criterios" / "criterios_TO-01.json",
    "TO-02": RAIZ / "criterios" / "criterios_TO-02.json",
}


def _costo(uso: dict) -> float:
    return uso["input_tokens"] / 1e6 * 2.00 + uso["output_tokens"] / 1e6 * 10.00


def main():
    print(f"Carpeta de caché: {CARPETA_CACHE}")
    cfg = json.load(open(RAIZ / "config" / "parametros.json", encoding="utf-8"))
    client = anthropic.Anthropic()
    costo_total = 0.0
    hashes_procesados = []

    for nombre_archivo, convocatoria, rotacion in LOTE:
        ruta_origen = RAIZ / "data-ejemplo" / nombre_archivo
        criterios = json.load(open(_CRITERIOS_PATH[convocatoria], encoding="utf-8"))

        contenido = ruta_origen.read_bytes()
        hash_ = hash_archivo(contenido)

        if existe_en_cache(hash_):
            print(f"=== {nombre_archivo} — hash {hash_} — YA ESTÁ EN CACHÉ, se omite (sin costo) ===\n")
            hashes_procesados.append(hash_)
            continue

        guardar_pdf(hash_, contenido)  # ya verifica tamaño al guardar
        ruta_cache = ruta_pdf(hash_)

        print(f"=== {nombre_archivo} ({convocatoria}, rotación {rotacion}°) — hash {hash_} ===")
        resultado = procesar_expediente(str(ruta_cache), criterios, cfg, client=client, rotacion=rotacion)
        resultado["convocatoria"] = convocatoria
        resultado["rotacion"] = rotacion
        guardar_resultado(hash_, resultado)  # ya verifica releyendo al guardar

        # Verificación extra, independiente de la que hace guardar_resultado:
        # releer desde cero con cargar_resultado() (la misma función que usa el
        # panel) y confirmar que el nombre coincide antes de dar el archivo por bueno.
        releido = cargar_resultado(hash_)
        if releido is None or releido["formulario"].get("nombre") != resultado["formulario"].get("nombre"):
            raise RuntimeError(f"No se pudo confirmar el guardado de {nombre_archivo} (hash {hash_}) — deteniendo el lote sin seguir gastando.")

        costo = _costo(resultado["uso_total"])
        costo_total += costo
        hashes_procesados.append(hash_)
        nombre = resultado["formulario"].get("nombre", "?")
        cedula = resultado["cedula"].get("numero", "?")
        decision = resultado["decision"]["estado_sugerido"]
        print(f"  {nombre} (C.C. {cedula}) -> {decision}  |  costo: ${costo:.4f} USD  |  guardado y verificado en {ruta_cache}")
        print()

    print(f"=== COSTO TOTAL DEL LOTE: ${costo_total:.4f} USD ===")

    print("\nVerificación final (releyendo la carpeta de caché desde cero):")
    en_cache = {e["hash"] for e in listar_cache()}
    faltantes = [h for h in hashes_procesados if h not in en_cache]
    if faltantes:
        raise RuntimeError(f"ALERTA: estos hashes se procesaron pero NO aparecen en la caché al releerla: {faltantes}")
    for e in listar_cache():
        if e["hash"] in hashes_procesados:
            print(f"  OK — {e['nombre']} (C.C. {e['cedula']}, {e['convocatoria']})")
    print(f"\n{len(hashes_procesados)}/{len(LOTE)} expedientes procesados y confirmados en disco.")


if __name__ == "__main__":
    main()
