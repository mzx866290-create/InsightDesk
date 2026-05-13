import importlib

import backend.agent_core as legacy_agent_core
import backend.agent as split_agent
import backend.agent.builder as split_agent_builder
import backend.agent.builder_context as split_agent_builder_context
import backend.agent.builder_history as split_agent_builder_history
import backend.agent.builder_streaming as split_agent_builder_streaming
import backend.agent.connection as split_agent_connection
import backend.agent.dashboard as split_agent_dashboard
import backend.agent.dashboard_attachments as split_agent_dashboard_attachments
import backend.agent.dashboard_payload as split_agent_dashboard_payload
import backend.agent.executor as split_agent_executor
import backend.agent.fallbacks as split_agent_fallbacks
import backend.agent.history as split_agent_history
import backend.agent.llm as split_agent_llm
import backend.agent.prompts as split_agent_prompts
import backend.agent.retrieval as split_agent_retrieval
import backend.agent.runtime_intent as split_agent_runtime_intent
import backend.agent.runtime_plain_chat as split_agent_runtime_plain_chat
import backend.agent.runtime_support as split_agent_runtime_support
import backend.agent.sources as split_agent_sources
import backend.agent.tool_registry as split_agent_tool_registry
import backend.agent.tools as split_agent_tools
import backend.artifact_service as legacy_artifact_service
import backend.api_agent_stream_helpers as legacy_agent_stream_helpers
import backend.api_attachment_route_helpers as legacy_attachment_route_helpers
import backend.api_chat_file_helpers as legacy_chat_file_helpers
import backend.api_chat_input_helpers as legacy_chat_input_helpers
import backend.api_chat_route_helpers as legacy_chat_route_helpers
import backend.api_chat_routes as legacy_chat_routes
import backend.api_chat_stream_helpers as legacy_chat_stream_helpers
import backend.api_config_store as legacy_config_store
import backend.api_deck_report_helpers as legacy_deck_report_helpers
import backend.api_document_helpers as legacy_document_helpers
import backend.api_artifact_helpers as legacy_artifact_helpers
import backend.api_env_config_helpers as legacy_env_config_helpers
import backend.api_content_routes as legacy_content_routes
import backend.api_http_runtime_helpers as legacy_http_runtime_helpers
import backend.api_misc_helpers as legacy_misc_helpers
import backend.api_kb_helpers as legacy_kb_helpers
import backend.api_kb_chunk_route_helpers as legacy_kb_chunk_route_helpers
import backend.api_kb_delete_helpers as legacy_kb_delete_helpers
import backend.api_kb_management_helpers as legacy_kb_management_helpers
import backend.api_model_config_helpers as legacy_model_config_helpers
import backend.api_kb_routes as legacy_kb_routes
import backend.api_operations_routes as legacy_operations_routes
import backend.api_prompt_routes as legacy_prompt_routes
import backend.api_security_audit_store as legacy_security_audit_store
import backend.api_security_helpers as legacy_security_helpers
import backend.api_security_routes as legacy_security_routes
import backend.api_share_helpers as legacy_share_helpers
import backend.api_session_helpers as legacy_session_helpers
import backend.api_session_memory_helpers as legacy_session_memory_helpers
import backend.api_session_memory_route_helpers as legacy_session_memory_route_helpers
import backend.api_session_routes as legacy_session_routes
import backend.api_shared_resource_helpers as legacy_shared_resource_helpers
import backend.api_task_execution_helpers as legacy_task_execution_helpers
import backend.api_task_store as legacy_task_store
import backend.api_task_helpers as legacy_task_helpers
import backend.api_task_runtime_helpers as legacy_task_runtime_helpers
import backend.api_workspace_session_helpers as legacy_workspace_session_helpers
import backend.deck_service as legacy_deck_service
import backend.helpers as backend_helpers
import backend.doc_pipeline as legacy_doc_pipeline
import backend.services as backend_services
import backend.services.agent_core as service_agent_core
import backend.services.artifact_service as service_artifact_service
import backend.services.deck_service as service_deck_service
import backend.services.doc_pipeline as service_doc_pipeline
import backend.stores as backend_stores
import backend.tasks as backend_tasks
import backend.tasks.backends as task_backends
import backend.tasks.registry as task_registry
from backend.helpers import (
    agent_stream_helpers,
    attachment_route_helpers,
    chat_file_helpers,
    chat_input_helpers,
    chat_route_helpers,
    chat_stream_helpers,
    delete_kb_directory,
    deck_report_helpers,
    document_helpers,
    artifact_helpers,
    env_config_helpers,
    http_runtime_helpers,
    misc_helpers,
    kb_helpers,
    kb_chunk_route_helpers,
    kb_management_helpers,
    model_config_helpers,
    security_helpers,
    share_helpers,
    session_helpers,
    session_memory_helpers,
    session_memory_route_helpers,
    shared_resource_helpers,
    task_execution_helpers,
    task_helpers,
    task_runtime_helpers,
    workspace_session_helpers,
)
from backend.routes import (
    CreatePromptRequest,
    TestRetrievalRequest as KBTestRetrievalRequest,
    SaveConfigRequest,
    UpdatePromptRequest,
    UpdateKBChunkRequest,
    UpsertCloudModelApiKeyRequest,
    build_chat_router,
    build_content_router,
    build_kb_router,
    build_operations_router,
    build_prompt_router,
    build_security_router,
    build_session_router,
)
from backend.routes import (
    chat_routes,
    content_routes,
    kb_routes,
    operations_routes,
    prompt_routes,
    security_routes,
    session_routes,
)
from backend.stores import (
    AttachmentPromotionRecord,
    RESTART_FAILURE_MESSAGE,
    SecurityAuditEventStoredRecord,
    SQLiteAppConfigStore,
    SQLiteSecurityAuditStore,
    SQLiteShareLinkStore,
    SQLiteTaskStore,
    ShareLinkRecord,
    StoredConfigValue,
    TaskRecord,
    TaskStatus,
)
from backend.stores import config_store, security_audit_store, share_link_store, task_store


def test_split_agent_executor_module_re_exports_legacy_entrypoints():
    assert split_agent_executor.build_agent is legacy_agent_core.build_agent
    assert split_agent_executor.build_langgraph_agent is legacy_agent_core.build_langgraph_agent
    assert split_agent_executor.test_agent is legacy_agent_core.test_agent
    assert split_agent_executor.AgentState is legacy_agent_core.AgentState


def test_split_agent_package_exports_current_public_agent_symbols():
    assert split_agent.build_agent is legacy_agent_core.build_agent
    assert split_agent.build_langgraph_agent is legacy_agent_core.build_langgraph_agent
    assert split_agent.test_agent is legacy_agent_core.test_agent
    assert split_agent.get_llm is legacy_agent_core.get_llm
    assert split_agent.normalize_connection_type is split_agent_connection.normalize_connection_type
    assert split_agent.CHAT_FILE_CONTEXT_START_MARKER == legacy_agent_core.CHAT_FILE_CONTEXT_START_MARKER
    assert split_agent.CHAT_FILE_CONTEXT_END_MARKER == legacy_agent_core.CHAT_FILE_CONTEXT_END_MARKER


def test_split_agent_tools_re_exports_tool_registry_helpers():
    assert (
        split_agent_tools._build_enabled_tool_directory
        is split_agent_tool_registry._build_enabled_tool_directory
    )
    assert (
        split_agent_tools.list_enabled_builtin_tool_specs
        is split_agent_tool_registry.list_enabled_builtin_tool_specs
    )


