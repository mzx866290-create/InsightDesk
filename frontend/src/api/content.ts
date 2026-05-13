import {
  BASE,
  authFetch,
  fetchWithApiToken,
  readErrorDetail,
} from './auth'
import {
  normalizeModelConfig,
  normalizeConnectionType,
  readString,
  readNumber,
  normalizeDeckCitationValidation,
  normalizeDeckEvidenceReview,
  defaultDeckCitationValidation,
  defaultDeckEvidenceReview,
  normalizeDeckBlock,
  normalizeDeckSpec,
  normalizeResearchConflictGroups,
  normalizeResearchArchive,
  normalizeArtifact,
} from './normalizers'
import type {
  AssistantPreset,
  AssistantPresetListResponse,
  AssistantPresetPayload,
  AssistantPresetToolConfig,
  ConnectionType,
  ModelConfig,
  AgentCatalogResponse,
  AgentCatalogItem,
  AgentPluginManifest,
  AgentPluginMarketplaceTemplate,
  InstallAgentPluginPayload,
  InstallDeliveryTemplatePayload,
  DeliveryTemplateCatalogResponse,
  DeliveryTemplateItem,
  ProviderCatalogResponse,
  DocStats,
  UploadDocumentsResponse,
  TaskStatus,
  TaskApprovalDecision,
  TaskApprovalPolicy,
  BatchTaskApproval,
  BatchTaskApprovalResponse,
  CreateMultiAgentWorkflowTaskPayload,
  TaskRecord,
  SystemPrompt,
  DashboardTemplateConfig,
  KnowledgeBase,
  KBHealthData,
  KnowledgeBaseChunksResponse,
  RetrievalTestResult,
  ShareLinkResponse,
  DeckSlide,
  DeckSpec,
  ArtifactType,
  ArtifactExportFormat,
  ResearchConflictResolutionPayload,
  ResearchArchive,
  ResearchArchiveListResponse,
  ArtifactRecord,
  GeneratedReport,
  ReportScopeOptions,
  ExportDeckOptions,
  DeckExportGate,
  UpdateDeckBlockRefsPayload,
  UpdateDeckBlockRefsResponse,
} from './types'

const fetch: typeof globalThis.fetch = fetchWithApiToken

const CONNECTION_TYPE_LABELS: Record<ConnectionType, string> = {
  ollama: '本地 Ollama',
  openai_compatible: 'OpenAI 兼容',
  deepseek: 'DeepSeek',
  anthropic: 'Anthropic',
  google: 'Google Gemini',
}

function normalizeAgentCatalogItem(agent: Partial<AgentCatalogItem>): AgentCatalogItem {
  return {
    name: typeof agent.name === 'string' ? agent.name : '',
    description: typeof agent.description === 'string' ? agent.description : '',
    capabilities: Array.isArray(agent.capabilities)
      ? agent.capabilities.filter((capability): capability is string => typeof capability === 'string')
      : [],
    metadata:
      agent.metadata && typeof agent.metadata === 'object' && !Array.isArray(agent.metadata)
        ? (agent.metadata as Record<string, unknown>)
        : {},
  }
}

function normalizeAgentPluginManifest(value: unknown): AgentPluginManifest {
  const manifest = isRecord(value) ? value : {}
  const metadata = isRecord(manifest.metadata)
    ? manifest.metadata
    : undefined
  const workflow = Array.isArray(manifest.workflow)
    ? manifest.workflow
        .map((rawStep) => {
          const step = isRecord(rawStep) ? rawStep : {}
          return {
            id: readString(step.id),
            title: readString(step.title || step.name),
            prompt: readString(step.prompt || step.instruction),
            artifact_type: readString(step.artifact_type) || 'text',
          }
        })
        .filter((step) => step.id && step.title && step.prompt)
    : undefined
  const normalized: AgentPluginManifest = {
    name: readString(manifest.name),
    description: readString(manifest.description),
    capabilities: Array.isArray(manifest.capabilities)
      ? manifest.capabilities.filter((capability): capability is string => typeof capability === 'string')
      : [],
  }
  if (manifest.enabled === true || manifest.enabled === false) normalized.enabled = manifest.enabled
  if (readString(manifest.version)) normalized.version = readString(manifest.version)
  if (readString(manifest.runtime)) normalized.runtime = readString(manifest.runtime)
  if (readString(manifest.output_prefix)) normalized.output_prefix = readString(manifest.output_prefix)
  if (readString(manifest.risk_level)) normalized.risk_level = readString(manifest.risk_level)
  if (manifest.requires_approval === true || manifest.requires_approval === false) {
    normalized.requires_approval = manifest.requires_approval
  }
  if (readString(manifest.approval_reason)) normalized.approval_reason = readString(manifest.approval_reason)
  if (workflow && workflow.length > 0) normalized.workflow = workflow
  if (metadata) normalized.metadata = metadata
  return normalized
}

