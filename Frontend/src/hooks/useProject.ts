import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { projectsApi } from '@/api'
import { useStore } from '@/store'

export function useProject(projectId: string | undefined) {
  const setProject = useStore((s) => s.setProject)

  const query = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.get(projectId!),
    enabled: !!projectId,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  })

  useEffect(() => {
    if (query.data) setProject(query.data)
  }, [query.data, setProject])

  return query
}
