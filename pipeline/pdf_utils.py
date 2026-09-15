"""Utilidades para convertir páginas de un PDF a imágenes para envío a la API de Claude."""
import base64

import pymupdf as fitz


def pagina_a_imagen_base64(pdf_path: str, numero_pagina: int, dpi: int = 150, rotacion: int = 0) -> str:
    """numero_pagina es 1-indexado (igual que blank_detector). Devuelve PNG en base64.

    `rotacion` (0/90/180/270) corrige escaneos que vinieron girados — no modifica el
    PDF en disco, solo cómo se renderiza esta imagen para enviarla a Claude. Se
    detectó necesario inspeccionando visualmente un lote real (Fase 7 del plan):
    algunos escaneos llegan consistentemente a 180°.
    """
    with fitz.open(pdf_path) as doc:
        page = doc[numero_pagina - 1]
        if rotacion:
            page.set_rotation(rotacion)
        pix = page.get_pixmap(dpi=dpi)
        png_bytes = pix.tobytes("png")
    return base64.standard_b64encode(png_bytes).decode("utf-8")


def paginas_a_imagenes_base64(pdf_path: str, numeros_pagina: list[int], dpi: int = 150, rotacion: int = 0) -> list[dict]:
    """Devuelve [{"pagina": N, "base64": "..."}] en el mismo orden de `numeros_pagina`."""
    with fitz.open(pdf_path) as doc:
        resultados = []
        for numero in numeros_pagina:
            page = doc[numero - 1]
            if rotacion:
                page.set_rotation(rotacion)
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes("png")
            resultados.append({"pagina": numero, "base64": base64.standard_b64encode(png_bytes).decode("utf-8")})
        return resultados
