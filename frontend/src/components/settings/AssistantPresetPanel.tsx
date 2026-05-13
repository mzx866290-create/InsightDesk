import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  activateAssistantPreset,
  createAssistantPreset,
  deleteAssistantPreset,
  getAssistantPresets,
  updateAssistantPreset,
  type AssistantPreset,
  type AssistantPresetPayload,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'

type PresetFormState = {
  id: string
  name: string
  avatar: string
  systemPromptId: string
  startersText: string
  webSearchEnabled: boolean
  knowledgeBaseEnabled: boolean
  mcpServersText: string
}

const EMPTY_FORM: PresetFormState = {
  id: '',
  name: '',
  avatar: '🤖',
  systemPromptId: '',
  startersText: '',
  webSearchEnabled: false,
  knowledgeBaseEnabled: true,
  mcpServersText: '',
}

function formFromPreset(preset: AssistantPreset): PresetFormState {
  return {
    id: preset.id,
    name: preset.name,
    avatar: preset.avatar || '🤖',
    systemPromptId: preset.system_prompt_id,
    startersText: preset.starters.join('\n'),
    webSearchEnabled: preset.tool_config.web_search_enabled,
    knowledgeBaseEnabled: preset.tool_config.knowledge_base_enabled,
    mcpServersText: preset.tool_config.mcp_servers_enabled.join(', '),
  }
}

