import { useEffect, useState, type ReactNode } from 'react'
import { urlPagina } from '../api/client'
import { ModalPaginas } from './ModalPaginas'

export interface PaginaVisor {
  pagina: number
  etiqueta: string | null
  inicioDoc: boolean
}

function BotonIcono({ etiqueta, onClick, children }: { etiqueta: string; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={etiqueta}
      title={etiqueta}
      onClick={onClick}
      className="flex h-[34px] w-[34px] items-center justify-center rounded-md text-white hover:bg-white/15"
    >
      {children}
    </button>
  )
}

const ICONO = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round' } as const

// Zona central: franja con el paso actual, visor con zoom/rotación y tira de miniaturas.
export function Visor({
  hash,
  paginas,
  pagina,
  onPagina,
  paso,
  totalPasos,
  titulo,
}: {
  hash: string
  paginas: PaginaVisor[]
  pagina: number | null
  onPagina: (p: number) => void
  paso: number
  totalPasos: number
  titulo: string
}) {
  const [zoom, setZoom] = useState(1)
  const [giro, setGiro] = useState(0)
  const [ampliado, setAmpliado] = useState(false)

  useEffect(() => {
    setZoom(1)
    setGiro(0)
  }, [pagina])

  const paginaActual = paginas.find((p) => p.pagina === pagina) ?? paginas[0] ?? null

  return (
    <main className="flex min-w-0 flex-1 flex-col" style={{ background: 'var(--to-bg)' }}>
      <div
        className="flex items-center gap-3.5 border-b px-5 py-3.5"
        style={{ background: 'var(--to-accent-tint)', borderColor: 'var(--to-accent-tint-border)' }}
      >
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[17px] font-bold"
          style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}
          aria-hidden="true"
        >
          {paso}
        </div>
        <div className="min-w-0">
          <div className="text-xs font-bold tracking-wide uppercase" style={{ color: 'var(--to-accent)' }}>
            Paso {paso} de {totalPasos}
          </div>
          <h2 className="truncate text-[20px] leading-tight font-bold" style={{ color: 'var(--to-ink)' }}>{titulo}</h2>
        </div>
      </div>

      <div className="relative min-h-0 flex-1" style={{ background: 'var(--to-viewer)' }}>
        {paginaActual ? (
          <>
            <div className="absolute inset-0 overflow-auto">
              <div
                className="flex items-center justify-center p-6"
                style={{ width: `${zoom * 100}%`, height: `${zoom * 100}%`, minWidth: '100%', minHeight: '100%' }}
              >
                <img
                  src={urlPagina(hash, paginaActual.pagina, 150, giro)}
                  alt={paginaActual.etiqueta ?? `Página ${paginaActual.pagina}`}
                  className="max-h-full max-w-full bg-white object-contain shadow-[0_8px_28px_rgba(33,36,43,.25)]"
                  onClick={() => setAmpliado(true)}
                  style={{ cursor: 'zoom-in' }}
                />
              </div>
            </div>
            <div className="pointer-events-none absolute top-3.5 left-3.5 rounded-full px-3 py-1 text-xs font-semibold text-white" style={{ background: 'rgba(33,36,43,.85)' }}>
              {paginaActual.etiqueta ? `${paginaActual.etiqueta} · ` : ''}página {paginaActual.pagina}
            </div>
            <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-full px-2 py-1" style={{ background: 'rgba(33,36,43,.9)' }}>
              <BotonIcono etiqueta="Alejar" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}>
                <svg width="17" height="17" viewBox="0 0 24 24" {...ICONO}><path d="M5 12h14" /></svg>
              </BotonIcono>
              <span className="min-w-11 text-center text-[12.5px] font-semibold text-white">{Math.round(zoom * 100)}%</span>
              <BotonIcono etiqueta="Acercar" onClick={() => setZoom((z) => Math.min(3, z + 0.25))}>
                <svg width="17" height="17" viewBox="0 0 24 24" {...ICONO}><path d="M12 5v14M5 12h14" /></svg>
              </BotonIcono>
              <span className="mx-1.5 h-[18px] w-px bg-white/30" />
              <BotonIcono etiqueta="Rotar 90°" onClick={() => setGiro((g) => (g + 90) % 360)}>
                <svg width="17" height="17" viewBox="0 0 24 24" {...ICONO}><path d="M20 12a8 8 0 1 1-2.6-5.9M20 4v5h-5" /></svg>
              </BotonIcono>
              <BotonIcono etiqueta="Pantalla completa (todas las páginas)" onClick={() => setAmpliado(true)}>
                <svg width="17" height="17" viewBox="0 0 24 24" {...ICONO}><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
              </BotonIcono>
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center text-sm" style={{ color: 'var(--to-ink-muted)' }}>
            No se aportó ningún documento en esta sección.
          </div>
        )}
      </div>

      <div className="flex items-end gap-3 overflow-x-auto border-t px-5 py-3" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)', minHeight: 104 }}>
        {paginas.map((p) => {
          const activa = paginaActual?.pagina === p.pagina
          return (
            <button key={p.pagina} type="button" onClick={() => onPagina(p.pagina)} className="flex shrink-0 flex-col items-center gap-1" title={`Página ${p.pagina}`}>
              <img
                src={urlPagina(hash, p.pagina, 30)}
                alt={`Miniatura página ${p.pagina}`}
                loading="lazy"
                className="block h-[68px] min-w-[52px] w-auto max-w-[96px] bg-white object-contain"
                style={{ border: activa ? '2px solid var(--to-accent)' : '1px solid var(--to-border)', borderRadius: 3 }}
              />
              <span className="max-w-[104px] text-center text-[11px] leading-tight" style={{ color: 'var(--to-ink-muted)' }}>
                {p.inicioDoc && p.etiqueta ? p.etiqueta : `Pág. ${p.pagina}`}
              </span>
            </button>
          )
        })}
        {paginas.length === 0 && <span className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>Sin páginas</span>}
      </div>

      {ampliado && paginaActual && (
        <ModalPaginas hash={hash} paginas={paginas.map((p) => p.pagina)} onCerrar={() => setAmpliado(false)} />
      )}
    </main>
  )
}
