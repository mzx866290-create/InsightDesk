"""Pydantic request/response schemas for InsightDesk API routes."""

from typing import Any, Literal, Optional

from backend.agent_mcp_helpers import default_mcp_server_names
from backend.deck_service import DeckSlide
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    panel_id: str
    connection_type: Optional[str] = None
    provider: str = "ollama"
    model: str = "qwen3.5-2B:latest"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    api_key_ref: str = ""
    temperature: float = 0.3
    agent_mode: str = "auto"


class ProviderCatalogItem(BaseModel):
    id: str
    connection_type: str
    aliases: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    default_base_url: str = ""
    default_model: str = ""
    base_url_env_keys: list[str] = Field(default_factory=list)
    model_env_keys: list[str] = Field(default_factory=list)


class ProviderCatalogResponse(BaseModel):
    providers: list[ProviderCatalogItem]
    default_provider: str = "ollama"
    total: int = 0


class AgentCatalogItem(BaseModel):
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentCatalogSummary(BaseModel):
    total: int = 0
    builtin: int = 0
    plugin: int = 0


class AgentPluginManifestIssue(BaseModel):
    file: str = ""
    code: str = ""
    message: str = ""


class AgentPluginManifestStatus(BaseModel):
    enabled: bool = True
    directory_count: int = 0
    scanned_count: int = 0
    loaded_count: int = 0
    issue_count: int = 0
    issues: list[AgentPluginManifestIssue] = Field(default_factory=list)


class AgentPluginMarketplaceTemplate(BaseModel):
    name: str
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    category: str = ""
    risk_level: str = "medium"
    requires_approval: bool = False
    approval_reason: str = ""
    source: str = "builtin"
    installed: bool = False
    template: bool = True
    manifest: dict[str, Any] = Field(default_factory=dict)


class AgentPluginMarketplaceSummary(BaseModel):
    total: int = 0
    installed: int = 0
    available: int = 0
    categories: int = 0
    issue_count: int = 0


class AgentPluginMarketplaceResponse(BaseModel):
    templates: list[AgentPluginMarketplaceTemplate] = Field(default_factory=list)
    summary: AgentPluginMarketplaceSummary = Field(
        default_factory=AgentPluginMarketplaceSummary
    )
    issues: list[AgentPluginManifestIssue] = Field(default_factory=list)


class InstalledAgentPluginSummary(BaseModel):
    name: str = ""
    agent: Optional[AgentCatalogItem] = None
    manifest_path: str = ""
    executed_entrypoint: bool = False


class UninstalledAgentPluginSummary(BaseModel):
    name: str = ""
    manifest_path: str = ""
    deleted_manifest: bool = False
    existed: bool = False


class AgentCatalogResponse(BaseModel):
    agents: list[AgentCatalogItem] = Field(default_factory=list)
    summary: AgentCatalogSummary = Field(default_factory=AgentCatalogSummary)
    plugin_manifests: AgentPluginManifestStatus = Field(
        default_factory=AgentPluginManifestStatus
    )
    marketplace: AgentPluginMarketplaceResponse = Field(
        default_factory=AgentPluginMarketplaceResponse
    )
    installed: Optional[InstalledAgentPluginSummary] = None
    uninstalled: Optional[UninstalledAgentPluginSummary] = None


class DeliveryTemplateItem(BaseModel):
    id: str
    name: str
    description: str = ""
    artifact_type: Literal["report", "deck"]
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    target_format: str = ""
    preview: str = ""
    suggested_options: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeliveryTemplateSummary(BaseModel):
    total: int = 0
    builtin: int = 0
    manifest: int = 0
    report: int = 0
    deck: int = 0


class DeliveryTemplateManifestIssue(BaseModel):
    file: str = ""
    code: str = ""
    message: str = ""


class DeliveryTemplateManifestStatus(BaseModel):
    enabled: bool = True
    directory_count: int = 0
    scanned_count: int = 0
    loaded_count: int = 0
    issue_count: int = 0
    issues: list[DeliveryTemplateManifestIssue] = Field(default_factory=list)


