import type {
  Session,
  Workspace,
  WorkspaceToolConfig,
  WorkspaceOutputPreset,
  WorkspacePreset,
  McpConnector,
  McpConnectorPolicy,
  McpConnectorApprovalDetail,
  McpConnectorApprovalsResponse,
  McpConfigPersistence,
  McpMarketplaceSummary,
  McpMarketplaceCategory,
  McpMarketplace,
  McpConfigResponse,
  SaveMcpConfigPayload,
  McpRuntimeServerHealth,
  McpRuntimeHealthSummary,
  McpRuntimeHealthHistoryServer,
  McpRuntimeHealthHistoryItem,
  McpRuntimeHealthHistoryResponse,
  McpRuntimeHealthResponse,
  IntegratorConnectorType,
  IntegratorConnector,
  IntegratorConnectorsResponse,
  IntegratorConnectorTestCheck,
  IntegratorConnectorTestResult,
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeMode,
  IntegratorConnectorProbeOptions,
  IntegratorConnectorProbeDetails,
  IntegratorConnectorProbeResponse,
  IntegratorAuditEvent,
  IntegratorAuditEventsResponse,
  IntegratorSchedule,
  IntegratorSchedulesResponse,
  IntegratorScheduleTriggerResponse,
  IntegratorScheduleTickResponse,
  SessionMemoryKind,
  MessageFeedbackValue,
  RetrievalFeedbackValue,
  SessionMemory,
  AuthWhoAmI,
  SsoConfig,
  SaveSsoConfigPayload,
  SsoLoginResponse,
  SecurityStatusResponse,
  SecurityAuditSummaryCategory,
  SecurityAuditSummaryApiCategory,
  SecurityAuditSummary,
  SecurityAuditEvent,
  SecurityAuditEventsResponse,
  SecurityAuditEventFilters,
  SecurityAuditCleanupPayload,
  SecurityAuditCleanupResponse,
  TraceEventKind,
  TraceFilters,
  TraceEvent,
  TraceSummary,
  TraceDashboardCard,
  TracePanelTemplate,
  TraceExportPreview,
  TraceExportPayload,
  TraceEventsResponse,
  ClearTracesResponse,
  IngestTraceEventsResponse,
  ObservabilitySnapshotResponse,
  ResourceGrantRole,
  ResourceGrantSubjectType,
  ResourceGrant,
  ResourceGrantListQuery,
  ResourceGrantListResponse,
  ResourceGrantMutationPayload,
  IdentityRole,
  IdentityOrganization,
  IdentityUser,
  IdentityMembership,
  IdentityCatalog,
  UpsertOrganizationPayload,
  UpsertUserPayload,
  SetMembershipPayload,
  Message,
  SessionPanel,
  ConnectionType,
  ModelConfig,
  SourceItem,
  ChatImage,
  ChatFile,
  SessionAttachment,
  SessionAttachmentSummary,
  SSEChunk,
  DocStats,
  UploadDocumentsResponse,
  TaskStatus,
  TaskApprovalDecision,
  TaskApprovalPolicy,
  BatchTaskApproval,
  BatchTaskApprovalResult,
  BatchTaskApprovalResponse,
  CreateMultiAgentWorkflowTaskPayload,
  TaskRecord,
  SystemPrompt,
  DashboardTemplateConfig,
  KnowledgeBase,
  KBHealthData,
  KnowledgeBaseChunk,
  KnowledgeBaseChunksResponse,
  RetrievalTestResult,
  RetrievalDebugItem,
  MessagesResponse,
  ImportSessionMessagesPayload,
  Bookmark,
  SessionAttachmentsResponse,
  AnswerGroupReviewFactor,
  AnswerGroupReviewComparisonFactorDelta,
  AnswerGroupReviewComparison,
  AnswerGroupReviewConsensusPoint,
  AnswerGroupReviewDifferencePoint,
  AnswerGroupModelPerformance,
  AnswerGroupTokenUsage,
  AnswerGroupTokenSummary,
  AnswerGroupSynthesis,
  AnswerGroupPreferenceSignal,
  AnswerGroupReviewResponseItem,
  AnswerGroupReviewResponse,
  PromoteAnswerResponse,
  ShareLinkResponse,
  DeckWarning,
  DeckQualityState,
  DeckSlideEvidenceCoverage,
  DeckEvidenceCoverage,
  DeckEvidenceReviewStatus,
  DeckEvidenceReviewSeverity,
  DeckEvidenceReviewActionItem,
  DeckCitationValidationStatus,
  DeckCitationValidationIssue,
  DeckCitationValidation,
  DeckEvidenceReviewSlide,
  DeckEvidenceReview,
  DeckMeta,
  DeckGeneration,
  DeckChartDataset,
  DeckBlock,
  DeckEvidenceRef,
  DeckSlideStatus,
  DeckSlide,
  DeckSourceItem,
  DeckSpec,
  ArtifactType,
  ArtifactExportFormat,
  ReportArtifactQA,
  ClaimEvidenceSource,
  ClaimEvidenceChain,
  ClaimVerificationSummary,
  ResearchParagraphCitation,
  ResearchNavigationIndex,
  ResearchCitationGraph,
  ResearchConflictSummary,
  ResearchConflictGroup,
  ResearchConflictResolutionPayload,
  ResearchArchive,
  ResearchArchiveListResponse,
  ReportArtifactContent,
  DeckArtifactContent,
  ArtifactRecord,
  GeneratedReport,
  ReportScopeOptions,
  ExportDeckOptions,
  DeckExportGate,
  UpdateDeckBlockRefsPayload,
  UpdateDeckBlockRefsResponse,
} from './types'



export function normalizeSession(raw: Partial<Session> & Pick<Session, 'session_id' | 'title' | 'created_at' | 'updated_at' | 'message_count'>): Session {
  return {
    session_id: raw.session_id,
    title: raw.title,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    message_count: raw.message_count,
    is_archived: raw.is_archived === true,
    is_favorite: raw.is_favorite === true,
    is_pinned: raw.is_pinned === true,
    session_order: Number(raw.session_order ?? 0) || 0,
    tags: Array.isArray(raw.tags)
      ? raw.tags.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    workspace_id: typeof raw.workspace_id === 'string' && raw.workspace_id.trim()
      ? raw.workspace_id.trim()
      : 'workspace-default',
    search_preview:
      typeof raw.search_preview === 'string' && raw.search_preview.trim()
        ? raw.search_preview
        : undefined,
    search_source: raw.search_source === 'message' ? 'message' : raw.search_source === 'title' ? 'title' : undefined,
  }
}

