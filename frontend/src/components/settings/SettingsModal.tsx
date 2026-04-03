import React, { useEffect, useState, useCallback } from 'react'
import {
  Upload, CheckCircle, AlertCircle, RefreshCw, Database, Plus, Pencil, Trash2,
  UserCog, Check, Activity, Search, ChevronDown, ChevronUp, Zap, HardDrive, FileText as FileIcon,
} from 'lucide-react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import {
  getConfig, saveConfig, uploadDocuments, getDocStats, resetAgents,
  getSystemPrompts, createSystemPromptWithKB, updateSystemPromptWithKB,
  deleteSystemPrompt, activateSystemPrompt,
  getKnowledgeBases, getKBHealth, testKBRetrieval, deleteKnowledgeBase,
} from '../../api/client'
import type {
  DocStats,
  SystemPrompt,
  KnowledgeBase,
  KBHealthData,
  RetrievalTestResult,
  DashboardTemplateConfig,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { useTaskStore } from '../../stores/taskStore'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

type Tab = 'general' | 'documents' | 'roles' | 'kb_monitor'

const BUILTIN_TEMPLATES = [
  {
    name: '企业知识库助手',
    content: '你是一个企业知识库助手，可以查询内部文档和联网搜索。请根据用户问题选择合适的工具来回答，回答时请引用信息来源。',
  },
  {
    name: '代码审查专家',
    content: '你是一位资深代码审查专家。分析代码质量、安全漏洞、性能问题和最佳实践，提供具体可行的改进建议。',
  },
  {
    name: '文档撰写助理',
    content: '你是一位专业的技术文档撰写助理。协助用户编写清晰、结构化的技术文档、API 说明和用户手册。',
  },
]

const DEFAULT_DASHBOARD_TEMPLATE: DashboardTemplateConfig = {
  title_hint: '知识库数据洞察',
  focus_metrics: [],
  preferred_charts: ['bar', 'line', 'pie'],
  section_order: ['summary', 'metrics', 'charts', 'table', 'evidence', 'warnings'],
  audience_tone: '专业、直观、适合业务汇报',
}

const SECTION_ORDER_OPTIONS: DashboardTemplateConfig['section_order'] = [
  'summary',
  'metrics',
  'charts',
  'table',
  'evidence',
  'warnings',
]

function normalizeDashboardTemplate(
  template?: Partial<DashboardTemplateConfig> | null,
): DashboardTemplateConfig {
  return {
    title_hint: template?.title_hint?.trim() || DEFAULT_DASHBOARD_TEMPLATE.title_hint,
    focus_metrics: Array.isArray(template?.focus_metrics)
      ? template!.focus_metrics.filter(Boolean)
      : DEFAULT_DASHBOARD_TEMPLATE.focus_metrics,
    preferred_charts: Array.isArray(template?.preferred_charts) && template!.preferred_charts.length > 0
      ? template!.preferred_charts.filter((item): item is 'bar' | 'line' | 'pie' => ['bar', 'line', 'pie'].includes(item))
      : DEFAULT_DASHBOARD_TEMPLATE.preferred_charts,
    section_order: Array.isArray(template?.section_order) && template!.section_order.length > 0
      ? template!.section_order.filter((item): item is 'summary' | 'metrics' | 'charts' | 'table' | 'evidence' | 'warnings' =>
          SECTION_ORDER_OPTIONS.includes(item),
        )
      : DEFAULT_DASHBOARD_TEMPLATE.section_order,
    audience_tone: template?.audience_tone?.trim() || DEFAULT_DASHBOARD_TEMPLATE.audience_tone,
  }
}

function StatusDot({ status }: { status: 'healthy' | 'empty' | 'not_found' | 'error' }) {
  const color = status === 'healthy' ? 'bg-accent-green' : status === 'empty' ? 'bg-yellow-400' : 'bg-accent-red'
  const label = status === 'healthy' ? '健康' : status === 'empty' ? '空' : status === 'not_found' ? '未找到' : '错误'
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2 h-2 rounded-full ${color}`} />
      <span className="text-xs">{label}</span>
    </span>
  )
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ open, onClose }) => {
  const [tab, setTab] = useState<Tab>('general')
  const [tavilyKey, setTavilyKey] = useState('')
  const [tavilyKeySet, setTavilyKeySet] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveOk, setSaveOk] = useState(false)

  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [stats, setStats] = useState<DocStats | null>(null)
  const [loadingStats, setLoadingStats] = useState(false)

  const [resetting, setResetting] = useState(false)

  // Roles tab state
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [loadingPrompts, setLoadingPrompts] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [promptName, setPromptName] = useState('')
  const [promptContent, setPromptContent] = useState('')
  const [promptVectorStoreId, setPromptVectorStoreId] = useState('')
  const [promptDashboardTitleHint, setPromptDashboardTitleHint] = useState(DEFAULT_DASHBOARD_TEMPLATE.title_hint)
  const [promptDashboardAudienceTone, setPromptDashboardAudienceTone] = useState(DEFAULT_DASHBOARD_TEMPLATE.audience_tone)
  const [promptDashboardFocusMetrics, setPromptDashboardFocusMetrics] = useState('')
  const [promptDashboardSectionOrder, setPromptDashboardSectionOrder] = useState(
    DEFAULT_DASHBOARD_TEMPLATE.section_order.join('\n'),
  )
  const [promptPreferredCharts, setPromptPreferredCharts] = useState<Array<'bar' | 'line' | 'pie'>>(
    DEFAULT_DASHBOARD_TEMPLATE.preferred_charts,
  )
  const [promptSaving, setPromptSaving] = useState(false)
  const [activatingId, setActivatingId] = useState<string | null>(null)
  const [activateStatus, setActivateStatus] = useState<Record<string, string>>({})
  const [deletingPromptId, setDeletingPromptId] = useState<string | null>(null)

  // Knowledge bases list for dropdown
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [loadingKBs, setLoadingKBs] = useState(false)

  // KB Monitor tab state
  const [kbHealth, setKbHealth] = useState<KBHealthData | null>(null)
  const [loadingKBHealth, setLoadingKBHealth] = useState(false)
  const [testQuery, setTestQuery] = useState('')
  const [testResult, setTestResult] = useState<RetrievalTestResult | null>(null)
  const [testingRetrieval, setTestingRetrieval] = useState(false)
  const [showDocList, setShowDocList] = useState(false)
  const [deletingKB, setDeletingKB] = useState(false)
  const [deleteKBConfirm, setDeleteKBConfirm] = useState(false)
  const [deleteKBPath, setDeleteKBPath] = useState<string | null>(null)
  const [kbActionError, setKbActionError] = useState<string | null>(null)

  const { setActivePromptId } = useChatStore()
  const addTask = useTaskStore((s) => s.addTask)
  const startPolling = useTaskStore((s) => s.startPolling)

  const loadConfig = useCallback(async () => {
    try {
      const cfg = await getConfig()
      setTavilyKeySet(cfg.tavily_api_key_set)
    } catch {
      // ignore
    }
  }, [])

  const loadPrompts = useCallback(async () => {
    setLoadingPrompts(true)
    try {
      const list = await getSystemPrompts()
      setPrompts(list)
    } catch {
      // ignore
    } finally {
      setLoadingPrompts(false)
    }
  }, [])

  const loadKnowledgeBases = useCallback(async () => {
    setLoadingKBs(true)
    try {
      const list = await getKnowledgeBases()
      setKnowledgeBases(list)
    } catch {
      // ignore
    } finally {
      setLoadingKBs(false)
    }
  }, [])

  const loadKBHealth = useCallback(async () => {
    setLoadingKBHealth(true)
    setKbActionError(null)
    try {
      const health = await getKBHealth()
      setKbHealth(health)
      setKbActionError(null)
    } catch (e) {
      setKbActionError((e as Error).message)
      setKbHealth(null)
    } finally {
      setLoadingKBHealth(false)
    }
  }, [])

  useEffect(() => {
    if (open) {
      loadConfig()
      loadPrompts()
    }
  }, [open, loadConfig, loadPrompts])

  useEffect(() => {
    if (open && tab === 'roles') {
      loadKnowledgeBases()
    }
  }, [open, tab, loadKnowledgeBases])

  useEffect(() => {
    if (open && tab === 'kb_monitor') {
      loadKBHealth()
    }
  }, [open, tab, loadKBHealth])

  const handleSaveGeneral = async () => {
    setSaving(true)
    try {
      await saveConfig({ tavily_api_key: tavilyKey || undefined })
      setSaveOk(true)
      setTimeout(() => setSaveOk(false), 2500)
      await loadConfig()
    } finally {
      setSaving(false)
    }
  }

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadResult(null)
    try {
      const result = await uploadDocuments(Array.from(files))
      addTask({
        task_id: result.task_id,
        task_type: result.task_type,
        status: result.status as 'pending' | 'running' | 'completed' | 'failed',
        progress: 0,
        created_at: Date.now() / 1000,
        updated_at: Date.now() / 1000,
      })
      startPolling(result.task_id)
      setUploadResult({ ok: true, message: `${result.message}，任务 ID: ${result.task_id}` })
    } catch (e) {
      setUploadResult({ ok: false, message: (e as Error).message })
    } finally {
      setUploading(false)
    }
  }

  const loadStats = async () => {
    setLoadingStats(true)
    try {
      const s = await getDocStats()
      setStats(s)
    } catch (e) {
      setStats({ status: '获取失败: ' + (e as Error).message })
    } finally {
      setLoadingStats(false)
    }
  }

  const handleResetAgents = async () => {
    setResetting(true)
    try {
      await resetAgents()
    } finally {
      setResetting(false)
    }
  }

  const startEdit = (prompt: SystemPrompt) => {
    setEditingPrompt(prompt)
    setIsCreating(false)
    setPromptName(prompt.name)
    setPromptContent(prompt.content)
    setPromptVectorStoreId(prompt.vector_store_id ?? '')
    const dashboardTemplate = normalizeDashboardTemplate(prompt.dashboard_template)
    setPromptDashboardTitleHint(dashboardTemplate.title_hint)
    setPromptDashboardAudienceTone(dashboardTemplate.audience_tone)
    setPromptDashboardFocusMetrics(dashboardTemplate.focus_metrics.join('\n'))
    setPromptDashboardSectionOrder(dashboardTemplate.section_order.join('\n'))
    setPromptPreferredCharts(dashboardTemplate.preferred_charts)
  }

  const startCreate = (template?: { name: string; content: string }) => {
    setEditingPrompt(null)
    setIsCreating(true)
    setPromptName(template?.name ?? '')
    setPromptContent(template?.content ?? '')
    setPromptVectorStoreId('')
    const dashboardTemplate = normalizeDashboardTemplate()
    setPromptDashboardTitleHint(dashboardTemplate.title_hint)
    setPromptDashboardAudienceTone(dashboardTemplate.audience_tone)
    setPromptDashboardFocusMetrics('')
    setPromptDashboardSectionOrder(dashboardTemplate.section_order.join('\n'))
    setPromptPreferredCharts(dashboardTemplate.preferred_charts)
  }

  const cancelEdit = () => {
    setEditingPrompt(null)
    setIsCreating(false)
    setPromptName('')
    setPromptContent('')
    setPromptVectorStoreId('')
    setPromptDashboardTitleHint(DEFAULT_DASHBOARD_TEMPLATE.title_hint)
    setPromptDashboardAudienceTone(DEFAULT_DASHBOARD_TEMPLATE.audience_tone)
    setPromptDashboardFocusMetrics('')
    setPromptDashboardSectionOrder(DEFAULT_DASHBOARD_TEMPLATE.section_order.join('\n'))
    setPromptPreferredCharts(DEFAULT_DASHBOARD_TEMPLATE.preferred_charts)
  }

  const buildDashboardTemplatePayload = (): DashboardTemplateConfig => {
    const focusMetrics = promptDashboardFocusMetrics
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean)

    const sectionOrder = promptDashboardSectionOrder
      .split('\n')
      .map((item) => item.trim())
      .filter((item): item is DashboardTemplateConfig['section_order'][number] =>
        SECTION_ORDER_OPTIONS.includes(item as DashboardTemplateConfig['section_order'][number]),
      )

    return normalizeDashboardTemplate({
      title_hint: promptDashboardTitleHint,
      audience_tone: promptDashboardAudienceTone,
      focus_metrics: focusMetrics,
      preferred_charts: promptPreferredCharts,
      section_order: sectionOrder,
    })
  }

  const handleSavePrompt = async () => {
    if (!promptName.trim() || !promptContent.trim()) return
    setPromptSaving(true)
    try {
      const dashboardTemplate = buildDashboardTemplatePayload()
      if (isCreating) {
        await createSystemPromptWithKB(
          promptName.trim(),
          promptContent.trim(),
          promptVectorStoreId || undefined,
          dashboardTemplate,
        )
      } else if (editingPrompt) {
        await updateSystemPromptWithKB(
          editingPrompt.id,
          promptName.trim(),
          promptContent.trim(),
          promptVectorStoreId || undefined,
          dashboardTemplate,
        )
      }
      await loadPrompts()
      cancelEdit()
    } finally {
      setPromptSaving(false)
    }
  }

  const handleActivate = async (id: string) => {
    setActivatingId(id)
    try {
      const result = await activateSystemPrompt(id)
      setActivePromptId(id)
      if (result.kb_status) {
        setActivateStatus((prev) => ({ ...prev, [id]: result.kb_status! }))
        setTimeout(() => setActivateStatus((prev) => { const n = { ...prev }; delete n[id]; return n }), 4000)
      }
      await loadPrompts()
    } finally {
      setActivatingId(null)
    }
  }

  const handleDeletePrompt = async (id: string) => {
    setDeletingPromptId(id)
    try {
      await deleteSystemPrompt(id)
      await loadPrompts()
    } finally {
      setDeletingPromptId(null)
    }
  }

  const handleTestRetrieval = async () => {
    if (!testQuery.trim()) return
    setTestingRetrieval(true)
    setTestResult(null)
    try {
      const result = await testKBRetrieval(testQuery)
      setTestResult(result)
    } catch (e) {
      setTestResult({ results_count: 0, latency_ms: 0, error: (e as Error).message })
    } finally {
      setTestingRetrieval(false)
    }
  }

  const handleDeleteKB = async (path?: string) => {
    const targetPath = path ?? null
    if (!deleteKBConfirm || deleteKBPath !== targetPath) {
      setDeleteKBConfirm(true)
      setDeleteKBPath(targetPath)
      setTimeout(() => { setDeleteKBConfirm(false); setDeleteKBPath(null) }, 4000)
      return
    }
    setDeletingKB(true)
    setKbActionError(null)
    setDeleteKBConfirm(false)
    setDeleteKBPath(null)
    try {
      await deleteKnowledgeBase(path)
      setKbHealth(null)
      setStats(null)
      await loadKnowledgeBases()
      await loadKBHealth()
    } catch (e) {
      alert('删除失败: ' + (e as Error).message)
    } finally {
      setDeletingKB(false)
    }
  }

  const tabs: [Tab, string][] = [
    ['general', '通用设置'],
    ['documents', '知识库文档'],
    ['roles', '角色管理'],
    ['kb_monitor', '知识库监控'],
  ]

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="设置"
      width={tab === 'roles' || tab === 'kb_monitor' ? 'max-w-4xl' : 'max-w-xl'}
    >
      {/* Tabs */}
      <div className="mb-5 flex flex-wrap gap-1 rounded-lg bg-bg-tertiary p-1">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`min-w-[6rem] flex-1 rounded-md py-1.5 text-xs font-medium transition-colors ${
              tab === id
                ? 'bg-bg-secondary text-text-primary shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {kbActionError && tab === 'kb_monitor' && (
        <div className="mb-4 rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {kbActionError}
        </div>
      )}

      {/* ── General Tab ── */}
      {tab === 'general' && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-secondary uppercase tracking-wide mb-2">
              Tavily 联网搜索 API Key
            </label>
            <div className="flex gap-2">
              <input
                className="input-base flex-1 text-sm"
                type="password"
                placeholder={tavilyKeySet ? '已配置（留空保持不变）' : 'tvly-xxxxxxxxxxxxxxxx'}
                value={tavilyKey}
                onChange={(e) => setTavilyKey(e.target.value)}
              />
            </div>
            <p className="text-[11px] text-text-secondary mt-1.5">
              获取地址：
              <a href="https://app.tavily.com" target="_blank" rel="noopener noreferrer" className="text-accent-blue hover:underline">
                app.tavily.com
              </a>
              {tavilyKeySet && <span className="ml-2 text-accent-green">· 已配置 ✓</span>}
            </p>
          </div>

          <div className="pt-2 flex items-center gap-3">
            <Button variant="primary" onClick={handleSaveGeneral} loading={saving}>
              {saveOk ? <CheckCircle size={14} /> : null}
              {saveOk ? '已保存' : '保存配置'}
            </Button>
            <Button variant="ghost" onClick={handleResetAgents} loading={resetting} title="清空 Agent 缓存，下次请求重新构建">
              <RefreshCw size={13} />
              重置 Agent 缓存
            </Button>
          </div>

          <div className="pt-3 border-t border-bg-border">
            <p className="text-xs text-text-secondary">
              模型配置（Provider / Model / Base URL / API Key / Temperature）可通过各聊天面板顶部的模型选择器分别设置。
            </p>
          </div>
        </div>
      )}

      {/* ── Documents Tab ── */}
      {tab === 'documents' && (
        <div className="space-y-4">
          {/* Upload area */}
          <div
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
              dragOver ? 'border-accent-blue bg-accent-blue/5' : 'border-bg-border hover:border-accent-blue/50'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => { e.preventDefault(); setDragOver(false); handleUpload(e.dataTransfer.files) }}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <input
              id="file-input"
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.md,.csv,.txt,.xlsx,.xls"
              className="hidden"
              onChange={(e) => handleUpload(e.target.files)}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-2">
                <span className="w-8 h-8 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-text-secondary">上传中…</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload size={28} className="text-text-secondary/50" />
                <p className="text-sm text-text-primary">拖放文件到此处，或点击选择</p>
                <p className="text-xs text-text-secondary">支持 PDF、Word、Markdown、CSV、TXT、Excel（单文件 ≤ 10 MB，大文件分批处理不卡顿）</p>
                <p className="text-xs text-text-secondary/60 mt-0.5">简历/结构化文档自动按章节智能分块，检索更完整</p>
              </div>
            )}
          </div>

          {uploadResult && (
            <div className={`flex items-start gap-2.5 p-3 rounded-lg text-sm ${
              uploadResult.ok
                ? 'bg-accent-green/10 border border-accent-green/30 text-accent-green'
                : 'bg-accent-red/10 border border-accent-red/30 text-accent-red'
            }`}>
              {uploadResult.ok ? <CheckCircle size={15} className="shrink-0 mt-0.5" /> : <AlertCircle size={15} className="shrink-0 mt-0.5" />}
              {uploadResult.message}
            </div>
          )}

          <div className="flex gap-2 flex-wrap">
            <Button variant="ghost" onClick={loadStats} loading={loadingStats} className="gap-2">
              <Database size={13} />
              查看统计
            </Button>
            <Button
              variant="ghost"
              onClick={() => handleDeleteKB()}
              loading={deletingKB}
              className={`gap-2 ${deleteKBConfirm && deleteKBPath === null ? 'text-accent-red border-accent-red/40' : ''}`}
            >
              <Trash2 size={13} />
              {deleteKBConfirm && deleteKBPath === null ? '确认删除?' : '删除知识库'}
            </Button>
          </div>

          {stats && (
            <div className="bg-bg-tertiary rounded-lg p-3 text-xs space-y-1.5">
              <div className="flex justify-between">
                <span className="text-text-secondary">状态</span>
                <span className="text-text-primary">{stats.status}</span>
              </div>
              {stats.total_docs !== undefined && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">文档片段数</span>
                  <span className="text-text-primary">{stats.total_docs}</span>
                </div>
              )}
              {stats.store_path && (
                <div className="flex justify-between">
                  <span className="text-text-secondary">存储路径</span>
                  <span className="text-text-primary truncate max-w-[200px]">{stats.store_path}</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Roles Tab ── */}
      {tab === 'roles' && (
        <div className="space-y-4">
          {(isCreating || editingPrompt) ? (
            <div className="grid gap-4 rounded-xl border border-bg-border bg-bg-tertiary p-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
              <p className="text-xs font-medium text-text-primary lg:col-span-2">
                {isCreating ? '新建角色' : `编辑：${editingPrompt?.name}`}
              </p>
              <input
                className="input-base w-full text-sm"
                placeholder="角色名称"
                value={promptName}
                onChange={(e) => setPromptName(e.target.value)}
                maxLength={40}
              />
              <div className="relative lg:row-span-3">
                <textarea
                  className="input-base w-full text-sm resize-none leading-relaxed"
                  placeholder="System Prompt 内容，描述 AI 的角色、能力和回答风格…"
                  value={promptContent}
                  onChange={(e) => setPromptContent(e.target.value)}
                  rows={5}
                />
                <span className="absolute bottom-2 right-2.5 text-[10px] text-text-secondary/40">
                  {promptContent.length} 字
                </span>
              </div>

              {/* Knowledge base binding */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  知识库挂载
                  <span className="ml-1.5 text-text-secondary/50 font-normal">（可选，切换角色时自动加载）</span>
                </label>
                {loadingKBs ? (
                  <span className="text-xs text-text-secondary">加载知识库列表…</span>
                ) : (
                  <select
                    className="input-base w-full text-sm"
                    value={promptVectorStoreId}
                    onChange={(e) => setPromptVectorStoreId(e.target.value)}
                  >
                    <option value="">不绑定（使用默认知识库）</option>
                    {knowledgeBases.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name} ({kb.doc_count} 片段){!kb.has_index ? ' ⚠️ 无索引' : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="rounded-lg border border-bg-border bg-bg-primary/30 p-3 space-y-3 lg:row-span-3">
                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">
                    仪表盘标题提示
                  </label>
                  <input
                    className="input-base w-full text-sm"
                    placeholder="例如：管理层经营分析看板"
                    value={promptDashboardTitleHint}
                    onChange={(e) => setPromptDashboardTitleHint(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">
                    受众语气
                  </label>
                  <input
                    className="input-base w-full text-sm"
                    placeholder="例如：专业、简洁、适合管理层汇报"
                    value={promptDashboardAudienceTone}
                    onChange={(e) => setPromptDashboardAudienceTone(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">
                    关注指标
                    <span className="ml-1.5 text-text-secondary/50 font-normal">（每行一个）</span>
                  </label>
                  <textarea
                    className="input-base w-full text-sm resize-none leading-relaxed"
                    rows={4}
                    placeholder={'例如：\n销售额\n客户数\n渠道占比'}
                    value={promptDashboardFocusMetrics}
                    onChange={(e) => setPromptDashboardFocusMetrics(e.target.value)}
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">
                    偏好图表
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {(['bar', 'line', 'pie'] as const).map((chartType) => {
                      const checked = promptPreferredCharts.includes(chartType)
                      const label = chartType === 'bar' ? '柱状图' : chartType === 'line' ? '折线图' : '饼图'
                      return (
                        <button
                          key={chartType}
                          type="button"
                          onClick={() =>
                            setPromptPreferredCharts((current) => {
                              if (checked) {
                                const next = current.filter((item) => item !== chartType)
                                return next.length > 0 ? next : current
                              }
                              return [...current, chartType]
                            })
                          }
                          className={`px-2.5 py-1 rounded-lg text-[11px] border transition-colors ${
                            checked
                              ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
                              : 'border-bg-border text-text-secondary hover:text-text-primary'
                          }`}
                        >
                          {label}
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-text-secondary mb-1.5">
                    展示顺序
                    <span className="ml-1.5 text-text-secondary/50 font-normal">（每行一个 section）</span>
                  </label>
                  <textarea
                    className="input-base w-full text-sm resize-none leading-relaxed"
                    rows={6}
                    value={promptDashboardSectionOrder}
                    onChange={(e) => setPromptDashboardSectionOrder(e.target.value)}
                    placeholder={'summary\nmetrics\ncharts\ntable\nevidence\nwarnings'}
                  />
                  <p className="mt-1 text-[11px] text-text-secondary/55">
                    可用值：summary、metrics、charts、table、evidence、warnings
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap gap-2 pt-1 lg:col-span-2">
                <Button variant="primary" onClick={handleSavePrompt} loading={promptSaving} disabled={!promptName.trim() || !promptContent.trim()}>
                  保存
                </Button>
                <Button variant="ghost" onClick={cancelEdit}>
                  取消
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-xs text-text-secondary">选择激活的 AI 角色，切换后下次对话生效</p>
              <Button variant="outline" onClick={() => startCreate()} className="gap-1.5 text-xs">
                <Plus size={12} />
                新建角色
              </Button>
            </div>
          )}

          {loadingPrompts ? (
            <div className="flex justify-center py-6">
              <span className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="space-y-2">
              {prompts.map((p) => (
                <div
                  key={p.id}
                  className={`rounded-xl border px-4 py-3 transition-colors ${
                    p.is_active
                      ? 'border-accent-blue/50 bg-accent-blue/5'
                      : 'border-bg-border bg-bg-tertiary/40 hover:bg-bg-tertiary/70'
                  }`}
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <UserCog size={13} className={p.is_active ? 'text-accent-blue' : 'text-text-secondary'} />
                        <span className="text-sm font-medium text-text-primary truncate">{p.name}</span>
                        {p.is_active && (
                          <span className="text-[10px] bg-accent-blue/20 text-accent-blue px-1.5 py-0.5 rounded-full font-medium shrink-0">
                            当前使用
                          </span>
                        )}
                        {p.is_default && (
                          <span className="text-[10px] text-text-secondary/50 shrink-0">内置</span>
                        )}
                        {p.vector_store_id && (
                          <span className="text-[10px] bg-accent-green/15 text-accent-green px-1.5 py-0.5 rounded-full shrink-0 flex items-center gap-1">
                            <Database size={9} />
                            已绑定 KB
                          </span>
                        )}
                        {p.dashboard_template && Object.keys(p.dashboard_template).length > 0 && (
                          <span className="text-[10px] bg-accent-blue/15 text-accent-blue px-1.5 py-0.5 rounded-full shrink-0 flex items-center gap-1">
                            <Zap size={9} />
                            仪表盘模板
                          </span>
                        )}
                        {activateStatus[p.id] && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${
                            activateStatus[p.id] === 'loaded'
                              ? 'bg-accent-green/15 text-accent-green'
                              : activateStatus[p.id] === 'error'
                              ? 'bg-accent-red/15 text-accent-red'
                              : 'bg-bg-tertiary text-text-secondary'
                          }`}>
                            KB: {activateStatus[p.id] === 'loaded' ? '已加载' : activateStatus[p.id] === 'error' ? '加载失败' : activateStatus[p.id]}
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-text-secondary mt-1 line-clamp-2 leading-relaxed">
                        {p.content}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0 self-end sm:self-auto">
                      {!p.is_active && (
                        <button
                          onClick={() => handleActivate(p.id)}
                          disabled={activatingId === p.id}
                          className="p-1.5 rounded-lg text-text-secondary hover:text-accent-blue hover:bg-accent-blue/10 transition-colors"
                          title="设为当前角色"
                        >
                          {activatingId === p.id ? (
                            <span className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin block" />
                          ) : (
                            <Check size={13} />
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => startEdit(p)}
                        className="p-1.5 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
                        title="编辑"
                      >
                        <Pencil size={12} />
                      </button>
                      {!p.is_default && (
                        <button
                          onClick={() => handleDeletePrompt(p.id)}
                          disabled={deletingPromptId === p.id}
                          className="p-1.5 rounded-lg text-text-secondary hover:text-accent-red hover:bg-accent-red/10 transition-colors"
                          title="删除"
                        >
                          {deletingPromptId === p.id ? (
                            <span className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin block" />
                          ) : (
                            <Trash2 size={12} />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {!isCreating && !editingPrompt && (
            <div className="pt-2 border-t border-bg-border">
              <p className="text-[11px] text-text-secondary mb-2">快速套用模板</p>
              <div className="flex flex-wrap gap-2">
                {BUILTIN_TEMPLATES.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => startCreate(t)}
                    className="px-2.5 py-1 rounded-lg text-[11px] border border-bg-border text-text-secondary hover:text-text-primary hover:border-accent-blue/40 hover:bg-accent-blue/5 transition-colors"
                  >
                    + {t.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── KB Monitor Tab ── */}
      {tab === 'kb_monitor' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Activity size={14} className="text-accent-blue" />
              知识库健康监控
            </h3>
            <Button variant="ghost" onClick={loadKBHealth} loading={loadingKBHealth} className="gap-1.5 text-xs">
              <RefreshCw size={12} />
              刷新
            </Button>
          </div>

          {loadingKBHealth && !kbHealth && (
            <div className="flex justify-center py-8">
              <span className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {kbHealth && (
            <>
              {/* Status overview */}
              <div className="bg-bg-tertiary rounded-xl p-4 space-y-3 border border-bg-border">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">索引状态</span>
                  <StatusDot status={kbHealth.index_status} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary flex items-center gap-1.5">
                    <Database size={11} />
                    切片总数
                  </span>
                  <span className="text-sm font-semibold text-text-primary">{kbHealth.total_chunks.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary flex items-center gap-1.5">
                    <HardDrive size={11} />
                    占用磁盘
                  </span>
                  <span className="text-xs text-text-primary">{kbHealth.store_size_mb} MB</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">Embedding 模型</span>
                  <span className="text-[11px] text-text-primary/70 truncate max-w-[180px]">{kbHealth.embedding_model}</span>
                </div>
                {kbHealth.last_updated && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-secondary">最后更新</span>
                    <span className="text-[11px] text-text-primary/70">
                      {new Date(kbHealth.last_updated * 1000).toLocaleString('zh-CN')}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">存储路径</span>
                  <span className="text-[11px] text-text-primary/70 truncate max-w-[180px]">{kbHealth.store_path}</span>
                </div>
              </div>

              {/* Document breakdown */}
              {kbHealth.documents.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowDocList((v) => !v)}
                    className="flex items-center gap-1.5 text-xs text-accent-blue/80 hover:text-accent-blue transition-colors mb-2"
                  >
                    {showDocList ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    文档列表 ({kbHealth.documents.length} 个文件)
                  </button>
                  {showDocList && (
                    <div className="rounded-lg border border-bg-border overflow-hidden text-xs">
                      <div className="bg-bg-tertiary/60 px-3 py-1.5 grid grid-cols-2 border-b border-bg-border">
                        <span className="text-text-secondary/70 font-medium">文件名</span>
                        <span className="text-text-secondary/70 font-medium text-right">切片数</span>
                      </div>
                      {kbHealth.documents.map((doc, i) => (
                        <div
                          key={i}
                          className="px-3 py-1.5 grid grid-cols-2 border-b border-bg-border/50 last:border-0 hover:bg-bg-hover/10"
                        >
                          <span className="text-text-primary/80 truncate flex items-center gap-1.5">
                            <FileIcon size={10} className="text-text-secondary/50 shrink-0" />
                            {doc.name}
                          </span>
                          <span className="text-text-secondary text-right">{doc.chunks}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Test retrieval */}
              <div className="border-t border-bg-border pt-4">
                <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <Zap size={11} />
                  检索诊断测试
                </h4>
                <div className="flex gap-2">
                  <input
                    className="input-base flex-1 text-sm"
                    placeholder="输入测试查询文本…"
                    value={testQuery}
                    onChange={(e) => setTestQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleTestRetrieval()}
                  />
                  <Button variant="primary" onClick={handleTestRetrieval} loading={testingRetrieval} disabled={!testQuery.trim()}>
                    <Search size={13} />
                    测试
                  </Button>
                </div>
                {testResult && (
                  <div className="mt-3 bg-bg-tertiary rounded-lg p-3 space-y-2">
                    {testResult.error ? (
                      <p className="text-xs text-accent-red">{testResult.error}</p>
                    ) : (
                      <>
                        <div className="flex gap-4 text-xs">
                          <span className="text-text-secondary">命中数：<span className="text-text-primary font-medium">{testResult.results_count}</span></span>
                          <span className="text-text-secondary">延迟：<span className="text-text-primary font-medium">{testResult.latency_ms} ms</span></span>
                        </div>
                        {testResult.top_results && testResult.top_results.length > 0 && (
                          <div className="space-y-1.5 mt-2">
                            {testResult.top_results.map((r, i) => (
                              <div key={i} className="bg-bg-secondary/60 rounded-md p-2">
                                <p className="text-[11px] font-medium text-accent-blue/80 mb-0.5">{r.source}</p>
                                <p className="text-[11px] text-text-secondary/80 leading-relaxed">{r.snippet}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Delete KB */}
              <div className="border-t border-bg-border pt-4">
                <Button
                  variant="ghost"
                  onClick={() => handleDeleteKB()}
                  loading={deletingKB}
                  className={`gap-2 w-full justify-center ${deleteKBConfirm && deleteKBPath === null ? 'text-accent-red border border-accent-red/40 bg-accent-red/5' : 'text-accent-red/60 hover:text-accent-red'}`}
                >
                  <Trash2 size={13} />
                  {deleteKBConfirm && deleteKBPath === null ? '再次点击确认删除知识库' : '删除当前知识库'}
                </Button>
                <p className="text-[11px] text-text-secondary/50 text-center mt-1">
                  此操作不可恢复，将删除所有向量索引文件
                </p>
              </div>
            </>
          )}

          {!kbHealth && !loadingKBHealth && (
            <div className="flex flex-col items-center gap-3 py-8 text-text-secondary/50">
              <Database size={32} />
              <p className="text-sm">知识库未初始化或无法访问</p>
              <Button variant="ghost" onClick={loadKBHealth}>重新检测</Button>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
