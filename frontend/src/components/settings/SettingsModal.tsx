import React, { useEffect, useState, useCallback } from 'react'
import { Upload, CheckCircle, AlertCircle, RefreshCw, Database, Plus, Pencil, Trash2, UserCog, Check } from 'lucide-react'
import { Modal } from '../ui/Modal'
import { Button } from '../ui/Button'
import {
  getConfig, saveConfig, uploadDocuments, getDocStats, resetAgents,
  getSystemPrompts, createSystemPrompt, updateSystemPrompt, deleteSystemPrompt, activateSystemPrompt,
} from '../../api/client'
import type { DocStats, SystemPrompt } from '../../api/client'
import { useChatStore } from '../../stores/chatStore'

interface SettingsModalProps {
  open: boolean
  onClose: () => void
}

type Tab = 'general' | 'documents' | 'roles'

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
  const [promptSaving, setPromptSaving] = useState(false)
  const [activatingId, setActivatingId] = useState<string | null>(null)
  const [deletingPromptId, setDeletingPromptId] = useState<string | null>(null)

  const { setActivePromptId } = useChatStore()

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

  useEffect(() => {
    if (open) {
      loadConfig()
      loadPrompts()
    }
  }, [open, loadConfig, loadPrompts])

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
      setUploadResult({ ok: true, message: result.message })
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
  }

  const startCreate = (template?: { name: string; content: string }) => {
    setEditingPrompt(null)
    setIsCreating(true)
    setPromptName(template?.name ?? '')
    setPromptContent(template?.content ?? '')
  }

  const cancelEdit = () => {
    setEditingPrompt(null)
    setIsCreating(false)
    setPromptName('')
    setPromptContent('')
  }

  const handleSavePrompt = async () => {
    if (!promptName.trim() || !promptContent.trim()) return
    setPromptSaving(true)
    try {
      if (isCreating) {
        await createSystemPrompt(promptName.trim(), promptContent.trim())
      } else if (editingPrompt) {
        await updateSystemPrompt(editingPrompt.id, promptName.trim(), promptContent.trim())
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
      await activateSystemPrompt(id)
      setActivePromptId(id)
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

  return (
    <Modal open={open} onClose={onClose} title="设置" width="max-w-xl">
      {/* Tabs */}
      <div className="flex gap-1 mb-5 bg-bg-tertiary p-1 rounded-lg">
        {([['general', '通用设置'], ['documents', '知识库文档'], ['roles', '角色管理']] as [Tab, string][]).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id as Tab)}
            className={`flex-1 py-1.5 rounded-md text-xs font-medium transition-colors ${
              tab === id
                ? 'bg-bg-secondary text-text-primary shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

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
              {tavilyKeySet && (
                <span className="ml-2 text-accent-green">· 已配置 ✓</span>
              )}
            </p>
          </div>

          <div className="pt-2 flex items-center gap-3">
            <Button
              variant="primary"
              onClick={handleSaveGeneral}
              loading={saving}
            >
              {saveOk ? <CheckCircle size={14} /> : null}
              {saveOk ? '已保存' : '保存配置'}
            </Button>
            <Button
              variant="ghost"
              onClick={handleResetAgents}
              loading={resetting}
              title="清空 Agent 缓存，下次请求重新构建"
            >
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

      {/* Documents Tab */}
      {tab === 'documents' && (
        <div className="space-y-4">
          {/* Upload area */}
          <div
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors cursor-pointer ${
              dragOver
                ? 'border-accent-blue bg-accent-blue/5'
                : 'border-bg-border hover:border-accent-blue/50'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              handleUpload(e.dataTransfer.files)
            }}
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <input
              id="file-input"
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.md,.csv,.txt"
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
                <p className="text-xs text-text-secondary">支持 PDF、Word、Markdown、CSV、TXT</p>
              </div>
            )}
          </div>

          {/* Upload result */}
          {uploadResult && (
            <div
              className={`flex items-start gap-2.5 p-3 rounded-lg text-sm ${
                uploadResult.ok
                  ? 'bg-accent-green/10 border border-accent-green/30 text-accent-green'
                  : 'bg-accent-red/10 border border-accent-red/30 text-accent-red'
              }`}
            >
              {uploadResult.ok ? <CheckCircle size={15} className="shrink-0 mt-0.5" /> : <AlertCircle size={15} className="shrink-0 mt-0.5" />}
              {uploadResult.message}
            </div>
          )}

          {/* Stats */}
          <div className="flex gap-2">
            <Button variant="ghost" onClick={loadStats} loading={loadingStats} className="gap-2">
              <Database size={13} />
              查看知识库统计
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

      {/* Roles Tab */}
      {tab === 'roles' && (
        <div className="space-y-4">
          {/* Edit / Create form */}
          {(isCreating || editingPrompt) ? (
            <div className="bg-bg-tertiary rounded-xl p-4 space-y-3 border border-bg-border">
              <p className="text-xs font-medium text-text-primary">
                {isCreating ? '新建角色' : `编辑：${editingPrompt?.name}`}
              </p>
              <input
                className="input-base w-full text-sm"
                placeholder="角色名称"
                value={promptName}
                onChange={(e) => setPromptName(e.target.value)}
                maxLength={40}
              />
              <div className="relative">
                <textarea
                  className="input-base w-full text-sm resize-none leading-relaxed"
                  placeholder="System Prompt 内容，描述 AI 的角色、能力和回答风格…"
                  value={promptContent}
                  onChange={(e) => setPromptContent(e.target.value)}
                  rows={6}
                />
                <span className="absolute bottom-2 right-2.5 text-[10px] text-text-secondary/40">
                  {promptContent.length} 字
                </span>
              </div>
              <div className="flex gap-2 pt-1">
                <Button variant="primary" onClick={handleSavePrompt} loading={promptSaving} disabled={!promptName.trim() || !promptContent.trim()}>
                  保存
                </Button>
                <Button variant="ghost" onClick={cancelEdit}>
                  取消
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <p className="text-xs text-text-secondary">选择激活的 AI 角色，切换后下次对话生效</p>
              <Button variant="outline" onClick={() => startCreate()} className="gap-1.5 text-xs">
                <Plus size={12} />
                新建角色
              </Button>
            </div>
          )}

          {/* Prompts list */}
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
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
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
                      </div>
                      <p className="text-xs text-text-secondary mt-1 line-clamp-2 leading-relaxed">
                        {p.content}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
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

          {/* Templates */}
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
    </Modal>
  )
}
