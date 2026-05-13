import { describe, expect, it } from 'vitest'

import {
  buildSettingsTabItems,
  getAdvancedTabsVisible,
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
  })

})