def test_split_agent_runtime_support_re_exports_focused_module_symbols():
    assert split_agent_runtime_support.DEFAULT_LLM_TIMEOUT_SECONDS == split_agent_llm.DEFAULT_LLM_TIMEOUT_SECONDS
    assert split_agent_runtime_support.PLACEHOLDER_SYSTEM_PROMPTS is split_agent_llm.PLACEHOLDER_SYSTEM_PROMPTS
    assert split_agent_runtime_support._ThinkTagStreamFilter is split_agent_llm._ThinkTagStreamFilter
    assert split_agent_runtime_support._ainvoke_llm_with_timeout is split_agent_llm._ainvoke_llm_with_timeout
    assert split_agent_runtime_support._astream_llm_with_timeout is split_agent_llm._astream_llm_with_timeout
    assert split_agent_runtime_support._compact_tool_result_for_prompt is split_agent_llm._compact_tool_result_for_prompt
    assert split_agent_runtime_support._has_image_input is split_agent_llm._has_image_input
    assert split_agent_runtime_support._is_timeout_error is split_agent_llm._is_timeout_error
    assert (
        split_agent_runtime_support._normalize_runtime_system_prompt
        is split_agent_llm._normalize_runtime_system_prompt
    )
    assert split_agent_runtime_support._record_llm_call_result is split_agent_llm._record_llm_call_result
    assert (
        split_agent_runtime_support._stringify_stream_chunk_content
        is split_agent_llm._stringify_stream_chunk_content
    )
    assert split_agent_runtime_support._stringify_user_input is split_agent_llm._stringify_user_input
    assert split_agent_runtime_support._strip_think_tags is split_agent_llm._strip_think_tags
    assert split_agent_runtime_support._build_attachment_sources is split_agent_sources._build_attachment_sources
    assert split_agent_runtime_support._merge_sources_with_attachments is split_agent_sources._merge_sources_with_attachments
    assert split_agent_runtime_support._extract_sources_from_marked_result is split_agent_sources._extract_sources_from_marked_result
    assert split_agent_runtime_support._finalize_agent_result is split_agent_prompts._finalize_agent_result
    assert split_agent_runtime_support._finalize_business_answer_output is split_agent_prompts._finalize_business_answer_output
    assert split_agent_runtime_support.get_session_history is split_agent_history.get_session_history
    assert split_agent_runtime_support._summarize_user_input_for_history is split_agent_history._summarize_user_input_for_history
    assert split_agent_runtime_support._retrieve_kb_documents is split_agent_retrieval._retrieve_kb_documents
    assert split_agent_runtime_support._dedupe_documents is split_agent_retrieval._dedupe_documents
    assert (
        split_agent_runtime_support._looks_like_reasoning_only_output
        is split_agent_runtime_intent._looks_like_reasoning_only_output
    )
    assert split_agent_runtime_support._normalized_intent_text is split_agent_runtime_intent._normalized_intent_text
    assert (
        split_agent_runtime_support._heuristic_langgraph_tool_choice
        is split_agent_runtime_plain_chat._heuristic_langgraph_tool_choice
    )
    assert (
        split_agent_runtime_support._looks_like_resume_request
        is split_agent_runtime_plain_chat._looks_like_resume_request
    )
    assert (
        split_agent_runtime_support._direct_multimodal_answer
        is split_agent_runtime_plain_chat._direct_multimodal_answer
    )
    assert (
        split_agent_runtime_support._build_plain_text_chat_messages
        is split_agent_runtime_plain_chat._build_plain_text_chat_messages
    )
    assert (
        split_agent_runtime_support._should_bypass_tools_for_plain_text_chat
        is split_agent_runtime_plain_chat._should_bypass_tools_for_plain_text_chat
    )
    assert (
        split_agent_runtime_support._plain_text_chat_timeout_seconds
        is split_agent_runtime_plain_chat._plain_text_chat_timeout_seconds
    )
    assert (
        split_agent_runtime_support._direct_plain_text_answer
        is split_agent_runtime_plain_chat._direct_plain_text_answer
    )
    assert (
        split_agent_runtime_support._astream_plain_text_answer
        is split_agent_runtime_plain_chat._astream_plain_text_answer
    )
    assert split_agent_runtime_support._build_kb_timeout_fallback is split_agent_fallbacks._build_kb_timeout_fallback
    assert (
        split_agent_runtime_support._build_resume_timeout_fallback
        is split_agent_fallbacks._build_resume_timeout_fallback
    )
    assert (
        split_agent_runtime_support.DASHBOARD_TRIGGER_KEYWORDS
        is split_agent_dashboard_payload.DASHBOARD_TRIGGER_KEYWORDS
    )
    assert (
        split_agent_runtime_support.DEFAULT_DASHBOARD_TEMPLATE
        is split_agent_dashboard_payload.DEFAULT_DASHBOARD_TEMPLATE
    )
    assert split_agent_runtime_support._extract_json_payload is split_agent_dashboard_payload._extract_json_payload
    assert (
        split_agent_runtime_support._normalize_dashboard_template
        is split_agent_dashboard_payload._normalize_dashboard_template
    )
    assert (
        split_agent_runtime_support._should_generate_dashboard
        is split_agent_dashboard_payload._should_generate_dashboard
    )
    assert split_agent_runtime_support._build_dashboard_sources is split_agent_dashboard_payload._build_dashboard_sources
    assert (
        split_agent_runtime_support._sanitize_dashboard_payload
        is split_agent_dashboard_payload._sanitize_dashboard_payload
    )
    assert split_agent_runtime_support._render_dashboard_card is split_agent_dashboard_payload._render_dashboard_card
    assert (
        split_agent_runtime_support._render_attachment_dashboard_card
        is split_agent_dashboard_payload._render_attachment_dashboard_card
    )
    assert (
        split_agent_runtime_support._extract_attachment_sections
        is split_agent_dashboard_attachments._extract_attachment_sections
    )
    assert (
        split_agent_runtime_support._extract_attachment_evidence
        is split_agent_dashboard_attachments._extract_attachment_evidence
    )
    assert (
        split_agent_runtime_support._parse_numeric_dashboard_value
        is split_agent_dashboard_attachments._parse_numeric_dashboard_value
    )
    assert (
        split_agent_runtime_support._coerce_dashboard_cell_value
        is split_agent_dashboard_attachments._coerce_dashboard_cell_value
    )
    assert split_agent_runtime_support._is_rate_like_metric is split_agent_dashboard_attachments._is_rate_like_metric
    assert (
        split_agent_runtime_support._looks_like_date_dimension
        is split_agent_dashboard_attachments._looks_like_date_dimension
    )
    assert split_agent_runtime_support._parse_attachment_tables is split_agent_dashboard_attachments._parse_attachment_tables
    assert (
        split_agent_runtime_support._build_attachment_dashboard_fallback
        is split_agent_dashboard_attachments._build_attachment_dashboard_fallback
    )
    assert split_agent_runtime_support._generate_dashboard_from_attachment is split_agent_dashboard._generate_dashboard_from_attachment
    assert split_agent_runtime_support._generate_dashboard_from_knowledge is split_agent_dashboard._generate_dashboard_from_knowledge


