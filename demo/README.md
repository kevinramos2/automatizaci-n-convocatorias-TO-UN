# Modo demo

Una versión pública de este panel, con **3 aspirantes 100% inventados** (ver
[`cache_demo/`](./cache_demo), generado por [`scripts/generar_demo.py`](../scripts/generar_demo.py)),
pensada para mostrar el proyecto sin tocar ningún dato real ni ninguna credencial.

**Déjalo dicho en cualquier lugar donde se enlace este demo:** los aspirantes, documentos y
números de cédula son inventados. Nada de lo que se ve ahí corresponde a una persona real ni al
proceso real de selección.

## Qué cambia con `DEMO_MODE=1`

- La API lee los expedientes de [`demo/cache_demo/`](./cache_demo) en vez de la caché real de la
  máquina (`pipeline/cache_expedientes.py`).
- `POST /api/expedientes/procesar` (subir un PDF nuevo) queda deshabilitado — los 3 aspirantes
  del demo son fijos.
- Al guardar una revisión, en vez de escribir en Google Sheets, la fila se agrega a
  [`demo/hoja_simulada.py`](./hoja_simulada.py) — un JSON local que el panel muestra en el botón
  "Ver hoja (simulada)". Se reinicia solo si el servidor se reinicia (esperado: cada visita
  empieza limpia). **No hace falta ninguna cuenta de Google ni clave de la API de Anthropic**
  para correr el demo.
- El panel muestra un aviso permanente de "Modo demo" y oculta "Subir expediente nuevo".

Nada de esto afecta al modo normal: todo queda detrás de `if DEMO_MODE`, que solo se activa si
la variable de entorno está puesta explícitamente.

## Los 3 aspirantes

Pensados para mostrar casos distintos, no solo una pantalla bonita:

1. **Todo en regla** — si se confirma cada ítem, termina ADMITIDO.
2. **Sin certificado de alturas y con poca experiencia** — termina NO ADMITIDO sin importar qué
   responda el revisor en lo demás: el sistema no deja admitir por debajo del mínimo.
3. **El resultado depende de la revisión** — tiene una segunda experiencia laboral con una
   relación con el cargo ambigua; según si el revisor la marca como relacionada o no, el
   resultado final cambia entre ADMITIDO y NO ADMITIDO. Es el caso que mejor muestra que el
   sistema sugiere, pero la decisión la toma una persona.

Para regenerarlos (por ejemplo, si cambia alguna regla de validación):

```bash
python scripts/generar_demo.py
rm -f demo/hoja_simulada.json
```

## Desplegarlo (Render + Vercel, ambos con capa gratis)

### 1. Backend en Render

1. [render.com](https://render.com) → crear cuenta con GitHub → **New +** → **Web Service** →
   elegir el repo `automatizaci-n-convocatorias-TO-UN`.
2. Configuración:
   - **Root Directory**: vacío (el backend vive en la raíz del repo).
   - **Runtime**: Python 3 (toma la versión de [`runtime.txt`](../runtime.txt) sola).
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free.
3. **Environment** → agregar variable `DEMO_MODE` = `1`. Nada más — no hace falta
   `ANTHROPIC_API_KEY`, `GOOGLE_SHEETS_SPREADSHEET_ID` ni `service-account.json`.
4. Deploy. Copiar la URL que asigna (algo como `https://automatizacion-to.onrender.com`).
5. Verificar: abrir `<esa URL>/api/config` en el navegador → debe responder
   `{"demo_mode": true, ...}`.

   La capa gratis de Render apaga el servicio tras ~15 min sin tráfico; la primera visita
   después de eso tarda unos 30-60s en responder mientras arranca — normal, no es un error.

### 2. Frontend en Vercel

1. [vercel.com](https://vercel.com) → crear cuenta con GitHub → **Add New** → **Project** →
   el mismo repo.
2. **Root Directory**: `frontend` (obligatorio — es la única carpeta con `package.json` del
   lado de la interfaz). Framework: Vite (se detecta solo).
3. **Environment Variables** → agregar `VITE_API_URL` = la URL de Render del paso anterior,
   **sin** `/` final (p. ej. `https://automatizacion-to.onrender.com`).
4. Deploy. Copiar la URL que asigna Vercel (algo como `https://to-demo.vercel.app`).

### 3. Conectar los dos (CORS)

Volver a Render → **Environment** → agregar `ALLOWED_ORIGINS` = la URL exacta de Vercel del
paso anterior (p. ej. `ALLOWED_ORIGINS=https://to-demo.vercel.app`) → guardar (Render reinicia
el servicio solo).

### 4. Probar

Abrir la URL de Vercel: debe salir el aviso de "Modo demo", los 3 aspirantes en Pendientes, y
"Ver hoja (simulada)" debe llenarse al guardar una revisión de prueba.
