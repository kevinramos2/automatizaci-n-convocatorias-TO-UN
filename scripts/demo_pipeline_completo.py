"""Demo de extremo a extremo: toma la extracción ya guardada de un legajo real y
corre el motor de validación de admisión + una vista previa del scoring.

No llama a la API — usa los JSON ya generados en data-ejemplo/. Sirve para ver
el pipeline completo funcionando y para la demo con Personal Administrativo.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.scoring_hoja_vida import calcular_puntaje_hoja_vida
from pipeline.validacion_admision import (
    evaluar_admision,
    validar_cedula,
    validar_certificado_alturas,
    validar_constancia_estudio,
    validar_constancias_laborales,
    validar_evaluacion_medica,
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
    extracciones = cargar("extraccion-legajo-01.json")

    print("=" * 70)
    print("DEMO PIPELINE COMPLETO — legajo-ejemplo-01.pdf")
    print("=" * 70)
    print("\nNOTA: ítem 1 (formulario de inscripción) aún no tiene prompt de\n"
          "extracción — se muestra PENDIENTE. Ítems 2-6 usan datos reales\n"
          "extraídos por la API en la sesión anterior.\n")

    resultados = {}

    # Item 2: cédula
    cedula = por_tipo(extracciones, "cedula")[0]["datos"]
    resultados["cedula"] = validar_cedula(cedula)

    # Item 3: constancia de estudio (todas las encontradas)
    estudios = [e["datos"] for e in por_tipo(extracciones, "constancia_estudio")]
    resultados["estudio"] = validar_constancia_estudio(estudios)

    # Item 4: constancias laborales — "relacionado" queda PENDIENTE hasta confirmación
    # humana (Sección 6.1: juicio semántico, nunca automático), aunque el clasificador
    # ya haya sugerido SI para ambas en la prueba anterior.
    laborales_crudas = [e["datos"] for e in por_tipo(extracciones, "constancia_laboral")]
    experiencias = [{**e, "relacionado": "PENDIENTE"} for e in laborales_crudas]
    resultados["laboral"] = validar_constancias_laborales(experiencias, cfg)

    # Item 5: certificado de alturas — hay DOS en este legajo (SENA sin vencimiento
    # explícito, y ALISO con vencimiento). Se valida el más favorable (vigente),
    # que es justamente el caso de uso real: cualquiera de los dos que sea válido basta.
    alturas_docs = [e["datos"] for e in por_tipo(extracciones, "certificado_alturas")]
    resultados_alturas = [validar_certificado_alturas(a, cfg) for a in alturas_docs]
    resultados["alturas"] = next((r for r in resultados_alturas if r.estado == "cumple"), resultados_alturas[0])

    # Item 6: evaluación médica con aptitud en alturas
    medica = por_tipo(extracciones, "evaluacion_medica")[0]["datos"]
    resultados["medica"] = validar_evaluacion_medica(medica, cfg)

    print("--- RESULTADO POR ÍTEM ---")
    for nombre, r in resultados.items():
        print(f"[{r.estado.upper():<22}] {nombre}: {r.motivo}")

    decision = evaluar_admision(resultados)
    print("\n--- DECISIÓN FINAL (sin contar ítem 1, aún pendiente) ---")
    print(json.dumps(decision, ensure_ascii=False, indent=2))

    print("\n--- VISTA PREVIA DE SCORING (Sección 6) ---")
    print("No aplica todavía — el gate de la Sección 6.3 exige que ya existan\n"
          "resultado_prueba_practica y resultado_prueba_teorica aprobados. Esto es\n"
          "solo para mostrar que la fórmula corre correctamente con datos reales,\n"
          "USANDO relacionado=SI (la sugerencia del clasificador) hipotéticamente:")
    certificados_hipoteticos = []  # este legajo no trajo certificados CAP/CAO/curso corto
    experiencias_hipoteticas = [{**e, "relacionado": "SI"} for e in laborales_crudas]
    preview = calcular_puntaje_hoja_vida(certificados_hipoteticos, experiencias_hipoteticas, cfg)
    print(json.dumps(preview, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
