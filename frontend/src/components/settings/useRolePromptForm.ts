import { useCallback, useState } from 'react'

import type { SystemPrompt } from '../../api/client'
import { usePromptDashboardTemplateForm } from './usePromptDashboardTemplateForm'

interface RolePromptTemplateInput {
  name: string
  content: string
}

interface RolePromptFormSnapshot {
  editingPrompt: SystemPrompt | null
  isCreating: boolean
  name: string
  content: string
  vectorStoreId: string
}

const EMPTY_FORM_SNAPSHOT: RolePromptFormSnapshot = {
  editingPrompt: null,
  isCreating: false,
  name: '',
  content: '',
  vectorStoreId: '',
}

function createFormSnapshot(template?: RolePromptTemplateInput): RolePromptFormSnapshot {
  return {
    editingPrompt: null,
    isCreating: true,
    name: template?.name ?? '',
    content: template?.content ?? '',
    vectorStoreId: '',
  }
}

function editFormSnapshot(prompt: SystemPrompt): RolePromptFormSnapshot {
  return {
    editingPrompt: prompt,
    isCreating: false,
    name: prompt.name,
    content: prompt.content,
    vectorStoreId: prompt.vector_store_id ?? '',
  }
}

export function useRolePromptForm() {
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [promptName, setPromptName] = useState('')
  const [promptContent, setPromptContent] = useState('')
  const [promptVectorStoreId, setPromptVectorStoreId] = useState('')
  const dashboardTemplateForm = usePromptDashboardTemplateForm()

  const applySnapshot = useCallback((snapshot: RolePromptFormSnapshot) => {
    setEditingPrompt(snapshot.editingPrompt)
    setIsCreating(snapshot.isCreating)
    setPromptName(snapshot.name)
    setPromptContent(snapshot.content)
    setPromptVectorStoreId(snapshot.vectorStoreId)
  }, [])

  const cancelEdit = useCallback(() => {
    applySnapshot(EMPTY_FORM_SNAPSHOT)
    dashboardTemplateForm.reset()
  }, [applySnapshot, dashboardTemplateForm])

  const startEdit = useCallback((prompt: SystemPrompt) => {
    applySnapshot(editFormSnapshot(prompt))
    dashboardTemplateForm.loadFromTemplate(prompt.dashboard_template)
  }, [applySnapshot, dashboardTemplateForm])

  const startCreate = useCallback((template?: RolePromptTemplateInput) => {
    applySnapshot(createFormSnapshot(template))
    dashboardTemplateForm.reset()
  }, [applySnapshot, dashboardTemplateForm])

  return {
    editingPrompt,
    isCreating,
    promptName,
    promptContent,
    promptVectorStoreId,
    dashboardFieldsProps: dashboardTemplateForm.fieldsProps,
    buildDashboardTemplatePayload: dashboardTemplateForm.buildPayload,
    cancelEdit,
    startEdit,
    startCreate,
    setPromptName,
    setPromptContent,
    setPromptVectorStoreId,
  }
}
