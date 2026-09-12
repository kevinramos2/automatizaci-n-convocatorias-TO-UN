"""Motor de validación de admisión — Sección 5 del plan.

Una función por ítem del checklist de 5 documentos. Cada una devuelve un
ResultadoRegla con estado CUMPLE / NO_CUMPLE / REQUIERE_REVISION + motivo.
Nunca se fuerza una decisión automática: si un ítem no puede confirmarse
con los datos disponibles, queda como REQUIERE_REVISION.
"""
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from pipeline.fechas import fecha_fin_efectiva, meses_entre, parse_fecha

CUMPLE = "cumple"
NO_CUMPLE = "no_cumple"
REQUIERE_REVISION = "requiere_revision_manual"

ADMITIDO = "ADMITIDO"
NO_ADMITIDO = "NO ADMITIDO"
PENDIENTE_DE_REVISION = "PENDIENTE DE REVISIÓN"


@dataclass
class ResultadoRegla:
    estado: str
    motivo: str


def _normalizar_nombre(nombre: str) -> str:
    """Compara nombres sin importar tildes ni orden de palabras.

    La cédula colombiana imprime "APELLIDOS NOMBRES"; el formulario de
    inscripción suele diligenciarse como "NOMBRES APELLIDOS" — mismo nombre,
    orden distinto. Sin esto, una comparación de string exacta marcaría como
    inconsistencia a casi cualquier aspirante real (encontrado con datos reales).
    """
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    palabras = sin_tildes.strip().upper().split()
    return " ".join(sorted(palabras))


def validar_formulario(formulario: dict, cedula_escaneada: dict, firma_verificada: bool | None = None) -> ResultadoRegla:
    """Ítem 1: formulario completo y coincidente con la cédula. La firma es siempre chequeo manual (Sección 3)."""
    campos_obligatorios = ["nombre", "cedula", "correo", "celular", "direccion"]
    faltantes = [c for c in campos_obligatorios if not formulario.get(c)]
    if faltantes:
        return ResultadoRegla(NO_CUMPLE, f"Formulario incompleto: falta {', '.join(faltantes)}")

    if cedula_escaneada.get("numero") and formulario["cedula"] != cedula_escaneada["numero"]:
        return ResultadoRegla(REQUIERE_REVISION, "El número de cédula del formulario no coincide con la cédula escaneada")

    if cedula_escaneada.get("nombre") and _normalizar_nombre(formulario["nombre"]) != _normalizar_nombre(cedula_escaneada["nombre"]):
        return ResultadoRegla(REQUIERE_REVISION, "El nombre del formulario no coincide con la cédula escaneada")

    if firma_verificada is True:
        return ResultadoRegla(CUMPLE, "Formulario completo, datos coinciden con la cédula, firma verificada")
    if firma_verificada is False:
        return ResultadoRegla(NO_CUMPLE, "La firma del formulario no coincide con la firma de la cédula")
    return ResultadoRegla(REQUIERE_REVISION, "Formulario completo y coincidente; pendiente verificación manual de la firma")


def validar_cedula(cedula_escaneada: dict) -> ResultadoRegla:
    """Ítem 2: fotocopia de cédula legible aportada."""
    if not cedula_escaneada.get("aportada"):
        return ResultadoRegla(NO_CUMPLE, "No se aportó fotocopia de la cédula")
    legible = cedula_escaneada.get("legible")
    if legible is False:
        return ResultadoRegla(NO_CUMPLE, "La fotocopia de la cédula no es legible")
    if legible is None:
        return ResultadoRegla(REQUIERE_REVISION, "Legibilidad de la cédula pendiente de confirmación manual")
    return ResultadoRegla(CUMPLE, "Cédula aportada y legible")


def validar_constancia_estudio(constancias: list[dict]) -> ResultadoRegla:
    """Ítem 3: constancia de estudio válida que acredite mínimo primaria (numerales 3.4.4/3.4.5 del aviso)."""
    if not constancias:
        return ResultadoRegla(NO_CUMPLE, "No se aportaron constancias de estudio")

    validas = [
        c for c in constancias
        if not c.get("es_boletin") and c.get("institucion") and (c.get("titulo") or c.get("ultimo_anio_cursado"))
    ]
    if not validas:
        return ResultadoRegla(NO_CUMPLE, "Ninguna constancia de estudio válida (falta institución/título, o son boletines de calificaciones)")

    niveles_aceptados = {"primaria", "secundaria", "tecnico", "tecnologo", "profesional", "especializacion", "maestria", "doctorado"}
    acredita_minimo = any((c.get("nivel") or "").lower() in niveles_aceptados for c in validas)
    if not acredita_minimo:
        return ResultadoRegla(REQUIERE_REVISION, "Se aportaron constancias de estudio, pero no se pudo confirmar automáticamente el nivel mínimo (primaria)")
    return ResultadoRegla(CUMPLE, f"{len(validas)} constancia(s) de estudio válida(s); acredita el nivel mínimo exigido")


