import { useCallback, useMemo, useState } from 'react'

import type { CloudModelProfile } from '../../stores/chatStore'
import {
  canSaveCloudModelProfileForm,
  cloudModelProfileToForm,
  defaultCloudModelProfileForm,
  findCloudModelProfileById,
  type CloudModelProfileForm,
} from './cloudModelProfilesModel'

interface CloudModelProfileFormState {
  form: CloudModelProfileForm
  editingProfile: CloudModelProfile | null
  editingProfileId: string | null
  canSave: boolean
  saveError: string | null
  setSaveError: (saveError: string | null) => void
  updateForm: (patch: Partial<CloudModelProfileForm>) => void
  resetForm: () => void
  editProfile: (profile: CloudModelProfile) => void
}

export function useCloudModelProfileFormState(
  profiles: CloudModelProfile[],
): CloudModelProfileFormState {
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null)
  const [form, setForm] = useState<CloudModelProfileForm>(() => defaultCloudModelProfileForm())
  const [saveError, setSaveError] = useState<string | null>(null)

  const editingProfile = useMemo(
    () => findCloudModelProfileById(profiles, editingProfileId),
    [profiles, editingProfileId],
  )

  const canSave = useMemo(
    () => canSaveCloudModelProfileForm(form),
    [form],
  )

  const updateForm = useCallback((patch: Partial<CloudModelProfileForm>) => {
    setForm((current) => ({ ...current, ...patch }))
  }, [])

  const resetForm = useCallback(() => {
    setEditingProfileId(null)
    setForm(defaultCloudModelProfileForm())
    setSaveError(null)
  }, [])

  const editProfile = useCallback((profile: CloudModelProfile) => {
    setEditingProfileId(profile.id)
    setForm(cloudModelProfileToForm(profile))
    setSaveError(null)
  }, [])

  return {
    form,
    editingProfile,
    editingProfileId,
    canSave,
    saveError,
    setSaveError,
    updateForm,
    resetForm,
    editProfile,
  }
}
