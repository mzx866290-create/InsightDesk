import React, { useEffect, useRef, useState } from 'react'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Eye,
  EyeOff,
  Heart,
  Loader2,
  Settings2,
  Trash2,
} from 'lucide-react'
import { useI18n } from '../../i18n'
import type { ProviderApiKeyFeedback, ProviderDisplayItem } from './modelProviderModel'

interface ModelProviderDetailProps {
  provider: ProviderDisplayItem | null
  apiKeyDraft: string
  onApiKeyChange: (v: string) => void
  apiKeySaving: boolean
  apiKeyClearing: boolean
  apiKeyFeedback: ProviderApiKeyFeedback
  showApiKey: boolean
  onToggleShowApiKey: () => void
  onSaveApiKey: () => void
  onClearApiKey: () => void
  enabled: boolean
  onToggleEnabled: () => void
  onDelete: () => Promise<void>
  healthChecking: boolean
  healthResult: 'ok' | 'fail' | null
  onHealthCheck: () => void
  onBack?: () => void
}

function ProviderInlineStatus({
  tone,
  children,
}: {
  tone: 'success' | 'error'
  children: React.ReactNode
}) {
  const isError = tone === 'error'

  return (
    <div
      role={isError ? 'alert' : 'status'}
      aria-live={isError ? 'assertive' : 'polite'}
      className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-xs leading-5 ${
        isError
          ? 'border-accent-red/30 bg-accent-red/10 text-accent-red'
          : 'border-accent-green/30 bg-accent-green/10 text-accent-green'
      }`}
    >
      {isError ? (
        <AlertCircle size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
      ) : (
        <CheckCircle2 size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
      )}
      <span>{children}</span>
    </div>
  )
}

export const ModelProviderDetail: React.FC<ModelProviderDetailProps> = ({
  provider,
  apiKeyDraft,
  onApiKeyChange,
  apiKeySaving,
  apiKeyClearing,
  apiKeyFeedback,
  showApiKey,
  onToggleShowApiKey,
  onSaveApiKey,
  onClearApiKey,
  enabled,
  onToggleEnabled,
  onDelete,
  healthChecking,
  healthResult,
  onHealthCheck,
  onBack,
}) => {
  const { t } = useI18n()
  const [deleteConfirming, setDeleteConfirming] = useState(false)
  const [providerDeleting, setProviderDeleting] = useState(false)
  const [providerDeleteError, setProviderDeleteError] = useState(false)
  const cancelDeleteRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    setDeleteConfirming(false)
    setProviderDeleting(false)
    setProviderDeleteError(false)
  }, [provider?.id])

  useEffect(() => {
    if (deleteConfirming) {
      cancelDeleteRef.current?.focus()
    }
  }, [deleteConfirming])

  if (!provider) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-text-secondary">
        {t('modelProviders.noModels')}
      </div>
    )
  }

  const apiKeyFeedbackText =
    apiKeyFeedback === 'saved'
      ? t('modelProviders.apiKeySaved')
      : apiKeyFeedback === 'cleared'
        ? t('modelProviders.apiKeyCleared')
        : apiKeyFeedback === 'save_error'
          ? t('modelProviders.apiKeySaveError')
          : apiKeyFeedback === 'clear_error'
            ? t('modelProviders.apiKeyClearError')
            : null
  const apiKeyFeedbackTone =
    apiKeyFeedback === 'save_error' || apiKeyFeedback === 'clear_error' ? 'error' : 'success'

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-y-auto p-4 sm:p-5">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="mb-4 inline-flex min-h-11 items-center gap-2 self-start rounded-lg px-2 text-sm text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary md:hidden"
        >
          <ArrowLeft size={16} aria-hidden="true" />
          {t('modelProviders.backToList')}
        </button>
      )}

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-2xl">{provider.icon}</span>
          <div className="min-w-0">
            <h3 className="truncate text-lg font-semibold text-text-primary">{provider.name}</h3>
            <p className="truncate text-xs text-text-secondary">{provider.slug}</p>
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 sm:justify-end">
          {!provider.isBuiltin && (
            <button
              type="button"
              onClick={() => {
                setProviderDeleteError(false)
                setDeleteConfirming(true)
              }}
              aria-label={t('modelProviders.deleteProvider')}
              aria-expanded={deleteConfirming}
              className="inline-flex h-11 w-11 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-red-500/10 hover:text-red-400"
              title={t('modelProviders.deleteProvider')}
            >
              <Trash2 size={15} aria-hidden="true" />
            </button>
          )}
          <button
            type="button"
            onClick={onToggleEnabled}
            role="switch"
            aria-checked={enabled}
            aria-label={enabled ? t('modelProviders.enabled') : t('modelProviders.disabled')}
            className="inline-flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-lg"
          >
            <span
              className={`pointer-events-none relative inline-flex h-6 w-11 rounded-full border-2 border-transparent transition-colors ${
                enabled ? 'bg-accent-blue' : 'bg-bg-border'
              }`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white shadow-sm transition-transform ${
                  enabled ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </span>
          </button>
          <span className="text-xs text-text-secondary">
            {enabled ? t('modelProviders.enabled') : t('modelProviders.disabled')}
          </span>
        </div>
      </div>

      {!provider.isBuiltin && deleteConfirming && (
        <div
          role="group"
          aria-label={t('modelProviders.deleteConfirm')}
          className="mt-4 rounded-xl border border-accent-red/30 bg-accent-red/10 p-3"
        >
          <p className="text-sm font-medium text-accent-red">
            {t('modelProviders.deleteConfirm')}
          </p>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            {t('modelProviders.deleteConfirmHint')}
          </p>
          {providerDeleteError && (
            <div className="mt-3">
              <ProviderInlineStatus tone="error">
                {t('modelProviders.deleteError')}
              </ProviderInlineStatus>
            </div>
          )}
          <div className="mt-3 flex flex-wrap justify-end gap-2">
            <button
              ref={cancelDeleteRef}
              type="button"
              onClick={() => {
                setProviderDeleteError(false)
                setDeleteConfirming(false)
              }}
              disabled={providerDeleting}
              className="min-h-11 rounded-lg border border-bg-border px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t('modelProviders.keepProvider')}
            </button>
            <button
              type="button"
              onClick={() => {
                setProviderDeleting(true)
                setProviderDeleteError(false)
                void onDelete()
                  .then(() => {
                    setDeleteConfirming(false)
                  })
                  .catch(() => {
                    setProviderDeleteError(true)
                  })
                  .finally(() => {
                    setProviderDeleting(false)
                  })
              }}
              disabled={providerDeleting}
              className="min-h-11 rounded-lg bg-accent-red px-3 py-1.5 text-xs font-medium text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {providerDeleting
                ? t('modelProviders.deletingProvider')
                : t('modelProviders.confirmDelete')}
            </button>
          </div>
        </div>
      )}

      {/* API Key */}
      <div className="mt-6">
        <div className="flex items-center justify-between">
          <label
            htmlFor="model-provider-api-key"
            className="text-xs font-semibold uppercase tracking-wide text-text-secondary"
          >
            {t('modelProviders.apiKey')}
          </label>
          {provider.apiKeyUrl && (
            <a
              href={provider.apiKeyUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex min-h-11 items-center gap-1 px-1 text-xs text-accent-blue hover:underline"
            >
              {t('modelProviders.getApiKey')}
              <ExternalLink size={12} aria-hidden="true" />
            </a>
          )}
        </div>
        <div className="mt-2 flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
          <div className="relative min-w-0 flex-1">
            <input
              id="model-provider-api-key"
              type={showApiKey ? 'text' : 'password'}
              value={apiKeyDraft}
              onChange={(e) => onApiKeyChange(e.target.value)}
              placeholder={provider.apiKeyRef ? 'sk-••••••' : t('modelProviders.apiKeyPlaceholder')}
              className="min-h-11 w-full rounded-lg border border-bg-border bg-bg-primary px-3 py-2.5 pr-12 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent-blue focus:outline-none"
            />
            <button
              type="button"
              onClick={onToggleShowApiKey}
              aria-label={
                showApiKey
                  ? t('modelProviders.hideApiKey')
                  : t('modelProviders.showApiKey')
              }
              className="absolute right-0 top-0 inline-flex h-11 w-11 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            >
              {showApiKey ? (
                <EyeOff size={15} aria-hidden="true" />
              ) : (
                <Eye size={15} aria-hidden="true" />
              )}
            </button>
          </div>
          {apiKeyDraft.trim() && (
            <button
              type="button"
              onClick={onSaveApiKey}
              disabled={apiKeySaving}
              className="min-h-11 w-full shrink-0 rounded-lg bg-accent-blue px-4 py-2.5 text-xs font-medium text-white transition-colors hover:bg-accent-blue/90 disabled:opacity-50 sm:w-auto"
            >
              {apiKeySaving ? t('modelProviders.saving') : t('modelProviders.save')}
            </button>
          )}
          {!apiKeyDraft.trim() && provider.apiKeyRef && (
            <button
              type="button"
              onClick={onClearApiKey}
              disabled={apiKeyClearing}
              className="min-h-11 w-full shrink-0 rounded-lg border border-bg-border px-4 py-2.5 text-xs font-medium text-text-secondary transition-colors hover:bg-bg-hover sm:w-auto"
            >
              {apiKeyClearing
                ? t('modelProviders.apiKeyClearing')
                : t('settings.cloud.clearKey')}
            </button>
          )}
        </div>
        {apiKeyFeedbackText && (
          <div className="mt-2">
            <ProviderInlineStatus tone={apiKeyFeedbackTone}>
              {apiKeyFeedbackText}
            </ProviderInlineStatus>
          </div>
        )}
      </div>

      {/* Base URL (for non-builtin or builtin with custom URLs) */}
      {provider.baseUrl && (
        <div className="mt-4">
          <label className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
            {t('modelProviders.baseUrl')}
          </label>
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-bg-border bg-bg-primary px-3 py-2.5">
            <span className="flex-1 truncate text-sm text-text-secondary">{provider.baseUrl}</span>
            <ExternalLink size={13} className="shrink-0 text-text-secondary/50" />
          </div>
        </div>
      )}

      {/* Model List */}
      <div className="mt-6">
        <label className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
          {t('modelProviders.modelList')}
        </label>
        <div className="mt-3 rounded-xl border border-bg-border bg-bg-tertiary/30">
          <div className="flex flex-wrap items-center gap-2 border-b border-bg-border px-4 py-2.5">
            <span
              aria-disabled="true"
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-text-disabled"
            >
              <Settings2 size={13} aria-hidden="true" />
              {t('modelProviders.manageModelsComingSoon')}
            </span>
            <button
              type="button"
              onClick={onHealthCheck}
              disabled={healthChecking}
              className="flex min-h-11 items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
            >
              {healthChecking ? (
                <Loader2 size={13} className="animate-spin" aria-hidden="true" />
              ) : (
                <Heart size={13} aria-hidden="true" />
              )}
              {healthChecking
                ? t('modelProviders.healthChecking')
                : t('modelProviders.healthCheck')}
            </button>
            <span className="w-full text-xs text-text-secondary/70 sm:ml-auto sm:w-auto">
              {t('modelProviders.noModels').replace('{count}', '0')}
            </span>
          </div>
          {healthResult && (
            <div className="px-4 pt-3">
              <ProviderInlineStatus tone={healthResult === 'ok' ? 'success' : 'error'}>
                {healthResult === 'ok'
                  ? t('modelProviders.healthOk')
                  : t('modelProviders.healthFailed')}
              </ProviderInlineStatus>
            </div>
          )}
          <div className="flex min-h-[120px] flex-col items-center justify-center gap-1.5 px-4 py-8 text-center">
            <p className="text-sm text-text-secondary">{t('modelProviders.noModels')}</p>
            <p className="text-xs text-text-secondary/70">{t('modelProviders.noModelsHint')}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
