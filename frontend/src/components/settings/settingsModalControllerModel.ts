import type { TranslationKey } from '../../i18n'
import type { SettingsTab, SettingsTabItem } from './SettingsNavigation'
import type { SettingsTabDefinition } from './settingsTabs'
import { isAdvancedSettingsTab } from './settingsTabs'

export function buildSettingsTabItems(
  tabs: SettingsTabDefinition[],
  translate: (key: TranslationKey) => string,
): SettingsTabItem[] {
  return tabs.map(({ id, labelKey }) => [id, translate(labelKey)])
}

export function getAdvancedTabsVisible(
  showAdvancedSettings: boolean,
  activeTab: SettingsTab,
): boolean {
  return showAdvancedSettings || isAdvancedSettingsTab(activeTab)
}
