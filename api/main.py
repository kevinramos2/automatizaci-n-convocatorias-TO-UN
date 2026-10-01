"""API REST que envuelve pipeline/*.py para el frontend de React — Fase 1 de la
migración de Streamlit a React (ver plan de migración). No reimplementa ninguna
regla de negocio: cada endpoint llama a las mismas funciones que ya usa
app_revision.py. Deliberadamente NO importa app_revision.py (ese módulo llama a
st.set_page_config a nivel de módulo, así que solo puede ejecutarse con
`streamlit run`) — las pocas funciones auxiliares de "forma de los datos" que
vivían ahí (normalizar documentos, resolver rotación por página, aplicar un
override manual, clasificar qué estudio es "académico") se copian aquí tal
cual: no son lógica de negocio, son el mismo tipo de pegamento que ya existía.

Uso: uvicorn api.main:app --reload --port 8000
"""
import base64
import json
import os
from dataclasses import asdict
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from api.schemas import RevisionInput
from pipeline.cache_expedientes import (
    cargar_resultado,
    existe_en_cache,
    guardar_pdf,
    guardar_resultado,
    hash_archivo,
    listar_cache,
    ruta_pdf,
)
from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.esquema_sheets import AUDITORIA, MAESTRO
from pipeline.mapeo_maestro import construir_fila_maestro
from pipeline.pdf_utils import pagina_a_imagen_base64
from pipeline.procesar_expediente import procesar_expediente
from pipeline.sheets_client import abrir_spreadsheet, agregar_filas, asegurar_hojas, autenticar, upsert_fila
from pipeline.validacion_admision import (
    CUMPLE,
    NO_CUMPLE,
    ResultadoRegla,
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
    validar_formulario,
)

RAIZ = Path(__file__).parent.parent
load_dotenv()

# Modo demo (ver demo/README.md): expedientes 100% inventados (demo/cache_demo,
# generados por scripts/generar_demo.py), subir expediente nuevo deshabilitado, y
# "guardar revisión" escribe en demo/hoja_simulada.py en vez de Google Sheets real
# — para poder mostrar el proyecto en vivo sin ninguna credencial ni dato real.
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"
if DEMO_MODE:
    from demo.hoja_simulada import agregar_fila as _agregar_fila_simulada
    from demo.hoja_simulada import leer_filas as _leer_hoja_simulada

# ALLOWED_ORIGINS (opcional): orígenes adicionales separados por coma, p. ej. el
# dominio de Vercel del demo público. Los de desarrollo local siempre se permiten.
_ORIGENES = ["http://localhost:5173", "http://127.0.0.1:5173"]
_ORIGENES += [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(title="API — Panel de revisión TO 2026")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGENES,
    allow_methods=["*"],
    allow_headers=["*"],
)

_CONVOCATORIAS = {
    "TO-02": {"etiqueta": "TO-02 · Ayudante de Albañilería", "criterios": "criterios/criterios_TO-02.json"},
    "TO-01": {"etiqueta": "TO-01 · Oficial de Jardinería", "criterios": "criterios/criterios_TO-01.json"},
}

# Igual que app_revision.py:_NIVELES_ESCOLARES — solo colegio (primaria/secundaria) cuenta
# como "información académica"; técnico/tecnólogo/etc. y cursos van a "relacionada".
_NIVELES_ESCOLARES = {"primaria", "secundaria"}

# Confirmación humana de que el aspirante entregó el formulario y la fotocopia de la
# cédula (lista de chequeo). Reemplaza a la antigua comparación de firmas, que en la
# práctica Personal Administrativo no valida.
# Versión del contrato entre la API y el panel. Se sube cada vez que cambia lo que el
# panel envía o espera; el panel avisa si la API que está corriendo es más vieja
# (el servidor no se recarga solo en esta carpeta, y una API vieja ignora en
# silencio los campos nuevos).
API_VERSION = 3

_OPCIONES_APORTO = {"Pendiente": None, "Sí aportó": True, "No aportó": False}
# Revisiones guardadas antes de separar formulario y cédula ("firma_verificada" o "entrega_verificada").
_ENTREGA_ANTIGUA = {"Sí coincide": "Sí aportó", "Sí, entregó ambos": "Sí aportó", "No coincide": "No aportó", "No, falta alguno": "No aportó", "Pendiente": "Pendiente"}


def _cargar_cfg() -> dict:
    return json.load(open(RAIZ / "config" / "parametros.json", encoding="utf-8"))


