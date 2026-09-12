import type { ProviderCatalogItem } from '../../api/types/index'
import type { ProviderConfig } from '../../stores/chatStore'

export interface ProviderDisplayItem {
  id: string
  name: string
  slug: string
  connectionType: string
  isBuiltin: boolean
  enabled: boolean
  apiKeyRef: string
  baseUrl: string
  apiKeyUrl: string
  icon: string
}

export type ProviderCatalogStatus = 'loading' | 'ready' | 'error'
export type ProviderApiKeyFeedback = 'saved' | 'cleared' | 'save_error' | 'clear_error' | null

const BUILTIN_PROVIDER_META: Record<string, { name: string; icon: string }> = {
  ollama: { name: 'Ollama', icon: '🦙' },
  openai_compatible: { name: 'OpenAI GPT', icon: '🤖' },
  deepseek: { name: 'DeepSeek', icon: '💠' },
  anthropic: { name: 'Anthropic Claude', icon: '🎭' },
  google: { name: 'Google Gemini', icon: '✨' },
}

const OFFICIAL_API_KEY_URLS: Record<string, string> = {
  deepseek: 'https://platform.deepseek.com/api_keys',
  anthropic: 'https://console.anthropic.com/settings/keys',
  google: 'https://aistudio.google.com/app/apikey',
}

function resolveOfficialApiKeyUrl(connectionType: string, baseUrl: string): string {
  if (connectionType !== 'openai_compatible') {
    return OFFICIAL_API_KEY_URLS[connectionType] ?? ''
  }

  try {
    const hostname = new URL(baseUrl).hostname.toLowerCase()
    if (hostname === 'openrouter.ai' || hostname.endsWith('.openrouter.ai')) {
      return 'https://openrouter.ai/settings/keys'
    }
    if (hostname === 'api.openai.com') {
      return 'https://platform.openai.com/api-keys'
    }
  } catch {
    return ''
  }

  return ''
}

export function buildProviderDisplayList(
  catalog: ProviderCatalogItem[],
  configs: ProviderConfig[],
): ProviderDisplayItem[] {
  const builtinItems: ProviderDisplayItem[] = catalog.map((provider) => {
    const meta = BUILTIN_PROVIDER_META[provider.connection_type] ?? {
      name: provider.id,
      icon: '☁️',
    }
    const config = configs.find(
      (c) => c.isBuiltin && c.connectionType === provider.connection_type,
    )
    const baseUrl = config?.baseUrl || provider.default_base_url
    return {
      id: `builtin:${provider.connection_type}`,
      name: meta.name,
      slug: provider.connection_type,
      connectionType: provider.connection_type,
      isBuiltin: true,
      enabled: config?.enabled ?? false,
      apiKeyRef: config?.apiKeyRef ?? '',
      baseUrl,
      apiKeyUrl: resolveOfficialApiKeyUrl(provider.connection_type, baseUrl),
      icon: meta.icon,
    }
  })

  const customItems: ProviderDisplayItem[] = configs
    .filter((c) => !c.isBuiltin)
    .map((c) => ({
      id: c.id,
      name: c.name,
      slug: c.connectionType,
      connectionType: c.connectionType,
      isBuiltin: false,
      enabled: c.enabled,
      apiKeyRef: c.apiKeyRef,
      baseUrl: c.baseUrl,
      apiKeyUrl: '',
      icon: '☁️',
    }))

  return [...builtinItems, ...customItems]
}

export function createCustomProviderConfig(name: string, baseUrl: string): ProviderConfig {
  return {
    id: `custom-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    connectionType: 'openai_compatible',
    apiKeyRef: '',
    baseUrl,
    enabled: false,
    isBuiltin: false,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}

export function createBuiltinProviderConfig(connectionType: string): ProviderConfig {
  return {
    id: `builtin:${connectionType}`,
    name: BUILTIN_PROVIDER_META[connectionType]?.name ?? connectionType,
    connectionType,
    apiKeyRef: '',
    baseUrl: '',
    enabled: false,
    isBuiltin: true,
    createdAt: Date.now(),
    updatedAt: Date.now(),
  }
}
