# Plan de Automatización — Proceso de Selección Trabajador Oficial (TO-02 primero)

**Alcance de esta primera fase:** validar admisión/no admisión de aspirantes según el checklist de 5 documentos, con sugerencia de causal, prellenado del registro maestro, y revisión humana obligatoria antes de publicar.

**Importante sobre el scoring del 10% de hoja de vida:** según el numeral 4.4.1 del aviso, el análisis de hoja de vida (educación y experiencia relacionada) **solo se aplica a quienes ya superaron la prueba práctica y la prueba teórica** — eso ocurre meses después de la admisión, según el cronograma (resultados hasta feb. 2027). Por eso el puntaje **no se puede asignar al momento de admitir** a alguien. Lo que sí hacemos desde ya: capturar toda la información estructurada necesaria (cursos, horas, experiencia) y dejar lista la fórmula de cálculo, de modo que cuando llegue el momento real solo haga falta un dato externo (quién pasó las pruebas) para calcular el puntaje al instante, sin reprocesar nada.

**Piloto:** Convocatoria TO-02 (Ayudante de Albañilería). Una vez validado, se replica para TO-01 (Oficial de Jardinería).

---

## 1. Decisiones de arquitectura tomadas

| Aspecto | Decisión | Motivo |
|---|---|---|
| Origen de los PDFs | Carpeta **local** (no Drive con API) | Simplifica ingesta, no requiere permisos de Google Cloud/Drive API |
| Motor de extracción | **Claude API (visión)** | Necesario por letra manuscrita del formulario; documentos impresos también se benefician de mayor precisión que OCR plano |
| Registro maestro / "base de datos" | **Google Sheets** vía Sheets API | Gratuito, colaborativo, exportable a `.xlsx` con un clic — resuelve la doble necesidad (app + Excel) sin duplicar trabajo |
| Interfaz de revisión humana | Panel simple (web local o sidebar sobre el Sheet) | El personal ya conoce Sheets/Excel; no se requiere capacitación pesada |
| Decisión ADMITIDO/NO ADMITIDO | **Sugerida por el sistema, nunca automática/publicada sin confirmación humana** | Proceso público con posibilidad de reclamaciones legales |
| Verificación certificado alturas en MinTrabajo | **Manual** (checkbox en la revisión) | Portal externo inestable para scraping, no crítico automatizar aún |
| Comparación de firmas (formulario vs. cédula) | **Manual** | No es tarea de OCR/extracción, requiere criterio humano |
| Presupuesto | Minimizar costos; único gasto aceptado es la API de Claude por volumen de documentos | Definido por el usuario |
| Entorno de desarrollo | **Claude Code**, ejecución local | El usuario construirá el aplicativo directamente con esta herramienta |
| Captura de datos para scoring | **Se extrae y estructura desde la admisión**, pero el cálculo del puntaje se **dispara después**, solo para quienes pasen prueba práctica + teórica | El aviso (num. 4.4.1) así lo exige; evita reprocesar PDFs meses después |

---

## 2. Taxonomía real de documentos en el legajo (basada en PDF de ejemplo de 36 páginas / 18 con contenido)

Un legajo por aspirante = **un solo PDF**, con orden variable, excepto que la "Hoja de vida" (= Formulario de inscripción diligenciado a mano) siempre va primero.

