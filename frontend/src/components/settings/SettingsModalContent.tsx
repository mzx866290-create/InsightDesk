import React from 'react'

import { AgentCatalogPanel } from './AgentCatalogPanel'
import { AssistantPresetPanel } from './AssistantPresetPanel'
import { DeliveryTemplateCatalogPanel } from './DeliveryTemplateCatalogPanel'
import { IntegratorConnectorsPanel } from './IntegratorConnectorsPanel'
import { DocumentIngestionPanel } from './DocumentIngestionPanel'
import { GeneralSettingsPanel, type GeneralSettingsPanelProps } from './GeneralSettingsPanel'
import { KbMonitorPanel } from './KbMonitorPanel'
import { McpApprovalsPanel } from './McpApprovalsPanel'
import { RoleSettingsPanel } from './RoleSettingsPanel'
import { SecurityAuditSummaryPanel } from './SecurityAuditSummaryPanel'
import type { SettingsTab } from './SettingsNavigation'
import { TraceOperationsPanel } from './TraceOperationsPanel'
import type { KbMonitorController } from './useKbMonitor'
import type { RolePromptTemplate, RolePromptsController } from './useRolePrompts'

export interface SettingsModalContentProps {
  tab: SettingsTab
  generalSettings: GeneralSettingsPanelProps
  kbMonitor: KbMonitorController
  rolePrompts: RolePromptsController
  quickTemplates: RolePromptTemplate[]
}

export const SettingsModalContent: React.FC<SettingsModalContentProps> = ({
  tab,
  generalSettings,
  kbMonitor,
  rolePrompts,
  quickTemplates,
}) => {
  if (tab === 'general') {
    return <GeneralSettingsPanel {...generalSettings} />
  }

  if (tab === 'documents') {
    return (
      <DocumentIngestionPanel
        deletingKnowledgeBase={kbMonitor.deletingKnowledgeBase}
        deleteKnowledgeBaseConfirming={kbMonitor.isDeleteKnowledgeBaseConfirming()}
        onDeleteKnowledgeBase={() => kbMonitor.deleteKnowledgeBase()}
      />
    )
  }

  if (tab === 'assistant_presets') {
    return <AssistantPresetPanel />
  }

  if (tab === 'roles') {
    return (
      <RoleSettingsPanel
        rolePrompts={rolePrompts}
        quickTemplates={quickTemplates}
      />
    )
  }

  if (tab === 'agent_catalog') {
    return <AgentCatalogPanel />
  }

  if (tab === 'delivery_templates') {
    return <DeliveryTemplateCatalogPanel />
  }

  if (tab === 'traces') {
    return <TraceOperationsPanel />
  }

  if (tab === 'mcp_approvals') {
    return <McpApprovalsPanel />
  }

  if (tab === 'integrations') {
    return <IntegratorConnectorsPanel />
  }

  if (tab === 'security_audit') {
    return <SecurityAuditSummaryPanel />
  }

  if (tab === 'kb_monitor') {
    return <KbMonitorPanel monitor={kbMonitor} />
  }

  return null
}
