import type {
  McpConnector,
  McpConnectorManifest,
  McpMarketplaceCategory,
  McpMarketplaceSummary,
} from '../../api/client'

export interface McpMarketplaceSummaryView {
  total: number
  enabled: number
  healthy: number
  approval: number
  builtin: number
  custom: number
  categories: number
}

export interface McpManifestValidationResult {
  valid: boolean
  errors: string[]
  requiredFields: string[]
  sensitiveFields: string[]
  parsed?: McpConnectorManifest
}

const MCP_MANIFEST_NAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/
const MCP_HTTP_TRANSPORTS = new Set(['http', 'sse', 'streamable_http'])

export function mcpConnectorTone(connector: McpConnector): string {
  if (connector.healthy) return 'bg-accent-green/15 text-accent-green'
  if (connector.enabled) return 'bg-amber-300/15 text-amber-300'
  return 'bg-bg-hover text-text-secondary'
}

export function mcpConnectorLabel(connector: McpConnector): string {
  if (connector.healthy) return 'Healthy'
  if (connector.template || connector.source === 'template') return 'Template'
  if (connector.enabled) return connector.status || 'Needs check'
  return connector.status || 'Disabled'
}

export function buildMcpConnectorManifestDraft(connector: McpConnector): McpConnectorManifest {
  const transport = connector.config_schema?.transport || connector.transport || 'stdio'
  const scopes = connector.capability_scopes ?? connector.policy?.capability_scopes ?? []
  const manifest: McpConnectorManifest = {
    name: connector.name,
    label: connector.label || connector.name,
    description: connector.description || undefined,
    category: connector.category || 'custom',
    transport,
    scopes,
    risk_level: connector.risk_level || connector.policy?.risk_level || 'medium',
    requires_approval: connector.requires_approval ?? connector.policy?.requires_approval,
  }

  if (transport === 'stdio') {
    manifest.command = ''
    manifest.args = []
  } else {
    manifest.url = ''
  }

  if (connector.config_schema) {
    manifest.config_schema = connector.config_schema
  }

  return manifest
}

export function formatMcpConnectorManifestDraft(connector: McpConnector): string {
  return JSON.stringify(buildMcpConnectorManifestDraft(connector), null, 2)
}

function uniqueStrings(values: Array<string | undefined>): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const value of values) {
    const normalized = String(value || '').trim()
    if (!normalized || seen.has(normalized)) continue
    seen.add(normalized)
    result.push(normalized)
  }
  return result
}

function readManifestField(manifest: McpConnectorManifest, field: string): unknown {
  return field.split('.').reduce<unknown>((current, part) => {
    if (!current || typeof current !== 'object') return undefined
    return (current as Record<string, unknown>)[part]
  }, manifest)
}

function hasManifestFieldValue(manifest: McpConnectorManifest, field: string): boolean {
  if (field === 'command') {
    const command = readManifestField(manifest, 'command')
    const installCommand = readManifestField(manifest, 'install_command')
    return hasRawManifestFieldValue(command) || hasRawManifestFieldValue(installCommand)
  }

  const value = readManifestField(manifest, field)
  return hasRawManifestFieldValue(value)
}

function hasRawManifestFieldValue(value: unknown): boolean {
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'string') return value.trim().length > 0
  if (value && typeof value === 'object') return Object.keys(value).length > 0
  return value !== undefined && value !== null
}

export function validateMcpConnectorManifest(manifest: McpConnectorManifest): McpManifestValidationResult {
  const transport = String(manifest.transport || manifest.config_schema?.transport || 'stdio').trim() || 'stdio'
  const requiredFields = uniqueStrings([
    'name',
    ...(manifest.config_schema?.required ?? []),
    transport === 'stdio' ? 'command' : undefined,
    MCP_HTTP_TRANSPORTS.has(transport) ? 'url' : undefined,
  ])
  const sensitiveFields = uniqueStrings(manifest.config_schema?.sensitive ?? [])
  const errors: string[] = []

  if (!manifest.name?.trim()) {
    errors.push('name: MCP connector manifest requires a name')
  } else if (!MCP_MANIFEST_NAME_PATTERN.test(manifest.name)) {
    errors.push('name: MCP connector manifest name must use only letters, numbers, dots, underscores, or hyphens')
  }

  if (transport !== 'stdio' && !MCP_HTTP_TRANSPORTS.has(transport)) {
    errors.push(`transport: Unsupported MCP connector transport: ${transport}`)
  }

  for (const field of requiredFields) {
    if (field === 'name') continue
    if (!hasManifestFieldValue(manifest, field)) {
      errors.push(`${field}: required by connector manifest`)
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    requiredFields,
    sensitiveFields,
    parsed: manifest,
  }
}

export function validateMcpConnectorManifestText(text: string): McpManifestValidationResult {
  if (!text.trim()) {
    return { valid: false, errors: [], requiredFields: [], sensitiveFields: [] }
  }

  try {
    const parsed = JSON.parse(text) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {
        valid: false,
        errors: ['MCP connector manifest must be a JSON object'],
        requiredFields: [],
        sensitiveFields: [],
      }
    }
    return validateMcpConnectorManifest(parsed as McpConnectorManifest)
  } catch {
    return {
      valid: false,
      errors: ['MCP connector manifest must be valid JSON'],
      requiredFields: [],
      sensitiveFields: [],
    }
  }
}

