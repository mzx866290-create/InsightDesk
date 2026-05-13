import { useCallback, useEffect, useRef, useState } from 'react'

import {
  getAdminApiToken,
  getAuthWhoAmI,
  saveAdminApiToken as persistAdminApiToken,
  type AuthWhoAmI,
} from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'

const ADMIN_TOKEN_SAVED_VISIBLE_MS = 2500

interface UseAdminTokenSettingsOptions {
  open: boolean
  onTokenSaved: () => Promise<void> | void
  setAdminAccessError: (message: string | null) => void
}

export interface AdminTokenSettingsController {
  adminToken: string
  adminTokenSaved: boolean
  authStatusText: string | null
  setAdminToken: (value: string) => void
  saveAdminToken: () => Promise<void>
  clearAdminToken: () => void
}

export function useAdminTokenSettings({
  open,
  onTokenSaved,
  setAdminAccessError,
}: UseAdminTokenSettingsOptions): AdminTokenSettingsController {
  const [adminToken, setAdminToken] = useState('')
  const [adminTokenSaved, setAdminTokenSaved] = useState(false)
  const [authProfile, setAuthProfile] = useState<AuthWhoAmI | null>(null)
  const [loadingAuthProfile, setLoadingAuthProfile] = useState(false)
  const savedStatusTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearSavedStatusTimer = useCallback(() => {
    if (savedStatusTimer.current) {
      clearTimeout(savedStatusTimer.current)
      savedStatusTimer.current = null
    }
  }, [])

  const showSavedStatus = useCallback(() => {
    clearSavedStatusTimer()
    setAdminTokenSaved(true)
    savedStatusTimer.current = setTimeout(() => {
      setAdminTokenSaved(false)
      savedStatusTimer.current = null
    }, ADMIN_TOKEN_SAVED_VISIBLE_MS)
  }, [clearSavedStatusTimer])

  const loadAuthProfile = useCallback(async () => {
    setLoadingAuthProfile(true)
    try {
      const profile = await getAuthWhoAmI()
      setAuthProfile(profile)
    } catch (e) {
      setAuthProfile(null)
      if (isAdminAccessError(e)) {
        setAdminAccessError((e as Error).message)
      }
    } finally {
      setLoadingAuthProfile(false)
    }
  }, [setAdminAccessError])

  const resetFromStoredToken = useCallback(() => {
    clearSavedStatusTimer()
    setAdminToken(getAdminApiToken())
    setAdminTokenSaved(false)
    setAdminAccessError(null)
    setAuthProfile(null)
  }, [clearSavedStatusTimer, setAdminAccessError])

  useEffect(() => {
    if (!open) return
    resetFromStoredToken()
    void loadAuthProfile()
  }, [loadAuthProfile, open, resetFromStoredToken])

  useEffect(() => clearSavedStatusTimer, [clearSavedStatusTimer])

  const saveAdminToken = useCallback(async () => {
    const nextToken = adminToken.trim()
    persistAdminApiToken(nextToken)
    setAdminToken(nextToken)
    showSavedStatus()
    setAdminAccessError(null)

    await loadAuthProfile()
    await onTokenSaved()
  }, [adminToken, loadAuthProfile, onTokenSaved, setAdminAccessError, showSavedStatus])

  const clearAdminToken = useCallback(() => {
    clearSavedStatusTimer()
    setAdminToken('')
    persistAdminApiToken('')
    setAdminTokenSaved(false)
    setAdminAccessError(null)
    setAuthProfile(null)
  }, [clearSavedStatusTimer, setAdminAccessError])

  const authStatusText = loadingAuthProfile
    ? '姝ｅ湪妫€鏌ヤ护鐗?..'
    : authProfile
      ? `${authProfile.role}${authProfile.user_id ? ` 路 ${authProfile.user_id}` : ''}${authProfile.is_local ? ' 路 鏈湴' : ''}`
      : null

  return {
    adminToken,
    adminTokenSaved,
    authStatusText,
    setAdminToken,
    saveAdminToken,
    clearAdminToken,
  }
}
