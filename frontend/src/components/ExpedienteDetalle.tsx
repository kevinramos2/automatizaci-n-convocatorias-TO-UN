import { useEffect, useMemo, useState } from 'react'
import type { Expediente, ResultadoRegla } from '../api/types'
import { ErrorAPI } from '../api/client'
import { useGuardarRevision } from '../hooks/useExpedientes'
import { useRevisionState } from '../hooks/useRevisionState'
import { AiBox, ETIQUETA_ESTADO, EstadoBadge, EstadoPill } from './Estado'
import { OpcionesGrandes, type Opcion } from './OpcionesGrandes'
import { GaleriaResumen } from './GaleriaResumen'
import { Visor, type PaginaVisor } from './Visor'

const MINTRABAJO_CONSULTA_ALTURAS = 'https://app2.mintrabajo.gov.co/CentrosEntrenamiento/consulta_ext.aspx'

// Atajos: en todas las preguntas 1 = sí, 2 = no, 3 = pendiente / según el sistema.
// Formulario y cédula se confirman por separado (cada uno con su documento en el visor).
const opcionesAporto = (que: string): Opcion[] => [
  { valor: 'Sí aportó', etiqueta: `Sí aportó ${que}`, tono: 'good' },
  { valor: 'No aportó', etiqueta: `No aportó ${que}`, tono: 'bad' },
  { valor: 'Pendiente', tono: 'neutral' },
]
const OPC_FORMULARIO = opcionesAporto('formulario')
const OPC_CEDULA = opcionesAporto('cédula')
const OPC_VALIDEZ: Opcion[] = [
  { valor: 'Sí, válido', tono: 'good' },
  { valor: 'No es válido', tono: 'bad' },
  { valor: 'Según el sistema', tono: 'neutral' },
]
const OPC_RELACIONADO: Opcion[] = [
  { valor: 'SI', etiqueta: 'SÍ', tono: 'good' },
  { valor: 'NO', etiqueta: 'NO', tono: 'bad' },
  { valor: 'PENDIENTE', tono: 'neutral' },
]

// Los 7 pasos, en el orden de app_revision.py + un resumen final antes de guardar.
const PASOS = [
  { clave: 'entrega', titulo: 'Formulario de inscripción y cédula' },
  { clave: 'academica', titulo: 'Información académica' },
  { clave: 'relacionada', titulo: 'Educación relacionada con el cargo' },
  { clave: 'laboral', titulo: 'Experiencia laboral relacionada' },
  { clave: 'alturas', titulo: 'Certificado de alturas' },
  { clave: 'medica', titulo: 'Evaluación médica' },
  { clave: 'resumen', titulo: 'Resumen antes de guardar' },
] as const
const ETIQUETA_STEPPER = ['Entrega', 'Académica', 'Relacionada', 'Laboral', 'Alturas', 'Médica', 'Resumen']
const PASO_RESUMEN = PASOS.length - 1

// Igual que el .capitalize() de Python que usa app_revision.py cuando no hay "titulo".
function capitalizar(texto: string): string {
  return texto ? texto.charAt(0).toUpperCase() + texto.slice(1).toLowerCase() : texto
}

function textoBooleano(valor: boolean | null): string {
  return valor === null ? 'No indica' : valor ? 'Sí' : 'No'
}

// Las cajas "Resultado del sistema" siempre muestran la etiqueta del estado + el motivo.
function etiquetaEstado(estado: string): string {
  return ETIQUETA_ESTADO[estado] ?? estado.toUpperCase()
}

function claveEstado(estadoDecision: string): string {
  if (estadoDecision === 'ADMITIDO') return 'cumple'
  if (estadoDecision === 'NO ADMITIDO') return 'no_cumple'
  return 'requiere_revision_manual'
}

function peor(estados: string[]): string {
  if (estados.includes('no_cumple')) return 'no_cumple'
  if (estados.includes('requiere_revision_manual')) return 'requiere_revision_manual'
  return 'cumple'
}

function paginasDeTipo(expediente: Expediente, tipo: string): number[] {
  return expediente.documentos.find((d) => d.tipo === tipo)?.paginas ?? []
}