### 2.1 Documentos del checklist (los 5 ítems que definen admisión)
1. **Formulario de inscripción / Hoja de vida** (manuscrito) → nombre, cédula, correo, celular, dirección, discapacidad, **tabla completa de educación formal**, **tabla completa de educación relacionada (todos los cursos, no solo el primero)**, **tabla completa de experiencia (todas las filas, no solo hasta sumar 12 meses)**. Se extrae todo desde ya porque esta misma tabla alimenta después el scoring de hoja de vida.
2. **Fotocopia de cédula** (impreso/oficial) → nombre, número, para cruce contra el formulario.
3. **Constancias de estudio** (impreso): diploma de bachillerato, acta de grado, certificados SENA / centros de formación para el trabajo → institución, título/año, fecha, **y si aplica: nombre del curso + intensidad horaria** (necesario para el scoring, no solo para validar el mínimo de primaria).
4. **Constancias laborales** (impreso): certificado laboral, certificado de la entidad empleadora (puede tener varias páginas) → entidad, cargo, jornada, fechas, funciones, firma del jefe inmediato.
5. **Certificado de trabajo seguro en alturas** (impreso) → entidad emisora, fecha de finalización, cálculo de vigencia.
6. **Evaluación médica con concepto de aptitud en alturas** (impreso) → fecha de expedición, concepto textual, cálculo de vigencia (30 días antes del cierre de inscripción).

### 2.2 Documentos adicionales (fuera del checklist, se clasifican y guardan aparte)
- Libreta militar (relevante para regla 3.4.3, no para el checklist de admisión).
- Exámenes médicos anexos: audiometría, visiometría, glucosa, triglicéridos/colesterol, certificado de preingreso ocupacional general (distinto del concepto específico de aptitud en alturas).

**Regla de clasificación:** cualquier página que no calce claramente en ninguna categoría anterior se marca como `"otro/no identificado"` y **nunca se descarta silenciosamente** — queda visible para revisión manual.

### 2.3 Páginas en blanco (reverso de las hojas escaneadas)
Al escanear ambas caras de cada hoja física, el PDF real duplica su cantidad de páginas (36 en vez de 18), donde la mitad son reversos sin contenido. Esto **no cambia la arquitectura del pipeline**, pero sí exige un paso adicional **antes** de la clasificación:

- **Detección de páginas en blanco:** se hace con una librería local (sin usar la API de Claude), midiendo si la página tiene contenido visual/texto relevante o no. Es rápido, gratuito y confiable porque no depende de interpretar contenido, solo de detectar ausencia de él.
- **Por qué importa hacerlo antes y no dejarlo pasar:** si no se filtra, cada página en blanco se envía igual al modelo de clasificación, lo cual duplica el costo y el tiempo de procesamiento por legajo sin aportar nada — con 100+ aspirantes esto se nota.
- **Manejo de casos límite:** una página "casi en blanco" (con un sello, una firma suelta, un membrete parcial) no se descarta automáticamente — se marca como "posible blanco, baja confianza" y sigue el flujo normal de clasificación, para no perder información real por error.
- Las páginas descartadas como blanco quedan registradas igual en la hoja de "Documentos por candidato" (con la marca `blank=true`), por trazabilidad — nunca se eliminan del legajo original, solo se excluyen del envío a la API.

---

## 3. Nivel de confianza esperado por tipo de documento

- **Documentos impresos/institucionales** (cédula, diplomas, certificados laborales, alturas, evaluación médica): alta confiabilidad de clasificación y extracción (~90-98%). Solo se marca para revisión lo que tenga baja confianza puntual (mala calidad de escaneo, campo ambiguo).
- **Formulario manuscrito**: se extrae automáticamente, pero **toda fila queda marcada por defecto para confirmación humana obligatoria**, sin importar el score de confianza reportado — por ser la fuente de nombre, cédula, educación y experiencia (los datos más críticos, tanto para admisión como para scoring futuro).
- **Mitigación clave:** los datos del formulario (cédula, estudios) se **cruzan automáticamente** contra la cédula escaneada y los diplomas. Si no coinciden, se marca como inconsistencia prioritaria — esto reduce el trabajo real de revisión a lo que el sistema ya señaló como sospechoso, en vez de revisar todo a ciegas.

---

## 4. Modelo de datos propuesto

