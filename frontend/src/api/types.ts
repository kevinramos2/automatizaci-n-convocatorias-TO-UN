// Formas de datos que devuelve api/main.py — reflejan exactamente lo que ya
// arma pipeline/*.py (ver pipeline/validacion_admision.py, procesar_expediente.py).

export interface ResultadoRegla {
  estado: 'cumple' | 'requiere_revision_manual' | 'no_cumple'
  motivo: string
}

export interface Documento {
  tipo: string
  paginas?: number[]
  datos: Record<string, unknown>
}

// Todo lo que el sistema encontró en el PDF, incluso lo que no llegó al checklist.
export interface DocumentoTodo {
  tipo: string | null // tipo final tras la extracción; null si no se pudo leer
  tipo_clasificado: string | null // tipo con el que se clasificó la página
  paginas: number[]
  con_datos: boolean
  entidad: string | null
}

export interface Estudio {
  nivel: string | null
  institucion: string | null
  titulo: string | null
  ultimo_anio_cursado: string | null
  es_boletin: boolean
  nombre_curso: string | null
  horas: number | null
  fecha_inicio: string | null
  fecha_fin: string | null
  fecha_terminacion?: string | null
  paginas?: number[]
  relacionado_sugerido: 'SI' | 'NO' | null
  justificacion_relacionado: string | null
}

export interface Laboral {
  entidad: string | null
  cargo: string | null
  jornada: string | null
  fecha_inicio: string | null
  fecha_fin: string | null
  funciones: string | null
  firmada_jefe: boolean | null
  es_declaracion_jurada_independiente: boolean | null
  notariada: boolean | null
  formato_valido: boolean | null
  paginas?: number[]
  relacionado_sugerido: 'SI' | 'NO' | null
  justificacion_relacionado: string | null
}

export interface Alturas {
  aportado: boolean
  entidad_emisora: string | null
  fecha_expedicion: string | null
  fecha_vencimiento: string | null
  paginas?: number[]
}

export interface Medica {
  aportado: boolean
  entidad_emisora: string | null
  fecha_expedicion: string | null
  concepto_aptitud_alturas: boolean | null
  paginas?: number[]
}

export interface Formulario {
  nombre: string | null
  cedula: string | null
  correo: string | null
  celular: string | null
  direccion: string | null
  experiencia: unknown[]
}

export interface Cedula {
  nombre: string | null
  numero: string | null
  aportada: boolean
  legible: boolean | null
}

export interface RevisionHumana {
  entrega_verificada: string
  overrides_academicos: Record<string, string>
  decisiones_relacionado_estudio: Record<string, string>
  decisiones_relacionado_laboral: Record<string, string>
  alturas_override: string
  medica_override: string
  revisado_por: string
}

export interface Inconsistencia {
  detalle: string
}

export interface Expediente {
  _hash: string
  formulario: Formulario
  cedula: Cedula
  estudios: Estudio[]
  laborales: Laboral[]
  alturas: Alturas | null
  medica: Medica | null
  resultados_validacion: Record<string, ResultadoRegla>
  decision: { estado_sugerido: string; causal_sugerida: string | null }
  inconsistencias: Inconsistencia[]
  documentos: Documento[]
  documentos_todos?: DocumentoTodo[]
  paginas_blancas?: number[]
  indices_academicos: number[]
  rotacion: number
  convocatoria?: string
  estado_confirmado_por_humano?: string | null
  revisado_por?: string | null
  fecha_revision?: string | null
  revision_humana?: RevisionHumana | null
}

export interface ExpedienteResumen {
  hash: string
  nombre: string
  cedula: string
  convocatoria: string
  estado_sugerido: string
  estado_confirmado_por_humano: string | null
}

export interface RevisionInput {
  revisado_por: string
  entrega_verificada: string
  overrides_academicos: Record<string, string>
  decisiones_relacionado_estudio: Record<string, string>
  decisiones_relacionado_laboral: Record<string, string>
  alturas_override: string
  medica_override: string
}

export interface RevisionResultado {
  estado_final: string
  causal: string | null
}

export interface RevisionPreview {
  resultados_actualizados: Record<string, ResultadoRegla>
  decision_actualizada: { estado_sugerido: string; causal_sugerida: string | null; items_pendientes?: string[] }
}

export interface ProcesarResultado {
  hash: string
  ya_procesado: boolean
  costo_usd: number
  uso?: { input_tokens: number; output_tokens: number }
}
