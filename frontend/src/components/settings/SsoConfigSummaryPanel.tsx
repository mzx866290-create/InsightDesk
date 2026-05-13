import React from 'react'

import type { SsoConfig } from '../../api/client'
import type { TranslationKey } from '../../i18n'

export interface SsoConfigSummaryPanelProps {
  config: SsoConfig | null
  t: (key: TranslationKey) => string
}

export const SsoConfigSummaryPanel: React.FC<SsoConfigSummaryPanelProps> = ({ config, t }) => (
  <>
    <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-text-secondary">
      <span>
        {t('settings.sso.summaryProvider')}:{' '}
        <span className="text-text-primary">{config?.provider ?? '-'}</span>
      </span>
      <span>
        {t('settings.sso.summaryMode')}:{' '}
        <span className="text-text-primary">{config?.mode ?? '-'}</span>
      </span>
      <span>
        {t('settings.sso.summaryAuthUrl')}:{' '}
        <span className="text-text-primary">
          {config?.authorization_endpoint_configured
            ? t('settings.sso.summarySet')
            : t('settings.sso.summaryMissing')}
        </span>
      </span>
      <span>
        {t('settings.sso.summaryJwks')}:{' '}
        <span className="text-text-primary">
          {config?.jwks_url_configured ? t('settings.sso.summarySet') : t('settings.sso.summaryMissing')}
        </span>
      </span>
    </div>
    {config?.allowed_domains.length ? (
      <p className="mt-2 text-[11px] text-text-secondary">
        {t('settings.sso.summaryAllowedDomains')}: {config.allowed_domains.join(', ')}
      </p>
    ) : null}
  </>
)