def _rotacion_de_pagina(resultado: dict, pagina: int) -> int:
    overrides = resultado.get("rotaciones_paginas") or {}
    return overrides.get(str(pagina), resultado.get("rotacion", 0))


def _normalizar_documentos(documentos_extraidos: list[dict]) -> list[dict]:
    return [
        {"tipo": d["tipo_final"], "paginas": d["paginas"], "datos": d["datos"]}
        for d in documentos_extraidos if d["tipo_final"] and d["datos"]
    ]


def _aplicar_override_manual(automatico: ResultadoRegla, eleccion: str) -> ResultadoRegla:
    if eleccion == "Sí, válido":
        return ResultadoRegla(CUMPLE, "Confirmado manualmente por el revisor, viendo el documento.")
    if eleccion == "No es válido":
        return ResultadoRegla(NO_CUMPLE, "Marcado manualmente como no válido por el revisor, viendo el documento.")
    return automatico


def _cargar_o_404(hash_: str) -> dict:
    resultado = cargar_resultado(hash_)
    if resultado is None:
        raise HTTPException(404, f"No existe ningún expediente con hash {hash_}")
    return resultado


def _recalcular(resultado: dict, cfg: dict, datos: RevisionInput) -> dict:
    """Recalcula el checklist y la decisión con las respuestas del revisor — la

    misma operación que hace el bloque final de app_revision.py en cada rerun
    (Streamlit lo recalculaba solo, en memoria, en cada clic; acá lo pide
    explícitamente /revision/preview para que React muestre lo mismo en vivo sin
    reimplementar ninguna regla de negocio en TypeScript). También la usa
    /revision al guardar, para no repetir la lógica dos veces.
    """
    formulario = resultado["formulario"]
    cedula = resultado["cedula"]
    estudios = resultado["estudios"]
    laborales = resultado["laborales"]
    alturas = resultado["alturas"]
    medica = resultado["medica"]

    indices_academicos = [
        i for i, e in enumerate(estudios) if (e.get("nivel") or "").lower() in _NIVELES_ESCOLARES
    ]

    for campo in ("entrega_formulario", "entrega_cedula"):
        if getattr(datos, campo) not in _OPCIONES_APORTO:
            raise HTTPException(400, f"{campo} inválida: {getattr(datos, campo)}")
    aporto = [_OPCIONES_APORTO[datos.entrega_formulario], _OPCIONES_APORTO[datos.entrega_cedula]]
    # Basta con que uno no se haya aportado para que el ítem no cumpla; cumple solo
    # si se confirmaron los dos; con alguno pendiente queda por revisar.
    entrega_valor = False if False in aporto else (True if aporto == [True, True] else None)

    decisiones_relacionado_laboral = [
        datos.decisiones_relacionado_laboral.get(str(i), "PENDIENTE") for i in range(len(laborales))
    ]
    laborales_confirmadas = [{**e, "relacionado": d} for e, d in zip(laborales, decisiones_relacionado_laboral)]

    # Cada documento académico marcado "No es válido" queda excluido por completo — no
    # cuenta para el nivel mínimo ni se guarda como confirmado.
    estudios_confirmados = [
        {**e, "relacionado": datos.decisiones_relacionado_estudio[str(i)]}
        if str(i) in datos.decisiones_relacionado_estudio else dict(e)
        for i, e in enumerate(estudios)
        if datos.overrides_academicos.get(str(i)) != "No es válido"
    ]

    resultados_actualizados = {
        "formulario": validar_formulario(
            {k: formulario.get(k) for k in ("nombre", "cedula", "correo", "celular", "direccion")},
            {"nombre": cedula.get("nombre"), "numero": cedula.get("numero")},
            entrega_confirmada=entrega_valor,
        ),
        "cedula": validar_cedula(cedula),
        "estudio": validar_constancia_estudio(estudios_confirmados),
        "laboral": validar_constancias_laborales(laborales_confirmadas, cfg),
        "alturas": _aplicar_override_manual(validar_certificado_alturas(alturas, cfg), datos.alturas_override),
        "medica": _aplicar_override_manual(validar_evaluacion_medica(medica, cfg), datos.medica_override),
    }
    decision_actualizada = evaluar_admision(resultados_actualizados)

    return {
        "indices_academicos": indices_academicos,
        "decisiones_relacionado_laboral": decisiones_relacionado_laboral,
        "laborales_confirmadas": laborales_confirmadas,
        "estudios_confirmados": estudios_confirmados,
        "resultados_actualizados": resultados_actualizados,
        "decision_actualizada": decision_actualizada,
    }