class InstalledDeliveryTemplateSummary(BaseModel):
    id: str = ""
    template: Optional[DeliveryTemplateItem] = None
    manifest_path: str = ""
    executed_template_code: bool = False


class UninstalledDeliveryTemplateSummary(BaseModel):
    id: str = ""
    manifest_path: str = ""
    deleted_manifest: bool = False
    existed: bool = False


class DeliveryTemplateCatalogResponse(BaseModel):
    templates: list[DeliveryTemplateItem] = Field(default_factory=list)
    summary: DeliveryTemplateSummary = Field(default_factory=DeliveryTemplateSummary)
    manifests: DeliveryTemplateManifestStatus = Field(
        default_factory=DeliveryTemplateManifestStatus
    )
    installed: Optional[InstalledDeliveryTemplateSummary] = None
    uninstalled: Optional[UninstalledDeliveryTemplateSummary] = None


class AssistantPresetToolConfig(BaseModel):
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    mcp_servers_enabled: list[str] = Field(default_factory=list)


class AssistantPresetRequest(BaseModel):
    name: str
    avatar: str = ""
    system_prompt_id: str = ""
    default_model_config: ModelConfig = Field(default_factory=ModelConfig)
    tool_config: AssistantPresetToolConfig = Field(
        default_factory=AssistantPresetToolConfig
    )
    starters: list[str] = Field(default_factory=list)


class AssistantPresetResponse(BaseModel):
    id: str
    name: str
    avatar: str = ""
    system_prompt_id: str = ""
    default_model_config: ModelConfig = Field(default_factory=ModelConfig)
    tool_config: AssistantPresetToolConfig = Field(
        default_factory=AssistantPresetToolConfig
    )
    starters: list[str] = Field(default_factory=list)
    is_default: bool = False
    is_active: bool = False
    created_at: float = 0
    updated_at: float = 0


class AssistantPresetListResponse(BaseModel):
    presets: list[AssistantPresetResponse]


class ImageInput(BaseModel):
    name: str
    media_type: str
    data_url: str


class FileInput(BaseModel):
    name: str
    media_type: str
    data_url: str
    size_bytes: int = 0
    extracted_text: str = ""


class ChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)
    models: list[ModelConfig]
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    enabled_mcp_servers: list[str] = Field(default_factory=list)
    answer_group_id: Optional[str] = None
    omit_history: bool = False


class SingleChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)
    panel_config: ModelConfig
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    enabled_mcp_servers: list[str] = Field(default_factory=list)
    answer_group_id: Optional[str] = None
    persist_user_history: bool = True
    persist_ai_history: bool = True
    replace_ai_history: bool = False
    exclude_ai_answer_group_id: Optional[str] = None
    omit_history: bool = False


class CreateSessionRequest(BaseModel):
    title: str = ""
    workspace_id: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None
    is_favorite: Optional[bool] = None
    is_pinned: Optional[bool] = None
    tags: Optional[list[str]] = None
    workspace_id: Optional[str] = None


class ReorderSessionsRequest(BaseModel):
    session_ids: list[str]
    workspace_id: Optional[str] = None


class CreateBookmarkRequest(BaseModel):
    session_id: str
    role: str
    message_id: Optional[int] = None
    panel_id: str = ""
    answer_group_id: str = ""
    content: str = ""
    model_id: str = ""
    session_title: str = ""


class ShareLinkResponse(BaseModel):
    resource_type: str
    resource_id: str
    share_token: str
    share_url: str
    expires_at: float


class RevokeShareLinkResponse(BaseModel):
    ok: bool


class ShareLinkAuditRecord(BaseModel):
    resource_type: str
    resource_id: str
    created_at: float
    expires_at: float
    revoked_at: Optional[float] = None
    is_active: bool
    created_by_ip: str = ""
    created_user_agent: str = ""
    access_count: int = 0
    last_accessed_at: Optional[float] = None
    last_accessed_ip: str = ""
    last_accessed_user_agent: str = ""
    share_token_preview: str
    share_token_fingerprint: str


