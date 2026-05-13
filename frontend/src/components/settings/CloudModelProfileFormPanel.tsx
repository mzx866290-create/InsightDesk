import React from 'react'

import type { TranslationKey } from '../../i18n'
import type { CloudModelProfile } from '../../stores/chatStore'
import { CloudModelProfileApiKeyField } from './CloudModelProfileApiKeyField'
import { CloudModelProfileFormActions } from './CloudModelProfileFormActions'
import { CloudModelProfileTemperatureField } from './CloudModelProfileTemperatureField'
import { CloudModelProfileTextField } from './CloudModelProfileTextField'
import type { CloudModelProfileForm } from './cloudModelProfilesModel'

export interface CloudModelProfileFormPanelProps {
  form: CloudModelProfileForm
  editingProfile: CloudModelProfile | null
  editingProfileId: string | null
  canSave: boolean
  saving: boolean
  apiKeyDeletingId: string | null
  saveError: string | null
  t: (key: TranslationKey) => string
  onChange: (patch: Partial<CloudModelProfileForm>) => void
  onSave: () => void
  onReset: () => void
  onClearApiKey: (profile: CloudModelProfile) => void
}

export const CloudModelProfileFormPanel: React.FC<CloudModelProfileFormPanelProps> = ({
  form,
  editingProfile,
  editingProfileId,
  canSave,
  saving,
  apiKeyDeletingId,
  saveError,
  t,
  onChange,
  onSave,
  onReset,
  onClearApiKey,
}) => {
  return (
    <>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <CloudModelProfileTextField
          labelKey="settings.cloud.name"
          testId="settings-cloud-profile-name-input"
          value={form.name}
          placeholder={t('settings.cloud.namePlaceholder')}
          onChange={(value) => onChange({ name: value })}
          t={t}
        />
        <CloudModelProfileTextField
          labelKey="settings.cloud.modelId"
          testId="settings-cloud-profile-model-input"
          value={form.model}
          placeholder="openai/gpt-4o-mini"
          onChange={(value) => onChange({ model: value })}
          t={t}
        />
        <CloudModelProfileTextField
          className="md:col-span-2"
          labelKey="settings.cloud.baseUrl"
          testId="settings-cloud-profile-base-url-input"
          value={form.baseUrl}
          placeholder="https://openrouter.ai/api/v1"
          onChange={(value) => onChange({ baseUrl: value })}
          t={t}
        />
        <CloudModelProfileApiKeyField
          apiKey={form.apiKey}
          editingProfile={editingProfile}
          saving={saving}
          apiKeyDeletingId={apiKeyDeletingId}
          onApiKeyChange={(value) => onChange({ apiKey: value })}
          onClearApiKey={onClearApiKey}
          t={t}
        />
        <CloudModelProfileTemperatureField
          temperature={form.temperature}
          onTemperatureChange={(value) => onChange({ temperature: value })}
          t={t}
        />
      </div>

      <CloudModelProfileFormActions
        canSave={canSave}
        editingProfileId={editingProfileId}
        saving={saving}
        saveError={saveError}
        onSave={onSave}
        onReset={onReset}
        t={t}
      />
    </>
  )
}
