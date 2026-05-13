import React from 'react'
import { CheckCircle } from 'lucide-react'

import { useI18n } from '../../i18n'
import { Button } from '../ui/Button'

interface TavilySettingsPanelProps {
  tavilyKey: string
  tavilyKeySet: boolean
  saving: boolean
  saveOk: boolean
  saveError: string | null
  onTavilyKeyChange: (value: string) => void
  onSaveGeneral: () => void
  onClearTavilyKey: () => void
}

export function TavilySettingsPanel({
  tavilyKey,
  tavilyKeySet,
  saving,
  saveOk,
  saveError,
  onTavilyKeyChange,
  onSaveGeneral,
  onClearTavilyKey,
}: TavilySettingsPanelProps) {
  const { t } = useI18n()

  return (
    <>
      <div>
        <label className="block text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">
          {t('settings.tavily.label')}
        </label>
        <div className="flex gap-2">
          <input
            className="input-base flex-1 text-sm"
            type="password"
            placeholder={tavilyKeySet ? t('settings.tavily.placeholderConfigured') : 'tvly-xxxxxxxxxxxxxxxx'}
            value={tavilyKey}
            onChange={(event) => onTavilyKeyChange(event.target.value)}
            data-testid="settings-tavily-key-input"
          />
        </div>
        <p className="text-[11px] text-text-secondary mt-1.5">
          {t('settings.tavily.helpPrefix')}
          <a
            href="https://app.tavily.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-blue hover:underline"
          >
            app.tavily.com
          </a>
          {tavilyKeySet && <span className="ml-2 text-accent-green">{t('settings.tavily.configured')}</span>}
        </p>
        <p className="text-[11px] text-text-secondary mt-1">
          {t('settings.tavily.keepOrClear')}
        </p>
        {saveError && (
          <div className="mt-2 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
            {saveError}
          </div>
        )}
      </div>

      <div className="pt-2 flex items-center gap-3">
        <Button variant="primary" onClick={onSaveGeneral} loading={saving}>
          {saveOk ? <CheckCircle size={14} /> : null}
          {saveOk ? t('settings.general.saved') : t('settings.general.save')}
        </Button>
        {tavilyKeySet && (
          <Button variant="ghost" onClick={onClearTavilyKey} loading={saving}>
            {t('settings.general.clearTavily')}
          </Button>
        )}
      </div>
    </>
  )
}