function normalizeAgentManifestIssue(issue: unknown): { file: string; code: string; message: string } {
  const item = isRecord(issue) ? issue : {}
  return {
    file: readString(item.file),
    code: readString(item.code),
    message: readString(item.message),
  }
}

function readAgentCatalogNumber(value: unknown, fallback: number): number {
  return value === undefined || value === null || value === ''
    ? fallback
    : readNumber(value)
}

function normalizeAgentPluginMarketplace(value: unknown): AgentCatalogResponse['marketplace'] {
  const marketplace = isRecord(value) ? value : {}
  const templates = Array.isArray(marketplace.templates)
    ? marketplace.templates.map((rawTemplate): AgentPluginMarketplaceTemplate => {
        const template = isRecord(rawTemplate) ? rawTemplate : {}
        const manifest = normalizeAgentPluginManifest(template.manifest)
        const name = readString(template.name) || manifest.name
        const description = readString(template.description) || manifest.description
        const capabilities = Array.isArray(template.capabilities)
          ? template.capabilities.filter((capability): capability is string => typeof capability === 'string')
          : manifest.capabilities
        return {
          name,
          description,
          capabilities,
          category: readString(template.category) || 'custom',
          risk_level: readString(template.risk_level) || manifest.risk_level || 'medium',
          requires_approval: template.requires_approval === true,
          approval_reason: readString(template.approval_reason),
          source: readString(template.source) || 'builtin',
          installed: template.installed === true,
          template: template.template !== false,
          manifest: {
            ...manifest,
            name: manifest.name || name,
            description: manifest.description || description,
            capabilities: manifest.capabilities.length > 0 ? manifest.capabilities : capabilities,
          },
        }
      })
    : []
  const summary = isRecord(marketplace.summary) ? marketplace.summary : {}
  const issues = Array.isArray(marketplace.issues)
    ? marketplace.issues.map(normalizeAgentManifestIssue).filter((issue) => issue.file || issue.code || issue.message)
    : []
  return {
    templates,
    summary: {
      total: readAgentCatalogNumber(summary.total, templates.length),
      installed: readAgentCatalogNumber(summary.installed, templates.filter((template) => template.installed).length),
      available: readAgentCatalogNumber(summary.available, templates.filter((template) => !template.installed).length),
      categories: readAgentCatalogNumber(summary.categories, new Set(templates.map((template) => template.category)).size),
      issue_count: readAgentCatalogNumber(summary.issue_count, issues.length),
    },
    issues,
  }
}

function normalizeAgentCatalogResponse(data: Partial<AgentCatalogResponse>): AgentCatalogResponse {
  const agents = Array.isArray(data.agents)
    ? data.agents.map((agent) => normalizeAgentCatalogItem(agent))
    : []
  const installed = isRecord(data.installed)
    ? {
        name: typeof data.installed.name === 'string' ? data.installed.name : '',
        agent: isRecord(data.installed.agent)
          ? normalizeAgentCatalogItem(data.installed.agent as Partial<AgentCatalogItem>)
          : undefined,
        manifest_path:
          typeof data.installed.manifest_path === 'string'
            ? data.installed.manifest_path
            : '',
        executed_entrypoint: data.installed.executed_entrypoint === true,
      }
    : undefined
  const uninstalled = isRecord(data.uninstalled)
    ? {
        name: typeof data.uninstalled.name === 'string' ? data.uninstalled.name : '',
        manifest_path:
          typeof data.uninstalled.manifest_path === 'string'
            ? data.uninstalled.manifest_path
            : '',
        deleted_manifest: data.uninstalled.deleted_manifest === true,
        existed: data.uninstalled.existed === true,
      }
    : undefined

  return {
    agents,
    summary: {
      total: typeof data.summary?.total === 'number' ? data.summary.total : agents.length,
      builtin: typeof data.summary?.builtin === 'number' ? data.summary.builtin : agents.length,
      plugin: typeof data.summary?.plugin === 'number' ? data.summary.plugin : 0,
    },
    plugin_manifests: {
      enabled: data.plugin_manifests?.enabled !== false,
      directory_count:
        typeof data.plugin_manifests?.directory_count === 'number'
          ? data.plugin_manifests.directory_count
          : 0,
      scanned_count:
        typeof data.plugin_manifests?.scanned_count === 'number'
          ? data.plugin_manifests.scanned_count
          : 0,
      loaded_count:
        typeof data.plugin_manifests?.loaded_count === 'number'
          ? data.plugin_manifests.loaded_count
          : 0,
      issue_count:
        typeof data.plugin_manifests?.issue_count === 'number'
          ? data.plugin_manifests.issue_count
          : 0,
      issues: Array.isArray(data.plugin_manifests?.issues)
        ? data.plugin_manifests.issues.map(normalizeAgentManifestIssue).filter((issue) => issue.file || issue.code || issue.message)
        : [],
    },
    marketplace: normalizeAgentPluginMarketplace(data.marketplace),
    ...(installed ? { installed } : {}),
    ...(uninstalled ? { uninstalled } : {}),
  }
}

