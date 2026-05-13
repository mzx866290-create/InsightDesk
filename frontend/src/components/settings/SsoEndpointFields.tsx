import React from 'react'

import type { TranslationKey } from '../../i18n'
import type { SsoConfigForm, SsoConfigFormChangeHandler } from './ssoSettingsModel'
import { SsoConfigTextField } from './SsoConfigTextField'

interface SsoEndpointFieldsProps {
  form: SsoConfigForm
  t: (key: TranslationKey) => string
  onFormChange: SsoConfigFormChangeHandler
}

export const SsoEndpointFields: React.FC<SsoEndpointFieldsProps> = ({
  form,
  t,
  onFormChange,
}) => (
  <>
    <SsoConfigTextField
      className="md:col-span-2"
      labelKey="settings.sso.issuerUrl"
      testId="settings-sso-issuer-url-input"
      value={form.issuer_url}
      placeholder="https://idp.example.com"
      t={t}
      onChange={(value) => onFormChange('issuer_url', value)}
    />
    <SsoConfigTextField
      className="md:col-span-2"
      labelKey="settings.sso.authorizationEndpoint"
      testId="settings-sso-authorization-endpoint-input"
      value={form.authorization_endpoint}
      placeholder="https://idp.example.com/oauth2/v1/authorize"
      t={t}
      onChange={(value) => onFormChange('authorization_endpoint', value)}
    />
    <SsoConfigTextField
      labelKey="settings.sso.tokenEndpoint"
      testId="settings-sso-token-endpoint-input"
      value={form.token_endpoint}
      placeholder="https://idp.example.com/oauth2/v1/token"
      t={t}
      onChange={(value) => onFormChange('token_endpoint', value)}
    />
    <SsoConfigTextField
      labelKey="settings.sso.jwksUrl"
      testId="settings-sso-jwks-url-input"
      value={form.jwks_url}
      placeholder="https://idp.example.com/oauth2/v1/keys"
      t={t}
      onChange={(value) => onFormChange('jwks_url', value)}
    />
  </>
)
