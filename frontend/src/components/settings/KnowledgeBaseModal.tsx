/**
 * 知识库管理弹窗
 * P0 功能：文档列表、上传进度、删除确认、检索测试
 * 根据 20260413plan.md P0 改进项实施
 */

import React, { useState, useCallback, useRef, useEffect } from 'react'
import {
  Database,
  Upload,
  Search,
  Activity,
  Trash2,
  RefreshCw,
  CheckCircle,
  AlertCircle,
  Clock,
  FileText,
  Loader2,
  ChevronDown,
  ChevronRight,
  X,
  HardDrive,
} from 'lucide-react'
import { AdminTokenPanel } from '../admin/AdminTokenPanel'
import { Modal } from '../ui/Modal'
import {
  getKBHealth,
  getKnowledgeBaseChunks,
  deleteKnowledgeBaseChunk,
  testKBRetrieval,
  uploadDocuments,
  getTask,
  getAdminApiToken,
  saveAdminApiToken,
  type KBHealthData,
  type KnowledgeBaseChunk,
  type RetrievalDebugItem,
  type RetrievalTestResult,
  type TaskRecord,
} from '../../api/client'
import { isAdminAccessError } from '../admin/adminAccess'

// ── 类型 ────────────────────────────────────────────

type TabKey = 'documents' | 'upload' | 'retrieval' | 'health'

interface DocGroup {
  source: string
  chunks: KnowledgeBaseChunk[]
  totalChars: number
}

// ── 工具函数 ─────────────────────────────────────────

function groupChunksBySource(chunks: KnowledgeBaseChunk[]): DocGroup[] {
  const map = new Map<string, KnowledgeBaseChunk[]>()
  for (const c of chunks) {
    const key = c.source || '未知来源'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(c)
  }
  return Array.from(map.entries()).map(([source, items]) => ({
    source,
    chunks: items,
    totalChars: items.reduce((s, c) => s + c.char_count, 0),
  }))
}

