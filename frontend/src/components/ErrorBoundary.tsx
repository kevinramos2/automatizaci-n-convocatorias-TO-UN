import { Component, type ReactNode } from 'react'

// Sin esto, cualquier error al renderizar deja TODA la pantalla en blanco sin
// pista de qué pasó. Con esto se ve el mensaje y el resto de la app sigue viva.
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="m-6 h-fit flex-1 rounded-lg border p-4" style={{ borderColor: 'var(--to-bad-border)', background: 'var(--to-bad-bg)', color: 'var(--to-bad)' }}>
          <p className="font-semibold">No se pudo mostrar este aspirante.</p>
          <p className="mt-1 text-sm">{this.state.error.message}</p>
        </div>
      )
    }
    return this.props.children
  }
}
