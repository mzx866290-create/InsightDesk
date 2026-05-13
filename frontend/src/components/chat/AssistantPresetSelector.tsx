import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, Sparkles } from 'lucide-react'

import {
  activateAssistantPreset,
  getAssistantPresets,
  type AssistantPreset,
} from '../../api/client'
import { useChatStore } from '../../stores/chatStore'

export function AssistantPresetSelector() {
  const panels = useChatStore((state) => state.panels)
  const activeAssistantPresetId = useChatStore((state) => state.activeAssistantPresetId)
  const setActiveAssistantPresetId = useChatStore((state) => state.setActiveAssistantPresetId)
  const setActivePromptId = useChatStore((state) => state.setActivePromptId)
  const updatePanelModel = useChatStore((state) => state.updatePanelModel)
  const setWebSearchEnabled = useChatStore((state) => state.setWebSearchEnabled)
  const setKnowledgeBaseEnabled = useChatStore((state) => state.setKnowledgeBaseEnabled)
  const setEnabledMcpServers = useChatStore((state) => state.setEnabledMcpServers)

  const [open, setOpen] = useState(false)
  const [presets, setPresets] = useState<AssistantPreset[]>([])
  const mountedRef = useRef(true)

  const loadPresets = useCallback(() => {
    getAssistantPresets()
      .then((items) => {
        if (mountedRef.current) setPresets(items)
      })
      .catch(() => {
        if (mountedRef.current) setPresets([])
      })
  }, [])

  useEffect(() => {
    mountedRef.current = true
    loadPresets()

    return () => {
      mountedRef.current = false
    }
  }, [loadPresets])

  useEffect(() => {
    if (open) loadPresets()
  }, [loadPresets, open])

  const activePreset = useMemo(
    () =>
      presets.find((preset) => preset.id === activeAssistantPresetId && preset.is_active) ??
      presets.find((preset) => preset.id === activeAssistantPresetId) ??
      presets.find((preset) => preset.is_active) ??
      presets[0] ??
      null,
    [activeAssistantPresetId, presets],
  )

  const applyPreset = async (preset: AssistantPreset) => {
    try {
      await activateAssistantPreset(preset.id)
      setActiveAssistantPresetId(preset.id)
      setActivePromptId(preset.system_prompt_id || null)
      setWebSearchEnabled(preset.tool_config.web_search_enabled)
      setKnowledgeBaseEnabled(preset.tool_config.knowledge_base_enabled)
      setEnabledMcpServers(preset.tool_config.mcp_servers_enabled)
      if (panels[0]) {
        updatePanelModel(panels[0].id, {
          ...preset.default_model_config,
          panel_id: panels[0].id,
        })
      }
      setOpen(false)
    } catch (error) {
      console.error('Failed to activate assistant preset', error)
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1.5 rounded-lg border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        title="切换助手预设"
      >
        <Sparkles size={11} className="text-accent-blue" />
        <span className="max-w-[8rem] truncate">
          {activePreset?.name ?? '助手预设'}
        </span>
        <ChevronDown size={11} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-bg-border bg-bg-secondary p-2 shadow-2xl">
          {presets.length > 0 ? (
            <div className="space-y-1">
              {presets.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => void applyPreset(preset)}
                  className={`w-full rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                    preset.id === activePreset?.id
                      ? 'bg-accent-blue/15 text-accent-blue'
                      : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">{preset.name}</span>
                    <span className="shrink-0 text-[10px] opacity-70">
                      {preset.tool_config.web_search_enabled ? '联网' : '本地'}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate text-[10px] opacity-70">
                    {preset.default_model_config.model}
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-3 py-2 text-xs text-text-secondary">还没有助手预设</div>
          )}
        </div>
      )}

      {open && <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />}
    </div>
  )
}
