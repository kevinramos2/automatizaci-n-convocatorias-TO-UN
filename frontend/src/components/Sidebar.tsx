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
                    onClick={(e) => {
                      // Sin foco residual: al navegar con el teclado no debe dibujarse un aro sobre la tarjeta.
                      e.currentTarget.blur()
                      onSeleccionar(o.hash)
                    }}
                    className="w-full rounded-[9px] border px-2.5 py-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-[var(--to-accent)]"
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
            className="flex h-10 items-center justify-center gap-1.5 rounded-lg border text-[13px] font-semibold"
            style={{ background: 'var(--to-accent-tint)', borderColor: 'var(--to-accent-tint-border)', color: 'var(--to-accent)' }}
          >
            <span className="text-base leading-none" aria-hidden="true">+</span> Subir expediente nuevo
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
  const [arrastrando, setArrastrando] = useState(false)
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

  const etiquetaCampo = 'mb-1.5 block text-[11px] font-bold tracking-wide uppercase'
  const tamano = archivo ? (archivo.size >= 1024 * 1024 ? `${(archivo.size / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(archivo.size / 1024))} KB`) : ''

  function elegir(f: File | undefined | null) {
    if (!f) return
    if (f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf')) {
      setMensaje('El archivo debe ser un PDF.')
      return
    }
    setMensaje(null)
    setArchivo(f)
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-center justify-between">
        <p className="text-[15px] font-bold" style={{ color: 'var(--to-ink)' }}>Subir expediente nuevo</p>
        <button type="button" onClick={onVolver} disabled={procesar.isPending} className="text-xs font-semibold disabled:opacity-50" style={{ color: 'var(--to-accent)' }}>
          ← Volver
        </button>
      </div>

      <div>
        <label htmlFor="conv" className={etiquetaCampo} style={{ color: 'var(--to-ink-muted)' }}>Convocatoria</label>
        <select
          id="conv"
          className="h-10 w-full rounded-lg border px-2.5 text-sm font-medium"
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
        <span className={etiquetaCampo} style={{ color: 'var(--to-ink-muted)' }}>PDF del expediente</span>
        {archivo ? (
          <div className="flex items-center gap-3 rounded-xl border p-3" style={{ background: 'var(--to-accent-tint)', borderColor: 'var(--to-accent-tint-border)' }}>
            <div className="flex h-10 w-9 shrink-0 items-center justify-center rounded-md text-[10px] font-bold" style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }} aria-hidden="true">PDF</div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-semibold" style={{ color: 'var(--to-ink)' }} title={archivo.name}>{archivo.name}</div>
              <div className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>{tamano}</div>
            </div>
            <button
              type="button"
              onClick={() => setArchivo(null)}
              disabled={procesar.isPending}
              aria-label="Quitar archivo"
              title="Quitar archivo"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-base disabled:opacity-50"
              style={{ color: 'var(--to-ink-muted)' }}
            >
              ✕
            </button>
          </div>
        ) : (
          <label
            htmlFor="pdf"
            onDragOver={(e) => {
              e.preventDefault()
              setArrastrando(true)
            }}
            onDragLeave={() => setArrastrando(false)}
            onDrop={(e) => {
              e.preventDefault()
              setArrastrando(false)
              elegir(e.dataTransfer.files?.[0])
            }}
            className="flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border-2 border-dashed px-4 py-6 text-center focus-within:ring-2 focus-within:ring-[var(--to-accent)]"
            style={{
              borderColor: arrastrando ? 'var(--to-accent)' : 'var(--to-border)',
              background: arrastrando ? 'var(--to-accent-tint)' : 'var(--to-surface)',
            }}
          >
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--to-accent)' }} aria-hidden="true">
              <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
            </svg>
            <span className="text-[13.5px] font-semibold" style={{ color: 'var(--to-ink)' }}>Arrastra el PDF aquí</span>
            <span className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>o <span className="font-semibold underline" style={{ color: 'var(--to-accent)' }}>elige un archivo</span></span>
            <input id="pdf" type="file" accept="application/pdf" onChange={(e) => elegir(e.target.files?.[0])} className="sr-only" />
          </label>
        )}
      </div>

      {archivo && (
        <p className="rounded-lg border px-3 py-2 text-xs leading-snug" style={{ color: 'var(--to-ink-muted)', borderColor: 'var(--to-border)', background: 'var(--to-surface)' }}>
          Procesar un expediente nuevo llama a la API de Claude (~$0.15-0.25 USD). Si ya se procesó antes, se carga sin costo.
        </p>
      )}

      <button
        type="button"
        disabled={!archivo || procesar.isPending}
        onClick={manejarProcesar}
        className="h-10 rounded-lg px-3 text-sm font-semibold disabled:opacity-50"
        style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}
      >
        {procesar.isPending ? 'Procesando… puede tardar 1-2 minutos' : 'Procesar expediente'}
      </button>

      {mensaje && <p className="text-xs" style={{ color: 'var(--to-bad)' }}>{mensaje}</p>}
    </div>
  )
}
