import { useHojaSimulada } from '../hooks/useExpedientes'

// Columnas más relevantes para mostrar primero; el resto de pipeline/esquema_sheets.py
// se ve igual al desplazar la tabla, pero estas son las que cuentan la historia.
const COLUMNAS_DESTACADAS = ['nombre_aspirante', 'id_aspirante', 'admitido_si_no', 'causal_no_admision', 'revisado_por', 'fecha_revision']

// Reemplaza al botón "Abrir Google Sheet" cuando config.demo_mode es true: no hay
// ninguna hoja de cálculo real detrás, así que esto muestra lo que se ha ido
// "guardando" en esta sesión del demo (ver demo/hoja_simulada.py en el backend).
export function HojaSimulada({ onCerrar }: { onCerrar: () => void }) {
  const { data, isLoading } = useHojaSimulada(true)
  const filas = data?.filas ?? []
  const columnas = filas.length
    ? [...COLUMNAS_DESTACADAS.filter((c) => c in filas[0]), ...Object.keys(filas[0]).filter((c) => !COLUMNAS_DESTACADAS.includes(c))]
    : []

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-5" style={{ background: 'rgba(15,17,21,.6)' }} onClick={onCerrar}>
      <div
        role="dialog"
        aria-label="Hoja de cálculo simulada"
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[80vh] w-full max-w-4xl flex-col gap-3 rounded-xl border p-5"
        style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-[17px] font-bold" style={{ color: 'var(--to-ink)' }}>Hoja de cálculo (simulada)</h2>
            <p className="mt-0.5 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
              En producción esto es un Google Sheet real. Acá, para la demo, cada fila se agrega sola a esta tabla
              en cuanto guardas una revisión — sin ninguna cuenta ni credencial de Google.
            </p>
          </div>
          <button type="button" onClick={onCerrar} aria-label="Cerrar" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-lg" style={{ color: 'var(--to-ink-muted)' }}>✕</button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto rounded-lg border" style={{ borderColor: 'var(--to-border)' }}>
          {isLoading ? (
            <p className="p-4 text-sm" style={{ color: 'var(--to-ink-muted)' }}>Cargando…</p>
          ) : filas.length === 0 ? (
            <p className="p-4 text-sm" style={{ color: 'var(--to-ink-muted)' }}>
              Todavía no has guardado ninguna revisión en este demo. Elige un aspirante, revísalo y guarda — la fila aparecerá aquí.
            </p>
          ) : (
            <table className="w-full border-collapse text-[12.5px]">
              <thead>
                <tr style={{ background: 'var(--to-surface-2)' }}>
                  {columnas.map((c) => (
                    <th key={c} className="sticky top-0 border-b px-3 py-2 text-left font-bold whitespace-nowrap" style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface-2)', color: 'var(--to-ink)' }}>
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filas.map((fila, i) => (
                  <tr key={i} style={{ borderTop: i ? '1px solid var(--to-border)' : undefined }}>
                    {columnas.map((c) => (
                      <td key={c} className="px-3 py-2 whitespace-nowrap" style={{ color: 'var(--to-ink-muted)' }}>{String(fila[c] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
