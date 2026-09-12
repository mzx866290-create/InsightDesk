import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { GeneralSettingsPanelProps } from './GeneralSettingsPanel';
import type { SsoSettingsPanelProps } from './SsoSettingsPanel';
import type { RolePromptsController } from './useRolePrompts';
import { SettingsModalContent } from './SettingsModalContent';

vi.mock('./AssistantPresetPanel', () => ({
  AssistantPresetPanel: () => <div data-testid="mock-assistant-presets-panel" />,
}));

vi.mock('./AgentCatalogPanel', () => ({
  AgentCatalogPanel: () => <div data-testid="mock-agent-catalog-panel" />,
}));

vi.mock('./DeliveryTemplateCatalogPanel', () => ({
  DeliveryTemplateCatalogPanel: () => <div data-testid="mock-delivery-template-panel" />,
}));

vi.mock('./GeneralSettingsPanel', () => ({
  GeneralSettingsPanel: () => <div data-testid="mock-general-panel" />,
}));

vi.mock('./RoleSettingsPanel', () => ({
  RoleSettingsPanel: () => <div data-testid="mock-roles-panel" />,
}));

vi.mock('./TraceOperationsPanel', () => ({
  TraceOperationsPanel: () => <div data-testid="mock-traces-panel" />,
}));

vi.mock('./McpApprovalsPanel', () => ({
  McpApprovalsPanel: () => <div data-testid="mock-mcp-panel" />,
}));

vi.mock('./IntegratorConnectorsPanel', () => ({
  IntegratorConnectorsPanel: () => <div data-testid="mock-integrations-panel" />,
}));

vi.mock('./SecurityAuditSummaryPanel', () => ({
  SecurityAuditSummaryPanel: () => <div data-testid="mock-security-panel" />,
}));

vi.mock('./CloudModelProfilesPanel', () => ({
  CloudModelProfilesPanel: () => <div data-testid="mock-cloud-models-panel" />,
}));

vi.mock('./SsoSettingsPanel', () => ({
  SsoSettingsPanel: () => <div data-testid="mock-sso-panel" />,
}));

const generalSettings = {
  language: 'zh-CN',
  adminToken: '',
  adminTokenSaved: false,
  adminAccessError: null,
  authStatusText: null,
  tavilyKey: '',
  tavilyKeySet: false,
  saving: false,
  saveOk: false,
  saveError: null,
  resetting: false,
  onLanguageChange: vi.fn(),
  onAdminTokenChange: vi.fn(),
  onSaveAdminToken: vi.fn(),
  onClearAdminToken: vi.fn(),
  onTavilyKeyChange: vi.fn(),
  onSaveGeneral: vi.fn(),
  onClearTavilyKey: vi.fn(),
  onResetAgents: vi.fn(),
} satisfies GeneralSettingsPanelProps;

const ssoSettings = {
  config: null,
  form: {
    provider: 'none',
    issuer_url: '',
    authorization_endpoint: '',
    token_endpoint: '',
    jwks_url: '',
    client_id: '',
    client_secret: '',
    clear_client_secret: false,
    allowed_domains: '',
    scopes: 'openid email profile',
    default_role: 'viewer',
    session_ttl_seconds: 28800,
  },
  loading: false,
  saving: false,
  loginStarting: false,
  error: null,
  onFormChange: vi.fn(),
  onSave: vi.fn(),
  onStartLogin: vi.fn(),
  onRefresh: vi.fn(),
} satisfies SsoSettingsPanelProps;

const rolePrompts = {
  isCreating: false,
  editingPrompt: null,
  promptName: '',
  promptContent: '',
  promptVectorStoreId: '',
  knowledgeBases: [],
  loadingKnowledgeBases: false,
  dashboardFieldsProps: {} as RolePromptsController['dashboardFieldsProps'],
  promptSaving: false,
  loadingPrompts: false,
  prompts: [],
  activatingId: null,
  deletingPromptId: null,
  activateStatus: {},
  loadPrompts: vi.fn(),
  loadKnowledgeBases: vi.fn(),
  setPromptName: vi.fn(),
  setPromptContent: vi.fn(),
  setPromptVectorStoreId: vi.fn(),
  savePrompt: vi.fn(),
  cancelEdit: vi.fn(),
  startCreate: vi.fn(),
  activatePrompt: vi.fn(),
  startEdit: vi.fn(),
  deletePrompt: vi.fn(),
} satisfies RolePromptsController;

function renderContent(tab: React.ComponentProps<typeof SettingsModalContent>['tab']) {
  return render(
    <SettingsModalContent
      tab={tab}
      generalSettings={generalSettings}
      ssoSettings={ssoSettings}
      rolePrompts={rolePrompts}
      quickTemplates={[]}
    />
  );
}

describe('SettingsModalContent', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it.each([
    ['general', 'mock-general-panel'],
    ['assistant_presets', 'mock-assistant-presets-panel'],
    ['sso', 'mock-sso-panel'],
    ['cloud_models', 'mock-cloud-models-panel'],
    ['agent_catalog', 'mock-agent-catalog-panel'],
    ['delivery_templates', 'mock-delivery-template-panel'],
    ['roles', 'mock-roles-panel'],
    ['traces', 'mock-traces-panel'],
    ['mcp_approvals', 'mock-mcp-panel'],
    ['integrations', 'mock-integrations-panel'],
    ['security_audit', 'mock-security-panel'],
  ] as const)('renders the %s tab panel', (tab, testId) => {
    renderContent(tab);

    expect(screen.getByTestId(testId)).toBeInTheDocument();
  });

});
