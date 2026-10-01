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

## Desplegarlo

1. **Backend** (Render, Fly.io o similar): desplegar la raíz del repo, comando de arranque
   `uvicorn api.main:app --host 0.0.0.0 --port $PORT`, con una sola variable de entorno:
   `DEMO_MODE=1`. No necesita `ANTHROPIC_API_KEY` ni `GOOGLE_SHEETS_SPREADSHEET_ID` ni
   `service-account.json`.
2. **Frontend** (Vercel): desplegar `frontend/`, con `API_URL` apuntando a la URL pública del
   backend del paso anterior (o ajustar `frontend/vite.config.ts` / las llamadas de
   `frontend/src/api/client.ts` si el hosting elegido no soporta un proxy de `/api`).
3. Agregar la variable de entorno `ALLOWED_ORIGINS` al backend con el dominio que asigne Vercel
   (p. ej. `ALLOWED_ORIGINS=https://tu-demo.vercel.app`) — ya no hace falta tocar código.
