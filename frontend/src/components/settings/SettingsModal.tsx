import React, { useEffect, useState, useCallback } from 'react'
import {
  Upload, CheckCircle, AlertCircle, RefreshCw, Database, Plus, Pencil, Trash2,
  UserCog, Check, Activity, Search, ChevronDown, ChevronUp, Zap, HardDrive, FileText as FileIcon,
  ToggleLeft, ToggleRight,
} from 'lucide-react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import {
  getConfig, saveConfig, uploadDocuments, getDocStats, resetAgents,
  getSystemPrompts, createSystemPromptWithKB, updateSystemPromptWithKB,
  deleteSystemPrompt, activateSystemPrompt,
  getKnowledgeBases, getKBHealth, getKnowledgeBaseChunks, updateKnowledgeBaseChunk,
  deleteKnowledgeBaseChunk, testKBRetrieval, deleteKnowledgeBase,
} from '../../api/client'
import type {
  DocStats,
  SystemPrompt,
  KnowledgeBase,
  KnowledgeBaseChunk,
  KBHealthData,
  RetrievalTestResult,
  DashboardTemplateConfig,
} from '../../api/client'
import { useChatStore, type CloudModelProfile } from '../../stores/chatStore'
import { useTaskStore } from '../../stores/taskStore'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

type Tab = 'general' | 'documents' | 'roles' | 'kb_monitor'

const BUILTIN_TEMPLATES = [
  {
    name: 'Enterprise KB Assistant',
    content: 'You are an enterprise knowledge base assistant. Use available tools to answer accurately and cite sources when possible.',
  },
  {
    name: '代码审查专家',
    content: 'You are a senior code review expert. Analyze quality, security, performance and maintainability, and provide concrete suggestions.',
  },
  {
    name: '文档写作助理',
    content: 'You are a professional writing assistant. Help the user produce clear, structured technical and business documents.',
  },
]

