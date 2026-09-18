import { useMemo, useState } from 'react'
import { useConvocatorias, useListaExpedientes, useProcesarExpediente } from '../hooks/useExpedientes'
import { ErrorAPI } from '../api/client'

type Bucket = 'pendientes' | 'admitidos' | 'noadmitidos'

const BUCKETS: Record<Bucket, { etiqueta: string; incluye: (estado: string | null) => boolean }> = {
  pendientes: { etiqueta: 'Pend.', incluye: (e) => e !== 'ADMITIDO' && e !== 'NO ADMITIDO' },
  admitidos: { etiqueta: 'Admit.', incluye: (e) => e === 'ADMITIDO' },
  noadmitidos: { etiqueta: 'No adm.', incluye: (e) => e === 'NO ADMITIDO' },
}

// Cola de aspirantes (columna izquierda): pestañas por estado, búsqueda y lista
// en orden alfabético y mayúsculas. También aloja la subida de un expediente nuevo.
export function Sidebar({
  hashSeleccionado,
  onSeleccionar,
}: {
  hashSeleccionado: string | null
  onSeleccionar: (hash: string) => void
}) {
  const [modo, setModo] = useState<'lista' | 'subir'>('lista')
  const [bucket, setBucket] = useState<Bucket>('pendientes')
  const [busqueda, setBusqueda] = useState('')

  const { data: expedientes, isLoading } = useListaExpedientes()

  const conteos = useMemo(() => {
    const c: Record<Bucket, number> = { pendientes: 0, admitidos: 0, noadmitidos: 0 }
    for (const e of expedientes ?? []) {
      for (const b of Object.keys(BUCKETS) as Bucket[]) if (BUCKETS[b].incluye(e.estado_confirmado_por_humano)) c[b]++
    }
    return c
  }, [expedientes])

  const opciones = useMemo(() => {
    const q = busqueda.trim().toUpperCase()
    return [...(expedientes ?? [])]
      .filter((e) => BUCKETS[bucket].incluye(e.estado_confirmado_por_humano))
      .filter((e) => !q || e.nombre.toUpperCase().includes(q) || e.cedula.replace(/\D/g, '').includes(q.replace(/\D/g, '') || '§'))
      .sort((a, b) => a.nombre.toUpperCase().localeCompare(b.nombre.toUpperCase()))
  }, [expedientes, bucket, busqueda])

  return (
    <aside
      className="flex w-[264px] shrink-0 flex-col gap-2.5 overflow-hidden border-r p-3.5"
      style={{ background: 'var(--to-surface-2)', borderColor: 'var(--to-border)', color: 'var(--to-ink)' }}
    >
      {modo === 'lista' ? (
        <>
          <div className="flex gap-0.5 rounded-[9px] p-[3px]" style={{ background: 'var(--to-border)' }} role="tablist">
            {(Object.keys(BUCKETS) as Bucket[]).map((b) => {
              const activa = bucket === b
              return (
                <button
                  key={b}
                  type="button"
                  role="tab"
                  aria-selected={activa}
                  onClick={() => setBucket(b)}
                  className="h-8 flex-1 basis-0 rounded-[7px] text-[11.5px] font-semibold"
                  style={{
                    background: activa ? 'var(--to-surface)' : 'transparent',
                    color: activa ? 'var(--to-ink)' : 'var(--to-ink-muted)',
                    boxShadow: activa ? '0 1px 2px rgba(0,0,0,.12)' : 'none',
                  }}
                >
                  {BUCKETS[b].etiqueta} <span className="font-bold">{conteos[b]}</span>
                </button>
              )
            })}
          </div>

          <input
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por nombre o cédula"
            aria-label="Buscar aspirante"
            className="h-[34px] w-full rounded-lg border px-3 text-[13px]"
            style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)', color: 'var(--to-ink)' }}
          />

          <div className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto">
            {isLoading ? (
              <p className="p-2 text-sm" style={{ color: 'var(--to-ink-muted)' }}>Cargando…</p>
            ) : opciones.length === 0 ? (
              <p className="p-2 text-sm" style={{ color: 'var(--to-ink-muted)' }}>
                No hay aspirantes en esta pestaña{busqueda ? ' con esa búsqueda' : ''}.
              </p>
            ) : (
              opciones.map((o) => {
                const sel = o.hash === hashSeleccionado
                return (
                  <button
                    key={o.hash}
                    type="button"
                    onClick={() => onSeleccionar(o.hash)}
                    className="w-full rounded-[9px] border px-2.5 py-2 text-left"
                    style={{
                      background: sel ? 'var(--to-accent-tint)' : 'transparent',
                      borderColor: sel ? 'var(--to-accent-tint-border)' : 'transparent',
                      color: 'var(--to-ink)',
                    }}
                  >
                    <div className="text-xs leading-snug font-semibold">{o.nombre.toUpperCase()}</div>
                    <div className="font-mono-to mt-0.5 text-[11px]" style={{ color: 'var(--to-ink-muted)' }}>
                      C.C. {o.cedula}
                      {o.convocatoria !== '—' ? ` · ${o.convocatoria}` : ''}
                    </div>
                  </button>
                )
              })
            )}
          </div>

          <button
            type="button"
            onClick={() => setModo('subir')}
            className="h-9 rounded-lg border text-[13px] font-semibold"
            style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}
          >
            Subir expediente nuevo
          </button>
        </>
      ) : (
        <SubirExpediente
          onVolver={() => setModo('lista')}
          onProcesado={(hash) => {
            setModo('lista')
            setBucket('pendientes')
            onSeleccionar(hash)
          }}
        />
      )}
    </aside>
  )
}

