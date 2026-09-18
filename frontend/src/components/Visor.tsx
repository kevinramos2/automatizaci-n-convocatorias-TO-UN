import { useEffect, useState, type ReactNode } from 'react'
import { urlPagina } from '../api/client'
import { ModalPaginas } from './ModalPaginas'
import { Tecla } from './OpcionesGrandes'

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
  contenido,
}: {
  hash: string
  paginas: PaginaVisor[]
  pagina: number | null
  onPagina: (p: number) => void
  paso: number
  totalPasos: number
  titulo: string
  // Si se da, reemplaza al visor y a las miniaturas (p. ej. la galería del resumen).
  contenido?: ReactNode
}) {
  const [zoom, setZoom] = useState(1)
  const [giro, setGiro] = useState(0)
  const [ampliado, setAmpliado] = useState(false)
  const [tira, setTira] = useState(() => {
    try {
      return localStorage.getItem('to-visor-tira') === 'visible'
    } catch {
      return false
    }
  })
  function alternarTira() {
    setTira((t) => {
      try {
        localStorage.setItem('to-visor-tira', t ? 'oculta' : 'visible')
      } catch {
        /* sin almacenamiento: solo dura esta sesión */
      }
      return !t
    })
  }

  useEffect(() => {
    setZoom(1)
    setGiro(0)
  }, [pagina])

  // Cada documento (PDF de origen) forma un grupo: empieza donde inicioDoc es verdadero.
  const grupos = paginas.reduce<PaginaVisor[][]>((acc, p) => {
    if (p.inicioDoc || !acc.length) acc.push([p])
    else acc[acc.length - 1].push(p)
    return acc
  }, [])

  const paginaActual = paginas.find((p) => p.pagina === pagina) ?? paginas[0] ?? null
  const indiceActual = Math.max(paginas.findIndex((p) => p.pagina === paginaActual?.pagina), 0)

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
        <div className="ml-auto flex shrink-0 items-center gap-1" style={{ color: 'var(--to-ink-muted)' }} title="Atajos de teclado: ← → cambian de ítem o paso; 1, 2 y 3 eligen la respuesta">
          <Tecla>←</Tecla><Tecla>→</Tecla>
          <span className="mx-1 h-4 w-px" style={{ background: 'var(--to-border)' }} aria-hidden="true" />
          <Tecla>1</Tecla><Tecla>2</Tecla><Tecla>3</Tecla>
        </div>
      </div>

      <div className="relative min-h-0 flex-1" style={{ background: 'var(--to-viewer)' }}>
        {contenido ? (
          contenido
        ) : paginaActual ? (
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
              {paginas.length > 1 && (
                <>
                  <BotonIcono etiqueta="Página anterior" onClick={() => onPagina(paginas[Math.max(indiceActual - 1, 0)].pagina)}>
                    <svg width="17" height="17" viewBox="0 0 24 24" {...ICONO}><path d="M15 5l-7 7 7 7" /></svg>
                  </BotonIcono>
                  <span className="min-w-12 text-center text-[12.5px] font-semibold text-white">{indiceActual + 1} / {paginas.length}</span>
                  <BotonIcono etiqueta="Página siguiente" onClick={() => onPagina(paginas[Math.min(indiceActual + 1, paginas.length - 1)].pagina)}>
                    <svg width="17" height="17" viewBox="0 0 24 24" {...ICONO}><path d="M9 5l7 7-7 7" /></svg>
                  </BotonIcono>
                  <span className="mx-1.5 h-[18px] w-px bg-white/30" />
                </>
              )}
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

      {!contenido && (
      <div className="flex items-center justify-between border-t px-4 py-1.5" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}>
        <span className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>
          {paginas.length} página{paginas.length === 1 ? '' : 's'} en {grupos.length} documento{grupos.length === 1 ? '' : 's'}
        </span>
        <button
          type="button"
          onClick={alternarTira}
          aria-expanded={tira}
          className="rounded-md border px-2.5 py-1 text-xs font-semibold"
          style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface-2)', color: 'var(--to-ink)' }}
        >
          {tira ? 'Ocultar miniaturas' : 'Mostrar miniaturas'}
        </button>
      </div>
      )}
      {!contenido && tira && (
      <div className="flex items-stretch gap-2.5 overflow-x-auto border-t px-4 py-2.5" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}>
        {grupos.map((g, n) => (
          <div
            key={n}
            className="flex shrink-0 flex-col gap-1.5 rounded-lg border px-2 py-1.5"
            style={{ borderColor: 'var(--to-border)', background: 'var(--to-surface-2)' }}
          >
            <div className="flex items-baseline gap-1.5 text-[11.5px] leading-none whitespace-nowrap" style={{ color: 'var(--to-ink)' }}>
              <span className="max-w-[190px] truncate font-semibold" title={g[0].etiqueta ?? undefined}>{g[0].etiqueta ?? 'Documento'}</span>
              <span style={{ color: 'var(--to-ink-muted)' }}>{g.length === 1 ? '1 pág.' : `${g.length} págs.`}</span>
            </div>
            <div className="flex gap-2">
              {g.map((p) => {
                const activa = paginaActual?.pagina === p.pagina
                return (
                  <button key={p.pagina} type="button" onClick={() => onPagina(p.pagina)} className="flex shrink-0 flex-col items-center gap-0.5" title={`Página ${p.pagina}`}>
                    <img
                      src={urlPagina(hash, p.pagina, 30)}
                      alt={`Miniatura página ${p.pagina}`}
                      loading="lazy"
                      className="block h-[64px] min-w-[46px] w-auto max-w-[90px] bg-white object-contain"
                      style={{ border: activa ? '2px solid var(--to-accent)' : '1px solid var(--to-border)', borderRadius: 3 }}
                    />
                    <span className="text-[10.5px] leading-tight" style={{ color: activa ? 'var(--to-accent)' : 'var(--to-ink-muted)', fontWeight: activa ? 700 : 400 }}>
                      Pág. {p.pagina}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
        {paginas.length === 0 && <span className="text-xs" style={{ color: 'var(--to-ink-muted)' }}>Sin páginas</span>}
      </div>
      )}

      {ampliado && paginaActual && (
        <ModalPaginas hash={hash} paginas={paginas.map((p) => p.pagina)} onCerrar={() => setAmpliado(false)} />
      )}
    </main>
  )
}