export function normalizeWorkspace(raw: Partial<Workspace> & Pick<Workspace, 'workspace_id' | 'name' | 'created_at' | 'updated_at' | 'session_count'>): Workspace {
  const color = typeof raw.color === 'string' ? raw.color.trim().toLowerCase() : 'blue'
  const rawPreset = (raw as Partial<Workspace> & { preset?: Partial<WorkspacePreset> }).preset
  const rawToolConfig = rawPreset?.tool_config
  const rawOutputPreset = rawPreset?.output_preset
  return {
    workspace_id: raw.workspace_id,
    name: raw.name,
    description: typeof raw.description === 'string' ? raw.description : '',
    color: (['slate', 'blue', 'green', 'amber', 'rose'].includes(color) ? color : 'blue') as Workspace['color'],
    preset: {
      default_panels: Array.isArray(rawPreset?.default_panels)
        ? rawPreset!.default_panels
          .filter(
            (item) =>
              Boolean(
                item &&
                typeof item === 'object' &&
                typeof (item as { panel_id?: string }).panel_id === 'string' &&
                (item as { panel_id?: string }).panel_id?.trim(),
              ),
          )
          .map((item) => normalizeModelConfig(item as Partial<ModelConfig> & { panel_id: string }))
        : [],
      tool_config: {
        web_search_enabled: rawToolConfig?.web_search_enabled === true,
        knowledge_base_enabled: rawToolConfig?.knowledge_base_enabled !== false,
        mcp_servers_enabled: Array.isArray(rawToolConfig?.mcp_servers_enabled)
          ? rawToolConfig.mcp_servers_enabled.filter(
              (item): item is string => typeof item === 'string' && item.trim().length > 0,
            )
          : [],
      },
      output_preset: {
        deck_theme:
          rawOutputPreset?.deck_theme === 'midnight' || rawOutputPreset?.deck_theme === 'sunrise'
            ? rawOutputPreset.deck_theme
            : 'default',
        target_slide_count: Math.max(
          4,
          Math.min(10, Number(rawOutputPreset?.target_slide_count ?? 8) || 8),
        ),
      },
    },
    is_active: raw.is_active === true,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    session_count: Number(raw.session_count ?? 0),
  }
}

export function normalizeBookmark(raw: Partial<Bookmark> & { id: string }): Bookmark {
  const rawBookmark = raw as Partial<Bookmark> & {
    session_id?: string
    session_title?: string
    message_id?: number
    panel_id?: string
    answer_group_id?: string
    model_id?: string
    created_at?: number
    updated_at?: number
  }

  return {
    id: raw.id,
    sessionId:
      typeof rawBookmark.sessionId === 'string' && rawBookmark.sessionId.trim()
        ? rawBookmark.sessionId.trim()
        : typeof rawBookmark.session_id === 'string' && rawBookmark.session_id.trim()
          ? rawBookmark.session_id.trim()
          : '',
    sessionTitle:
      typeof rawBookmark.sessionTitle === 'string'
        ? rawBookmark.sessionTitle
        : typeof rawBookmark.session_title === 'string'
          ? rawBookmark.session_title
          : '',
    messageId:
      typeof rawBookmark.messageId === 'number'
        ? rawBookmark.messageId
        : typeof rawBookmark.message_id === 'number'
          ? rawBookmark.message_id
          : undefined,
    panelId:
      typeof rawBookmark.panelId === 'string'
        ? rawBookmark.panelId
        : typeof rawBookmark.panel_id === 'string'
          ? rawBookmark.panel_id
          : '',
    answerGroupId:
      typeof rawBookmark.answerGroupId === 'string'
        ? rawBookmark.answerGroupId
        : typeof rawBookmark.answer_group_id === 'string'
          ? rawBookmark.answer_group_id
          : '',
    role: rawBookmark.role === 'user' ? 'user' : 'assistant',
    content: typeof rawBookmark.content === 'string' ? rawBookmark.content : '',
    modelId:
      typeof rawBookmark.modelId === 'string'
        ? rawBookmark.modelId
        : typeof rawBookmark.model_id === 'string'
          ? rawBookmark.model_id
          : undefined,
    createdAt:
      typeof rawBookmark.createdAt === 'number'
        ? rawBookmark.createdAt
        : typeof rawBookmark.created_at === 'number'
          ? rawBookmark.created_at
          : Date.now() / 1000,
    updatedAt:
      typeof rawBookmark.updatedAt === 'number'
        ? rawBookmark.updatedAt
        : typeof rawBookmark.updated_at === 'number'
          ? rawBookmark.updated_at
          : Date.now() / 1000,
    source: rawBookmark.source === 'local' ? 'local' : 'remote',
  }
}

export function normalizeConnectionType(
  connectionType?: string,
  baseUrl?: string,
): ConnectionType {
  const rawType = (connectionType ?? '').trim().toLowerCase()
  const rawBaseUrl = (baseUrl ?? '').trim().toLowerCase()

  if (rawType === 'ollama' || rawType === 'local') return 'ollama'
  if (rawType === 'deepseek' || rawType === 'deepseek_compatible') return 'deepseek'
  if (rawType === 'anthropic' || rawType === 'claude') return 'anthropic'
  if (rawType === 'google' || rawType === 'gemini') return 'google'
  if (
    rawType === 'openai_compatible' ||
    rawType === 'cloud' ||
    rawType === 'openai' ||
    rawType === 'openrouter'
  ) {
    return 'openai_compatible'
  }

  if (rawBaseUrl.includes('deepseek')) return 'deepseek'
  if (rawBaseUrl.includes('anthropic')) return 'anthropic'
  if (rawBaseUrl.includes('generativelanguage') || rawBaseUrl.includes('googleapis')) {
    return 'google'
  }
  if (rawBaseUrl.includes('11434')) return 'ollama'
  return 'openai_compatible'
}

export function defaultBaseUrlForConnectionType(connectionType: ConnectionType): string {
  switch (connectionType) {
    case 'ollama':
      return 'http://localhost:11434'
    case 'deepseek':
      return 'https://api.deepseek.com'
    case 'anthropic':
    case 'google':
      return ''
    case 'openai_compatible':
    default:
      return 'https://openrouter.ai/api/v1'
  }
}

export function defaultModelForConnectionType(connectionType: ConnectionType): string {
  switch (connectionType) {
    case 'ollama':
      return 'qwen3.5-2B:latest'
    case 'deepseek':
      return 'deepseek-chat'
    case 'anthropic':
      return 'claude-3-5-sonnet-latest'
    case 'google':
      return 'gemini-2.0-flash'
    case 'openai_compatible':
    default:
      return 'gpt-4o-mini'
  }
}

export function normalizeModelConfig(config: Partial<ModelConfig> & { panel_id: string }): ModelConfig {
  const connectionType = normalizeConnectionType(
    config.connection_type ?? config.provider,
    config.base_url,
  )
  return {
    panel_id: config.panel_id,
    connection_type: connectionType,
    provider: connectionType,
    model: (config.model ?? defaultModelForConnectionType(connectionType)).trim(),
    base_url: (config.base_url ?? defaultBaseUrlForConnectionType(connectionType)).trim(),
    api_key: config.api_key ?? '',
    api_key_ref: (config.api_key_ref ?? '').trim(),
    temperature: config.temperature ?? 0.3,
    agent_mode: config.agent_mode ?? 'auto',
  }
}

