import { urlPagina } from '../api/client'
import { EstadoPill } from './Estado'

export interface SeccionGaleria {
  paso: number
  titulo: string
  estado: string
  detalle: string
  paginas: number[]
}

const MAX_MINIATURAS = 4

// Reemplaza al visor en el resumen: una tarjeta por sección con sus documentos; al tocarla
// se vuelve al paso correspondiente para editarlo.
export function GaleriaResumen({ hash, secciones, onIr }: { hash: string; secciones: SeccionGaleria[]; onIr: (paso: number) => void }) {
  return (
    <div className="absolute inset-0 overflow-auto p-5">
      <div className="grid gap-3.5 [grid-template-columns:repeat(auto-fill,minmax(250px,1fr))]">
        {secciones.map((s) => (
          <button
            key={s.paso}
            type="button"
            onClick={() => onIr(s.paso)}
            className="flex flex-col gap-2.5 rounded-xl border p-3.5 text-left hover:shadow-md focus-visible:ring-2 focus-visible:ring-[var(--to-accent)] focus-visible:outline-none"
            style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}
            aria-label={`${s.titulo}: editar`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-[14px] font-bold" style={{ color: 'var(--to-ink)' }}>{s.titulo}</span>
              <EstadoPill estado={s.estado} />
            </div>
            {s.paginas.length ? (
              <div className="flex items-end gap-1.5">
                {s.paginas.slice(0, MAX_MINIATURAS).map((p) => (
                  <img
                    key={p}
                    src={urlPagina(hash, p, 40)}
                    alt={`Página ${p}`}
                    loading="lazy"
                    className="block h-[86px] w-auto max-w-[80px] min-w-[56px] bg-white object-contain"
                    style={{ border: '1px solid var(--to-border)', borderRadius: 3 }}
                  />
                ))}
                {s.paginas.length > MAX_MINIATURAS && (
                  <span className="pb-1 text-xs font-semibold" style={{ color: 'var(--to-ink-muted)' }}>+{s.paginas.length - MAX_MINIATURAS}</span>
                )}
              </div>
            ) : (
              <div className="flex h-[86px] items-center rounded-md border border-dashed px-3 text-xs" style={{ borderColor: 'var(--to-border)', color: 'var(--to-ink-muted)' }}>
                Sin documento aportado
              </div>
            )}
            <div className="flex items-end justify-between gap-2">
              <span className="line-clamp-2 text-xs leading-snug" style={{ color: 'var(--to-ink-muted)' }}>{s.detalle}</span>
              <span className="shrink-0 text-xs font-semibold underline" style={{ color: 'var(--to-accent)' }}>Editar</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
