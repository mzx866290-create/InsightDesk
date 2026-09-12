import React from 'react'

import { useI18n } from '../../i18n'
import { useChatStore } from '../../stores/chatStore'
import { Button } from '../ui/Button'
import { CloudModelProfileFormPanel } from './CloudModelProfileFormPanel'
import { CloudModelProfileListPanel } from './CloudModelProfileListPanel'
import { useCloudModelProfilesController } from './useCloudModelProfilesController'

export const CloudModelProfilesPanel: React.FC = () => {
  const { t } = useI18n()
  const setModelProviderOpen = useChatStore((state) => state.setModelProviderOpen)
  const { formProps, listProps, resetForm } = useCloudModelProfilesController()

  return (
    <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{t('settings.cloud.title')}</h3>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            {t('settings.cloud.description')}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="min-h-11"
            onClick={() => setModelProviderOpen(true)}
          >
            {t('settings.cloud.providerManager')}
          </Button>
          <Button variant="outline" size="sm" className="min-h-11" onClick={resetForm}>
            {t('settings.cloud.new')}
          </Button>
        </div>
      </div>

      <CloudModelProfileFormPanel
        {...formProps}
        t={t}
      />

      <CloudModelProfileListPanel
        {...listProps}
        t={t}
      />

      <div className="pt-3 border-t border-bg-border">
        <p className="text-xs text-text-secondary">
          {t('settings.cloud.panelOverrideHint')}
        </p>
      </div>
    </div>
  )
}