def validar_constancias_laborales(experiencias: list[dict], cfg: dict) -> ResultadoRegla:
    """Ítem 4: >= 12 meses de experiencia RELACIONADA (numeral 2.2 de cada aviso).

    Cada entrada de `experiencias` (constancia formal, informal autenticada, o
    declaración juramentada) debe traer: fecha_inicio, fecha_fin,
    relacionado ("SI"/"NO"/"PENDIENTE" — juicio semántico de la Sección 6.1),
    formato_valido (bool: cumple firma/autenticación/juramento según el caso).
    """
    if not experiencias:
        return ResultadoRegla(NO_CUMPLE, "No se aportaron constancias laborales ni declaraciones juramentadas")

    minimo = cfg["experiencia_minima_meses"]
    invalidas_formato = [e for e in experiencias if e.get("formato_valido") is False]
    pendientes_relacion = [e for e in experiencias if e.get("relacionado") == "PENDIENTE"]

    def meses(entradas):
        return sum(
            meses_entre(parse_fecha(e["fecha_inicio"]), fecha_fin_efectiva(e["fecha_fin"], cfg["fecha_cierre_inscripcion"]))
            for e in entradas
        )

    confirmadas = [e for e in experiencias if e.get("relacionado") == "SI" and e.get("formato_valido", True)]
    meses_confirmados = meses(confirmadas)

    if meses_confirmados >= minimo and not pendientes_relacion and not invalidas_formato:
        return ResultadoRegla(CUMPLE, f"{meses_confirmados} meses de experiencia relacionada confirmados (mínimo {minimo})")

    meses_potenciales = meses_confirmados + meses(pendientes_relacion)
    if meses_potenciales < minimo:
        return ResultadoRegla(NO_CUMPLE, f"Máximo {meses_potenciales} meses de experiencia relacionada posibles, no alcanza el mínimo de {minimo}")

    motivos = []
    if pendientes_relacion:
        motivos.append(f"{len(pendientes_relacion)} experiencia(s) pendiente(s) de confirmar si están relacionadas con el cargo")
    if invalidas_formato:
        motivos.append(f"{len(invalidas_formato)} constancia(s) con formato/autenticación por revisar")
    return ResultadoRegla(REQUIERE_REVISION, f"{meses_confirmados} meses confirmados; " + "; ".join(motivos))


def validar_certificado_alturas(certificado: dict, cfg: dict) -> ResultadoRegla:
    """Ítem 5: certificado de alturas vigente al cierre de inscripción (Resolución 4272 de 2021)."""
    if not certificado or not certificado.get("aportado"):
        return ResultadoRegla(NO_CUMPLE, "No se aportó certificado de trabajo seguro en alturas")

    fecha_vencimiento = certificado.get("fecha_vencimiento")
    if not fecha_vencimiento:
        return ResultadoRegla(REQUIERE_REVISION, "No se pudo determinar la fecha de vigencia del certificado de alturas")

    cierre = parse_fecha(cfg["fecha_cierre_inscripcion"])
    if parse_fecha(fecha_vencimiento) >= cierre:
        return ResultadoRegla(CUMPLE, f"Certificado de alturas vigente hasta {fecha_vencimiento} (cierre de inscripción: {cfg['fecha_cierre_inscripcion']})")
    return ResultadoRegla(NO_CUMPLE, f"Certificado de alturas vencido el {fecha_vencimiento}, antes del cierre de inscripción ({cfg['fecha_cierre_inscripcion']})")


def validar_evaluacion_medica(evaluacion: dict, cfg: dict) -> ResultadoRegla:
    """Ítem 6: evaluación médica con aptitud en alturas, dentro de los 30 días previos al cierre."""
    if not evaluacion or not evaluacion.get("aportado"):
        return ResultadoRegla(NO_CUMPLE, "No se aportó evaluación médica ocupacional")

    concepto_apto = evaluacion.get("concepto_aptitud_alturas")
    if concepto_apto is False:
        return ResultadoRegla(NO_CUMPLE, "La evaluación médica no otorga concepto de aptitud para trabajo en alturas")
    if concepto_apto is None:
        return ResultadoRegla(REQUIERE_REVISION, "No se pudo confirmar el concepto de aptitud en alturas en la evaluación médica")

    fecha_expedicion = evaluacion.get("fecha_expedicion")
    if not fecha_expedicion:
        return ResultadoRegla(REQUIERE_REVISION, "No se pudo leer la fecha de expedición de la evaluación médica")

    cierre = parse_fecha(cfg["fecha_cierre_inscripcion"])
    ventana_dias = cfg["ventana_evaluacion_medica_dias"]
    limite_inferior = cierre - timedelta(days=ventana_dias)
    fecha_exp = parse_fecha(fecha_expedicion)

    if limite_inferior <= fecha_exp <= cierre:
        return ResultadoRegla(CUMPLE, f"Evaluación médica expedida el {fecha_expedicion}, dentro de la ventana de {ventana_dias} días previos al cierre")
    return ResultadoRegla(
        NO_CUMPLE,
        f"Evaluación médica expedida el {fecha_expedicion}, fuera de la ventana de {ventana_dias} días previos al cierre "
        f"({limite_inferior.isoformat()} a {cfg['fecha_cierre_inscripcion']})",
    )


def evaluar_admision(resultados: dict) -> dict:
    """Combina los 6 resultados de ítem en la decisión final (Sección 5, 'Regla de decisión final').

    NO_CUMPLE en cualquier ítem gana sobre REQUIERE_REVISION: si ya es imposible
    que la persona cumpla, no tiene sentido esperar a que se resuelvan pendientes.
    """
    estados = {nombre: r.estado for nombre, r in resultados.items()}

    if NO_CUMPLE in estados.values():
        motivos = [f"{nombre}: {r.motivo}" for nombre, r in resultados.items() if r.estado == NO_CUMPLE]
        return {
            "estado_sugerido": NO_ADMITIDO,
            "causal_sugerida": "Numeral 2.5.3 - Incumplimiento de requisitos mínimos. " + " | ".join(motivos),
        }

    if REQUIERE_REVISION in estados.values():
        pendientes = [nombre for nombre, r in resultados.items() if r.estado == REQUIERE_REVISION]
        return {
            "estado_sugerido": PENDIENTE_DE_REVISION,
            "causal_sugerida": None,
            "items_pendientes": pendientes,
        }

    return {"estado_sugerido": ADMITIDO, "causal_sugerida": None}
