"""Modelos Pydantic de entrada/salida de la API. Sin lógica de negocio — eso vive
en pipeline/*.py, esto solo describe la forma de los datos que cruzan la red.
"""
from pydantic import BaseModel, Field


class RevisionInput(BaseModel):
    """Lo que React manda al guardar una revisión — un campo por cada control que

    hoy existe en app_revision.py (firma, cada documento académico, cada
    relacionado de estudio/laboral, alturas, médica). Los diccionarios usan el
    índice del ítem (como string, por json) como llave, igual que
    "overrides_academicos"/"decisiones_relacionado_estudio" en la caché local.
    """
    revisado_por: str = Field(min_length=1)
    firma_verificada: str = "Pendiente"  # "Pendiente" | "Sí coincide" | "No coincide"
    overrides_academicos: dict[str, str] = {}  # índice -> "Según el sistema"|"Sí, válido"|"No es válido"
    decisiones_relacionado_estudio: dict[str, str] = {}  # índice -> "PENDIENTE"|"SI"|"NO"
    decisiones_relacionado_laboral: dict[str, str] = {}  # índice -> "PENDIENTE"|"SI"|"NO"
    alturas_override: str = "Según el sistema"
    medica_override: str = "Según el sistema"
