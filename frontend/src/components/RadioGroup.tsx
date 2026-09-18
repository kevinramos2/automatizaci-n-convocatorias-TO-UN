export function RadioGroup({
  label,
  opciones,
  valor,
  onChange,
  name,
}: {
  label: string
  opciones: string[]
  valor: string
  onChange: (v: string) => void
  name: string
}) {
  return (
    <div className="mt-2">
      <p className="mb-1.5 text-[14.5px] font-medium" style={{ color: 'var(--to-ink)' }}>
        {label}
      </p>
      <div className="flex flex-wrap gap-4">
        {opciones.map((op) => (
          <label key={op} className="flex cursor-pointer items-center gap-1.5 text-[14px]" style={{ color: 'var(--to-ink)' }}>
            <input
              type="radio"
              name={name}
              value={op}
              checked={valor === op}
              onChange={() => onChange(op)}
              className="accent-[var(--to-accent)]"
            />
            {op}
          </label>
        ))}
      </div>
    </div>
  )
}