export function getConnectionTypeLabel(modelConfig: ModelConfig): string {
  const connectionType = normalizeConnectionType(
    modelConfig.connection_type ?? modelConfig.provider,
    modelConfig.base_url,
  )
  return CONNECTION_TYPE_LABELS[connectionType]
}

export async function getProviderCatalog(): Promise<ProviderCatalogResponse> {
  const res = await fetch(`${BASE}/providers`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<ProviderCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }

  const providers = Array.isArray(data.providers)
    ? data.providers.map((provider) => ({
        id: typeof provider.id === 'string' ? provider.id : '',
        connection_type:
          typeof provider.connection_type === 'string'
            ? provider.connection_type
            : '',
        aliases: Array.isArray(provider.aliases)
          ? provider.aliases.filter((alias): alias is string => typeof alias === 'string')
          : [],
        capabilities: Array.isArray(provider.capabilities)
          ? provider.capabilities.filter((capability): capability is string => typeof capability === 'string')
          : [],
        default_base_url:
          typeof provider.default_base_url === 'string'
            ? provider.default_base_url
            : '',
        default_model:
          typeof provider.default_model === 'string'
            ? provider.default_model
            : '',
        base_url_env_keys: Array.isArray(provider.base_url_env_keys)
          ? provider.base_url_env_keys.filter((key): key is string => typeof key === 'string')
          : [],
        model_env_keys: Array.isArray(provider.model_env_keys)
          ? provider.model_env_keys.filter((key): key is string => typeof key === 'string')
          : [],
      }))
    : []

  return {
    providers,
    default_provider:
      typeof data.default_provider === 'string'
        ? data.default_provider
        : 'ollama',
    total: typeof data.total === 'number' ? data.total : providers.length,
  }
}

export async function getAgentCatalog(): Promise<AgentCatalogResponse> {
  const res = await authFetch('/agents/catalog')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<AgentCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }

  return normalizeAgentCatalogResponse(data)
}