// Algunos expedientes procesados antes no guardaron las páginas del certificado de
// alturas / evaluación médica elegido (p. ej. la médica de Andrés). Si faltan, se busca
// entre los documentos de ese tipo — preferiendo el de la misma entidad emisora.
function paginasConRespaldo(
  expediente: Expediente,
  tipo: string,
  elegido: { paginas?: number[]; entidad_emisora: string | null } | null,
): number[] {
  if (elegido?.paginas?.length) return elegido.paginas
  const candidatos = expediente.documentos.filter((d) => d.tipo === tipo)
  const mismo = candidatos.find((d) => elegido?.entidad_emisora && d.datos.entidad_emisora === elegido.entidad_emisora)
  return (mismo ?? candidatos[0])?.paginas ?? []
}

function aPaginas(paginas: number[] | undefined, etiqueta: string | null): PaginaVisor[] {
  return (paginas ?? []).map((pagina, i) => ({ pagina, etiqueta, inicioDoc: i === 0 }))
}

interface FilaResumen {
  paso: number
  titulo: string
  estado: string
  detalle: string
  revision: string
}

interface Control {
  opciones: Opcion[]
  valor: string
  cambiar: (v: string) => void
}

export function ExpedienteDetalle({
  expediente,
  onGuardado,
}: {
  expediente: Expediente
  onGuardado: (estadoFinal: string) => void
}) {
  const { estado, set, setEnMapa, preview } = useRevisionState(expediente)
  const guardar = useGuardarRevision(expediente._hash)
  const [mensajeError, setMensajeError] = useState<string | null>(null)
  const [paso, setPaso] = useState(0)
  const [itemIdx, setItemIdx] = useState(0)
  const [visitados, setVisitados] = useState<Set<number>>(() => new Set([0]))

  const hash = expediente._hash
  const { formulario, cedula, estudios, laborales, alturas, medica } = expediente

  const idxAcademicos = expediente.indices_academicos
  const idxRelacionados = useMemo(
    () => estudios.map((_, i) => i).filter((i) => !idxAcademicos.includes(i)),
    [estudios, idxAcademicos],
  )

  const estadoHeader = expediente.estado_confirmado_por_humano || expediente.decision.estado_sugerido
  const estadoFinal = preview?.decision_actualizada.estado_sugerido ?? 'PENDIENTE DE REVISIÓN'
  const causalFinal = preview?.decision_actualizada.causal_sugerida ?? null
  const decisionFinal = estadoFinal === 'ADMITIDO' || estadoFinal === 'NO ADMITIDO'

  // Cuántos ítems tiene cada paso (el resumen no tiene).
  function nItems(p: number): number {
    if (p === 0) return 2 // formulario, luego cédula
    if (p === 1) return idxAcademicos.length
    if (p === 2) return idxRelacionados.length
    if (p === 3) return laborales.length
    if (p === 4) return alturas?.aportado ? 1 : 0
    if (p === 5) return medica?.aportado ? 1 : 0
    return 0
  }

  function irA(p: number, i = 0) {
    setPaso(p)
    setItemIdx(i)
    setVisitados((v) => new Set(v).add(p))
  }
  function siguiente() {
    if (itemIdx < nItems(paso) - 1) setItemIdx(itemIdx + 1)
    else if (paso < PASO_RESUMEN) irA(paso + 1)
  }
  function anterior() {
    if (itemIdx > 0) setItemIdx(itemIdx - 1)
    else if (paso > 0) irA(paso - 1, Math.max(nItems(paso - 1) - 1, 0))
  }

  // ---- ¿Qué paso está resuelto? (para el avance y los puntos de las pestañas) ----
  const decidido = (mapa: Record<string, string>, i: number) => (mapa[i] ?? 'PENDIENTE') !== 'PENDIENTE'
  // Un paso cuenta como resuelto cuando ya se vio y su resultado (recalculado con las
  // respuestas del revisor) ya no está en "requiere revisión".
  const resultadosVivos = preview?.resultados_actualizados ?? expediente.resultados_validacion
  function hecho(p: number): boolean {
    if (p === PASO_RESUMEN) return decisionFinal
    if (p === 2) return visitados.has(2) && idxRelacionados.every((i) => decidido(estado.decisiones_relacionado_estudio, i))
    const r = resultadosVivos
    const est = p === 0 ? peor([r.formulario.estado, r.cedula.estado]) : r[['formulario', 'estudio', '', 'laboral', 'alturas', 'medica'][p]].estado
    return visitados.has(p) && est !== 'requiere_revision_manual'
  }

  // ---- Visor: documentos de la sección del paso actual ----
  // Documentos por sección del checklist, con solo los de ese paso ("academica" solo el
  // colegio, "relacionada" solo cursos/técnicos). El visor muestra la del paso actual.
  const tabs: { clave: string; paginas: PaginaVisor[] }[] = useMemo(() => {
    const etiquetaEstudio = (i: number) => estudios[i].titulo || estudios[i].nombre_curso || capitalizar(estudios[i].nivel ?? 'Estudio')
    return [
      { clave: 'formulario', paginas: aPaginas(paginasDeTipo(expediente, 'formulario_inscripcion'), 'Formulario') },
      { clave: 'cedula', paginas: aPaginas(paginasDeTipo(expediente, 'cedula'), 'Cédula') },
      { clave: 'academica', paginas: idxAcademicos.flatMap((i) => aPaginas(estudios[i].paginas, etiquetaEstudio(i))) },
      { clave: 'relacionada', paginas: idxRelacionados.flatMap((i) => aPaginas(estudios[i].paginas, etiquetaEstudio(i))) },
      { clave: 'laboral', paginas: laborales.flatMap((l) => aPaginas(l.paginas, l.cargo || l.entidad)) },
      { clave: 'alturas', paginas: aPaginas(paginasConRespaldo(expediente, 'certificado_alturas', alturas), 'Certificado de alturas') },
      { clave: 'medica', paginas: aPaginas(paginasConRespaldo(expediente, 'evaluacion_medica', medica), 'Evaluación médica') },
    ]
  }, [expediente, estudios, laborales, alturas, medica, idxAcademicos, idxRelacionados])
  const [tab, setTab] = useState('formulario')
  const [pagina, setPagina] = useState<number | null>(tabs[0].paginas[0]?.pagina ?? tabs[1].paginas[0]?.pagina ?? null)

  // Al cambiar de paso/ítem, el visor salta al documento correspondiente.
  useEffect(() => {
    const foco = ((): { tab: string; pagina?: number } | null => {
      if (paso === 0) return itemIdx === 0 ? { tab: 'formulario', pagina: tabs[0].paginas[0]?.pagina } : { tab: 'cedula', pagina: tabs[1].paginas[0]?.pagina }
      if (paso === 1) return { tab: 'academica', pagina: estudios[idxAcademicos[itemIdx]]?.paginas?.[0] }
      if (paso === 2) return { tab: 'relacionada', pagina: estudios[idxRelacionados[itemIdx]]?.paginas?.[0] }
      if (paso === 3) return { tab: 'laboral', pagina: laborales[itemIdx]?.paginas?.[0] }
      if (paso === 4) return { tab: 'alturas', pagina: tabs.find((t) => t.clave === 'alturas')?.paginas[0]?.pagina }
      if (paso === 5) return { tab: 'medica', pagina: tabs.find((t) => t.clave === 'medica')?.paginas[0]?.pagina }
      return null
    })()
    if (foco) {
      setTab(foco.tab)
      setPagina(foco.pagina ?? tabs.find((t) => t.clave === foco.tab)?.paginas[0]?.pagina ?? null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paso, itemIdx])

  // ---- Control (opciones) del ítem actual: lo usan la tarjeta y los atajos 1/2/3 ----
  const control: Control | null = (() => {
    if (paso === 0) {
      return itemIdx === 0
        ? { opciones: OPC_FORMULARIO, valor: estado.entrega_formulario, cambiar: (v) => set('entrega_formulario', v) }
        : { opciones: OPC_CEDULA, valor: estado.entrega_cedula, cambiar: (v) => set('entrega_cedula', v) }
    }
    if (paso === 1 && idxAcademicos.length) {
      const i = idxAcademicos[itemIdx]
      return { opciones: OPC_VALIDEZ, valor: estado.overrides_academicos[i] ?? 'Según el sistema', cambiar: (v) => setEnMapa('overrides_academicos', i, v) }
    }
    if (paso === 2 && idxRelacionados.length) {
      const i = idxRelacionados[itemIdx]
      return { opciones: OPC_RELACIONADO, valor: estado.decisiones_relacionado_estudio[i] ?? 'PENDIENTE', cambiar: (v) => setEnMapa('decisiones_relacionado_estudio', i, v) }
    }
    if (paso === 3 && laborales.length) {
      return { opciones: OPC_RELACIONADO, valor: estado.decisiones_relacionado_laboral[itemIdx] ?? 'PENDIENTE', cambiar: (v) => setEnMapa('decisiones_relacionado_laboral', itemIdx, v) }
    }
    if (paso === 4 && alturas?.aportado) return { opciones: OPC_VALIDEZ, valor: estado.alturas_override, cambiar: (v) => set('alturas_override', v) }
    if (paso === 5 && medica?.aportado) return { opciones: OPC_VALIDEZ, valor: estado.medica_override, cambiar: (v) => set('medica_override', v) }
    return null
  })()

  // Atajos: ← → cambian de ítem/paso; 1/2/3 responden (no se activan al escribir en un campo).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLElement | null
      const escribiendo = el && ((el.tagName === 'INPUT' && (el as HTMLInputElement).type !== 'radio') || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')
      if (escribiendo || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 'ArrowRight') siguiente()
      else if (e.key === 'ArrowLeft') anterior()
      else if (control && ['1', '2', '3'].includes(e.key)) {
        const o = control.opciones[Number(e.key) - 1]
        if (o) control.cambiar(o.valor)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  async function manejarGuardar() {
    setMensajeError(null)
    try {
      const r = await guardar.mutateAsync(estado)
      // Igual que Streamlit tras guardar: se quita al aspirante de la vista y queda
      // la pantalla de "elige un aspirante" (el padre muestra el aviso).
      onGuardado(r.estado_final)
    } catch (e) {
      setMensajeError(e instanceof ErrorAPI ? e.message : 'No se pudo guardar la revisión.')
    }
  }

  // ---- Piezas del panel ----
  const rvs = expediente.resultados_validacion
  const cajaSistema = (r: ResultadoRegla) => <AiBox label="Resultado del sistema" valor={etiquetaEstado(r.estado)} motivo={r.motivo} />

  const listaItems = (titulo: string, etiquetas: string[], hechoDe: (n: number) => boolean) =>
    etiquetas.length > 1 && (
      <div className="flex items-center gap-2" role="group" aria-label={titulo}>
        <span className="text-[11.5px] font-bold tracking-wide whitespace-nowrap uppercase" style={{ color: 'var(--to-ink-muted)' }}>
          Ítem {itemIdx + 1} de {etiquetas.length}
        </span>
        <div className="flex flex-wrap gap-1">
          {etiquetas.map((t, n) => {
            const actual = n === itemIdx
            const ok = hechoDe(n)
            return (
              <button
                key={n}
                type="button"
                onClick={() => setItemIdx(n)}
                title={`${t} — ${ok ? 'confirmado' : 'por confirmar'}`}
                aria-label={`${titulo}: ${t}`}
                aria-current={actual ? 'true' : undefined}
                className="flex h-7 min-w-7 items-center justify-center rounded-md border px-1.5 text-xs font-bold"
                style={
                  actual
                    ? { background: 'var(--to-accent)', color: 'var(--to-bg)', borderColor: 'var(--to-accent)' }
                    : ok
                      ? { background: 'var(--to-good-bg)', color: 'var(--to-good)', borderColor: 'var(--to-good-border)' }
                      : { background: 'var(--to-surface)', color: 'var(--to-ink-muted)', borderColor: 'var(--to-border)' }
                }
              >
                {ok && !actual ? '✓' : n + 1}
              </button>
            )
          })}
        </div>
      </div>
    )

  const pregunta = (texto: string) => (
    <>
      <div className="text-[14px] font-semibold" style={{ color: 'var(--to-ink)' }}>{texto}</div>
      {control && <OpcionesGrandes name={`p${paso}_${itemIdx}`} opciones={control.opciones} valor={control.valor} onChange={control.cambiar} />}
    </>
  )
  const titulo = (t: string, sub?: string | null) => (
    <div>
      <div className="line-clamp-2 text-[19px] leading-tight font-bold" title={t} style={{ color: 'var(--to-ink)' }}>{t}</div>
      {sub ? <div className="mt-0.5 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>{sub}</div> : null}
    </div>
  )
  const vacio = (texto: string) => (
    <p className="rounded-lg border p-4 text-sm" style={{ borderColor: 'var(--to-border)', color: 'var(--to-ink-muted)', background: 'var(--to-surface)' }}>{texto}</p>
  )

  // Una fila por sección del resumen (la usan la lista de la derecha y la galería del visor).
  function construirFilas(): FilaResumen[] {
    const res = preview?.resultados_actualizados ?? rvs
    const nRel = idxRelacionados.length
    const nSi = idxRelacionados.filter((i) => estado.decisiones_relacionado_estudio[i] === 'SI').length
    const corto = (v: string) => (v === 'Sí aportó' ? 'sí' : v === 'No aportó' ? 'no' : 'pendiente')
    const nLab = laborales.length
    const nLabSi = laborales.filter((_, n) => estado.decisiones_relacionado_laboral[n] === 'SI').length
    const nombresRel = idxRelacionados.map((i) => `${estudios[i].nombre_curso || estudios[i].titulo || capitalizar(estudios[i].nivel ?? 'Estudio')}: ${estado.decisiones_relacionado_estudio[i] === 'SI' ? 'sí' : estado.decisiones_relacionado_estudio[i] === 'NO' ? 'no' : 'pendiente'}`)
    const nAcadRev = idxAcademicos.filter((i) => (estado.overrides_academicos[i] ?? 'Según el sistema') !== 'Según el sistema').length
    return [
      { paso: 0, titulo: 'Formulario y cédula', estado: peor([res.formulario.estado, res.cedula.estado]), detalle: res.formulario.motivo, revision: `Formulario: ${corto(estado.entrega_formulario)} · Cédula: ${corto(estado.entrega_cedula)}` },
      { paso: 1, titulo: 'Información académica', estado: res.estudio.estado, detalle: res.estudio.motivo, revision: idxAcademicos.length ? `${idxAcademicos.length} documento(s) · ${nAcadRev} validado(s) por ti` : 'Sin documentos del colegio' },
      { paso: 2, titulo: 'Educación relacionada', estado: hecho(2) ? 'cumple' : 'requiere_revision_manual', detalle: nRel ? `${nSi} de ${nRel} relacionados con el cargo` : 'No se aportó formación adicional', revision: nombresRel.join(' · ') || '—' },
      { paso: 3, titulo: 'Experiencia laboral', estado: res.laboral.estado, detalle: res.laboral.motivo, revision: nLab ? `${nLabSi} de ${nLab} constancia(s) relacionada(s) según tú` : 'Sin constancias' },
      { paso: 4, titulo: 'Certificado de alturas', estado: res.alturas.estado, detalle: res.alturas.motivo, revision: `Tu respuesta: ${estado.alturas_override}` },
      { paso: 5, titulo: 'Evaluación médica', estado: res.medica.estado, detalle: res.medica.motivo, revision: `Tu respuesta: ${estado.medica_override}` },
    ]
  }

  // Documentos de cada fila del resumen, para la galería del visor.
  function seccionesGaleria() {
    const de = (clave: string) => tabs.find((t) => t.clave === clave)?.paginas.map((p) => p.pagina) ?? []
    const porPaso = [[...de('formulario'), ...de('cedula')], de('academica'), de('relacionada'), de('laboral'), de('alturas'), de('medica')]
    return construirFilas().map((f) => ({ ...f, paginas: porPaso[f.paso] }))
  }

  function cuerpoPaso() {
    if (paso === 0) {
      const esFormulario = itemIdx === 0
      return (
        <>
          {titulo(
            esFormulario ? 'Formulario de inscripción' : 'Fotocopia de la cédula',
            esFormulario
              ? 'Lista de chequeo: formulario de inscripción diligenciado.'
              : 'Lista de chequeo: fotocopia de la cédula.',
          )}
          {cajaSistema(esFormulario ? rvs.formulario : rvs.cedula)}
          {pregunta(esFormulario ? '¿Aportó el formulario de inscripción?' : '¿Aportó la fotocopia de la cédula?')}
          {listaItems('Documentos de entrega', ['Formulario de inscripción', 'Fotocopia de la cédula'], (n) => (n === 0 ? estado.entrega_formulario : estado.entrega_cedula) !== 'Pendiente')}
        </>
      )
    }
    if (paso === 1) {
      if (!idxAcademicos.length) return vacio('No se aportó información académica del colegio (acta de grado o diploma de bachiller).')
      const e = estudios[idxAcademicos[itemIdx]]
      return (
        <>
          {titulo(e.titulo || capitalizar(e.nivel ?? '—'), [e.institucion, e.fecha_terminacion || e.fecha_fin].filter(Boolean).join(' · '))}
          <p className="text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
            Solo el colegio: acta de grado y diploma. Cada documento se valida por separado.
          </p>
          {cajaSistema(rvs.estudio)}
          {pregunta('¿Es válido este documento?')}
          {listaItems('Documentos del colegio', idxAcademicos.map((i) => estudios[i].titulo || capitalizar(estudios[i].nivel ?? '—')), (n) => (estado.overrides_academicos[idxAcademicos[n]] ?? 'Según el sistema') !== 'Según el sistema')}
        </>
      )
    }
    if (paso === 2) {
      if (!idxRelacionados.length) return vacio('No se aportaron cursos, técnicos u otra formación adicional.')
      const e = estudios[idxRelacionados[itemIdx]]
      const esCurso = (e.nivel || '').toLowerCase() === 'curso_capacitacion'
      const meta = [e.institucion, e.horas ? `${e.horas} horas` : null].filter(Boolean).join(' · ')
      return (
        <>
          {titulo(esCurso ? `Curso: ${e.nombre_curso || '—'}` : e.titulo || capitalizar(e.nivel ?? '—'), meta)}
          {e.relacionado_sugerido && <AiBox label="Sugerencia de la IA" valor={e.relacionado_sugerido} motivo={e.justificacion_relacionado} />}
          {pregunta('¿Está relacionado con el cargo?')}
          {listaItems('Formación de este aspirante', idxRelacionados.map((i) => estudios[i].nombre_curso || estudios[i].titulo || capitalizar(estudios[i].nivel ?? '—')), (n) => decidido(estado.decisiones_relacionado_estudio, idxRelacionados[n]))}
        </>
      )
    }
    if (paso === 3) {
      if (!laborales.length) return vacio('No se aportaron constancias laborales.')
      const l = laborales[itemIdx]
      return (
        <>
          {titulo(`${l.cargo || '—'} en ${l.entidad || '—'}`, `${l.fecha_inicio || '?'} → ${l.fecha_fin || 'a la fecha'}`)}
          {l.funciones && <p className="line-clamp-1 text-[12.5px] leading-snug" title={l.funciones} style={{ color: 'var(--to-ink-muted)' }}>{l.funciones}</p>}
          {l.relacionado_sugerido && <AiBox label="Sugerencia de la IA" valor={l.relacionado_sugerido} motivo={l.justificacion_relacionado} />}
          {pregunta('¿Relacionada con el cargo?')}
          {listaItems('Experiencias de este aspirante', laborales.map((x) => `${x.cargo || '—'} · ${x.entidad || '—'}`), (n) => decidido(estado.decisiones_relacionado_laboral, n))}
          {cajaSistema(rvs.laboral)}
          {expediente.inconsistencias.length > 0 && (
            <details className="rounded-lg border px-3 py-2" style={{ borderColor: 'var(--to-warn-border)', background: 'var(--to-warn-bg)' }}>
              <summary className="cursor-pointer text-[13px] font-semibold" style={{ color: 'var(--to-warn)' }}>
                {expediente.inconsistencias.length} inconsistencia(s) detectada(s) automáticamente — ver
              </summary>
              <div className="mt-1.5 flex max-h-40 flex-col gap-1 overflow-y-auto">
                {expediente.inconsistencias.map((inc, i) => (
                  <p key={i} className="text-[12.5px]" style={{ color: 'var(--to-ink)' }}>{inc.detalle}</p>
                ))}
              </div>
            </details>
          )}
        </>
      )
    }
    if (paso === 4) {
      if (!alturas?.aportado) return vacio('No se aportó certificado de trabajo seguro en alturas.')
      return (
        <>
          {titulo('Certificado de alturas', `${alturas.entidad_emisora || '—'} · Expedición: ${alturas.fecha_expedicion || '—'} · Vencimiento: ${alturas.fecha_vencimiento || '—'}`)}
          <div
            className="flex flex-col gap-2 rounded-xl border-2 p-3"
            style={{ borderColor: 'var(--to-accent)', background: 'var(--to-accent-tint)' }}
          >
            <p className="text-[13.5px] leading-snug font-semibold" style={{ color: 'var(--to-ink)' }}>
              Antes de responder, verifica el certificado en el Ministerio del Trabajo con la cédula{' '}
              <span className="font-mono-to font-bold">{cedula.numero || '—'}</span>.
            </p>
            <a
              href={MINTRABAJO_CONSULTA_ALTURAS}
              target="_blank"
              rel="noreferrer"
              className="flex h-11 items-center justify-center gap-2 rounded-lg px-4 text-[15px] font-bold shadow-md hover:opacity-90"
              style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}
            >
              Verificar en el Ministerio del Trabajo ↗
            </a>
          </div>
          {cajaSistema(rvs.alturas)}
          <p className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>
            El sistema calcula esto de las fechas extraídas y puede equivocarse: revisa la imagen.
          </p>
          {pregunta('¿Es válido el certificado de alturas al cierre de inscripción?')}
        </>
      )
    }
    if (paso === 5) {
      if (!medica?.aportado) return vacio('No se aportó evaluación médica ocupacional.')
      return (
        <>
          {titulo('Evaluación médica', `${medica.entidad_emisora || '—'} · Expedición: ${medica.fecha_expedicion || '—'} · Apto para trabajo en alturas: ${textoBooleano(medica.concepto_aptitud_alturas)}`)}
          {cajaSistema(rvs.medica)}
          {pregunta('¿Es válida la evaluación médica?')}
        </>
      )
    }
    // Resumen
    const filas = construirFilas()
    return (
      <>
        <div className="flex flex-col gap-1.5">
          {filas.map((f, n) => (
            <div key={f.paso} className="flex items-center gap-3 rounded-[10px] border px-3 py-[3px]" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}>
              <span className="font-mono-to text-xs" style={{ color: 'var(--to-ink-muted)' }}>{String(n + 1).padStart(2, '0')}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[13.5px] font-semibold" style={{ color: 'var(--to-ink)' }}>{f.titulo}</div>
                <div className="truncate text-xs leading-snug [@media(min-height:820px)]:line-clamp-2 [@media(min-height:820px)]:whitespace-normal" title={f.detalle} style={{ color: 'var(--to-ink-muted)' }}>{f.detalle}</div>
                <div className="hidden truncate text-xs leading-snug font-medium [@media(min-height:690px)]:block" title={f.revision} style={{ color: 'var(--to-ink)' }}>{f.revision}</div>
              </div>
              <EstadoPill estado={f.estado} />
              <button type="button" onClick={() => irA(f.paso)} className="text-[12.5px] font-semibold underline" style={{ color: 'var(--to-accent)' }}>Editar</button>
            </div>
          ))}
        </div>
      </>
    )
  }

  return (
    <>
      <Visor
        hash={hash}
        paginas={tabs.find((t) => t.clave === tab)?.paginas ?? []}
        pagina={pagina}
        onPagina={setPagina}
        paso={paso + 1}
        totalPasos={PASOS.length}
        titulo={PASOS[paso].titulo}
        contenido={paso === PASO_RESUMEN ? <GaleriaResumen hash={hash} secciones={seccionesGaleria()} onIr={(p) => irA(p)} /> : undefined}
      />

      <aside className="flex w-[460px] shrink-0 flex-col border-l" style={{ background: 'var(--to-bg)', borderColor: 'var(--to-border)' }}>
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-5 py-2">
          <div className="min-w-0">
            <div className="line-clamp-2 text-[19px] leading-tight font-bold" style={{ color: 'var(--to-ink)' }} title={(formulario.nombre || '—').toUpperCase()}>
              {(formulario.nombre || '—').toUpperCase()}
            </div>
            <div className="font-mono-to text-[14px]" style={{ color: 'var(--to-ink-muted)' }}>C.C. {cedula.numero || '—'}</div>
          </div>
          {expediente.estado_confirmado_por_humano && (
            <div className="-mt-1.5 flex items-center gap-2 text-xs" style={{ color: 'var(--to-ink-muted)' }}>
              Guardado como <EstadoBadge estado={claveEstado(estadoHeader)} texto={estadoHeader} pequeno />
            </div>
          )}

          <nav aria-label="Pasos de la revisión" className="flex items-center gap-1.5">
            {PASOS.map((p, i) => {
              const actual = i === paso
              const ok = !actual && hecho(i) && (visitados.has(i) || i === PASO_RESUMEN)
              return (
                <div key={p.clave} className="flex flex-1 items-center gap-1.5 last:flex-none">
                  <button
                    type="button"
                    onClick={() => irA(i)}
                    aria-label={`Paso ${i + 1}: ${ETIQUETA_STEPPER[i]}`}
                    aria-current={actual ? 'step' : undefined}
                    title={ETIQUETA_STEPPER[i]}
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[12.5px] font-bold"
                    style={
                      actual
                        ? { background: 'var(--to-accent)', color: 'var(--to-bg)', boxShadow: '0 0 0 3px var(--to-accent-tint-border)' }
                        : ok
                          ? { background: 'var(--to-good)', color: 'var(--to-bg)' }
                          : { background: 'var(--to-surface)', color: 'var(--to-ink-muted)', border: '1.5px solid var(--to-border)' }
                    }
                  >
                    {ok ? '✓' : i + 1}
                  </button>
                  {i < PASOS.length - 1 && <div className="h-0.5 flex-1" style={{ background: i < paso ? 'var(--to-good)' : 'var(--to-border)' }} />}
                </div>
              )
            })}
          </nav>

          <div className="flex flex-col gap-2">{cuerpoPaso()}</div>
        </div>

        <div className="flex flex-col gap-2 border-t px-5 py-2" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}>
          {paso === PASO_RESUMEN && (
            <div className="flex items-center gap-2.5">
              <EstadoBadge estado={claveEstado(estadoFinal)} texto={estadoFinal} pequeno />
              {(causalFinal || !decisionFinal) && (
                <p className="line-clamp-2 min-w-0 text-xs leading-snug" style={{ color: 'var(--to-ink-muted)' }} title={causalFinal ?? undefined}>
                  {decisionFinal ? causalFinal : 'Hay ítems por confirmar: resuélvelos para poder guardar.'}
                </p>
              )}
            </div>
          )}

          {paso === PASO_RESUMEN ? (
            <>
              <input
                type="text"
                value={estado.revisado_por}
                onChange={(e) => set('revisado_por', e.target.value)}
                aria-label="Tu nombre (queda registrado en la auditoría)"
                placeholder="Tu nombre (queda registrado en la auditoría)"
                className="h-9 rounded-lg border px-3 text-sm"
                style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)', color: 'var(--to-ink)' }}
              />
              <div className="flex gap-2.5">
                <button type="button" onClick={anterior} className="h-10 shrink-0 rounded-lg border px-4 text-sm font-semibold" style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)', color: 'var(--to-ink)' }}>← Anterior</button>
                <button
                  type="button"
                  disabled={!estado.revisado_por.trim() || !decisionFinal || guardar.isPending}
                  onClick={manejarGuardar}
                  className="h-10 flex-1 rounded-lg text-sm font-semibold disabled:opacity-50"
                  style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}
                >
                  {guardar.isPending ? 'Guardando…' : 'Guardar revisión en Google Sheets'}
                </button>
              </div>
              {mensajeError && <p className="text-sm" style={{ color: 'var(--to-bad)' }}>{mensajeError}</p>}
            </>
          ) : (
            <div className="flex items-center gap-2.5">
              <button type="button" onClick={anterior} disabled={paso === 0 && itemIdx === 0} className="h-10 shrink-0 rounded-lg border px-4 text-sm font-semibold disabled:opacity-40" style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)', color: 'var(--to-ink)' }}>← Anterior</button>
              <div className="flex min-w-0 flex-1 justify-center" title="Decisión con tu revisión hasta ahora">
                <EstadoBadge estado={claveEstado(estadoFinal)} texto={estadoFinal} pequeno />
              </div>
              <button type="button" onClick={siguiente} className="h-10 shrink-0 rounded-lg px-4 text-sm font-semibold" style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}>Siguiente →</button>
            </div>
          )}
        </div>
      </aside>
    </>
  )
}