def test_legacy_agent_core_monkeypatch_reaches_dashboard_split_modules(monkeypatch):
    def sentinel_dashboard_detector(user_input):
        return bool(user_input)

    monkeypatch.setattr(legacy_agent_core, "_should_generate_dashboard", sentinel_dashboard_detector)

    assert split_agent_runtime_support._should_generate_dashboard is sentinel_dashboard_detector
    assert split_agent_dashboard._should_generate_dashboard is sentinel_dashboard_detector
    assert split_agent_dashboard_payload._should_generate_dashboard is sentinel_dashboard_detector
    assert split_agent_runtime_plain_chat._should_generate_dashboard is sentinel_dashboard_detector


def test_split_agent_dashboard_re_exports_payload_helpers():
    assert (
        split_agent_dashboard.DASHBOARD_TRIGGER_KEYWORDS
        is split_agent_dashboard_payload.DASHBOARD_TRIGGER_KEYWORDS
    )
    assert (
        split_agent_dashboard.DEFAULT_DASHBOARD_TEMPLATE
        is split_agent_dashboard_payload.DEFAULT_DASHBOARD_TEMPLATE
    )
    assert split_agent_dashboard._extract_json_payload is split_agent_dashboard_payload._extract_json_payload
    assert (
        split_agent_dashboard._normalize_dashboard_template
        is split_agent_dashboard_payload._normalize_dashboard_template
    )
    assert split_agent_dashboard._should_generate_dashboard is split_agent_dashboard_payload._should_generate_dashboard
    assert split_agent_dashboard._build_dashboard_sources is split_agent_dashboard_payload._build_dashboard_sources
    assert (
        split_agent_dashboard._sanitize_dashboard_payload
        is split_agent_dashboard_payload._sanitize_dashboard_payload
    )
    assert split_agent_dashboard._render_dashboard_card is split_agent_dashboard_payload._render_dashboard_card
    assert (
        split_agent_dashboard._render_attachment_dashboard_card
        is split_agent_dashboard_payload._render_attachment_dashboard_card
    )
    assert (
        split_agent_dashboard._extract_attachment_sections
        is split_agent_dashboard_payload._extract_attachment_sections
    )
    assert (
        split_agent_dashboard._extract_attachment_evidence
        is split_agent_dashboard_payload._extract_attachment_evidence
    )
    assert (
        split_agent_dashboard._parse_numeric_dashboard_value
        is split_agent_dashboard_payload._parse_numeric_dashboard_value
    )
    assert split_agent_dashboard._parse_attachment_tables is split_agent_dashboard_payload._parse_attachment_tables
    assert (
        split_agent_dashboard._build_attachment_dashboard_fallback
        is split_agent_dashboard_payload._build_attachment_dashboard_fallback
    )


def test_split_agent_dashboard_payload_re_exports_attachment_helpers():
    assert (
        split_agent_dashboard_payload._extract_attachment_sections
        is split_agent_dashboard_attachments._extract_attachment_sections
    )
    assert (
        split_agent_dashboard_payload._extract_attachment_evidence
        is split_agent_dashboard_attachments._extract_attachment_evidence
    )
    assert (
        split_agent_dashboard_payload._parse_numeric_dashboard_value
        is split_agent_dashboard_attachments._parse_numeric_dashboard_value
    )
    assert (
        split_agent_dashboard_payload._coerce_dashboard_cell_value
        is split_agent_dashboard_attachments._coerce_dashboard_cell_value
    )
    assert (
        split_agent_dashboard_payload._is_rate_like_metric
        is split_agent_dashboard_attachments._is_rate_like_metric
    )
    assert (
        split_agent_dashboard_payload._looks_like_date_dimension
        is split_agent_dashboard_attachments._looks_like_date_dimension
    )
    assert (
        split_agent_dashboard_payload._parse_attachment_tables
        is split_agent_dashboard_attachments._parse_attachment_tables
    )
    assert (
        split_agent_dashboard_payload._build_attachment_dashboard_fallback
        is split_agent_dashboard_attachments._build_attachment_dashboard_fallback
    )


def test_split_agent_builder_re_exports_builder_context_helpers():
    assert split_agent_builder._configurable_value is split_agent_builder_context._configurable_value
    assert split_agent_builder._configurable_list is split_agent_builder_context._configurable_list
    assert split_agent_builder._attach_configured_task_meta is split_agent_builder_context._attach_configured_task_meta
    assert split_agent_builder._build_workflow_snapshot is split_agent_builder_context._build_workflow_snapshot


def test_split_agent_builder_re_exports_builder_history_helpers():
    assert split_agent_builder._load_chat_history is split_agent_builder_history._load_chat_history
    assert split_agent_builder._persist_panel_history is split_agent_builder_history._persist_panel_history


def test_split_agent_builder_re_exports_builder_streaming_helpers():
    assert split_agent_builder._ainvoke_agent_wrapper is split_agent_builder_streaming._ainvoke_agent_wrapper
    assert split_agent_builder._astream_langgraph_wrapper is split_agent_builder_streaming._astream_langgraph_wrapper


def test_split_agent_dashboard_payload_re_export_behavior_matches_payload_module():
    raw = "prefix ```json\n{\"title\":\"Demo\",\"summary\":\"ok\",\"evidence\":[{\"id\":\"e1\"}]}\n``` suffix"
    assert split_agent_dashboard._extract_json_payload(raw) == split_agent_dashboard_payload._extract_json_payload(raw)

    payload = {
        "title": "Demo",
        "summary": "ok",
        "metrics": [{"label": "Revenue", "value": "12", "evidence_ids": ["e1", "missing"]}],
        "charts": [],
        "table": None,
        "evidence": [{"id": "e1", "title": "Source", "snippet": "snippet", "source_type": "doc"}],
        "warnings": ["check"],
    }
    assert (
        split_agent_dashboard._sanitize_dashboard_payload(payload)
        == split_agent_dashboard_payload._sanitize_dashboard_payload(payload)
    )


def test_legacy_config_store_module_re_exports_new_store_symbols():
    assert legacy_config_store.SQLiteAppConfigStore is config_store.SQLiteAppConfigStore
    assert legacy_config_store.StoredConfigValue is config_store.StoredConfigValue
    assert (
        legacy_config_store.append_mcp_runtime_health_history
        is config_store.append_mcp_runtime_health_history
    )
    assert (
        legacy_config_store.read_mcp_runtime_health_history
        is config_store.read_mcp_runtime_health_history
    )
    assert (
        legacy_config_store.sanitize_mcp_runtime_health_history_item
        is config_store.sanitize_mcp_runtime_health_history_item
    )
    assert SQLiteAppConfigStore is config_store.SQLiteAppConfigStore
    assert StoredConfigValue is config_store.StoredConfigValue


def test_legacy_security_audit_store_module_re_exports_new_store_symbols():
    assert (
        legacy_security_audit_store.SecurityAuditEventStoredRecord
        is security_audit_store.SecurityAuditEventStoredRecord
    )
    assert legacy_security_audit_store.SQLiteSecurityAuditStore is security_audit_store.SQLiteSecurityAuditStore
    assert SecurityAuditEventStoredRecord is security_audit_store.SecurityAuditEventStoredRecord
    assert SQLiteSecurityAuditStore is security_audit_store.SQLiteSecurityAuditStore