export function readString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

export function readNumber(value: unknown): number {
  return typeof value === 'number' ? value : Number(value ?? 0) || 0
}

export function readBoolean(value: unknown): boolean {
  return value === true
}

export function readStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

export function readOptionalRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : undefined
}

export function readRecordCollection(value: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(value)) {
    return value
      .map((item, index): Record<string, unknown> | undefined => {
        if (typeof item === 'object' && item !== null) return item as Record<string, unknown>
        if (item === undefined || item === null) return undefined
        return { index, value: item }
      })
      .filter((item): item is Record<string, unknown> => item !== undefined)
  }

  const data = readOptionalRecord(value)
  if (!data) return []
  return Object.entries(data).map(([key, item]) => {
    if (typeof item === 'object' && item !== null) {
      return { key, ...(item as Record<string, unknown>) }
    }
    return { key, value: item }
  })
}

export function readStringArrayRecord(value: unknown): Record<string, string[]> {
  const data = readOptionalRecord(value)
  if (!data) return {}
  return Object.fromEntries(
    Object.entries(data).map(([key, item]) => [key, readStringArray(item)]),
  )
}

export function readFirstField(
  primary: Record<string, unknown>,
  fallback: Record<string, unknown>,
  keys: string[],
): unknown {
  for (const key of keys) {
    if (primary[key] !== undefined) return primary[key]
    if (fallback[key] !== undefined) return fallback[key]
  }
  return undefined
}

export function normalizeDeckQualityState(value: unknown): DeckQualityState {
  return value === 'supported' || value === 'manual' ? value : 'weak_support'
}

export function normalizeDeckSlideEvidenceCoverage(value: unknown): DeckSlideEvidenceCoverage[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      slide_id: readString(item.slide_id),
      slide_type: readString(item.slide_type),
      evidence_ref_count: readNumber(item.evidence_ref_count),
      has_evidence: item.has_evidence === true,
      is_coverable: item.is_coverable !== false,
      quality_state: normalizeDeckQualityState(item.quality_state),
    }))
}

export function normalizeDeckEvidenceCoverage(value: unknown): DeckEvidenceCoverage | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  return {
    total_slides: readNumber(data.total_slides),
    coverable_slide_count: readNumber(data.coverable_slide_count),
    slides_with_evidence: readNumber(data.slides_with_evidence),
    total_evidence_refs: readNumber(data.total_evidence_refs),
    coverage_ratio: readNumber(data.coverage_ratio),
    unsupported_slide_ids: readStringArray(data.unsupported_slide_ids),
    slides: normalizeDeckSlideEvidenceCoverage(data.slides),
  }
}

export function normalizeDeckEvidenceReviewStatus(value: unknown): DeckEvidenceReviewStatus {
  if (value === 'supported' || value === 'not_applicable') return value
  return 'needs_review'
}

export function normalizeDeckEvidenceReviewSeverity(value: unknown): DeckEvidenceReviewSeverity {
  if (value === 'error' || value === 'info') return value
  return 'warning'
}

export function normalizeDeckEvidenceReviewActionItems(value: unknown): DeckEvidenceReviewActionItem[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      code: readString(item.code),
      severity: normalizeDeckEvidenceReviewSeverity(item.severity),
      message: readString(item.message),
      slide_ids: readStringArray(item.slide_ids),
    }))
}

export function normalizeDeckCitationValidationStatus(value: unknown): DeckCitationValidationStatus {
  return value === 'failed' ? 'failed' : 'passed'
}

export function normalizeDeckCitationValidationIssues(value: unknown): DeckCitationValidationIssue[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      code: readString(item.code),
      message: readString(item.message),
      slide_id: readString(item.slide_id),
      block_id: readString(item.block_id),
      evidence_ref_id: readString(item.evidence_ref_id),
      source_id: readString(item.source_id),
    }))
}

export function normalizeDeckCitationValidation(value: unknown): DeckCitationValidation | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  const issues = normalizeDeckCitationValidationIssues(data.issues)
  return {
    status: normalizeDeckCitationValidationStatus(data.status),
    can_export: data.can_export !== false,
    issue_count: readNumber(data.issue_count) || issues.length,
    missing_source_ids: readStringArray(data.missing_source_ids),
    missing_block_evidence_ref_ids: readStringArray(data.missing_block_evidence_ref_ids),
    issues,
  }
}

export function normalizeDeckEvidenceReviewSlides(value: unknown): DeckEvidenceReviewSlide[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      slide_id: readString(item.slide_id),
      title: readString(item.title),
      slide_type: readString(item.slide_type),
      is_coverable: item.is_coverable !== false,
      has_evidence: item.has_evidence === true,
      evidence_ref_count: readNumber(item.evidence_ref_count),
      quality_state: normalizeDeckQualityState(item.quality_state),
      needs_review: item.needs_review === true,
      source_ids: readStringArray(item.source_ids),
      source_titles: readStringArray(item.source_titles),
    }))
}

export function normalizeDeckEvidenceReview(value: unknown): DeckEvidenceReview | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  const actionItems = normalizeDeckEvidenceReviewActionItems(data.action_items)
  return {
    status: normalizeDeckEvidenceReviewStatus(data.status),
    coverage_ratio: readNumber(data.coverage_ratio),
    coverable_slide_count: readNumber(data.coverable_slide_count),
    slides_with_evidence: readNumber(data.slides_with_evidence),
    unsupported_slide_ids: readStringArray(data.unsupported_slide_ids),
    needs_review_slide_ids: readStringArray(data.needs_review_slide_ids),
    action_count: readNumber(data.action_count) || actionItems.length,
    action_items: actionItems,
    slides: normalizeDeckEvidenceReviewSlides(data.slides),
    citation_validation: normalizeDeckCitationValidation(data.citation_validation),
  }
}

export function defaultDeckCitationValidation(): DeckCitationValidation {
  return {
    status: 'passed',
    can_export: true,
    issue_count: 0,
    missing_source_ids: [],
    missing_block_evidence_ref_ids: [],
    issues: [],
  }
}

export function defaultDeckEvidenceReview(): DeckEvidenceReview {
  return {
    status: 'not_applicable',
    coverage_ratio: 0,
    coverable_slide_count: 0,
    slides_with_evidence: 0,
    unsupported_slide_ids: [],
    needs_review_slide_ids: [],
    action_count: 0,
    action_items: [],
    slides: [],
  }
}

