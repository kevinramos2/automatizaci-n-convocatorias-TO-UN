import { useEffect, useState } from 'react'
import { urlPagina } from '../api/client'

// Equivalente a app_revision.py:_documento_clickeable — pero sin el hack de CSS
// (botón de popover invisible superpuesto). Acá es un <img> normal con onClick
// que abre un modal real; React maneja el clic de forma nativa.
export function DocumentoClickeable({
  hash,
  paginas: paginasProp,
  etiqueta,
}: {
  hash: string
  paginas?: number[] | null
  etiqueta?: string | null
}) {
  // Algunos expedientes cacheados traen documentos sin "paginas" (Streamlit usaba
  // .get("paginas", [])) — no debe romper toda la pantalla.
  const paginas = paginasProp ?? []
  const [abierto, setAbierto] = useState(false)

  useEffect(() => {
    if (!abierto) return
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && setAbierto(false)
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [abierto])

  if (!paginas.length) return null
  const primera = paginas[0]

  return (
    <>
      <div
        className="group relative cursor-pointer overflow-hidden rounded-lg border"
        style={{ borderColor: 'var(--to-border)' }}
        onClick={() => setAbierto(true)}
      >
        <img src={urlPagina(hash, primera)} alt={etiqueta ?? `Página ${primera}`} className="block w-full transition group-hover:brightness-90" />
        {etiqueta ? (
          <p className="px-1 pt-1 text-[13px]" style={{ color: 'var(--to-ink-muted)' }}>
            {etiqueta}
          </p>
        ) : null}
        <span
          className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full px-2.5 py-0.5 text-[11px] text-white opacity-0 transition group-hover:opacity-100"
          style={{ background: 'rgba(0,0,0,0.65)' }}
        >
          🔍 {paginas.length > 1 ? `Ver las ${paginas.length} páginas` : 'Ampliar'}
        </span>
      </div>

      {abierto && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-6"
          onClick={() => setAbierto(false)}
        >
          <div
            className="flex max-w-4xl flex-col gap-4"
            onClick={(e) => e.stopPropagation()}
          >
            {paginas.map((p) => (
              <div key={p} className="rounded-lg bg-white p-1 shadow-2xl">
                <img src={urlPagina(hash, p, 220)} alt={`Página ${p}`} className="block w-full rounded" />
                {paginas.length > 1 && (
                  <p className="py-1 text-center text-[13px] text-neutral-500">Página {p}</p>
                )}
              </div>
            ))}
            <button
              type="button"
              className="mx-auto rounded-full bg-white px-5 py-2 text-sm font-semibold shadow-lg"
              onClick={() => setAbierto(false)}
            >
              Cerrar
            </button>
          </div>
        </div>
      )}
    </>
  )
}