### Hoja "Maestro" (una fila por aspirante)
Mantiene la estructura de las ~60 columnas del Excel actual, agregando:
- `Estado_sugerido` (ADMITIDO / NO ADMITIDO / PENDIENTE DE REVISIÓN)
- `Causal_sugerida` (texto, en los términos exactos del numeral 5 del aviso)
- `Estado_confirmado_por_humano` (vacío hasta que Personal Administrativo lo confirme)
- `Revisado_por` / `Fecha_revisión`
- `Resultado_prueba_practica` (vacío hasta la Fase 6 del proceso oficial — se llena manualmente meses después)
- `Resultado_prueba_teorica` (idem)
- `Puntaje_educacion`, `Puntaje_experiencia`, `Puntaje_hoja_de_vida_total` (vacíos hasta que ambos resultados anteriores estén registrados — el sistema los calcula automáticamente en ese momento, ver Sección 6)

### Hoja "Auditoría"
Registro de trazabilidad: qué extrajo la IA, con qué confianza, qué corrigió el humano y cuándo. Necesario ante posibles reclamaciones (numeral del aviso sobre plazos de reclamación).

### Hoja "Documentos por candidato"
Mapeo de qué páginas del PDF se clasificaron como qué tipo de documento, con enlace/referencia a la imagen de la página fuente (para que el revisor no tenga que abrir el PDF completo).

### Hoja "Documentos adicionales"
Libreta militar, exámenes anexos — clasificados pero fuera del checklist principal.

### Hoja "Formación y Experiencia Detallada" (nueva)
Una fila por **cada** curso/certificado y **cada** experiencia laboral reportada por el aspirante (no resumida, no truncada al mínimo necesario para el checklist). Columnas:
- `ID_aspirante`
- `Tipo` (Educación formal / Curso-capacitación / Experiencia laboral / Experiencia independiente)
- `Nombre_institucion_o_entidad`
- `Nombre_curso_o_cargo`
- `Fecha_inicio`, `Fecha_fin`
- `Duracion_horas` (para cursos) o `Duracion_meses` (para experiencia)
- `Relacionado_con_el_cargo` (SI/NO/PENDIENTE — ver Sección 6, se calcula con criterio específico por convocatoria)
- `Folio_fuente` (referencia a la página del PDF de donde salió, para auditoría)

Esta hoja es el insumo directo de la Sección 6 (scoring), y también sirve hoy para la validación de la Sección 5 (ítems 3 y 4 del checklist), evitando extraer los datos dos veces.

### Identificador único de aspirante
`ID Aspirante` = número de cédula (confirmado).

---

## 5. Motor de validación — checklist de admisión (el que decide quién sigue en el proceso)

Una función por ítem, cada una devuelve `cumple / no cumple / requiere revisión manual` + motivo:

1. **Formulario completo y coincidente** con la cédula (nombre, número) — verificable automáticamente en su mayoría; la firma queda como chequeo manual.
2. **Cédula legible aportada.**
3. **Constancia de estudio válida** (no es boletín de calificaciones; tiene institución + título/año; acredita mínimo primaria).
4. **Constancia(s) laboral(es):** suma de meses ≥ 12; formato correcto o autenticada ante notaría si es informal; declaración juramentada si es experiencia independiente.
5. **Certificado de alturas vigente** al cierre de inscripción (18 sept 2026), según Resolución 4272 de 2021 — cálculo automático de fecha.
6. **Evaluación médica** dentro de los 30 días calendario previos al cierre de inscripción, con concepto explícito de aptitud en alturas — cálculo automático de ventana de fechas.

**Regla de decisión final:**
- Los 5 ítems cumplen → sugerencia **ADMITIDO**.
- Cualquiera falla → sugerencia **NO ADMITIDO**, con causal(es) citada(s) en los términos del aviso (numeral 5, 2.5.1 a 2.5.8).
- Algún ítem en "requiere revisión manual" → estado **PENDIENTE DE REVISIÓN** (nunca se fuerza una decisión automática).

