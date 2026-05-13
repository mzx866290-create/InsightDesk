import React from 'react'

import { McpApprovalsListPanel } from './McpApprovalsListPanel'
import { McpApprovalsMessage } from './McpApprovalsMessage'
import { McpApprovalsSummaryPanel } from './McpApprovalsSummaryPanel'
import { McpApprovalsToolbar } from './McpApprovalsToolbar'
import { McpConfigSection } from './McpConfigSection'
import { McpRuntimeSection } from './McpRuntimeSection'
import { McpUnknownApprovalsPanel } from './McpUnknownApprovalsPanel'
import { useMcpApprovals } from './useMcpApprovals'

export const McpApprovalsPanel: React.FC = () => {
  const {
    approvals,
    sortedConnectors,
    unknownApprovedConnectors,
    connectorLabelByName,
    mcpConfig,
    mcpConfigText,
    runtimeHealth,
    runtimeHealthHistory,
    loading,
    loadingConfig,
    savingConfig,
    checkingRuntime,
    loadingRuntimeHistory,
    actingName,
    error,
    runtimeHistoryError,
    notice,
    setMcpConfigText,
    loadState,
    loadRuntimeHealthHistory,
    handleRuntimeHealth,
    handleSaveConfig,
    handleApprove,
    handleRevoke,
  } = useMcpApprovals()

  return (
    <div className="space-y-4" data-testid="settings-mcp-approvals-panel">
      <McpApprovalsToolbar
        checkingRuntime={checkingRuntime}
        loading={loading}
        onRuntimeHealth={() => void handleRuntimeHealth()}
        onRefresh={() => void loadState()}
      />

      <McpApprovalsSummaryPanel approvals={approvals} />

      <McpConfigSection
        config={mcpConfig}
        value={mcpConfigText}
        loading={loadingConfig}
        saving={savingConfig}
        onValueChange={setMcpConfigText}
        onSave={() => void handleSaveConfig()}
      />

      <McpRuntimeSection
        runtimeHealth={runtimeHealth}
        runtimeHealthHistory={runtimeHealthHistory}
        loadingRuntimeHistory={loadingRuntimeHistory}
        runtimeHistoryError={runtimeHistoryError}
        onRuntimeHistoryRefresh={() => void loadRuntimeHealthHistory()}
        connectorLabelByName={connectorLabelByName}
      />

      <McpApprovalsMessage error={error} notice={notice} />

      <McpApprovalsListPanel
        connectors={sortedConnectors}
        approvals={approvals}
        actingName={actingName}
        loading={loading}
        onApprove={(name) => void handleApprove(name)}
        onRevoke={(name) => void handleRevoke(name)}
      />

      <McpUnknownApprovalsPanel
        connectorNames={unknownApprovedConnectors}
        actingName={actingName}
        onRevoke={(name) => void handleRevoke(name)}
      />
    </div>
  )
}
