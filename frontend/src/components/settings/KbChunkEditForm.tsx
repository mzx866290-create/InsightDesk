import React from 'react'

import { useI18n } from '../../i18n'
import { Button } from '../ui/Button'

export interface KbChunkEditFormProps {
  source: string
  content: string
  saving: boolean
  onSourceChange: (value: string) => void
  onContentChange: (value: string) => void
  onSave: () => void
  onCancel: () => void
}

export const KbChunkEditForm: React.FC<KbChunkEditFormProps> = ({
  source,
  content,
  saving,
  onSourceChange,
  onContentChange,
  onSave,
  onCancel,
}) => {
  const { t } = useI18n()

  return (
    <div className="space-y-2">
      <input
        data-testid="settings-kb-chunk-edit-source"
        className="input-base min-h-11 w-full text-xs"
        value={source}
        onChange={(event) => onSourceChange(event.target.value)}
        placeholder={t('settings.kbChunks.sourcePlaceholder')}
      />
      <textarea
        data-testid="settings-kb-chunk-edit-content"
        className="input-base min-h-[120px] w-full resize-y text-xs"
        value={content}
        onChange={(event) => onContentChange(event.target.value)}
        placeholder={t('settings.kbChunks.contentPlaceholder')}
      />
      <div className="flex items-center gap-2">
        <Button
          data-testid="settings-kb-chunk-edit-save"
          variant="primary"
          onClick={onSave}
          loading={saving}
          className="min-h-11 text-xs"
        >
          {t('settings.kbChunks.save')}
        </Button>
        <Button
          data-testid="settings-kb-chunk-edit-cancel"
          variant="ghost"
          onClick={onCancel}
          className="min-h-11 text-xs"
        >
          {t('settings.kbChunks.cancel')}
        </Button>
      </div>
    </div>
  )
}
