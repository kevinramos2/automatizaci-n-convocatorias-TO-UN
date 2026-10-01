import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  guardarRevision,
  listarConvocatorias,
  listarExpedientes,
  obtenerConfig,
  obtenerExpediente,
  obtenerHojaSimulada,
  procesarExpediente,
} from '../api/client'
import type { RevisionInput } from '../api/types'

export function useListaExpedientes() {
  return useQuery({ queryKey: ['expedientes'], queryFn: listarExpedientes })
}

export function useExpediente(hash: string | null) {
  return useQuery({
    queryKey: ['expediente', hash],
    queryFn: () => obtenerExpediente(hash as string),
    enabled: !!hash,
  })
}

export function useConvocatorias() {
  return useQuery({ queryKey: ['convocatorias'], queryFn: listarConvocatorias })
}

export function useConfig() {
  return useQuery({ queryKey: ['config'], queryFn: obtenerConfig })
}

// Solo se usa cuando config.demo_mode es true (ver App.tsx) — la lista de
// "filas guardadas" en el demo, como reemplazo de abrir el Google Sheet real.
export function useHojaSimulada(habilitada: boolean) {
  return useQuery({ queryKey: ['hoja-simulada'], queryFn: obtenerHojaSimulada, enabled: habilitada })
}

export function useGuardarRevision(hash: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (datos: RevisionInput) => guardarRevision(hash as string, datos),
    // Se devuelve la promesa para que la mutación no termine hasta que la lista
    // (buckets Pendientes/Admitidos/No admitidos) y el expediente ya estén
    // refrescados — mismo espíritu del st.rerun() de Streamlit tras guardar.
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ['expedientes'] }),
        qc.invalidateQueries({ queryKey: ['expediente', hash] }),
        qc.invalidateQueries({ queryKey: ['hoja-simulada'] }),
      ]),
  })
}

export function useProcesarExpediente() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ convocatoria, archivo }: { convocatoria: string; archivo: File }) =>
      procesarExpediente(convocatoria, archivo),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['expedientes'] })
    },
  })
}
