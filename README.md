# Panel de revisión de aspirantes — Trabajador Oficial

Herramienta interna para apoyar el proceso de selección de **Trabajador Oficial** de la
Universidad Nacional de Colombia (convocatorias TO-01 Oficial de Jardinería y TO-02 Ayudante
de Albañilería). Lee cada expediente en PDF, extrae y valida la información contra la lista de
chequeo del aviso oficial, y deja la decisión final — siempre tomada por una persona — registrada
en Google Sheets.

> **Sobre los datos.** El equipo de selección me pidió ayuda para registrar estos documentos de
> forma más ágil; les propuse automatizar la lectura y validación, y construí esto. El proceso
> maneja cédulas, certificados laborales y evaluaciones médicas de personas reales, así que
> **ningún dato real de aspirantes vive en este repositorio** (ver [Privacidad y datos](#privacidad-y-datos)).
> Las capturas de pantalla en [`/capturas`](./capturas) están censuradas o tomadas con datos de
> prueba inventados.

## Qué hace

- **Lee el PDF del expediente** con la API de Claude: separa y clasifica cada documento
  (formulario, cédula, diplomas, certificados, constancias laborales, certificado de alturas,
  evaluación médica), corrige automáticamente páginas escaneadas al revés, y extrae los datos de
  cada una.
- **Valida contra el aviso oficial**: compara cada documento con los requisitos mínimos de
  admisión (Sección 5 del aviso) y marca cada ítem como *cumple*, *no cumple* o *requiere revisión
  manual*.
- **Guía la revisión humana paso a paso**: un panel con 7 pasos (entrega de formulario/cédula,
  información académica, educación relacionada, experiencia laboral, alturas, evaluación médica
  y resumen) muestra el documento correspondiente junto a cada pregunta, con atajos de teclado
  para revisar rápido.
- **Nunca decide ni publica solo**: el sistema sugiere; cada confirmación (firma y entrega,
  formación relacionada, vigencia del certificado de alturas, aptitud médica) la da la persona
  que revisa. Es el principio de diseño de todo el proyecto — "humano en el ciclo" — porque la
  decisión final afecta el proceso de selección de alguien.
- **Escribe automáticamente en Google Sheets**: en cuanto quien revisa guarda su decisión sobre
  un aspirante, el sistema arma la fila (datos del expediente + la decisión + quién y cuándo
  revisó) y la escribe en la hoja de cálculo compartida con el equipo de selección — sin que
  nadie tenga que copiar o digitar nada a mano. Queda también un registro de auditoría por
  campo (qué se confirmó, con qué respuesta) en una segunda pestaña.
- **Reporta el costo de cada expediente procesado** (~$0.15–0.25 USD en la API de Claude), para
  que el gasto de usar IA quede visible, no escondido.

## Cómo está construido

```
PDF del expediente
      │
      ▼
pipeline/  (Python)                    api/ (FastAPI)              frontend/ (React + Vite)
 ├─ clasificador_paginas.py   ──┐        ├─ expone el pipeline        ├─ lista de aspirantes
 ├─ rotacion_auto.py            │        │  como endpoints REST       ├─ visor de documentos
 ├─ extractor_documentos.py     ├──────▶ ├─ arma y escribe la fila    ├─ revisión paso a paso
 ├─ agrupador_documentos.py     │        │  en Google Sheets al       └─ resumen y guardado
 ├─ validacion_admision.py      │        │  guardar una revisión
 ├─ consistencia.py             │        └─ cachea el resultado
 └─ sheets_client.py          ──┘           localmente (PDF + JSON)
```

- **`pipeline/`** — toda la lógica de negocio: lectura de PDF, llamadas a la API de Claude
  (extracción de datos, clasificación de páginas, detección de rotación, sugerencia de si una
  formación o experiencia está "relacionada con el cargo"), las reglas de validación de
  admisión, y el cliente de Google Sheets (con upsert seguro: nunca sobrescribe la fila de otro
  aspirante). Es la parte con pruebas automatizadas (102 pruebas).
- **`api/`** — una API en FastAPI, delgada a propósito: expone el pipeline por HTTP y es la
  única pieza nueva de orquestación (arma la fila final y decide cuándo escribirla). No duplica
  ninguna regla de negocio.
- **`frontend/`** — el panel de revisión en React + TypeScript + TanStack Query + Tailwind.
  Empezó en Streamlit; se migró a React completo cuando Streamlit se quedó corto para la
  interacción que necesitaba (clic en una imagen para verla en grande, atajos de teclado, estado
  que se recuerda entre pasos), manteniendo el mismo backend de Python.

## Demo

Hay un modo demo (`DEMO_MODE=1`) con 3 aspirantes 100% inventados — ninguna credencial, ningún
dato real — pensado para mostrar el flujo completo sin depender de Google Sheets ni de la API de
Anthropic. Ver [`demo/README.md`](./demo/README.md).

## Stack

Python · FastAPI · React · TypeScript · Vite · TanStack Query · Tailwind CSS · API de Claude
(Anthropic) · Google Sheets API · PyMuPDF.

## Correrlo en local

Requiere Python 3.11+, Node 20+, una clave de la API de Anthropic y una cuenta de servicio de
Google Cloud con acceso de editor a una hoja de cálculo.

```bash
pip install -r requirements.txt
cp .env.example .env            # completar ANTHROPIC_API_KEY y GOOGLE_SHEETS_SPREADSHEET_ID
# colocar las credenciales de la cuenta de servicio en service-account.json

python -m uvicorn api.main:app --reload --port 8000    # backend
npm install --prefix frontend
npm run dev --prefix frontend                           # frontend (http://localhost:5173)
```

(`.claude/launch.json` ya trae estos tres comandos listos para quien use Claude Code.)

### Pruebas

```bash
python -m pytest tests/ -v
```

## Privacidad y datos

Este proceso maneja información personal real (Ley 1581/2012 de Colombia): cédulas, certificados
laborales, evaluaciones médicas. Por eso:

- `.gitignore` excluye explícitamente cualquier expediente, extracción o caché real
  (`data-ejemplo/*`, `expedientes_procesados/`, el Excel de inscripciones), además de las
  credenciales (`.env`, `service-account.json`).
- El sistema nunca toma ni publica una decisión por sí solo: toda confirmación queda a cargo de
  una persona del equipo de selección, y cada una queda registrada con quién la hizo.
- Las capturas en [`/capturas`](./capturas) usan datos inventados o están censuradas — ningún
  nombre, cédula o documento ahí corresponde a un aspirante real.

## Estado del proyecto

En uso por el equipo de selección de la Universidad Nacional para las convocatorias TO-01 y
TO-02 de 2026. El desarrollo fue dirigido con Claude Code: yo definí las reglas de validación,
el flujo de revisión y cada decisión de producto, probé cada entrega con expedientes reales
cacheados (sin costo de API) antes de aprobarla, y el agente escribió el código.
