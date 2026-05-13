import { useCallback, useEffect, useRef, useState } from 'react'

const ACTIVATE_STATUS_VISIBLE_MS = 4000

export function useRolePromptActivationState() {
  const [activatingId, setActivatingId] = useState<string | null>(null)
  const [activateStatus, setActivateStatus] = useState<Record<string, string>>({})
  const statusTimers = useRef<Record<string, number>>({})

  const clearStatusTimer = useCallback((id: string) => {
    const timer = statusTimers.current[id]
    if (timer === undefined) return

    window.clearTimeout(timer)
    delete statusTimers.current[id]
  }, [])

  const clearAllStatusTimers = useCallback(() => {
    Object.values(statusTimers.current).forEach((timer) => window.clearTimeout(timer))
    statusTimers.current = {}
  }, [])

  useEffect(() => clearAllStatusTimers, [clearAllStatusTimers])

  const showActivateStatus = useCallback((id: string, status: string) => {
    clearStatusTimer(id)
    setActivateStatus((current) => ({ ...current, [id]: status }))

    statusTimers.current[id] = window.setTimeout(() => {
      setActivateStatus((current) => {
        const next = { ...current }
        delete next[id]
        return next
      })
      delete statusTimers.current[id]
    }, ACTIVATE_STATUS_VISIBLE_MS)
  }, [clearStatusTimer])

  return {
    activatingId,
    activateStatus,
    setActivatingId,
    showActivateStatus,
  }
}
