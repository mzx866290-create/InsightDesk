import React, { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Database, Layers3, Palette } from 'lucide-react'
import { getConnectionTypeLabel, getDeliveryTemplateCatalog } from '../../api/client'
import type { DeliveryTemplateItem, ModelConfig } from '../../api/client'
import { Button } from '../ui/Button'
import { Modal } from '../ui/Modal'

interface PanelOption {
  id: string
  modelConfig: ModelConfig
}

interface DeckGenerationModalProps {
  open: boolean
  panels: PanelOption[]
  knowledgeBaseEnabled: boolean
  initialPanelId?: string
  initialTheme?: 'default' | 'midnight' | 'sunrise'
  initialSlideCount?: number
  onClose: () => void
  onSubmit: (payload: {
    panel_config: ModelConfig
    target_slide_count: number
    theme: 'default' | 'midnight' | 'sunrise'
    template_id?: string
    template_options?: Record<string, unknown>
  }) => Promise<void> | void
}

const DECK_THEMES = [
  {
    value: 'default',
    label: '经典蓝图',
    description: '清爽蓝白，适合通用汇报。',
    preview: 'from-slate-50 via-white to-blue-50 border-blue-100',
  },
  {
    value: 'midnight',
    label: '深夜简报',
    description: '深色高对比，适合战略或技术汇报。',
    preview: 'from-slate-950 via-slate-900 to-sky-950 border-slate-700',
  },
  {
    value: 'sunrise',
    label: '晨曦回顾',
    description: '暖色评审风格，适合复盘和业务回顾。',
    preview: 'from-orange-50 via-amber-50 to-rose-100 border-orange-200',
  },
] as const

type DeckTheme = (typeof DECK_THEMES)[number]['value']

function isDeckTheme(value: unknown): value is DeckTheme {
  return value === 'default' || value === 'midnight' || value === 'sunrise'
}

function safeSlideCount(value: unknown, fallback: number): number {
  const next = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : fallback
  if (!Number.isFinite(next)) return fallback
  return Math.max(4, Math.min(10, Math.floor(next)))
}