export function normalizeDeckBlock(raw: unknown, index: number): DeckBlock {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const content = typeof data.content === 'object' && data.content !== null
    ? (data.content as Record<string, unknown>)
    : {}
  return {
    id: readString(data.id) || `block-${index + 1}`,
    kind: readString(data.kind),
    role: readString(data.role),
    content: {
      ...content,
      text: readString(content.text) || undefined,
      items: readStringArray(content.items),
      title: readString(content.title) || undefined,
      description: readString(content.description) || undefined,
      chart_type:
        content.chart_type === 'bar' || content.chart_type === 'line' || content.chart_type === 'pie'
          ? content.chart_type
          : undefined,
      labels: readStringArray(content.labels),
      datasets: Array.isArray(content.datasets) ? (content.datasets as DeckChartDataset[]) : [],
      evidence_ref_ids: readStringArray(content.evidence_ref_ids),
      evidence_source_ids: readStringArray(content.evidence_source_ids),
      evidence_excerpt_ids: readStringArray(content.evidence_excerpt_ids),
    },
    editable: data.editable !== false,
  }
}

export function normalizeDeckEvidenceRef(raw: unknown): DeckEvidenceRef {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  return {
    id: readString(data.id),
    source_id: readString(data.source_id),
    source_title: readString(data.source_title),
    excerpt_id: data.excerpt_id === null ? null : readString(data.excerpt_id) || undefined,
    snippet: readString(data.snippet),
    confidence: readNumber(data.confidence),
  }
}

export function normalizeDeckSlide(raw: unknown, index: number): DeckSlide {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const status = typeof data.status === 'object' && data.status !== null
    ? (data.status as Record<string, unknown>)
    : {}
  return {
    id: readString(data.id) || `slide-${index + 1}`,
    type: readString(data.type),
    title: readString(data.title),
    subtitle: readString(data.subtitle),
    layout: readString(data.layout),
    intent: readString(data.intent),
    speaker_notes: readString(data.speaker_notes),
    blocks: Array.isArray(data.blocks) ? data.blocks.map(normalizeDeckBlock) : [],
    evidence_refs: Array.isArray(data.evidence_refs) ? data.evidence_refs.map(normalizeDeckEvidenceRef) : [],
    quality_state: normalizeDeckQualityState(data.quality_state),
    status: {
      locked: status.locked === true,
      dirty: status.dirty === true,
      review_state: readString(status.review_state) || 'draft',
    },
  }
}

export function normalizeDeckSourceItem(raw: unknown): DeckSourceItem {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  return {
    id: readString(data.id),
    type: readString(data.type),
    title: readString(data.title),
    document_id: data.document_id === null ? null : readString(data.document_id) || undefined,
    uri: data.uri === null ? null : readString(data.uri) || undefined,
    metadata: typeof data.metadata === 'object' && data.metadata !== null
      ? (data.metadata as Record<string, unknown>)
      : {},
  }
}

export function normalizeDeckSpec(raw: unknown): DeckSpec {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const meta = typeof data.meta === 'object' && data.meta !== null ? (data.meta as Record<string, unknown>) : {}
  const generation = typeof data.generation === 'object' && data.generation !== null
    ? (data.generation as Record<string, unknown>)
    : {}
  const evidenceReview = normalizeDeckEvidenceReview(generation.evidence_review)
  const generationCitationValidation = normalizeDeckCitationValidation(generation.citation_validation)
  const topLevelCitationValidation = normalizeDeckCitationValidation(data.citation_validation)
  return {
    version: readString(data.version),
    deck_id: readString(data.deck_id),
    status: readString(data.status),
    meta: {
      title: readString(meta.title),
      subtitle: readString(meta.subtitle),
      language: readString(meta.language),
      audience: readString(meta.audience),
      purpose: readString(meta.purpose),
      author: readString(meta.author),
      theme: meta.theme === 'midnight' || meta.theme === 'sunrise' ? meta.theme : 'default',
      created_at: readString(meta.created_at),
      session_id: readString(meta.session_id),
      source_mode: meta.source_mode === 'chat_only' ? 'chat_only' : 'kb_plus_chat',
      generator_panel_id: readString(meta.generator_panel_id),
      source_answer_group_id: readString(meta.source_answer_group_id) || undefined,
      source_panel_id: readString(meta.source_panel_id) || undefined,
    },
    generation: {
      source: generation.source === 'chat_only' ? 'chat_only' : 'kb_plus_chat',
      target_slide_count: readNumber(generation.target_slide_count),
      actual_slide_count: readNumber(generation.actual_slide_count),
      warnings: Array.isArray(generation.warnings)
        ? generation.warnings
            .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
            .map((item) => ({
              code: readString(item.code),
              message: readString(item.message),
            }))
        : [],
      evidence_coverage: normalizeDeckEvidenceCoverage(generation.evidence_coverage),
      evidence_review: evidenceReview,
      citation_validation: generationCitationValidation ?? evidenceReview?.citation_validation,
    },
    slides: Array.isArray(data.slides) ? data.slides.map(normalizeDeckSlide) : [],
    source_registry: Array.isArray(data.source_registry) ? data.source_registry.map(normalizeDeckSourceItem) : [],
    citation_validation: topLevelCitationValidation ?? generationCitationValidation ?? evidenceReview?.citation_validation,
  }
}

export function normalizeClaimEvidenceSources(value: unknown): ClaimEvidenceSource[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      source_index: readNumber(item.source_index),
      title: readString(item.title),
      url: readString(item.url) || undefined,
      domain: readString(item.domain) || undefined,
      source_tier: readString(item.source_tier) || undefined,
      source_family: readString(item.source_family) || undefined,
      freshness_band: readString(item.freshness_band) || undefined,
      published_at: readString(item.published_at) || undefined,
      selection_reason: readString(item.selection_reason) || undefined,
      provider_caveat: readString(item.provider_caveat) || undefined,
    }))
}

export function normalizeClaimEvidenceChains(value: unknown): ClaimEvidenceChain[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      claim_id: readString(item.claim_id),
      claim_text: readString(item.claim_text),
      facet: readString(item.facet) || undefined,
      claim_type: readString(item.claim_type) || undefined,
      date: readString(item.date) || undefined,
      status: readString(item.status) || 'unverified',
      evidence_strength: readString(item.evidence_strength) || 'low',
      verification_note: readString(item.verification_note) || undefined,
      candidate_sources: readStringArray(item.candidate_sources),
      supporting_source_count: readNumber(item.supporting_source_count),
      independent_source_families: readStringArray(item.independent_source_families),
      has_primary_source: item.has_primary_source === true,
      needs_attention: item.needs_attention === true,
      sources: normalizeClaimEvidenceSources(item.sources),
    }))
}