const DEFAULT_DASHBOARD_TEMPLATE: DashboardTemplateConfig = {
  enabled: true,
  title_hint: '知识看板',
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
const KB_CHUNK_PAGE_SIZE = 12

function normalizeDashboardTemplate(
  template?: Partial<DashboardTemplateConfig> | null,
): DashboardTemplateConfig {
  return {
    enabled: template?.enabled !== false,
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
  const label = status === 'healthy' ? '正常' : status === 'empty' ? '空库' : status === 'not_found' ? '未找到' : '错误'
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
  const [uploadTaskId, setUploadTaskId] = useState<string | null>(null)
  const [uploadResult, setUploadResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [stats, setStats] = useState<DocStats | null>(null)
  const [loadingStats, setLoadingStats] = useState(false)

  const [resetting, setResetting] = useState(false)
  const [editingCloudProfileId, setEditingCloudProfileId] = useState<string | null>(null)
  const [cloudProfileName, setCloudProfileName] = useState('')
  const [cloudProfileModel, setCloudProfileModel] = useState('openai/gpt-4o-mini')
  const [cloudProfileBaseUrl, setCloudProfileBaseUrl] = useState('https://openrouter.ai/api/v1')
  const [cloudProfileApiKey, setCloudProfileApiKey] = useState('')
  const [cloudProfileTemperature, setCloudProfileTemperature] = useState(0.3)

  // Roles tab state
  const [prompts, setPrompts] = useState<SystemPrompt[]>([])
  const [loadingPrompts, setLoadingPrompts] = useState(false)
  const [editingPrompt, setEditingPrompt] = useState<SystemPrompt | null>(null)
  const [isCreating, setIsCreating] = useState(false)
  const [promptName, setPromptName] = useState('')
  const [promptContent, setPromptContent] = useState('')
  const [promptVectorStoreId, setPromptVectorStoreId] = useState('')
  const [promptDashboardEnabled, setPromptDashboardEnabled] = useState(DEFAULT_DASHBOARD_TEMPLATE.enabled)
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
  const [retrievalSearchK, setRetrievalSearchK] = useState(5)
  const [retrievalFetchK, setRetrievalFetchK] = useState(10)
  const [retrievalUseRerank, setRetrievalUseRerank] = useState(false)
  const [showDocList, setShowDocList] = useState(false)
  const [kbChunks, setKbChunks] = useState<KnowledgeBaseChunk[]>([])
  const [loadingKBChunks, setLoadingKBChunks] = useState(false)
  const [kbChunkQuery, setKbChunkQuery] = useState('')
  const [kbChunkSourceFilter, setKbChunkSourceFilter] = useState('')
  const [kbChunkAppliedQuery, setKbChunkAppliedQuery] = useState('')
  const [kbChunkAppliedSourceFilter, setKbChunkAppliedSourceFilter] = useState('')
  const [kbChunkOffset, setKbChunkOffset] = useState(0)
  const [kbChunkTotal, setKbChunkTotal] = useState(0)
  const [editingChunkId, setEditingChunkId] = useState<string | null>(null)
  const [editingChunkContent, setEditingChunkContent] = useState('')
  const [editingChunkSource, setEditingChunkSource] = useState('')
  const [savingChunkId, setSavingChunkId] = useState<string | null>(null)
  const [deletingChunkId, setDeletingChunkId] = useState<string | null>(null)
  const [deletingKB, setDeletingKB] = useState(false)
  const [deleteKBConfirm, setDeleteKBConfirm] = useState(false)
  const [deleteKBPath, setDeleteKBPath] = useState<string | null>(null)
  const [kbActionError, setKbActionError] = useState<string | null>(null)

  const {
    setActivePromptId,
    cloudModelProfiles,
    saveCloudModelProfile,
    deleteCloudModelProfile,
  } = useChatStore()
  const addTask = useTaskStore((s) => s.addTask)
  const startPolling = useTaskStore((s) => s.startPolling)
  const tasks = useTaskStore((s) => s.tasks)

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

  const loadKBChunks = useCallback(
    async (params?: { offset?: number; query?: string; source?: string }) => {
      setLoadingKBChunks(true)
      setKbActionError(null)
      try {
        const data = await getKnowledgeBaseChunks({
          query: params?.query ?? '',
          source: params?.source ?? '',
          offset: params?.offset ?? 0,
          limit: KB_CHUNK_PAGE_SIZE,
        })
        setKbChunks(data.items)
        setKbChunkOffset(data.offset)
        setKbChunkTotal(data.total)
      } catch (e) {
        setKbActionError((e as Error).message)
        setKbChunks([])
        setKbChunkTotal(0)
        setKbChunkOffset(0)
      } finally {
        setLoadingKBChunks(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (open) {
      setTab('general')
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
      loadKBChunks({ offset: 0, query: '', source: '' })
      setKbChunkAppliedQuery('')
      setKbChunkAppliedSourceFilter('')
    }
  }, [open, tab, loadKBHealth, loadKBChunks])

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
    setUploadTaskId(null)
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
      setUploadTaskId(result.task_id)
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

  const resetCloudProfileForm = useCallback(() => {
    setEditingCloudProfileId(null)
    setCloudProfileName('')
    setCloudProfileModel('openai/gpt-4o-mini')
    setCloudProfileBaseUrl('https://openrouter.ai/api/v1')
    setCloudProfileApiKey('')
    setCloudProfileTemperature(0.3)
  }, [])

  const handleEditCloudProfile = useCallback((profile: CloudModelProfile) => {
    setEditingCloudProfileId(profile.id)
    setCloudProfileName(profile.name)
    setCloudProfileModel(profile.modelConfig.model)
    setCloudProfileBaseUrl(profile.modelConfig.base_url)
    setCloudProfileApiKey(profile.modelConfig.api_key)
    setCloudProfileTemperature(profile.modelConfig.temperature)
  }, [])

  const handleSaveCloudProfile = useCallback(() => {
    if (!cloudProfileName.trim() || !cloudProfileModel.trim() || !cloudProfileBaseUrl.trim()) {
      return
    }

    saveCloudModelProfile({
      id: editingCloudProfileId ?? undefined,
      name: cloudProfileName.trim(),
      modelConfig: {
        panel_id: editingCloudProfileId ?? 'cloud-profile-editor',
        connection_type: 'openai_compatible',
        provider: 'openai_compatible',
        model: cloudProfileModel.trim(),
        base_url: cloudProfileBaseUrl.trim(),
        api_key: cloudProfileApiKey,
        temperature: cloudProfileTemperature,
        agent_mode: 'auto',
      },
    })

    resetCloudProfileForm()
  }, [
    cloudProfileApiKey,
    cloudProfileBaseUrl,
    cloudProfileModel,
    cloudProfileName,
    cloudProfileTemperature,
    editingCloudProfileId,
    resetCloudProfileForm,
    saveCloudModelProfile,
  ])

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
    setPromptDashboardEnabled(dashboardTemplate.enabled)
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
    setPromptDashboardEnabled(dashboardTemplate.enabled)
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
    setPromptDashboardEnabled(DEFAULT_DASHBOARD_TEMPLATE.enabled)
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
      enabled: promptDashboardEnabled,
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
      const result = await testKBRetrieval(testQuery, {
        search_k: retrievalSearchK,
        fetch_k: retrievalFetchK,
        use_rerank: retrievalUseRerank,
      })
      setTestResult(result)
    } catch (e) {
      setTestResult({ results_count: 0, latency_ms: 0, error: (e as Error).message })
    } finally {
      setTestingRetrieval(false)
    }
  }

  const handleChunkSearch = () => {
    const query = kbChunkQuery.trim()
    const source = kbChunkSourceFilter.trim()
    setKbChunkAppliedQuery(query)
    setKbChunkAppliedSourceFilter(source)
    void loadKBChunks({ offset: 0, query, source })
  }

  const handleStartEditChunk = (chunk: KnowledgeBaseChunk) => {
    setEditingChunkId(chunk.chunk_id)
    setEditingChunkContent(chunk.content)
    setEditingChunkSource(chunk.source)
  }

  const handleCancelEditChunk = () => {
    setEditingChunkId(null)
    setEditingChunkContent('')
    setEditingChunkSource('')
  }

  const handleSaveChunk = async () => {
    if (!editingChunkId) return
    if (!editingChunkContent.trim()) {
      setKbActionError('切片内容不能为空')
      return
    }
    if (!editingChunkSource.trim()) {
      setKbActionError('来源不能为空')
      return
    }

    setSavingChunkId(editingChunkId)
    setKbActionError(null)
    try {
      await updateKnowledgeBaseChunk(editingChunkId, {
        content: editingChunkContent,
        source: editingChunkSource,
      })
      handleCancelEditChunk()
      await loadKBChunks({
        offset: kbChunkOffset,
        query: kbChunkAppliedQuery,
        source: kbChunkAppliedSourceFilter,
      })
      await loadKBHealth()
    } catch (e) {
      setKbActionError((e as Error).message)
    } finally {
      setSavingChunkId(null)
    }
  }

  const handleDeleteChunk = async (chunkId: string) => {
    if (!window.confirm('Confirm deleting this knowledge-base chunk? This action cannot be undone.')) return
    setDeletingChunkId(chunkId)
    setKbActionError(null)
    try {
      await deleteKnowledgeBaseChunk(chunkId)
      const nextOffset =
        kbChunks.length === 1 && kbChunkOffset > 0
          ? Math.max(0, kbChunkOffset - KB_CHUNK_PAGE_SIZE)
          : kbChunkOffset
      await loadKBChunks({
        offset: nextOffset,
        query: kbChunkAppliedQuery,
        source: kbChunkAppliedSourceFilter,
      })
      await loadKBHealth()
    } catch (e) {
      setKbActionError((e as Error).message)
    } finally {
      setDeletingChunkId(null)
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
      setKbChunks([])
      setKbChunkTotal(0)
      setKbChunkOffset(0)
      setKbChunkAppliedQuery('')
      setKbChunkAppliedSourceFilter('')
      setStats(null)
      await loadKnowledgeBases()
      await loadKBHealth()
      await loadKBChunks({ offset: 0, query: '', source: '' })
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
  const uploadTask = uploadTaskId ? tasks[uploadTaskId] : undefined
  const uploadProgress = Math.max(0, Math.min(100, uploadTask?.progress ?? 0))
  const kbChunkTotalPages = Math.max(1, Math.ceil(kbChunkTotal / KB_CHUNK_PAGE_SIZE))
  const kbChunkCurrentPage = Math.floor(kbChunkOffset / KB_CHUNK_PAGE_SIZE) + 1

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

      {/* General Tab */}
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
                placeholder={tavilyKeySet ? '已配置（留空则保持当前值）' : 'tvly-xxxxxxxxxxxxxxxx'}
                value={tavilyKey}
                onChange={(e) => setTavilyKey(e.target.value)}
              />
            </div>
            <p className="text-[11px] text-text-secondary mt-1.5">
              获取地址：<a href="https://app.tavily.com" target="_blank" rel="noopener noreferrer" className="text-accent-blue hover:underline">
                app.tavily.com
              </a>
              {tavilyKeySet && <span className="ml-2 text-accent-green">已配置</span>}
            </p>
          </div>

          <div className="pt-2 flex items-center gap-3">
            <Button variant="primary" onClick={handleSaveGeneral} loading={saving}>
              {saveOk ? <CheckCircle size={14} /> : null}
              {saveOk ? '已保存' : '保存设置'}
            </Button>
            <Button variant="ghost" onClick={handleResetAgents} loading={resetting} title="Clear agent cache and rebuild on next request">
              <RefreshCw size={13} />
              重置 Agent 缓存
            </Button>
          </div>

          <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">云端模型配置</h3>
                <p className="mt-1 text-xs leading-5 text-text-secondary">
                  常用的云端模型配置可以保存在这里，方便不同面板快速复用。</p>
              </div>
              <Button variant="outline" size="sm" onClick={resetCloudProfileForm}>
                新建
              </Button>
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
                  配置名称
                </label>
                <input
                  className="input-base w-full text-sm"
                  value={cloudProfileName}
                  onChange={(e) => setCloudProfileName(e.target.value)}
                  placeholder="例如：OpenRouter GPT-4o mini"
                />
              </div>

              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
                  模型 ID
                </label>
                <input
                  className="input-base w-full text-sm"
                  value={cloudProfileModel}
                  onChange={(e) => setCloudProfileModel(e.target.value)}
                  placeholder="openai/gpt-4o-mini"
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
                  服务地址
                </label>
                <input
                  className="input-base w-full text-sm"
                  value={cloudProfileBaseUrl}
                  onChange={(e) => setCloudProfileBaseUrl(e.target.value)}
                  placeholder="https://openrouter.ai/api/v1"
                />
              </div>

              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
                  API Key
                </label>
                <input
                  className="input-base w-full text-sm"
                  type="password"
                  value={cloudProfileApiKey}
                  onChange={(e) => setCloudProfileApiKey(e.target.value)}
                  placeholder="sk-..."
                />
              </div>

              <div>
                <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
                  温度
                </label>
                <div className="rounded-lg border border-bg-border bg-bg-primary/60 px-3 py-2 text-sm text-text-primary">
                  <div className="mb-2 flex items-center justify-between">
                    <span>当前值</span>
                    <span>{cloudProfileTemperature.toFixed(1)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={cloudProfileTemperature}
                    onChange={(e) => setCloudProfileTemperature(parseFloat(e.target.value))}
                    className="w-full accent-accent-blue"
                  />
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button
                variant="primary"
                onClick={handleSaveCloudProfile}
                disabled={
                  !cloudProfileName.trim() ||
                  !cloudProfileModel.trim() ||
                  !cloudProfileBaseUrl.trim()
                }
              >
                {editingCloudProfileId ? '更新云端模型' : '保存到配置库'}
              </Button>
              <Button variant="ghost" onClick={resetCloudProfileForm}>
                清空表单
              </Button>
              <span className="text-[11px] text-text-secondary">
                这些配置仅保存在当前浏览器本地。</span>
            </div>

            <div className="mt-4 border-t border-bg-border pt-4">
              <div className="mb-2 text-[11px] uppercase tracking-wide text-text-secondary">
                已保存配置</div>
              {cloudModelProfiles.length > 0 ? (
                <div className="space-y-2">
                  {cloudModelProfiles.map((profile) => (
                    <div
                      key={profile.id}
                      className="rounded-lg border border-bg-border bg-bg-primary/40 px-3 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-text-primary">
                            {profile.name}
                          </div>
                          <div className="mt-1 truncate text-xs text-text-secondary">
                            {profile.modelConfig.model}
                          </div>
                          <div className="mt-1 truncate text-[11px] text-text-secondary/70">
                            {profile.modelConfig.base_url}
                          </div>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEditCloudProfile(profile)}
                          >
                            编辑
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-accent-red hover:text-accent-red"
                            onClick={() => {
                              if (editingCloudProfileId === profile.id) {
                                resetCloudProfileForm()
                              }
                              deleteCloudModelProfile(profile.id)
                            }}
                          >
                            删除
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-secondary">
                  还没有保存的云端模型配置。保存后，可在聊天面板顶部的模型选择器里直接使用。</p>
              )}
            </div>
          </div>

          <div className="pt-3 border-t border-bg-border">
            <p className="text-xs text-text-secondary">
              模型配置（提供方 / 模型 / 服务地址 / API Key / 温度）也可以通过各聊天面板顶部的模型选择器分别设置。</p>
          </div>
        </div>
      )}

      {/* Documents Tab */}
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
                <p className="text-sm text-text-secondary">上传中...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload size={28} className="text-text-secondary/50" />
                <p className="text-sm text-text-primary">拖拽文件到此处，或点击选择</p>
                <p className="text-xs text-text-secondary">支持 PDF、Word、Markdown、CSV、TXT、Excel（单文件不超过 10 MB，大文件会自动分批处理）</p>
                <p className="text-xs text-text-secondary/60 mt-0.5">结构化文档会按章节智能切块，检索结果更完整</p>
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

          {uploadTaskId && (
            <div className="rounded-lg border border-bg-border bg-bg-tertiary/60 p-3">
              <div className="flex items-center justify-between text-xs text-text-secondary">
                <span>
                  上传任务进度
                  {uploadTask
                    ? `(status: ${uploadTask.status === 'completed' ? 'done' : uploadTask.status === 'failed' ? 'failed' : 'running'})`
                    : '（等待任务状态）'}
                </span>
                <span className="text-text-primary">{uploadProgress}%</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-bg-border/80">
                <div
                  className={`h-full transition-all duration-300 ${
                    uploadTask?.status === 'failed'
                      ? 'bg-accent-red'
                      : uploadTask?.status === 'completed'
                        ? 'bg-accent-green'
                        : 'bg-accent-blue'
                  }`}
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="mt-1.5 text-[11px] text-text-secondary/80">
                任务 ID: {uploadTaskId}
              </p>
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
              {deleteKBConfirm && deleteKBPath === null ? '再次点击确认删除' : '删除知识库'}
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
                  <span className="text-text-secondary">文档切片数</span>
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

      {/* Roles Tab */}
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
                  placeholder="描述这个 AI 角色的职责、能力边界和回答风格..."
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
                  知识库绑定 <span className="ml-1.5 text-text-secondary/50 font-normal">（可选，切换角色时自动加载）</span>
                </label>
                {loadingKBs ? (
                  <span className="text-xs text-text-secondary">正在加载知识库列表...</span>
                ) : (
                  <select
                    className="input-base w-full text-sm"
                    value={promptVectorStoreId}
                    onChange={(e) => setPromptVectorStoreId(e.target.value)}
                  >
                    <option value="">不绑定（使用默认知识库）</option>
                    {knowledgeBases.map((kb) => (
                      <option key={kb.id} value={kb.id}>
                        {kb.name} ({kb.doc_count} chunks){!kb.has_index ? ' [no index]' : ''}
                      </option>
                    ))}
                  </select>
                )}
              </div>

              <div className="rounded-lg border border-bg-border bg-bg-primary/30 p-3 space-y-3 lg:row-span-3">
                <div className="flex items-center justify-between gap-3 rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2.5">
                  <div>
                    <p className="text-xs font-medium text-text-primary">Dashboard</p>
                    <p className="mt-1 text-[11px] text-text-secondary/65">
                      如果这个角色不需要生成仪表盘卡片，可以在这里关闭。
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPromptDashboardEnabled((value) => !value)}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] transition-colors ${
                      promptDashboardEnabled
                        ? 'border-accent-blue/35 bg-accent-blue/12 text-accent-blue'
                        : 'border-bg-border bg-bg-primary text-text-secondary'
                    }`}
                    aria-pressed={promptDashboardEnabled}
                    title={promptDashboardEnabled ? '关闭仪表盘' : '启用仪表盘'}
                  >
                    {promptDashboardEnabled ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                    {promptDashboardEnabled ? '已启用' : '已关闭'}
                  </button>
                </div>

                <div className={`space-y-3 ${promptDashboardEnabled ? '' : 'opacity-55'}`}>
                  <div>
                    <label className="block text-xs font-medium text-text-secondary mb-1.5">
                      仪表盘标题提示
                    </label>
                    <input
                      className="input-base w-full text-sm"
                      placeholder="例如：管理层经营分析看板"
                      value={promptDashboardTitleHint}
                      onChange={(e) => setPromptDashboardTitleHint(e.target.value)}
                      disabled={!promptDashboardEnabled}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-text-secondary mb-1.5">
                      受众语气
                    </label>
                    <input
                      className="input-base w-full text-sm"
                      placeholder="例如：专业、直观、适合业务汇报"
                      value={promptDashboardAudienceTone}
                      onChange={(e) => setPromptDashboardAudienceTone(e.target.value)}
                      disabled={!promptDashboardEnabled}
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
                      disabled={!promptDashboardEnabled}
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
                            disabled={!promptDashboardEnabled}
                            className={`px-2.5 py-1 rounded-lg text-[11px] border transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
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
                      disabled={!promptDashboardEnabled}
                    />
                    <p className="mt-1 text-[11px] text-text-secondary/55">
                      可用值：summary、metrics、charts、table、evidence、warnings
                    </p>
                  </div>
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
              <p className="text-xs text-text-secondary">选择当前生效的 AI 角色，切换后会在下一次对话中生效</p>
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
                            已绑定知识库
                          </span>
                        )}
                        {p.dashboard_template && Object.keys(p.dashboard_template).length > 0 && (
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 flex items-center gap-1 ${
                            normalizeDashboardTemplate(p.dashboard_template).enabled
                              ? 'bg-accent-blue/15 text-accent-blue'
                              : 'bg-bg-secondary text-text-secondary'
                          }`}>
                            <Zap size={9} />
                            {normalizeDashboardTemplate(p.dashboard_template).enabled ? '仪表盘已启用' : '仪表盘已关闭'}
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
                            知识库 {activateStatus[p.id] === 'loaded' ? '已加载' : activateStatus[p.id] === 'error' ? '加载失败' : activateStatus[p.id]}
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
              <p className="text-[11px] text-text-secondary mb-2">快捷模板</p>
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

      {/* KB Monitor Tab */}
      {tab === 'kb_monitor' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
              <Activity size={14} className="text-accent-blue" />
              知识库健康监控</h3>
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
                  <span className="text-xs text-text-secondary">向量模型</span>
                  <span className="text-[11px] text-text-primary/70 truncate max-w-[180px]">{kbHealth.embedding_model}</span>
                </div>
                {kbHealth.last_updated && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-text-secondary">最近更新</span>
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
                    文档列表（{kbHealth.documents.length} 个文件）
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

              {/* Chunk browser */}
              <div className="border-t border-bg-border pt-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wide">
                    知识库切片浏览器
                  </h4>
                  <Button
                    variant="ghost"
                    onClick={() =>
                      loadKBChunks({
                        offset: kbChunkOffset,
                        query: kbChunkAppliedQuery,
                        source: kbChunkAppliedSourceFilter,
                      })
                    }
                    loading={loadingKBChunks}
                    className="gap-1.5 text-xs"
                  >
                    <RefreshCw size={12} />
                    刷新切片
                  </Button>
                </div>

                <div className="mb-3 flex flex-col gap-2 sm:flex-row">
                  <input
                    className="input-base flex-1 text-sm"
                    placeholder="搜索切片内容或来源..."
                    value={kbChunkQuery}
                    onChange={(e) => setKbChunkQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleChunkSearch()}
                  />
                  <select
                    className="input-base text-sm sm:w-52"
                    value={kbChunkSourceFilter}
                    onChange={(e) => setKbChunkSourceFilter(e.target.value)}
                  >
                    <option value="">全部来源</option>
                    {kbHealth.documents.map((doc) => (
                      <option key={doc.name} value={doc.name}>
                        {doc.name}
                      </option>
                    ))}
                  </select>
                  <Button variant="primary" onClick={handleChunkSearch} loading={loadingKBChunks}>
                    <Search size={13} />
                    搜索
                  </Button>
                </div>

                {loadingKBChunks && (
                  <div className="flex justify-center py-5">
                    <span className="w-5 h-5 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
                  </div>
                )}

                {!loadingKBChunks && kbChunks.length === 0 && (
                  <div className="rounded-lg border border-bg-border bg-bg-tertiary/40 px-3 py-5 text-center text-xs text-text-secondary">
                    当前条件下没有切片数据</div>
                )}

                {!loadingKBChunks && kbChunks.length > 0 && (
                  <div className="space-y-2">
                    {kbChunks.map((chunk) => {
                      const isEditing = editingChunkId === chunk.chunk_id
                      return (
                        <div key={chunk.chunk_id} className="rounded-lg border border-bg-border bg-bg-tertiary/40 p-3">
                          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-[11px] font-medium text-accent-blue/80">
                                {chunk.source || '未知来源'}
                              </p>
                              <p className="text-[10px] text-text-secondary/70">
                                #{chunk.position >= 0 ? chunk.position + 1 : '-'} · {chunk.char_count} 字符
                              </p>
                            </div>
                            <div className="flex items-center gap-1">
                              {!isEditing && (
                                <button
                                  onClick={() => handleStartEditChunk(chunk)}
                                  className="p-1.5 rounded-md text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
                                  title="编辑切片"
                                >
                                  <Pencil size={12} />
                                </button>
                              )}
                              <button
                                onClick={() => handleDeleteChunk(chunk.chunk_id)}
                                disabled={deletingChunkId === chunk.chunk_id}
                                className="p-1.5 rounded-md text-text-secondary hover:text-accent-red hover:bg-accent-red/10 transition-colors disabled:opacity-50"
                                title="删除切片"
                              >
                                {deletingChunkId === chunk.chunk_id ? (
                                  <span className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin block" />
                                ) : (
                                  <Trash2 size={12} />
                                )}
                              </button>
                            </div>
                          </div>

                          {isEditing ? (
                            <div className="space-y-2">
                              <input
                                className="input-base w-full text-xs"
                                value={editingChunkSource}
                                onChange={(e) => setEditingChunkSource(e.target.value)}
                                placeholder="来源名称"
                              />
                              <textarea
                                className="input-base w-full text-xs resize-y min-h-[120px]"
                                value={editingChunkContent}
                                onChange={(e) => setEditingChunkContent(e.target.value)}
                                placeholder="切片内容"
                              />
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="primary"
                                  onClick={handleSaveChunk}
                                  loading={savingChunkId === chunk.chunk_id}
                                  className="text-xs"
                                >
                                  保存
                                </Button>
                                <Button variant="ghost" onClick={handleCancelEditChunk} className="text-xs">
                                  取消
                                </Button>
                              </div>
                            </div>
                          ) : (
                            <p className="whitespace-pre-wrap break-words text-xs leading-relaxed text-text-secondary/85">
                              {chunk.preview}
                            </p>
                          )}
                        </div>
                      )
                    })}
                  </div>
                )}

                <div className="mt-3 flex items-center justify-between text-xs text-text-secondary">
                  <span>
                    第 {Math.min(kbChunkCurrentPage, kbChunkTotalPages)} / {kbChunkTotalPages} 页 · 共 {kbChunkTotal} 条</span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      onClick={() =>
                        loadKBChunks({
                          offset: Math.max(0, kbChunkOffset - KB_CHUNK_PAGE_SIZE),
                          query: kbChunkAppliedQuery,
                          source: kbChunkAppliedSourceFilter,
                        })
                      }
                      disabled={kbChunkOffset <= 0 || loadingKBChunks}
                      className="text-xs"
                    >
                      上一页</Button>
                    <Button
                      variant="ghost"
                      onClick={() =>
                        loadKBChunks({
                          offset: kbChunkOffset + KB_CHUNK_PAGE_SIZE,
                          query: kbChunkAppliedQuery,
                          source: kbChunkAppliedSourceFilter,
                        })
                      }
                      disabled={kbChunkOffset + KB_CHUNK_PAGE_SIZE >= kbChunkTotal || loadingKBChunks}
                      className="text-xs"
                    >
                      下一页</Button>
                  </div>
                </div>
              </div>

              {/* Test retrieval */}
              <div className="border-t border-bg-border pt-4">
                <h4 className="text-xs font-medium text-text-secondary uppercase tracking-wide mb-3 flex items-center gap-1.5">
                  <Zap size={11} />
                  检索诊断</h4>
                {/* 参数配置 */}
                <div className="mb-2 flex flex-wrap items-center gap-3 text-xs">
                  <label className="flex items-center gap-1.5 text-text-secondary">
                    <input
                      type="checkbox"
                      checked={retrievalUseRerank}
                      onChange={(e) => setRetrievalUseRerank(e.target.checked)}
                      className="accent-accent-blue"
                    />
                    向量 + 重排
                  </label>
                  <label className="flex items-center gap-1.5 text-text-secondary">
                    Top K
                    <input
                      type="number"
                      min={1}
                      max={20}
                      value={retrievalSearchK}
                      onChange={(e) => setRetrievalSearchK(Math.max(1, Math.min(20, Number(e.target.value))))}
                      className="input-base w-14 text-center text-xs py-0.5"
                    />
                  </label>
                  {retrievalUseRerank && (
                    <label className="flex items-center gap-1.5 text-text-secondary">
                      Fetch K
                      <input
                        type="number"
                        min={retrievalSearchK}
                        max={50}
                        value={retrievalFetchK}
                        onChange={(e) => setRetrievalFetchK(Math.max(retrievalSearchK, Math.min(50, Number(e.target.value))))}
                        className="input-base w-14 text-center text-xs py-0.5"
                      />
                    </label>
                  )}
                </div>
                <div className="flex gap-2">
                  <input
                    className="input-base flex-1 text-sm"
                    placeholder="输入测试检索问题..."
                    value={testQuery}
                    onChange={(e) => setTestQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && void handleTestRetrieval()}
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
                        <div className="flex flex-wrap gap-3 text-xs">
                          <span className="text-text-secondary">命中数：<span className="text-text-primary font-medium">{testResult.results_count}</span></span>
                          <span className="text-text-secondary">耗时：<span className="text-text-primary font-medium">{testResult.latency_ms} ms</span></span>
                          {testResult.search_mode && (
                            <span className={`rounded-full px-2 py-0.5 font-medium ${testResult.search_mode === 'vector_rerank' ? 'bg-accent-green/15 text-accent-green' : 'bg-accent-blue/15 text-accent-blue'}`}>
                              {testResult.search_mode === 'vector_rerank' ? '向量 + 重排' : '仅向量'}
                            </span>
                          )}
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
                  {deleteKBConfirm && deleteKBPath === null ? '再次点击确认删除' : '删除当前知识库'}
                </Button>
                <p className="text-[11px] text-text-secondary/50 text-center mt-1">
                  此操作不可撤销，并会删除全部向量索引文件。
                </p>
              </div>
            </>
          )}

          {!kbHealth && !loadingKBHealth && (
            <div className="flex flex-col items-center gap-3 py-8 text-text-secondary/50">
              <Database size={32} />
              <p className="text-sm">知识库未初始化或无法访问</p>
              <Button variant="ghost" onClick={loadKBHealth}>重新检查</Button>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}


