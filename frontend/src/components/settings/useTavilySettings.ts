import { useCallback, useRef, useState } from 'react'

import { saveConfig } from '../../api/client'
import { useI18n } from '../../i18n'

const TAVILY_SAVED_VISIBLE_MS = 2500

type ConfigSavedCallback = () => Promise<void> | void

export interface TavilySettingsController {
  tavilyKey: string
  tavilyKeySet: boolean
  saving: boolean
  saveOk: boolean
  saveError: string | null
  setTavilyKey: (value: string) => void
  setTavilyKeySet: (value: boolean) => void
  setSaveError: (message: string | null) => void
  saveTavilyKey: (onConfigSaved: ConfigSavedCallback) => Promise<void>
  clearTavilyKey: (onConfigSaved: ConfigSavedCallback) => Promise<void>
}

export function useTavilySettings(): TavilySettingsController {
  const { t } = useI18n()
  const [tavilyKey, setTavilyKey] = useState('')
  const [tavilyKeySet, setTavilyKeySet] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveOk, setSaveOk] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const savedStatusTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const showSavedStatus = useCallback(() => {
    if (savedStatusTimer.current) {
      clearTimeout(savedStatusTimer.current)
    }
    setSaveOk(true)
    savedStatusTimer.current = setTimeout(() => {
      setSaveOk(false)
      savedStatusTimer.current = null
    }, TAVILY_SAVED_VISIBLE_MS)
  }, [])

  const persistTavilyKey = useCallback(
    async (nextKey: string | undefined, fallbackError: string, onConfigSaved: ConfigSavedCallback) => {
      setSaving(true)
      setSaveError(null)
      try {
        await saveConfig({ tavily_api_key: nextKey })
        setTavilyKey('')
        showSavedStatus()
        await onConfigSaved()
      } catch (e) {
        setSaveError((e as Error).message || fallbackError)
      } finally {
        setSaving(false)
      }
    },
    [showSavedStatus],
  )

  const saveTavilyKey = useCallback(
    async (onConfigSaved: ConfigSavedCallback) => {
      await persistTavilyKey(
        tavilyKey || undefined,
        t('settings.tavily.saveError'),
        onConfigSaved,
      )
    },
    [persistTavilyKey, t, tavilyKey],
  )

  const clearTavilyKey = useCallback(
    async (onConfigSaved: ConfigSavedCallback) => {
      await persistTavilyKey('', t('settings.tavily.clearError'), onConfigSaved)
    },
    [persistTavilyKey, t],
  )

  return {
    tavilyKey,
    tavilyKeySet,
    saving,
    saveOk,
    saveError,
    setTavilyKey,
    setTavilyKeySet,
    setSaveError,
    saveTavilyKey,
    clearTavilyKey,
  }
}
