import React, { useEffect, useMemo, useState } from 'react'
import {
  ArrowDownUp,
  CheckSquare,
  Download,
  Eye,
  FileText,
  Image as ImageIcon,
  LibraryBig,
  Link2,
  Paperclip,
  Plus,
  Quote,
  RefreshCcw,
  Search,
  Square,
  X,
} from 'lucide-react'
import {
  getKnowledgeBases,
  getSessionAttachments,
  promoteSessionAttachmentToKnowledgeBase,
  type ChatFile,
  type KnowledgeBase,
  type SessionAttachment,
  type SessionAttachmentSummary,
  type TaskRecord,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'
import { useTaskStore } from '../../stores/taskStore'
import { AttachmentPreviewModal } from './AttachmentPreviewModal'

type WorkspaceFilter = 'all' | 'file' | 'image' | 'text'
type SortKey = 'time' | 'size' | 'refs'

interface AttachmentWorkspaceProps {
  open: boolean
  onClose: () => void
  interactionLocked?: boolean
}

const EMPTY_SUMMARY: SessionAttachmentSummary = {
  total_attachments: 0,
  file_count: 0,
  image_count: 0,
  text_ready_count: 0,
  reusable_count: 0,
  total_size_bytes: 0,
}

const CURRENT_KB_OPTION = '__current_kb__'

function formatFileSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatRelativeTime(timestamp: number): string {
  if (!timestamp) return '未知'
  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp))
  if (diffSeconds < 60) return '刚刚'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)} 分钟前`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)} 小时前`
  return `${Math.floor(diffSeconds / 86400)} 天前`
}

function attachmentMatchesFilter(attachment: SessionAttachment, filter: WorkspaceFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'file') return attachment.kind === 'file'
  if (filter === 'image') return attachment.kind === 'image'
  return Boolean(attachment.preview_text?.trim())
}

function buildQuotedExcerpt(attachment: SessionAttachment): string {
  const rawText = (attachment.extracted_text ?? attachment.preview_text ?? '').trim()
  if (!rawText) return ''
  const clipped =
    rawText.length > 500
      ? `${rawText.slice(0, 500).trim()}\n...[以下内容已截断]`
      : rawText
  return `请把以下来自“${attachment.name}”的片段作为上下文：\n"""\n${clipped}\n"""`
}

function formatKnowledgeBaseLabel(path: string): string {
  const normalized = path.trim().replace(/\\/g, '/')
  if (!normalized) return '当前知识库'
  const segments = normalized.split('/').filter(Boolean)
  return segments[segments.length - 1] ?? normalized
}

function describeKnowledgeBase(kb: KnowledgeBase): string {
  const base = kb.name?.trim() || formatKnowledgeBaseLabel(kb.path)
  if (kb.doc_count > 0) return `${base} | ${kb.doc_count} 个分块`
  if (kb.has_index) return `${base} | 已建立索引`
  return `${base} | 空知识库`
}

function getPromotionBadgeMeta(attachment: SessionAttachment): {
  label: string
  badgeClass: string
} {
  switch (attachment.promotion_status) {
    case 'completed':
      return {
        label: '已加入当前知识库',
        badgeClass: 'border-accent-green/30 bg-accent-green/10 text-accent-green',
      }
    case 'pending':
    case 'running':
      return {
        label: '正在索引到知识库',
        badgeClass: 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue',
      }
    case 'failed':
      return {
        label: '入库失败',
        badgeClass: 'border-accent-red/30 bg-accent-red/10 text-accent-red',
      }
    default:
      return {
        label: '尚未加入当前知识库',
        badgeClass: 'border-bg-border bg-bg-primary text-text-secondary',
      }
  }
}

