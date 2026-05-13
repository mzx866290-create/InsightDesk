import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, FileText, Presentation, RefreshCw, Trash2 } from 'lucide-react'

import {
  getDeliveryTemplateCatalog,
  installDeliveryTemplateManifest,
  uninstallDeliveryTemplateManifest,
  type DeliveryTemplateCatalogResponse,
  type DeliveryTemplateManifest,
} from '../../api/client'
import { Button } from '../ui/Button'

const DEFAULT_DELIVERY_TEMPLATE_MANIFEST = JSON.stringify({
  id: 'sales_readout',
  version: '1.0.0',
  name: 'Sales Readout',
  description: 'Sales team readout deck.',
  artifact_type: 'deck',
  category: 'sales',
  tags: ['sales', 'deck'],
  target_format: 'pptx',
  preview: 'Pipeline -> Risks -> Actions',
  suggested_options: {
    target_slide_count: 6,
    theme: 'midnight',
  },
  metadata: {
    owner: 'sales',
  },
}, null, 2)

function formatOptionValue(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(', ')
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return ''
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function parseDeliveryTemplateManifestDraft(rawDraft: string): DeliveryTemplateManifest {
  const parsed = JSON.parse(rawDraft) as unknown
  const manifest = isRecord(parsed) && isRecord(parsed.manifest)
    ? parsed.manifest
    : parsed
  if (!isRecord(manifest)) {
    throw new Error('Delivery template manifest must be a JSON object.')
  }
  return manifest as unknown as DeliveryTemplateManifest
}

export const DeliveryTemplateCatalogPanel: React.FC = () => {
  const [catalog, setCatalog] = useState<DeliveryTemplateCatalogResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [uninstallingId, setUninstallingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [manifestDraft, setManifestDraft] = useState(DEFAULT_DELIVERY_TEMPLATE_MANIFEST)

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setCatalog(await getDeliveryTemplateCatalog())
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to load delivery templates'))
    } finally {
      setLoading(false)
    }
  }, [])

  const installManifest = useCallback(async () => {
    setInstalling(true)
    setError(null)
    setMessage(null)
    try {
      const manifest = parseDeliveryTemplateManifestDraft(manifestDraft)
      const nextCatalog = await installDeliveryTemplateManifest({ manifest })
      setCatalog(nextCatalog)
      const installedId = nextCatalog.installed?.id || manifest.id || 'template'
      setMessage(`Installed ${installedId}; template code execution: no.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to install delivery template manifest'))
    } finally {
      setInstalling(false)
    }
  }, [manifestDraft])

  const uninstallManifest = useCallback(async (templateId: string) => {
    const normalizedId = templateId.trim()
    if (!normalizedId) return
    setUninstallingId(normalizedId)
    setError(null)
    setMessage(null)
    try {
      const nextCatalog = await uninstallDeliveryTemplateManifest(normalizedId)
      setCatalog(nextCatalog)
      const uninstalledId = nextCatalog.uninstalled?.id || normalizedId
      setMessage(`Uninstalled ${uninstalledId}; manifest deleted: yes.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err || 'Failed to uninstall delivery template manifest'))
    } finally {
      setUninstallingId(null)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  const templates = catalog?.templates ?? []
  const manifestIssues = catalog?.manifests.issues ?? []
  const manifestIssueCount = catalog?.manifests.issue_count ?? manifestIssues.length
  const categories = useMemo(
    () => Array.from(new Set(templates.map((template) => template.category).filter(Boolean))).sort(),
    [templates],
  )

  return (
    <div className="space-y-4" data-testid="settings-delivery-template-catalog-panel">
      <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
              <Presentation size={15} className="text-accent-blue" />
              Delivery template catalog
            </h3>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              Productized report and Deck/PPT templates. Manifest templates are declarative only; no template code is executed.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadCatalog}
            loading={loading}
            data-testid="settings-delivery-template-refresh"
          >
            <RefreshCw size={12} />
            Refresh
          </Button>
        </div>

        {catalog && (
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-text-secondary" data-testid="settings-delivery-template-summary">
            <span>Total: <b className="text-text-primary">{catalog.summary.total}</b></span>
            <span>Built-in: <b className="text-text-primary">{catalog.summary.builtin}</b></span>
            <span>Manifests: <b className="text-text-primary">{catalog.summary.manifest}</b></span>
            <span>Reports: <b className="text-text-primary">{catalog.summary.report}</b></span>
            <span>Decks: <b className="text-text-primary">{catalog.summary.deck}</b></span>
            <span>Scanned: <b className="text-text-primary">{catalog.manifests.scanned_count}</b></span>
            <span>Issues: <b className={manifestIssueCount > 0 ? 'text-amber-300' : 'text-text-primary'}>{manifestIssueCount}</b></span>
          </div>
        )}

        {categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1 text-[10px] text-text-secondary">
            {categories.map((category) => (
              <span key={category} className="rounded-full bg-bg-secondary px-2 py-0.5">
                {category}
              </span>
            ))}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red" data-testid="settings-delivery-template-error">
          {error}
        </div>
      )}

      <div className="rounded-xl border border-bg-border bg-bg-tertiary/20 p-4" data-testid="settings-delivery-template-install-panel">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h4 className="text-sm font-semibold text-text-primary">Install delivery template manifest</h4>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              Paste a report or Deck/PPT template manifest. The backend persists JSON only; no template code is executed.
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={installManifest}
            loading={installing}
            data-testid="settings-delivery-template-install-submit"
          >
            Install manifest
          </Button>
        </div>
        <textarea
          value={manifestDraft}
          onChange={(event) => setManifestDraft(event.target.value)}
          className="mt-3 h-44 w-full rounded-lg border border-bg-border bg-bg-primary p-3 font-mono text-xs leading-5 text-text-primary outline-none focus:border-accent-blue"
          spellCheck={false}
          data-testid="settings-delivery-template-manifest-input"
        />
        {message && (
          <div className="mt-2 rounded-lg border border-accent-green/30 bg-accent-green/10 px-3 py-2 text-xs text-accent-green" data-testid="settings-delivery-template-success">
            {message}
          </div>
        )}
      </div>

      {manifestIssues.length > 0 && (
        <div className="rounded-xl border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-text-secondary" data-testid="settings-delivery-template-manifest-issues">
          <div className="mb-2 flex items-center gap-2 font-medium text-amber-300">
            <AlertTriangle size={13} />
            Template manifest issues
          </div>
          <div className="space-y-2">
            {manifestIssues.map((issue, index) => (
              <div key={`${issue.file}-${issue.code}-${index}`} className="rounded-lg bg-bg-primary/50 px-2 py-1.5">
                <p className="font-medium text-text-primary">{issue.file || 'catalog manifest'}</p>
                <p className="mt-0.5">
                  {issue.code || 'invalid'}: {issue.message || 'Manifest was skipped.'}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {templates.map((template) => {
          const isManifest = Boolean(template.metadata?.manifest)
          const optionEntries = Object.entries(template.suggested_options ?? {})
            .map(([key, value]) => [key, formatOptionValue(value)] as const)
            .filter(([, value]) => value)

          return (
            <div
              key={template.id}
              className="rounded-xl border border-bg-border bg-bg-tertiary/20 p-4"
              data-testid="settings-delivery-template-row"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h4 className="flex items-center gap-2 text-sm font-medium text-text-primary">
                    {template.artifact_type === 'deck' ? <Presentation size={13} /> : <FileText size={13} />}
                    {template.name}
                  </h4>
                  <p className="mt-1 text-xs leading-5 text-text-secondary">{template.description}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${isManifest ? 'bg-accent-blue/10 text-accent-blue' : 'bg-bg-secondary text-text-secondary'}`}>
                    {isManifest ? 'Manifest' : 'Built-in'}
                  </span>
                  {isManifest && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => uninstallManifest(template.id)}
                      loading={uninstallingId === template.id}
                      disabled={installing || Boolean(uninstallingId)}
                      data-testid={`settings-delivery-template-uninstall-${template.id}`}
                    >
                      <Trash2 size={12} />
                      Uninstall
                    </Button>
                  )}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-1">
                <span className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                  {template.artifact_type}
                </span>
                <span className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                  {template.target_format}
                </span>
                {template.tags.map((tag) => (
                  <span key={tag} className="rounded-full bg-bg-secondary px-2 py-0.5 text-[10px] text-text-secondary">
                    {tag}
                  </span>
                ))}
              </div>

              {template.preview && (
                <p className="mt-3 rounded-lg bg-bg-secondary/50 px-2 py-1.5 text-[11px] leading-5 text-text-secondary">
                  {template.preview}
                </p>
              )}

              {optionEntries.length > 0 && (
                <div className="mt-3 space-y-1 text-[11px] text-text-secondary">
                  {optionEntries.map(([key, value]) => (
                    <p key={key}>
                      {key}: <b className="text-text-primary">{value}</b>
                    </p>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {!loading && !error && templates.length === 0 && (
        <div className="rounded-lg border border-bg-border bg-bg-tertiary/20 px-3 py-4 text-center text-xs text-text-secondary">
          No delivery templates are registered yet.
        </div>
      )}
    </div>
  )
}
