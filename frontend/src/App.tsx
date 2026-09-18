import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Sidebar } from './components/Sidebar'
import { ExpedienteDetalle } from './components/ExpedienteDetalle'
import { useExpediente } from './hooks/useExpedientes'

const queryClient = new QueryClient()

function AppInterna() {
  const [oscuro, setOscuro] = useState(false)
  const [hashSeleccionado, setHashSeleccionado] = useState<string | null>(null)

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
        onSeleccionar={setHashSeleccionado}
      />
      <main className="flex-1 px-8 py-8" style={{ background: 'var(--to-bg)' }}>
        <h1 className="mb-6 text-[28px] font-bold" style={{ color: 'var(--to-ink)' }}>
          Panel de revisión — Proceso de selección TO 2026
        </h1>
        {!hashSeleccionado && (
          <p style={{ color: 'var(--to-ink-muted)' }}>
            Elige la convocatoria y un expediente en la barra lateral para comenzar.
          </p>
        )}
        {hashSeleccionado && isLoading && <p style={{ color: 'var(--to-ink-muted)' }}>Cargando…</p>}
        {hashSeleccionado && expediente && (
          <ExpedienteDetalle key={expediente._hash} expediente={expediente} />
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
