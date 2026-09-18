import type {
  Expediente,
  ExpedienteResumen,
  ProcesarResultado,
  RevisionInput,
  RevisionPreview,
  RevisionResultado,
} from './types'

// vite.config.ts hace proxy de /api -> http://127.0.0.1:8000 en dev.
const BASE = '/api'

class ErrorAPI extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${ruta}`, init)
  if (!r.ok) {
    const cuerpo = await r.json().catch(() => ({}))
    throw new ErrorAPI(r.status, cuerpo.detail || `Error ${r.status}`)
  }
  return r.json()
}

export function listarExpedientes(): Promise<ExpedienteResumen[]> {
  return pedir('/expedientes')
}

export function obtenerExpediente(hash: string): Promise<Expediente> {
  return pedir(`/expedientes/${hash}`)
}

export function listarConvocatorias(): Promise<Record<string, string>> {
  return pedir('/convocatorias')
}

export function obtenerConfig(): Promise<{ sheet_url: string | null }> {
  return pedir('/config')
}

export function urlPagina(hash: string, numero: number, dpi = 150): string {
  return `${BASE}/expedientes/${hash}/paginas/${numero}?dpi=${dpi}`
}

export function previsualizarRevision(hash: string, datos: RevisionInput): Promise<RevisionPreview> {
  return pedir(`/expedientes/${hash}/revision/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })
}

export function guardarRevision(hash: string, datos: RevisionInput): Promise<RevisionResultado> {
  return pedir(`/expedientes/${hash}/revision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(datos),
  })
}

export async function procesarExpediente(convocatoria: string, archivo: File): Promise<ProcesarResultado> {
  const form = new FormData()
  form.append('convocatoria', convocatoria)
  form.append('archivo', archivo)
  return pedir('/expedientes/procesar', { method: 'POST', body: form })
}

export { ErrorAPI }