def test_legacy_task_store_module_re_exports_new_store_symbols():
    assert legacy_task_store.AttachmentPromotionRecord is task_store.AttachmentPromotionRecord
    assert legacy_task_store.RESTART_FAILURE_MESSAGE == task_store.RESTART_FAILURE_MESSAGE
    assert legacy_task_store.SQLiteTaskStore is task_store.SQLiteTaskStore
    assert legacy_task_store.TaskRecord is task_store.TaskRecord
    assert legacy_task_store.TaskStatus is task_store.TaskStatus
    assert AttachmentPromotionRecord is task_store.AttachmentPromotionRecord
    assert RESTART_FAILURE_MESSAGE == task_store.RESTART_FAILURE_MESSAGE
    assert SQLiteTaskStore is task_store.SQLiteTaskStore
    assert TaskRecord is task_store.TaskRecord
    assert TaskStatus is task_store.TaskStatus


def test_legacy_prompt_routes_module_re_exports_new_route_symbols():
    assert legacy_prompt_routes.build_prompt_router is prompt_routes.build_prompt_router
    assert legacy_prompt_routes.CreatePromptRequest is prompt_routes.CreatePromptRequest
    assert legacy_prompt_routes.UpdatePromptRequest is prompt_routes.UpdatePromptRequest
    assert build_prompt_router is prompt_routes.build_prompt_router
    assert CreatePromptRequest is prompt_routes.CreatePromptRequest
    assert UpdatePromptRequest is prompt_routes.UpdatePromptRequest


def test_legacy_operations_routes_module_re_exports_new_route_symbols():
    assert legacy_operations_routes.build_operations_router is operations_routes.build_operations_router
    assert legacy_operations_routes.SaveConfigRequest is operations_routes.SaveConfigRequest
    assert (
        legacy_operations_routes.UpsertCloudModelApiKeyRequest
        is operations_routes.UpsertCloudModelApiKeyRequest
    )
    assert build_operations_router is operations_routes.build_operations_router
    assert SaveConfigRequest is operations_routes.SaveConfigRequest
    assert UpsertCloudModelApiKeyRequest is operations_routes.UpsertCloudModelApiKeyRequest


def test_legacy_content_routes_module_re_exports_new_route_symbol():
    assert legacy_content_routes.build_content_router is content_routes.build_content_router
    assert build_content_router is content_routes.build_content_router


def test_legacy_kb_routes_module_re_exports_new_route_symbols():
    assert legacy_kb_routes.TestRetrievalRequest is kb_routes.TestRetrievalRequest
    assert legacy_kb_routes.UpdateKBChunkRequest is kb_routes.UpdateKBChunkRequest
    assert legacy_kb_routes.build_kb_router is kb_routes.build_kb_router
    assert KBTestRetrievalRequest is kb_routes.TestRetrievalRequest
    assert UpdateKBChunkRequest is kb_routes.UpdateKBChunkRequest
    assert build_kb_router is kb_routes.build_kb_router


def test_legacy_session_routes_module_re_exports_new_route_symbol():
    assert legacy_session_routes.build_session_router is session_routes.build_session_router
    assert build_session_router is session_routes.build_session_router


def test_legacy_kb_delete_helper_re_exports_new_helper_symbol():
    from backend.helpers import kb_delete_helpers

    assert legacy_kb_delete_helpers.delete_kb_directory is kb_delete_helpers.delete_kb_directory
    assert delete_kb_directory is kb_delete_helpers.delete_kb_directory


def test_legacy_kb_helpers_re_export_new_helper_symbols():
    assert legacy_kb_helpers.filter_kb_chunks is kb_helpers.filter_kb_chunks
    assert legacy_kb_helpers.kb_collect_chunks is kb_helpers.kb_collect_chunks
    assert legacy_kb_helpers.kb_docstore_dict is kb_helpers.kb_docstore_dict
    assert legacy_kb_helpers.kb_rebuild_from_documents is kb_helpers.kb_rebuild_from_documents
    assert legacy_kb_helpers.kb_safe_metadata is kb_helpers.kb_safe_metadata


def test_legacy_attachment_route_helpers_re_export_new_helper_symbols():
    assert (
        legacy_attachment_route_helpers.prepare_attachment_promotion
        is attachment_route_helpers.prepare_attachment_promotion
    )
    assert (
        legacy_attachment_route_helpers.session_attachments_payload
        is attachment_route_helpers.session_attachments_payload
    )


def test_legacy_chat_input_helpers_re_export_new_helper_symbols():
    assert legacy_chat_input_helpers.validate_chat_payload is chat_input_helpers.validate_chat_payload
    assert legacy_chat_input_helpers.chat_file_suffix is chat_input_helpers.chat_file_suffix
    assert legacy_chat_input_helpers.decode_data_url is chat_input_helpers.decode_data_url
    assert (
        legacy_chat_input_helpers.clip_attachment_preview_text
        is chat_input_helpers.clip_attachment_preview_text
    )
    assert (
        legacy_chat_input_helpers.build_message_with_files
        is chat_input_helpers.build_message_with_files
    )
    assert legacy_chat_input_helpers.build_user_input is chat_input_helpers.build_user_input
    assert legacy_chat_input_helpers.user_input_has_images is chat_input_helpers.user_input_has_images
    assert legacy_chat_input_helpers.model_supports_images is chat_input_helpers.model_supports_images
    assert legacy_chat_input_helpers.stringify_user_input is chat_input_helpers.stringify_user_input


def test_legacy_chat_file_helpers_re_export_new_helper_symbols():
    assert legacy_chat_file_helpers.ChatFileConfig is chat_file_helpers.ChatFileConfig
    assert legacy_chat_file_helpers.prepare_chat_files is chat_file_helpers.prepare_chat_files


def test_legacy_document_helpers_re_export_new_helper_symbols():
    assert (
        legacy_document_helpers.DEFAULT_UPLOAD_ALLOWED_SUFFIXES
        == document_helpers.DEFAULT_UPLOAD_ALLOWED_SUFFIXES
    )
    assert (
        legacy_document_helpers.DEFAULT_UPLOAD_MAX_FILE_COUNT
        == document_helpers.DEFAULT_UPLOAD_MAX_FILE_COUNT
    )
    assert (
        legacy_document_helpers.DEFAULT_UPLOAD_MAX_FILE_BYTES
        == document_helpers.DEFAULT_UPLOAD_MAX_FILE_BYTES
    )
    assert (
        legacy_document_helpers.DEFAULT_UPLOAD_MAX_TOTAL_BYTES
        == document_helpers.DEFAULT_UPLOAD_MAX_TOTAL_BYTES
    )
    assert legacy_document_helpers.upload_file_suffix is document_helpers.upload_file_suffix
    assert legacy_document_helpers.cleanup_temp_paths is document_helpers.cleanup_temp_paths
    assert legacy_document_helpers.stage_upload_files is document_helpers.stage_upload_files
    assert (
        legacy_document_helpers.stage_upload_files_with_limits
        is document_helpers.stage_upload_files_with_limits
    )
    assert (
        legacy_document_helpers.build_upload_documents_task_record
        is document_helpers.build_upload_documents_task_record
    )
    assert (
        legacy_document_helpers.upload_documents_response
        is document_helpers.upload_documents_response
    )
    assert legacy_document_helpers.build_chat_report_title is document_helpers.build_chat_report_title
    assert legacy_document_helpers.safe_report_filename is document_helpers.safe_report_filename
    assert (
        legacy_document_helpers.populate_chat_report_presentation
        is document_helpers.populate_chat_report_presentation
    )
    assert legacy_document_helpers.retrieval_test_payload is document_helpers.retrieval_test_payload


