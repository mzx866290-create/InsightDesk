import { describe, expect, it } from 'vitest'

import {
  buildSettingsTabItems,
  getAdvancedTabsVisible,
  shouldLoadSsoSettings,
} from './settingsModalControllerModel'

describe('settingsModalControllerModel', () => {
  it('builds translated tab tuples without changing ids', () => {
    const items = buildSettingsTabItems(
      [{ id: 'general', labelKey: 'settings.tabs.general' }],
      (key) => `t:${key}`,
    )

    expect(items).toEqual([['general', 't:settings.tabs.general']])
  })

  it('shows advanced tabs when expanded or when an advanced tab is active', () => {
    expect(getAdvancedTabsVisible(false, 'general')).toBe(false)
    expect(getAdvancedTabsVisible(true, 'general')).toBe(true)
    expect(getAdvancedTabsVisible(false, 'integrations')).toBe(true)
    expect(getAdvancedTabsVisible(false, 'sso')).toBe(true)
  })

  it('loads SSO configuration only on the first visit to its advanced tab', () => {
    expect(shouldLoadSsoSettings(true, 'general', false)).toBe(false)
    expect(shouldLoadSsoSettings(false, 'sso', false)).toBe(false)
    expect(shouldLoadSsoSettings(true, 'sso', false)).toBe(true)
    expect(shouldLoadSsoSettings(true, 'sso', true)).toBe(false)
  })

})
