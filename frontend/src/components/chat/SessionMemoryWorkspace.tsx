import React, { useEffect, useMemo, useState } from 'react'
import {
  Brain,
  Check,
  Edit3,
  Pin,
  Plus,
  RefreshCcw,
  Search,
  Send,
  Trash2,
  X,
} from 'lucide-react'
import {
  deleteSessionMemory,
  getSessionMemory,
  pinSessionMemory,
  summarizeSessionMemory,
  type SessionMemory,
  type SessionMemoryKind,
  updateSessionMemory,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'

type MemoryFilter = 'all' | SessionMemoryKind

interface SessionMemoryWorkspaceProps {
  open: boolean
  onClose: () => void
  interactionLocked?: boolean
}

function formatRelativeTime(timestamp: number): string {
  if (!timestamp) return '未知'
  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp))
  if (diffSeconds < 60) return '刚刚'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)} 分钟前`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)} 小时前`
  return `${Math.floor(diffSeconds / 86400)} 天前`
}

function sortMemories(memories: SessionMemory[]): SessionMemory[] {
  return [...memories].sort((a, b) => b.updated_at - a.updated_at)
}

function memoryKindLabel(kind: SessionMemoryKind): string {
  if (kind === 'summary') return '摘要'
  if (kind === 'decision') return '决策'
  if (kind === 'todo') return '待办'
  return '事实'
}

function memoryKindBadgeClass(kind: SessionMemoryKind): string {
  if (kind === 'summary') return 'border-accent-blue/30 bg-accent-blue/10 text-accent-blue'
  if (kind === 'decision') return 'border-accent-green/30 bg-accent-green/10 text-accent-green'
  if (kind === 'todo') return 'border-bg-border bg-bg-primary text-text-secondary'
  return 'border-bg-border bg-bg-primary text-text-secondary'
}

function upsertMemory(memories: SessionMemory[], memory: SessionMemory): SessionMemory[] {
  const next = memories.filter((item) => item.id !== memory.id)
  next.unshift(memory)
  return sortMemories(next)
}

