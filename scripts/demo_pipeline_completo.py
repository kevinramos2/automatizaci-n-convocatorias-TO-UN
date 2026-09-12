"""Demo de extremo a extremo: toma la extracción ya guardada de un expediente real y
corre el motor de validación de admisión + una vista previa del scoring.

No llama a la API — usa los JSON ya generados en data-ejemplo/. Sirve para ver
el pipeline completo funcionando y para la demo con Personal Administrativo.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.consistencia import cruzar_experiencia_formulario_vs_constancias
from pipeline.scoring_hoja_vida import calcular_puntaje_hoja_vida
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


def cargar(nombre):
    with open(RAIZ / "data-ejemplo" / nombre, encoding="utf-8") as f:
        return json.load(f)


def cargar_config():
    with open(RAIZ / "config" / "parametros.json", encoding="utf-8") as f:
        return json.load(f)


def por_tipo(extracciones, tipo):
    return [e for e in extracciones if e["tipo"] == tipo]


def main():
    cfg = cargar_config()
    extracciones = cargar("extraccion-expediente-01.json")

    print("=" * 70)
    print("DEMO PIPELINE COMPLETO — expediente-ejemplo-01.pdf")
    print("=" * 70)
    print("\nLos 6 ítems del checklist usan datos reales extraídos por la API.\n")

    resultados = {}

    # Item 1: formulario de inscripción. La firma NUNCA se verifica automáticamente
    # (Sección 3 del plan) — firma_verificada=None dejará este ítem en REQUIERE_REVISION.
    formulario = por_tipo(extracciones, "formulario_inscripcion")[0]["datos"]
    cedula_datos = por_tipo(extracciones, "cedula")[0]["datos"]
    resultados["formulario"] = validar_formulario(
        {
            "nombre": formulario["nombre"],
            "cedula": formulario["cedula"],
            "correo": formulario["correo"],
            "celular": formulario["celular"],
            "direccion": formulario["direccion"],
        },
        {"nombre": cedula_datos["nombre"], "numero": cedula_datos["numero"]},
        firma_verificada=None,
    )

    # Item 2: cédula
    resultados["cedula"] = validar_cedula(cedula_datos)

    # Item 3: constancia de estudio (todas las encontradas, excluyendo cualquier
    # documento que la propia extracción marcó como mal clasificado)
    estudios = [e["datos"] for e in por_tipo(extracciones, "constancia_estudio") if not e.get("requiere_reclasificacion")]
    resultados["estudio"] = validar_constancia_estudio(estudios)

    # Item 4: constancias laborales — "relacionado" queda PENDIENTE hasta confirmación
    # humana (Sección 6.1: juicio semántico, nunca automático), aunque el clasificador
    # ya haya sugerido SI para ambas en la prueba anterior.
    laborales_crudas = [e["datos"] for e in por_tipo(extracciones, "constancia_laboral")]
    experiencias = [{**e, "relacionado": "PENDIENTE"} for e in laborales_crudas]
    resultados["laboral"] = validar_constancias_laborales(experiencias, cfg)

    # Item 5: certificado de alturas — hay DOS documentos que se clasificaron así, pero
    # UNO fue marcado por la propia extracción como mal clasificado (en realidad es un
    # curso SENA sin relación con alturas, ver commit "Corregir bug real..."). Solo se
    # valida el que la extracción confirmó que sí es un certificado_alturas real.
    alturas_docs = [e["datos"] for e in por_tipo(extracciones, "certificado_alturas") if not e.get("requiere_reclasificacion")]
    resultados["alturas"] = validar_certificado_alturas(alturas_docs[0], cfg) if alturas_docs else validar_certificado_alturas(None, cfg)

    # Item 6: evaluación médica con aptitud en alturas
    medica = por_tipo(extracciones, "evaluacion_medica")[0]["datos"]
    resultados["medica"] = validar_evaluacion_medica(medica, cfg)

    print("--- RESULTADO POR ÍTEM ---")
    for nombre, r in resultados.items():
        print(f"[{r.estado.upper():<22}] {nombre}: {r.motivo}")

    decision = evaluar_admision(resultados)
    print("\n--- DECISIÓN FINAL (los 6 ítems del checklist) ---")
    print(json.dumps(decision, ensure_ascii=False, indent=2))

    print("\n--- CRUCE DE CONSISTENCIA: experiencia del formulario vs. constancias laborales ---")
    inconsistencias = cruzar_experiencia_formulario_vs_constancias(formulario["experiencia"], laborales_crudas, cfg)
    if not inconsistencias:
        print("Sin inconsistencias (dentro de la tolerancia configurada).")
    for inc in inconsistencias:
        print(json.dumps(inc, ensure_ascii=False, indent=2))

    print("\n--- VISTA PREVIA DE SCORING (Sección 6) ---")
    print("No aplica todavía — el gate de la Sección 6.3 exige que ya existan\n"
          "resultado_prueba_practica y resultado_prueba_teorica aprobados. Esto es\n"
          "solo para mostrar que la fórmula corre correctamente con datos reales,\n"
          "USANDO relacionado=SI (la sugerencia del clasificador) hipotéticamente:")
    certificados_hipoteticos = []  # este expediente no trajo certificados CAP/CAO/curso corto
    experiencias_hipoteticas = [{**e, "relacionado": "SI"} for e in laborales_crudas]
    preview = calcular_puntaje_hoja_vida(certificados_hipoteticos, experiencias_hipoteticas, cfg)
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
