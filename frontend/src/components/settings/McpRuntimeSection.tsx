import React from 'react'

import type {
  McpRuntimeHealthHistoryItem,
  McpRuntimeHealthResponse,
} from '../../api/client'
import { McpRuntimeHealthHistoryPanel } from './McpRuntimeHealthHistoryPanel'
import { McpRuntimeHealthPanel } from './McpRuntimeHealthPanel'

interface McpRuntimeSectionProps {
  runtimeHealth: McpRuntimeHealthResponse | null
  runtimeHealthHistory: McpRuntimeHealthHistoryItem[]
  loadingRuntimeHistory: boolean
  runtimeHistoryError: string | null
  onRuntimeHistoryRefresh: () => void
  connectorLabelByName: Map<string, string>
}

export const McpRuntimeSection: React.FC<McpRuntimeSectionProps> = ({
  runtimeHealth,
  runtimeHealthHistory,
  loadingRuntimeHistory,
  runtimeHistoryError,
  onRuntimeHistoryRefresh,
  connectorLabelByName,
}) => (
  <>
    <McpRuntimeHealthPanel
      runtimeHealth={runtimeHealth}
      connectorLabelByName={connectorLabelByName}
    />

    <McpRuntimeHealthHistoryPanel
      history={runtimeHealthHistory}
      loading={loadingRuntimeHistory}
      error={runtimeHistoryError}
      onRefresh={onRuntimeHistoryRefresh}
      connectorLabelByName={connectorLabelByName}
    />
  </>
)
