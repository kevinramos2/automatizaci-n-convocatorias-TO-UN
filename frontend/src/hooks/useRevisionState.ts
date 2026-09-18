import { useEffect, useMemo, useState } from 'react'
import { previsualizarRevision } from '../api/client'
import type { Expediente, RevisionInput, RevisionPreview } from '../api/types'

export const OPCIONES_VALIDEZ = ['Según el sistema', 'Sí, válido', 'No es válido']
export const OPCIONES_FIRMA = ['Pendiente', 'Sí coincide', 'No coincide']
export const OPCIONES_RELACIONADO = ['PENDIENTE', 'SI', 'NO']

function sugeridoOPendiente(sugerido: string | null) {
  return sugerido === 'SI' || sugerido === 'NO' ? sugerido : 'PENDIENTE'
}

/** Estado inicial de cada control — restaurado desde expediente.revision_humana

 * si ya existe (persistencia entre buckets), si no cae a la sugerencia de la
 * IA para "relacionado" o al valor por defecto del sistema. Reemplaza el
 * `index=` que en Streamlit había que calcular a mano por cada st.radio.
 */
function estadoInicial(expediente: Expediente): RevisionInput {
  const g = expediente.revision_humana

  const decisionesLaboral: Record<string, string> = {}
  expediente.laborales.forEach((l, i) => {
    decisionesLaboral[i] = g?.decisiones_relacionado_laboral?.[i] ?? sugeridoOPendiente(l.relacionado_sugerido)
  })

  const decisionesEstudio: Record<string, string> = {}
  expediente.estudios.forEach((e, i) => {
    if (expediente.indices_academicos.includes(i)) return
    decisionesEstudio[i] = g?.decisiones_relacionado_estudio?.[i] ?? sugeridoOPendiente(e.relacionado_sugerido)
  })

  return {
    revisado_por: g?.revisado_por ?? '',
    firma_verificada: g?.firma_verificada ?? 'Pendiente',
    overrides_academicos: g?.overrides_academicos ?? {},
    decisiones_relacionado_estudio: decisionesEstudio,
    decisiones_relacionado_laboral: decisionesLaboral,
    alturas_override: g?.alturas_override ?? 'Según el sistema',
    medica_override: g?.medica_override ?? 'Según el sistema',
  }
}

export function useRevisionState(expediente: Expediente) {
  const [estado, setEstado] = useState<RevisionInput>(() => estadoInicial(expediente))
  const [preview, setPreview] = useState<RevisionPreview | null>(null)
  const [cargandoPreview, setCargandoPreview] = useState(false)

  const claveEstado = useMemo(() => JSON.stringify(estado), [estado])

  useEffect(() => {
    let vigente = true
    setCargandoPreview(true)
    const temporizador = setTimeout(() => {
      previsualizarRevision(expediente._hash, estado)
        .then((r) => {
          if (vigente) setPreview(r)
        })
        .finally(() => {
          if (vigente) setCargandoPreview(false)
        })
    }, 300)
    return () => {
      vigente = false
      clearTimeout(temporizador)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claveEstado, expediente._hash])

  function set<K extends keyof RevisionInput>(campo: K, valor: RevisionInput[K]) {
    setEstado((prev) => ({ ...prev, [campo]: valor }))
  }

  function setEnMapa(campo: 'overrides_academicos' | 'decisiones_relacionado_estudio' | 'decisiones_relacionado_laboral', indice: number, valor: string) {
    setEstado((prev) => ({ ...prev, [campo]: { ...prev[campo], [String(indice)]: valor } }))
  }

  return { estado, set, setEnMapa, preview, cargandoPreview }
}