def _resultado_serializable(hash_: str) -> dict:
    """Deja un expediente cacheado listo para responder como JSON: ResultadoRegla

    -> dict, documentos normalizados por tipo (para buscar páginas), e índices de
    estudios ya clasificados en académico/relacionado (misma regla que usa el
    panel de Streamlit) para que React no tenga que reimplementar esa clasificación.
    """
    resultado = _cargar_o_404(hash_)
    resultado["resultados_validacion"] = {k: asdict(v) for k, v in resultado["resultados_validacion"].items()}
    resultado["documentos"] = _normalizar_documentos(resultado.pop("documentos_extraidos", []))

    # Revisiones guardadas antes del cambio usaban "firma_verificada" (Sí coincide/...).
    revision = resultado.get("revision_humana")
    if revision and "entrega_formulario" not in revision:
        antigua = revision.get("entrega_verificada") or revision.get("firma_verificada")
        if antigua:
            valor = _ENTREGA_ANTIGUA.get(antigua, "Pendiente")
            revision["entrega_formulario"] = valor
            # "No, falta alguno" no dice cuál falta: la cédula queda por confirmar.
            revision["entrega_cedula"] = "Pendiente" if valor == "No aportó" else valor

    # El ítem 1 se guardó al procesar con el texto de "verificar firma"; se vuelve a
    # calcular (función pura, sin costo) para mostrar el texto actual.
    f, c = resultado["formulario"], resultado["cedula"]
    resultado["resultados_validacion"]["formulario"] = asdict(validar_formulario(
        {k: f.get(k) for k in ("nombre", "cedula", "correo", "celular", "direccion")},
        {"nombre": c.get("nombre"), "numero": c.get("numero")},
    ))

    estudios = resultado.get("estudios", [])
    resultado["indices_academicos"] = [
        i for i, e in enumerate(estudios) if (e.get("nivel") or "").lower() in _NIVELES_ESCOLARES
    ]

    resultado["_hash"] = hash_
    return resultado


@app.get("/api/convocatorias")
def listar_convocatorias():
    return {clave: v["etiqueta"] for clave, v in _CONVOCATORIAS.items()}


@app.get("/api/config")
def config_publica():
    """Datos no sensibles que el frontend necesita — igual que el botón fijo

    "Abrir Google Sheet" del sidebar en app_revision.py: se construye la URL
    directo del ID de la hoja, sin autenticar.
    """
    spreadsheet_id = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID")
    return {
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit" if spreadsheet_id else None,
        "api_version": API_VERSION,
        "demo_mode": DEMO_MODE,
    }


@app.get("/api/demo/hoja")
def hoja_simulada():
    """Solo tiene sentido en modo demo: las filas que se han ido "guardando" en esta
    sesión del demo, como reemplazo de Google Sheets. Ver demo/hoja_simulada.py."""
    if not DEMO_MODE:
        raise HTTPException(404, "No disponible fuera del modo demo.")
    return {"filas": _leer_hoja_simulada()}


@app.get("/api/expedientes")
def listar_expedientes():
    return listar_cache()


@app.get("/api/expedientes/{hash_}")
def obtener_expediente(hash_: str):
    return _resultado_serializable(hash_)


@app.get("/api/expedientes/{hash_}/paginas/{numero}")
def imagen_pagina(hash_: str, numero: int, dpi: int = 150, extra: int = 0):
    """`extra` (múltiplo de 90) es un giro manual encima de la rotación automática
    guardada — lo usa el botón "Rotar" del visor; no modifica el PDF ni la caché.
    """
    if extra % 90 != 0:
        raise HTTPException(400, "extra debe ser múltiplo de 90")
    resultado = _cargar_o_404(hash_)
    pdf_path = str(ruta_pdf(hash_))
    rotacion = (_rotacion_de_pagina(resultado, numero) + extra) % 360
    b64 = pagina_a_imagen_base64(pdf_path, numero, dpi=dpi, rotacion=rotacion)
    return Response(content=base64.b64decode(b64), media_type="image/png")