export function normalizeClaimVerificationSummary(value: unknown): ClaimVerificationSummary | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  const resolutionActions =
    typeof data.resolution_actions === 'object' && data.resolution_actions !== null
      ? Object.fromEntries(
          Object.entries(data.resolution_actions as Record<string, unknown>).map(([key, count]) => [
            key,
            readNumber(count),
          ]),
        )
      : {}

  return {
    total_claims: readNumber(data.total_claims),
    verified_claims: readNumber(data.verified_claims),
    partial_claims: readNumber(data.partial_claims),
    unverified_claims: readNumber(data.unverified_claims),
    high_strength_claims: readNumber(data.high_strength_claims),
    medium_strength_claims: readNumber(data.medium_strength_claims),
    low_strength_claims: readNumber(data.low_strength_claims),
    claims_needing_attention: readStringArray(data.claims_needing_attention),
    contradiction_count: readNumber(data.contradiction_count),
    resolution_actions: resolutionActions,
  }
}

export function normalizeResearchCitationGraph(value: unknown): ResearchCitationGraph | undefined {
  const data = readOptionalRecord(value)
  if (!data) return undefined
  const nodes = readRecordCollection(data.nodes ?? data.vertices)
  const edges = readRecordCollection(data.edges ?? data.links)
  if (nodes.length === 0 && edges.length === 0) return undefined
  return { nodes, edges }
}

export function normalizeResearchNavigationIndex(value: unknown): ResearchNavigationIndex | undefined {
  const data = readOptionalRecord(value)
  if (!data) return undefined
  const links = readRecordCollection(data.links)
  return {
    paragraph_to_claims: readStringArrayRecord(data.paragraph_to_claims),
    paragraph_to_sources: readStringArrayRecord(data.paragraph_to_sources),
    claim_to_paragraphs: readStringArrayRecord(data.claim_to_paragraphs),
    source_to_paragraphs: readStringArrayRecord(data.source_to_paragraphs),
    links,
  }
}

export function normalizeResearchConflictSummary(value: unknown): ResearchConflictSummary | undefined {
  const data = readOptionalRecord(value)
  if (!data) {
    const conflicts = readRecordCollection(value)
    return conflicts.length > 0 ? { conflict_count: conflicts.length, conflicts } : undefined
  }
  const conflicts = readRecordCollection(data.conflicts ?? data.items ?? data.claim_conflicts)
  const conflictCount =
    readNumber(data.conflict_count) ||
    readNumber(data.conflicts_count) ||
    readNumber(data.total_conflicts) ||
    readNumber(data.contradiction_count) ||
    conflicts.length
  return {
    conflict_count: conflictCount,
    conflicts,
    details: data,
  }
}

export function normalizeResearchConflictGroups(value: unknown): ResearchConflictGroup[] {
  return readRecordCollection(value).map((item, index) => ({
    group_id: readString(item.group_id) || `conflict-group-${index + 1}`,
    normalized_claim: readString(item.normalized_claim),
    normalized_source: readString(item.normalized_source),
    normalized_conflict_text: readString(item.normalized_conflict_text),
    conflict_text: readString(item.conflict_text),
    claim_ids: readStringArray(item.claim_ids),
    source_ids: readStringArray(item.source_ids),
    review_statuses: readStringArray(item.review_statuses),
    total: readNumber(item.total),
    archives: readRecordCollection(item.archives),
  }))
}

export function normalizeResearchArchive(raw: unknown): ResearchArchive {
  const data = (raw ?? {}) as Record<string, unknown>
  const content = readOptionalRecord(data.content) ?? {}
  const previewClaims = Array.isArray(data.preview_claims) ? data.preview_claims : []
  const chains = normalizeClaimEvidenceChains(
    data.claim_evidence_chains ?? content.claim_evidence_chains ?? previewClaims,
  )
  const previewSources = Array.isArray(data.preview_sources)
    ? data.preview_sources
    : Array.isArray(data.sources)
      ? data.sources
      : []
  const paragraphCitations = readRecordCollection(
    readFirstField(data, content, [
      'paragraph_citations',
      'paragraphCitations',
      'paragraph_links',
      'paragraphLinks',
      'paragraph_citation_map',
      'paragraphCitationMap',
    ]),
  )
  const citationGraph = normalizeResearchCitationGraph(
    readFirstField(data, content, ['citation_graph', 'citationGraph', 'graph']),
  )
  const navigationIndex = normalizeResearchNavigationIndex(
    readFirstField(data, content, ['navigation_index', 'navigationIndex']),
  )
  const conflictSummary = normalizeResearchConflictSummary(
    readFirstField(data, content, ['conflict_summary', 'conflictSummary', 'conflicts']),
  )
  const sourceCount =
    readNumber(data.source_count) ||
    chains.reduce((total, chain) => total + (chain.sources.length || chain.supporting_source_count), 0) ||
    previewSources.length
  return {
    archive_id: readString(data.archive_id) || readString(data.artifact_id) || readString(data.id),
    title: readString(data.title) || 'Untitled research archive',
    session_id: readString(data.session_id) || undefined,
    task_id: readString(data.task_id) || undefined,
    artifact_id: readString(data.artifact_id) || undefined,
    claim_count: readNumber(data.claim_count) || chains.length,
    source_count: sourceCount,
    verification_summary: normalizeClaimVerificationSummary(
      data.verification_summary ?? data.claim_verification_summary ?? content.claim_verification_summary,
    ),
    claim_evidence_chains: chains,
    paragraph_citations: paragraphCitations,
    paragraph_claim_links: readRecordCollection(
      readFirstField(data, content, ['paragraph_claim_links', 'paragraphClaimLinks']),
    ),
    navigation_index: navigationIndex,
    citation_graph: citationGraph,
    conflict_summary: conflictSummary,
    conflict_review_resolutions: readRecordCollection(
      readFirstField(data, content, [
        'conflict_review_resolutions',
        'conflictReviewResolutions',
      ]),
    ),
    provider_capabilities: readOptionalRecord(
      readFirstField(data, content, ['provider_capabilities', 'providerCapabilities']),
    ),
    delivery_quality:
      typeof data.delivery_quality === 'object' && data.delivery_quality !== null
        ? (data.delivery_quality as Record<string, unknown>)
        : undefined,
    preview_claims: previewClaims.filter(
      (item): item is Record<string, unknown> => typeof item === 'object' && item !== null,
    ),
    preview_sources: previewSources.filter(
      (item): item is Record<string, unknown> => typeof item === 'object' && item !== null,
    ),
    created_at: readNumber(data.created_at) || undefined,
    updated_at: readNumber(data.updated_at) || undefined,
  }
}

