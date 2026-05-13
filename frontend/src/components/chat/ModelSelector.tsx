import React, { useEffect, useMemo, useState } from 'react'
import { ChevronDown, Cloud, Cpu, X } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import {
  defaultBaseUrlForConnectionType,
  defaultModelForConnectionType,
  getConnectionTypeLabel,
  getProviderCatalog,
  getOllamaModels,
  normalizeConnectionType,
} from '../../api/client'
import type { ConnectionType, ModelConfig, ProviderCatalogResponse } from '../../api/client'

interface ModelSelectorProps {
  panelId: string
  modelConfig: ModelConfig
  onRemove?: () => void
  canRemove: boolean
  disabled?: boolean
}

const COMPATIBLE_PRESETS: Array<{
  label: string
  description: string
  baseUrl: string
  defaultModel?: string
}> = [
  {
    label: 'OpenRouter',
    description: '托管的 OpenAI 兼容网关',
    baseUrl: 'https://openrouter.ai/api/v1',
    defaultModel: 'openai/gpt-4o-mini',
  },
  {
    label: 'LM Studio',
    description: '本地 OpenAI 兼容服务',
    baseUrl: 'http://localhost:1234/v1',
  },
  {
    label: 'vLLM / OneAPI',
    description: '自托管兼容网关',
    baseUrl: 'http://localhost:8000/v1',
  },
]

const PROVIDER_BUTTONS: Array<{
  id: ConnectionType
  icon: 'cloud' | 'cpu'
  label: string
}> = [
  { id: 'openai_compatible', icon: 'cloud', label: 'OpenAI 兼容' },
  { id: 'ollama', icon: 'cpu', label: 'Ollama' },
  { id: 'deepseek', icon: 'cloud', label: 'DeepSeek' },
  { id: 'anthropic', icon: 'cloud', label: 'Anthropic' },
  { id: 'google', icon: 'cloud', label: 'Google Gemini' },
]

const CONNECTION_TYPES: ConnectionType[] = [
  'ollama',
  'openai_compatible',
  'deepseek',
  'anthropic',
  'google',
]

