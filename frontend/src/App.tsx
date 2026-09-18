import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ExpedienteDetalle } from './components/ExpedienteDetalle'
import { useConfig, useConvocatorias, useExpediente } from './hooks/useExpedientes'

const queryClient = new QueryClient()

function AppInterna() {
  const [oscuro, setOscuro] = useState(false)
  const [hashSeleccionado, setHashSeleccionado] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', oscuro ? 'dark' : 'light')
  }, [oscuro])

  const { data: expediente, isLoading } = useExpediente(hashSeleccionado)
  const { data: config } = useConfig()
  const { data: convocatorias } = useConvocatorias()

  const convocatoria = expediente?.convocatoria ? convocatorias?.[expediente.convocatoria] ?? expediente.convocatoria : null

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--to-bg)', color: 'var(--to-ink)' }}>
      <header
        className="flex h-14 shrink-0 items-center gap-3.5 border-b px-5"
        style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}
      >
        <div className="flex h-[30px] w-[30px] items-center justify-center rounded-lg text-base font-bold" style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }} aria-hidden="true">
          ✓
        </div>
        <h1 className="text-[15px] font-bold">Revisión de aspirantes</h1>
        {convocatoria && (
          <span
            className="rounded-full border px-3 py-1 text-[12.5px] font-semibold"
            style={{ background: 'var(--to-accent-tint)', borderColor: 'var(--to-accent-tint-border)', color: 'var(--to-accent)' }}
          >
            {convocatoria}
          </span>
        )}
        <div className="flex-1" />
        {config?.sheet_url && (
          <a
            href={config.sheet_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border px-3.5 text-[13px] font-semibold"
            style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)', color: 'var(--to-ink)' }}
          >
            Abrir Google Sheet ↗
          </a>
        )}
        <button
          type="button"
          onClick={() => setOscuro((o) => !o)}
          aria-pressed={oscuro}
          className="h-9 rounded-lg border px-3 text-[13px] font-semibold"
          style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface)', color: 'var(--to-ink)' }}
        >
          {oscuro ? 'Tema claro' : 'Tema oscuro'}
        </button>
      </header>

      <div className="flex min-h-0 flex-1">
        <Sidebar
          hashSeleccionado={hashSeleccionado}
          onSeleccionar={(h) => {
            setAviso(null)
            setHashSeleccionado(h)
          }}
        />

        {hashSeleccionado && expediente ? (
          <ErrorBoundary key={expediente._hash}>
            <ExpedienteDetalle
              expediente={expediente}
              onGuardado={(estadoFinal) => {
                setAviso(`Revisión guardada. Estado final: ${estadoFinal}`)
                setHashSeleccionado(null)
              }}
            />
          </ErrorBoundary>
        ) : (
          <main className="flex-1 overflow-y-auto p-8">
            {aviso && (
              <p
                className="mb-4 rounded-lg border px-4 py-3 text-sm font-medium"
                style={{ borderColor: 'var(--to-good-border)', background: 'var(--to-good-bg)', color: 'var(--to-good)' }}
              >
                {aviso}
              </p>
            )}
            <p style={{ color: 'var(--to-ink-muted)' }}>
              {hashSeleccionado && isLoading
                ? 'Cargando…'
                : 'Elige un aspirante en la lista de la izquierda para comenzar la revisión.'}
            </p>
          </main>
        )}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppInterna />
    </QueryClientProvider>
  )
}
