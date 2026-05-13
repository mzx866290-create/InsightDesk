import { useCallback, useState } from 'react'

import { deleteCloudModelApiKey, saveCloudModelApiKey } from '../../api/client'
import type { CloudModelProfile } from '../../stores/chatStore'
import type { CloudModelProfileInput } from '../../stores/chatStoreModel'
import {
  buildCloudModelProfileClearedApiKeyInput,
  buildCloudModelProfileInput,
  findCloudModelProfileById,
  normalizedCloudProfileApiKey,
  type CloudModelProfileForm,
} from './cloudModelProfilesModel'

interface CloudModelProfileActionsOptions {
  profiles: CloudModelProfile[]
  form: CloudModelProfileForm
  editingProfileId: string | null
  canSave: boolean
  saveProfile: (profile: CloudModelProfileInput) => void
  deleteProfile: (profileId: string) => void
  resetForm: () => void
  updateForm: (patch: Partial<CloudModelProfileForm>) => void
  setSaveError: (saveError: string | null) => void
}

interface CloudModelProfileActions {
  saving: boolean
  apiKeyDeletingId: string | null
  saveCurrentProfile: () => Promise<void>
  deleteProfileWithKey: (profile: CloudModelProfile) => Promise<void>
  clearProfileApiKey: (profile: CloudModelProfile) => Promise<void>
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

export function useCloudModelProfileActions({
  profiles,
  form,
  editingProfileId,
  canSave,
  saveProfile,
  deleteProfile,
  resetForm,
  updateForm,
  setSaveError,
}: CloudModelProfileActionsOptions): CloudModelProfileActions {
  const [saving, setSaving] = useState(false)
  const [apiKeyDeletingId, setApiKeyDeletingId] = useState<string | null>(null)

  const saveCurrentProfile = useCallback(async () => {
    if (!canSave) {
      return
    }

    setSaving(true)
    setSaveError(null)
    try {
      const existingProfile = findCloudModelProfileById(profiles, editingProfileId)

      let apiKeyRef = existingProfile?.modelConfig.api_key_ref ?? ''
      const normalizedApiKey = normalizedCloudProfileApiKey(form)
      if (normalizedApiKey) {
        const result = await saveCloudModelApiKey({
          api_key: normalizedApiKey,
          api_key_ref: apiKeyRef || undefined,
        })
        apiKeyRef = result.api_key_ref
      }

      saveProfile(buildCloudModelProfileInput(form, editingProfileId, apiKeyRef))
      resetForm()
    } catch (error) {
      setSaveError(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }, [
    canSave,
    editingProfileId,
    form,
    profiles,
    resetForm,
    saveProfile,
    setSaveError,
  ])

  const deleteProfileWithKey = useCallback(async (profile: CloudModelProfile) => {
    setSaveError(null)
    try {
      if (profile.modelConfig.api_key_ref) {
        await deleteCloudModelApiKey(profile.modelConfig.api_key_ref)
      }
      if (editingProfileId === profile.id) {
        resetForm()
      }
      deleteProfile(profile.id)
    } catch (error) {
      setSaveError(errorMessage(error))
    }
  }, [
    deleteProfile,
    editingProfileId,
    resetForm,
    setSaveError,
  ])

  const clearProfileApiKey = useCallback(async (profile: CloudModelProfile) => {
    const apiKeyRef = profile.modelConfig.api_key_ref?.trim()
    if (!apiKeyRef) {
      return
    }

    setApiKeyDeletingId(profile.id)
    setSaveError(null)
    try {
      await deleteCloudModelApiKey(apiKeyRef)
      saveProfile(buildCloudModelProfileClearedApiKeyInput(profile))
      if (editingProfileId === profile.id) {
        updateForm({ apiKey: '' })
      }
    } catch (error) {
      setSaveError(errorMessage(error))
    } finally {
      setApiKeyDeletingId(null)
    }
  }, [
    editingProfileId,
    saveProfile,
    setSaveError,
    updateForm,
  ])

  return {
    saving,
    apiKeyDeletingId,
    saveCurrentProfile,
    deleteProfileWithKey,
    clearProfileApiKey,
  }
}