@app.post("/api/expedientes/procesar")
async def procesar(convocatoria: str = Form(...), archivo: UploadFile = File(...)):
    if DEMO_MODE:
        raise HTTPException(403, "Deshabilitado en el demo: los expedientes son fijos y los datos son inventados.")
    if convocatoria not in _CONVOCATORIAS:
        raise HTTPException(400, f"Convocatoria inválida: {convocatoria}")

    contenido = await archivo.read()
    hash_ = hash_archivo(contenido)

    if existe_en_cache(hash_):
        return {"hash": hash_, "ya_procesado": True, "costo_usd": 0.0}

    ruta = guardar_pdf(hash_, contenido)
    cfg = _cargar_cfg()
    criterios = json.load(open(RAIZ / _CONVOCATORIAS[convocatoria]["criterios"], encoding="utf-8"))
    client = anthropic.Anthropic()
    resultado = procesar_expediente(str(ruta), criterios, cfg, client=client)
    resultado["convocatoria"] = convocatoria
    guardar_resultado(hash_, resultado)

    uso = resultado["uso_total"]
    costo = uso["input_tokens"] / 1e6 * 2.00 + uso["output_tokens"] / 1e6 * 10.00
    return {"hash": hash_, "ya_procesado": False, "costo_usd": round(costo, 4), "uso": uso}


@app.post("/api/expedientes/{hash_}/revision/preview")
def previsualizar_revision(hash_: str, datos: RevisionInput):
    """Recalcula el checklist y la decisión en vivo, sin escribir nada (ni en

    Sheets ni en la caché) — lo que usa React para mostrar "Decisión con tu
    revisión" actualizándose con cada clic, igual que hacía Streamlit al
    recalcular todo en cada rerun, pero sin reimplementar reglas de negocio en
    TypeScript.
    """
    resultado = _cargar_o_404(hash_)
    cfg = _cargar_cfg()
    calculo = _recalcular(resultado, cfg, datos)
    return {
        "resultados_actualizados": {k: asdict(v) for k, v in calculo["resultados_actualizados"].items()},
        "decision_actualizada": calculo["decision_actualizada"],
    }