**Nota:** la fecha de cierre de inscripción (18 sept 2026) debe quedar como **parámetro configurable**, no fija en el código, porque de ella dependen los cálculos de vigencia.

---

## 6. Motor de scoring de hoja de vida (10% final) — preparado desde ya, calculado más adelante

Este motor se **construye ahora** (mismo esfuerzo, mismos datos ya extraídos en la Sección 4), pero solo se **ejecuta** cuando se cumplan las condiciones de la Sección 6.3.

### 6.1 Clasificación de "relacionado con el cargo" (requiere contexto por convocatoria)
Cada curso y cada experiencia laboral debe evaluarse contra el `propósito principal` y los `conocimientos básicos` específicos del cargo (sección 2.4 y 1.1 de cada aviso — distintos entre TO-01 y TO-02). Esto se resuelve con **un archivo de configuración por convocatoria** (ej. `criterios_TO-01.json`, `criterios_TO-02.json`) que contiene ese texto de referencia, y un prompt de clasificación que lo usa como contexto para marcar cada fila de la hoja "Formación y Experiencia Detallada" como relacionada o no. Como es un juicio semántico (no un dato objetivo), **el resultado queda visible para confirmación humana**, igual que el resto de campos sensibles.

### 6.2 Fórmula de puntaje (tomada literalmente del numeral 4.4.2 del aviso)

**Educación relacionada (máx. 50 puntos):** se suman las horas de hasta 5 certificados marcados como relacionados, y se ubica el total en la tabla de bandas:

| Horas acumuladas | Puntos |
|---|---|
| CAP / CAO / cursos ≥ 200 horas | 25 |
| 100 a 199 horas | 12 |
| 50 a 99 horas | 8 |
| 8 a 49 horas | 1 |

**Experiencia relacionada (máx. 50 puntos):** 1 punto por cada mes completo de experiencia relacionada **adicional** al mínimo de 12 meses ya exigido para admisión, con tope de 50 puntos.

**Puntaje total de hoja de vida** = Educación + Experiencia (máx. 100, que representa el 10% final de la calificación global del proceso).

### 6.3 Condición de disparo (gate)
El cálculo **no corre automáticamente al admitir a alguien**. Se dispara únicamente cuando, para un aspirante dado, existan registrados:
- `Resultado_prueba_practica` = aprobado (≥60/100, según num. 4.2.4 del aviso), **y**
- `Resultado_prueba_teorica` = aprobado.

Estos dos datos **no salen de ningún PDF** — provienen de las pruebas físicas/escritas que administra la universidad meses después (cronograma: nov. 2026 – feb. 2027). Se necesita un mecanismo simple de carga manual de esos resultados (ej. una columna editable en el Sheet, o una pequeña importación desde el archivo de resultados de pruebas que genere la universidad) — este mecanismo se define con más detalle cuando se llegue a esa fase, pero el motor de cálculo ya queda listo desde ahora.

---

## 7. Pipeline técnico (orden de ejecución)

