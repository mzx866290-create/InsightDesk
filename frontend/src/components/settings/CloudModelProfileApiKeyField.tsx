import React from 'react'

import type { TranslationKey } from '../../i18n'
import type { CloudModelProfile } from '../../stores/chatStore'
import { Button } from '../ui/Button'

interface CloudModelProfileApiKeyFieldProps {
  apiKey: string
  apiKeyDeletingId: string | null
  editingProfile: CloudModelProfile | null
  saving: boolean
  onApiKeyChange: (value: string) => void
  onClearApiKey: (profile: CloudModelProfile) => void
  t: (key: TranslationKey) => string
}

export const CloudModelProfileApiKeyField: React.FC<CloudModelProfileApiKeyFieldProps> = ({
  apiKey,
  apiKeyDeletingId,
  editingProfile,
  saving,
  onApiKeyChange,
  onClearApiKey,
  t,
}) => (
  <div>
    <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
      {t('settings.cloud.apiKey')}
    </label>
    <input
      data-testid="settings-cloud-profile-api-key-input"
      className="input-base w-full text-sm"
      type="password"
      value={apiKey}
      onChange={(event) => onApiKeyChange(event.target.value)}
      placeholder="sk-..."
    />
    <p className="mt-1 text-[11px] text-text-secondary">
      {t('settings.cloud.apiKeyHint')}
    </p>
    {editingProfile ? (
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-text-secondary">
        <span>
          {editingProfile.modelConfig.api_key_ref
            ? t('settings.cloud.currentKeyManaged')
            : t('settings.cloud.currentKeyNotManaged')}
        </span>
        {editingProfile.modelConfig.api_key_ref ? (
          <Button
            data-testid="settings-cloud-profile-clear-editor"
            variant="ghost"
            size="sm"
            disabled={saving || apiKeyDeletingId === editingProfile.id}
            onClick={() => onClearApiKey(editingProfile)}
          >
            {apiKeyDeletingId === editingProfile.id
              ? t('settings.cloud.clearingManagedKey')
              : t('settings.cloud.clearManagedKey')}
          </Button>
        ) : null}
      </div>
    ) : null}
  </div>
)
