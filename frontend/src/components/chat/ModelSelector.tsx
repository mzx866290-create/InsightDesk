import React, { useEffect, useState } from 'react'
import { ChevronDown, X, Cpu, Cloud } from 'lucide-react'
import { useChatStore } from '../../stores/chatStore'
import { getOllamaModels } from '../../api/client'
import type { ModelConfig } from '../../api/client'

interface ModelSelectorProps {
  panelId: string
  modelConfig: ModelConfig
  onRemove?: () => void
  canRemove: boolean
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  panelId,
  modelConfig,
  onRemove,
  canRemove,
}) => {
  const { updatePanelModel } = useChatStore()
  const [open, setOpen] = useState(false)
  const [ollamaModels, setOllamaModels] = useState<string[]>([])
  const [customModel, setCustomModel] = useState('')

  useEffect(() => {
    if (modelConfig.provider === 'local') {
      getOllamaModels(modelConfig.base_url).then(setOllamaModels)
    }
  }, [modelConfig.provider, modelConfig.base_url])

  const handleProviderChange = (provider: 'local' | 'cloud') => {
    updatePanelModel(panelId, {
      provider,
      model: provider === 'local' ? 'qwen2.5:7b' : 'gpt-4o-mini',
      base_url: provider === 'local' ? 'http://localhost:11434' : 'https://openrouter.ai/api/v1',
      api_key: '',
    })
  }

  const shortModel = modelConfig.model.length > 18
    ? modelConfig.model.slice(0, 16) + '…'
    : modelConfig.model

  return (
    <div className="relative flex items-center gap-1.5 min-w-0">
      {/* Provider icon */}
      {modelConfig.provider === 'local' ? (
        <Cpu size={12} className="text-accent-green shrink-0" />
      ) : (
        <Cloud size={12} className="text-accent-blue shrink-0" />
      )}

      {/* Model name button */}
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary transition-colors min-w-0"
      >
        <span className="truncate max-w-[120px]">{shortModel}</span>
        <ChevronDown size={11} className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Remove panel button */}
      {canRemove && (
        <button
          onClick={onRemove}
          className="text-text-secondary hover:text-accent-red transition-colors ml-1"
          title="移除此面板"
        >
          <X size={12} />
        </button>
      )}

      {/* Dropdown */}
      {open && (
        <div
          className="absolute top-full left-0 mt-1 z-50 bg-bg-secondary border border-bg-border rounded-xl shadow-2xl p-3 w-72 animate-fade-in"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Provider tabs */}
          <div className="flex gap-1 mb-3 bg-bg-tertiary p-1 rounded-lg">
            {(['local', 'cloud'] as const).map((p) => (
              <button
                key={p}
                onClick={() => handleProviderChange(p)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  modelConfig.provider === p
                    ? 'bg-accent-blue text-white'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                {p === 'local' ? <Cpu size={11} /> : <Cloud size={11} />}
                {p === 'local' ? '本地 Ollama' : '云端 API'}
              </button>
            ))}
          </div>

          {/* Model selection */}
          {modelConfig.provider === 'local' ? (
            <div className="space-y-2">
              {ollamaModels.length > 0 ? (
                <div>
                  <div className="text-[10px] text-text-secondary uppercase tracking-wide mb-1.5">已安装模型</div>
                  <div className="space-y-0.5 max-h-40 overflow-y-auto">
                    {ollamaModels.map((m) => (
                      <button
                        key={m}
                        onClick={() => { updatePanelModel(panelId, { model: m }); setOpen(false) }}
                        className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
                          modelConfig.model === m
                            ? 'bg-accent-blue/20 text-accent-blue'
                            : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-text-secondary text-center py-2">未检测到 Ollama 模型</p>
              )}
              <div>
                <div className="text-[10px] text-text-secondary uppercase tracking-wide mb-1">自定义 Base URL</div>
                <input
                  className="input-base w-full text-xs"
                  value={modelConfig.base_url}
                  onChange={(e) => updatePanelModel(panelId, { base_url: e.target.value })}
                  placeholder="http://localhost:11434"
                />
              </div>
              <div>
                <div className="text-[10px] text-text-secondary uppercase tracking-wide mb-1">自定义模型名</div>
                <div className="flex gap-1.5">
                  <input
                    className="input-base flex-1 text-xs"
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                    placeholder="qwen3:4b"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && customModel.trim()) {
                        updatePanelModel(panelId, { model: customModel.trim() })
                        setCustomModel('')
                        setOpen(false)
                      }
                    }}
                  />
                  <button
                    className="btn-primary text-xs px-2"
                    onClick={() => {
                      if (customModel.trim()) {
                        updatePanelModel(panelId, { model: customModel.trim() })
                        setCustomModel('')
                        setOpen(false)
                      }
                    }}
                  >
                    确定
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <div>
                <div className="text-[10px] text-text-secondary uppercase tracking-wide mb-1">Model ID</div>
                <input
                  className="input-base w-full text-xs"
                  value={modelConfig.model}
                  onChange={(e) => updatePanelModel(panelId, { model: e.target.value })}
                  placeholder="gpt-4o-mini"
                />
              </div>
              <div>
                <div className="text-[10px] text-text-secondary uppercase tracking-wide mb-1">Base URL</div>
                <input
                  className="input-base w-full text-xs"
                  value={modelConfig.base_url}
                  onChange={(e) => updatePanelModel(panelId, { base_url: e.target.value })}
                  placeholder="https://openrouter.ai/api/v1"
                />
              </div>
              <div>
                <div className="text-[10px] text-text-secondary uppercase tracking-wide mb-1">API Key</div>
                <input
                  className="input-base w-full text-xs"
                  type="password"
                  value={modelConfig.api_key}
                  onChange={(e) => updatePanelModel(panelId, { api_key: e.target.value })}
                  placeholder="sk-or-v1-..."
                />
              </div>
            </div>
          )}

          {/* Temperature */}
          <div className="mt-3 pt-3 border-t border-bg-border">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] text-text-secondary uppercase tracking-wide">Temperature</span>
              <span className="text-xs text-text-primary">{modelConfig.temperature.toFixed(1)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={modelConfig.temperature}
              onChange={(e) => updatePanelModel(panelId, { temperature: parseFloat(e.target.value) })}
              className="w-full accent-accent-blue"
            />
          </div>

          <button
            onClick={() => setOpen(false)}
            className="mt-3 w-full btn-primary text-xs"
          >
            完成
          </button>
        </div>
      )}

      {/* Click outside to close */}
      {open && (
        <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
      )}
    </div>
  )
}
