import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  getConfig,
  resetAgents,
} from '../../api/client'
import { useI18n } from '../../i18n'
import { isAdminAccessError } from '../admin/adminAccess'
import {
  buildGeneralSettingsControllerProps,
  type GeneralSettingsControllerProps,
} from './generalSettingsControllerModel'
import type { SettingsTab } from './SettingsNavigation'
import { shouldLoadSsoSettings } from './settingsModalControllerModel'
import { useAdminTokenSettings } from './useAdminTokenSettings'
import type { RolePromptsController } from './useRolePrompts'
import { useSsoSettings } from './useSsoSettings'
import { useTavilySettings } from './useTavilySettings'

interface UseGeneralSettingsControllerOptions {
  adminAccessError: string | null
  open: boolean
  rolePrompts: RolePromptsController
  setAdminAccessError: (message: string | null) => void
  tab: SettingsTab
}

export function useGeneralSettingsController({
  adminAccessError,
  open,
  rolePrompts,
  setAdminAccessError,
  tab,
}: UseGeneralSettingsControllerOptions): GeneralSettingsControllerProps {
  const { language, setLanguage } = useI18n()
  const [resetting, setResetting] = useState(false)
  const ssoLoadedForOpenRef = useRef(false)
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
  }, [loadConfig, rolePrompts, tab])

  const adminTokenSettings = useAdminTokenSettings({
    open,
    onTokenSaved: refreshAfterAdminTokenSaved,
    setAdminAccessError,
  })

  useEffect(() => {
    if (!open) {
      ssoLoadedForOpenRef.current = false
      return
    }
    setAdminAccessError(null)
    resetSsoSettings()
    void loadConfig()
  }, [
    loadConfig,
    open,
    resetSsoSettings,
    setAdminAccessError,
  ])

  useEffect(() => {
    if (!shouldLoadSsoSettings(open, tab, ssoLoadedForOpenRef.current)) return
    ssoLoadedForOpenRef.current = true
    void loadSsoConfig()
  }, [loadSsoConfig, open, tab])

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

  return useMemo<GeneralSettingsControllerProps>(
    () => buildGeneralSettingsControllerProps({
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
