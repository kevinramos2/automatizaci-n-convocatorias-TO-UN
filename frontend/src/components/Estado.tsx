// Mismo mapeo de colores que app_revision.py:_badge_html/_pill_html/_ETIQUETA_ESTADO.

export const ETIQUETA_ESTADO: Record<string, string> = {
  cumple: 'CUMPLE',
  requiere_revision_manual: 'REQUIERE REVISIÓN',
  no_cumple: 'NO CUMPLE',
}

const COLORES: Record<string, { color: string; bg: string; border: string }> = {
  cumple: { color: 'var(--to-good)', bg: 'var(--to-good-bg)', border: 'var(--to-good-border)' },
  requiere_revision_manual: { color: 'var(--to-warn)', bg: 'var(--to-warn-bg)', border: 'var(--to-warn-border)' },
  no_cumple: { color: 'var(--to-bad)', bg: 'var(--to-bad-bg)', border: 'var(--to-bad-border)' },
}

function coloresDe(estado: string) {
  return COLORES[estado] ?? { color: 'var(--to-ink-muted)', bg: 'var(--to-surface-2)', border: 'var(--to-border)' }
}

export function EstadoBadge({ estado, texto }: { estado: string; texto: string }) {
  const c = coloresDe(estado)
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border px-4.5 py-2.5 text-[13px] font-bold tracking-wide whitespace-nowrap"
      style={{ color: c.color, background: c.bg, borderColor: c.border }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: 'currentColor' }} />
      {texto}
    </span>
  )
}

export function EstadoPill({ estado }: { estado: string }) {
  const c = coloresDe(estado)
  const etiqueta = ETIQUETA_ESTADO[estado] ?? estado.toUpperCase()
  return (
    <span
      className="rounded-full px-2.5 py-[3px] text-[10.5px] font-bold tracking-wide whitespace-nowrap"
      style={{ color: c.color, background: c.bg }}
    >
      {etiqueta}
    </span>
  )
}

export function AiBox({ label, valor, motivo }: { label: string; valor: string; motivo?: string | null }) {
  return (
    <div
      className="my-2 rounded-[9px] border px-3.5 py-2.5 text-[13px]"
      style={{ background: 'var(--to-accent-tint)', borderColor: 'var(--to-accent-tint-border)', color: 'var(--to-ink)' }}
    >
      <span
        className="mb-0.5 block text-[10.5px] font-bold tracking-wide uppercase"
        style={{ color: 'var(--to-accent)' }}
      >
        {label}
      </span>
      <strong>{valor}</strong>
      {motivo ? <em className="not-italic text-inherit"> — {motivo}</em> : null}
    </div>
  )
}