export async function installAgentPluginManifest(
  payload: InstallAgentPluginPayload,
): Promise<AgentCatalogResponse> {
  const res = await authFetch('/agents/plugins/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<AgentCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeAgentCatalogResponse(data)
}

export async function uninstallAgentPluginManifest(
  name: string,
): Promise<AgentCatalogResponse> {
  const res = await authFetch(`/agents/plugins/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<AgentCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeAgentCatalogResponse(data)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function normalizeCatalogRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {}
}

function normalizeCatalogStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

export async function getDeliveryTemplateCatalog(): Promise<DeliveryTemplateCatalogResponse> {
  const res = await authFetch('/delivery-templates/catalog')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<DeliveryTemplateCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }

  return normalizeDeliveryTemplateCatalogResponse(data)
}

function normalizeDeliveryTemplateItem(template: Partial<DeliveryTemplateItem>): DeliveryTemplateItem {
  return {
    id: typeof template.id === 'string' ? template.id : '',
    name: typeof template.name === 'string' ? template.name : '',
    description: typeof template.description === 'string' ? template.description : '',
    artifact_type: template.artifact_type === 'deck' ? 'deck' as const : 'report' as const,
    category: typeof template.category === 'string' ? template.category : '',
    tags: normalizeCatalogStrings(template.tags),
    target_format: typeof template.target_format === 'string' ? template.target_format : '',
    preview: typeof template.preview === 'string' ? template.preview : '',
    suggested_options: normalizeCatalogRecord(template.suggested_options),
    metadata: normalizeCatalogRecord(template.metadata),
  }
}

function normalizeDeliveryTemplateCatalogResponse(data: Partial<DeliveryTemplateCatalogResponse>): DeliveryTemplateCatalogResponse {
  const templates = Array.isArray(data.templates)
    ? data.templates.map((template) => normalizeDeliveryTemplateItem(template))
    : []

  const manifestIssues = Array.isArray(data.manifests?.issues)
    ? data.manifests.issues.map((issue) => ({
        file: typeof issue.file === 'string' ? issue.file : '',
        code: typeof issue.code === 'string' ? issue.code : '',
        message: typeof issue.message === 'string' ? issue.message : '',
      })).filter((issue) => issue.file || issue.code || issue.message)
    : []
  const installed = isRecord(data.installed)
    ? {
        id: typeof data.installed.id === 'string' ? data.installed.id : '',
        template: isRecord(data.installed.template)
          ? normalizeDeliveryTemplateItem(data.installed.template as Partial<DeliveryTemplateItem>)
          : undefined,
        manifest_path:
          typeof data.installed.manifest_path === 'string'
            ? data.installed.manifest_path
            : '',
        executed_template_code: data.installed.executed_template_code === true,
      }
    : undefined
  const uninstalled = isRecord(data.uninstalled)
    ? {
        id: typeof data.uninstalled.id === 'string' ? data.uninstalled.id : '',
        manifest_path:
          typeof data.uninstalled.manifest_path === 'string'
            ? data.uninstalled.manifest_path
            : '',
        deleted_manifest: data.uninstalled.deleted_manifest === true,
        existed: data.uninstalled.existed === true,
      }
    : undefined

  return {
    templates,
    summary: {
      total: typeof data.summary?.total === 'number' ? data.summary.total : templates.length,
      builtin: typeof data.summary?.builtin === 'number' ? data.summary.builtin : templates.length,
      manifest: typeof data.summary?.manifest === 'number' ? data.summary.manifest : 0,
      report: typeof data.summary?.report === 'number'
        ? data.summary.report
        : templates.filter((template) => template.artifact_type === 'report').length,
      deck: typeof data.summary?.deck === 'number'
        ? data.summary.deck
        : templates.filter((template) => template.artifact_type === 'deck').length,
    },
    manifests: {
      enabled: data.manifests?.enabled !== false,
      directory_count: typeof data.manifests?.directory_count === 'number' ? data.manifests.directory_count : 0,
      scanned_count: typeof data.manifests?.scanned_count === 'number' ? data.manifests.scanned_count : 0,
      loaded_count: typeof data.manifests?.loaded_count === 'number' ? data.manifests.loaded_count : 0,
      issue_count: typeof data.manifests?.issue_count === 'number' ? data.manifests.issue_count : manifestIssues.length,
      issues: manifestIssues,
    },
    ...(installed ? { installed } : {}),
    ...(uninstalled ? { uninstalled } : {}),
  }
}

export async function installDeliveryTemplateManifest(
  payload: InstallDeliveryTemplatePayload,
): Promise<DeliveryTemplateCatalogResponse> {
  const res = await authFetch('/delivery-templates/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<DeliveryTemplateCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeDeliveryTemplateCatalogResponse(data)
}

export async function uninstallDeliveryTemplateManifest(
  templateId: string,
): Promise<DeliveryTemplateCatalogResponse> {
  const res = await authFetch(`/delivery-templates/${encodeURIComponent(templateId)}`, {
    method: 'DELETE',
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<DeliveryTemplateCatalogResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeDeliveryTemplateCatalogResponse(data)
}

function normalizeAssistantPresetToolConfig(
  value?: Partial<AssistantPresetToolConfig>,
): AssistantPresetToolConfig {
  return {
    web_search_enabled: Boolean(value?.web_search_enabled ?? false),
    knowledge_base_enabled: Boolean(value?.knowledge_base_enabled ?? true),
    mcp_servers_enabled: Array.isArray(value?.mcp_servers_enabled)
      ? value.mcp_servers_enabled.filter((item): item is string => typeof item === 'string')
      : [],
  }
}

function normalizeAssistantPreset(raw: Partial<AssistantPreset>, index = 0): AssistantPreset {
  const modelConfig: Partial<ModelConfig> = raw.default_model_config ?? {}
  return {
    id: typeof raw.id === 'string' ? raw.id : '',
    name: typeof raw.name === 'string' ? raw.name : 'Assistant Preset',
    avatar: typeof raw.avatar === 'string' ? raw.avatar : '',
    system_prompt_id: typeof raw.system_prompt_id === 'string' ? raw.system_prompt_id : '',
    default_model_config: normalizeModelConfig({
      ...(typeof modelConfig === 'object' && modelConfig ? modelConfig : {}),
      panel_id:
        typeof modelConfig.panel_id === 'string' && modelConfig.panel_id
          ? modelConfig.panel_id
          : `assistant-preset-${index + 1}`,
    }),
    tool_config: normalizeAssistantPresetToolConfig(raw.tool_config),
    starters: Array.isArray(raw.starters)
      ? raw.starters.filter((item): item is string => typeof item === 'string')
      : [],
    is_default: Boolean(raw.is_default),
    is_active: Boolean(raw.is_active),
    created_at: typeof raw.created_at === 'number' ? raw.created_at : 0,
    updated_at: typeof raw.updated_at === 'number' ? raw.updated_at : 0,
  }
}

function assistantPresetPayloadBody(payload: AssistantPresetPayload): AssistantPresetPayload {
  return {
    name: payload.name,
    avatar: payload.avatar,
    system_prompt_id: payload.system_prompt_id,
    default_model_config: normalizeModelConfig(payload.default_model_config),
    tool_config: normalizeAssistantPresetToolConfig(payload.tool_config),
    starters: payload.starters.filter((item) => item.trim()).map((item) => item.trim()),
  }
}

export async function getAssistantPresets(): Promise<AssistantPreset[]> {
  const res = await fetch(`${BASE}/assistant-presets`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load assistant presets'))
  const data = await res.json() as Partial<AssistantPresetListResponse>
  return Array.isArray(data.presets)
    ? data.presets.map((preset, index) => normalizeAssistantPreset(preset, index))
    : []
}

export async function createAssistantPreset(
  payload: AssistantPresetPayload,
): Promise<AssistantPreset> {
  const res = await fetch(`${BASE}/assistant-presets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assistantPresetPayloadBody(payload)),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to create assistant preset'))
  return normalizeAssistantPreset(await res.json())
}

export async function updateAssistantPreset(
  id: string,
  payload: AssistantPresetPayload,
): Promise<AssistantPreset> {
  const res = await fetch(`${BASE}/assistant-presets/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assistantPresetPayloadBody(payload)),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to update assistant preset'))
  return normalizeAssistantPreset(await res.json())
}

export async function deleteAssistantPreset(id: string): Promise<void> {
  const res = await fetch(`${BASE}/assistant-presets/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to delete assistant preset'))
}

export async function activateAssistantPreset(id: string): Promise<{ ok: boolean }> {
  const res = await fetch(`${BASE}/assistant-presets/${id}/activate`, { method: 'POST' })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to activate assistant preset'))
  return res.json()
}


export async function generateSessionReport(
  sessionId: string,
  options?: ReportScopeOptions,
): Promise<GeneratedReport> {
  const res = await fetch(`${BASE}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      answer_group_id: options?.answer_group_id,
      panel_id: options?.panel_id,
      template_id: options?.template_id,
      template_options: options?.template_options,
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    markdown?: string
    title?: string
    artifact_id?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (typeof data.markdown !== 'string' || typeof data.title !== 'string') {
    throw new Error('Invalid report generation response.')
  }
  return {
    markdown: data.markdown,
    title: data.title,
    artifact_id: typeof data.artifact_id === 'string' ? data.artifact_id : undefined,
  }
}

export async function getSessionArtifacts(
  sessionId: string,
  options?: { artifact_type?: ArtifactType },
): Promise<ArtifactRecord[]> {
  const params = new URLSearchParams()
  if (options?.artifact_type) params.set('artifact_type', options.artifact_type)
  const query = params.toString()
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/artifacts${query ? `?${query}` : ''}`,
  )
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    artifacts?: unknown[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return Array.isArray(data.artifacts) ? data.artifacts.map((item) => normalizeArtifact(item)) : []
}

export async function getArtifacts(options?: { artifact_type?: ArtifactType; limit?: number }): Promise<ArtifactRecord[]> {
  const params = new URLSearchParams()
  if (options?.artifact_type) params.set('artifact_type', options.artifact_type)
  if (typeof options?.limit === 'number' && Number.isFinite(options.limit)) {
    params.set('limit', String(Math.max(1, Math.min(500, Math.floor(options.limit)))))
  }
  const query = params.toString()
  const res = await fetch(`${BASE}/artifacts${query ? `?${query}` : ''}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    artifacts?: unknown[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return Array.isArray(data.artifacts) ? data.artifacts.map((item) => normalizeArtifact(item)) : []
}

export async function getResearchArchiveList(options?: {
  q?: string
  session_id?: string
  task_id?: string
  limit?: number
}): Promise<ResearchArchiveListResponse> {
  const params = new URLSearchParams()
  if (options?.q?.trim()) params.set('q', options.q.trim())
  if (options?.session_id?.trim()) params.set('session_id', options.session_id.trim())
  if (options?.task_id?.trim()) params.set('task_id', options.task_id.trim())
  if (typeof options?.limit === 'number' && Number.isFinite(options.limit)) {
    params.set('limit', String(Math.max(1, Math.min(100, Math.floor(options.limit)))))
  }
  const query = params.toString()
  const res = await authFetch(`/research/archives${query ? `?${query}` : ''}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    archives?: unknown[]
    items?: unknown[]
    conflict_groups?: unknown[]
    total?: unknown
    limit?: unknown
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  const archives = Array.isArray(data.archives) ? data.archives : data.items
  return {
    archives: Array.isArray(archives) ? archives.map((item) => normalizeResearchArchive(item)) : [],
    conflict_groups: normalizeResearchConflictGroups(data.conflict_groups),
    total: readNumber(data.total),
    limit: readNumber(data.limit),
  }
}

export async function getResearchArchives(options?: {
  q?: string
  session_id?: string
  task_id?: string
  limit?: number
}): Promise<ResearchArchive[]> {
  const payload = await getResearchArchiveList(options)
  return payload.archives
}

export async function upsertResearchConflictResolution(
  artifactId: string,
  payload: ResearchConflictResolutionPayload,
): Promise<ResearchArchive> {
  const res = await authFetch(
    `/research/archives/${encodeURIComponent(artifactId)}/conflict-resolutions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    archive?: unknown
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeResearchArchive(data.archive)
}

export async function getArtifact(artifactId: string): Promise<ArtifactRecord> {
  const res = await fetch(`${BASE}/artifacts/${encodeURIComponent(artifactId)}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeArtifact(data)
}

export async function exportArtifact(
  artifactId: string,
  format: ArtifactExportFormat,
): Promise<Blob> {
  const res = await fetch(
    `${BASE}/artifacts/${encodeURIComponent(artifactId)}/export?format=${encodeURIComponent(format)}`,
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.blob()
}

// 鈹€鈹€ Chat 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function getOllamaModels(baseUrl = 'http://localhost:11434'): Promise<string[]> {
  try {
    const res = await fetch(`${BASE}/models/ollama?base_url=${encodeURIComponent(baseUrl)}`)
    const data = await res.json()
    return (data.models as string[]) ?? []
  } catch {
    return []
  }
}

// 鈹€鈹€ Config 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function getConfig() {
  const res = await authFetch('/config')
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load config'))
  return res.json()
}

export async function saveConfig(payload: { tavily_api_key?: string }): Promise<void> {
  const res = await authFetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save config'))
}

export async function saveCloudModelApiKey(payload: {
  api_key: string
  api_key_ref?: string
}): Promise<{ api_key_ref: string; api_key_set: boolean }> {
  const res = await authFetch('/config/cloud-model-api-key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save cloud model API key'))
  return res.json()
}

export async function deleteCloudModelApiKey(apiKeyRef: string): Promise<void> {
  const res = await authFetch(`/config/cloud-model-api-key/${encodeURIComponent(apiKeyRef)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to delete cloud model API key'))
}

export async function resetAgents(): Promise<void> {
  const res = await authFetch('/agents/reset', { method: 'POST' })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to reset agents'))
}

// 鈹€鈹€ Documents 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function uploadDocuments(files: File[]): Promise<UploadDocumentsResponse> {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const res = await authFetch('/documents/upload', { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, res.statusText))
  }
  return res.json()
}

export async function getTask(taskId: string): Promise<TaskRecord> {
  const res = await fetch(`${BASE}/tasks/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function listTasks(limit = 20, status?: TaskStatus): Promise<TaskRecord[]> {
  const searchParams = new URLSearchParams()
  searchParams.set('limit', String(limit))
  if (status) {
    searchParams.set('status', status)
  }
  const res = await fetch(`${BASE}/tasks?${searchParams.toString()}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { tasks?: TaskRecord[] }
  return data.tasks ?? []
}

export async function createMultiAgentWorkflowTask(
  payload: CreateMultiAgentWorkflowTaskPayload,
): Promise<TaskRecord> {
  const res = await authFetch('/tasks/multi-agent-workflow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to create multi-agent workflow task'))
  }
  return res.json()
}

export async function getTaskApprovalPolicy(): Promise<TaskApprovalPolicy> {
  const res = await authFetch('/tasks/approval-policy')
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to load approval policy'))
  }
  return res.json()
}

export async function updateTaskApprovalPolicy(
  payload: TaskApprovalPolicy,
): Promise<TaskApprovalPolicy> {
  const res = await authFetch('/tasks/approval-policy', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to save approval policy'))
  }
  return res.json()
}

export async function decideTaskApproval(
  taskId: string,
  payload: {
    decision: TaskApprovalDecision
    reviewer?: string
    comment?: string
  },
): Promise<TaskRecord> {
  const res = await authFetch(`/tasks/${encodeURIComponent(taskId)}/approval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to submit approval decision'))
  }
  return res.json()
}

export async function decideTaskApprovalsBatch(
  payload: BatchTaskApproval,
): Promise<BatchTaskApprovalResponse> {
  const res = await authFetch('/tasks/approvals/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to submit batch approval decision'))
  }
  return res.json()
}

export async function getDocStats(): Promise<DocStats> {
  const res = await fetch(`${BASE}/documents/stats`)
  if (!res.ok) throw new Error(await readErrorDetail(res, '鑾峰彇缁熻淇℃伅澶辫触'))
  return res.json()
}

// 鈹€鈹€ System Prompts 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function getSystemPrompts(): Promise<SystemPrompt[]> {
  const res = await fetch(`${BASE}/prompts`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load prompts'))
  const data = await res.json()
  return data.prompts as SystemPrompt[]
}

export async function createSystemPrompt(
  name: string,
  content: string,
  dashboard_template?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, dashboard_template: dashboard_template ?? {} }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '鍒涘缓瑙掕壊澶辫触'))
  return res.json()
}

