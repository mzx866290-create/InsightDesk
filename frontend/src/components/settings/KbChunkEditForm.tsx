import React from 'react'

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
}) => (
  <div className="space-y-2">
    <input
      data-testid="settings-kb-chunk-edit-source"
      className="input-base w-full text-xs"
      value={source}
      onChange={(event) => onSourceChange(event.target.value)}
      placeholder="閺夈儲绨崥宥囆?"
    />
    <textarea
      data-testid="settings-kb-chunk-edit-content"
      className="input-base w-full text-xs resize-y min-h-[120px]"
      value={content}
      onChange={(event) => onContentChange(event.target.value)}
      placeholder="閸掑洨澧栭崘鍛啇"
    />
    <div className="flex items-center gap-2">
      <Button
        data-testid="settings-kb-chunk-edit-save"
        variant="primary"
        onClick={onSave}
        loading={saving}
        className="text-xs"
      >
        娣囨繂鐡?
      </Button>
      <Button data-testid="settings-kb-chunk-edit-cancel" variant="ghost" onClick={onCancel} className="text-xs">
        閸欐牗绉?
      </Button>
    </div>
  </div>
)