def test_legacy_deck_report_helpers_re_export_new_helper_symbols():
    assert (
        legacy_deck_report_helpers.build_scoped_report_messages
        is deck_report_helpers.build_scoped_report_messages
    )
    assert legacy_deck_report_helpers.resolve_report_messages is deck_report_helpers.resolve_report_messages
    assert (
        legacy_deck_report_helpers.create_share_link_payload
        is deck_report_helpers.create_share_link_payload
    )
    assert (
        legacy_deck_report_helpers.build_create_deck_kwargs
        is deck_report_helpers.build_create_deck_kwargs
    )
    assert legacy_deck_report_helpers.apply_deck_update is deck_report_helpers.apply_deck_update
    assert (
        legacy_deck_report_helpers.build_regenerate_deck_kwargs
        is deck_report_helpers.build_regenerate_deck_kwargs
    )
    assert legacy_deck_report_helpers.replace_deck_slide is deck_report_helpers.replace_deck_slide
    assert legacy_deck_report_helpers.export_deck_payload is deck_report_helpers.export_deck_payload
    assert (
        legacy_deck_report_helpers.report_markdown_payload
        is deck_report_helpers.report_markdown_payload
    )
    assert (
        legacy_deck_report_helpers.report_download_payload
        is deck_report_helpers.report_download_payload
    )


def test_legacy_kb_chunk_route_helpers_re_export_new_helper_symbols():
    assert (
        legacy_kb_chunk_route_helpers.list_kb_chunks_payload
        is kb_chunk_route_helpers.list_kb_chunks_payload
    )
    assert (
        legacy_kb_chunk_route_helpers.update_kb_chunk_payload
        is kb_chunk_route_helpers.update_kb_chunk_payload
    )
    assert (
        legacy_kb_chunk_route_helpers.delete_kb_chunk_payload
        is kb_chunk_route_helpers.delete_kb_chunk_payload
    )


def test_legacy_chat_route_helpers_re_export_new_helper_symbols():
    assert legacy_chat_route_helpers.ChatRouteRuntime is chat_route_helpers.ChatRouteRuntime
    assert legacy_chat_route_helpers.SSE_RESPONSE_HEADERS == chat_route_helpers.SSE_RESPONSE_HEADERS
    assert (
        legacy_chat_route_helpers.build_parallel_agent_streams
        is chat_route_helpers.build_parallel_agent_streams
    )
    assert (
        legacy_chat_route_helpers.build_single_agent_stream
        is chat_route_helpers.build_single_agent_stream
    )
    assert (
        legacy_chat_route_helpers.prepare_chat_route_runtime
        is chat_route_helpers.prepare_chat_route_runtime
    )
    assert (
        legacy_chat_route_helpers.sse_streaming_response
        is chat_route_helpers.sse_streaming_response
    )


def test_legacy_chat_stream_helpers_re_export_new_helper_symbols():
    assert legacy_chat_stream_helpers.encode_sse is chat_stream_helpers.encode_sse
    assert legacy_chat_stream_helpers.panel_event is chat_stream_helpers.panel_event
    assert legacy_chat_stream_helpers.all_done_event is chat_stream_helpers.all_done_event
    assert legacy_chat_stream_helpers.heartbeat_event is chat_stream_helpers.heartbeat_event
    assert legacy_chat_stream_helpers.done_event is chat_stream_helpers.done_event
    assert (
        legacy_chat_stream_helpers.build_agent_config_payload
        is chat_stream_helpers.build_agent_config_payload
    )
    assert legacy_chat_stream_helpers.answer_chunks is chat_stream_helpers.answer_chunks
    assert legacy_chat_stream_helpers.stream_single_sse is chat_stream_helpers.stream_single_sse
    assert legacy_chat_stream_helpers.stream_parallel_sse is chat_stream_helpers.stream_parallel_sse


def test_legacy_agent_stream_helpers_re_export_new_helper_symbols():
    assert (
        legacy_agent_stream_helpers.MAX_ITERATIONS_ERROR_MESSAGE
        == agent_stream_helpers.MAX_ITERATIONS_ERROR_MESSAGE
    )
    assert (
        legacy_agent_stream_helpers.MAX_ITERATIONS_ERROR_SUGGESTION
        == agent_stream_helpers.MAX_ITERATIONS_ERROR_SUGGESTION
    )
    assert (
        legacy_agent_stream_helpers.MAX_ITERATIONS_DASHBOARD_ERROR
        == agent_stream_helpers.MAX_ITERATIONS_DASHBOARD_ERROR
    )
    assert legacy_agent_stream_helpers.NonStreamAgentOutcome is agent_stream_helpers.NonStreamAgentOutcome
    assert legacy_agent_stream_helpers.dashboard_prompt_excerpt is agent_stream_helpers.dashboard_prompt_excerpt
    assert legacy_agent_stream_helpers.task_created_event is agent_stream_helpers.task_created_event
    assert legacy_agent_stream_helpers.stream_agent_item is agent_stream_helpers.stream_agent_item
    assert (
        legacy_agent_stream_helpers.resolve_non_stream_agent_result
        is agent_stream_helpers.resolve_non_stream_agent_result
    )
    assert legacy_agent_stream_helpers.finalize_dashboard_task is agent_stream_helpers.finalize_dashboard_task
    assert legacy_agent_stream_helpers.fail_dashboard_task is agent_stream_helpers.fail_dashboard_task


def test_legacy_session_memory_helpers_re_export_new_helper_symbols():
    assert legacy_session_memory_helpers.summary_llm_enabled is session_memory_helpers.summary_llm_enabled
    assert (
        legacy_session_memory_helpers.summary_llm_timeout_seconds
        is session_memory_helpers.summary_llm_timeout_seconds
    )
    assert (
        legacy_session_memory_helpers.normalize_llm_text_content
        is session_memory_helpers.normalize_llm_text_content
    )
    assert (
        legacy_session_memory_helpers.build_phase_summary_llm_prompt
        is session_memory_helpers.build_phase_summary_llm_prompt
    )
    assert legacy_session_memory_helpers.summary_turns is session_memory_helpers.summary_turns
    assert (
        legacy_session_memory_helpers.build_phase_summary_content
        is session_memory_helpers.build_phase_summary_content
    )
    assert legacy_session_memory_helpers.latest_auto_summary is session_memory_helpers.latest_auto_summary
    assert (
        legacy_session_memory_helpers.covered_turns_from_summary
        is session_memory_helpers.covered_turns_from_summary
    )
    assert (
        legacy_session_memory_helpers.summarize_window_meta
        is session_memory_helpers.summarize_window_meta
    )


def test_legacy_task_runtime_helpers_re_export_new_helper_symbols():
    assert legacy_task_runtime_helpers.task_record_payload is task_runtime_helpers.task_record_payload
    assert legacy_task_runtime_helpers.attach_current_kb_status is task_runtime_helpers.attach_current_kb_status
    assert legacy_task_runtime_helpers.enqueue_task is task_runtime_helpers.enqueue_task
    assert legacy_task_runtime_helpers.list_tasks_payload is task_runtime_helpers.list_tasks_payload