class ShareLinkAuditListResponse(BaseModel):
    share_links: list[ShareLinkAuditRecord]
    total: int
    active_count: int


class SecurityStatusResponse(BaseModel):
    allow_remote_clients: bool
    local_only_mode: bool
    remote_auth_ready: bool
    admin_token_configured: bool
    remote_admin_ready: bool
    auth_token_count: int
    configured_roles: list[str]
    auth_token_hygiene_healthy: bool
    weak_auth_token_count: int
    legacy_auth_token_count: int
    share_link_secret_healthy: bool
    share_link_secret_uses_default: bool
    share_link_secret_min_length: int
    remote_share_ready: bool
    remote_management_rate_limit_enabled: bool
    remote_management_rate_limit_window_seconds: int
    remote_management_rate_limit_window_seconds_source: str
    remote_management_rate_limit_max_requests: int
    remote_management_rate_limit_max_requests_source: str
    remote_management_rate_limit_scope: str
    remote_management_rate_limit_storage: str
    remote_management_rate_limit_path_prefixes: list[str]
    remote_management_rate_limit_response_headers: list[str]
    remote_management_rate_limit_tracked_principal_count: int
    remote_management_rate_limit_active_request_count: int
    remote_management_rate_limit_blocked_count: int
    remote_management_rate_limit_last_blocked_at: float | None = None
    remote_management_rate_limit_next_reset_after_seconds: int
    share_link_ttl_seconds: int
    share_link_ttl_hours: float
    cors_allow_credentials: bool
    cors_allowed_origins: list[str]
    request_id_header: str
    process_time_header: str
    security_audit_storage: str
    security_audit_history_limit: int
    security_audit_history_limit_source: str
    security_audit_persisted_count: int
    security_audit_memory_window_limit: int
    chat_file_limits: dict[str, int]
    document_upload_limits: dict[str, int]


class AuthWhoAmIResponse(BaseModel):
    user_id: str
    role: str
    auth_mode: str
    auth_source: str
    is_local: bool
    capabilities: list[str]


class AuthTokenCatalogRecord(BaseModel):
    user_id: str
    role: str
    auth_source: str
    token_preview: str
    token_fingerprint: str
    is_legacy: bool
    is_weak: bool


class AuthTokenCatalogResponse(BaseModel):
    tokens: list[AuthTokenCatalogRecord]
    total: int
    configured_roles: list[str]
    healthy: bool
    weak_count: int
    legacy_count: int


class SsoConfigResponse(BaseModel):
    enabled: bool
    provider: str
    issuer_url: str
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    jwks_url: str = ""
    authorization_endpoint_configured: bool = False
    token_endpoint_configured: bool = False
    jwks_url_configured: bool = False
    client_id: str = ""
    client_id_configured: bool
    client_secret_configured: bool
    allowed_domains: list[str]
    scopes: list[str] = Field(default_factory=list)
    default_role: str = "viewer"
    session_ttl_seconds: int = 28800
    callback_path: str
    ready: bool
    mode: str
    claim_mapping: dict[str, str]


class SsoLoginResponse(BaseModel):
    authorization_url: str
    state: str
    nonce: str
    code_challenge_method: str
    redirect_uri: str
    scopes: list[str]


class SecurityAuditEventRecord(BaseModel):
    timestamp: float
    request_id: str
    action: str
    result: str
    ip: str
    is_local: bool
    auth_mode: str
    auth_source: str
    user_id: str
    user_role: str
    details: str
    tenant_id: str = ""
    org_id: str = ""
    legal_hold: bool = False


class SecurityAuditEventFilters(BaseModel):
    action: str = ""
    result: str = ""
    category: str = ""
    user_id: str = ""
    since: float | None = None
    until: float | None = None


class SecurityAuditEventListResponse(BaseModel):
    events: list[SecurityAuditEventRecord]
    total: int
    limit: int
    filters: SecurityAuditEventFilters = Field(
        default_factory=SecurityAuditEventFilters
    )