1. **Ingesta:** el script lee los PDFs nuevos de la carpeta local (procesamiento por lote, manual al inicio — botón/comando "procesar").
2. **División en páginas:** cada PDF se convierte a imágenes por página.
3. **Filtrado de páginas en blanco:** detección local (sin API) de páginas de reverso sin contenido; se excluyen del envío a clasificación pero quedan registradas como `blank=true` en el legajo.
4. **Clasificación de páginas:** prompt a Claude que etiqueta cada página/bloque restante (con contenido) según la taxonomía de la sección 2 (checklist + adicionales + no identificado).
5. **Agrupación:** páginas consecutivas del mismo tipo se agrupan en "documentos lógicos" dentro del legajo (resuelve el problema del orden variable).
6. **Extracción estructurada completa:** un prompt específico por tipo de documento devuelve JSON con **todos** los campos requeridos (checklist + scoring futuro), con score de confianza por campo. Puebla tanto "Maestro" como "Formación y Experiencia Detallada".
7. **Cruce de consistencia:** cédula/nombre del formulario vs. cédula escaneada vs. diplomas — genera banderas de inconsistencia.
8. **Validación de admisión (motor de reglas, Sección 5):** genera estado sugerido + causal.
9. **Clasificación de relacionado con el cargo (Sección 6.1):** se ejecuta ya (no depende de las pruebas), queda registrada para uso futuro.
10. **Escritura en Google Sheets:** vía Sheets API, puebla/actualiza la fila del aspirante en "Maestro", "Auditoría", "Documentos por candidato" y "Formación y Experiencia Detallada".
11. **Revisión humana:** Personal Administrativo confirma o corrige en el Sheet (o panel simple), incluyendo los dos chequeos manuales (MinTrabajo, firma) y la clasificación de "relacionado con el cargo".
12. **Cierre de admisión:** solo tras confirmación humana, el estado ADMITIDO/NO ADMITIDO se vuelve oficial para publicar.
13. **Exportación:** botón/comando para descargar `.xlsx` con las columnas del formato actual, para quien prefiera trabajar así.
14. **(Meses después) Disparo de scoring:** al registrarse los resultados de prueba práctica y teórica, se ejecuta automáticamente la fórmula de la Sección 6.2 sobre los datos ya almacenados — sin reprocesar PDFs.

---

## 8. Fases de construcción (orden sugerido de trabajo con Claude Code)

### Fase 0 — Preparación
- [ ] Confirmar protocolo de tratamiento de datos personales (Ley 1581/2012) con la universidad, o redactar uno mínimo (consentimiento, acceso restringido, retención).
- [ ] Definir fecha de cierre de inscripción como parámetro de configuración.
- [ ] Reunir 5-10 legajos reales o representativos (ya se cuenta con 1 completo de ejemplo).
- [ ] Redactar los archivos de criterios por convocatoria (`criterios_TO-01.json`, `criterios_TO-02.json`) con el texto de propósito principal y conocimientos básicos de cada aviso.

### Fase 1 — Piloto de clasificación y extracción
- [ ] Función local de detección de páginas en blanco, probada contra el PDF de ejemplo de 36 páginas (18 con contenido + 18 reversos en blanco).
- [ ] Prompt de clasificación de páginas, probado contra las páginas con contenido ya filtradas.
- [ ] Prompt de extracción por tipo de documento (empezar por los impresos, luego el formulario manuscrito), capturando **todas** las filas de educación y experiencia, no solo lo mínimo para el checklist.
- [ ] Medir precisión real y ajustar prompts.

### Fase 2 — Motor de validación de admisión
- [ ] Implementar las 6 reglas de la Sección 5 como funciones independientes y testeables.
- [ ] Implementar el cálculo de vigencias (alturas, evaluación médica) parametrizado por fecha de cierre.
- [ ] Implementar la lógica de causales en los términos exactos del aviso.

### Fase 3 — Motor de scoring (construido ahora, sin disparar aún)
- [ ] Prompt de clasificación "relacionado con el cargo" usando el archivo de criterios por convocatoria.
- [ ] Implementar la fórmula de puntaje de la Sección 6.2 (educación + experiencia) como función pura, testeable con datos de ejemplo.
- [ ] Implementar el mecanismo de "gate" (Sección 6.3): el cálculo solo corre si existen ambos resultados de prueba registrados.

### Fase 4 — Integración con Google Sheets
- [ ] Crear la hoja de cálculo con las hojas "Maestro", "Auditoría", "Documentos por candidato", "Documentos adicionales", "Formación y Experiencia Detallada".
- [ ] Conectar vía Sheets API (cuenta de servicio compartida solo con esa hoja, no con toda la carpeta).
- [ ] Escritura automática de resultados por candidato.