export const DeckGenerationModal: React.FC<DeckGenerationModalProps> = ({
  open,
  panels,
  knowledgeBaseEnabled,
  initialPanelId,
  initialTheme = 'default',
  initialSlideCount = 8,
  onClose,
  onSubmit,
}) => {
  const [selectedPanelId, setSelectedPanelId] = useState('')
  const [targetSlideCount, setTargetSlideCount] = useState(8)
  const [selectedTheme, setSelectedTheme] = useState<'default' | 'midnight' | 'sunrise'>('default')
  const [templates, setTemplates] = useState<DeliveryTemplateItem[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [templateLoading, setTemplateLoading] = useState(false)
  const [templateError, setTemplateError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!open) return
    setSelectedPanelId(initialPanelId || panels[0]?.id || '')
    setTargetSlideCount(Math.max(4, Math.min(10, initialSlideCount)))
    setSelectedTheme(initialTheme)
    setSelectedTemplateId('')
  }, [initialPanelId, initialSlideCount, initialTheme, open, panels])

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setTemplateLoading(true)
    setTemplateError(null)
    void getDeliveryTemplateCatalog()
      .then((catalog) => {
        if (cancelled) return
        setTemplates(catalog.templates.filter((template) => template.artifact_type === 'deck'))
      })
      .catch((error) => {
        if (cancelled) return
        setTemplateError((error as Error).message || 'Failed to load delivery templates.')
        setTemplates([])
      })
      .finally(() => {
        if (!cancelled) setTemplateLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const selectedPanel = panels.find((panel) => panel.id === selectedPanelId) ?? panels[0] ?? null
  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === selectedTemplateId) ?? null,
    [selectedTemplateId, templates],
  )

  const selectTemplate = (template: DeliveryTemplateItem | null) => {
    setSelectedTemplateId(template?.id ?? '')
    if (!template) {
      setTargetSlideCount(Math.max(4, Math.min(10, initialSlideCount)))
      setSelectedTheme(initialTheme)
      return
    }
    setTargetSlideCount(
      safeSlideCount(template.suggested_options['target_slide_count'], targetSlideCount),
    )
    if (isDeckTheme(template.suggested_options['theme'])) {
      setSelectedTheme(template.suggested_options['theme'])
    }
  }

  const handleSubmit = async () => {
    if (!selectedPanel) return
    setSubmitting(true)
    try {
      await onSubmit({
        panel_config: selectedPanel.modelConfig,
        target_slide_count: targetSlideCount,
        theme: selectedTheme,
        template_id: selectedTemplate?.id,
        template_options: selectedTemplate?.suggested_options,
      })
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal open={open} onClose={() => !submitting && onClose()} title="生成演示稿" width="max-w-2xl">
      <div className="space-y-5" data-testid="deck-generation-modal">
        <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <Layers3 size={16} />
            Delivery template
          </div>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            选择一个产品化 Deck 模板会自动套用建议页数、主题和生成参数；不选择则沿用工作区默认配置。
          </p>

          {templateError && (
            <div className="mt-3 flex items-center gap-2 rounded-xl border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-xs text-amber-200">
              <AlertTriangle size={13} />
              {templateError}
            </div>
          )}

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => selectTemplate(null)}
              data-testid="deck-template-custom"
              className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                !selectedTemplateId
                  ? 'border-accent-blue/40 bg-accent-blue/10'
                  : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
              }`}
            >
              <div className="text-sm font-medium text-text-primary">Custom defaults</div>
              <p className="mt-2 text-xs leading-5 text-text-secondary">
                使用当前工作区的默认主题和页数。
              </p>
            </button>

            {templateLoading && (
              <div className="rounded-2xl border border-bg-border bg-bg-secondary px-4 py-3 text-xs text-text-secondary">
                Loading templates...
              </div>
            )}

            {!templateLoading && templates.map((template) => {
              const active = template.id === selectedTemplateId
              return (
                <button
                  key={template.id}
                  type="button"
                  onClick={() => selectTemplate(template)}
                  data-testid="deck-template-option"
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

        <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <Layers3 size={16} />
            最终面板
          </div>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            选择这次真正负责生成 PPT 成稿的模型面板。系统会用这个面板的模型配置做大纲规划和整稿生成。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {panels.map((panel, index) => {
              const active = panel.id === selectedPanelId
              return (
                <button
                  key={panel.id}
                  type="button"
                  onClick={() => setSelectedPanelId(panel.id)}
                  className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                    active
                      ? 'border-accent-blue/40 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
                  }`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-text-primary">面板 {index + 1}</span>
                    <span className="text-[11px] uppercase tracking-wide text-text-secondary">
                      {getConnectionTypeLabel(panel.modelConfig)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-text-primary/90">{panel.modelConfig.model}</p>
                  <p className="mt-1 truncate text-xs text-text-secondary">{panel.modelConfig.base_url}</p>
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_220px]">
          <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
              <Database size={16} />
              当前来源模式
            </div>
            <p className="mt-2 text-sm text-text-primary">
              {knowledgeBaseEnabled ? '知识库 + 成功聊天答案' : '仅成功聊天答案'}
            </p>
            <p className="mt-1 text-xs leading-5 text-text-secondary">
              {knowledgeBaseEnabled
                ? '开启知识库时会严格依赖检索结果；证据不足会直接拦截，不再退回纯聊天模式。'
                : '未开启知识库时只会使用成功回答生成主题页，并在成稿里标记为 chat_only。'}
            </p>
          </div>

          <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
            <label className="text-sm font-medium text-text-primary">目标页数</label>
            <input
              type="number"
              min={4}
              max={10}
              value={targetSlideCount}
              onChange={(event) => {
                const next = Number(event.target.value)
                if (Number.isNaN(next)) return
                setTargetSlideCount(Math.max(4, Math.min(10, next)))
              }}
              className="mt-3 w-full rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent-blue/40"
            />
            <p className="mt-2 text-xs leading-5 text-text-secondary">
              默认 8 页。系统会宁少勿水，内容不足时会自动缩页，不会硬凑空话。
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-bg-border bg-bg-primary/60 p-4">
          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
            <Palette size={16} />
            主题模板
          </div>
          <p className="mt-2 text-sm leading-6 text-text-secondary">
            先选定视觉方向，生成后仍可在编辑器里继续切换。
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {DECK_THEMES.map((theme) => {
              const active = theme.value === selectedTheme
              return (
                <button
                  key={theme.value}
                  type="button"
                  onClick={() => setSelectedTheme(theme.value)}
                  className={`rounded-2xl border px-3 py-3 text-left transition-colors ${
                    active
                      ? 'border-accent-blue/40 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-secondary hover:border-accent-blue/25 hover:bg-bg-hover'
                  }`}
                >
                  <div className={`h-20 rounded-xl border bg-gradient-to-br ${theme.preview}`} />
                  <div className="mt-3 text-sm font-medium text-text-primary">{theme.label}</div>
                  <p className="mt-1 text-xs leading-5 text-text-secondary">{theme.description}</p>
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
            disabled={!selectedPanel}
            data-testid="deck-generation-submit"
          >
            开始生成
          </Button>
        </div>
      </div>
    </Modal>
  )
}
