import { useCallback, useState, type Dispatch, type SetStateAction } from 'react'

import {
  getKnowledgeBases,
  getSystemPrompts,
  type KnowledgeBase,
  type SystemPrompt,
} from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'

interface UseRolePromptLoadersParams {
  setAdminAccessError: (message: string | null) => void
}

interface LoadAdminResourceOptions<T> {
  request: () => Promise<T[]>
  setItems: Dispatch<SetStateAction<T[]>>
  setLoading: Dispatch<SetStateAction<boolean>>
  setAdminAccessError: (message: string | null) => void
}

async function loadAdminResource<T>({
  request,
  setItems,
  setLoading,
  setAdminAccessError,
}: LoadAdminResourceOptions<T>) {
  setLoading(true)
  try {
    const list = await request()
    setItems(list)
    setAdminAccessError(null)
  } catch (error) {
    if (isAdminAccessError(error)) {
      setAdminAccessError((error as Error).message)
    }
  } finally {
    setLoading(false)
  }
}

export function useRolePromptLoaders({
  setAdminAccessError,
}: UseRolePromptLoadersParams) {
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [loadingPrompts, setLoadingPrompts] = useState(false)
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [loadingKnowledgeBases, setLoadingKnowledgeBases] = useState(false)

  const loadPrompts = useCallback(async () => {
    await loadAdminResource({
      request: getSystemPrompts,
      setItems: setPrompts,
      setLoading: setLoadingPrompts,
      setAdminAccessError,
    })
  }, [setAdminAccessError])

  const loadKnowledgeBases = useCallback(async () => {
    await loadAdminResource({
      request: getKnowledgeBases,
      setItems: setKnowledgeBases,
      setLoading: setLoadingKnowledgeBases,
      setAdminAccessError,
    })
  }, [setAdminAccessError])

  return {
    prompts,
    loadingPrompts,
    knowledgeBases,
    loadingKnowledgeBases,
    loadPrompts,
    loadKnowledgeBases,
  }
}