function isConnectionType(value: string): value is ConnectionType {
  return CONNECTION_TYPES.includes(value as ConnectionType)
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  panelId,
  modelConfig,
  onRemove,
  canRemove,
  disabled = false,
}) => {
  const {
    updatePanelModel,
    modelPresets,
    cloudModelProfiles,
    saveModelPreset,
    deleteModelPreset,
    applyModelPreset,
    applyCloudModelProfile,
    setSettingsOpen,
  } = useChatStore()
  const [open, setOpen] = useState(false)
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [customModel, setCustomModel] = useState('')
  const [presetName, setPresetName] = useState('')
  const [providerCatalog, setProviderCatalog] = useState<ProviderCatalogResponse | null>(null)
  const [providerCatalogLoaded, setProviderCatalogLoaded] = useState(false)

  const connectionType = normalizeConnectionType(
    modelConfig.connection_type ?? modelConfig.provider,
    modelConfig.base_url,
  )
  const connectionLabel = getConnectionTypeLabel(modelConfig)
  const providerButtons = useMemo(() => {
    if (!providerCatalog?.providers.length) return PROVIDER_BUTTONS

    const availableTypes = new Set(
      providerCatalog.providers
        .map((provider) => provider.connection_type)
        .filter(isConnectionType),
    )
    const availableButtons = PROVIDER_BUTTONS.filter((button) => availableTypes.has(button.id))
    return availableButtons.length > 0 ? availableButtons : PROVIDER_BUTTONS
  }, [providerCatalog])

  useEffect(() => {
    if (!open || providerCatalogLoaded) return
    let cancelled = false

    getProviderCatalog()
      .then((catalog) => {
        if (!cancelled) {
          setProviderCatalog(catalog)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProviderCatalog(null)
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProviderCatalogLoaded(true)
        }
      })

    return () => {
      cancelled = true
    }
  }, [open, providerCatalogLoaded])

  useEffect(() => {
    if (!open) return
    if (connectionType === 'ollama') {
      getOllamaModels(modelConfig.base_url).then(setOllamaModels).catch(() => setOllamaModels([]))
      return
    }
    setOllamaModels([])
  }, [connectionType, modelConfig.base_url, open])

  const handleConnectionTypeChange = (nextType: ConnectionType) => {
    updatePanelModel(panelId, {
      connection_type: nextType,
      provider: nextType,
      model: defaultModelForConnectionType(nextType),
      base_url: defaultBaseUrlForConnectionType(nextType),
      api_key: '',
      api_key_ref: '',
    })
  }

  const applyCompatiblePreset = (preset: (typeof COMPATIBLE_PRESETS)[number]) => {
    updatePanelModel(panelId, {
      connection_type: 'openai_compatible',
      provider: 'openai_compatible',
      base_url: preset.baseUrl,
      model:
        preset.defaultModel ??
        modelConfig.model ??
        defaultModelForConnectionType('openai_compatible'),
      api_key: preset.baseUrl.startsWith('http://localhost') ? '' : modelConfig.api_key,
      api_key_ref: modelConfig.api_key_ref,
    })
  }

  const shortModel =
    modelConfig.model.length > 18 ? `${modelConfig.model.slice(0, 16)}...` : modelConfig.model
  const agentModeOptions: Array<{
    id: ModelConfig['agent_mode']
    label: string
    description: string
  }> = [
    {
      id: 'auto',
      label: '智能体',
      description: '保留知识库、联网搜索和工具编排能力',
    },
    {
      id: 'plain_chat',
      label: '直连',
      description: '绕过智能体，仅进行纯文本生成',
    },
  ]

  const handleSavePreset = () => {
    if (disabled) return
    const trimmedName = presetName.trim()
    if (!trimmedName) return
    saveModelPreset(trimmedName, modelConfig)
    setPresetName('')
  }

  return (
    <div className="relative flex min-w-0 items-center gap-1.5">
      {connectionType === 'ollama' ? (
        <Cpu size={12} className="shrink-0 text-accent-green" />
      ) : (
        <Cloud size={12} className="shrink-0 text-accent-blue" />
      )}

      <button
        type="button"
        onClick={() => {
          if (disabled) return
          setOpen(!open)
        }}
        data-testid={`model-selector-trigger-${panelId}`}
        disabled={disabled}
        className="flex min-w-0 items-center gap-1 text-xs text-text-secondary transition-colors hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span className="max-w-[120px] truncate">{shortModel}</span>
        <span className="hidden text-[10px] text-text-secondary/60 sm:inline">{connectionLabel}</span>
        <ChevronDown
          size={11}
          className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {canRemove && (
        <button
          type="button"
          onClick={onRemove}
          disabled={disabled}
          className="ml-1 text-text-secondary transition-colors hover:text-accent-red disabled:cursor-not-allowed disabled:opacity-40"
          title="移除此面板"
        >
          <X size={12} />
        </button>
      )}

      {open && (
        <div
          data-testid={`model-selector-menu-${panelId}`}
          className="absolute left-0 top-full z-50 mt-1 w-[min(20rem,calc(100vw-1rem))] max-h-[min(70vh,38rem)] max-w-[calc(100vw-1rem)] overflow-y-auto animate-fade-in rounded-xl border border-bg-border bg-bg-secondary p-3 shadow-2xl sm:w-80"
          onClick={(event) => event.stopPropagation()}
        >
          <div className="mb-3 rounded-lg bg-bg-tertiary p-1">
            <div className="grid grid-cols-2 gap-1">
              {providerButtons.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  data-testid={`model-selector-connection-${panelId}-${item.id}`}
                  onClick={() => handleConnectionTypeChange(item.id)}
                  disabled={disabled}
                  className={`flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs font-medium transition-colors ${
                    connectionType === item.id
                      ? 'bg-accent-blue text-white'
                      : 'text-text-secondary hover:text-text-primary'
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                >
                  {item.icon === 'cpu' ? <Cpu size={11} /> : <Cloud size={11} />}
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {connectionType === 'ollama' ? (
            <div className="space-y-2">
              {ollamaModels.length > 0 ? (
                <div>
                  <div className="mb-1.5 text-[10px] uppercase tracking-wide text-text-secondary">
                    已安装模型
                  </div>
                  <div className="max-h-40 space-y-0.5 overflow-y-auto">
                    {ollamaModels.map((model) => (
                      <button
                        key={model}
                        type="button"
                        onClick={() => {
                          if (disabled) return
                          updatePanelModel(panelId, { model })
                          setOpen(false)
                        }}
                        disabled={disabled}
                        className={`w-full rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors ${
                          modelConfig.model === model
                            ? 'bg-accent-blue/20 text-accent-blue'
                            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        {model}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="py-2 text-center text-xs text-text-secondary">未检测到 Ollama 模型</p>
              )}

              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                  基础 URL
                </div>
                <input
                  className="input-base w-full text-xs"
                  value={modelConfig.base_url}
                  onChange={(event) => updatePanelModel(panelId, { base_url: event.target.value })}
                  placeholder="http://localhost:11434"
                  disabled={disabled}
                />
              </div>

              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                  自定义模型名
                </div>
                <div className="flex gap-1.5">
                  <input
                    className="input-base flex-1 text-xs"
                    value={customModel}
                    onChange={(event) => setCustomModel(event.target.value)}
                    placeholder="qwen3.5-2B:latest"
                    disabled={disabled}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && customModel.trim()) {
                        updatePanelModel(panelId, { model: customModel.trim() })
                        setCustomModel('')
                        setOpen(false)
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="btn-primary px-2 text-xs"
                    disabled={disabled}
                    onClick={() => {
                      if (!customModel.trim()) return
                      updatePanelModel(panelId, { model: customModel.trim() })
                      setCustomModel('')
                      setOpen(false)
                    }}
                  >
                    应用
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div>
                <div className="mb-1 flex items-center justify-between gap-2">
                  <div className="text-[10px] uppercase tracking-wide text-text-secondary">
                    已保存云端配置
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSettingsOpen(true)
                      setOpen(false)
                    }}
                    className="text-[11px] text-accent-blue transition-colors hover:text-accent-blue-hover"
                  >
                    管理
                  </button>
                </div>

                {cloudModelProfiles.length > 0 ? (
                  <div
                    data-testid={`model-selector-cloud-profile-list-${panelId}`}
                    className="max-h-36 space-y-1.5 overflow-y-auto"
                  >
                    {cloudModelProfiles.map((profile) => (
                      <button
                        key={profile.id}
                        type="button"
                        data-testid={`model-selector-cloud-profile-${panelId}-${profile.id}`}
                        onClick={() => {
                          if (disabled) return
                          applyCloudModelProfile(panelId, profile.id)
                          setOpen(false)
                        }}
                        disabled={disabled}
                        className={`w-full rounded-lg border px-2.5 py-2 text-left transition-colors ${
                          profile.modelConfig.model === modelConfig.model &&
                          profile.modelConfig.base_url === modelConfig.base_url
                            ? 'border-accent-blue/40 bg-accent-blue/10'
                            : 'border-bg-border bg-bg-primary/30 hover:border-accent-blue/35 hover:bg-bg-hover'
                        } disabled:cursor-not-allowed disabled:opacity-50`}
                      >
                        <div className="text-xs font-medium text-text-primary">{profile.name}</div>
                        <div className="mt-0.5 truncate text-[11px] text-text-secondary">
                          {profile.modelConfig.model}
                        </div>
                        <div className="mt-0.5 truncate text-[11px] text-text-secondary/70">
                          {profile.modelConfig.base_url}
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="rounded-lg border border-dashed border-bg-border px-2.5 py-2 text-[11px] leading-5 text-text-secondary">
                    还没有已保存的云端配置。先点“管理”创建，再回来在这里应用。
                  </p>
                )}
              </div>

              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                  常用预设
                </div>
                <div className="grid gap-1.5">
                  {COMPATIBLE_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => applyCompatiblePreset(preset)}
                      disabled={disabled}
                      className="rounded-lg border border-bg-border px-2.5 py-2 text-left transition-colors hover:border-accent-blue/35 hover:bg-bg-hover disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <div className="text-xs font-medium text-text-primary">{preset.label}</div>
                      <div className="mt-0.5 text-[11px] text-text-secondary">
                        {preset.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                  模型 ID
                </div>
                <input
                  className="input-base w-full text-xs"
                  value={modelConfig.model}
                  onChange={(event) => updatePanelModel(panelId, { model: event.target.value })}
                  placeholder="gpt-4o-mini / qwen/qwen-2.5-72b-instruct"
                  disabled={disabled}
                />
              </div>

              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                  基础 URL
                </div>
                <input
                  className="input-base w-full text-xs"
                  value={modelConfig.base_url}
                  onChange={(event) => updatePanelModel(panelId, { base_url: event.target.value })}
                  placeholder="https://openrouter.ai/api/v1"
                  disabled={disabled}
                />
              </div>

              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
                  API Key
                </div>
                <input
                  data-testid={`model-selector-api-key-input-${panelId}`}
                  className="input-base w-full text-xs"
                  type="password"
                  value={modelConfig.api_key}
                  onChange={(event) =>
                    updatePanelModel(panelId, {
                      api_key: event.target.value,
                      api_key_ref: '',
                    })}
                  placeholder="本地兼容服务可留空"
                  disabled={disabled}
                />
                {modelConfig.api_key_ref ? (
                  <p
                    data-testid={`model-selector-managed-key-notice-${panelId}`}
                    className="mt-1 text-[11px] leading-5 text-text-secondary"
                  >
                    当前已关联后端托管密钥，在此输入会解除关联。
                  </p>
                ) : null}
              </div>

              <p className="text-[11px] leading-5 text-text-secondary">
                支持 OpenRouter、OneAPI、NewAPI、LM Studio、vLLM 等 OpenAI 兼容网关和服务。
              </p>
            </div>
          )}

          <div className="mt-3 border-t border-bg-border pt-3">
            <div className="mb-2 text-[10px] uppercase tracking-wide text-text-secondary">
              执行模式
            </div>
            <div className="grid gap-1.5">
              {agentModeOptions.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => updatePanelModel(panelId, { agent_mode: option.id })}
                  disabled={disabled}
                  className={`rounded-lg border px-2.5 py-2 text-left transition-colors ${
                    modelConfig.agent_mode === option.id
                      ? 'border-accent-blue/40 bg-accent-blue/10'
                      : 'border-bg-border bg-bg-primary/30 hover:border-accent-blue/35 hover:bg-bg-hover'
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                >
                  <div className="text-xs font-medium text-text-primary">{option.label}</div>
                  <div className="mt-0.5 text-[11px] text-text-secondary">
                    {option.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3 border-t border-bg-border pt-3">
            <div className="mb-1 text-[10px] uppercase tracking-wide text-text-secondary">
              已保存预设
            </div>
            <div className="flex gap-1.5">
              <input
                className="input-base flex-1 text-xs"
                value={presetName}
                onChange={(event) => setPresetName(event.target.value)}
                placeholder="预设名称"
                disabled={disabled}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    handleSavePreset()
                  }
                }}
              />
              <button
                type="button"
                onClick={handleSavePreset}
                disabled={disabled || !presetName.trim()}
                className="btn-primary px-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
              >
                保存
              </button>
            </div>

            {modelPresets.length > 0 ? (
              <div className="mt-2 max-h-36 space-y-1.5 overflow-y-auto">
                {modelPresets.map((preset) => (
                  <div
                    key={preset.id}
                    className="rounded-lg border border-bg-border bg-bg-primary/40 px-2.5 py-2"
                  >
                    <div className="truncate text-xs font-medium text-text-primary">
                      {preset.name}
                    </div>
                    <div className="mt-0.5 truncate text-[11px] text-text-secondary">
                      {preset.modelConfig.model}
                    </div>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => {
                          applyModelPreset(panelId, preset.id)
                          setOpen(false)
                        }}
                        disabled={disabled}
                        className="rounded-md border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-blue/35 hover:text-accent-blue disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        应用
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteModelPreset(preset.id)}
                        disabled={disabled}
                        className="rounded-md border border-bg-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:border-accent-red/35 hover:text-accent-red disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-2 text-[11px] text-text-secondary">还没有已保存的预设。</p>
            )}
          </div>

          <div className="mt-3 border-t border-bg-border pt-3">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wide text-text-secondary">温度</span>
              <span className="text-xs text-text-primary">{modelConfig.temperature.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={modelConfig.temperature}
              onChange={(event) =>
                updatePanelModel(panelId, { temperature: parseFloat(event.target.value) })
              }
              className="w-full accent-accent-blue"
              disabled={disabled}
            />
          </div>

          <button
            type="button"
            onClick={() => setOpen(false)}
            disabled={disabled}
            className="btn-primary mt-3 w-full text-xs"
          >
            完成
          </button>
        </div>
      )}

      {open && <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />}
    </div>
  )
}
