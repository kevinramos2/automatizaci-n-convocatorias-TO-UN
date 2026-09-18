import { useMemo, useState } from 'react'
import { useConfig, useConvocatorias, useListaExpedientes, useProcesarExpediente } from '../hooks/useExpedientes'
import { ErrorAPI } from '../api/client'

type Bucket = 'Pendientes de revisión' | 'Admitidos' | 'No admitidos'

const BUCKETS: Record<Bucket, (estado: string | null) => boolean> = {
  'Pendientes de revisión': (e) => e !== 'ADMITIDO' && e !== 'NO ADMITIDO',
  Admitidos: (e) => e === 'ADMITIDO',
  'No admitidos': (e) => e === 'NO ADMITIDO',
}

export function Sidebar({
  oscuro,
  onCambiarOscuro,
  hashSeleccionado,
  onSeleccionar,
}: {
  oscuro: boolean
  onCambiarOscuro: (v: boolean) => void
  hashSeleccionado: string | null
  onSeleccionar: (hash: string) => void
}) {
  const [fuente, setFuente] = useState<'elegir' | 'subir'>('elegir')
  const [bucket, setBucket] = useState<Bucket>('Pendientes de revisión')

  const { data: config } = useConfig()
  const { data: expedientes, isLoading } = useListaExpedientes()

  const opciones = useMemo(() => {
    if (!expedientes) return []
    return [...expedientes]
      .filter((e) => BUCKETS[bucket](e.estado_confirmado_por_humano))
      .sort((a, b) => a.nombre.toUpperCase().localeCompare(b.nombre.toUpperCase()))
  }, [expedientes, bucket])

  return (
    <aside
      className="sticky top-0 flex h-screen w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r px-5 py-6"
      style={{ background: 'var(--to-surface-2)', borderColor: 'var(--to-border)', color: 'var(--to-ink)' }}
    >
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={oscuro} onChange={(e) => onCambiarOscuro(e.target.checked)} />
        Tema oscuro
      </label>

      <hr style={{ borderColor: 'var(--to-border)' }} />

      <h2 className="text-lg font-bold">Proceso de selección TO 2026</h2>

      {config?.sheet_url && (
        <a
          href={config.sheet_url}
          target="_blank"
          rel="noreferrer"
          className="block rounded-md border px-3 py-2 text-center text-sm font-medium"
          style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)' }}
        >
          Abrir Google Sheet ↗
        </a>
      )}

      <div>
        <p className="mb-1 text-sm font-medium">Expediente a revisar</p>
        {(['elegir', 'subir'] as const).map((f) => (
          <label key={f} className="flex cursor-pointer items-center gap-2 py-0.5 text-sm">
            <input type="radio" name="fuente" checked={fuente === f} onChange={() => setFuente(f)} />
            {f === 'elegir' ? 'Elegir un expediente ya procesado' : 'Subir un expediente nuevo'}
          </label>
        ))}
      </div>

      <hr style={{ borderColor: 'var(--to-border)' }} />

      {fuente === 'elegir' ? (
        <>
          <div>
            <p className="mb-1 text-sm font-medium">Ver</p>
            {(Object.keys(BUCKETS) as Bucket[]).map((b) => (
              <label key={b} className="flex cursor-pointer items-center gap-2 py-0.5 text-sm">
                <input type="radio" name="bucket" checked={bucket === b} onChange={() => setBucket(b)} />
                {b}
              </label>
            ))}
          </div>

          <div>
            <p className="mb-1 text-sm font-medium">Aspirante</p>
            {isLoading ? (
              <p className="text-sm" style={{ color: 'var(--to-ink-muted)' }}>Cargando…</p>
            ) : opciones.length === 0 ? (
              <p className="text-sm" style={{ color: 'var(--to-ink-muted)' }}>
                No hay expedientes en «{bucket}» todavía.
              </p>
            ) : (
              <select
                className="w-full rounded-md border px-2 py-1.5 text-sm"
                style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)', color: 'var(--to-ink)' }}
                value={hashSeleccionado ?? ''}
                onChange={(e) => onSeleccionar(e.target.value)}
              >
                <option value="" disabled>
                  — elige un aspirante —
                </option>
                {opciones.map((o) => (
                  <option key={o.hash} value={o.hash}>
                    {o.nombre.toUpperCase()} — C.C. {o.cedula}
                    {o.convocatoria !== '—' ? ` — ${o.convocatoria}` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>
        </>
      ) : (
        <SubirExpediente onProcesado={onSeleccionar} />
      )}
    </aside>
  )
}

function SubirExpediente({ onProcesado }: { onProcesado: (hash: string) => void }) {
  const { data: convocatorias } = useConvocatorias()
  const [convocatoria, setConvocatoria] = useState<string>('')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const procesar = useProcesarExpediente()

  const opcionesConv = convocatorias ? Object.entries(convocatorias) : []
  if (!convocatoria && opcionesConv.length) setConvocatoria(opcionesConv[0][0])

  async function manejarProcesar() {
    if (!archivo || !convocatoria) return
    setMensaje(null)
    try {
      const r = await procesar.mutateAsync({ convocatoria, archivo })
      setMensaje(
        r.ya_procesado
          ? 'Este expediente ya se había procesado antes — se cargó del caché, sin costo de API.'
          : `Expediente procesado. Costo aprox: $${r.costo_usd.toFixed(4)} USD.`,
      )
      onProcesado(r.hash)
    } catch (e) {
      setMensaje(e instanceof ErrorAPI ? e.message : 'No se pudo procesar el expediente.')
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div>
        <p className="mb-1 text-sm font-medium">Convocatoria</p>
        <select
          className="w-full rounded-md border px-2 py-1.5 text-sm"
          style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)', color: 'var(--to-ink)' }}
          value={convocatoria}
          onChange={(e) => setConvocatoria(e.target.value)}
        >
          {opcionesConv.map(([clave, etiqueta]) => (
            <option key={clave} value={clave}>
              {etiqueta}
            </option>
          ))}
        </select>
      </div>

      <div>
        <p className="mb-1 text-sm font-medium">PDF del expediente del aspirante</p>
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
          className="w-full text-sm"
        />
      </div>

      {archivo && (
        <p className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>
          Procesar un expediente nuevo llama a la API de Claude (~$0.15-0.25 USD por expediente).
        </p>
      )}

      <button
        type="button"
        disabled={!archivo || procesar.isPending}
        onClick={manejarProcesar}
        className="rounded-md px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        style={{ background: 'var(--to-accent)' }}
      >
        {procesar.isPending ? 'Procesando… puede tardar 1-2 minutos' : 'Procesar expediente'}
      </button>

      {mensaje && <p className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>{mensaje}</p>}
    </div>
  )
}