export function normalizeArtifact(raw: unknown): ArtifactRecord {
  const data = (raw ?? {}) as Record<string, unknown>
  const artifactType = data.artifact_type === 'deck' ? 'deck' : 'report'
  const rawContent =
    typeof data.content === 'object' && data.content !== null
      ? (data.content as Record<string, unknown>)
      : {}

  const content =
    artifactType === 'deck'
      ? {
          deck_id: typeof rawContent.deck_id === 'string' ? rawContent.deck_id : '',
          theme: typeof rawContent.theme === 'string' ? rawContent.theme : 'default',
          slide_count:
            typeof rawContent.slide_count === 'number'
              ? rawContent.slide_count
              : Number(rawContent.slide_count ?? 0) || 0,
          answer_group_id:
            typeof rawContent.answer_group_id === 'string' ? rawContent.answer_group_id : null,
          panel_id: typeof rawContent.panel_id === 'string' ? rawContent.panel_id : null,
          evidence_coverage: normalizeDeckEvidenceCoverage(rawContent.evidence_coverage),
          evidence_review: normalizeDeckEvidenceReview(rawContent.evidence_review),
          citation_validation: normalizeDeckCitationValidation(rawContent.citation_validation),
        }
      : {
          markdown: typeof rawContent.markdown === 'string' ? rawContent.markdown : '',
          qa_pairs: Array.isArray(rawContent.qa_pairs)
            ? rawContent.qa_pairs
                .filter(
                  (item): item is Record<string, unknown> =>
                    typeof item === 'object' && item !== null,
                )
                .map((item) => ({
                  question: typeof item.question === 'string' ? item.question : '',
                  answer: typeof item.answer === 'string' ? item.answer : '',
                }))
            : [],
          answer_group_id:
            typeof rawContent.answer_group_id === 'string' ? rawContent.answer_group_id : null,
          panel_id: typeof rawContent.panel_id === 'string' ? rawContent.panel_id : null,
          claim_evidence_chains: normalizeClaimEvidenceChains(rawContent.claim_evidence_chains),
          claim_verification_summary: normalizeClaimVerificationSummary(
            rawContent.claim_verification_summary,
          ),
        }

  return {
    artifact_id: typeof data.artifact_id === 'string' ? data.artifact_id : '',
    session_id: typeof data.session_id === 'string' ? data.session_id : '',
    artifact_type: artifactType,
    title: typeof data.title === 'string' ? data.title : 'Untitled Artifact',
    status: typeof data.status === 'string' ? data.status : 'ready',
    linked_resource_type:
      typeof data.linked_resource_type === 'string' ? data.linked_resource_type : null,
    linked_resource_id:
      typeof data.linked_resource_id === 'string' ? data.linked_resource_id : null,
    content,
    available_formats: Array.isArray(data.available_formats)
      ? data.available_formats.filter(
          (item): item is ArtifactExportFormat =>
            item === 'md' || item === 'docx' || item === 'xlsx' || item === 'pptx',
        )
      : artifactType === 'report'
        ? ['md', 'docx', 'xlsx', 'pptx']
        : ['pptx'],
    created_at:
      typeof data.created_at === 'number' ? data.created_at : Number(data.created_at ?? 0) || 0,
    updated_at:
      typeof data.updated_at === 'number' ? data.updated_at : Number(data.updated_at ?? 0) || 0,
  }
}

export function normalizeMcpMarketplace(value: unknown): McpMarketplace | undefined {
  const data = readRecord(value)
  const rawSummary = readRecord(data.summary)
  const rawCategories = Array.isArray(data.categories) ? data.categories : []
  if (Object.keys(rawSummary).length === 0 && rawCategories.length === 0) return undefined
  return {
    summary: {
      total: readNumber(rawSummary.total),
      builtin: readNumber(rawSummary.builtin),
      custom: readNumber(rawSummary.custom),
      enabled: readNumber(rawSummary.enabled),
      healthy: readNumber(rawSummary.healthy),
      requires_approval: readNumber(rawSummary.requires_approval),
      categories: readNumber(rawSummary.categories),
    },
    categories: rawCategories
      .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
      .map((item) => ({
        id: readString(item.id),
        label: readString(item.label),
        total: readNumber(item.total),
        enabled: readNumber(item.enabled),
        healthy: readNumber(item.healthy),
        requires_approval: readNumber(item.requires_approval),
        connectors: readStringArray(item.connectors),
      })),
  }
}

export function normalizeMcpConfigPayload(data: Partial<McpConfigResponse>): McpConfigResponse {
  const persistence =
    typeof data.persistence === 'object' && data.persistence !== null
      ? data.persistence
      : { enabled: false, config_key: '' }
  const servers = readRecord(data.servers) as Record<string, Record<string, unknown>>
  const config = readRecord(data.config)
  const marketplace = normalizeMcpMarketplace(data.marketplace)
  return {
    connectors: Array.isArray(data.connectors) ? data.connectors : [],
    config: Object.keys(config).length > 0 ? config : { servers },
    servers,
    default_enabled: readStringArray(data.default_enabled),
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key) || readString(data.path),
    },
    sensitive_fields_redacted:
      data.sensitive_fields_redacted === true ||
      (readRecord(data.persistence).sensitive_fields_redacted === true),
    source: readString(data.source),
    path: readString(data.path),
    total: readNumber(data.total),
    marketplace,
  }
}

export function normalizeMcpApprovalsPayload(data: Partial<McpConnectorApprovalsResponse>): McpConnectorApprovalsResponse {
  const approved = readStringArray(data.approved_connectors)
  const env = readStringArray(data.env_connectors)
  const runtime = readStringArray(data.runtime_connectors)
  const persisted = readStringArray(data.persisted_connectors)
  const sources =
    typeof data.sources === 'object' && data.sources !== null
      ? Object.fromEntries(
          Object.entries(data.sources).map(([name, value]) => [name, readStringArray(value)]),
        )
      : {}
  const persistence =
    typeof data.persistence === 'object' && data.persistence !== null
      ? data.persistence
      : { enabled: false, config_key: '' }

  return {
    approved_connectors: approved,
    env_connectors: env,
    runtime_connectors: runtime,
    persisted_connectors: persisted,
    sources,
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key),
    },
    total: readNumber(data.total ?? approved.length),
    connector: data.connector,
  }
}

export function normalizeIntegratorConnector(value: unknown): IntegratorConnector {
  const record = readRecord(value)
  return {
    id: readString(record.id) || undefined,
    type: readString(record.type) || 'webhook',
    name: readString(record.name) || undefined,
    description: readString(record.description) || undefined,
    enabled: record.enabled !== false,
    approved: record.approved === true,
    settings: normalizeIntegratorSafeSettings(record.settings),
  }
}

export function normalizeIntegratorConnectorsResponse(
  data: Partial<IntegratorConnectorsResponse>,
): IntegratorConnectorsResponse {
  const connectors = Array.isArray(data.connectors)
    ? data.connectors.map((item) => normalizeIntegratorConnector(item))
    : []
  const persistence = readRecord(data.persistence)
  return {
    connectors,
    total: readNumber(data.total ?? connectors.length),
    supported_types: readStringArray(data.supported_types),
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key),
      sensitive_fields_redacted: persistence.sensitive_fields_redacted === true,
    },
  }
}

