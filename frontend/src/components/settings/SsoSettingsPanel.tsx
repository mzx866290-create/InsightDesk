import React from 'react'
import { Check, LogIn, RefreshCw } from 'lucide-react'
import type { SsoConfig } from '../../api/client'
import type { SsoConfigForm } from './ssoSettingsModel'
import { useI18n } from '../../i18n'
import { Button } from '../ui/Button'
import { SsoConfigFormPanel } from './SsoConfigFormPanel'
import { SsoConfigSummaryPanel } from './SsoConfigSummaryPanel'

export interface SsoSettingsPanelProps {
  config: SsoConfig | null
  form: SsoConfigForm
  loading: boolean
  saving: boolean
  loginStarting: boolean
  error: string | null
  onFormChange: <Key extends keyof SsoConfigForm>(key: Key, value: SsoConfigForm[Key]) => void
  onSave: () => void
  onStartLogin: () => void
  onRefresh: () => void
}

export const SsoSettingsPanel: React.FC<SsoSettingsPanelProps> = ({
  config,
  form,
  loading,
  saving,
  loginStarting,
  error,
  onFormChange,
  onSave,
  onStartLogin,
  onRefresh,
}) => {
  const { t } = useI18n()

  return (
    <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">SSO / OIDC</h3>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            {t('settings.sso.description')}
          </p>
        </div>
        <span
          data-testid="settings-sso-status"
          className={`rounded-full px-2 py-1 text-[11px] ${
          config?.ready
            ? 'bg-accent-green/10 text-accent-green'
            : 'bg-bg-secondary text-text-secondary'
          }`}
        >
          {loading
            ? t('settings.sso.statusChecking')
            : config?.ready
              ? t('settings.sso.statusReady')
              : t('settings.sso.statusNotReady')}
        </span>
      </div>
      <SsoConfigFormPanel config={config} form={form} t={t} onFormChange={onFormChange} />
      <SsoConfigSummaryPanel config={config} t={t} />
      {error && (
        <div
          data-testid="settings-sso-error"
          className="mt-3 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
        >
          {error}
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          data-testid="settings-sso-save"
          variant="outline"
          onClick={onSave}
          loading={saving}
        >
          <Check size={14} />
          {t('settings.sso.save')}
        </Button>
        <Button
          data-testid="settings-sso-login"
          variant="primary"
          onClick={onStartLogin}
          loading={loginStarting}
          disabled={!config?.ready}
        >
          <LogIn size={14} />
          {t('settings.sso.login')}
        </Button>
        <Button
          data-testid="settings-sso-refresh"
          variant="ghost"
          onClick={onRefresh}
          loading={loading}
        >
          <RefreshCw size={14} />
          {t('settings.sso.refresh')}
        </Button>
      </div>
    </div>
  )
}
