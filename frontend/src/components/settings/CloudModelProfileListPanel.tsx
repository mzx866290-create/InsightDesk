import React from 'react'

import type { TranslationKey } from '../../i18n'
import type { CloudModelProfile } from '../../stores/chatStore'
import { Button } from '../ui/Button'

export interface CloudModelProfileListPanelProps {
  profiles: CloudModelProfile[]
  saving: boolean
  apiKeyDeletingId: string | null
  t: (key: TranslationKey) => string
  onEdit: (profile: CloudModelProfile) => void
  onDelete: (profile: CloudModelProfile) => void
  onClearApiKey: (profile: CloudModelProfile) => void
}

export const CloudModelProfileListPanel: React.FC<CloudModelProfileListPanelProps> = ({
  profiles,
  saving,
  apiKeyDeletingId,
  t,
  onEdit,
  onDelete,
  onClearApiKey,
}) => {
  return (
    <div className="mt-4 border-t border-bg-border pt-4">
      <div className="mb-2 text-[11px] uppercase tracking-wide text-text-secondary">
        {t('settings.cloud.savedProfiles')}
      </div>
      {profiles.length > 0 ? (
        <div className="space-y-2" data-testid="settings-cloud-profile-list">
          {profiles.map((profile) => (
            <div
              key={profile.id}
              data-testid="settings-cloud-profile-card"
              data-profile-id={profile.id}
              data-profile-name={profile.name}
              className="rounded-lg border border-bg-border bg-bg-primary/40 px-3 py-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-text-primary">
                    {profile.name}
                  </div>
                  <div className="mt-1 truncate text-xs text-text-secondary">
                    {profile.modelConfig.model}
                  </div>
                  <div className="mt-1 truncate text-[11px] text-text-secondary/70">
                    {profile.modelConfig.base_url}
                  </div>
                  <div className="mt-2 text-[11px] text-text-secondary">
                    {profile.modelConfig.api_key_ref
                      ? t('settings.cloud.keyManaged')
                      : t('settings.cloud.keyNotManaged')}
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  {profile.modelConfig.api_key_ref ? (
                    <Button
                      data-testid="settings-cloud-profile-clear"
                      variant="ghost"
                      size="sm"
                      disabled={saving || apiKeyDeletingId === profile.id}
                      onClick={() => onClearApiKey(profile)}
                    >
                      {apiKeyDeletingId === profile.id
                        ? t('settings.cloud.clearingKey')
                        : t('settings.cloud.clearKey')}
                    </Button>
                  ) : null}
                  <Button
                    data-testid="settings-cloud-profile-edit"
                    variant="outline"
                    size="sm"
                    onClick={() => onEdit(profile)}
                  >
                    {t('settings.cloud.edit')}
                  </Button>
                  <Button
                    data-testid="settings-cloud-profile-delete"
                    variant="ghost"
                    size="sm"
                    className="text-accent-red hover:text-accent-red"
                    onClick={() => onDelete(profile)}
                  >
                    {t('settings.cloud.delete')}
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-secondary">
          {t('settings.cloud.empty')}
        </p>
      )}
    </div>
  )
}