def test_tasks_package_exports_queue_backend_abstractions():
    assert backend_tasks.TaskQueueBackend is task_backends.TaskQueueBackend
    assert backend_tasks.MemoryTaskQueueBackend is task_backends.MemoryTaskQueueBackend
    assert backend_tasks.ArqTaskQueueBackend is task_backends.ArqTaskQueueBackend
    assert backend_tasks.build_task_queue_backend is task_backends.build_task_queue_backend
    assert backend_tasks.dispatch_task_record is task_backends.dispatch_task_record


def test_tasks_registry_re_exports_split_module_core_symbols():
    task_settings = importlib.import_module("backend.tasks.settings")
    task_health = importlib.import_module("backend.tasks.health")
    task_enqueue = importlib.import_module("backend.tasks.enqueue")

    assert task_registry.normalize_task_backend is task_settings.normalize_task_backend
    assert (
        task_registry.arq_worker_runtime_settings_from_env
        is task_settings.arq_worker_runtime_settings_from_env
    )
    assert task_registry.task_stale_health_payload is task_health.task_stale_health_payload
    assert task_registry.arq_queue_health_payload is task_health.arq_queue_health_payload
    assert task_registry.enqueue_arq_task is task_enqueue.enqueue_arq_task


def test_tasks_package_exports_registry_core_symbols():
    assert backend_tasks.DEFAULT_ARQ_QUEUE_NAME == task_registry.DEFAULT_ARQ_QUEUE_NAME
    assert backend_tasks.TaskBackendName is task_registry.TaskBackendName
    assert backend_tasks.arq_keep_result_from_env is task_registry.arq_keep_result_from_env
    assert backend_tasks.arq_queue_health_payload is task_registry.arq_queue_health_payload
    assert backend_tasks.arq_queue_name_from_env is task_registry.arq_queue_name_from_env
    assert backend_tasks.arq_should_start_task_record is task_registry.arq_should_start_task_record
    assert backend_tasks.enqueue_arq_task is task_registry.enqueue_arq_task
    assert backend_tasks.normalize_task_backend is task_registry.normalize_task_backend
    assert backend_tasks.task_backend_from_env is task_registry.task_backend_from_env


def test_legacy_task_execution_helpers_re_export_new_helper_symbols():
    assert (
        legacy_task_execution_helpers.persist_web_research_task_placeholder
        is task_execution_helpers.persist_web_research_task_placeholder
    )
    assert (
        legacy_task_execution_helpers.persist_web_research_task_result
        is task_execution_helpers.persist_web_research_task_result
    )
    assert (
        legacy_task_execution_helpers.run_analyze_knowledge_base_task
        is task_execution_helpers.run_analyze_knowledge_base_task
    )
    assert legacy_task_execution_helpers.run_generate_deck_task is task_execution_helpers.run_generate_deck_task
    assert (
        legacy_task_execution_helpers.run_generate_report_task
        is task_execution_helpers.run_generate_report_task
    )
    assert legacy_task_execution_helpers.run_placeholder_task is task_execution_helpers.run_placeholder_task
    assert (
        legacy_task_execution_helpers.run_promote_attachment_to_kb_task
        is task_execution_helpers.run_promote_attachment_to_kb_task
    )
    assert legacy_task_execution_helpers.run_upload_documents_task is task_execution_helpers.run_upload_documents_task
    assert legacy_task_execution_helpers.run_web_research_task is task_execution_helpers.run_web_research_task


def test_legacy_task_helpers_re_export_new_helper_symbols():
    assert legacy_task_helpers.should_start_dashboard_task is task_helpers.should_start_dashboard_task
    assert legacy_task_helpers.contains_dashboard_card is task_helpers.contains_dashboard_card
    assert (
        legacy_task_helpers.summarize_dashboard_task_result
        is task_helpers.summarize_dashboard_task_result
    )
    assert (
        legacy_task_helpers.summarize_dashboard_task_error
        is task_helpers.summarize_dashboard_task_error
    )
    assert legacy_task_helpers.prune_task_records is task_helpers.prune_task_records
    assert legacy_task_helpers.create_inline_task_record is task_helpers.create_inline_task_record
    assert legacy_task_helpers.set_inline_task_state is task_helpers.set_inline_task_state


def test_legacy_kb_management_helpers_re_export_new_helper_symbols():
    assert (
        legacy_kb_management_helpers.resolve_project_subdir
        is kb_management_helpers.resolve_project_subdir
    )
    assert (
        legacy_kb_management_helpers.faiss_safe_store_path
        is kb_management_helpers.faiss_safe_store_path
    )
    assert (
        legacy_kb_management_helpers.resolve_deletable_knowledge_base
        is kb_management_helpers.resolve_deletable_knowledge_base
    )
    assert (
        legacy_kb_management_helpers.effective_vector_store_path
        is kb_management_helpers.effective_vector_store_path
    )
    assert legacy_kb_management_helpers.kb_health_payload is kb_management_helpers.kb_health_payload
    assert (
        legacy_kb_management_helpers.knowledge_bases_payload
        is kb_management_helpers.knowledge_bases_payload
    )


def test_legacy_env_config_helpers_re_export_new_helper_symbols():
    assert legacy_env_config_helpers.env_flag is env_config_helpers.env_flag
    assert legacy_env_config_helpers.env_int is env_config_helpers.env_int
    assert legacy_env_config_helpers.env_int_setting is env_config_helpers.env_int_setting
    assert legacy_env_config_helpers.env_bool_setting is env_config_helpers.env_bool_setting
    assert legacy_env_config_helpers.cors_settings is env_config_helpers.cors_settings
    assert (
        legacy_env_config_helpers.is_loopback_host
        is env_config_helpers.is_loopback_host
    )
    assert (
        legacy_env_config_helpers.integrator_scheduler_config_from_env
        is env_config_helpers.integrator_scheduler_config_from_env
    )


def test_legacy_artifact_helpers_re_export_new_helper_symbols():
    assert legacy_artifact_helpers.artifact_payload is artifact_helpers.artifact_payload


def test_legacy_misc_helpers_re_export_new_helper_symbols():
    assert legacy_misc_helpers.request_field_set is misc_helpers.request_field_set
    assert (
        legacy_misc_helpers.dashboard_feature_enabled
        is misc_helpers.dashboard_feature_enabled
    )
    assert (
        legacy_misc_helpers.is_max_iterations_output
        is misc_helpers.is_max_iterations_output
    )


def test_legacy_http_runtime_helpers_re_export_new_helper_symbols():
    assert (
        legacy_http_runtime_helpers.build_download_content_disposition
        is http_runtime_helpers.build_download_content_disposition
    )
    assert (
        legacy_http_runtime_helpers.classify_runtime_error
        is http_runtime_helpers.classify_runtime_error
    )


def test_legacy_model_config_helpers_re_export_new_helper_symbols():
    assert (
        legacy_model_config_helpers.model_config_payload
        is model_config_helpers.model_config_payload
    )
    assert (
        legacy_model_config_helpers.base_model_payload
        is model_config_helpers.base_model_payload
    )
    assert (
        legacy_model_config_helpers.normalize_model_config
        is model_config_helpers.normalize_model_config
    )


