import React from 'react'

import type { SsoConfig } from '../../api/client'
import type { TranslationKey } from '../../i18n'
import type { SsoConfigForm, SsoConfigFormChangeHandler } from './ssoSettingsModel'
import { SsoConfigTextField } from './SsoConfigTextField'

interface SsoClientFieldsProps {
  config: SsoConfig | null
  form: SsoConfigForm
  t: (key: TranslationKey) => string
  onFormChange: SsoConfigFormChangeHandler
}

export const SsoClientFields: React.FC<SsoClientFieldsProps> = ({
  config,
  form,
  t,
  onFormChange,
}) => (
  <>
    <SsoConfigTextField
      labelKey="settings.sso.clientId"
      testId="settings-sso-client-id-input"
      value={form.client_id}
      placeholder="insightdesk"
      t={t}
      onChange={(value) => onFormChange('client_id', value)}
    />

    <div>
      <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
        {t('settings.sso.clientSecret')}
      </label>
      <input
        data-testid="settings-sso-client-secret-input"
        className="input-base w-full text-sm"
        type="password"
        value={form.client_secret}
        onChange={(event) => onFormChange('client_secret', event.target.value)}
        placeholder={config?.client_secret_configured
          ? t('settings.sso.clientSecretConfiguredPlaceholder')
          : t('settings.sso.clientSecretOptionalPlaceholder')}
      />
      <label className="mt-2 flex items-center gap-2 text-[11px] text-text-secondary">
        <input
          data-testid="settings-sso-clear-client-secret-input"
          type="checkbox"
          checked={form.clear_client_secret}
          onChange={(event) => onFormChange('clear_client_secret', event.target.checked)}
          className="accent-accent-blue"
        />
        {t('settings.sso.clearClientSecret')}
      </label>
    </div>

    <SsoConfigTextField
      labelKey="settings.sso.scopes"
      testId="settings-sso-scopes-input"
      value={form.scopes}
      placeholder="openid email profile"
      t={t}
      onChange={(value) => onFormChange('scopes', value)}
    />
    <SsoConfigTextField
      labelKey="settings.sso.sessionTtlSeconds"
      testId="settings-sso-session-ttl-input"
      type="number"
      min={300}
      max={604800}
      value={form.session_ttl_seconds}
      t={t}
      onChange={(value) => onFormChange('session_ttl_seconds', Number(value || 28800))}
    />
    <SsoConfigTextField
      className="md:col-span-2"
      labelKey="settings.sso.allowedEmailDomains"
      testId="settings-sso-allowed-domains-input"
      value={form.allowed_domains}
      placeholder="example.com, ops.example.com"
      t={t}
      onChange={(value) => onFormChange('allowed_domains', value)}
    />
  </>
)
