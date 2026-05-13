import React from 'react'

import type { TranslationKey } from '../../i18n'
import { Button } from '../ui/Button'

interface CloudModelProfileFormActionsProps {
  canSave: boolean
  editingProfileId: string | null
  saving: boolean
  saveError: string | null
  onSave: () => void
  onReset: () => void
  t: (key: TranslationKey) => string
}

export const CloudModelProfileFormActions: React.FC<CloudModelProfileFormActionsProps> = ({
  canSave,
  editingProfileId,
  saving,
  saveError,
  onSave,
  onReset,
  t,
}) => (
  <>
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <Button
        data-testid="settings-cloud-profile-save"
        variant="primary"
        onClick={onSave}
        disabled={saving || !canSave}
      >
        {saving
          ? t('settings.cloud.saving')
          : editingProfileId
            ? t('settings.cloud.update')
            : t('settings.cloud.save')}
      </Button>
      <Button variant="ghost" onClick={onReset}>
        {t('settings.cloud.resetForm')}
      </Button>
      <span className="text-[11px] text-text-secondary">
        {t('settings.cloud.encryptedHint')}
      </span>
    </div>
    {saveError ? (
      <p className="mt-2 text-xs text-accent-red">{saveError}</p>
    ) : null}
  </>
)
