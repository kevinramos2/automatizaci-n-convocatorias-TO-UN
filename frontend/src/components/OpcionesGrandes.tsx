export type Tono = 'good' | 'bad' | 'neutral'

export interface Opcion {
  valor: string
  etiqueta?: string
  tono: Tono
}

const TONOS: Record<Tono, { color: string; bg: string; borde: string }> = {
  good: { color: 'var(--to-good)', bg: 'var(--to-good-bg)', borde: 'var(--to-good)' },
  bad: { color: 'var(--to-bad)', bg: 'var(--to-bad-bg)', borde: 'var(--to-bad)' },
  neutral: { color: 'var(--to-ink)', bg: 'var(--to-surface-2)', borde: 'var(--to-ink-muted)' },
}

export function Tecla({ children }: { children: string }) {
  return (
    <span
      className="font-mono-to inline-flex h-[22px] min-w-[22px] items-center justify-center rounded-[5px] border border-b-2 px-1.5 text-xs"
      style={{ borderColor: 'var(--to-border)', color: 'var(--to-ink-muted)', background: 'var(--to-surface-2)' }}
    >
      {children}
    </span>
  )
}

// Opciones como tarjetas grandes (una por respuesta posible) con su atajo de teclado.
export function OpcionesGrandes({
  name,
  opciones,
  valor,
  onChange,
}: {
  name: string
  opciones: Opcion[]
  valor: string
  onChange: (v: string) => void
}) {
  return (
    <div role="radiogroup" className="flex gap-2.5">
      {opciones.map((o, i) => {
        const activa = valor === o.valor
        const t = TONOS[o.tono]
        return (
          <label
            key={o.valor}
            className="relative flex flex-1 basis-0 cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 px-1.5 py-3.5 text-center focus-within:ring-2 focus-within:ring-[var(--to-accent)]"
            style={{
              background: activa ? t.bg : 'var(--to-surface)',
              borderColor: activa ? t.borde : 'var(--to-border)',
              color: activa ? t.color : 'var(--to-ink)',
            }}
          >
            <input
              type="radio"
              name={name}
              value={o.valor}
              checked={activa}
              onChange={() => onChange(o.valor)}
              className="sr-only"
            />
            <span className="text-[15px] leading-tight font-bold">{o.etiqueta ?? o.valor}</span>
            <Tecla>{String(i + 1)}</Tecla>
          </label>
        )
      })}
    </div>
  )
}