@app.post("/api/expedientes/{hash_}/revision")
def guardar_revision(hash_: str, datos: RevisionInput):
    """Misma orquestación que el botón "Guardar revisión en Google Sheets" de

    app_revision.py (líneas ~679-760): arma la fila con construir_fila_maestro,
    escribe con upsert_fila/agregar_filas, y persiste "revision_humana" en la
    caché local para que los controles se restauren al volver a este aspirante.
    No hay una versión "sugerida" aparte: esto solo se llama cuando un humano ya
    confirmó la revisión completa.
    """
    if not datos.revisado_por.strip():
        raise HTTPException(400, "Falta el nombre de quien revisa.")

    resultado = _cargar_o_404(hash_)
    cfg = _cargar_cfg()
    formulario = resultado["formulario"]
    cedula = resultado["cedula"]
    estudios = resultado["estudios"]
    laborales = resultado["laborales"]
    alturas = resultado["alturas"]
    medica = resultado["medica"]

    calculo = _recalcular(resultado, cfg, datos)
    indices_academicos = calculo["indices_academicos"]
    decisiones_relacionado_laboral = calculo["decisiones_relacionado_laboral"]
    laborales_confirmadas = calculo["laborales_confirmadas"]
    estudios_confirmados = calculo["estudios_confirmados"]
    resultados_actualizados = calculo["resultados_actualizados"]
    decision_actualizada = calculo["decision_actualizada"]
    estado_final = decision_actualizada["estado_sugerido"]

    if estado_final not in ("ADMITIDO", "NO ADMITIDO"):
        raise HTTPException(
            400,
            "Todavía hay ítems pendientes de confirmar (formulario, cédula, relacionado, alturas, médica) — "
            "no se puede guardar una decisión final.",
        )

    try:
        hojas = None
        if not DEMO_MODE:
            client = autenticar(str(RAIZ / "service-account.json"))
            spreadsheet = abrir_spreadsheet(client, os.environ["GOOGLE_SHEETS_SPREADSHEET_ID"])
            hojas = asegurar_hojas(spreadsheet)

        inconsistencias = cruzar_experiencia_formulario_vs_constancias(
            formulario.get("experiencia", []), laborales_confirmadas, cfg,
        )
        fila_maestro = construir_fila_maestro(
            formulario, cedula, estudios_confirmados, laborales_confirmadas, alturas, medica,
            resultados_actualizados, decision_actualizada, [i["detalle"] for i in inconsistencias], cfg,
        )
        fila_maestro["admitido_si_no"] = "SI" if estado_final == "ADMITIDO" else "NO"
        fila_maestro["causal_no_admision"] = decision_actualizada.get("causal_sugerida") or ""
        fila_maestro["estado_confirmado_por_humano"] = estado_final
        fila_maestro["revisado_por"] = datos.revisado_por
        fila_maestro["fecha_revision"] = date.today().isoformat()

        id_aspirante = cedula.get("numero", "")
        if DEMO_MODE:
            # Sin Google Sheets real: la fila queda en demo/hoja_simulada.json, que
            # el panel lee para mostrar "lo que se escribió" al guardar.
            _agregar_fila_simulada(fila_maestro)
        else:
            upsert_fila(hojas["Maestro"], MAESTRO, "id_aspirante", id_aspirante, fila_maestro)

        filas_auditoria = [
            {
                "id_aspirante": id_aspirante, "campo": campo,
                "valor_extraido_ia": "pendiente", "valor_corregido_humano": valor,
                "corregido_por": datos.revisado_por, "fecha_correccion": date.today().isoformat(),
            }
            for campo, valor in (("entrega_formulario", datos.entrega_formulario), ("entrega_cedula", datos.entrega_cedula))
        ]
        if alturas and alturas.get("aportado"):
            filas_auditoria.append({
                "id_aspirante": id_aspirante, "campo": "validez_certificado_alturas",
                "valor_extraido_ia": resultado["resultados_validacion"]["alturas"].estado,
                "valor_corregido_humano": datos.alturas_override,
                "corregido_por": datos.revisado_por, "fecha_correccion": date.today().isoformat(),
            })
        if medica and medica.get("aportado"):
            filas_auditoria.append({
                "id_aspirante": id_aspirante, "campo": "validez_evaluacion_medica",
                "valor_extraido_ia": resultado["resultados_validacion"]["medica"].estado,
                "valor_corregido_humano": datos.medica_override,
                "corregido_por": datos.revisado_por, "fecha_correccion": date.today().isoformat(),
            })
        for i in indices_academicos:
            e = estudios[i]
            etiqueta_doc = e.get("titulo") or (e.get("nivel") or "—").capitalize()
            filas_auditoria.append({
                "id_aspirante": id_aspirante, "campo": f"validez_diploma_estudio_{i}_{etiqueta_doc}",
                "valor_extraido_ia": "pendiente",
                "valor_corregido_humano": datos.overrides_academicos.get(str(i), "Según el sistema"),
                "corregido_por": datos.revisado_por, "fecha_correccion": date.today().isoformat(),
            })
        for i, (exp, d) in enumerate(zip(laborales, decisiones_relacionado_laboral)):
            filas_auditoria.append({
                "id_aspirante": id_aspirante, "campo": f"relacionado_laboral_{i}_{exp.get('entidad', '')}",
                "valor_extraido_ia": exp.get("relacionado_sugerido", ""), "valor_corregido_humano": d,
                "corregido_por": datos.revisado_por, "fecha_correccion": date.today().isoformat(),
            })
        if not DEMO_MODE:
            agregar_filas(hojas["Auditoría"], AUDITORIA, filas_auditoria)

        # También en la caché local — "revision_humana" guarda cada respuesta
        # individual (no solo el resultado final) para que al volver a este
        # aspirante los controles se restauren tal como quedaron.
        resultado_cache = cargar_resultado(hash_)
        resultado_cache["estado_confirmado_por_humano"] = estado_final
        resultado_cache["revisado_por"] = datos.revisado_por
        resultado_cache["fecha_revision"] = date.today().isoformat()
        resultado_cache["revision_humana"] = {
            "entrega_formulario": datos.entrega_formulario,
            "entrega_cedula": datos.entrega_cedula,
            "overrides_academicos": datos.overrides_academicos,
            "decisiones_relacionado_estudio": datos.decisiones_relacionado_estudio,
            "decisiones_relacionado_laboral": {str(i): d for i, d in enumerate(decisiones_relacionado_laboral)},
            "alturas_override": datos.alturas_override,
            "medica_override": datos.medica_override,
            "revisado_por": datos.revisado_por,
        }
        guardar_resultado(hash_, resultado_cache)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"No se pudo guardar: {exc}")

    return {"estado_final": estado_final, "causal": decision_actualizada.get("causal_sugerida")}
