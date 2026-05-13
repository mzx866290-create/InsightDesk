import React from 'react'

import type { SsoConfig } from '../../api/client'
import type { TranslationKey } from '../../i18n'
import { SsoClientFields } from './SsoClientFields'
import { SsoEndpointFields } from './SsoEndpointFields'
import { SsoProviderRoleFields } from './SsoProviderRoleFields'
import type { SsoConfigForm, SsoConfigFormChangeHandler } from './ssoSettingsModel'

export interface SsoConfigFormPanelProps {
  config: SsoConfig | null
  form: SsoConfigForm
  t: (key: TranslationKey) => string
  onFormChange: SsoConfigFormChangeHandler
}

export const SsoConfigFormPanel: React.FC<SsoConfigFormPanelProps> = ({
  config,
  form,
  t,
  onFormChange,
}) => (
  <div className="mt-4 grid gap-3 md:grid-cols-2">
    <SsoProviderRoleFields form={form} t={t} onFormChange={onFormChange} />
    <SsoEndpointFields form={form} t={t} onFormChange={onFormChange} />
    <SsoClientFields config={config} form={form} t={t} onFormChange={onFormChange} />
  </div>
)
