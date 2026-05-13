import React from 'react'

import type { McpConfigResponse } from '../../api/client'
import { McpConfigEditorPanel } from './McpConfigEditorPanel'

interface McpConfigSectionProps {
  config: McpConfigResponse | null
  value: string
  loading: boolean
  saving: boolean
  onValueChange: (value: string) => void
  onSave: () => void
}

export const McpConfigSection: React.FC<McpConfigSectionProps> = ({
  config,
  value,
  loading,
  saving,
  onValueChange,
  onSave,
}) => (
  <McpConfigEditorPanel
    config={config}
    value={value}
    loading={loading}
    saving={saving}
    onValueChange={onValueChange}
    onSave={onSave}
  />
)