class SecurityAuditCleanupResponse(BaseModel):
    dry_run: bool = False
    would_delete_count: int = 0
    deleted_count: int
    remaining_count: int
    memory_deleted_count: int
    memory_remaining_count: int
    keep_latest: int
    history_limit: int
    includes_cleanup_event: bool


class SecurityAuditActionRecord(BaseModel):
    action: str
    category: str
    minimum_reader_role: str
    description: str


class SecurityAuditActionCatalogResponse(BaseModel):
    actions: list[SecurityAuditActionRecord]
    total: int
    categories: list[str]


class SecurityAuditSummaryResponse(BaseModel):
    category: str = ""
    categories: list[str]
    total: int
    recent_count: int
    window_limit: int
    action_counts: dict[str, int]
    result_counts: dict[str, int]
    category_counts: dict[str, int]
    unknown_action_count: int


class SecurityAuditSiemExportResponse(BaseModel):
    format: Literal["json", "ndjson"]
    content_type: str
    total: int
    limit: int
    events: list[dict[str, Any]] = Field(default_factory=list)
    content: str = ""
    filters: SecurityAuditEventFilters = Field(
        default_factory=SecurityAuditEventFilters
    )


class SecurityAuditAggregateRow(BaseModel):
    tenant: str
    org: str
    user_id: str
    category: str
    action: str
    result: str
    count: int


class SecurityAuditAggregateReportResponse(BaseModel):
    total: int
    window_limit: int
    group_by: list[str]
    rows: list[SecurityAuditAggregateRow]
    totals: dict[str, dict[str, int]]
    filters: SecurityAuditEventFilters = Field(
        default_factory=SecurityAuditEventFilters
    )


class SecurityAuditArchivePolicyResponse(BaseModel):
    mode: Literal["preview", "export"]
    retention_days: int
    cutoff_timestamp: float | None = None
    history_limit: int
    total: int
    archive_candidate_count: int
    export_count: int
    legal_hold_count: int
    legal_hold_preserved_count: int
    cleanup_behavior: dict[str, Any]
    events: list[dict[str, Any]] = Field(default_factory=list)


class SecurityAuditLegalHoldResponse(BaseModel):
    request_id: str
    legal_hold: bool
    updated_count: int


class RuntimeRequestMetricsResponse(BaseModel):
    total_requests: int
    total_errors: int
    by_status_class: dict[str, int]
    last_request_at: float | None = None
    last_error_at: float | None = None


class RuntimeRecentErrorResponse(BaseModel):
    timestamp: float
    request_id: str
    path: str
    method: str
    status_code: int
    error_code: str
    message: str


class RuntimeTaskSummaryResponse(BaseModel):
    in_memory_total: int
    pending: int
    running: int
    completed: int
    failed: int
    latest_task_updated_at: float | None = None


class RuntimeOperationsAlertResponse(BaseModel):
    severity: str
    code: str
    message: str
    value: float | int | None = None


class RuntimeOperationsSummaryResponse(BaseModel):
    health_status: str
    error_rate: float
    requests_per_minute: float
    active_tasks: int
    llm_error_rate: float
    alert_count: int
    alerts: list[RuntimeOperationsAlertResponse]


class RuntimeOperationsResponse(BaseModel):
    started_at: float
    uptime_seconds: float
    request_metrics: RuntimeRequestMetricsResponse
    recent_errors: list[RuntimeRecentErrorResponse]
    task_summary: RuntimeTaskSummaryResponse
    operations_summary: RuntimeOperationsSummaryResponse
    security: dict[str, Any]


class WorkspaceToolConfigRequest(BaseModel):
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True
    mcp_servers_enabled: list[str] = Field(default_factory=default_mcp_server_names)


class WorkspaceOutputPresetRequest(BaseModel):
    deck_theme: Literal["default", "midnight", "sunrise"] = "default"
    target_slide_count: int = Field(default=8, ge=4, le=10)


