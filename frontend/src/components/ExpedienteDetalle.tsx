import { useState } from 'react'
import type { Expediente } from '../api/types'
import { ErrorAPI } from '../api/client'
import { useGuardarRevision } from '../hooks/useExpedientes'
import { OPCIONES_ENTREGA, OPCIONES_RELACIONADO, OPCIONES_VALIDEZ, useRevisionState } from '../hooks/useRevisionState'
import { AiBox, ETIQUETA_ESTADO, EstadoBadge, EstadoPill } from './Estado'
import { RadioGroup } from './RadioGroup'
import { DocumentoClickeable } from './DocumentoClickeable'

const ETIQUETA_ITEM: Record<string, string> = {
  formulario: 'Formulario de inscripción',
  cedula: 'Fotocopia de cédula',
  estudio: 'Constancia de estudio',
  laboral: 'Constancias laborales',
  alturas: 'Certificado de alturas',
  medica: 'Evaluación médica',
}

const MINTRABAJO_CONSULTA_ALTURAS = 'https://app2.mintrabajo.gov.co/CentrosEntrenamiento/consulta_ext.aspx'

function paginasDe(expediente: Expediente, tipo: string): number[] {
  const doc = expediente.documentos.find((d) => d.tipo === tipo)
  return doc?.paginas ?? []
}

// Igual que el .capitalize() de Python que usa app_revision.py para el título de
// cada documento académico/relacionado cuando no hay "titulo" (ej. "primaria" -> "Primaria").
function capitalizar(texto: string): string {
  return texto ? texto.charAt(0).toUpperCase() + texto.slice(1).toLowerCase() : texto
}

// Python str(bool) es "True"/"False" — así se veía en Streamlit.
function textoBooleano(valor: boolean | null): string {
  return valor === null ? 'None' : valor ? 'True' : 'False'
}

// Las cajas "Resultado del sistema" en Streamlit siempre muestran la etiqueta del
// estado (CUMPLE/REQUIERE REVISIÓN/NO CUMPLE) seguida del motivo, no solo el motivo.
function etiquetaEstado(estado: string): string {
  return ETIQUETA_ESTADO[estado] ?? estado.toUpperCase()
}