export async function updateSystemPrompt(
  id: string,
  name: string,
  content: string,
  dashboard_template?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, dashboard_template: dashboard_template ?? {} }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '鏇存柊瑙掕壊澶辫触'))
  return res.json()
}

export async function deleteSystemPrompt(id: string): Promise<void> {
  const res = await fetch(`${BASE}/prompts/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await readErrorDetail(res, '鍒犻櫎瑙掕壊澶辫触'))
}

export async function activateSystemPrompt(id: string): Promise<{ ok: boolean; kb_status?: string }> {
  const res = await fetch(`${BASE}/prompts/${id}/activate`, { method: 'POST' })
  if (!res.ok) throw new Error(await readErrorDetail(res, '鍚敤瑙掕壊澶辫触'))
  return res.json()
}

export async function createSystemPromptWithKB(
  name: string,
  content: string,
  vectorStoreId?: string,
  dashboardTemplate?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      content,
      vector_store_id: vectorStoreId ?? '',
      dashboard_template: dashboardTemplate ?? {},
    }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '鍒涘缓瑙掕壊澶辫触'))
  return res.json()
}

export async function updateSystemPromptWithKB(
  id: string,
  name: string,
  content: string,
  vectorStoreId?: string,
  dashboardTemplate?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      content,
      vector_store_id: vectorStoreId ?? '',
      dashboard_template: dashboardTemplate ?? {},
    }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '鏇存柊瑙掕壊澶辫触'))
  return res.json()
}

// 鈹€鈹€ Reports 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function createDeckDraft(payload: {
  session_id: string
  panel_config: ModelConfig
  knowledge_base_enabled: boolean
  target_slide_count: number
  theme?: 'default' | 'midnight' | 'sunrise'
  answer_group_id?: string
  panel_id?: string
  template_id?: string
  template_options?: Record<string, unknown>
}): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

export async function getDecks(limit = 100): Promise<DeckSpec[]> {
  const safeLimit = Math.max(1, Math.min(500, Math.floor(limit)))
  const res = await fetch(`${BASE}/decks?limit=${encodeURIComponent(String(safeLimit))}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    decks?: DeckSpec[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return Array.isArray(data.decks) ? data.decks.map(normalizeDeckSpec) : []
}

export async function getDeck(deckId: string): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

export async function updateDeck(deckId: string, payload: {
  title?: string
  theme?: 'default' | 'midnight' | 'sunrise'
  slides?: DeckSlide[]
}): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

export async function exportDeck(
  deckId: string,
  format: 'pptx' = 'pptx',
  options: ExportDeckOptions = {},
): Promise<Blob> {
  const params = new URLSearchParams({ format })
  if (options.allowUnsafeExport) {
    params.set('allow_unsafe_export', 'true')
  }
  if (options.overrideReason?.trim()) {
    params.set('override_reason', options.overrideReason.trim())
  }

  const res = await fetch(`${BASE}/decks/${deckId}/export?${params.toString()}`)
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, res.statusText))
  }
  return res.blob()
}