class WorkspacePresetRequest(BaseModel):
    default_panels: list[ModelConfig] = Field(default_factory=list)
    tool_config: WorkspaceToolConfigRequest = Field(
        default_factory=WorkspaceToolConfigRequest
    )
    output_preset: WorkspaceOutputPresetRequest = Field(
        default_factory=WorkspaceOutputPresetRequest
    )


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str = ""
    color: str = "blue"
    activate: bool = True
    preset: Optional[WorkspacePresetRequest] = None


class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    preset: Optional[WorkspacePresetRequest] = None


class SetMessageFeedbackRequest(BaseModel):
    value: int
    message_id: Optional[int] = None
    panel_id: str = ""
    answer_group_id: str = ""


class TruncateSessionMessagesRequest(BaseModel):
    answer_group_id: str
    content: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)


class ImportedFileInput(BaseModel):
    name: str
    media_type: str
    data_url: str = ""
    size_bytes: int = 0
    extracted_text: str = ""


class ImportSessionMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[ImportedFileInput] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    model_id: str = ""
    panel_id: str = ""
    answer_group_id: str = ""
    workflow_nodes: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, Any] = Field(default_factory=dict)
    task_id: str = ""
    task_type: str = ""


class ImportSessionMessagesRequest(BaseModel):
    panels: list[ModelConfig] = Field(default_factory=list)
    messages: list[ImportSessionMessageRequest] = Field(default_factory=list)


class SetRetrievalFeedbackRequest(BaseModel):
    panel_id: str
    answer_group_id: str
    source: dict[str, Any]
    value: int


class PinSessionMemoryRequest(BaseModel):
    content: str
    kind: str = Field(default="fact")


class UpdateSessionMemoryRequest(BaseModel):
    content: Optional[str] = None
    kind: Optional[str] = None


class GenerateReportRequest(BaseModel):
    session_id: str
    answer_group_id: Optional[str] = None
    panel_id: Optional[str] = None
    template_id: str = ""
    template_options: dict[str, Any] = Field(default_factory=dict)


class CreateDeckRequest(BaseModel):
    session_id: str
    panel_config: ModelConfig
    knowledge_base_enabled: bool = True
    target_slide_count: int = Field(default=8, ge=4, le=10)
    theme: str = "default"
    answer_group_id: Optional[str] = None
    panel_id: Optional[str] = None
    template_id: str = ""
    template_options: dict[str, Any] = Field(default_factory=dict)


class GenerateArtifactRequest(BaseModel):
    artifact_type: Literal["report", "deck"]
    session_id: str
    answer_group_id: Optional[str] = None
    panel_id: Optional[str] = None
    panel_config: Optional[ModelConfig] = None
    knowledge_base_enabled: bool = True
    target_slide_count: int = Field(default=8, ge=4, le=10)
    theme: str = "default"
    template_id: str = ""
    template_options: dict[str, Any] = Field(default_factory=dict)


class UpdateArtifactRequest(BaseModel):
    title: Optional[str] = None
    markdown: Optional[str] = None


class UpdateDeckRequest(BaseModel):
    title: Optional[str] = None
    theme: Optional[str] = None
    slides: Optional[list[DeckSlide]] = None


class RegenerateDeckSlideRequest(BaseModel):
    panel_config: ModelConfig
    knowledge_base_enabled: Optional[bool] = None


class UpsertResourceGrantRequest(BaseModel):
    resource_type: str
    resource_id: str
    role: Literal["viewer", "editor", "admin", "owner"] = "viewer"
    org_id: str = ""
    user_id: str = ""


class DeleteResourceGrantRequest(BaseModel):
    resource_type: str
    resource_id: str
    org_id: str = ""
    user_id: str = ""


class ResourceGrantResponse(BaseModel):
    resource_type: str
    resource_id: str
    org_id: str = ""
    user_id: str = ""
    role: str
    created_at: float
    updated_at: float