export const AttachmentWorkspace: React.FC<AttachmentWorkspaceProps> = ({
  open,
  onClose,
  interactionLocked = false,
}) => {
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const primaryMessages = useChatStore((state) => state.panels[0]?.messages ?? [])
  const pushComposerSeed = useChatStore((state) => state.pushComposerSeed)
  const taskMap = useTaskStore((state) => state.tasks)
  const addTask = useTaskStore((state) => state.addTask)
  const startPolling = useTaskStore((state) => state.startPolling)

  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [loadingKnowledgeBases, setLoadingKnowledgeBases] = useState(false)
  const [selectedVectorStorePath, setSelectedVectorStorePath] = useState('')
  const [attachments, setAttachments] = useState<SessionAttachment[]>([])
  const [summary, setSummary] = useState<SessionAttachmentSummary>(EMPTY_SUMMARY)
  const [currentVectorStorePath, setCurrentVectorStorePath] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<WorkspaceFilter>('all')
  const [previewFile, setPreviewFile] = useState<ChatFile | null>(null)
  const [promotingAttachmentId, setPromotingAttachmentId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [sortKey, setSortKey] = useState<SortKey>('time')
  const [bulkPromoting, setBulkPromoting] = useState(false)

  const attachmentSyncKey = useMemo(
    () =>
      primaryMessages
        .filter((message) => message.role === 'user')
        .map(
          (message) =>
            `${message.answerGroupId ?? message.id}:${message.images?.length ?? 0}:${message.files?.length ?? 0}`,
        )
        .join('|'),
    [primaryMessages],
  )

  const promotionTaskByAttachmentKey = useMemo(() => {
    const nextMap = new Map<string, TaskRecord>()
    for (const task of Object.values(taskMap)) {
      if (task.task_type !== 'promote_attachment_to_kb') continue
      const attachmentId =
        typeof task.params?.attachment_id === 'string' ? task.params.attachment_id.trim() : ''
      const vectorStorePath =
        typeof task.params?.vector_store_path === 'string'
          ? task.params.vector_store_path.trim()
          : ''
      if (!attachmentId || !vectorStorePath) continue

      const key = `${vectorStorePath}::${attachmentId}`
      const existing = nextMap.get(key)
      const taskUpdatedAt = task.updated_at ?? task.created_at
      const existingUpdatedAt = existing ? (existing.updated_at ?? existing.created_at) : -1
      if (!existing || taskUpdatedAt >= existingUpdatedAt) {
        nextMap.set(key, task)
      }
    }
    return nextMap
  }, [taskMap])

  const requestedVectorStorePath = selectedVectorStorePath.trim()

  const knowledgeBaseOptions = useMemo(() => {
    const currentPath = currentVectorStorePath.trim()
    const next = knowledgeBases.filter(
      (kb) => !currentPath || kb.path.trim() !== currentPath,
    )
    if (
      requestedVectorStorePath &&
      requestedVectorStorePath !== currentPath &&
      !next.some((kb) => kb.path.trim() === requestedVectorStorePath)
    ) {
      next.unshift({
        id: requestedVectorStorePath,
        name: formatKnowledgeBaseLabel(requestedVectorStorePath),
        path: requestedVectorStorePath,
        doc_count: 0,
        has_index: false,
      })
    }
    return next
  }, [currentVectorStorePath, knowledgeBases, requestedVectorStorePath])

  useEffect(() => {
    if (!open) return

    let cancelled = false
    const loadKnowledgeBaseOptions = async () => {
      setLoadingKnowledgeBases(true)
      try {
        const list = await getKnowledgeBases()
        if (!cancelled) {
          setKnowledgeBases(list)
        }
      } catch {
        if (!cancelled) {
          setKnowledgeBases([])
        }
      } finally {
        if (!cancelled) {
          setLoadingKnowledgeBases(false)
        }
      }
    }

    void loadKnowledgeBaseOptions()
    return () => {
      cancelled = true
    }
  }, [open])

  useEffect(() => {
    if (!open) return

    if (!currentSessionId) {
      setAttachments([])
      setSummary(EMPTY_SUMMARY)
      setCurrentVectorStorePath('')
      setError('')
      setNotice('')
      setLoading(false)
      return
    }

    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError('')
      setNotice('')
      try {
        const data = await getSessionAttachments(currentSessionId, requestedVectorStorePath || undefined)
        if (cancelled) return
        setAttachments(data.attachments)
        setSummary(data.summary)
        setCurrentVectorStorePath(data.current_vector_store_path ?? '')
      } catch (err) {
        if (cancelled) return
        setError((err as Error).message ?? '加载附件失败。')
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [open, currentSessionId, attachmentSyncKey, requestedVectorStorePath])

  useEffect(() => {
    if (!currentVectorStorePath) return

    setAttachments((current) =>
      current.map((attachment) => {
        if (attachment.kind !== 'file') return attachment
        const task = promotionTaskByAttachmentKey.get(
          `${currentVectorStorePath}::${attachment.attachment_id}`,
        )
        if (!task) return attachment

        const nextStatus = task.status
        const nextUpdatedAt = task.updated_at ?? task.created_at
        const nextInCurrentKb = nextStatus === 'completed'
        if (
          attachment.promotion_status === nextStatus &&
          attachment.promotion_task_id === task.task_id &&
          attachment.promotion_updated_at === nextUpdatedAt &&
          attachment.is_in_current_kb === nextInCurrentKb &&
          attachment.current_vector_store_path === currentVectorStorePath
        ) {
          return attachment
        }

        return {
          ...attachment,
          current_vector_store_path: currentVectorStorePath,
          promotion_status: nextStatus,
          promotion_task_id: task.task_id,
          promotion_updated_at: nextUpdatedAt,
          is_in_current_kb: nextInCurrentKb,
        }
      }),
    )
  }, [currentVectorStorePath, promotionTaskByAttachmentKey])

  useEffect(() => {
    if (!selectedVectorStorePath || !currentVectorStorePath) return
    if (selectedVectorStorePath.trim() === currentVectorStorePath.trim()) {
      setSelectedVectorStorePath('')
    }
  }, [currentVectorStorePath, selectedVectorStorePath])

  const filteredAttachments = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    const filtered = attachments.filter((attachment) => {
      if (!attachmentMatchesFilter(attachment, filter)) {
        return false
      }
      if (!keyword) {
        return true
      }
      const haystack = [
        attachment.name,
        attachment.media_type,
        attachment.preview_text ?? '',
        attachment.extracted_text ?? '',
      ]
        .join('\n')
        .toLowerCase()
      return haystack.includes(keyword)
    })
    return [...filtered].sort((a, b) => {
      if (sortKey === 'size') return b.size_bytes - a.size_bytes
      if (sortKey === 'refs') return b.turn_count - a.turn_count
      return b.last_seen_at - a.last_seen_at
    })
  }, [attachments, filter, search, sortKey])

  const filterCounts = useMemo(
    () => ({
      all: attachments.length,
      file: attachments.filter((attachment) => attachment.kind === 'file').length,
      image: attachments.filter((attachment) => attachment.kind === 'image').length,
      text: attachments.filter((attachment) => Boolean(attachment.preview_text?.trim())).length,
    }),
    [attachments],
  )

  const indexedInCurrentKbCount = useMemo(
    () => attachments.filter((attachment) => attachment.kind === 'file' && attachment.is_in_current_kb).length,
    [attachments],
  )

  const indexingInCurrentKbCount = useMemo(
    () =>
      attachments.filter(
        (attachment) =>
          attachment.kind === 'file' &&
          (attachment.promotion_status === 'pending' || attachment.promotion_status === 'running'),
      ).length,
    [attachments],
  )

  if (!open) {
    return null
  }

  const handleRefresh = async () => {
    if (!currentSessionId) return
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const data = await getSessionAttachments(currentSessionId, requestedVectorStorePath || undefined)
      setAttachments(data.attachments)
      setSummary(data.summary)
      setCurrentVectorStorePath(data.current_vector_store_path ?? '')
    } catch (err) {
      setError((err as Error).message ?? '加载附件失败。')
    } finally {
      setLoading(false)
    }
  }

  const handleReuseAttachment = (attachment: SessionAttachment) => {
    if (interactionLocked || !attachment.data_url) return

    if (attachment.kind === 'image') {
      pushComposerSeed({
        images: [
          {
            name: attachment.name,
            media_type: attachment.media_type,
            data_url: attachment.data_url,
          },
        ],
      })
      return
    }

    pushComposerSeed({
      files: [
        {
          name: attachment.name,
          media_type: attachment.media_type,
          data_url: attachment.data_url,
          size_bytes: attachment.size_bytes,
          extracted_text: attachment.extracted_text,
        },
      ],
    })
  }

  const handleQuoteAttachment = (attachment: SessionAttachment) => {
    const excerpt = buildQuotedExcerpt(attachment)
    if (!excerpt) return
    pushComposerSeed({ text: excerpt })
  }

  const handleJumpToTurn = (attachment: SessionAttachment) => {
    const answerGroupId = attachment.latest_answer_group_id?.trim()
    if (!answerGroupId) return

    const target = Array.from(
      document.querySelectorAll<HTMLElement>('[data-role="user"][data-answer-group-id]'),
    ).find((element) => element.dataset.answerGroupId === answerGroupId)

    target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const handlePromoteToKnowledgeBase = async (attachment: SessionAttachment) => {
    if (!currentSessionId) return
    setPromotingAttachmentId(attachment.attachment_id)
    setError('')
    setNotice('')
    try {
      const task = await promoteSessionAttachmentToKnowledgeBase(
        currentSessionId,
        attachment.attachment_id,
        requestedVectorStorePath || undefined,
      )
      addTask(task)
      if (task.status === 'pending' || task.status === 'running') {
        startPolling(task.task_id)
      }

      const updatedAt = task.updated_at ?? task.created_at ?? Math.floor(Date.now() / 1000)
      setAttachments((current) =>
        current.map((item) =>
          item.attachment_id === attachment.attachment_id
            ? {
                ...item,
                current_vector_store_path: currentVectorStorePath,
                promotion_status: task.status,
                promotion_task_id: task.task_id,
                promotion_updated_at: updatedAt,
                is_in_current_kb: task.status === 'completed',
              }
            : item,
        ),
      )

      const kbLabel = formatKnowledgeBaseLabel(currentVectorStorePath)
      const dedupeHit = task.params?.dedupe_hit === true
      if (dedupeHit && task.status === 'completed') {
        setNotice(`“${attachment.name}”已经在 ${kbLabel} 中。`)
      } else if (dedupeHit && (task.status === 'pending' || task.status === 'running')) {
        setNotice(`“${attachment.name}”正在被索引到 ${kbLabel}。`)
      } else {
        setNotice(`已开始将“${attachment.name}”索引到 ${kbLabel}。`)
      }
    } catch (err) {
      setError((err as Error).message ?? '添加附件到知识库失败。')
    } finally {
      setPromotingAttachmentId(null)
    }
  }

  const handleBulkPromote = async () => {
    if (!currentSessionId || selectedIds.size === 0) return
    setBulkPromoting(true)
    setError('')
    setNotice('')
    const targets = filteredAttachments.filter(
      (a) => selectedIds.has(a.attachment_id) && a.kind === 'file' && Boolean(a.data_url),
    )
    let successCount = 0
    for (const attachment of targets) {
      try {
        const task = await promoteSessionAttachmentToKnowledgeBase(
          currentSessionId,
          attachment.attachment_id,
          requestedVectorStorePath || undefined,
        )
        addTask(task)
        if (task.status === 'pending' || task.status === 'running') {
          startPolling(task.task_id)
        }
        successCount++
      } catch {
        // continue best-effort
      }
    }
    setBulkPromoting(false)
    setSelectedIds(new Set())
    if (successCount > 0) {
      setNotice(`已提交 ${successCount} 个文件到知识库索引队列。`)
    }
  }

  const workspaceBody = (
    <section className="flex h-full w-full flex-col border-l border-bg-border bg-bg-primary lg:w-[21rem]">
      <div className="flex items-start justify-between gap-3 border-b border-bg-border px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
            <Paperclip size={14} className="text-accent-blue" />
            附件工作区
          </div>
          <p className="mt-1 text-[11px] text-text-secondary">
            无需重复上传，直接复用当前会话中的附件和图片。
          </p>
          <p
            className="mt-1 truncate text-[11px] text-text-secondary"
            title={currentVectorStorePath || '当前知识库'}
          >
            当前知识库：
            <span className="text-text-primary">{currentVectorStorePath || '当前知识库'}</span>
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => void handleRefresh()}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title="刷新附件"
          >
            <RefreshCcw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary lg:hidden"
            title="关闭附件工作区"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      <div className="border-b border-bg-border px-4 py-3">
        <div className="mb-3">
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-text-secondary/70">
            目标知识库
          </label>
          <select
            value={requestedVectorStorePath || CURRENT_KB_OPTION}
            onChange={(event) =>
              setSelectedVectorStorePath(
                event.target.value === CURRENT_KB_OPTION ? '' : event.target.value,
              )
            }
            className="w-full rounded-xl border border-bg-border bg-bg-secondary px-3 py-2 text-xs text-text-primary outline-none"
          >
            <option value={CURRENT_KB_OPTION}>
              {currentVectorStorePath
                ? `当前知识库 | ${formatKnowledgeBaseLabel(currentVectorStorePath)}`
                : '当前知识库'}
            </option>
            {knowledgeBaseOptions.map((kb) => (
              <option key={kb.path} value={kb.path}>
                {describeKnowledgeBase(kb)}
              </option>
            ))}
          </select>
          <div className="mt-1 text-[11px] text-text-secondary">
            {loadingKnowledgeBases
              ? '正在加载知识库列表...'
              : '选择附件要索引到哪个知识库。'}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">附件总数</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{summary.total_attachments}</div>
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">可提取文本</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{summary.text_ready_count}</div>
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">可复用</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{summary.reusable_count}</div>
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">已入库</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{indexedInCurrentKbCount}</div>
          </div>
        </div>

        <div className="mt-3 flex items-center justify-between text-[11px] text-text-secondary">
          <span>{summary.file_count} 个文件 / {summary.image_count} 张图片</span>
          <span>{formatFileSize(summary.total_size_bytes)}</span>
        </div>
        {indexingInCurrentKbCount > 0 && (
          <div className="mt-2 text-[11px] text-accent-blue">
            当前有 {indexingInCurrentKbCount} 个附件正在索引中。
          </div>
        )}

        <label className="mt-3 flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
          <Search size={13} className="text-text-secondary" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索附件"
            className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
          />
        </label>

        <div className="mt-3 flex items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            {([
              ['all', `全部 ${filterCounts.all}`],
              ['file', `文件 ${filterCounts.file}`],
              ['image', `图片 ${filterCounts.image}`],
              ['text', `文本 ${filterCounts.text}`],
            ] as Array<[WorkspaceFilter, string]>).map(([value, label]) => {
              const active = filter === value
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFilter(value)}
                  className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                    active
                      ? 'bg-accent-blue/15 text-accent-blue'
                      : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>
          <div className="flex items-center gap-1">
            <ArrowDownUp size={11} className="text-text-secondary/60" />
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="rounded-lg border border-bg-border bg-bg-secondary px-1.5 py-1 text-[11px] text-text-secondary outline-none"
            >
              <option value="time">时间</option>
              <option value="size">大小</option>
              <option value="refs">引用</option>
            </select>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {notice && (
          <div className="mb-3 rounded-2xl border border-accent-green/30 bg-accent-green/10 px-4 py-3 text-xs text-accent-green">
            {notice}
          </div>
        )}
        {filteredAttachments.length > 0 && (
          <div className="mb-2 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => {
                const selectableIds = filteredAttachments
                  .filter((a) => a.kind === 'file' && Boolean(a.data_url))
                  .map((a) => a.attachment_id)
                const allSelected = selectableIds.every((id) => selectedIds.has(id))
                if (allSelected) {
                  setSelectedIds(new Set())
                } else {
                  setSelectedIds(new Set(selectableIds))
                }
              }}
              className="inline-flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary"
            >
              {filteredAttachments
                .filter((a) => a.kind === 'file' && Boolean(a.data_url))
                .every((a) => selectedIds.has(a.attachment_id)) && selectedIds.size > 0 ? (
                <CheckSquare size={13} className="text-accent-blue" />
              ) : (
                <Square size={13} />
              )}
              全选文件
            </button>
            {selectedIds.size > 0 && (
              <button
                type="button"
                onClick={() => void handleBulkPromote()}
                disabled={bulkPromoting}
                className="inline-flex items-center gap-1 rounded-lg border border-accent-blue/30 bg-accent-blue/10 px-2.5 py-1 text-[11px] text-accent-blue transition-colors hover:bg-accent-blue/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <LibraryBig size={11} />
                {bulkPromoting ? '索引中...' : `批量加入知识库 (${selectedIds.size})`}
              </button>
            )}
          </div>
        )}

        {!currentSessionId ? (
          <div className="rounded-2xl border border-dashed border-bg-border px-4 py-10 text-center text-xs text-text-secondary">
            先开始一段会话，再上传文件或图片来构建附件工作区。
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-xs text-accent-red">
            {error}
          </div>
        ) : loading && attachments.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-xs text-text-secondary">
            正在加载附件...
          </div>
        ) : filteredAttachments.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-bg-border px-4 py-10 text-center text-xs text-text-secondary">
            当前筛选条件下没有匹配的附件。
          </div>
        ) : (
          <div className="space-y-3">
            {filteredAttachments.map((attachment) => {
              const canPreviewText = Boolean(attachment.preview_text?.trim())
              const canReuse = Boolean(attachment.data_url)
              const canJump = Boolean(attachment.latest_answer_group_id?.trim())
              const promotionStatus = attachment.promotion_status ?? 'idle'
              const promotionBusy = promotionStatus === 'pending' || promotionStatus === 'running'
              const promotionDone = promotionStatus === 'completed'
              const showPromoteAction = attachment.kind === 'file' && Boolean(attachment.data_url)
              const promotionBadge =
                attachment.kind === 'file' ? getPromotionBadgeMeta(attachment) : null
              const isPromoting = promotingAttachmentId === attachment.attachment_id

              const isSelectable = attachment.kind === 'file' && Boolean(attachment.data_url)
              const isSelected = selectedIds.has(attachment.attachment_id)

              return (
                <article
                  key={attachment.attachment_id}
                  className={`rounded-2xl border bg-bg-secondary/60 p-3 ${isSelected ? 'border-accent-blue/40' : 'border-bg-border'}`}
                >
                  <div className="flex items-start gap-3">
                    {isSelectable && (
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedIds((prev) => {
                            const next = new Set(prev)
                            if (next.has(attachment.attachment_id)) {
                              next.delete(attachment.attachment_id)
                            } else {
                              next.add(attachment.attachment_id)
                            }
                            return next
                          })
                        }}
                        className="mt-1 shrink-0 text-text-secondary hover:text-accent-blue"
                      >
                        {isSelected ? <CheckSquare size={14} className="text-accent-blue" /> : <Square size={14} />}
                      </button>
                    )}
                    {attachment.kind === 'image' && attachment.data_url ? (
                      <a
                        href={attachment.data_url}
                        target="_blank"
                        rel="noreferrer"
                        className="block h-14 w-14 shrink-0 overflow-hidden rounded-xl border border-bg-border bg-black/10"
                        title={`打开 ${attachment.name}`}
                      >
                        <img
                          src={attachment.data_url}
                          alt={attachment.name}
                          className="h-full w-full object-cover"
                        />
                      </a>
                    ) : (
                      <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-bg-border bg-bg-primary">
                        {attachment.kind === 'image' ? (
                          <ImageIcon size={18} className="text-accent-blue" />
                        ) : (
                          <FileText size={18} className="text-accent-blue" />
                        )}
                      </div>
                    )}

                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <h3 className="truncate text-sm font-semibold text-text-primary">
                            {attachment.name || '未命名附件'}
                          </h3>
                          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-text-secondary">
                            <span>{attachment.kind === 'image' ? '图片' : '文件'}</span>
                            <span>{formatFileSize(attachment.size_bytes)}</span>
                            <span>{attachment.turn_count} 次引用</span>
                            <span>{formatRelativeTime(attachment.last_seen_at)}</span>
                          </div>
                          {promotionBadge && (
                            <div className="mt-2">
                              <span
                                className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] ${promotionBadge.badgeClass}`}
                              >
                                {promotionBadge.label}
                              </span>
                            </div>
                          )}
                        </div>
                        <span className="rounded-full bg-bg-primary px-2 py-0.5 text-[10px] text-text-secondary">
                          x{attachment.occurrence_count}
                        </span>
                      </div>

                      {canPreviewText && (
                        <div className="mt-2 rounded-xl border border-bg-border bg-bg-primary/70 px-3 py-2">
                          <p className="max-h-24 overflow-hidden whitespace-pre-wrap break-words text-[11px] leading-5 text-text-secondary">
                            {attachment.preview_text}
                          </p>
                        </div>
                      )}

                      <div className="mt-3 flex flex-wrap gap-2">
                        {canPreviewText && (
                          <button
                            type="button"
                            onClick={() =>
                              setPreviewFile({
                                name: attachment.name,
                                media_type: attachment.media_type,
                                data_url: attachment.data_url,
                                size_bytes: attachment.size_bytes,
                                extracted_text: attachment.extracted_text,
                              })
                            }
                            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                          >
                            <Eye size={11} />
                            预览
                          </button>
                        )}

                        {canPreviewText && (
                          <button
                            type="button"
                            onClick={() => handleQuoteAttachment(attachment)}
                            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                          >
                            <Quote size={11} />
                            引用
                          </button>
                        )}

                        {canReuse && (
                          <button
                            type="button"
                            onClick={() => handleReuseAttachment(attachment)}
                            disabled={interactionLocked}
                            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            <Plus size={11} />
                            加入输入框
                          </button>
                        )}

                        {showPromoteAction && (
                          <button
                            type="button"
                            onClick={() => {
                              void handlePromoteToKnowledgeBase(attachment)
                            }}
                            disabled={isPromoting || promotionBusy || promotionDone}
                            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                          >
                            <LibraryBig size={11} />
                            {isPromoting || promotionBusy
                              ? '索引中...'
                              : promotionDone
                                ? '已入库'
                                : '加入知识库'}
                          </button>
                        )}

                        {canJump && (
                          <button
                            type="button"
                            onClick={() => handleJumpToTurn(attachment)}
                            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                          >
                            <Link2 size={11} />
                            跳转
                          </button>
                        )}

                        {attachment.data_url && (
                          <a
                            href={attachment.data_url}
                            download={attachment.name}
                            className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                          >
                            <Download size={11} />
                            下载
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>

      {previewFile && (
        <AttachmentPreviewModal
          file={previewFile}
          onClose={() => setPreviewFile(null)}
        />
      )}
    </section>
  )

  return (
    <>
      <div className="absolute inset-0 z-30 bg-black/50 backdrop-blur-[1px] lg:hidden" onClick={onClose} />
      <div className="absolute inset-y-0 right-0 z-40 w-[min(22rem,100vw)] max-w-full shadow-2xl lg:static lg:z-0 lg:w-auto lg:max-w-none lg:shadow-none">
        {workspaceBody}
      </div>
    </>
  )
}