export function normalizeIntegratorConnectorTestResult(
  data: Partial<IntegratorConnectorTestResult>,
): IntegratorConnectorTestResult {
  const summary = readRecord(data.summary)
  return {
    ok: data.ok === true,
    status: readString(data.status) || 'unknown',
    dry_run: data.dry_run !== false,
    executed: data.executed === true,
    connector: normalizeIntegratorConnector(data.connector),
    checks: normalizeIntegratorConnectorChecks(data.checks),
    summary: {
      check_count: readNumber(summary.check_count),
      failed_count: readNumber(summary.failed_count),
      blocking_failure_count: readNumber(summary.blocking_failure_count),
      warning_count: readNumber(summary.warning_count),
    },
  }
}

export function normalizeIntegratorAuditEvent(value: unknown): IntegratorAuditEvent {
  const record = readRecord(value)
  const connector = readRecord(record.connector)
  const endpoint = readRecord(record.endpoint)
  const response = readRecord(record.response)
  const details = readRecord(record.details)
  return {
    timestamp: readNumber(record.timestamp),
    action: readString(record.action || record.event),
    result: readString(record.result || record.status),
    connector_id: readString(record.connector_id || connector.id),
    connector_type: readString(record.connector_type || connector.type),
    actor: readString(record.actor || record.user_id),
    request_id: readString(record.request_id || record.id),
    details: {
      ...details,
      connector_name: readString(connector.name || details.connector_name),
      endpoint_host: readString(endpoint.host || details.endpoint_host),
      endpoint_fingerprint: readString(endpoint.fingerprint || details.endpoint_fingerprint),
      status_code: readNumber(response.status_code || details.status_code),
    },
  }
}

export function normalizeIntegratorAuditEventsResponse(
  data: Partial<IntegratorAuditEventsResponse>,
): IntegratorAuditEventsResponse {
  const events = Array.isArray(data.events)
    ? data.events.map((item) => normalizeIntegratorAuditEvent(item))
    : []
  return {
    events,
    total: readNumber(data.total ?? events.length),
    limit: readNumber(data.limit ?? events.length),
  }
}

export function normalizeIntegratorConnectorChecks(value: unknown): IntegratorConnectorTestCheck[] {
  return Array.isArray(value)
    ? value.map((item) => {
        const check = readRecord(item)
        return {
          name: readString(check.name),
          ok: check.ok === true,
          severity: readString(check.severity),
          message: readString(check.message),
        }
      })
    : []
}

export function normalizeIntegratorCredentialsRotationResponse(
  data: Partial<IntegratorConnectorCredentialsRotationResponse>,
): IntegratorConnectorCredentialsRotationResponse {
  const summary = readRecord(data.summary)
  const rotatedFields = readStringArray(data.rotated_fields)
  const preservedFields = readStringArray(data.preserved_fields)
  return {
    ok: data.ok !== false,
    status: readString(data.status) || 'rotated',
    connector: normalizeIntegratorConnector(data.connector),
    rotated_fields: rotatedFields,
    preserved_fields: preservedFields,
    summary: {
      rotated_count: readNumber(summary.rotated_count ?? rotatedFields.length),
      preserved_count: readNumber(summary.preserved_count ?? preservedFields.length),
    },
  }
}

export function normalizeIntegratorConnectorProbeResponse(
  data: Partial<IntegratorConnectorProbeResponse>,
): IntegratorConnectorProbeResponse {
  const summary = readRecord(data.summary)
  const probe = readRecord(data.probe)
  const timeoutSeconds = probe.timeout_seconds === undefined
    ? undefined
    : readNumber(probe.timeout_seconds)
  return {
    ok: data.ok === true,
    status: readString(data.status) || 'unknown',
    dry_run: data.dry_run !== false,
    executed: data.executed === true,
    connector: normalizeIntegratorConnector(data.connector),
    checks: normalizeIntegratorConnectorChecks(data.checks),
    probe: {
      mode: readString(probe.mode) || readString(summary.probe_mode) || (data.dry_run === false ? 'external' : 'static'),
      outbound_request_sent: probe.outbound_request_sent === true,
      ...(timeoutSeconds !== undefined ? { timeout_seconds: timeoutSeconds } : {}),
      ...(Object.keys(readRecord(probe.endpoint)).length > 0 ? { endpoint: readRecord(probe.endpoint) } : {}),
      ...(Object.keys(readRecord(probe.response)).length > 0 ? { response: readRecord(probe.response) } : {}),
    },
    summary: {
      check_count: readNumber(summary.check_count),
      failed_count: readNumber(summary.failed_count),
      blocking_failure_count: readNumber(summary.blocking_failure_count),
      warning_count: readNumber(summary.warning_count),
      probe_mode: readString(summary.probe_mode) || undefined,
    },
  }
}

export function normalizeIntegratorSchedule(value: unknown): IntegratorSchedule {
  const record = readRecord(value)
  const rawLastRunAt = record.last_run_at
  const rawNextRunAt = record.next_run_at
    return {
      schedule_id: readString(record.schedule_id || record.id) || undefined,
      name: readString(record.name) || 'Integrator schedule',
      connector_id: readString(record.connector_id),
      cron: readString(record.cron || record.cron_expression) || '0 * * * *',
      timezone: readString(record.timezone) || 'UTC',
      interval_minutes: readNumber(record.interval_minutes) || 60,
      enabled: record.enabled !== false,
      settings: readRecord(record.settings),
      last_run_at: rawLastRunAt === null ? null : readNumber(rawLastRunAt),
      next_run_at: rawNextRunAt === null ? null : readNumber(rawNextRunAt),
    }
}

export function normalizeIntegratorSchedulesResponse(
  data: Partial<IntegratorSchedulesResponse>,
): IntegratorSchedulesResponse {
  const schedules = Array.isArray(data.schedules)
    ? data.schedules.map((item) => normalizeIntegratorSchedule(item))
    : []
  const persistence = readRecord(data.persistence)
  const scheduler = readRecord(data.scheduler)
  return {
    schedules,
    total: readNumber(data.total ?? schedules.length),
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key),
      sensitive_fields_redacted: persistence.sensitive_fields_redacted === true,
    },
    scheduler: {
      mode: readString(scheduler.mode) || 'unknown',
      automatic_dispatch: scheduler.automatic_dispatch === true,
      manual_trigger_supported: scheduler.manual_trigger_supported === true,
    },
  }
}

export function readRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}

export const INTEGRATOR_SENSITIVE_SETTING_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|key)/i

export const INTEGRATOR_REDACTED_VALUE = '***redacted***'

export function normalizeIntegratorSafeSettings(value: unknown): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(readRecord(value)).map(([key, item]) => {
      if (INTEGRATOR_SENSITIVE_SETTING_PATTERN.test(key)) {
        return [key, INTEGRATOR_REDACTED_VALUE]
      }
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        return [key, normalizeIntegratorSafeSettings(item)]
      }
      return [key, item]
    }),
  )
}

