import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ExpedienteDetalle } from './components/ExpedienteDetalle'
import { useExpediente } from './hooks/useExpedientes'

const queryClient = new QueryClient()

function AppInterna() {
  const [oscuro, setOscuro] = useState(false)
  const [hashSeleccionado, setHashSeleccionado] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', oscuro ? 'dark' : 'light')
  }, [oscuro])

  const { data: expediente, isLoading } = useExpediente(hashSeleccionado)

  return (
    <div className="flex min-h-screen">
      <Sidebar
        oscuro={oscuro}
        onCambiarOscuro={setOscuro}
        hashSeleccionado={hashSeleccionado}
        onSeleccionar={(h) => {
          setAviso(null)
          setHashSeleccionado(h)
        }}
      />
      <main className="flex-1 px-8 py-8" style={{ background: 'var(--to-bg)' }}>
        <h1 className="mb-6 text-[28px] font-bold" style={{ color: 'var(--to-ink)' }}>
          Panel de revisión — Proceso de selección TO 2026
        </h1>
        {aviso && !hashSeleccionado && (
          <p
            className="mb-4 rounded-lg border px-4 py-3 text-sm font-medium"
            style={{ borderColor: 'var(--to-good-border)', background: 'var(--to-good-bg)', color: 'var(--to-good)' }}
          >
            {aviso}
          </p>
        )}
        {!hashSeleccionado && (
          <p style={{ color: 'var(--to-ink-muted)' }}>
            Elige la convocatoria y un expediente en la barra lateral para comenzar.
          </p>
        )}
        {hashSeleccionado && isLoading && <p style={{ color: 'var(--to-ink-muted)' }}>Cargando…</p>}
        {hashSeleccionado && expediente && (
          <ErrorBoundary key={expediente._hash}>
            <ExpedienteDetalle
              expediente={expediente}
              onGuardado={(estadoFinal) => {
                setAviso(`Revisión guardada. Estado final: ${estadoFinal}`)
                setHashSeleccionado(null)
              }}
            />
          </ErrorBoundary>
        )}
      </main>
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
