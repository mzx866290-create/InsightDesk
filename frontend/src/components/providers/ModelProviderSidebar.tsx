import React from 'react'
import { AlertCircle, GripVertical, Loader2, Plus, RefreshCw } from 'lucide-react'
import { useI18n } from '../../i18n'
import type { ProviderCatalogStatus, ProviderDisplayItem } from './modelProviderModel'

interface ModelProviderSidebarProps {
  items: ProviderDisplayItem[]
  selectedId: string | null
  onSelect: (id: string) => void
  addingCustom: boolean
  onStartAdd: () => void
  onCancelAdd: () => void
  customName: string
  onCustomNameChange: (v: string) => void
  customBaseUrl: string
  onCustomBaseUrlChange: (v: string) => void
  onConfirmAdd: () => void
  catalogStatus: ProviderCatalogStatus
  onRetryCatalog: () => void
}

export const ModelProviderSidebar: React.FC<ModelProviderSidebarProps> = ({
  items,
  selectedId,
  onSelect,
  addingCustom,
  onStartAdd,
  onCancelAdd,
  customName,
  onCustomNameChange,
  customBaseUrl,
  onCustomBaseUrlChange,
  onConfirmAdd,
  catalogStatus,
  onRetryCatalog,
}) => {
  const { t } = useI18n()

  return (
    <div className="flex h-full w-full min-w-0 flex-col md:w-60 md:shrink-0 md:border-r md:border-bg-border">
      <div className="flex-1 overflow-y-auto py-2">
        {catalogStatus === 'loading' && (
          <div
            role="status"
            aria-live="polite"
            className="mx-3 mb-2 flex items-center gap-2 rounded-lg border border-bg-border bg-bg-tertiary/40 px-3 py-2 text-xs text-text-secondary"
          >
            <Loader2 size={13} className="shrink-0 animate-spin" aria-hidden="true" />
            {t('modelProviders.catalogLoading')}
          </div>
        )}

        {catalogStatus === 'error' && (
          <div
            role="alert"
            className="mx-3 mb-2 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red"
          >
            <div className="flex items-start gap-2">
              <AlertCircle size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
              <span className="leading-5">{t('modelProviders.catalogLoadError')}</span>
            </div>
            <button
              type="button"
              onClick={onRetryCatalog}
              className="mt-2 inline-flex min-h-11 items-center gap-1.5 rounded-md border border-accent-red/30 px-2.5 py-1 text-xs font-medium transition-colors hover:bg-accent-red/10"
            >
              <RefreshCw size={12} aria-hidden="true" />
              {t('modelProviders.retry')}
            </button>
          </div>
        )}

        {catalogStatus === 'ready' && items.length === 0 && (
          <div role="status" className="px-4 py-8 text-center">
            <p className="text-sm font-medium text-text-primary">
              {t('modelProviders.catalogEmpty')}
            </p>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              {t('modelProviders.catalogEmptyHint')}
            </p>
          </div>
        )}

        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            aria-pressed={selectedId === item.id}
            className={`flex min-h-11 w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm transition-colors ${
              selectedId === item.id
                ? 'bg-accent-blue/10 text-accent-blue'
                : 'text-text-primary hover:bg-bg-hover'
            }`}
          >
            <GripVertical size={14} className="shrink-0 text-text-secondary/40" />
            <span className="text-base leading-none">{item.icon}</span>
            <span className="truncate font-medium">{item.name}</span>
          </button>
        ))}
      </div>

      <div className="border-t border-bg-border p-3">
        {addingCustom ? (
          <div className="space-y-2">
            <input
              type="text"
              value={customName}
              onChange={(e) => onCustomNameChange(e.target.value)}
              placeholder={t('modelProviders.providerName')}
              className="min-h-11 w-full rounded-lg border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent-blue focus:outline-none"
              autoFocus
            />
            <input
              type="text"
              value={customBaseUrl}
              onChange={(e) => onCustomBaseUrlChange(e.target.value)}
              placeholder={t('modelProviders.baseUrl')}
              className="min-h-11 w-full rounded-lg border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent-blue focus:outline-none"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onConfirmAdd}
                disabled={!customName.trim()}
                className="min-h-11 flex-1 rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent-blue/90 disabled:opacity-40"
              >
                {t('modelProviders.save')}
              </button>
              <button
                type="button"
                onClick={onCancelAdd}
                className="min-h-11 flex-1 rounded-lg border border-bg-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-bg-hover"
              >
                {t('modelProviders.cancel')}
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={onStartAdd}
            className="flex min-h-11 w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-bg-border px-3 py-2.5 text-sm text-text-secondary transition-colors hover:border-accent-blue hover:text-accent-blue"
          >
            <Plus size={14} />
            {t('modelProviders.addProvider')}
          </button>
        )}
      </div>
    </div>
  )
}
