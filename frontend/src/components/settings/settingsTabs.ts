import type { SettingsTab } from './SettingsNavigation'
import type { TranslationKey } from '../../i18n'

export type SettingsTabDefinition = {
  id: SettingsTab
  labelKey: TranslationKey
}

export const PRIMARY_SETTINGS_TABS: SettingsTabDefinition[] = [
  { id: 'general', labelKey: 'settings.tabs.general' },
  { id: 'assistant_presets', labelKey: 'settings.tabs.assistantPresets' },
  { id: 'documents', labelKey: 'settings.tabs.documents' },
]

export const ADVANCED_SETTINGS_TABS: SettingsTabDefinition[] = [
  { id: 'roles', labelKey: 'settings.tabs.roles' },
  { id: 'agent_catalog', labelKey: 'settings.tabs.agentCatalog' },
  { id: 'delivery_templates', labelKey: 'settings.tabs.deliveryTemplates' },
  { id: 'integrations', labelKey: 'settings.tabs.integrations' },
  { id: 'kb_monitor', labelKey: 'settings.tabs.kbMonitor' },
  { id: 'mcp_approvals', labelKey: 'settings.tabs.mcpApprovals' },
  { id: 'traces', labelKey: 'settings.tabs.traces' },
  { id: 'security_audit', labelKey: 'settings.tabs.securityAudit' },
]

const WIDE_SETTINGS_TABS = new Set<SettingsTab>([
  'assistant_presets',
  'roles',
  'agent_catalog',
  'delivery_templates',
  'kb_monitor',
  'mcp_approvals',
  'integrations',
  'traces',
  'security_audit',
])

export function isAdvancedSettingsTab(tab: SettingsTab): boolean {
  return ADVANCED_SETTINGS_TABS.some(({ id }) => id === tab)
}

export function getSettingsModalWidth(tab: SettingsTab): 'max-w-4xl' | 'max-w-xl' {
  return WIDE_SETTINGS_TABS.has(tab) ? 'max-w-4xl' : 'max-w-xl'
}
