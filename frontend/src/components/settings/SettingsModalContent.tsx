import React from 'react';

import { AgentCatalogPanel } from './AgentCatalogPanel';
import { AssistantPresetPanel } from './AssistantPresetPanel';
import { CloudModelProfilesPanel } from './CloudModelProfilesPanel';
import { DeliveryTemplateCatalogPanel } from './DeliveryTemplateCatalogPanel';
import { IntegratorConnectorsPanel } from './IntegratorConnectorsPanel';
import { GeneralSettingsPanel, type GeneralSettingsPanelProps } from './GeneralSettingsPanel';
import { McpApprovalsPanel } from './McpApprovalsPanel';
import { RoleSettingsPanel } from './RoleSettingsPanel';
import { SecurityAuditSummaryPanel } from './SecurityAuditSummaryPanel';
import type { SettingsTab } from './SettingsNavigation';
import { SsoSettingsPanel, type SsoSettingsPanelProps } from './SsoSettingsPanel';
import { TraceOperationsPanel } from './TraceOperationsPanel';
import type { RolePromptTemplate, RolePromptsController } from './useRolePrompts';

export interface SettingsModalContentProps {
  tab: SettingsTab;
  generalSettings: GeneralSettingsPanelProps;
  ssoSettings: SsoSettingsPanelProps;
  rolePrompts: RolePromptsController;
  quickTemplates: RolePromptTemplate[];
}

export const SettingsModalContent: React.FC<SettingsModalContentProps> = ({
  tab,
  generalSettings,
  ssoSettings,
  rolePrompts,
  quickTemplates,
}) => {
  if (tab === 'general') {
    return <GeneralSettingsPanel {...generalSettings} />;
  }

  if (tab === 'sso') {
    return <SsoSettingsPanel {...ssoSettings} />;
  }

  if (tab === 'cloud_models') {
    return <CloudModelProfilesPanel />;
  }

  if (tab === 'assistant_presets') {
    return <AssistantPresetPanel />;
  }

  if (tab === 'roles') {
    return <RoleSettingsPanel rolePrompts={rolePrompts} quickTemplates={quickTemplates} />;
  }

  if (tab === 'agent_catalog') {
    return <AgentCatalogPanel />;
  }

  if (tab === 'delivery_templates') {
    return <DeliveryTemplateCatalogPanel />;
  }

  if (tab === 'traces') {
    return <TraceOperationsPanel />;
  }

  if (tab === 'mcp_approvals') {
    return <McpApprovalsPanel />;
  }

  if (tab === 'integrations') {
    return <IntegratorConnectorsPanel />;
  }

  if (tab === 'security_audit') {
    return <SecurityAuditSummaryPanel />;
  }

  return null;
};
