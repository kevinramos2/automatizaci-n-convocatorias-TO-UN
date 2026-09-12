"""Escribe los resultados de un expediente ya procesado en las 5 hojas de Google Sheets.

No llama a la API de Claude — usa los JSON ya generados en data-ejemplo/ y
llama solo a la API de Google Sheets (gratuita). Requiere service-account.json
y GOOGLE_SHEETS_SPREADSHEET_ID en .env (ver scripts/verificar_sheets.py).
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from pipeline.agrupador_documentos import agrupar_en_documentos
from pipeline.blank_detector import clasificar_paginas_pdf
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.esquema_sheets import AUDITORIA, DOCUMENTOS_ADICIONALES, DOCUMENTOS_POR_CANDIDATO, FORMACION_EXPERIENCIA_DETALLADA, MAESTRO
from pipeline.mapeo_auxiliar import (
    construir_filas_auditoria,
    construir_filas_documentos_adicionales,
    construir_filas_documentos_candidato,
    construir_filas_formacion_experiencia,
)
from pipeline.mapeo_maestro import construir_fila_maestro
from pipeline.sheets_client import abrir_spreadsheet, agregar_filas, asegurar_hojas, autenticar, upsert_fila
from pipeline.validacion_admision import (
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

RAIZ = Path(__file__).parent.parent


def por_tipo(extracciones, tipo):
    return [e for e in extracciones if e["tipo"] == tipo]


def main():
    cfg = json.load(open(RAIZ / "config" / "parametros.json", encoding="utf-8"))
    extracciones = json.load(open(RAIZ / "data-ejemplo" / "extraccion-expediente-01.json", encoding="utf-8"))
    clasificacion = json.load(open(RAIZ / "data-ejemplo" / "clasificacion-expediente-01.json", encoding="utf-8"))["resultados"]
    pdf_path = str(RAIZ / "data-ejemplo" / "expediente-ejemplo-01.pdf")

    formulario = por_tipo(extracciones, "formulario_inscripcion")[0]["datos"]
    cedula = por_tipo(extracciones, "cedula")[0]["datos"]
    estudios = [{**e["datos"], "paginas": e["paginas"]} for e in por_tipo(extracciones, "constancia_estudio") if not e.get("requiere_reclasificacion")]
    laborales = [{**e["datos"], "paginas": e["paginas"], "relacionado": "PENDIENTE"} for e in por_tipo(extracciones, "constancia_laboral")]
    alturas_docs = [{**e["datos"], "paginas": e["paginas"]} for e in por_tipo(extracciones, "certificado_alturas") if not e.get("requiere_reclasificacion")]
    alturas = alturas_docs[0] if alturas_docs else None
    medica = por_tipo(extracciones, "evaluacion_medica")[0]["datos"]

    id_aspirante = cedula["numero"]

    resultados = {
        "formulario": validar_formulario(
            {k: formulario[k] for k in ("nombre", "cedula", "correo", "celular", "direccion")},
            {"nombre": cedula["nombre"], "numero": cedula["numero"]}, firma_verificada=None,
        ),
        "cedula": validar_cedula(cedula),
        "estudio": validar_constancia_estudio(estudios),
        "laboral": validar_constancias_laborales(laborales, cfg),
        "alturas": validar_certificado_alturas(alturas, cfg),
        "medica": validar_evaluacion_medica(medica, cfg),
    }
    decision = evaluar_admision(resultados)

    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario["experiencia"], laborales, cfg)
    observaciones = [i["detalle"] for i in inconsistencias]

    fila_maestro = construir_fila_maestro(formulario, cedula, estudios, laborales, alturas, medica, resultados, decision, observaciones, cfg)

    paginas_blancas = [r["pagina"] for r in clasificar_paginas_pdf(pdf_path) if r["clasificacion"] == "blank"]
    documentos_logicos = agrupar_en_documentos(clasificacion)

    filas_auditoria = construir_filas_auditoria(clasificacion, id_aspirante)
    filas_documentos = construir_filas_documentos_candidato(documentos_logicos, id_aspirante, paginas_blancas)
    filas_adicionales = construir_filas_documentos_adicionales(clasificacion, id_aspirante)
    filas_formacion = construir_filas_formacion_experiencia(estudios, laborales, id_aspirante)

    credenciales = str(RAIZ / "service-account.json")
    spreadsheet_id = os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"]
    client = autenticar(credenciales)
    spreadsheet = abrir_spreadsheet(client, spreadsheet_id)
    hojas = asegurar_hojas(spreadsheet)

    resultado_maestro = upsert_fila(hojas["Maestro"], MAESTRO, "id_aspirante", id_aspirante, fila_maestro)
    print(f"Maestro: fila {resultado_maestro} para aspirante {id_aspirante}")

    agregar_filas(hojas["Auditoría"], AUDITORIA, filas_auditoria)
    print(f"Auditoría: {len(filas_auditoria)} filas agregadas")

    agregar_filas(hojas["Documentos por candidato"], DOCUMENTOS_POR_CANDIDATO, filas_documentos)
    print(f"Documentos por candidato: {len(filas_documentos)} filas agregadas")

    agregar_filas(hojas["Documentos adicionales"], DOCUMENTOS_ADICIONALES, filas_adicionales)
    print(f"Documentos adicionales: {len(filas_adicionales)} filas agregadas")

    agregar_filas(hojas["Formación y Experiencia Detallada"], FORMACION_EXPERIENCIA_DETALLADA, filas_formacion)
    print(f"Formación y Experiencia Detallada: {len(filas_formacion)} filas agregadas")

    print(f"\nListo: {spreadsheet.url}")


if __name__ == "__main__":
    main()
