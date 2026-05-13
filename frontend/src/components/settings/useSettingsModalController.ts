import { useCallback, useEffect, useMemo, useState } from 'react'

import { useI18n } from '../../i18n'
import { useChatStore } from '../../stores/chatStore'
import type { SettingsModalContentProps } from './SettingsModalContent'
import type { SettingsNavigationProps, SettingsTab, SettingsTabItem } from './SettingsNavigation'
import {
  ADVANCED_SETTINGS_TABS,
  PRIMARY_SETTINGS_TABS,
  getSettingsModalWidth,
  isAdvancedSettingsTab,
} from './settingsTabs'
import {
  buildSettingsTabItems,
  getAdvancedTabsVisible,
} from './settingsModalControllerModel'
import { useGeneralSettingsController } from './useGeneralSettingsController'
import { useKbMonitor } from './useKbMonitor'
import { useRolePrompts } from './useRolePrompts'
import type { RolePromptTemplate } from './useRolePrompts'

interface UseSettingsModalControllerOptions {
  open: boolean
  quickTemplates: RolePromptTemplate[]
}

interface SettingsModalController {
  tab: SettingsTab
  modalTitle: string
  modalWidth: string
  navigationProps: SettingsNavigationProps
  contentProps: SettingsModalContentProps
}

export function useSettingsModalController({
  open,
  quickTemplates,
}: UseSettingsModalControllerOptions): SettingsModalController {
  const { t } = useI18n()
  const [tab, setTab] = useState<SettingsTab>('general')
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(false)
  const [adminAccessError, setAdminAccessError] = useState<string | null>(null)

  const setActivePromptId = useChatStore((state) => state.setActivePromptId)
  const rolePrompts = useRolePrompts({
    setAdminAccessError,
    setActivePromptId,
  })
  const kbMonitor = useKbMonitor({
    enabled: open && tab === 'kb_monitor',
    onKnowledgeBasesChanged: rolePrompts.loadKnowledgeBases,
  })
  const generalSettings = useGeneralSettingsController({
    adminAccessError,
    kbMonitor,
    open,
    rolePrompts,
    setAdminAccessError,
    tab,
  })

  useEffect(() => {
    if (open) {
      setTab('general')
      setShowAdvancedSettings(false)
      setAdminAccessError(null)
      rolePrompts.loadPrompts()
    }
  }, [open, rolePrompts.loadPrompts])

  useEffect(() => {
    if (open && tab === 'roles') {
      rolePrompts.loadKnowledgeBases()
    }
  }, [open, tab, rolePrompts.loadKnowledgeBases])

  const primaryTabs: SettingsTabItem[] = useMemo(
    () => buildSettingsTabItems(PRIMARY_SETTINGS_TABS, t),
    [t],
  )
  const advancedTabs: SettingsTabItem[] = useMemo(
    () => buildSettingsTabItems(ADVANCED_SETTINGS_TABS, t),
    [t],
  )
  const advancedTabsVisible = getAdvancedTabsVisible(showAdvancedSettings, tab)
  const selectSettingsTab = useCallback((nextTab: SettingsTab) => {
    if (isAdvancedSettingsTab(nextTab)) {
      setShowAdvancedSettings(true)
    }
    setTab(nextTab)
  }, [])

  const navigationProps = useMemo<SettingsNavigationProps>(
    () => ({
      activeTab: tab,
      primaryTabs,
      advancedTabs,
      advancedVisible: advancedTabsVisible,
      dailyTitle: t('settings.groups.daily'),
      dailyDescription: t('settings.groups.dailyDescription'),
      advancedTitle: t('settings.groups.advanced'),
      advancedDescription: t('settings.groups.advancedDescription'),
      advancedCollapsedHint: t('settings.groups.advancedCollapsedHint'),
      onSelectTab: selectSettingsTab,
      onToggleAdvanced: () => setShowAdvancedSettings((value) => !value),
    }),
    [advancedTabs, advancedTabsVisible, primaryTabs, selectSettingsTab, t, tab],
  )

  const contentProps = useMemo<SettingsModalContentProps>(
    () => ({
      tab,
      generalSettings,
      kbMonitor,
      rolePrompts,
      quickTemplates,
    }),
    [generalSettings, kbMonitor, quickTemplates, rolePrompts, tab],
  )

  return {
    tab,
    modalTitle: t('settings.title'),
    modalWidth: getSettingsModalWidth(tab),
    navigationProps,
    contentProps,
  }
}