export function readNumberRecord(value: unknown): Record<string, number> {
  const record = readRecord(value)
  return Object.fromEntries(
    Object.entries(record).map(([key, item]) => [key, readNumber(item)]),
  )
}

export function normalizeMcpRuntimeHealthSummary(value: unknown): McpRuntimeHealthSummary {
  const summary = readRecord(value)
  return {
    total: readNumber(summary.total),
    healthy: readNumber(summary.healthy),
    unhealthy: readNumber(summary.unhealthy),
    tool_count: readNumber(summary.tool_count),
    status_counts: readNumberRecord(summary.status_counts),
    alert_count: readNumber(summary.alert_count),
    unhealthy_connectors: readStringArray(summary.unhealthy_connectors),
    slow_connectors: readStringArray(summary.slow_connectors),
  }
}

export function normalizeMcpRuntimeHealthHistoryServer(value: unknown): McpRuntimeHealthHistoryServer {
  const server = readRecord(value)
  return {
    name: readString(server.name),
    status: readString(server.status) || 'unknown',
    healthy: server.healthy === true,
    tool_count: readNumber(server.tool_count),
    duration_ms: readNumber(server.duration_ms),
    error: typeof server.error === 'string' && server.error.trim() ? server.error : null,
  }
}

export function normalizeMcpRuntimeHealthHistoryItem(value: unknown): McpRuntimeHealthHistoryItem {
  const item = readRecord(value)
  return {
    timestamp: readNumber(item.timestamp),
    status: readString(item.status) || 'unknown',
    summary: normalizeMcpRuntimeHealthSummary(item.summary),
    servers: Array.isArray(item.servers)
      ? item.servers.map(normalizeMcpRuntimeHealthHistoryServer)
      : [],
  }
}

export const normalizeRetrievalSourceText = (value: unknown): string =>
  String(value ?? '')
    .trim()
    .replace(/\s+/g, ' ')

export function normalizeSecurityStatusPayload(data: Partial<SecurityStatusResponse>): SecurityStatusResponse {
  return {
    allow_remote_clients: readBoolean(data.allow_remote_clients),
    local_only_mode: readBoolean(data.local_only_mode),
    remote_auth_ready: readBoolean(data.remote_auth_ready),
    admin_token_configured: readBoolean(data.admin_token_configured),
    remote_admin_ready: readBoolean(data.remote_admin_ready),
    auth_token_count: readNumber(data.auth_token_count),
    configured_roles: readStringArray(data.configured_roles),
    auth_token_hygiene_healthy: readBoolean(data.auth_token_hygiene_healthy),
    weak_auth_token_count: readNumber(data.weak_auth_token_count),
    legacy_auth_token_count: readNumber(data.legacy_auth_token_count),
    share_link_secret_healthy: readBoolean(data.share_link_secret_healthy),
    share_link_secret_uses_default: readBoolean(data.share_link_secret_uses_default),
    share_link_secret_min_length: readNumber(data.share_link_secret_min_length),
    remote_share_ready: readBoolean(data.remote_share_ready),
    remote_management_rate_limit_enabled: readBoolean(data.remote_management_rate_limit_enabled),
    remote_management_rate_limit_window_seconds: readNumber(data.remote_management_rate_limit_window_seconds),
    remote_management_rate_limit_window_seconds_source: readString(data.remote_management_rate_limit_window_seconds_source),
    remote_management_rate_limit_max_requests: readNumber(data.remote_management_rate_limit_max_requests),
    remote_management_rate_limit_max_requests_source: readString(data.remote_management_rate_limit_max_requests_source),
    remote_management_rate_limit_scope: readString(data.remote_management_rate_limit_scope),
    remote_management_rate_limit_storage: readString(data.remote_management_rate_limit_storage),
    remote_management_rate_limit_path_prefixes: readStringArray(data.remote_management_rate_limit_path_prefixes),
    remote_management_rate_limit_response_headers: readStringArray(data.remote_management_rate_limit_response_headers),
    remote_management_rate_limit_tracked_principal_count: readNumber(data.remote_management_rate_limit_tracked_principal_count),
    remote_management_rate_limit_active_request_count: readNumber(data.remote_management_rate_limit_active_request_count),
    remote_management_rate_limit_blocked_count: readNumber(data.remote_management_rate_limit_blocked_count),
    remote_management_rate_limit_last_blocked_at:
      data.remote_management_rate_limit_last_blocked_at == null
        ? null
        : readNumber(data.remote_management_rate_limit_last_blocked_at),
    remote_management_rate_limit_next_reset_after_seconds: readNumber(data.remote_management_rate_limit_next_reset_after_seconds),
    share_link_ttl_seconds: readNumber(data.share_link_ttl_seconds),
    share_link_ttl_hours: readNumber(data.share_link_ttl_hours),
    cors_allow_credentials: readBoolean(data.cors_allow_credentials),
    cors_allowed_origins: readStringArray(data.cors_allowed_origins),
    request_id_header: readString(data.request_id_header),
    process_time_header: readString(data.process_time_header),
    security_audit_storage: readString(data.security_audit_storage),
    security_audit_history_limit: readNumber(data.security_audit_history_limit),
    security_audit_history_limit_source: readString(data.security_audit_history_limit_source),
    security_audit_persisted_count: readNumber(data.security_audit_persisted_count),
    security_audit_memory_window_limit: readNumber(data.security_audit_memory_window_limit),
    chat_file_limits: readNumberRecord(data.chat_file_limits),
    document_upload_limits: readNumberRecord(data.document_upload_limits),
  }
}

export function normalizeSecurityAuditSummaryCategory(
  category: SecurityAuditSummaryCategory | string = 'all',
): SecurityAuditSummaryApiCategory | '' {
  if (
    category === 'access' ||
    category === 'identity' ||
    category === 'auth' ||
    category === 'audit'
  ) {
    return category
  }
  return ''
}

export function normalizeSecurityAuditSummaryPayload(
  data: Partial<SecurityAuditSummary> & { category?: unknown },
): SecurityAuditSummary {
  const category = normalizeSecurityAuditSummaryCategory(
    typeof data.category === 'string' ? data.category : 'all',
  )
  const categories = readStringArray(data.categories).filter(
    (item): item is SecurityAuditSummaryApiCategory =>
      item === 'access' || item === 'identity' || item === 'auth' || item === 'audit',
  )

  return {
    category,
    categories,
    total: readNumber(data.total),
    recent_count: readNumber(data.recent_count),
    window_limit: readNumber(data.window_limit),
    action_counts: readNumberRecord(data.action_counts),
    result_counts: readNumberRecord(data.result_counts),
    category_counts: readNumberRecord(data.category_counts),
    unknown_action_count: readNumber(data.unknown_action_count),
  }
}
