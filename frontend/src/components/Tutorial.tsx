import type { ReactNode } from 'react'
import { Tecla } from './OpcionesGrandes'

const PASOS_REVISION = [
  ['Formulario y cédula', 'Confirma que el aspirante aportó cada uno.'],
  ['Información académica', 'Valida el acta de grado o el diploma del colegio.'],
  ['Educación relacionada', 'Cursos y técnicos: ¿se relacionan con el cargo?'],
  ['Experiencia laboral', 'Cada constancia: ¿es experiencia relacionada?'],
  ['Certificado de alturas', 'Verifícalo en el Ministerio del Trabajo y respóndelo.'],
  ['Evaluación médica', 'Confirma que la evaluación ocupacional es válida.'],
  ['Resumen', 'Revisa todo, escribe tu nombre y guarda.'],
]

function Tarjeta({ numero, titulo, children }: { numero: number; titulo: string; children: ReactNode }) {
  return (
    <section className="flex gap-3.5 rounded-xl border p-4" style={{ background: 'var(--to-surface)', borderColor: 'var(--to-border)' }}>
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold"
        style={{ background: 'var(--to-accent)', color: 'var(--to-bg)' }}
        aria-hidden="true"
      >
        {numero}
      </div>
      <div className="min-w-0 flex-1">
        <h3 className="text-[15px] font-bold" style={{ color: 'var(--to-ink)' }}>{titulo}</h3>
        <div className="mt-1 flex flex-col gap-1.5 text-[13.5px] leading-snug" style={{ color: 'var(--to-ink-muted)' }}>{children}</div>
      </div>
    </section>
  )
}

// Pantalla de bienvenida: se muestra mientras no hay ningún aspirante seleccionado.
export function Tutorial() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div>
        <h2 className="text-[24px] leading-tight font-bold" style={{ color: 'var(--to-ink)' }}>Cómo revisar un aspirante</h2>
        <p className="mt-1 text-[14px]" style={{ color: 'var(--to-ink-muted)' }}>
          El sistema lee los documentos y sugiere un resultado, pero la decisión es siempre tuya. Elige un aspirante en la lista de la izquierda para empezar.
        </p>
      </div>

      <Tarjeta numero={1} titulo="Elige a quién revisar">
        <p>
          La lista tiene tres pestañas: <strong style={{ color: 'var(--to-ink)' }}>Pendientes</strong>, <strong style={{ color: 'var(--to-ink)' }}>Admitidos</strong> y{' '}
          <strong style={{ color: 'var(--to-ink)' }}>No admitidos</strong>. Puedes buscar por nombre o cédula. Los aspirantes ya guardados se pueden abrir de nuevo y conservan tus respuestas.
        </p>
        <p>Con «Subir expediente nuevo» procesas un PDF que todavía no está en la lista.</p>
      </Tarjeta>

      <Tarjeta numero={2} titulo="Recorre los 7 pasos">
        <ol className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
          {PASOS_REVISION.map(([t, d], i) => (
            <li key={t} className="flex gap-2">
              <span className="font-mono-to w-4 shrink-0 text-right text-xs leading-[1.5]" style={{ color: 'var(--to-accent)' }}>{i + 1}</span>
              <span>
                <strong style={{ color: 'var(--to-ink)' }}>{t}.</strong> {d}
              </span>
            </li>
          ))}
        </ol>
        <p>Arriba a la derecha ves en qué paso vas; puedes saltar a cualquiera tocando su número.</p>
      </Tarjeta>

      <Tarjeta numero={3} titulo="Mira el documento y responde">
        <p>
          El visor del centro salta solo al documento que estás revisando. Toca la imagen para verla en pantalla completa, y usa los botones de acercar, rotar y pasar de página.
          Las miniaturas se pueden mostrar u ocultar.
        </p>
        <p>
          Responde con los botones grandes o con el teclado:
        </p>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5" style={{ color: 'var(--to-ink)' }}>
          <span className="inline-flex items-center gap-1.5"><Tecla>1</Tecla> Sí</span>
          <span className="inline-flex items-center gap-1.5"><Tecla>2</Tecla> No</span>
          <span className="inline-flex items-center gap-1.5"><Tecla>3</Tecla> Pendiente / según el sistema</span>
          <span className="inline-flex items-center gap-1.5"><Tecla>←</Tecla><Tecla>→</Tecla> Anterior / siguiente</span>
        </div>
      </Tarjeta>

      <Tarjeta numero={4} titulo="Certificado de alturas">
        <p>
          En ese paso hay un botón grande que abre la consulta del Ministerio del Trabajo con la cédula del aspirante a la vista. Verifica allí el certificado antes de responder.
        </p>
      </Tarjeta>

      <Tarjeta numero={5} titulo="Guarda la revisión">
        <p>
          En el paso 7 ves el resultado final con tus respuestas. Escribe tu nombre (queda en la auditoría) y guarda: la revisión se escribe en Google Sheets y vuelves a esta pantalla.
          El botón «Abrir Google Sheet» de la barra superior lleva a la hoja en cualquier momento.
        </p>
        <p>Mientras haya ítems sin confirmar el botón de guardar queda bloqueado; el aspirante pasa a «Admitidos» o «No admitidos» cuando guardas.</p>
      </Tarjeta>
    </div>
  )
}