export function normalizeMcpCategoryId(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '-')
}

export function mcpCategoryLabel(value: string): string {
  return value
    .trim()
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function buildMcpMarketplaceSummary(
  connectors: McpConnector[],
  backendSummary?: McpMarketplaceSummary | null,
): McpMarketplaceSummaryView {
  if (backendSummary) {
    return {
      total: backendSummary.total,
      enabled: backendSummary.enabled,
      healthy: backendSummary.healthy,
      approval: backendSummary.requires_approval,
      builtin: backendSummary.builtin,
      custom: backendSummary.custom,
      categories: backendSummary.categories,
    }
  }

  return {
    total: connectors.length,
    enabled: connectors.filter((connector) => connector.enabled).length,
    healthy: connectors.filter((connector) => connector.healthy).length,
    approval: connectors.filter((connector) => connector.requires_approval).length,
    builtin: connectors.filter((connector) => connector.builtin).length,
    custom: connectors.filter((connector) => !connector.builtin).length,
    categories: new Set(connectors.map((connector) => connector.category || 'custom')).size,
  }
}

export function buildMcpMarketplaceCategories(
  connectors: McpConnector[],
  backendCategories?: McpMarketplaceCategory[] | null,
): McpMarketplaceCategory[] {
  if (backendCategories && backendCategories.length > 0) {
    return backendCategories.map((category) => ({
      id: normalizeMcpCategoryId(category.id || category.label || 'custom'),
      label: category.label || mcpCategoryLabel(category.id || 'custom'),
      total: category.total,
      enabled: category.enabled,
      healthy: category.healthy,
      requires_approval: category.requires_approval,
      connectors: category.connectors,
    }))
  }

  const grouped = new Map<string, McpMarketplaceCategory>()
  for (const connector of connectors) {
    const rawCategory = connector.category || 'custom'
    const id = normalizeMcpCategoryId(rawCategory)
    const existing = grouped.get(id) ?? {
      id,
      label: mcpCategoryLabel(rawCategory),
      total: 0,
      enabled: 0,
      healthy: 0,
      requires_approval: 0,
      connectors: [],
    }
    existing.total += 1
    existing.enabled += connector.enabled ? 1 : 0
    existing.healthy += connector.healthy ? 1 : 0
    existing.requires_approval += connector.requires_approval ? 1 : 0
    existing.connectors.push(connector.name)
    grouped.set(id, existing)
  }

  return Array.from(grouped.values()).sort((a, b) => a.label.localeCompare(b.label))
}

export function filterVisibleMcpConnectors(
  connectors: McpConnector[],
  categories: McpMarketplaceCategory[],
  categoryId: string,
): McpConnector[] {
  if (categoryId === 'all') return connectors
  const category = categories.find((item) => item.id === categoryId)
  const connectorNames = new Set(category?.connectors ?? [])
  if (connectorNames.size > 0) {
    return connectors.filter((connector) => connectorNames.has(connector.name))
  }
  return connectors.filter(
    (connector) => normalizeMcpCategoryId(connector.category || 'custom') === categoryId,
  )
}

export function mcpMarketplaceSummaryFromConfig(
  config: { marketplace?: { summary?: McpMarketplaceSummary | null } | null } | null,
  connectors: McpConnector[],
): McpMarketplaceSummaryView {
  return buildMcpMarketplaceSummary(connectors, config?.marketplace?.summary ?? null)
}

export function mcpMarketplaceCategoriesFromConfig(
  config: { marketplace?: { categories?: McpMarketplaceCategory[] | null } | null } | null,
  connectors: McpConnector[],
): McpMarketplaceCategory[] {
  return buildMcpMarketplaceCategories(connectors, config?.marketplace?.categories ?? null)
}

export function visibleMcpConnectors(
  config: { marketplace?: { categories?: McpMarketplaceCategory[] | null } | null } | null,
  connectors: McpConnector[],
  categoryId: string,
): McpConnector[] {
  return filterVisibleMcpConnectors(
    connectors,
    buildMcpMarketplaceCategories(connectors, config?.marketplace?.categories ?? null),
    categoryId,
  )
}
