import { useEffect } from 'react'
import { urlPagina } from '../api/client'

// Vista ampliada (pantalla completa) de las páginas de un documento — un modal
// normal de React: clic fuera o Escape lo cierra.
export function ModalPaginas({
  hash,
  paginas,
  onCerrar,
}: {
  hash: string
  paginas: number[]
  onCerrar: () => void
}) {
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && onCerrar()
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [onCerrar])

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/70 p-6" onClick={onCerrar}>
      <div className="flex max-w-4xl flex-col gap-4" onClick={(e) => e.stopPropagation()}>
        {paginas.map((p) => (
          <div key={p} className="rounded-lg bg-white p-1 shadow-2xl">
            <img src={urlPagina(hash, p, 220)} alt={`Página ${p}`} className="block w-full rounded" />
            {paginas.length > 1 && <p className="py-1 text-center text-[13px] text-neutral-500">Página {p}</p>}
          </div>
        ))}
        <button
          type="button"
          className="mx-auto rounded-full bg-white px-5 py-2 text-sm font-semibold shadow-lg"
          onClick={onCerrar}
        >
          Cerrar
        </button>
      </div>
    </div>
  )
}