### Fase 5 — Interfaz de revisión
- [ ] Formato condicional en el Sheet (verde/amarillo/rojo).
- [ ] Panel o sidebar que muestre el campo extraído junto a la imagen de la página fuente.
- [ ] Registro de auditoría (quién revisó, cuándo, qué corrigió).
- [ ] Vista de confirmación para la clasificación "relacionado con el cargo" de cada curso/experiencia.

### Fase 6 — Exportación
- [ ] Función de exportación a `.xlsx` con las columnas del formato actual.

### Fase 7 — Piloto controlado con datos reales de TO-02
- [ ] Procesar el primer lote real de inscritos.
- [ ] Correr en paralelo con el proceso manual actual antes de depender 100% del aplicativo.
- [ ] Ajustar según hallazgos.

### Fase 8 — Réplica a TO-01
- [ ] Reutilizar el mismo motor, ajustando solo el archivo de criterios específico del cargo.

### Fase 9 (meses después, cuando existan resultados de pruebas)
- [ ] Definir e implementar el mecanismo de carga de `Resultado_prueba_practica` / `Resultado_prueba_teorica`.
- [ ] Disparar el cálculo de puntaje para los aspirantes que correspondan.
- [ ] Validar los resultados con Personal Administrativo antes de publicar el resultado final del proceso.

---

## 9. Sobre el uso de Claude Code

Claude Code puede ejecutar código Python/Node localmente, leer y escribir archivos en tu máquina, y llamar a la API de Claude para clasificación/extracción — todo el pipeline descrito arriba se puede construir y correr desde ahí.

**Recomendación:** sí, crea un repositorio (aunque sea local, con `git init`, sin necesidad de subirlo a GitHub todavía). No es estrictamente obligatorio para que Claude Code funcione, pero:
- Permite versionar cambios en los prompts de clasificación/extracción (que se van a ajustar varias veces durante el piloto).
- Facilita deshacer cambios si un ajuste rompe algo.
- Da una estructura clara de carpetas (ej. `/prompts`, `/pipeline`, `/tests`, `/data-ejemplo`, `/criterios`) que Claude Code puede navegar mejor que un directorio suelto.

No necesitas subirlo a GitHub ni hacerlo público — puede quedar 100% local mientras development. Cuando quieras compartirlo con Personal Administrativo o respaldarlo, ahí sí conviene subirlo a un repo privado.

---

## 10. Costos operativos estimados (API de Claude, tarifas vigentes sept. 2026)

| Modelo | Input | Output | Uso en el pipeline |
|---|---|---|---|
| Haiku 4.5 | $1.00 / MTok | $5.00 / MTok | Clasificación de páginas |
| Sonnet 5 | $2.00 / MTok | $10.00 / MTok | Extracción de datos y formulario manuscrito |

- **Estimado por legajo (~18 páginas con contenido):** entre $0.15 y $0.25 USD.
- **Estimado por convocatoria completa (100-150 aspirantes):** entre $15 y $40 USD.
- **Con Batch API (50% descuento) + prompt caching (hasta 90% en input repetido):** el costo real puede bajar a $10-20 USD por convocatoria.
- Esta es una estimación basada en supuestos razonables; la Fase 1 (piloto) mide el costo real antes de comprometerse con una cifra definitiva.
- El scoring (Sección 6) no agrega costo relevante nuevo: la clasificación "relacionado con el cargo" ocurre en la misma pasada de extracción, y el cálculo del puntaje (Sección 6.2) es una fórmula determinística, sin costo de API.

---

## 11. Pendientes que quedan abiertos para cuando retomemos

- Validar con Personal Administrativo si existe protocolo formal de datos personales.
- Definir si el procesamiento será manual (tú corres el script por lote) o si en algún punto se automatiza con un watcher de carpeta.
- Ajustar el nivel de detalle del panel de revisión según el uso real que le dé el personal en la Fase 7.
- Definir el mecanismo concreto de carga de resultados de pruebas (Fase 9) cuando se acerque esa etapa del proceso.