function formatSize(mb: number): string {
  if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`
  return `${mb.toFixed(1)} MB`
}

function formatDate(ts: number | null): string {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

// ── 子组件：文档列表 Tab ─────────────────────────────

interface DocumentsTabProps {
  onDeleted?: () => void
  onAdminAccessError?: (message: string | null) => void
}

const DocumentsTab: React.FC<DocumentsTabProps> = ({ onDeleted, onAdminAccessError }) => {
  const [loading, setLoading] = useState(true)
  const [groups, setGroups] = useState<DocGroup[]>([])
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set())
  const [deletingChunk, setDeletingChunk] = useState<string | null>(null)
  const [deletingSource, setDeletingSource] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<{ type: 'chunk'; id: string; label: string } | { type: 'source'; source: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      // 分批加载所有 chunks
      const allChunks: KnowledgeBaseChunk[] = []
      let offset = 0
      const limit = 200
      while (true) {
        const res = await getKnowledgeBaseChunks({ offset, limit })
        allChunks.push(...res.items)
        if (!res.has_more) break
        offset += limit
      }
      setGroups(groupChunksBySource(allChunks))
      onAdminAccessError?.(null)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '加载失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setLoading(false)
    }
  }, [onAdminAccessError])

  useEffect(() => { load() }, [load])

  const toggleSource = (source: string) => {
    setExpandedSources(prev => {
      const next = new Set(prev)
      if (next.has(source)) next.delete(source)
      else next.add(source)
      return next
    })
  }

  const handleDeleteChunk = async (chunkId: string) => {
    setDeletingChunk(chunkId)
    setConfirmDelete(null)
    try {
      await deleteKnowledgeBaseChunk(chunkId)
      await load()
      onDeleted?.()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '删除失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setDeletingChunk(null)
    }
  }

  const handleDeleteSource = async (source: string) => {
    const group = groups.find(g => g.source === source)
    if (!group) return
    setDeletingSource(source)
    setConfirmDelete(null)
    try {
      for (const chunk of group.chunks) {
        await deleteKnowledgeBaseChunk(chunk.chunk_id)
      }
      await load()
      onDeleted?.()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '删除失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setDeletingSource(null)
    }
  }

  const filteredGroups = searchQuery.trim()
    ? groups.filter(g => g.source.toLowerCase().includes(searchQuery.toLowerCase()))
    : groups

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={20} className="animate-spin text-accent-blue mr-2" />
        <span className="text-sm text-text-secondary">加载中...</span>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* 搜索栏 */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="搜索文档名..."
            className="w-full pl-8 pr-3 py-1.5 text-sm bg-bg-tertiary border border-bg-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
          />
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover border border-bg-border transition-colors flex items-center gap-1"
        >
          <RefreshCw size={11} />
          刷新
        </button>
      </div>

      {error && (
        <div className="px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-lg text-xs text-accent-red">{error}</div>
      )}

      {filteredGroups.length === 0 ? (
        <div className="text-center py-10 text-text-secondary text-sm">
          {searchQuery ? '未找到匹配的文档' : '知识库暂无文档，请上传文件'}
        </div>
      ) : (
        <div className="space-y-1.5">
          {/* 统计 */}
          <p className="text-xs text-text-muted">
            共 {filteredGroups.length} 个文档，{filteredGroups.reduce((s, g) => s + g.chunks.length, 0)} 个分块
          </p>

          {filteredGroups.map(group => (
            <div key={group.source} className="border border-bg-border rounded-lg overflow-hidden">
              {/* 文档行 */}
              <div
                className="flex items-center gap-2 px-3 py-2.5 bg-bg-tertiary hover:bg-bg-hover cursor-pointer select-none"
                onClick={() => toggleSource(group.source)}
              >
                {expandedSources.has(group.source) ? (
                  <ChevronDown size={13} className="text-text-muted shrink-0" />
                ) : (
                  <ChevronRight size={13} className="text-text-muted shrink-0" />
                )}
                <FileText size={13} className="text-accent-blue shrink-0" />
                <span className="flex-1 text-sm text-text-primary font-medium truncate">{group.source}</span>
                <span className="text-xs text-text-muted shrink-0">{group.chunks.length} 块</span>
                <button
                  onClick={e => {
                    e.stopPropagation()
                    setConfirmDelete({ type: 'source', source: group.source })
                  }}
                  disabled={deletingSource === group.source}
                  className="ml-1 p-1 rounded text-text-muted hover:text-accent-red hover:bg-accent-red/10 transition-colors shrink-0"
                  title="删除该文档的所有分块"
                >
                  {deletingSource === group.source
                    ? <Loader2 size={12} className="animate-spin" />
                    : <Trash2 size={12} />
                  }
                </button>
              </div>

              {/* 分块列表（展开） */}
              {expandedSources.has(group.source) && (
                <div className="divide-y divide-bg-border">
                  {group.chunks.map(chunk => (
                    <div key={chunk.chunk_id} className="flex items-start gap-2 px-3 py-2 hover:bg-bg-hover group">
                      <span className="text-[10px] text-text-muted mt-0.5 shrink-0 w-6 text-right">{chunk.position}</span>
                      <p className="flex-1 text-xs text-text-secondary line-clamp-2">{chunk.preview}</p>
                      <span className="text-[10px] text-text-muted shrink-0">{chunk.char_count}字</span>
                      <button
                        onClick={() => setConfirmDelete({ type: 'chunk', id: chunk.chunk_id, label: chunk.preview.slice(0, 30) })}
                        disabled={deletingChunk === chunk.chunk_id}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded text-text-muted hover:text-accent-red hover:bg-accent-red/10 transition-all shrink-0"
                      >
                        {deletingChunk === chunk.chunk_id
                          ? <Loader2 size={11} className="animate-spin" />
                          : <X size={11} />
                        }
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 删除确认对话框 */}
      {confirmDelete && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" onClick={() => setConfirmDelete(null)}>
          <div className="absolute inset-0 bg-black/50" />
          <div
            className="relative z-10 bg-bg-secondary border border-bg-border rounded-xl p-5 max-w-sm w-full shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 mb-3">
              <AlertCircle size={16} className="text-accent-red" />
              <h3 className="text-sm font-semibold text-text-primary">
                {confirmDelete.type === 'source' ? '删除整个文档' : '删除分块'}
              </h3>
            </div>
            <p className="text-xs text-text-secondary mb-4">
              {confirmDelete.type === 'source'
                ? `确定要删除文档「${confirmDelete.source}」的所有分块吗？此操作不可撤销。`
                : `确定要删除分块「${confirmDelete.label}...」吗？此操作不可撤销。`
              }
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-3 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:bg-bg-hover transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => {
                  if (confirmDelete.type === 'chunk') handleDeleteChunk(confirmDelete.id)
                  else handleDeleteSource(confirmDelete.source)
                }}
                className="px-3 py-1.5 text-xs rounded-lg bg-accent-red text-white hover:bg-accent-red/80 transition-colors"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── 子组件：上传文档 Tab ─────────────────────────────

const UploadTab: React.FC<{
  onUploaded?: () => void
  onAdminAccessError?: (message: string | null) => void
}> = ({ onUploaded, onAdminAccessError }) => {
  const [dragging, setDragging] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [task, setTask] = useState<TaskRecord | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const ACCEPTED = '.pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.md,.png,.jpg,.jpeg,.webp'

  const addFiles = (newFiles: FileList | File[]) => {
    const arr = Array.from(newFiles)
    setFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      return [...prev, ...arr.filter(f => !existing.has(f.name))]
    })
  }

  const removeFile = (name: string) => setFiles(prev => prev.filter(f => f.name !== name))

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const startPolling = (taskId: string) => {
    const poll = async () => {
      try {
        const rec = await getTask(taskId)
        setTask(rec)
        if (rec.status === 'completed' || rec.status === 'failed') {
          setUploading(false)
          if (rec.status === 'completed') {
            setFiles([])
            onUploaded?.()
          }
          return
        }
        pollRef.current = setTimeout(poll, 1500)
      } catch {
        setUploading(false)
        setError('无法获取任务状态')
      }
    }
    pollRef.current = setTimeout(poll, 800)
  }

  useEffect(() => () => { if (pollRef.current) clearTimeout(pollRef.current) }, [])

  const handleUpload = async () => {
    if (!files.length) return
    setUploading(true)
    setError(null)
    setTask(null)
    try {
      const res = await uploadDocuments(files)
      startPolling(res.task_id)
      onAdminAccessError?.(null)
    } catch (e: unknown) {
      setUploading(false)
      const message = e instanceof Error ? e.message : '上传失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    }
  }

  const taskStatusColor = task?.status === 'completed' ? 'text-accent-green'
    : task?.status === 'failed' ? 'text-accent-red'
    : 'text-accent-blue'

  return (
    <div className="space-y-4">
      {/* 拖拽区域 */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragging ? 'border-accent-blue bg-accent-blue/5' : 'border-bg-border hover:border-accent-blue/50 hover:bg-bg-hover'
        }`}
      >
        <Upload size={24} className="mx-auto mb-3 text-text-muted" />
        <p className="text-sm text-text-secondary font-medium">点击选择文件或拖拽到此处</p>
        <p className="text-xs text-text-muted mt-1">支持 PDF、Word、Excel、CSV、TXT、Markdown、图片</p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          className="hidden"
          onChange={e => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {/* 文件列表 */}
      {files.length > 0 && (
        <div className="space-y-1.5">
          {files.map(f => (
            <div key={f.name} className="flex items-center gap-2 px-3 py-2 bg-bg-tertiary rounded-lg border border-bg-border">
              <FileText size={13} className="text-accent-blue shrink-0" />
              <span className="flex-1 text-sm text-text-primary truncate">{f.name}</span>
              <span className="text-xs text-text-muted shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
              <button onClick={() => removeFile(f.name)} className="p-1 rounded text-text-muted hover:text-accent-red transition-colors">
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 任务进度 */}
      {task && (
        <div className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-2">
          <div className="flex items-center gap-2">
            {task.status === 'completed' && <CheckCircle size={14} className="text-accent-green" />}
            {task.status === 'failed' && <AlertCircle size={14} className="text-accent-red" />}
            {(task.status === 'pending' || task.status === 'running') && (
              <Loader2 size={14} className="animate-spin text-accent-blue" />
            )}
            <span className={`text-sm font-medium ${taskStatusColor}`}>
              {task.status === 'completed' ? '上传并索引完成！'
                : task.status === 'failed' ? `失败: ${task.error || '未知错误'}`
                : task.status === 'running' ? '正在处理文档...'
                : '等待处理...'}
            </span>
            {task.status !== 'failed' && task.status !== 'completed' && (
              <span className="text-xs text-text-muted ml-auto">{Math.round(task.progress * 100)}%</span>
            )}
          </div>
          {(task.status === 'pending' || task.status === 'running') && (
            <div className="w-full bg-bg-border rounded-full h-1.5">
              <div
                className="bg-accent-blue h-1.5 rounded-full transition-all duration-300"
                style={{ width: `${Math.round(task.progress * 100)}%` }}
              />
            </div>
          )}
          {task.result && (
            <p className="text-xs text-text-secondary">{task.result}</p>
          )}
        </div>
      )}

      {error && (
        <div className="px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-lg text-xs text-accent-red">{error}</div>
      )}

      <button
        onClick={handleUpload}
        disabled={!files.length || uploading}
        className="w-full py-2.5 rounded-xl text-sm font-medium bg-accent-blue text-white hover:bg-accent-blue/80 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
      >
        {uploading ? <><Loader2 size={14} className="animate-spin" />处理中...</> : <><Upload size={14} />上传并索引</>}
      </button>
    </div>
  )
}

// ── 子组件：检索测试 Tab ─────────────────────────────

const RetrievalTab: React.FC<{ onAdminAccessError?: (message: string | null) => void }> = ({
  onAdminAccessError,
}) => {
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RetrievalTestResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [retrievalMode, setRetrievalMode] = useState<'semantic' | 'keyword' | 'hybrid'>('semantic')
  const [useRerank, setUseRerank] = useState(false)
  const [searchK, setSearchK] = useState(5)
  const [fetchK, setFetchK] = useState(10)

  const handleTest = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await testKBRetrieval(query.trim(), {
        retrieval_mode: retrievalMode,
        search_k: searchK,
        fetch_k: fetchK,
        use_rerank: useRerank,
      })
      setResult(res)
      if (res.error) setError(res.error)
      onAdminAccessError?.(null)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '检索失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setLoading(false)
    }
  }

  const renderDebugList = (
    title: string,
    items: RetrievalTestResult['top_results'] | undefined,
    accentClass: string,
  ) => {
    if (!items || items.length === 0) return null
    return (
      <div className="space-y-2">
        <p className="text-xs text-text-muted font-medium">{title}</p>
        {items.map((item, index) => (
          <div key={`${title}-${index}`} className="px-3 py-2.5 bg-bg-tertiary rounded-lg border border-bg-border space-y-1">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${accentClass}`}>#{item.rank ?? index + 1}</span>
                <span className="text-xs text-text-secondary font-medium truncate">{item.source}</span>
              </div>
              <span className="text-[10px] text-text-muted whitespace-nowrap">score {Number(item.score ?? 0).toFixed(3)}</span>
            </div>
            {renderFeedbackSummary(item)}
            <p className="text-xs text-text-primary leading-relaxed">{item.snippet}</p>
            {item.matched_terms && item.matched_terms.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {item.matched_terms.slice(0, 6).map((term) => (
                  <span key={term} className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-secondary text-text-secondary">
                    {term}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    )
  }

  const renderFeedbackSummary = (item: RetrievalDebugItem) => {
    const positiveCount = typeof item.feedback_positive_count === 'number' ? item.feedback_positive_count : 0
    const negativeCount = typeof item.feedback_negative_count === 'number' ? item.feedback_negative_count : 0
    const netFeedback = typeof item.feedback_net === 'number' ? item.feedback_net : positiveCount - negativeCount
    const feedbackBoost = typeof item.feedback_boost === 'number' ? item.feedback_boost : 0
    const hasFeedbackSignal =
      positiveCount > 0 ||
      negativeCount > 0 ||
      netFeedback !== 0 ||
      Math.abs(feedbackBoost) >= 0.0005

    if (!hasFeedbackSignal) return null

    return (
      <div className="flex flex-wrap gap-1">
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-secondary text-text-secondary">
          反馈 +{positiveCount}/-{negativeCount}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-secondary text-text-secondary">
          净值 {netFeedback >= 0 ? '+' : ''}{netFeedback}
        </span>
        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bg-secondary text-text-secondary">
          boost {feedbackBoost >= 0 ? '+' : ''}{feedbackBoost.toFixed(3)}
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2 text-xs">
        <label className="flex items-center gap-1.5 text-text-secondary">
          模式
          <select
            value={retrievalMode}
            onChange={(e) => setRetrievalMode(e.target.value as 'semantic' | 'keyword' | 'hybrid')}
            className="px-2 py-1 rounded-md bg-bg-tertiary border border-bg-border text-text-primary"
          >
            <option value="semantic">仅向量</option>
            <option value="keyword">仅关键词</option>
            <option value="hybrid">混合检索</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-text-secondary">
          Top K
          <input
            type="number"
            min={1}
            max={20}
            value={searchK}
            onChange={(e) => setSearchK(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
            className="w-14 px-2 py-1 rounded-md bg-bg-tertiary border border-bg-border text-center text-text-primary"
          />
        </label>
        <label className="flex items-center gap-1.5 text-text-secondary">
          Fetch K
          <input
            type="number"
            min={searchK}
            max={50}
            value={fetchK}
            onChange={(e) => setFetchK(Math.max(searchK, Math.min(50, Number(e.target.value) || searchK)))}
            className="w-14 px-2 py-1 rounded-md bg-bg-tertiary border border-bg-border text-center text-text-primary"
          />
        </label>
        <label className="flex items-center gap-1.5 text-text-secondary">
          <input
            type="checkbox"
            checked={useRerank}
            onChange={(e) => setUseRerank(e.target.checked)}
            className="accent-accent-blue"
          />
          二段重排
        </label>
      </div>

      <div className="flex gap-2">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleTest()}
          placeholder="输入检索词，测试知识库召回效果..."
          className="flex-1 px-3 py-2 text-sm bg-bg-tertiary border border-bg-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-blue"
        />
        <button
          onClick={handleTest}
          disabled={!query.trim() || loading}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-accent-blue text-white hover:bg-accent-blue/80 disabled:opacity-50 transition-colors flex items-center gap-1.5"
        >
          {loading ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
          检索
        </button>
      </div>

      {error && (
        <div className="px-3 py-2 bg-accent-red/10 border border-accent-red/20 rounded-lg text-xs text-accent-red">{error}</div>
      )}

      {result && !error && (
        <div className="space-y-3">
          <div className="flex items-center gap-4 px-3 py-2 bg-bg-tertiary rounded-lg border border-bg-border">
            <div className="text-center">
              <div className="text-lg font-bold text-text-primary">{result.results_count}</div>
              <div className="text-[10px] text-text-muted">命中数</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold text-accent-green">{result.latency_ms}ms</div>
              <div className="text-[10px] text-text-muted">耗时</div>
            </div>
            {result.search_mode && (
              <div className="ml-auto text-right">
                <div className="text-sm font-semibold text-text-primary">{result.search_mode}</div>
                <div className="text-[10px] text-text-muted">执行模式</div>
              </div>
            )}
          </div>

          {result.coverage && (
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2">
                <div className="text-text-muted">去重来源</div>
                <div className="text-text-primary font-semibold">{result.coverage.unique_sources}</div>
              </div>
              <div className="rounded-lg border border-bg-border bg-bg-secondary/40 px-3 py-2">
                <div className="text-text-muted">命中关键词</div>
                <div className="text-text-primary font-semibold">{result.coverage.matched_term_count}</div>
              </div>
            </div>
          )}

          {result.rewrite_query && (
            <div className="px-3 py-2 rounded-lg border border-bg-border bg-bg-secondary/40">
              <div className="text-[10px] uppercase tracking-wide text-text-muted mb-1">Effective Query</div>
              <div className="text-sm text-text-primary">{result.rewrite_query}</div>
            </div>
          )}

          {result.top_results && result.top_results.length > 0 ? (
            <div className="space-y-3">
              {renderDebugList('Top 命中片段', result.top_results, 'text-accent-blue bg-accent-blue/10')}
              {renderDebugList('向量候选', result.semantic_candidates, 'text-accent-green bg-accent-green/10')}
              {renderDebugList('关键词候选', result.keyword_candidates, 'text-amber-300 bg-amber-300/10')}
              {renderDebugList('融合候选', result.fused_candidates, 'text-accent-blue bg-accent-blue/10')}
            </div>
          ) : (
            <p className="text-sm text-center text-text-secondary py-4">未命中任何片段</p>
          )}
        </div>
      )}

      {!result && !error && (
        <div className="text-center py-8 text-text-muted text-sm">
          输入查询词后点击检索，查看知识库召回效果和命中片段
        </div>
      )}
    </div>
  )
}

// ── 子组件：健康状态 Tab ─────────────────────────────

const HealthTab: React.FC<{ onAdminAccessError?: (message: string | null) => void }> = ({
  onAdminAccessError,
}) => {
  const [loading, setLoading] = useState(true)
  const [health, setHealth] = useState<KBHealthData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getKBHealth()
      setHealth(data)
      onAdminAccessError?.(null)
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '获取状态失败'
      setError(message)
      if (isAdminAccessError(e)) onAdminAccessError?.(message)
    } finally {
      setLoading(false)
    }
  }, [onAdminAccessError])

  useEffect(() => { load() }, [load])

  const statusConfig = {
    healthy: { icon: <CheckCircle size={16} className="text-accent-green" />, label: '健康', color: 'text-accent-green' },
    empty: { icon: <Clock size={16} className="text-accent-orange" />, label: '空（未上传文档）', color: 'text-accent-orange' },
    not_found: { icon: <AlertCircle size={16} className="text-accent-red" />, label: '未找到', color: 'text-accent-red' },
    error: { icon: <AlertCircle size={16} className="text-accent-red" />, label: '异常', color: 'text-accent-red' },
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 size={20} className="animate-spin text-accent-blue mr-2" />
        <span className="text-sm text-text-secondary">加载中...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8 space-y-3">
        <AlertCircle size={32} className="mx-auto text-accent-red" />
        <p className="text-sm text-accent-red">{error}</p>
        <button onClick={load} className="px-3 py-1.5 text-xs rounded-lg border border-bg-border text-text-secondary hover:bg-bg-hover transition-colors">
          重试
        </button>
      </div>
    )
  }

  if (!health) return null

  const status = statusConfig[health.index_status] ?? statusConfig.error

  return (
    <div className="space-y-4">
      {/* 状态概览 */}
      <div className="grid grid-cols-2 gap-3">
        <div className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-1">
          <div className="flex items-center gap-2">
            {status.icon}
            <span className={`text-sm font-semibold ${status.color}`}>{status.label}</span>
          </div>
          <p className="text-[10px] text-text-muted">索引状态</p>
        </div>
        <div className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-1">
          <div className="text-lg font-bold text-text-primary">{health.total_chunks}</div>
          <p className="text-[10px] text-text-muted">总分块数</p>
        </div>
        <div className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-1">
          <div className="flex items-center gap-1">
            <HardDrive size={13} className="text-text-muted" />
            <span className="text-lg font-bold text-text-primary">{formatSize(health.store_size_mb)}</span>
          </div>
          <p className="text-[10px] text-text-muted">存储占用</p>
        </div>
        <div className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-1">
          <div className="text-sm font-bold text-text-primary">{health.documents.length}</div>
          <p className="text-[10px] text-text-muted">文档数量</p>
        </div>
      </div>

      {/* 模型信息 */}
      <div className="px-4 py-3 bg-bg-tertiary rounded-xl border border-bg-border space-y-2">
        <p className="text-xs text-text-muted font-medium">技术信息</p>
        <div className="flex justify-between items-center">
          <span className="text-xs text-text-secondary">嵌入模型</span>
          <span className="text-xs text-text-primary font-mono">{health.embedding_model || '—'}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-xs text-text-secondary">最后更新</span>
          <span className="text-xs text-text-primary">{formatDate(health.last_updated)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-xs text-text-secondary">存储路径</span>
          <span className="text-[10px] text-text-muted font-mono truncate max-w-[180px]">{health.store_path}</span>
        </div>
      </div>

      {/* 文档列表 */}
      {health.documents.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs text-text-muted font-medium">已索引文档</p>
          {health.documents.map((doc, i) => (
            <div key={i} className="flex items-center gap-2 px-3 py-2 bg-bg-tertiary rounded-lg border border-bg-border">
              <FileText size={12} className="text-accent-blue shrink-0" />
              <span className="flex-1 text-xs text-text-primary truncate">{doc.name}</span>
              <span className="text-[10px] text-text-muted shrink-0">{doc.chunks} 块</span>
            </div>
          ))}
        </div>
      )}

      <button
        onClick={load}
        className="w-full py-2 rounded-lg text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover border border-bg-border transition-colors flex items-center justify-center gap-1.5"
      >
        <RefreshCw size={11} />
        刷新状态
      </button>
    </div>
  )
}

// ── 主组件 ───────────────────────────────────────────

interface KnowledgeBaseModalProps {
  open: boolean
  onClose: () => void
}

const TABS: { key: TabKey; icon: React.ReactNode; label: string }[] = [
  { key: 'documents', icon: <Database size={14} />, label: '文档列表' },
  { key: 'upload', icon: <Upload size={14} />, label: '上传文档' },
  { key: 'retrieval', icon: <Search size={14} />, label: '检索测试' },
  { key: 'health', icon: <Activity size={14} />, label: '健康状态' },
]

export const KnowledgeBaseModal: React.FC<KnowledgeBaseModalProps> = ({ open, onClose }) => {
  const [activeTab, setActiveTab] = useState<TabKey>('documents')
  const [refreshKey, setRefreshKey] = useState(0)
  const [adminToken, setAdminToken] = useState('')
  const [adminTokenSaved, setAdminTokenSaved] = useState(false)
  const [adminAccessError, setAdminAccessError] = useState<string | null>(null)

  const handleDataChanged = () => setRefreshKey(k => k + 1)

  useEffect(() => {
    if (!open) return
    setAdminToken(getAdminApiToken())
    setAdminTokenSaved(false)
    setAdminAccessError(null)
  }, [open])

  const handleSaveAdminToken = () => {
    const normalized = adminToken.trim()
    saveAdminApiToken(normalized)
    setAdminToken(normalized)
    setAdminTokenSaved(true)
    setAdminAccessError(null)
    setRefreshKey((key) => key + 1)
    window.setTimeout(() => setAdminTokenSaved(false), 2500)
  }

  return (
    <Modal open={open} onClose={onClose} title="知识库管理" width="max-w-2xl">
      <AdminTokenPanel
        token={adminToken}
        saved={adminTokenSaved}
        error={adminAccessError}
        description="远程访问知识库管理接口时需要。可在这里直接保存后刷新当前知识库视图。"
        onTokenChange={setAdminToken}
        onSave={handleSaveAdminToken}
        onClear={() => {
          setAdminToken('')
          saveAdminApiToken('')
          setAdminTokenSaved(false)
          setAdminAccessError(null)
          setRefreshKey((key) => key + 1)
        }}
      />

      {/* Tab 导航 */}
      <div className="flex gap-1 mb-5 p-1 bg-bg-tertiary rounded-xl border border-bg-border">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-all ${
              activeTab === tab.key
                ? 'bg-bg-secondary text-text-primary shadow-sm border border-bg-border'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {tab.icon}
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab 内容 */}
      {activeTab === 'documents' && (
        <DocumentsTab
          key={`docs-${refreshKey}`}
          onDeleted={handleDataChanged}
          onAdminAccessError={setAdminAccessError}
        />
      )}
      {activeTab === 'upload' && (
        <UploadTab onUploaded={handleDataChanged} onAdminAccessError={setAdminAccessError} />
      )}
      {activeTab === 'retrieval' && <RetrievalTab onAdminAccessError={setAdminAccessError} />}
      {activeTab === 'health' && (
        <HealthTab key={`health-${refreshKey}`} onAdminAccessError={setAdminAccessError} />
      )}
    </Modal>
  )
}
