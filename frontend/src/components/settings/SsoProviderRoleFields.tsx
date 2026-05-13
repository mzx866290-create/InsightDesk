import React from 'react'

import type { TranslationKey } from '../../i18n'
import type { SsoConfigForm, SsoConfigFormChangeHandler } from './ssoSettingsModel'

interface SsoProviderRoleFieldsProps {
  form: SsoConfigForm
  t: (key: TranslationKey) => string
  onFormChange: SsoConfigFormChangeHandler
}

export const SsoProviderRoleFields: React.FC<SsoProviderRoleFieldsProps> = ({
  form,
  t,
  onFormChange,
}) => (
  <>
    <div>
      <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
        {t('settings.sso.provider')}
      </label>
      <select
        data-testid="settings-sso-provider-input"
        className="input-base w-full text-sm"
        value={form.provider}
        onChange={(event) => onFormChange('provider', event.target.value === 'oidc' ? 'oidc' : 'none')}
      >
        <option value="none">{t('settings.sso.providerDisabled')}</option>
        <option value="oidc">OIDC</option>
      </select>
    </div>

    <div>
      <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
        {t('settings.sso.defaultRole')}
      </label>
      <select
        data-testid="settings-sso-default-role-input"
        className="input-base w-full text-sm"
        value={form.default_role}
        onChange={(event) => onFormChange('default_role', event.target.value as SsoConfigForm['default_role'])}
      >
        <option value="viewer">viewer</option>
        <option value="editor">editor</option>
        <option value="admin">admin</option>
      </select>
    </div>
  </>
)