function claveEstado(estadoDecision: string): string {
  if (estadoDecision === 'ADMITIDO') return 'cumple'
  if (estadoDecision === 'NO ADMITIDO') return 'no_cumple'
  return 'requiere_revision_manual'
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

  const hash = expediente._hash
  const { formulario, cedula, estudios, laborales, alturas, medica } = expediente

  const estadoHeader = expediente.estado_confirmado_por_humano || expediente.decision.estado_sugerido

  const indicesRelacionados = estudios.map((_, i) => i).filter((i) => !expediente.indices_academicos.includes(i))

  const estadoFinal = preview?.decision_actualizada.estado_sugerido ?? 'PENDIENTE DE REVISIÓN'
  const decisionFinal = estadoFinal === 'ADMITIDO' || estadoFinal === 'NO ADMITIDO'

  async function manejarGuardar() {
    setMensajeError(null)
    try {
      const r = await guardar.mutateAsync(estado)
      // Igual que Streamlit tras guardar: se quita al aspirante de la vista y
      // queda la pantalla de "elige un aspirante" (el padre muestra el aviso).
      onGuardado(r.estado_final)
    } catch (e) {
      setMensajeError(e instanceof ErrorAPI ? e.message : 'No se pudo guardar la revisión.')
    }
  }

  return (
    <div className="flex max-w-4xl flex-col gap-8">
      {/* Encabezado */}
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="text-xs font-semibold tracking-wide uppercase" style={{ color: 'var(--to-ink-faint)' }}>
            Aspirante
          </span>
          <span className="text-[26px] font-bold" style={{ color: 'var(--to-ink)' }}>
            {(formulario.nombre || '—').toUpperCase()}
          </span>
          <span className="font-mono-to text-[14.5px]" style={{ color: 'var(--to-ink-muted)' }}>
            C.C. {cedula.numero || '—'}
          </span>
        </div>
        <EstadoBadge estado={claveEstado(estadoHeader)} texto={estadoHeader} />
      </div>

      {expediente.inconsistencias.length > 0 && (
        <div className="rounded-lg border px-4 py-3" style={{ borderColor: 'var(--to-warn-border)', background: 'var(--to-warn-bg)' }}>
          <p className="mb-2 font-semibold" style={{ color: 'var(--to-warn)' }}>
            {expediente.inconsistencias.length} inconsistencia(s) detectada(s) automáticamente
          </p>
          {expediente.inconsistencias.map((inc, i) => (
            <p key={i} className="text-sm" style={{ color: 'var(--to-ink)' }}>
              {inc.detalle}
            </p>
          ))}
        </div>
      )}

      {/* Checklist de admisión */}
      <section>
        <h2 className="mb-3 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Checklist de admisión
        </h2>
        <div className="flex flex-col gap-2">
          {Object.entries(expediente.resultados_validacion).map(([clave, r], i) => (
            <div key={clave} className="flex gap-3.5 rounded-[10px] border px-4.5 py-3.5" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}>
              <span className="font-mono-to pt-0.5 text-[12.5px]" style={{ color: 'var(--to-ink-faint)' }}>
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <span className="text-[14.5px] font-semibold" style={{ color: 'var(--to-ink)' }}>
                    {ETIQUETA_ITEM[clave] ?? clave}
                  </span>
                  <EstadoPill estado={r.estado} />
                </div>
                <p className="mt-0.5 text-[13px] leading-relaxed" style={{ color: 'var(--to-ink-muted)' }}>
                  {r.motivo}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Firma */}
      <section>
        <h2 className="mb-1 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Confirmar formulario de inscripción y cédula
        </h2>
        <p className="mb-3 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
          Según la lista de chequeo: confirma que el aspirante entregó el formulario de inscripción y la fotocopia de la
          cédula. Nunca se confirma automáticamente.
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            {paginasDe(expediente, 'formulario_inscripcion').length > 1 ? (
              <p className="mb-1 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                Formulario de inscripción — clic en la imagen para ver las {paginasDe(expediente, 'formulario_inscripcion').length} páginas
              </p>
            ) : (
              <p className="mb-1 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                Formulario de inscripción
              </p>
            )}
            <DocumentoClickeable hash={hash} paginas={paginasDe(expediente, 'formulario_inscripcion')} />
          </div>
          <div>
            <p className="mb-1 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>Cédula</p>
            <DocumentoClickeable hash={hash} paginas={paginasDe(expediente, 'cedula')} />
          </div>
        </div>
        <RadioGroup
          name="entrega"
          label="¿Entregó el formulario de inscripción y la fotocopia de la cédula?"
          opciones={OPCIONES_ENTREGA}
          valor={estado.entrega_verificada}
          onChange={(v) => set('entrega_verificada', v)}
        />
      </section>

      {/* Información académica */}
      <section>
        <h2 className="mb-1 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Confirmar información académica
        </h2>
        <p className="mb-3 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
          Solo el colegio (primaria/secundaria) — acta de grado y diploma de bachiller. Acreditan el nivel mínimo de
          educación exigido. Cada documento se valida por separado.
        </p>
        {expediente.indices_academicos.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--to-ink-muted)' }}>
            No se aportó información académica del colegio (acta de grado o diploma de bachiller).
          </p>
        ) : (
          <>
            <AiBox
              label="Resultado del sistema"
              valor={etiquetaEstado(expediente.resultados_validacion.estudio.estado)}
              motivo={expediente.resultados_validacion.estudio.motivo}
            />
            <div className="flex flex-col gap-3">
              {expediente.indices_academicos.map((i) => {
                const e = estudios[i]
                return (
                  <div key={i} className="grid grid-cols-[2fr_1fr] gap-4 rounded-lg border p-4" style={{ borderColor: 'var(--to-border)' }}>
                    <div>
                      <p className="font-semibold" style={{ color: 'var(--to-ink)' }}>
                        {e.titulo || capitalizar(e.nivel ?? '—')} — <em>{e.institucion || '—'}</em>
                      </p>
                      <p className="text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                        {e.fecha_terminacion || e.fecha_fin || ''}
                      </p>
                      <RadioGroup
                        name={`estudio_val_${i}`}
                        label="¿Es válido este documento?"
                        opciones={OPCIONES_VALIDEZ}
                        valor={estado.overrides_academicos[i] ?? OPCIONES_VALIDEZ[0]}
                        onChange={(v) => setEnMapa('overrides_academicos', i, v)}
                      />
                    </div>
                    <DocumentoClickeable hash={hash} paginas={e.paginas} etiqueta={e.titulo || e.nivel} />
                  </div>
                )
              })}
            </div>
          </>
        )}
      </section>

      {/* Educación relacionada */}
      <section>
        <h2 className="mb-1 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Confirmar educación relacionada con las funciones del cargo
        </h2>
        <p className="mb-3 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
          Cursos, técnicos, tecnólogos u otra formación adicional — distintos de la información académica del
          colegio. El sistema sugiere SI/NO, pero nunca decide solo.
        </p>
        {indicesRelacionados.length === 0 ? (
          <p className="text-sm" style={{ color: 'var(--to-ink-muted)' }}>
            No se aportaron cursos, técnicos u otra formación adicional.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {indicesRelacionados.map((i) => {
              const e = estudios[i]
              const esCurso = (e.nivel || '').toLowerCase() === 'curso_capacitacion'
              return (
                <div key={i} className="grid grid-cols-[2fr_1fr] gap-4 rounded-lg border p-4" style={{ borderColor: 'var(--to-border)' }}>
                  <div>
                    <p className="font-semibold" style={{ color: 'var(--to-ink)' }}>
                      {esCurso ? (
                        <>Curso: {e.nombre_curso || '—'} — <em>{e.institucion || '—'}</em></>
                      ) : (
                        <>{e.titulo || capitalizar(e.nivel ?? '—')} — <em>{e.institucion || '—'}</em></>
                      )}
                    </p>
                    {e.relacionado_sugerido && (
                      <AiBox label="Sugerencia de la IA" valor={e.relacionado_sugerido} motivo={e.justificacion_relacionado} />
                    )}
                    <RadioGroup
                      name={`estudio_rel_${i}`}
                      label="¿Relacionado con el cargo?"
                      opciones={OPCIONES_RELACIONADO}
                      valor={estado.decisiones_relacionado_estudio[i] ?? 'PENDIENTE'}
                      onChange={(v) => setEnMapa('decisiones_relacionado_estudio', i, v)}
                    />
                  </div>
                  <DocumentoClickeable hash={hash} paginas={e.paginas} etiqueta={e.titulo || e.nombre_curso} />
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Experiencia laboral relacionada */}
      <section>
        <h2 className="mb-1 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Confirmar experiencia laboral relacionada con el cargo
        </h2>
        <p className="mb-3 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
          El sistema sugiere SI/NO, pero nunca decide solo — confirma o corrige cada una.
        </p>
        <div className="flex flex-col gap-3">
          {laborales.map((exp, i) => (
            <div key={i} className="grid grid-cols-[2fr_1fr] gap-4 rounded-lg border p-4" style={{ borderColor: 'var(--to-border)' }}>
              <div>
                <p className="font-semibold" style={{ color: 'var(--to-ink)' }}>
                  {exp.cargo || '—'} en <em>{exp.entidad || '—'}</em>
                </p>
                <p className="text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>{exp.funciones}</p>
                <p className="text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                  {exp.fecha_inicio || '?'} → {exp.fecha_fin || 'a la fecha'}
                </p>
                {exp.relacionado_sugerido && (
                  <AiBox label="Sugerencia de la IA" valor={exp.relacionado_sugerido} motivo={exp.justificacion_relacionado} />
                )}
                <RadioGroup
                  name={`laboral_rel_${i}`}
                  label="¿Relacionada con el cargo?"
                  opciones={OPCIONES_RELACIONADO}
                  valor={estado.decisiones_relacionado_laboral[i] ?? 'PENDIENTE'}
                  onChange={(v) => setEnMapa('decisiones_relacionado_laboral', i, v)}
                />
              </div>
              <DocumentoClickeable hash={hash} paginas={exp.paginas} />
            </div>
          ))}
        </div>
      </section>

      {/* Alturas y médica */}
      <section>
        <h2 className="mb-1 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Confirmar certificado de alturas y evaluación médica
        </h2>
        <p className="mb-3 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
          El sistema calcula esto de las fechas extraídas, y a veces se equivoca leyendo el documento — revisa la
          imagen antes de confirmar.
        </p>

        {alturas?.aportado && (
          <div className="mb-3 grid grid-cols-[2fr_1fr] gap-4 rounded-lg border p-4" style={{ borderColor: 'var(--to-border)' }}>
            <div>
              <p className="font-semibold" style={{ color: 'var(--to-ink)' }}>
                Certificado de alturas — <em>{alturas.entidad_emisora || '—'}</em>
              </p>
              <p className="text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                Expedición: {alturas.fecha_expedicion || '—'} · Vencimiento: {alturas.fecha_vencimiento || '—'}
              </p>
              <AiBox
                label="Resultado del sistema"
                valor={etiquetaEstado(expediente.resultados_validacion.alturas.estado)}
                motivo={expediente.resultados_validacion.alturas.motivo}
              />
              <a
                href={MINTRABAJO_CONSULTA_ALTURAS}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-block rounded-md border px-3 py-1.5 text-sm font-medium"
                style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface-2)' }}
              >
                Verificar en el Ministerio del Trabajo ↗
              </a>
              <p className="mt-1 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                Busca con la cédula {cedula.numero || '—'} antes de marcar válido o no válido.
              </p>
              <RadioGroup
                name="alturas_val"
                label="¿Es válido el certificado de alturas al cierre de inscripción?"
                opciones={OPCIONES_VALIDEZ}
                valor={estado.alturas_override}
                onChange={(v) => set('alturas_override', v)}
              />
            </div>
            <DocumentoClickeable hash={hash} paginas={alturas.paginas} />
          </div>
        )}

        {medica?.aportado && (
          <div className="grid grid-cols-[2fr_1fr] gap-4 rounded-lg border p-4" style={{ borderColor: 'var(--to-border)' }}>
            <div>
              <p className="font-semibold" style={{ color: 'var(--to-ink)' }}>
                Evaluación médica — <em>{medica.entidad_emisora || '—'}</em>
              </p>
              <p className="text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
                Expedición: {medica.fecha_expedicion || '—'} · Concepto de aptitud en alturas:{' '}
                {textoBooleano(medica.concepto_aptitud_alturas)}
              </p>
              <AiBox
                label="Resultado del sistema"
                valor={etiquetaEstado(expediente.resultados_validacion.medica.estado)}
                motivo={expediente.resultados_validacion.medica.motivo}
              />
              <RadioGroup
                name="medica_val"
                label="¿Es válida la evaluación médica?"
                opciones={OPCIONES_VALIDEZ}
                valor={estado.medica_override}
                onChange={(v) => set('medica_override', v)}
              />
            </div>
            <DocumentoClickeable hash={hash} paginas={medica.paginas} />
          </div>
        )}
      </section>

      {/* Decisión y guardar */}
      <section>
        <h2 className="mb-2 text-xl font-bold" style={{ color: 'var(--to-ink)' }}>
          Decisión con tu revisión
        </h2>
        <EstadoBadge
          estado={claveEstado(estadoFinal)}
          texto={
            estadoFinal +
            (preview?.decision_actualizada.causal_sugerida ? ` — ${preview.decision_actualizada.causal_sugerida}` : '')
          }
        />

        <h3 className="mt-6 mb-2 text-lg font-bold" style={{ color: 'var(--to-ink)' }}>
          Guardar revisión
        </h3>
        {!decisionFinal && (
          <p className="mb-2 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
            Todavía hay ítems pendientes de confirmar arriba (entrega, relacionado, alturas, médica) — resuélvelos
            para poder guardar una decisión final.
          </p>
        )}
        <input
          type="text"
          placeholder="Tu nombre (queda registrado en la auditoría)"
          value={estado.revisado_por}
          onChange={(e) => set('revisado_por', e.target.value)}
          className="mb-3 w-80 rounded-md border px-3 py-2 text-sm"
          style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)', color: 'var(--to-ink)' }}
        />
        <div>
          <button
            type="button"
            disabled={!estado.revisado_por || !decisionFinal || guardar.isPending}
            onClick={manejarGuardar}
            className="rounded-md px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            style={{ background: 'var(--to-accent)' }}
          >
            {guardar.isPending ? 'Guardando…' : 'Guardar revisión en Google Sheets'}
          </button>
        </div>
        {mensajeError && <p className="mt-2 text-sm" style={{ color: 'var(--to-bad)' }}>{mensajeError}</p>}
      </section>
    </div>
  )
}
