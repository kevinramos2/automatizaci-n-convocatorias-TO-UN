"""Detección local de páginas en blanco (reversos sin contenido) en un legajo escaneado.

No usa la API de Claude: mide contenido visual de la página renderizada a bajo DPI.
Ver Sección 2.3 y Fase 1 de plan-automatizacion-convocatoria.md.
"""
import json
from pathlib import Path

import pymupdf as fitz
import numpy as np

CONFIG_PATH = Path(__file__).parent.parent / "config" / "parametros.json"

BLANCO = "blank"
POSIBLE_BLANCO = "posible_blanco_baja_confianza"
CON_CONTENIDO = "con_contenido"


def _cargar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["deteccion_paginas_blancas"]


def _ratio_contenido_visual(page: fitz.Page, dpi: int) -> float:
    """Fracción de píxeles no-blancos en la página renderizada (0.0 = página en blanco)."""
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8)
    umbral_blanco_pixel = 250
    no_blancos = np.count_nonzero(arr < umbral_blanco_pixel)
    return float(no_blancos) / arr.size


def analizar_pagina(page: fitz.Page, config: dict | None = None) -> dict:
    """Clasifica una sola página como blank / posible_blanco_baja_confianza / con_contenido.

    No descarta nada por sí mismo: solo etiqueta. La decisión de excluir del envío
    a la API la toma el llamador para `clasificacion == BLANCO`.
    """
    cfg = config or _cargar_config()
    ratio = _ratio_contenido_visual(page, cfg["dpi_render"])
    texto_len = len(page.get_text().strip())

    # Un texto digital extraíble es evidencia fuerte de contenido, independiente
    # de la densidad visual (relevante si algún documento no viene solo escaneado).
    # La mayoría de páginas reales de este pipeline son escaneos sin capa de texto,
    # así que en la práctica la clasificación recae en `ratio`.
    if texto_len > 0:
        clasificacion = CON_CONTENIDO
    elif ratio < cfg["umbral_blanco_ratio"]:
        clasificacion = BLANCO
    elif ratio < cfg["umbral_ambiguo_ratio"]:
        clasificacion = POSIBLE_BLANCO
    else:
        clasificacion = CON_CONTENIDO

    return {
        "ratio_contenido_visual": ratio,
        "texto_len": texto_len,
        "clasificacion": clasificacion,
    }


def clasificar_paginas_pdf(pdf_path: str) -> list[dict]:
    """Recorre todo el PDF y devuelve un registro por página (1-indexado), sin modificar el archivo."""
    cfg = _cargar_config()
    resultados = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            info = analizar_pagina(page, cfg)
            info["pagina"] = i
            info["blank"] = info["clasificacion"] == BLANCO
            resultados.append(info)
    return resultados


def paginas_para_clasificacion(pdf_path: str) -> list[int]:
    """Números de página (1-indexado) que deben enviarse al pipeline de clasificación de Claude.

    Excluye solo las marcadas como BLANCO puro; las 'posible_blanco_baja_confianza'
    siguen el flujo normal para no perder información real por error (Sección 2.3).
    """
    resultados = clasificar_paginas_pdf(pdf_path)
    return [r["pagina"] for r in resultados if r["clasificacion"] != BLANCO]
