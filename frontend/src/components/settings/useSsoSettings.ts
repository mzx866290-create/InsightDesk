import { useCallback, useState } from 'react'
import {
  getAuthSsoConfig,
  saveAuthSsoConfig,
  startAuthSsoLogin,
  type SaveSsoConfigPayload,
  type SsoConfig,
} from '../../api/client'
import {
  DEFAULT_SSO_FORM,
  ssoConfigToForm,
  type SsoConfigForm,
} from './ssoSettingsModel'

export function useSsoSettings() {
  const [config, setConfig] = useState<SsoConfig | null>(null)
  const [form, setForm] = useState<SsoConfigForm>(DEFAULT_SSO_FORM)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [loginStarting, setLoginStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = useCallback(() => {
    setConfig(null)
    setForm(DEFAULT_SSO_FORM)
    setError(null)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const nextConfig = await getAuthSsoConfig()
      setConfig(nextConfig)
      setForm(ssoConfigToForm(nextConfig))
    } catch (err) {
      setConfig(null)
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  const updateForm = useCallback(<Key extends keyof SsoConfigForm>(key: Key, value: SsoConfigForm[Key]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }, [])

  const save = useCallback(async () => {
    setSaving(true)
    setError(null)
    try {
      const payload: SaveSsoConfigPayload = {
        provider: form.provider,
        issuer_url: form.issuer_url,
        authorization_endpoint: form.authorization_endpoint,
        token_endpoint: form.token_endpoint,
        jwks_url: form.jwks_url,
        client_id: form.client_id,
        allowed_domains: form.allowed_domains,
        scopes: form.scopes,
        default_role: form.default_role,
        session_ttl_seconds: form.session_ttl_seconds,
        clear_client_secret: form.clear_client_secret,
      }
      if (form.client_secret.trim()) {
        payload.client_secret = form.client_secret.trim()
      }
      const savedConfig = await saveAuthSsoConfig(payload)
      setConfig(savedConfig)
      setForm(ssoConfigToForm(savedConfig))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }, [form])

  const startLogin = useCallback(async () => {
    setLoginStarting(true)
    setError(null)
    try {
      const payload = await startAuthSsoLogin()
      window.location.assign(payload.authorization_url)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoginStarting(false)
    }
  }, [])

  return {
    config,
    form,
    loading,
    saving,
    loginStarting,
    error,
    reset,
    load,
    updateForm,
    save,
    startLogin,
  }
}