export async function createDeckShareLink(deckId: string): Promise<ShareLinkResponse> {
  const res = await fetch(`${BASE}/decks/${deckId}/share`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<ShareLinkResponse>
}

export async function updateDeckBlockRefs(
  deckId: string,
  slideId: string,
  blockId: string,
  payload: UpdateDeckBlockRefsPayload,
): Promise<UpdateDeckBlockRefsResponse> {
  const res = await fetch(
    `${BASE}/decks/${encodeURIComponent(deckId)}/slides/${encodeURIComponent(slideId)}/blocks/${encodeURIComponent(blockId)}/refs`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to update deck block references'))
  }
  const data = await res.json().catch(() => ({})) as Record<string, unknown>
  return {
    deck: normalizeDeckSpec(data.deck),
    slide_id: readString(data.slide_id),
    block_id: readString(data.block_id),
    block: normalizeDeckBlock(data.block, 0),
    citation_validation: normalizeDeckCitationValidation(data.citation_validation) ?? defaultDeckCitationValidation(),
    evidence_review: normalizeDeckEvidenceReview(data.evidence_review) ?? defaultDeckEvidenceReview(),
    export_gate: (typeof data.export_gate === 'object' && data.export_gate !== null
      ? data.export_gate
      : {
          blocked: false,
          overridden: false,
          can_export: true,
          reason: '',
          message: '',
        }) as DeckExportGate,
  }
}

export async function regenerateDeckSlide(
  deckId: string,
  slideId: string,
  payload: {
    panel_config: ModelConfig
    knowledge_base_enabled?: boolean
  },
): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}/slides/${slideId}/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

