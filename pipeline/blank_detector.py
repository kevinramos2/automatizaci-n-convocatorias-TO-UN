"""Detección local de páginas en blanco (reversos sin contenido) en un expediente escaneado.

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


def _estadisticas_pagina(page: fitz.Page, dpi: int) -> tuple[float, float]:
    """(ratio de píxeles no-blancos, desviación estándar de grises) de la página renderizada.

    La desviación estándar es la señal principal: una página en blanco o de color
    casi uniforme (blanca, o gris/negra por un artefacto de escaneo) tiene poca
    variación de tono; una página con contenido real (texto, líneas, tablas)
    siempre mezcla tonos claros y oscuros y por eso tiene std alta. El ratio de
    no-blancos por sí solo falla con escaneos oscuros uniformes (ver Fase 1:
    3 páginas del expediente de ejemplo con ~95% de "tinta" pero std < 6, sin
    contenido real legible — el propio clasificador de Claude las marcó como
    en blanco/vacías).
    """
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8)
    umbral_blanco_pixel = 250
    ratio = float(np.count_nonzero(arr < umbral_blanco_pixel)) / arr.size
    return ratio, float(arr.std())


def analizar_pagina(page: fitz.Page, config: dict | None = None) -> dict:
    """Clasifica una sola página como blank / posible_blanco_baja_confianza / con_contenido.

    No descarta nada por sí mismo: solo etiqueta. La decisión de excluir del envío
    a la API la toma el llamador para `clasificacion == BLANCO`.
    """
    cfg = config or _cargar_config()
    ratio, std = _estadisticas_pagina(page, cfg["dpi_render"])
    texto_len = len(page.get_text().strip())

    # Un texto digital extraíble es evidencia fuerte de contenido, independiente
    # de la variación visual (relevante si algún documento no viene solo escaneado).
    # La mayoría de páginas reales de este pipeline son escaneos sin capa de texto,
    # así que en la práctica la clasificación recae en `std`.
    if texto_len > 0:
        clasificacion = CON_CONTENIDO
    elif std < cfg["umbral_std_blanco"]:
        clasificacion = BLANCO
    elif std < cfg["umbral_std_ambiguo"]:
        clasificacion = POSIBLE_BLANCO
    else:
        clasificacion = CON_CONTENIDO

    return {
        "ratio_contenido_visual": ratio,
        "std_grises": std,
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