def test_legacy_security_helpers_re_export_new_helper_symbols():
    assert legacy_security_helpers.hash_secret is security_helpers.hash_secret
    assert (
        legacy_security_helpers.token_fingerprint
        is security_helpers.token_fingerprint
    )
    assert legacy_security_helpers.token_preview is security_helpers.token_preview
    assert (
        legacy_security_helpers.auth_token_preview
        is security_helpers.auth_token_preview
    )
    assert (
        legacy_security_helpers.normalize_auth_role
        is security_helpers.normalize_auth_role
    )
    assert legacy_security_helpers.role_rank is security_helpers.role_rank
    assert (
        legacy_security_helpers.safe_epoch_seconds
        is security_helpers.safe_epoch_seconds
    )
    assert (
        legacy_security_helpers.sanitize_log_value
        is security_helpers.sanitize_log_value
    )
    assert (
        legacy_security_helpers.sanitize_request_path
        is security_helpers.sanitize_request_path
    )
    assert (
        legacy_security_helpers.security_audit_detail_value
        is security_helpers.security_audit_detail_value
    )
    assert (
        legacy_security_helpers.security_audit_event_org
        is security_helpers.security_audit_event_org
    )
    assert (
        legacy_security_helpers.security_audit_event_tenant
        is security_helpers.security_audit_event_tenant
    )
    assert (
        legacy_security_helpers.security_audit_event_to_payload
        is security_helpers.security_audit_event_to_payload
    )
    assert (
        legacy_security_helpers.security_audit_redacted_details
        is security_helpers.security_audit_redacted_details
    )
    assert (
        legacy_security_helpers.security_audit_siem_event_payload
        is security_helpers.security_audit_siem_event_payload
    )
    assert (
        legacy_security_helpers.build_security_audit_siem_export_payload
        is security_helpers.build_security_audit_siem_export_payload
    )
    assert (
        legacy_security_helpers.build_security_audit_aggregate_report_payload
        is security_helpers.build_security_audit_aggregate_report_payload
    )
    assert (
        backend_helpers.build_security_audit_archive_policy_payload
        is security_helpers.build_security_audit_archive_policy_payload
    )
    assert (
        legacy_security_helpers.build_security_audit_archive_policy_payload
        is security_helpers.build_security_audit_archive_policy_payload
    )
    assert (
        legacy_security_helpers.filter_security_audit_events
        is security_helpers.filter_security_audit_events
    )
    assert (
        legacy_security_helpers.share_link_audit_payload
        is security_helpers.share_link_audit_payload
    )
    assert (
        legacy_security_helpers.auth_token_is_weak
        is security_helpers.auth_token_is_weak
    )
    assert legacy_security_helpers.ceil_seconds is security_helpers.ceil_seconds
    assert legacy_security_helpers.content_hash is security_helpers.content_hash
    assert (
        legacy_security_helpers.auth_capabilities_for_role
        is security_helpers.auth_capabilities_for_role
    )
    assert (
        legacy_security_helpers.build_auth_whoami_payload
        is security_helpers.build_auth_whoami_payload
    )
    assert (
        legacy_security_helpers.build_security_status_payload
        is security_helpers.build_security_status_payload
    )
    assert (
        legacy_security_helpers.build_auth_token_catalog_payload
        is security_helpers.build_auth_token_catalog_payload
    )
    assert (
        legacy_security_helpers.normalize_sso_config_update
        is security_helpers.normalize_sso_config_update
    )
    assert (
        legacy_security_helpers.sso_callback_url_for_mode
        is security_helpers.sso_callback_url_for_mode
    )
    assert (
        legacy_security_helpers.pkce_code_challenge
        is security_helpers.pkce_code_challenge
    )
    assert (
        legacy_security_helpers.sso_session_token_hash
        is security_helpers.sso_session_token_hash
    )


def test_legacy_security_routes_module_re_exports_new_route_symbol():
    assert legacy_security_routes.build_security_router is security_routes.build_security_router
    assert build_security_router is security_routes.build_security_router


def test_legacy_share_helpers_module_re_exports_new_helper_and_store_symbols():
    assert legacy_share_helpers.share_signature is share_helpers.share_signature
    assert legacy_share_helpers.encode_share_token is share_helpers.encode_share_token
    assert legacy_share_helpers.decode_share_token is share_helpers.decode_share_token
    assert legacy_share_helpers.build_share_url is share_helpers.build_share_url
    assert legacy_share_helpers.ShareLinkRecord is share_link_store.ShareLinkRecord
    assert legacy_share_helpers.SQLiteShareLinkStore is share_link_store.SQLiteShareLinkStore
    assert ShareLinkRecord is share_link_store.ShareLinkRecord
    assert SQLiteShareLinkStore is share_link_store.SQLiteShareLinkStore


def test_legacy_session_helpers_re_export_new_helper_symbols():
    assert legacy_session_helpers.message_payload is session_helpers.message_payload
    assert legacy_session_helpers.set_answer_group_reviewer is session_helpers.set_answer_group_reviewer
    assert (
        legacy_session_helpers.build_answer_group_review_payload
        is session_helpers.build_answer_group_review_payload
    )
    assert (
        legacy_session_helpers.build_session_messages_payload
        is session_helpers.build_session_messages_payload
    )
    assert legacy_session_helpers.render_shared_session_html is session_helpers.render_shared_session_html
    assert legacy_session_helpers.render_shared_deck_html is session_helpers.render_shared_deck_html
    assert legacy_session_helpers.session_attachment_id is session_helpers.session_attachment_id
    assert legacy_session_helpers.collect_session_attachments is session_helpers.collect_session_attachments
    assert legacy_session_helpers.find_session_attachment is session_helpers.find_session_attachment


def test_legacy_chat_routes_module_re_exports_new_route_symbol():
    assert legacy_chat_routes.build_chat_router is chat_routes.build_chat_router
    assert build_chat_router is chat_routes.build_chat_router


def test_legacy_session_memory_route_helpers_re_export_new_helper_symbols():
    assert (
        legacy_session_memory_route_helpers.session_memory_payload
        is session_memory_route_helpers.session_memory_payload
    )
    assert (
        legacy_session_memory_route_helpers.pin_session_memory_payload
        is session_memory_route_helpers.pin_session_memory_payload
    )
    assert (
        legacy_session_memory_route_helpers.session_memory_updates
        is session_memory_route_helpers.session_memory_updates
    )
    assert (
        legacy_session_memory_route_helpers.update_session_memory_payload
        is session_memory_route_helpers.update_session_memory_payload
    )
    assert (
        legacy_session_memory_route_helpers.summarize_session_memory_payload
        is session_memory_route_helpers.summarize_session_memory_payload
    )
    assert (
        legacy_session_memory_route_helpers.delete_session_memory_payload
        is session_memory_route_helpers.delete_session_memory_payload
    )


def test_legacy_shared_resource_helpers_re_export_new_helper_symbol():
    assert (
        legacy_shared_resource_helpers.open_shared_resource_payload
        is shared_resource_helpers.open_shared_resource_payload
    )


def test_legacy_workspace_session_helpers_re_export_new_helper_symbols():
    assert (
        legacy_workspace_session_helpers.create_session_record
        is workspace_session_helpers.create_session_record
    )
    assert (
        legacy_workspace_session_helpers.fallback_session_payload
        is workspace_session_helpers.fallback_session_payload
    )
    assert (
        legacy_workspace_session_helpers.normalize_workspace_id
        is workspace_session_helpers.normalize_workspace_id
    )
    assert (
        legacy_workspace_session_helpers.reorder_sessions_payload
        is workspace_session_helpers.reorder_sessions_payload
    )
    assert (
        legacy_workspace_session_helpers.session_update_requested
        is workspace_session_helpers.session_update_requested
    )
    assert (
        legacy_workspace_session_helpers.workspaces_payload
        is workspace_session_helpers.workspaces_payload
    )


