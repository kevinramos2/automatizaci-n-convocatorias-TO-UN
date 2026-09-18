"""Modelos Pydantic de entrada/salida de la API. Sin lógica de negocio — eso vive
en pipeline/*.py, esto solo describe la forma de los datos que cruzan la red.
"""
from pydantic import BaseModel


class RevisionInput(BaseModel):
    """Lo que React manda al guardar una revisión — un campo por cada control que

    hoy existe en app_revision.py (entrega de formulario y cédula, cada documento académico, cada
    relacionado de estudio/laboral, alturas, médica). Los diccionarios usan el
    índice del ítem (como string, por json) como llave, igual que
    "overrides_academicos"/"decisiones_relacionado_estudio" en la caché local.

    "revisado_por" NO exige mínimo de caracteres acá: esta misma forma la usa
    también /revision/preview, que se llama en vivo con cada clic — mientras el
    revisor todavía no ha escrito su nombre, el campo llega vacío y la vista
    previa igual debe poder calcularse. Que el nombre sea obligatorio para
    GUARDAR de verdad se valida en el endpoint /revision, no acá.
    """
    revisado_por: str = ""
    # Se confirman por separado: primero el formulario, luego la cédula.
    entrega_formulario: str = "Pendiente"  # "Pendiente" | "Sí aportó" | "No aportó"
    entrega_cedula: str = "Pendiente"  # "Pendiente" | "Sí aportó" | "No aportó"
    overrides_academicos: dict[str, str] = {}  # índice -> "Según el sistema"|"Sí, válido"|"No es válido"
    decisiones_relacionado_estudio: dict[str, str] = {}  # índice -> "PENDIENTE"|"SI"|"NO"
    decisiones_relacionado_laboral: dict[str, str] = {}  # índice -> "PENDIENTE"|"SI"|"NO"
    alturas_override: str = "Según el sistema"
    medica_override: str = "Según el sistema"