// 鈹€鈹€ Knowledge Bases 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

export async function getKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await fetch(`${BASE}/knowledge-bases`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load knowledge bases'))
  const data = await res.json()
  return data.knowledge_bases as KnowledgeBase[]
}

export async function getKBHealth(): Promise<KBHealthData> {
  const res = await fetch(`${BASE}/knowledge-base/health`)
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to load knowledge base health.'))
  }
  return res.json()
}

export async function getKnowledgeBaseChunks(params?: {
  path?: string
  query?: string
  source?: string
  offset?: number
  limit?: number
}): Promise<KnowledgeBaseChunksResponse> {
  const searchParams = new URLSearchParams()
  if (params?.path?.trim()) searchParams.set('path', params.path.trim())
  if (params?.query?.trim()) searchParams.set('query', params.query.trim())
  if (params?.source?.trim()) searchParams.set('source', params.source.trim())
  if (typeof params?.offset === 'number' && Number.isFinite(params.offset)) {
    searchParams.set('offset', String(Math.max(0, Math.floor(params.offset))))
  }
  if (typeof params?.limit === 'number' && Number.isFinite(params.limit)) {
    const safeLimit = Math.max(1, Math.min(200, Math.floor(params.limit)))
    searchParams.set('limit', String(safeLimit))
  }

  const query = searchParams.toString()
  const res = await fetch(`${BASE}/knowledge-base/chunks${query ? `?${query}` : ''}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function updateKnowledgeBaseChunk(
  chunkId: string,
  payload: {
    content?: string
    source?: string
    path?: string
  },
): Promise<{ ok: boolean; chunk_id: string; reindexed: boolean }> {
  const searchParams = new URLSearchParams()
  if (payload.path?.trim()) searchParams.set('path', payload.path.trim())
  const query = searchParams.toString()
  const res = await fetch(
    `${BASE}/knowledge-base/chunks/${encodeURIComponent(chunkId)}${query ? `?${query}` : ''}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(payload.content !== undefined ? { content: payload.content } : {}),
        ...(payload.source !== undefined ? { source: payload.source } : {}),
      }),
    },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function deleteKnowledgeBaseChunk(chunkId: string, path?: string): Promise<void> {
  const searchParams = new URLSearchParams()
  if (path?.trim()) searchParams.set('path', path.trim())
  const query = searchParams.toString()
  const res = await fetch(
    `${BASE}/knowledge-base/chunks/${encodeURIComponent(chunkId)}${query ? `?${query}` : ''}`,
    { method: 'DELETE' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function testKBRetrieval(
  query: string,
  options?: {
    search_k?: number
    fetch_k?: number
    use_rerank?: boolean
    retrieval_mode?: 'semantic' | 'keyword' | 'hybrid'
  },
): Promise<RetrievalTestResult> {
  const res = await fetch(`${BASE}/knowledge-base/test-retrieval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, ...options }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Retrieval test failed.'))
  return res.json()
}

export async function deleteKnowledgeBase(path?: string): Promise<void> {
  const url = path
    ? `${BASE}/knowledge-base/by-path?path=${encodeURIComponent(path)}`
    : `${BASE}/knowledge-base`
  const res = await fetch(url, { method: 'DELETE' })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, res.statusText))
  }
}