def test_backend_refactor_skeleton_packages_are_importable():
    expected_backend_helper_exports = [
        "contains_dashboard_card",
        "create_inline_task_record",
        "dashboard_prompt_excerpt",
        "fail_dashboard_task",
        "finalize_dashboard_task",
        "all_done_event",
        "answer_chunks",
        "apply_deck_update",
        "attach_current_kb_status",
        "auth_capabilities_for_role",
        "build_agent_config_payload",
        "build_auth_token_catalog_payload",
        "build_auth_whoami_payload",
        "build_answer_group_review_payload",
        "build_chat_report_title",
        "build_create_deck_kwargs",
        "build_phase_summary_content",
        "build_phase_summary_llm_prompt",
        "build_message_with_files",
        "build_regenerate_deck_kwargs",
        "build_scoped_report_messages",
        "build_security_status_payload",
        "build_upload_documents_task_record",
        "build_user_input",
        "build_parallel_agent_streams",
        "build_single_agent_stream",
        "chat_file_suffix",
        "ChatFileConfig",
        "ChatRouteRuntime",
        "clip_attachment_preview_text",
        "collect_session_attachments",
        "covered_turns_from_summary",
        "create_session_record",
        "create_share_link_payload",
        "cleanup_temp_paths",
        "decode_data_url",
        "decode_share_token",
        "DEFAULT_UPLOAD_ALLOWED_SUFFIXES",
        "DEFAULT_UPLOAD_MAX_FILE_BYTES",
        "DEFAULT_UPLOAD_MAX_FILE_COUNT",
        "DEFAULT_UPLOAD_MAX_TOTAL_BYTES",
        "delete_kb_chunk_payload",
        "delete_kb_directory",
        "done_event",
        "enqueue_task",
        "encode_sse",
        "encode_share_token",
        "export_deck_payload",
        "find_session_attachment",
        "filter_kb_chunks",
        "heartbeat_event",
        "kb_collect_chunks",
        "kb_docstore_dict",
        "kb_health_payload",
        "kb_rebuild_from_documents",
        "kb_safe_metadata",
        "knowledge_bases_payload",
        "list_kb_chunks_payload",
        "delete_session_memory_payload",
        "fallback_session_payload",
        "latest_auto_summary",
        "list_tasks_payload",
        "MAX_ITERATIONS_DASHBOARD_ERROR",
        "MAX_ITERATIONS_ERROR_MESSAGE",
        "MAX_ITERATIONS_ERROR_SUGGESTION",
        "message_payload",
        "model_supports_images",
        "NonStreamAgentOutcome",
        "normalize_workspace_id",
        "normalize_llm_text_content",
        "open_shared_resource_payload",
        "panel_event",
        "pin_session_memory_payload",
        "prepare_attachment_promotion",
        "prepare_chat_files",
        "prepare_chat_route_runtime",
        "populate_chat_report_presentation",
        "persist_web_research_task_placeholder",
        "persist_web_research_task_result",
        "prune_task_records",
        "replace_deck_slide",
        "render_shared_deck_html",
        "render_shared_session_html",
        "reorder_sessions_payload",
        "report_download_payload",
        "report_markdown_payload",
        "resolve_report_messages",
        "run_analyze_knowledge_base_task",
        "run_generate_deck_task",
        "run_generate_report_task",
        "run_placeholder_task",
        "run_promote_attachment_to_kb_task",
        "run_upload_documents_task",
        "run_web_research_task",
        "retrieval_test_payload",
        "resolve_non_stream_agent_result",
        "SSE_RESPONSE_HEADERS",
        "safe_report_filename",
        "build_share_url",
        "share_signature",
        "build_session_messages_payload",
        "session_memory_payload",
        "session_memory_updates",
        "session_attachments_payload",
        "session_update_requested",
        "set_inline_task_state",
        "should_start_dashboard_task",
        "stage_upload_files",
        "stage_upload_files_with_limits",
        "stream_parallel_sse",
        "stream_single_sse",
        "stream_agent_item",
        "stringify_user_input",
        "summarize_window_meta",
        "summarize_dashboard_task_error",
        "summarize_dashboard_task_result",
        "summarize_session_memory_payload",
        "sse_streaming_response",
        "summary_llm_enabled",
        "summary_llm_timeout_seconds",
        "summary_turns",
        "task_created_event",
        "task_record_payload",
        "update_kb_chunk_payload",
        "update_session_memory_payload",
        "upload_documents_response",
        "upload_file_suffix",
        "user_input_has_images",
        "validate_chat_payload",
        "workspaces_payload",
    ]
    assert not (set(expected_backend_helper_exports) - set(backend_helpers.__all__))
    assert build_chat_router is chat_routes.build_chat_router
    assert build_content_router is content_routes.build_content_router
    assert build_kb_router is kb_routes.build_kb_router
    assert build_session_router is session_routes.build_session_router
    assert backend_stores.__all__ == [
        "SQLiteAppConfigStore",
        "StoredConfigValue",
        "SecurityAuditEventStoredRecord",
        "SQLiteSecurityAuditStore",
        "ShareLinkRecord",
        "SQLiteShareLinkStore",
        "AttachmentPromotionRecord",
        "RESTART_FAILURE_MESSAGE",
        "SQLiteTaskStore",
        "TaskRecord",
        "TaskStatus",
    ]
    assert SQLiteAppConfigStore is config_store.SQLiteAppConfigStore
    assert SQLiteSecurityAuditStore is security_audit_store.SQLiteSecurityAuditStore
    assert ShareLinkRecord is share_link_store.ShareLinkRecord
    assert SQLiteShareLinkStore is share_link_store.SQLiteShareLinkStore
    assert SQLiteTaskStore is task_store.SQLiteTaskStore
    assert backend_services.__all__ == [
        "agent_core",
        "artifact_service",
        "deck_service",
        "doc_pipeline",
    ]
    assert service_agent_core.build_agent is legacy_agent_core.build_agent
    assert service_agent_core.clear_session_history is legacy_agent_core.clear_session_history
    assert service_agent_core.get_llm is legacy_agent_core.get_llm
    assert service_artifact_service.ArtifactRecord is legacy_artifact_service.ArtifactRecord
    assert service_artifact_service.SQLiteArtifactStore is legacy_artifact_service.SQLiteArtifactStore
    assert service_artifact_service.build_deck_artifact is legacy_artifact_service.build_deck_artifact
    assert service_artifact_service.build_report_artifact is legacy_artifact_service.build_report_artifact
    assert service_artifact_service.sync_deck_artifact is legacy_artifact_service.sync_deck_artifact
    assert service_deck_service.DeckMeta is legacy_deck_service.DeckMeta
    assert service_deck_service.DeckSlide is legacy_deck_service.DeckSlide
    assert service_deck_service.SQLiteDeckStore is legacy_deck_service.SQLiteDeckStore
    assert service_deck_service.build_deck is legacy_deck_service.build_deck
    assert service_deck_service.build_report_markdown is legacy_deck_service.build_report_markdown
    assert service_deck_service.ensure_deckable_chat is legacy_deck_service.ensure_deckable_chat
    assert service_deck_service.export_deck_to_pptx is legacy_deck_service.export_deck_to_pptx
    assert service_deck_service.regenerate_deck_slide is legacy_deck_service.regenerate_deck_slide
    assert service_doc_pipeline.DocPipeline is legacy_doc_pipeline.DocPipeline
