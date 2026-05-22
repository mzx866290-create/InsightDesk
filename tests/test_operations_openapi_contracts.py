from __future__ import annotations

from backend.api_server import app


def _response_schema_name(openapi_schema: dict, path: str, method: str) -> str:
    response_schema = openapi_schema["paths"][path][method]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    ref = str(response_schema.get("$ref") or "")
    assert ref.startswith("#/components/schemas/")
    return ref.rsplit("/", 1)[-1]


def test_operations_routes_publish_named_response_models() -> None:
    app.openapi_schema = None
    openapi_schema = app.openapi()

    expected_response_models = {
        ("/api/operations/traces", "get"): "TraceEventsResponse",
        ("/api/operations/traces/ingest", "post"): "IngestTraceEventsResponse",
        ("/api/operations/observability", "get"): "ObservabilitySnapshotResponse",
        ("/api/operations/traces", "delete"): "ClearTracesResponse",
        ("/api/config", "get"): "ConfigResponse",
        ("/api/config", "post"): "SaveConfigResponse",
        ("/api/config/cloud-model-api-key", "post"): "CloudModelApiKeyResponse",
        (
            "/api/config/cloud-model-api-key/{api_key_ref}",
            "delete",
        ): "DeleteCloudModelApiKeyResponse",
        ("/api/connectors/mcp/config", "get"): "McpConfigResponse",
        ("/api/connectors/mcp/config", "put"): "McpConfigResponse",
        (
            "/api/connectors/mcp/marketplace/install",
            "post",
        ): "InstallMcpConnectorResponse",
        ("/api/integrations/connectors", "get"): "IntegratorConnectorsResponse",
        ("/api/integrations/connectors", "put"): "IntegratorConnectorsResponse",
        (
            "/api/integrations/connectors/test",
            "post",
        ): "IntegratorConnectorTestResult",
        (
            "/api/integrations/connectors/{connector_id}/credentials/rotate",
            "post",
        ): "IntegratorConnectorCredentialsRotationResponse",
        (
            "/api/integrations/connectors/{connector_id}/probe",
            "post",
        ): "IntegratorConnectorProbeResponse",
        ("/api/integrations/schedules", "get"): "IntegratorSchedulesResponse",
        ("/api/integrations/schedules", "put"): "IntegratorSchedulesResponse",
        (
            "/api/integrations/schedules/tick",
            "post",
        ): "IntegratorScheduleTickResponse",
        (
            "/api/integrations/schedules/{schedule_id}/trigger",
            "post",
        ): "IntegratorScheduleTriggerResponse",
        ("/api/integrations/audit", "get"): "IntegratorOutboundAuditResponse",
        ("/api/integrations/outbound-audit", "get"): "IntegratorOutboundAuditResponse",
        (
            "/api/integrations/outbound-audit/cleanup",
            "post",
        ): "IntegratorOutboundAuditCleanupResponse",
    }

    for (path, method), schema_name in expected_response_models.items():
        assert _response_schema_name(openapi_schema, path, method) == schema_name