export const SessionMemoryWorkspace: React.FC<SessionMemoryWorkspaceProps> = ({
  open,
  onClose,
  interactionLocked = false,
}) => {
  const currentSessionId = useChatStore((state) => state.currentSessionId)
  const currentSessionUpdatedAt = useChatStore((state) =>
    state.sessions.find((session) => session.session_id === state.currentSessionId)?.updated_at ?? 0,
  )
  const pushComposerSeed = useChatStore((state) => state.pushComposerSeed)
  const updateSession = useChatStore((state) => state.updateSession)

  const [memories, setMemories] = useState<SessionMemory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<MemoryFilter>('all')
  const [draftContent, setDraftContent] = useState('')
  const [draftKind, setDraftKind] = useState<SessionMemoryKind>('fact')
  const [saving, setSaving] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editingContent, setEditingContent] = useState('')
  const [editingKind, setEditingKind] = useState<SessionMemoryKind>('fact')
  const [updatingId, setUpdatingId] = useState<string | null>(null)
  const [summarizing, setSummarizing] = useState(false)

  useEffect(() => {
    if (!open) return

    if (!currentSessionId) {
      setMemories([])
      setLoading(false)
      setError('')
      setNotice('')
      setEditingId(null)
      setEditingContent('')
      setEditingKind('fact')
      return
    }

    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const items = await getSessionMemory(currentSessionId)
        if (cancelled) return
        setMemories(sortMemories(items))
      } catch (err) {
        if (cancelled) return
        setError((err as Error).message ?? '加载会话记忆失败。')
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
  }, [open, currentSessionId, currentSessionUpdatedAt])

  const filteredMemories = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return memories.filter((memory) => {
      if (filter !== 'all' && memory.kind !== filter) return false
      if (!keyword) return true
      return (
        memory.content.toLowerCase().includes(keyword) ||
        memoryKindLabel(memory.kind).toLowerCase().includes(keyword)
      )
    })
  }, [filter, memories, search])

  const counts = useMemo(
    () => ({
      all: memories.length,
      summary: memories.filter((item) => item.kind === 'summary').length,
      fact: memories.filter((item) => item.kind === 'fact').length,
      decision: memories.filter((item) => item.kind === 'decision').length,
      todo: memories.filter((item) => item.kind === 'todo').length,
    }),
    [memories],
  )

  if (!open) return null

  const touchSession = () => {
    if (!currentSessionId) return
    updateSession(currentSessionId, {
      updated_at: Date.now() / 1000,
    })
  }

  const handleRefresh = async () => {
    if (!currentSessionId) return
    setLoading(true)
    setError('')
    setNotice('')
    setEditingId(null)
    try {
      const items = await getSessionMemory(currentSessionId)
      setMemories(sortMemories(items))
    } catch (err) {
      setError((err as Error).message ?? '加载会话记忆失败。')
    } finally {
      setLoading(false)
    }
  }

  const handleAddMemory = async () => {
    const content = draftContent.trim()
    if (!currentSessionId || !content) return

    setSaving(true)
    setError('')
    setNotice('')
    try {
      const result = await pinSessionMemory(currentSessionId, {
        content,
        kind: draftKind,
      })
      setMemories((current) => upsertMemory(current, result.memory))
      setDraftContent('')
      setNotice(result.created ? '已固定一条新的会话记忆。' : '记忆已存在，已为你刷新时间。')
      touchSession()
    } catch (err) {
      setError((err as Error).message ?? '固定会话记忆失败。')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteMemory = async (memory: SessionMemory) => {
    if (!currentSessionId) return
    setDeletingId(memory.id)
    setError('')
    setNotice('')
    try {
      await deleteSessionMemory(currentSessionId, memory.id)
      setMemories((current) => current.filter((item) => item.id !== memory.id))
      if (editingId === memory.id) {
        handleCancelEdit()
      }
      setNotice('已删除这条会话记忆。')
      touchSession()
    } catch (err) {
      setError((err as Error).message ?? '删除会话记忆失败。')
    } finally {
      setDeletingId(null)
    }
  }

  const handleStartEdit = (memory: SessionMemory) => {
    setEditingId(memory.id)
    setEditingContent(memory.content)
    setEditingKind(memory.kind)
    setError('')
    setNotice('')
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditingContent('')
    setEditingKind('fact')
    setUpdatingId(null)
  }

  const handleSaveEdit = async (memory: SessionMemory) => {
    if (!currentSessionId) return
    const nextContent = editingContent.trim()
    if (!nextContent) {
      setError('记忆内容不能为空。')
      return
    }

    setUpdatingId(memory.id)
    setError('')
    setNotice('')
    try {
      const updated = await updateSessionMemory(currentSessionId, memory.id, {
        content: nextContent,
        kind: editingKind,
      })
      setMemories((current) => upsertMemory(current, updated))
      setNotice('记忆已更新。')
      touchSession()
      handleCancelEdit()
    } catch (err) {
      setError((err as Error).message ?? '更新会话记忆失败。')
    } finally {
      setUpdatingId(null)
    }
  }

  const handleGenerateSummaryMemory = async () => {
    if (!currentSessionId) return
    setSummarizing(true)
    setError('')
    setNotice('')
    try {
      const result = await summarizeSessionMemory(currentSessionId)
      setMemories((current) => upsertMemory(current, result.memory))
      if (result.reason === 'up_to_date') {
        setNotice('摘要记忆已经是最新状态。')
      } else if (result.created) {
        setNotice('已生成新的摘要记忆。')
      } else {
        setNotice('摘要记忆已刷新。')
      }
      touchSession()
    } catch (err) {
      setError((err as Error).message ?? '生成摘要记忆失败。')
    } finally {
      setSummarizing(false)
    }
  }

  const handleSendToComposer = (memory: SessionMemory) => {
    pushComposerSeed({
      text: `请记住这条会话记忆：[${memoryKindLabel(memory.kind)}] ${memory.content}`,
    })
  }

  const workspaceBody = (
    <section className="flex h-full w-full flex-col border-l border-bg-border bg-bg-primary lg:w-[21rem]">
      <div className="flex items-start justify-between gap-3 border-b border-bg-border px-4 py-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
            <Brain size={14} className="text-accent-green" />
            记忆工作区
          </div>
          <p className="mt-1 text-[11px] text-text-secondary">
            持续记录本次会话里的长期约束、关键决策和重要事实。
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => {
              void handleGenerateSummaryMemory()
            }}
            disabled={!currentSessionId || summarizing || interactionLocked}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
            title="生成摘要记忆"
          >
            {summarizing ? <RefreshCcw size={14} className="animate-spin" /> : <Brain size={14} />}
          </button>
          <button
            type="button"
            onClick={() => void handleRefresh()}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
            title="刷新记忆"
          >
            <RefreshCcw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary lg:hidden"
            title="关闭记忆工作区"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      <div className="border-b border-bg-border px-4 py-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">已固定</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{counts.all}</div>
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">决策</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{counts.decision}</div>
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">事实</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{counts.fact}</div>
          </div>
          <div className="rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
            <div className="text-[10px] uppercase tracking-wide text-text-secondary/70">待办</div>
            <div className="mt-1 text-sm font-semibold text-text-primary">{counts.todo}</div>
          </div>
        </div>

        <label className="mt-3 flex items-center gap-2 rounded-xl border border-bg-border bg-bg-secondary px-3 py-2">
          <Search size={13} className="text-text-secondary" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="搜索记忆内容"
            className="w-full bg-transparent text-xs text-text-primary outline-none placeholder:text-text-secondary"
          />
        </label>

        <div className="mt-3 flex flex-wrap gap-2">
          {([
            ['all', `全部 ${counts.all}`],
            ['decision', `决策 ${counts.decision}`],
            ['fact', `事实 ${counts.fact}`],
            ['todo', `待办 ${counts.todo}`],
            ['summary', `摘要 ${counts.summary}`],
          ] as Array<[MemoryFilter, string]>).map(([value, label]) => {
            const active = filter === value
            return (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                className={`rounded-full px-2.5 py-1 text-[11px] transition-colors ${
                  active
                    ? 'bg-accent-green/15 text-accent-green'
                    : 'bg-bg-secondary text-text-secondary hover:text-text-primary'
                }`}
              >
                {label}
              </button>
            )
          })}
        </div>

        <div className="mt-3 rounded-2xl border border-bg-border bg-bg-secondary/70 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-[11px] font-medium text-text-primary">手动添加记忆</span>
            <select
              value={draftKind}
              onChange={(event) => setDraftKind(event.target.value as SessionMemoryKind)}
              className="rounded-lg border border-bg-border bg-bg-primary px-2 py-1 text-[11px] text-text-primary outline-none"
            >
              <option value="fact">事实</option>
              <option value="decision">决策</option>
              <option value="todo">待办</option>
              <option value="summary">摘要</option>
            </select>
          </div>
          <textarea
            value={draftContent}
            onChange={(event) => setDraftContent(event.target.value)}
            rows={4}
            placeholder="例如：这次会话用于 Q2 预算评审，所有输出都需要保持中文，汇报对象是 CFO。"
            className="w-full resize-none rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-xs leading-5 text-text-primary outline-none placeholder:text-text-secondary"
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-[11px] text-text-secondary">
              提示：你也可以直接在聊天区把任意助手回复固定为记忆。
            </span>
            <button
              type="button"
              onClick={() => {
                void handleAddMemory()
              }}
              disabled={saving || !currentSessionId || !draftContent.trim()}
              className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2.5 py-1.5 text-[11px] text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? (
                <RefreshCcw size={11} className="animate-spin" />
              ) : (
                <Plus size={11} />
              )}
              添加记忆
            </button>
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {notice && (
          <div className="mb-3 rounded-2xl border border-accent-green/30 bg-accent-green/10 px-4 py-3 text-xs text-accent-green">
            {notice}
          </div>
        )}

        {!currentSessionId ? (
          <div className="rounded-2xl border border-dashed border-bg-border px-4 py-10 text-center text-xs text-text-secondary">
            先开始一段会话，再来固定记忆。
          </div>
        ) : error ? (
          <div className="rounded-2xl border border-accent-red/30 bg-accent-red/10 px-4 py-3 text-xs text-accent-red">
            {error}
          </div>
        ) : loading && memories.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-xs text-text-secondary">
            正在加载会话记忆...
          </div>
        ) : filteredMemories.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-bg-border px-4 py-10 text-center text-xs text-text-secondary">
            当前筛选条件下没有匹配到记忆。
          </div>
        ) : (
          <div className="space-y-3">
            {filteredMemories.map((memory) => {
              const deleting = deletingId === memory.id
              const editing = editingId === memory.id
              const updating = updatingId === memory.id
              return (
                <article
                  key={memory.id}
                  className="rounded-2xl border border-bg-border bg-bg-secondary/60 p-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] ${memoryKindBadgeClass(memory.kind)}`}
                        >
                          {memoryKindLabel(memory.kind)}
                        </span>
                        <span className="text-[11px] text-text-secondary">
                          更新于 {formatRelativeTime(memory.updated_at)}
                        </span>
                      </div>
                      {editing ? (
                        <div className="mt-2 space-y-2">
                          <select
                            value={editingKind}
                            onChange={(event) => setEditingKind(event.target.value as SessionMemoryKind)}
                            disabled={updating}
                            className="w-full rounded-lg border border-bg-border bg-bg-primary px-2 py-1 text-[11px] text-text-primary outline-none disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <option value="fact">事实</option>
                            <option value="decision">决策</option>
                            <option value="todo">待办</option>
                            <option value="summary">摘要</option>
                          </select>
                          <textarea
                            value={editingContent}
                            onChange={(event) => setEditingContent(event.target.value)}
                            rows={4}
                            disabled={updating}
                            className="w-full resize-none rounded-xl border border-bg-border bg-bg-primary px-3 py-2 text-xs leading-5 text-text-primary outline-none placeholder:text-text-secondary disabled:cursor-not-allowed disabled:opacity-50"
                          />
                        </div>
                      ) : (
                        <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-5 text-text-primary">
                          {memory.content}
                        </p>
                      )}
                    </div>
                    <Pin size={14} className="mt-0.5 shrink-0 text-accent-green/70" />
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {editing ? (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            void handleSaveEdit(memory)
                          }}
                          disabled={updating || !editingContent.trim()}
                          className="inline-flex items-center gap-1 rounded-lg border border-accent-green/20 px-2 py-1 text-[11px] text-accent-green transition-colors hover:border-accent-green/40 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {updating ? (
                            <RefreshCcw size={11} className="animate-spin" />
                          ) : (
                            <Check size={11} />
                          )}
                          保存
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelEdit}
                          disabled={updating}
                          className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <X size={11} />
                          取消
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => handleSendToComposer(memory)}
                          disabled={interactionLocked}
                          className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Send size={11} />
                          发送到输入框
                        </button>
                        <button
                          type="button"
                          onClick={() => handleStartEdit(memory)}
                          disabled={interactionLocked}
                          className="inline-flex items-center gap-1 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          <Edit3 size={11} />
                          编辑
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            void handleDeleteMemory(memory)
                          }}
                          disabled={deleting}
                          className="inline-flex items-center gap-1 rounded-lg border border-accent-red/20 px-2 py-1 text-[11px] text-accent-red transition-colors hover:border-accent-red/40 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          {deleting ? (
                            <RefreshCcw size={11} className="animate-spin" />
                          ) : (
                            <Trash2 size={11} />
                          )}
                          删除
                        </button>
                        {memory.kind === 'decision' && (
                          <span className="inline-flex items-center gap-1 rounded-lg border border-accent-green/20 px-2 py-1 text-[11px] text-accent-green">
                            <Check size={11} />
                            稳定决策
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </div>
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
