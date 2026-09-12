import React, { useEffect, useState } from 'react'
import { Cpu } from 'lucide-react'
import { useI18n } from '../../i18n'
import { Modal } from '../ui/Modal'
import { ModelProviderSidebar } from './ModelProviderSidebar'
import { ModelProviderDetail } from './ModelProviderDetail'
import { useModelProviderController } from './useModelProviderController'

interface ModelProviderModalProps {
  open: boolean
  onClose: () => void
}

export const ModelProviderModal: React.FC<ModelProviderModalProps> = ({ open, onClose }) => {
  const { t } = useI18n()
  const ctrl = useModelProviderController()
  const [mobilePane, setMobilePane] = useState<'list' | 'detail'>('list')

  useEffect(() => {
    if (!open) {
      setMobilePane('list')
    }
  }, [open])

  const handleClose = () => {
    setMobilePane('list')
    onClose()
  }

  const handleSelectProvider = (providerId: string) => {
    ctrl.setSelectedId(providerId)
    setMobilePane('detail')
  }

  const handleConfirmAdd = () => {
    ctrl.addCustomProvider()
    setMobilePane('detail')
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={t('modelProviders.title')}
      closeLabel={t('modelProviders.close')}
      titleIcon={<Cpu size={18} className="text-text-secondary" />}
      width="max-w-4xl"
      contentClassName="flex h-[calc(100svh-5rem)] max-h-[36rem] min-h-0 min-w-0 overflow-hidden p-0 sm:h-[calc(100svh-6rem)]"
    >
      <div
        data-testid="model-provider-list-pane"
        className={`${mobilePane === 'list' ? 'flex' : 'hidden'} min-h-0 min-w-0 flex-1 md:flex md:w-60 md:flex-none`}
      >
        <ModelProviderSidebar
          items={ctrl.displayList}
          selectedId={ctrl.selectedId}
          onSelect={handleSelectProvider}
          addingCustom={ctrl.addingCustom}
          onStartAdd={() => ctrl.setAddingCustom(true)}
          onCancelAdd={() => ctrl.setAddingCustom(false)}
          customName={ctrl.customName}
          onCustomNameChange={ctrl.setCustomName}
          customBaseUrl={ctrl.customBaseUrl}
          onCustomBaseUrlChange={ctrl.setCustomBaseUrl}
          onConfirmAdd={handleConfirmAdd}
          catalogStatus={ctrl.catalogStatus}
          onRetryCatalog={ctrl.reloadCatalog}
        />
      </div>
      <div
        data-testid="model-provider-detail-pane"
        className={`${mobilePane === 'detail' ? 'flex' : 'hidden'} min-h-0 min-w-0 flex-1 md:flex`}
      >
        <ModelProviderDetail
          provider={ctrl.selected}
          apiKeyDraft={ctrl.apiKeyDraft}
          onApiKeyChange={ctrl.setApiKeyDraft}
          apiKeySaving={ctrl.apiKeySaving}
          apiKeyClearing={ctrl.apiKeyClearing}
          apiKeyFeedback={ctrl.apiKeyFeedback}
          showApiKey={ctrl.showApiKey}
          onToggleShowApiKey={() => ctrl.setShowApiKey(!ctrl.showApiKey)}
          onSaveApiKey={ctrl.saveApiKey}
          onClearApiKey={ctrl.clearApiKey}
          enabled={ctrl.selected?.enabled ?? false}
          onToggleEnabled={ctrl.toggleEnabled}
          onDelete={ctrl.deleteSelected}
          healthChecking={ctrl.healthChecking}
          healthResult={ctrl.healthResult}
          onHealthCheck={ctrl.runHealthCheck}
          onBack={() => setMobilePane('list')}
        />
      </div>
    </Modal>
  )
}
