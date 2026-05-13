import React from 'react'
import { RefreshCw } from 'lucide-react'
import { AdminTokenPanel } from '../admin/AdminTokenPanel'
import { Button } from '../ui/Button'
import type { AppLanguage } from '../../stores/chatStore'
import { useI18n } from '../../i18n'
import { CloudModelProfilesPanel } from './CloudModelProfilesPanel'
import { SsoSettingsPanel, type SsoSettingsPanelProps } from './SsoSettingsPanel'
import { TavilySettingsPanel } from './TavilySettingsPanel'

export interface GeneralSettingsPanelProps {
  language: AppLanguage
  adminToken: string
  adminTokenSaved: boolean
  adminAccessError: string | null
  authStatusText: string | null
  tavilyKey: string
  tavilyKeySet: boolean
  saving: boolean
  saveOk: boolean
  saveError: string | null
  resetting: boolean
  ssoSettings: SsoSettingsPanelProps
  onLanguageChange: (language: AppLanguage) => void
  onAdminTokenChange: (value: string) => void
  onSaveAdminToken: () => void
  onClearAdminToken: () => void
  onTavilyKeyChange: (value: string) => void
  onSaveGeneral: () => void
  onClearTavilyKey: () => void
  onResetAgents: () => void
}

export function GeneralSettingsPanel({
  language,
  adminToken,
  adminTokenSaved,
  adminAccessError,
  authStatusText,
  tavilyKey,
  tavilyKeySet,
  saving,
  saveOk,
  saveError,
  resetting,
  ssoSettings,
  onLanguageChange,
  onAdminTokenChange,
  onSaveAdminToken,
  onClearAdminToken,
  onTavilyKeyChange,
  onSaveGeneral,
  onClearTavilyKey,
  onResetAgents,
}: GeneralSettingsPanelProps) {
  const { t } = useI18n()

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">{t('settings.language.title')}</h3>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              {t('settings.language.description')}
            </p>
          </div>
          <div className="flex rounded-lg border border-bg-border bg-bg-primary/70 p-1">
            {(['zh-CN', 'en-US'] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => onLanguageChange(value)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  language === value
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                }`}
                aria-pressed={language === value}
                data-testid={`settings-language-${value}`}
              >
                {value === 'zh-CN' ? t('settings.language.zh') : t('settings.language.en')}
              </button>
            ))}
          </div>
        </div>
      </div>

      <AdminTokenPanel
        token={adminToken}
        saved={adminTokenSaved}
        error={adminAccessError}
        title={t('settings.adminToken.title')}
        placeholder={t('settings.adminToken.placeholder')}
        statusText={authStatusText}
        description={t('settings.adminToken.description')}
        onTokenChange={onAdminTokenChange}
        onSave={onSaveAdminToken}
        onClear={onClearAdminToken}
      />

      <SsoSettingsPanel {...ssoSettings} />

      <TavilySettingsPanel
        tavilyKey={tavilyKey}
        tavilyKeySet={tavilyKeySet}
        saving={saving}
        saveOk={saveOk}
        saveError={saveError}
        onTavilyKeyChange={onTavilyKeyChange}
        onSaveGeneral={onSaveGeneral}
        onClearTavilyKey={onClearTavilyKey}
      />

      <div className="pt-2 flex items-center gap-3">
        <Button
          variant="ghost"
          onClick={onResetAgents}
          loading={resetting}
          title={t('settings.general.resetAgentsTitle')}
        >
          <RefreshCw size={13} />
          {t('settings.general.resetAgents')}
        </Button>
      </div>

      <CloudModelProfilesPanel />
    </div>
  )
}
