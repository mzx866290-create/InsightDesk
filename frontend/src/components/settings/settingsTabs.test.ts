import { describe, expect, it } from 'vitest'

import {
  ADVANCED_SETTINGS_TABS,
  PRIMARY_SETTINGS_TABS,
  getSettingsModalWidth,
  isAdvancedSettingsTab,
} from './settingsTabs'

describe('settingsTabs', () => {
  it('keeps daily tabs separate from advanced tabs', () => {
    expect(PRIMARY_SETTINGS_TABS.map((tab) => tab.id)).toEqual([
      'general',
      'assistant_presets',
      'documents',
    ])
    expect(ADVANCED_SETTINGS_TABS.map((tab) => tab.id)).toEqual([
      'roles',
      'agent_catalog',
      'delivery_templates',
      'integrations',
      'kb_monitor',
      'mcp_approvals',
      'traces',
      'security_audit',
    ])
  })

  it('detects advanced tabs by definition list', () => {
    expect(isAdvancedSettingsTab('general')).toBe(false)
    expect(isAdvancedSettingsTab('assistant_presets')).toBe(false)
    expect(isAdvancedSettingsTab('documents')).toBe(false)
    expect(isAdvancedSettingsTab('roles')).toBe(true)
    expect(isAdvancedSettingsTab('agent_catalog')).toBe(true)
    expect(isAdvancedSettingsTab('delivery_templates')).toBe(true)
    expect(isAdvancedSettingsTab('security_audit')).toBe(true)
  })

  it('uses wide modal width only for dense settings panels', () => {
    expect(getSettingsModalWidth('general')).toBe('max-w-xl')
    expect(getSettingsModalWidth('assistant_presets')).toBe('max-w-4xl')
    expect(getSettingsModalWidth('documents')).toBe('max-w-xl')
    expect(getSettingsModalWidth('kb_monitor')).toBe('max-w-4xl')
    expect(getSettingsModalWidth('agent_catalog')).toBe('max-w-4xl')
    expect(getSettingsModalWidth('delivery_templates')).toBe('max-w-4xl')
    expect(getSettingsModalWidth('integrations')).toBe('max-w-4xl')
  })
})