function SubirExpediente({ onProcesado, onVolver }: { onProcesado: (hash: string) => void; onVolver: () => void }) {
  const { data: convocatorias } = useConvocatorias()
  const [convocatoria, setConvocatoria] = useState<string>('')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const procesar = useProcesarExpediente()

  const opcionesConv = convocatorias ? Object.entries(convocatorias) : []
  const convActual = convocatoria || opcionesConv[0]?.[0] || ''

  async function manejarProcesar() {
    if (!archivo || !convActual) return
    setMensaje(null)
    try {
      const r = await procesar.mutateAsync({ convocatoria: convActual, archivo })
      onProcesado(r.hash)
    } catch (e) {
      setMensaje(e instanceof ErrorAPI ? e.message : 'No se pudo procesar el expediente.')
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-bold">Subir expediente nuevo</p>
      <div>
        <label htmlFor="conv" className="mb-1 block text-sm font-medium">Convocatoria</label>
        <select
          id="conv"
          className="w-full rounded-md border px-2 py-1.5 text-sm"
          style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)', color: 'var(--to-ink)' }}
          value={convActual}
          onChange={(e) => setConvocatoria(e.target.value)}
        >
          {opcionesConv.map(([clave, etiqueta]) => (
            <option key={clave} value={clave}>{etiqueta}</option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="pdf" className="mb-1 block text-sm font-medium">PDF del expediente del aspirante</label>
        <input id="pdf" type="file" accept="application/pdf" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} className="w-full text-sm" />
      </div>

      {archivo && (
        <p className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>
          Procesar un expediente nuevo llama a la API de Claude (~$0.15-0.25 USD). Si ya se procesó antes, se carga sin costo.
        </p>
      )}

      <button
        type="button"
        disabled={!archivo || procesar.isPending}
        onClick={manejarProcesar}
        className="rounded-md px-3 py-2 text-sm font-semibold disabled:opacity-50"
        style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}
      >
        {procesar.isPending ? 'Procesando… puede tardar 1-2 minutos' : 'Procesar expediente'}
      </button>
      <button type="button" onClick={onVolver} disabled={procesar.isPending} className="text-sm font-medium underline disabled:opacity-50">
        Volver a la lista
      </button>

      {mensaje && <p className="text-xs" style={{ color: 'var(--to-bad)' }}>{mensaje}</p>}
    </div>
  )
}
