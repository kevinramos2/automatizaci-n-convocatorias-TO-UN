import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  guardarRevision,
  listarConvocatorias,
  listarExpedientes,
  obtenerConfig,
  obtenerExpediente,
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

export function useGuardarRevision(hash: string | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (datos: RevisionInput) => guardarRevision(hash as string, datos),
    onSuccess: () => {
      // Refresca la lista (buckets Pendientes/Admitidos/No admitidos) y el
      // expediente actual — mismo espíritu del st.rerun() de Streamlit tras guardar.
      qc.invalidateQueries({ queryKey: ['expedientes'] })
      qc.invalidateQueries({ queryKey: ['expediente', hash] })
    },
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
