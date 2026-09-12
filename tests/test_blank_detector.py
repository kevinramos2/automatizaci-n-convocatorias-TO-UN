"""Pruebas del detector de páginas en blanco con PDFs sintéticos.

No sustituyen la calibración contra el legajo real de 36 páginas (pendiente,
ver Fase 1 del plan) pero validan que la lógica distingue los tres casos base.
"""
import sys
from pathlib import Path

import pymupdf as fitz

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.blank_detector import BLANCO, CON_CONTENIDO, POSIBLE_BLANCO, analizar_pagina


def _pagina_blanca() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page()
    return page


def _pagina_con_texto() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 100), "CONSTANCIA LABORAL\nNombre de la entidad: Universidad Nacional\nCargo: Ayudante", fontsize=14)
    return page


def _pagina_con_sello_pequeno() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page()
    # Simula un sello/firma suelta: un pequeño círculo relleno en una esquina.
    page.draw_circle((100, 100), 40, color=(0, 0, 0), fill=(0, 0, 0))
    return page


def test_pagina_totalmente_blanca_se_marca_blank():
    resultado = analizar_pagina(_pagina_blanca())
    assert resultado["clasificacion"] == BLANCO
    assert resultado["texto_len"] == 0


def test_pagina_con_texto_se_marca_con_contenido():
    resultado = analizar_pagina(_pagina_con_texto())
    assert resultado["clasificacion"] == CON_CONTENIDO
    assert resultado["texto_len"] > 0


def test_pagina_con_marca_pequena_no_se_descarta_automaticamente():
    resultado = analizar_pagina(_pagina_con_sello_pequeno())
    # Regla del plan (Sección 2.3): un sello/firma suelta no debe clasificarse como BLANCO puro.
    assert resultado["clasificacion"] in (POSIBLE_BLANCO, CON_CONTENIDO)
    assert resultado["clasificacion"] != BLANCO


if __name__ == "__main__":
    test_pagina_totalmente_blanca_se_marca_blank()
    test_pagina_con_texto_se_marca_con_contenido()
    test_pagina_con_marca_pequena_no_se_descarta_automaticamente()
    print("OK: 3/3 pruebas pasaron")
