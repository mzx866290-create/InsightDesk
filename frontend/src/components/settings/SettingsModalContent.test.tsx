import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { GeneralSettingsPanelProps } from './GeneralSettingsPanel'
import type { KbMonitorController } from './useKbMonitor'
import type { RolePromptsController } from './useRolePrompts'
import { SettingsModalContent } from './SettingsModalContent'

vi.mock('./AssistantPresetPanel', () => ({
  AssistantPresetPanel: () => <div data-testid="mock-assistant-presets-panel" />,
}))

vi.mock('./AgentCatalogPanel', () => ({
  AgentCatalogPanel: () => <div data-testid="mock-agent-catalog-panel" />,
}))

vi.mock('./DeliveryTemplateCatalogPanel', () => ({
  DeliveryTemplateCatalogPanel: () => <div data-testid="mock-delivery-template-panel" />,
}))

vi.mock('./GeneralSettingsPanel', () => ({
  GeneralSettingsPanel: () => <div data-testid="mock-general-panel" />,
}))

vi.mock('./DocumentIngestionPanel', () => ({
  DocumentIngestionPanel: ({
    deleteKnowledgeBaseConfirming,
    onDeleteKnowledgeBase,
  }: {
    deleteKnowledgeBaseConfirming: boolean
    onDeleteKnowledgeBase: () => Promise<unknown>
  }) => (
    <button
      type="button"
      data-testid="mock-documents-panel"
      data-confirming={deleteKnowledgeBaseConfirming ? 'true' : 'false'}
      onClick={() => {
        void onDeleteKnowledgeBase()
      }}
    >
      documents
    </button>
  ),
}))

vi.mock('./RoleSettingsPanel', () => ({
  RoleSettingsPanel: () => <div data-testid="mock-roles-panel" />,
}))

vi.mock('./TraceOperationsPanel', () => ({
  TraceOperationsPanel: () => <div data-testid="mock-traces-panel" />,
}))

vi.mock('./McpApprovalsPanel', () => ({
  McpApprovalsPanel: () => <div data-testid="mock-mcp-panel" />,
}))

vi.mock('./IntegratorConnectorsPanel', () => ({
  IntegratorConnectorsPanel: () => <div data-testid="mock-integrations-panel" />,
}))

vi.mock('./SecurityAuditSummaryPanel', () => ({
  SecurityAuditSummaryPanel: () => <div data-testid="mock-security-panel" />,
}))

vi.mock('./KbMonitorPanel', () => ({
  KbMonitorPanel: () => <div data-testid="mock-kb-monitor-panel" />,
}))

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
  ssoSettings: {
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
  },
  onLanguageChange: vi.fn(),
  onAdminTokenChange: vi.fn(),
  onSaveAdminToken: vi.fn(),
  onClearAdminToken: vi.fn(),
  onTavilyKeyChange: vi.fn(),
  onSaveGeneral: vi.fn(),
  onClearTavilyKey: vi.fn(),
  onResetAgents: vi.fn(),
} satisfies GeneralSettingsPanelProps

const kbMonitor = {
  health: null,
  loadingHealth: false,
  actionError: null,
  chunkBrowserProps: {} as KbMonitorController['chunkBrowserProps'],
  retrievalTestProps: {} as KbMonitorController['retrievalTestProps'],
  dangerZoneProps: {} as KbMonitorController['dangerZoneProps'],
  deletingKnowledgeBase: false,
  isDeleteKnowledgeBaseConfirming: vi.fn(() => true),
  refreshHealth: vi.fn(),
  refreshCurrent: vi.fn(),
  deleteKnowledgeBase: vi.fn(async () => 'deleted' as const),
} satisfies KbMonitorController

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
} satisfies RolePromptsController

function renderContent(tab: React.ComponentProps<typeof SettingsModalContent>['tab']) {
  return render(
    <SettingsModalContent
      tab={tab}
      generalSettings={generalSettings}
      kbMonitor={kbMonitor}
      rolePrompts={rolePrompts}
      quickTemplates={[]}
    />,
  )
}

describe('SettingsModalContent', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it.each([
    ['general', 'mock-general-panel'],
    ['assistant_presets', 'mock-assistant-presets-panel'],
    ['agent_catalog', 'mock-agent-catalog-panel'],
    ['delivery_templates', 'mock-delivery-template-panel'],
    ['roles', 'mock-roles-panel'],
    ['traces', 'mock-traces-panel'],
    ['mcp_approvals', 'mock-mcp-panel'],
    ['integrations', 'mock-integrations-panel'],
    ['security_audit', 'mock-security-panel'],
    ['kb_monitor', 'mock-kb-monitor-panel'],
  ] as const)('renders the %s tab panel', (tab, testId) => {
    renderContent(tab)

    expect(screen.getByTestId(testId)).toBeInTheDocument()
  })

  it('passes knowledge-base deletion state and action to the documents panel', () => {
    renderContent('documents')

    const panel = screen.getByTestId('mock-documents-panel')
    expect(panel).toHaveAttribute('data-confirming', 'true')

    fireEvent.click(panel)
    expect(kbMonitor.deleteKnowledgeBase).toHaveBeenCalledTimes(1)
  })
})
