import { useMemo } from 'react'

import { useChatStore } from '../../stores/chatStore'
import type { CloudModelProfileFormPanelProps } from './CloudModelProfileFormPanel'
import type { CloudModelProfileListPanelProps } from './CloudModelProfileListPanel'
import { useCloudModelProfileActions } from './useCloudModelProfileActions'
import { useCloudModelProfileFormState } from './useCloudModelProfileFormState'

type CloudModelFormControllerProps = Omit<CloudModelProfileFormPanelProps, 't'>
type CloudModelListControllerProps = Omit<CloudModelProfileListPanelProps, 't'>

interface CloudModelProfilesController {
  formProps: CloudModelFormControllerProps
  listProps: CloudModelListControllerProps
  resetForm: () => void
}

export function useCloudModelProfilesController(): CloudModelProfilesController {
  const {
    cloudModelProfiles,
    saveCloudModelProfile,
    deleteCloudModelProfile,
  } = useChatStore()

  const {
    form: cloudProfileForm,
    editingProfile: editingCloudProfile,
    editingProfileId: editingCloudProfileId,
    canSave: canSaveCloudProfile,
    saveError: cloudProfileSaveError,
    setSaveError: setCloudProfileSaveError,
    updateForm: updateCloudProfileForm,
    resetForm: resetCloudProfileForm,
    editProfile: handleEditCloudProfile,
  } = useCloudModelProfileFormState(cloudModelProfiles)

  const {
    saving: cloudProfileSaving,
    apiKeyDeletingId: cloudProfileApiKeyDeletingId,
    saveCurrentProfile: handleSaveCloudProfile,
    deleteProfileWithKey: handleDeleteCloudProfile,
    clearProfileApiKey: handleClearCloudProfileApiKey,
  } = useCloudModelProfileActions({
    profiles: cloudModelProfiles,
    form: cloudProfileForm,
    editingProfileId: editingCloudProfileId,
    canSave: canSaveCloudProfile,
    saveProfile: saveCloudModelProfile,
    deleteProfile: deleteCloudModelProfile,
    resetForm: resetCloudProfileForm,
    updateForm: updateCloudProfileForm,
    setSaveError: setCloudProfileSaveError,
  })

  const formProps = useMemo<CloudModelFormControllerProps>(
    () => ({
      form: cloudProfileForm,
      editingProfile: editingCloudProfile,
      editingProfileId: editingCloudProfileId,
      canSave: canSaveCloudProfile,
      saving: cloudProfileSaving,
      apiKeyDeletingId: cloudProfileApiKeyDeletingId,
      saveError: cloudProfileSaveError,
      onChange: updateCloudProfileForm,
      onSave: () => {
        void handleSaveCloudProfile()
      },
      onReset: resetCloudProfileForm,
      onClearApiKey: (profile) => {
        void handleClearCloudProfileApiKey(profile)
      },
    }),
    [
      canSaveCloudProfile,
      cloudProfileApiKeyDeletingId,
      cloudProfileForm,
      cloudProfileSaveError,
      cloudProfileSaving,
      editingCloudProfile,
      editingCloudProfileId,
      handleClearCloudProfileApiKey,
      handleSaveCloudProfile,
      resetCloudProfileForm,
      updateCloudProfileForm,
    ],
  )

  const listProps = useMemo<CloudModelListControllerProps>(
    () => ({
      profiles: cloudModelProfiles,
      saving: cloudProfileSaving,
      apiKeyDeletingId: cloudProfileApiKeyDeletingId,
      onEdit: handleEditCloudProfile,
      onDelete: (profile) => {
        void handleDeleteCloudProfile(profile)
      },
      onClearApiKey: (profile) => {
        void handleClearCloudProfileApiKey(profile)
      },
    }),
    [
      cloudModelProfiles,
      cloudProfileApiKeyDeletingId,
      cloudProfileSaving,
      handleClearCloudProfileApiKey,
      handleDeleteCloudProfile,
      handleEditCloudProfile,
    ],
  )

  return {
    formProps,
    listProps,
    resetForm: resetCloudProfileForm,
  }
}
