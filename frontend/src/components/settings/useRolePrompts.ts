import { useCallback, useState } from 'react'
import {
  activateSystemPrompt,
  createSystemPromptWithKB,
  deleteSystemPrompt,
  updateSystemPromptWithKB,
} from '../../api/client'
import { useRolePromptActivationState } from './useRolePromptActivationState'
import { useRolePromptForm } from './useRolePromptForm'
import { useRolePromptLoaders } from './useRolePromptLoaders'

export interface RolePromptTemplate {
  name: string
  content: string
}

interface UseRolePromptsParams {
  setAdminAccessError: (message: string | null) => void
  setActivePromptId: (id: string | null) => void
}

export function useRolePrompts({
  setAdminAccessError,
  setActivePromptId,
}: UseRolePromptsParams) {
  const {
    prompts,
    loadingPrompts,
    knowledgeBases,
    loadingKnowledgeBases,
    loadPrompts,
    loadKnowledgeBases,
  } = useRolePromptLoaders({ setAdminAccessError })
  const {
    editingPrompt,
    isCreating,
    promptName,
    promptContent,
    promptVectorStoreId,
    dashboardFieldsProps,
    buildDashboardTemplatePayload,
    cancelEdit,
    startEdit,
    startCreate,
    setPromptName,
    setPromptContent,
    setPromptVectorStoreId,
  } = useRolePromptForm()
  const {
    activatingId,
    activateStatus,
    setActivatingId,
    showActivateStatus,
  } = useRolePromptActivationState()
  const [promptSaving, setPromptSaving] = useState(false)
  const [deletingPromptId, setDeletingPromptId] = useState<string | null>(null)

  const savePrompt = useCallback(async () => {
    const trimmedName = promptName.trim()
    const trimmedContent = promptContent.trim()
    if (!trimmedName || !trimmedContent) return

    setPromptSaving(true)
    try {
      const dashboardTemplate = buildDashboardTemplatePayload()
      if (isCreating) {
        await createSystemPromptWithKB(
          trimmedName,
          trimmedContent,
          promptVectorStoreId || undefined,
          dashboardTemplate,
        )
      } else if (editingPrompt) {
        await updateSystemPromptWithKB(
          editingPrompt.id,
          trimmedName,
          trimmedContent,
          promptVectorStoreId || undefined,
          dashboardTemplate,
        )
      }
      await loadPrompts()
      cancelEdit()
    } finally {
      setPromptSaving(false)
    }
  }, [
    buildDashboardTemplatePayload,
    cancelEdit,
    editingPrompt,
    isCreating,
    loadPrompts,
    promptContent,
    promptName,
    promptVectorStoreId,
  ])

  const activatePrompt = useCallback(async (id: string) => {
    setActivatingId(id)
    try {
      const result = await activateSystemPrompt(id)
      setActivePromptId(id)
      if (result.kb_status) {
        showActivateStatus(id, result.kb_status)
      }
      await loadPrompts()
    } finally {
      setActivatingId(null)
    }
  }, [loadPrompts, setActivePromptId, setActivatingId, showActivateStatus])

  const deletePrompt = useCallback(async (id: string) => {
    setDeletingPromptId(id)
    try {
      await deleteSystemPrompt(id)
      await loadPrompts()
    } finally {
      setDeletingPromptId(null)
    }
  }, [loadPrompts])

  return {
    prompts,
    loadingPrompts,
    editingPrompt,
    isCreating,
    promptName,
    promptContent,
    promptVectorStoreId,
    dashboardFieldsProps,
    promptSaving,
    activatingId,
    activateStatus,
    deletingPromptId,
    knowledgeBases,
    loadingKnowledgeBases,
    loadPrompts,
    loadKnowledgeBases,
    startCreate,
    startEdit,
    cancelEdit,
    savePrompt,
    activatePrompt,
    deletePrompt,
    setPromptName,
    setPromptContent,
    setPromptVectorStoreId,
  }
}

export type RolePromptsController = ReturnType<typeof useRolePrompts>