class ResourceGrantListResponse(BaseModel):
    grants: list[ResourceGrantResponse]
    total: int
    limit: int = 100
    offset: int = 0
    returned: int = 0


class ResourceAccessResponse(BaseModel):
    resource_type: str
    resource_id: str
    user_id: str
    role: str = ""
    allowed: bool
    source: str = "none"


class RolePermissionMatrixEntry(BaseModel):
    operation: str
    minimum_role: str
    roles: dict[str, bool]
    description: str


class RolePermissionMatrixResponse(BaseModel):
    roles: list[str]
    operations: list[RolePermissionMatrixEntry]
    role_ranks: dict[str, int]
    inheritance_rule: str


class CreateTaskRequest(BaseModel):
    task_type: str  # e.g. "analyze_knowledge_base", "generate_report"
    params: dict = {}
    session_id: Optional[str] = None


class CreateMultiAgentWorkflowTaskRequest(BaseModel):
    user_request: str
    session_id: Optional[str] = None
    panel_id: str = ""
    answer_group_id: str = ""
    model_id: str = "multi_agent_workflow"
    context: dict[str, Any] = Field(default_factory=dict)
    data_files: list[FileInput] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    panel_config: ModelConfig | dict[str, Any] | None = None
    research_mode: Literal["quick", "deep"] = "deep"
    providers: list[str] = Field(default_factory=list)
    max_rounds: int = 2
    max_results_per_query: int = 4
    max_fetch_pages: int = 3
    time_range: str = ""
    use_kb_context: bool = False
    vector_store_path: Optional[str] = None
    allow_quick_fallback: bool = True


class ApprovalTaskDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reviewer: str = ""
    comment: str = ""


class ApprovalTaskBatchDecisionRequest(BaseModel):
    task_ids: list[str] = Field(default_factory=list)
    decision: Literal["approved", "rejected"]
    reviewer: str = ""
    comment: str = ""


class ApprovalPolicyRequest(BaseModel):
    enabled: bool = False
    required_task_types: list[str] = Field(default_factory=list)
    high_risk_requires_approval: bool = True
    default_reviewer_role: str = "admin"
    updated_at: float | None = None


class UpsertOrganizationRequest(BaseModel):
    org_id: str
    name: str
    description: str = ""


class UpsertUserRequest(BaseModel):
    user_id: str
    display_name: str = ""
    email: str = ""


class SetMembershipRequest(BaseModel):
    org_id: str
    user_id: str
    role: Literal["viewer", "editor", "admin", "owner"] = "viewer"


class SyncExternalIdentityRequest(BaseModel):
    claims: dict[str, Any]
    provider: str = "oidc"
    default_org_id: str = ""
    default_role: Literal["viewer", "editor", "admin", "owner"] = "viewer"
    group_org_map: dict[str, str] = Field(default_factory=dict)
    group_role_map: dict[str, Literal["viewer", "editor", "admin", "owner"]] = Field(
        default_factory=dict
    )
    allowed_domains: list[str] = Field(default_factory=list)


class OrganizationResponse(BaseModel):
    org_id: str
    name: str
    description: str = ""
    created_at: float
    updated_at: float


class UserResponse(BaseModel):
    user_id: str
    display_name: str
    email: str = ""
    created_at: float
    updated_at: float


class MembershipResponse(BaseModel):
    org_id: str
    user_id: str
    role: str
    created_at: float
    updated_at: float


class IdentityCatalogResponse(BaseModel):
    organizations: list[OrganizationResponse]
    users: list[UserResponse]
    memberships: list[MembershipResponse]


class ExternalIdentitySummaryResponse(BaseModel):
    provider: str
    external_subject: str
    groups: list[str]


class SyncExternalIdentityResponse(BaseModel):
    user: UserResponse
    memberships: list[MembershipResponse]
    external: ExternalIdentitySummaryResponse


class SsoCallbackResponse(SyncExternalIdentityResponse):
    auth_source: str
    token_type: str = ""
    expires_in: int | None = None
    app_session_token: str
    app_session_expires_at: float
    role: str
