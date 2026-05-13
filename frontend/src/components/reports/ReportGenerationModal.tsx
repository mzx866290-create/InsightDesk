import React, { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, FileText } from 'lucide-react'

import { getDeliveryTemplateCatalog } from '../../api/client'
import type { DeliveryTemplateItem } from '../../api/client'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'

interface ReportGenerationModalProps {
  open: boolean
  onClose: () => void
  onSubmit: (payload: {
    template_id?: string
    template_options?: Record<string, unknown>
  }) => Promise<void> | void
}

export const ReportGenerationModal: React.FC<ReportGenerationModalProps> = ({
  open,
  onClose,
  onSubmit,
}) => {
  const [templates, setTemplates] = useState<DeliveryTemplateItem[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setSelectedTemplateId('')
    setLoading(true)
    setError(null)
    void getDeliveryTemplateCatalog()
      .then((catalog) => {
        if (cancelled) return
        setTemplates(catalog.templates.filter((template) => template.artifact_type === 'report'))
      })
      .catch((catalogError) => {
        if (cancelled) return
        setError((catalogError as Error).message || 'Failed to load delivery templates.')
        setTemplates([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) ?? null,
    [selectedTemplateId, templates],
  )

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await onSubmit({
        template_id: selectedTemplate?.id,
        template_options: selectedTemplate?.suggested_options,
      })
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => !submitting && onClose()}
      title="生成报告"
      width="max-w-2xl"
    >
      <div className="space-y-5" data-testid="report-generation-modal">
        <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <FileText size={16} />
            Delivery template
          </div>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            选择报告模板会把模板 ID 和建议参数传入生成任务；不选择则沿用当前默认报告结构。
          </p>

          {error && (
            <div
              className="mt-3 flex items-center gap-2 rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-200"
              data-testid="report-template-error"
            >
              <AlertTriangle size={13} />
              {error}
            </div>
          )}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setSelectedTemplateId('')}
              data-testid="report-template-custom"
              className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                !selectedTemplateId
                  ? 'border-accent-blue/40 bg-accent-blue/10'
                  : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
              }`}
            >
              <div className="text-sm font-medium text-text-primary">Custom defaults</div>
              <p className="mt-2 text-xs leading-5 text-text-secondary">
                使用当前默认报告结构，不附加模板参数。
              </p>
            </button>

            {loading && (
              <div className="rounded-2xl border border-bg-border bg-bg-secondary px-4 py-3 text-xs text-text-secondary">
                Loading templates...
              </div>
            )}

            {!loading &&
              templates.map((template) => {
                const active = template.id === selectedTemplateId
                return (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => setSelectedTemplateId(template.id)}
                    data-testid="report-template-option"
                    data-template-id={template.id}
                    className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                      active
                        ? 'border-accent-blue/40 bg-accent-blue/10'
                        : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-text-primary">{template.name}</span>
                      <span className="rounded-full bg-bg-tertiary px-2 py-0.5 text-[10px] text-text-secondary">
                        {template.target_format}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-text-secondary">{template.description}</p>
                    {template.preview && (
                      <p className="mt-2 text-[11px] text-text-secondary/80">{template.preview}</p>
                    )}
                  </button>
                )
              })}
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={() => void handleSubmit()}
            loading={submitting}
            data-testid="report-generation-submit"
          >
            开始生成
          </Button>
        </div>
      </div>
    </Modal>
  )
}