function parseDelimitedList(value: string): string[] {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function AssistantPresetPanel() {
  const panels = useChatStore((state) => state.panels)
  const activeAssistantPresetId = useChatStore((state) => state.activeAssistantPresetId)
  const setActiveAssistantPresetId = useChatStore((state) => state.setActiveAssistantPresetId)
  const setActivePromptId = useChatStore((state) => state.setActivePromptId)
  const updatePanelModel = useChatStore((state) => state.updatePanelModel)
  const setWebSearchEnabled = useChatStore((state) => state.setWebSearchEnabled)
  const setKnowledgeBaseEnabled = useChatStore((state) => state.setKnowledgeBaseEnabled)
  const setEnabledMcpServers = useChatStore((state) => state.setEnabledMcpServers)

  const [presets, setPresets] = useState<AssistantPreset[]>([])
  const [form, setForm] = useState<PresetFormState>(EMPTY_FORM)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)

  const activePresetId = activeAssistantPresetId || presets.find((preset) => preset.is_active)?.id || ''
  const firstPanel = panels[0] ?? null
  const isEditing = Boolean(form.id)
  const canSave = Boolean(form.name.trim() && firstPanel)

  const loadPresets = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const nextPresets = await getAssistantPresets()
      if (!mountedRef.current) return
      setPresets(nextPresets)
      const activePreset = nextPresets.find((preset) => preset.is_active) ?? nextPresets[0]
      if (activePreset) {
        setActiveAssistantPresetId(activePreset.id)
      }
    } catch (err) {
      if (!mountedRef.current) return
      setError((err as Error).message || '加载助手预设失败')
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [setActiveAssistantPresetId])

  useEffect(() => {
    mountedRef.current = true
    void loadPresets()

    return () => {
      mountedRef.current = false
    }
  }, [loadPresets])

  const payload = useMemo<AssistantPresetPayload | null>(() => {
    if (!firstPanel) return null
    return {
      name: form.name.trim(),
      avatar: form.avatar.trim() || '🤖',
      system_prompt_id: form.systemPromptId.trim(),
      default_model_config: firstPanel.modelConfig,
      tool_config: {
        web_search_enabled: form.webSearchEnabled,
        knowledge_base_enabled: form.knowledgeBaseEnabled,
        mcp_servers_enabled: parseDelimitedList(form.mcpServersText),
      },
      starters: parseDelimitedList(form.startersText),
    }
  }, [firstPanel, form])

  const applyPreset = async (preset: AssistantPreset) => {
    setError(null)
    try {
      await activateAssistantPreset(preset.id)
      setActiveAssistantPresetId(preset.id)
      setActivePromptId(preset.system_prompt_id || null)
      setWebSearchEnabled(preset.tool_config.web_search_enabled)
      setKnowledgeBaseEnabled(preset.tool_config.knowledge_base_enabled)
      setEnabledMcpServers(preset.tool_config.mcp_servers_enabled)
      if (firstPanel) {
        updatePanelModel(firstPanel.id, {
          ...preset.default_model_config,
          panel_id: firstPanel.id,
        })
      }
      setPresets((items) =>
        items.map((item) => ({ ...item, is_active: item.id === preset.id })),
      )
    } catch (err) {
      setError((err as Error).message || '应用助手预设失败')
    }
  }

  const savePreset = async () => {
    if (!payload || !canSave) return
    setSaving(true)
    setError(null)
    try {
      if (isEditing) {
        await updateAssistantPreset(form.id, payload)
      } else {
        await createAssistantPreset(payload)
      }
      setForm(EMPTY_FORM)
      await loadPresets()
    } catch (err) {
      setError((err as Error).message || '保存助手预设失败')
    } finally {
      setSaving(false)
    }
  }

  const deletePreset = async (preset: AssistantPreset) => {
    setError(null)
    try {
      await deleteAssistantPreset(preset.id)
      if (form.id === preset.id) setForm(EMPTY_FORM)
      await loadPresets()
    } catch (err) {
      setError((err as Error).message || '删除助手预设失败')
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-text-primary">助手预设</h3>
        <p className="mt-1 text-xs leading-5 text-text-secondary">
          将系统提示、默认模型、工具开关和开场问题绑定成一个可切换的工作台预设。
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-accent-red/30 bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
          {error}
        </div>
      )}

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(20rem,24rem)]">
        <div className="space-y-2">
          {loading ? (
            <div className="rounded-lg border border-bg-border px-3 py-4 text-xs text-text-secondary">
              加载中...
            </div>
          ) : (
            presets.map((preset) => (
              <div
                key={preset.id}
                className="rounded-xl border border-bg-border bg-bg-primary/40 p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
                      <span>{preset.avatar || '🤖'}</span>
                      <span className="truncate">{preset.name}</span>
                      {(preset.id === activePresetId || preset.is_active) && (
                        <span className="rounded-full bg-accent-green/15 px-2 py-0.5 text-[10px] text-accent-green">
                          当前
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-[11px] text-text-secondary">
                      {preset.default_model_config.model} · 知识库
                      {preset.tool_config.knowledge_base_enabled ? '开' : '关'} · 联网
                      {preset.tool_config.web_search_enabled ? '开' : '关'}
                    </div>
                    {preset.starters.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {preset.starters.slice(0, 3).map((starter) => (
                          <span
                            key={starter}
                            className="rounded-full bg-bg-tertiary px-2 py-0.5 text-[10px] text-text-secondary"
                          >
                            {starter}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <button
                      type="button"
                      className="btn-secondary px-2 py-1 text-[11px]"
                      aria-label={`Apply assistant preset ${preset.name}`}
                      onClick={() => void applyPreset(preset)}
                    >
                      应用
                    </button>
                    <button
                      type="button"
                      className="btn-secondary px-2 py-1 text-[11px]"
                      aria-label={`Edit assistant preset ${preset.name}`}
                      onClick={() => setForm(formFromPreset(preset))}
                    >
                      编辑
                    </button>
                    <button
                      type="button"
                      className="rounded-md border border-accent-red/30 px-2 py-1 text-[11px] text-accent-red"
                      aria-label={`Delete assistant preset ${preset.name}`}
                      onClick={() => void deletePreset(preset)}
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="rounded-xl border border-bg-border bg-bg-primary/50 p-3">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium text-text-primary">
              {isEditing ? '编辑预设' : '新建预设'}
            </div>
            {isEditing && (
              <button
                type="button"
                className="text-[11px] text-text-secondary hover:text-text-primary"
                onClick={() => setForm(EMPTY_FORM)}
              >
                取消编辑
              </button>
            )}
          </div>

          <div className="space-y-3">
            <input
              aria-label="Assistant preset name"
              className="input-base w-full text-xs"
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="预设名称"
            />
            <div className="grid grid-cols-[4rem_minmax(0,1fr)] gap-2">
              <input
                aria-label="Assistant preset avatar"
                className="input-base text-xs"
                value={form.avatar}
                onChange={(event) => setForm({ ...form, avatar: event.target.value })}
                placeholder="头像"
              />
              <input
                aria-label="Assistant preset system prompt id"
                className="input-base text-xs"
                value={form.systemPromptId}
                onChange={(event) => setForm({ ...form, systemPromptId: event.target.value })}
                placeholder="system_prompt_id（可选）"
              />
            </div>
            <textarea
              aria-label="Assistant preset starters"
              className="input-base min-h-20 w-full text-xs"
              value={form.startersText}
              onChange={(event) => setForm({ ...form, startersText: event.target.value })}
              placeholder="开场问题，每行一个"
            />
            <div className="grid gap-2 text-xs text-text-secondary">
              <label className="flex items-center gap-2">
                <input
                  aria-label="Enable web search by default"
                  type="checkbox"
                  checked={form.webSearchEnabled}
                  onChange={(event) =>
                    setForm({ ...form, webSearchEnabled: event.target.checked })}
                />
                默认启用联网搜索
              </label>
              <label className="flex items-center gap-2">
                <input
                  aria-label="Enable knowledge base by default"
                  type="checkbox"
                  checked={form.knowledgeBaseEnabled}
                  onChange={(event) =>
                    setForm({ ...form, knowledgeBaseEnabled: event.target.checked })}
                />
                默认启用知识库
              </label>
            </div>
            <input
              aria-label="Assistant preset MCP servers"
              className="input-base w-full text-xs"
              value={form.mcpServersText}
              onChange={(event) => setForm({ ...form, mcpServersText: event.target.value })}
              placeholder="MCP servers，逗号分隔；默认留空"
            />
            <button
              type="button"
              aria-label="Save assistant preset"
              className="btn-primary w-full text-xs disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!canSave || saving}
              onClick={() => void savePreset()}
            >
              {saving ? '保存中...' : isEditing ? '更新预设' : '保存为预设'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
