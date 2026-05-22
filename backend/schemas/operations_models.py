"""Pydantic contracts for operations, MCP, and Integrator API routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ConfigResponse(BaseModel):
    tavily_api_key_set: bool
    llm_provider: str = "ollama"
    ollama_model: str = ""
    ollama_base_url: str = ""
    openrouter_model: str = ""
    openrouter_base_url: str = ""


class SaveConfigResponse(BaseModel):
    ok: bool
    tavily_api_key_set: bool


class CloudModelApiKeyResponse(BaseModel):
    ok: bool
    api_key_ref: str
    api_key_set: bool = True


class DeleteCloudModelApiKeyResponse(BaseModel):
    ok: bool
    deleted: bool


class TraceEventResponse(BaseModel):
    event: Literal["start", "end", "error"]
    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    timestamp: float
    duration_ms: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None
    process_id: str | None = None
    source: str | None = None


class TraceSummaryResponse(BaseModel):
    returned: int
    limit: int
    error_events: int
    filters: dict[str, Any] = Field(default_factory=dict)
    source_nodes: dict[str, int] = Field(default_factory=dict)
    process_nodes: dict[str, int] = Field(default_factory=dict)
    otel_exporter: dict[str, Any] = Field(default_factory=dict)


class TraceDashboardCard(BaseModel):
    id: str
    title: str
    value: int | float | str
    unit: str = ""
    severity: str = "ok"


class TracePanelTemplate(BaseModel):
    id: str
    title: str
    kind: str
    source: str
    fields: list[str] = Field(default_factory=list)


class TraceExportPreviewResponse(BaseModel):
    service_name: str
    span_count: int
    log_record_count: int
    source_nodes: dict[str, int] = Field(default_factory=dict)
    process_nodes: dict[str, int] = Field(default_factory=dict)
    avg_duration_ms: float = 0
    sample_spans: list[dict[str, Any]] = Field(default_factory=list)


class TraceExportSummaryResponse(BaseModel):
    service_name: str
    event_count: int
    span_count: int
    log_record_count: int
    source_nodes: dict[str, int] = Field(default_factory=dict)
    process_nodes: dict[str, int] = Field(default_factory=dict)
    otel_exporter: dict[str, Any] = Field(default_factory=dict)


class TraceExportPayloadResponse(BaseModel):
    format: str
    resource_spans: list[dict[str, Any]] = Field(default_factory=list)
    resource_logs: list[dict[str, Any]] = Field(default_factory=list)
    summary: TraceExportSummaryResponse


class TraceEventsResponse(BaseModel):
    events: list[TraceEventResponse] = Field(default_factory=list)
    summary: TraceSummaryResponse
    export: TraceExportPayloadResponse | None = None
    export_preview: TraceExportPreviewResponse | None = None
    dashboard_cards: list[TraceDashboardCard] = Field(default_factory=list)
    panel_templates: list[TracePanelTemplate] = Field(default_factory=list)


class IngestTraceEventsResponse(BaseModel):
    ok: bool
    accepted: int
    rejected: int
    source: str
    process_id: str


class ObservabilityTraceSnapshot(BaseModel):
    summary: TraceSummaryResponse
    export_preview: TraceExportPreviewResponse


class ObservabilitySnapshotResponse(BaseModel):
    runtime: dict[str, Any] = Field(default_factory=dict)
    traces: ObservabilityTraceSnapshot
    metrics_aggregation: dict[str, Any] = Field(default_factory=dict)
    exporters: dict[str, Any] = Field(default_factory=dict)
    dashboard_cards: list[TraceDashboardCard] = Field(default_factory=list)
    panel_templates: list[TracePanelTemplate] = Field(default_factory=list)


class ClearTracesResponse(BaseModel):
    ok: bool
    cleared: bool


class McpConnectorConfigSchema(BaseModel):
    transport: str = "stdio"
    required: list[str] = Field(default_factory=list)
    optional: list[str] = Field(default_factory=list)
    sensitive: list[str] = Field(default_factory=list)


class McpConnectorPolicy(BaseModel):
    allowed: bool = False
    requires_approval: bool = False
    missing_scopes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    connector_approved: bool = False
    risk_level: str = "medium"
    capability_scopes: list[str] = Field(default_factory=list)


class McpConnector(BaseModel):
    name: str
    label: str = ""
    description: str = ""
    category: str = "custom"
    builtin: bool = False
    transport: str = "stdio"
    source: str = ""
    capability_scopes: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    requires_approval: bool = False
    enabled: bool = False
    configured: bool = False
    healthy: bool = False
    status: str = ""
    status_reasons: list[str] = Field(default_factory=list)
    policy: McpConnectorPolicy | None = None
    config_schema: McpConnectorConfigSchema | None = None
    template: bool | None = None


class McpConfigPersistence(BaseModel):
    enabled: bool = False
    config_key: str = ""
    sensitive_fields_redacted: bool = False


class McpMarketplaceSummary(BaseModel):
    total: int = 0
    builtin: int = 0
    custom: int = 0
    enabled: int = 0
    healthy: int = 0
    requires_approval: int = 0
    categories: int = 0


class McpMarketplaceCategory(BaseModel):
    id: str
    label: str = ""
    total: int = 0
    enabled: int = 0
    healthy: int = 0
    requires_approval: int = 0
    connectors: list[str] = Field(default_factory=list)


class McpMarketplace(BaseModel):
    summary: McpMarketplaceSummary = Field(default_factory=McpMarketplaceSummary)
    categories: list[McpMarketplaceCategory] = Field(default_factory=list)


class InstalledMcpConnectorSummary(BaseModel):
    name: str
    connector: McpConnector | None = None
    executed_install_command: bool = False


class McpConfigResponse(BaseModel):
    connectors: list[McpConnector] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    servers: dict[str, dict[str, Any]] = Field(default_factory=dict)
    default_enabled: list[str] = Field(default_factory=list)
    persistence: McpConfigPersistence = Field(default_factory=McpConfigPersistence)
    marketplace: McpMarketplace | None = None
    hot_update: dict[str, Any] = Field(default_factory=dict)
    sensitive_fields_redacted: bool = False
    source: str = ""
    path: str = ""
    total: int = 0
    installed: InstalledMcpConnectorSummary | None = None


class InstallMcpConnectorResponse(McpConfigResponse):
    installed: InstalledMcpConnectorSummary | None = None


class IntegratorPersistence(BaseModel):
    enabled: bool = False
    config_key: str = ""
    sensitive_fields_redacted: bool = False


class IntegratorConnector(BaseModel):
    id: str | None = None
    type: str
    name: str = ""
    description: str = ""
    enabled: bool = True
    approved: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)


class IntegratorConnectorsResponse(BaseModel):
    connectors: list[IntegratorConnector] = Field(default_factory=list)
    total: int = 0
    supported_types: list[str] = Field(default_factory=list)
    persistence: IntegratorPersistence = Field(default_factory=IntegratorPersistence)


class IntegratorConnectorTestCheck(BaseModel):
    name: str
    ok: bool
    severity: str
    message: str


class IntegratorConnectorTestSummary(BaseModel):
    check_count: int = 0
    failed_count: int = 0
    blocking_failure_count: int = 0
    warning_count: int = 0
    connector_id: str | None = None
    sensitive_fields_redacted: bool | None = None
    probe_mode: str | None = None


class IntegratorConnectorTestResult(BaseModel):
    ok: bool
    status: str
    dry_run: bool
    executed: bool
    connector: IntegratorConnector
    checks: list[IntegratorConnectorTestCheck] = Field(default_factory=list)
    summary: IntegratorConnectorTestSummary


class IntegratorConnectorCredentialsRotationSummary(BaseModel):
    connector_id: str = ""
    rotated_count: int = 0
    preserved_count: int = 0
    sensitive_fields_redacted: bool = True


class IntegratorConnectorCredentialsRotationResponse(BaseModel):
    ok: bool
    status: str
    connector: IntegratorConnector
    rotated_fields: list[str] = Field(default_factory=list)
    preserved_fields: list[str] = Field(default_factory=list)
    summary: IntegratorConnectorCredentialsRotationSummary


class IntegratorConnectorProbeDetails(BaseModel):
    mode: str
    outbound_request_sent: bool
    timeout_seconds: float | None = None
    target_policy: dict[str, Any] | None = None
    endpoint: dict[str, Any] | None = None
    response: dict[str, Any] | None = None
    retry: dict[str, Any] | None = None
    signing: dict[str, Any] | None = None


class IntegratorConnectorProbeResponse(BaseModel):
    ok: bool
    status: str
    dry_run: bool
    executed: bool
    connector: IntegratorConnector
    checks: list[IntegratorConnectorTestCheck] = Field(default_factory=list)
    probe: IntegratorConnectorProbeDetails
    summary: IntegratorConnectorTestSummary


class IntegratorSchedulerStatus(BaseModel):
    mode: str = "configured"
    automatic_dispatch: bool = False
    manual_trigger_supported: bool = True
    interval_seconds: int | None = None


class IntegratorSchedule(BaseModel):
    id: str | None = None
    schedule_id: str | None = None
    name: str
    description: str = ""
    connector_id: str
    action: str = "sync"
    cron: str = ""
    timezone: str = "UTC"
    interval_minutes: int
    enabled: bool = True
    payload: dict[str, Any] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    last_triggered_at: float | None = None
    last_run_at: float | None = None
    next_run_at: float | None = None
    trigger_count: int = 0


class IntegratorSchedulesResponse(BaseModel):
    schedules: list[IntegratorSchedule] = Field(default_factory=list)
    total: int = 0
    persistence: IntegratorPersistence = Field(default_factory=IntegratorPersistence)
    scheduler: IntegratorSchedulerStatus = Field(default_factory=IntegratorSchedulerStatus)


class IntegratorScheduleTaskSpec(BaseModel):
    task_type: str
    params: dict[str, Any] = Field(default_factory=dict)


class IntegratorScheduleTriggerResponse(BaseModel):
    ok: bool
    status: str
    schedule_id: str
    triggered_at: float
    dry_run: bool = True
    executed: bool = False
    schedule: IntegratorSchedule | None = None
    would_create_task: IntegratorScheduleTaskSpec | None = None
    task: dict[str, Any] | None = None
    message: str = ""


class IntegratorScheduleTickSkipped(BaseModel):
    disabled: int = 0
    not_due: int = 0


class IntegratorScheduleTickResponse(BaseModel):
    ok: bool = True
    status: str = "ok"
    dry_run: bool
    executed: bool
    checked: int
    due_count: int
    due: list[dict[str, Any]] = Field(default_factory=list)
    skipped: IntegratorScheduleTickSkipped
    now: float | None = None
    skipped_reason: str | None = None


class IntegratorOutboundAuditRetention(BaseModel):
    history_limit: int = 0
    sensitive_fields_redacted: bool = True


class IntegratorOutboundAuditResponse(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    limit: int = 0
    retention: IntegratorOutboundAuditRetention | None = None


class IntegratorOutboundAuditCleanupResponse(BaseModel):
    dry_run: bool
    would_delete_count: int
    deleted_count: int
    remaining_count: int
    keep_latest: int
    history_limit: int
