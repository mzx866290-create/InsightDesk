import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  getConfig,
  resetAgents,
} from '../../api/client'
import { useI18n } from '../../i18n'
import { isAdminAccessError } from '../admin/adminAccess'
import type { GeneralSettingsPanelProps } from './GeneralSettingsPanel'
import { buildGeneralSettingsPanelProps } from './generalSettingsControllerModel'
import type { SettingsTab } from './SettingsNavigation'
import { useAdminTokenSettings } from './useAdminTokenSettings'
import type { KbMonitorController } from './useKbMonitor'
import type { RolePromptsController } from './useRolePrompts'
import { useSsoSettings } from './useSsoSettings'
import { useTavilySettings } from './useTavilySettings'

interface UseGeneralSettingsControllerOptions {
  adminAccessError: string | null
  kbMonitor: KbMonitorController
  open: boolean
  rolePrompts: RolePromptsController
  setAdminAccessError: (message: string | null) => void
  tab: SettingsTab
}

export function useGeneralSettingsController({
  adminAccessError,
  kbMonitor,
  open,
  rolePrompts,
  setAdminAccessError,
  tab,
}: UseGeneralSettingsControllerOptions): GeneralSettingsPanelProps {
  const { language, setLanguage } = useI18n()
  const [resetting, setResetting] = useState(false)
  const ssoSettings = useSsoSettings()
  const tavilySettings = useTavilySettings()

  const {
    clearTavilyKey,
    saveTavilyKey,
    setSaveError,
    setTavilyKeySet,
  } = tavilySettings
  const {
    load: loadSsoConfig,
    reset: resetSsoSettings,
  } = ssoSettings

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await getConfig()
      setTavilyKeySet(cfg.tavily_api_key_set)
      setSaveError(null)
      setAdminAccessError(null)
    } catch (e) {
      if (isAdminAccessError(e)) {
        setAdminAccessError((e as Error).message)
      }
    }
  }, [setAdminAccessError, setSaveError, setTavilyKeySet])

  const refreshAfterAdminTokenSaved = useCallback(async () => {
    await loadConfig()
    await rolePrompts.loadPrompts()
    if (tab === 'roles') {
      await rolePrompts.loadKnowledgeBases()
    }
    if (tab === 'kb_monitor') {
      await kbMonitor.refreshCurrent()
    }
  }, [kbMonitor, loadConfig, rolePrompts, tab])

  const adminTokenSettings = useAdminTokenSettings({
    open,
    onTokenSaved: refreshAfterAdminTokenSaved,
    setAdminAccessError,
  })

  useEffect(() => {
    if (!open) return
    setAdminAccessError(null)
    resetSsoSettings()
    void loadSsoConfig()
    void loadConfig()
  }, [
    loadConfig,
    loadSsoConfig,
    open,
    resetSsoSettings,
    setAdminAccessError,
  ])

  const handleSaveGeneral = useCallback(async () => {
    await saveTavilyKey(loadConfig)
  }, [loadConfig, saveTavilyKey])

  const handleClearTavilyKey = useCallback(async () => {
    await clearTavilyKey(loadConfig)
  }, [clearTavilyKey, loadConfig])

  const handleResetAgents = useCallback(async () => {
    setResetting(true)
    try {
      await resetAgents()
    } finally {
      setResetting(false)
    }
  }, [])

  return useMemo<GeneralSettingsPanelProps>(
    () => buildGeneralSettingsPanelProps({
      language,
      adminTokenSettings,
      adminAccessError,
      resetting,
      ssoSettings,
      tavilySettings,
      onLanguageChange: setLanguage,
      onSaveGeneral: handleSaveGeneral,
      onClearTavilyKey: handleClearTavilyKey,
      onResetAgents: handleResetAgents,
    }),
    [
      adminAccessError,
      adminTokenSettings,
      handleClearTavilyKey,
      handleResetAgents,
      handleSaveGeneral,
      language,
      resetting,
      setLanguage,
      ssoSettings,
      tavilySettings,
    ],
  )
}
