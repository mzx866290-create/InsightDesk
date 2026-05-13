from pathlib import Path
import ast


def test_api_server_no_longer_seeds_legacy_short_module_aliases():
    source = Path("backend/api_server.py").read_text(encoding="utf-8")

    assert "_alias_backend_module" not in source
    assert "from backend.api_config_store import" not in source
    assert "importlib.import_module(f\"backend." not in source
    assert "sys.path.insert" not in source
    assert "sys.modules[__name__]" not in source
    assert "def _list_assistant_presets" not in source
    assert "def _list_system_prompts" not in source
    assert "def _build_doc_pipeline" not in source
    assert "def _build_langchain_document" not in source
    assert "def _sync_runtime_secret_from_store" not in source
    assert "def _stored_config_value" not in source
    assert "def _normalize_cloud_model_api_key_ref" not in source
    assert "def _cloud_model_api_key_config_key" not in source
    assert "def _upsert_cloud_model_api_key" not in source
    assert "def _delete_cloud_model_api_key" not in source
    assert "def _validate_tavily_api_key" not in source
    assert "def _integrator_scheduler_config_from_env" not in source
    assert "def _env_int_setting" not in source
    assert "def _env_bool_setting" not in source
    assert "def _env_flag" not in source
    assert "def _env_int(" not in source
    assert "def _cors_settings" not in source
    assert "def _is_loopback_host" not in source
    assert "def _model_config_payload" not in source
    assert "def _base_model_payload" not in source
    assert "def _normalize_model_config" not in source
    assert "def _build_download_content_disposition" not in source
    assert "def _dashboard_feature_enabled" not in source
    assert "def _is_max_iterations_output" not in source
    assert "def _request_field_set" not in source
    assert "def _artifact_payload" not in source
    assert "def _classify_error" not in source
    assert "def _hash_secret" not in source
    assert "def _token_fingerprint" not in source
    assert "def _token_preview" not in source
    assert "def _auth_token_preview" not in source
    assert "def _ceil_seconds" not in source
    assert "def _content_hash" not in source
    assert "def _auth_token_is_weak" not in source
    assert "def _sanitize_log_value" not in source
    assert "def _sanitize_request_path" not in source
    assert "def _auth_capabilities_for_role" not in source
    assert "def _auth_token_hygiene_summary" not in source
    assert "def _role_permission_matrix_payload" not in source
    assert "def _normalize_auth_role" not in source
    assert "def _role_rank" not in source
    assert "def _pkce_code_challenge" not in source
    assert "def _sso_callback_url_for_mode" not in source
    assert "def _sso_session_token_hash" not in source
    assert "def _security_audit_action_catalog_payload" not in source
    assert "def _resolve_project_subdir" not in source
    assert "def _faiss_safe_store_path" not in source
    assert "def _resolve_deletable_knowledge_base" not in source
    assert "def _request_client_ip" not in source
    assert "def _request_user_agent" not in source
    assert "def _current_admin_api_token" not in source
    assert "def _extract_request_token" not in source
    assert "def _extract_admin_token" not in source
    assert "def _configured_auth_token_records" not in source
    assert "def _configured_auth_token_map" not in source
    assert "def _request_auth_mode" not in source
    assert "def _admin_auth_mode" not in source
    assert "def _resolve_request_auth" not in source
    assert "def _request_user_id" not in source
    assert "def _request_user_role" not in source
    assert "def _request_auth_source" not in source
    assert "def _remote_management_rate_limit_applies" not in source
    assert "def _remote_management_rate_limit_principal" not in source
    assert "def _consume_remote_management_rate_limit" not in source
    assert "def _share_link_secret_is_weak" not in source
    assert "def _share_link_secret_uses_default" not in source
    assert "def _require_remote_role" not in source
    assert "def _require_remote_viewer" not in source
    assert "def _require_remote_editor" not in source
    assert "def _require_remote_admin" not in source
    assert "def _require_remote_share_secret" not in source
    assert "def _audit_security_event" not in source
    assert "def _current_share_link_secret" not in source
    assert "def _share_link_audit_payload" not in source
    assert "def _auth_token_catalog_payload" not in source
    assert "def _security_audit_events_payload" not in source
    assert "def _security_audit_summary_payload" not in source
    assert "def _security_audit_siem_export_payload" not in source
    assert "def _security_audit_aggregate_report_payload" not in source
    assert "def _security_audit_archive_policy_payload" not in source
    assert "def _security_audit_legal_hold_payload" not in source
    assert "def _cleanup_security_audit_events" not in source
    assert "def _runtime_request_metrics_payload" not in source
    assert "def _runtime_task_summary_payload" not in source
    assert "def _runtime_operations_payload" not in source
    assert "def _runtime_status_class" not in source
    assert "def _record_runtime_request" not in source
    assert "def _record_runtime_error" not in source
    assert "def _mcp_runtime_health_history_limit" not in source
    assert "def _sanitize_mcp_runtime_health_history_item" not in source
    assert "def _stored_mcp_runtime_health_history" not in source
    assert "def _persist_mcp_runtime_health_history_item" not in source
    assert "def _stored_mcp_approved_connectors" not in source
    assert "def _persist_mcp_approved_connectors" not in source
    assert "def _hydrate_runtime_mcp_approved_connectors_from_store" not in source
    assert "def _mcp_approvals_payload_with_persistence" not in source
    assert "mcp_runtime_helpers.runtime_health_history_payload(" in source
    assert "mcp_runtime_helpers.approvals_payload_with_persistence(" in source
    assert "def _validate_chat_payload" not in source
    assert "def _prepare_chat_files" not in source
    assert "def _build_message_with_files" not in source
    assert "def _build_user_input" not in source
    assert "def _user_input_has_images" not in source
    assert "def _model_supports_images" not in source
    assert "def _clip_attachment_preview_text" not in source
    assert "def _stringify_user_input" not in source
    assert "def _chat_file_suffix" not in source
    assert "def _decode_data_url" not in source
    assert "def _get_identity_store" not in source
    assert "def _get_resource_access_store" not in source
    assert "def _get_app_config_store" not in source
    assert "def _resolve_report_messages" not in source
    assert "def _resolve_model_api_key" not in source
    assert "def _resolve_runtime_model_config" not in source
    assert "def get_ollama_models" not in source
    assert "def _new_runtime_metrics_state" not in source
    assert "def _clip_text" not in source
    assert "def _summary_llm_enabled" not in source
    assert "def _summary_llm_timeout_seconds" not in source
    assert "def _normalize_llm_text_content" not in source
    assert "def _build_phase_summary_llm_prompt" not in source
    assert "def _try_llm_phase_summary_content" not in source
    assert "def _summary_turns" not in source
    assert "def _build_phase_summary_content" not in source
    assert "def _sync_deck_artifacts" not in source
    assert "def _get_attachment_promotion_task" not in source
    assert "def _resolve_active_prompt_runtime" not in source
    assert "def _fallback_generate" not in source
    assert "def _require_workspace_session" not in source
    assert "def _sync_external_identity_payload" not in source
    assert "def _sso_config_payload" not in source
    assert "def _normalize_sso_config_update" not in source
    assert "def _save_sso_config_payload" not in source
    assert "def _register_app_lifecycle_handler" not in source
    assert "async def _generate_session_phase_summary_memory" not in source
    assert "async def _auto_generate_phase_summary_memory" not in source


def test_legacy_api_config_store_is_re_export_only():
    source = Path("backend/api_config_store.py").read_text(encoding="utf-8")

    assert "Compatibility re-export" in source
    assert "from backend.stores.config_store import" in source
    assert "def append_mcp_runtime_health_history" not in source
    assert "def read_mcp_runtime_health_history" not in source


def test_helpers_api_misc_is_compatibility_re_export_only():
    source = Path("backend/helpers/api_misc_helpers.py").read_text(encoding="utf-8")

    assert "Compatibility re-export" in source
    assert "from backend.helpers.misc_helpers import" in source
    assert "def request_field_set" not in source


def test_legacy_api_modules_are_structural_re_exports_only():
    allowed_import_roots = (
        "backend.helpers.",
        "backend.routes.",
        "backend.stores.",
        "backend.tasks.",
    )

    for path in Path("backend").glob("api_*.py"):
        if path.name == "api_server.py":
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        assert "Compatibility" in (ast.get_docstring(tree) or "")
        assert "sys.path" not in source
        assert "importlib" not in source

        for node in tree.body:
            assert not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ), f"{path} should not define implementation symbols"
            if isinstance(node, ast.Import):
                raise AssertionError(f"{path} should use explicit re-export imports")
            if isinstance(node, ast.ImportFrom):
                assert node.module is not None
                assert node.module.startswith(allowed_import_roots), (
                    f"{path} imports from unexpected module {node.module}"
                )


def test_router_registration_uses_explicit_dependency_functions():
    source = Path("backend/core/router_registration.py").read_text(encoding="utf-8")

    assert "import importlib" not in source
    assert "importlib.import_module" not in source
    assert "ctx.importlib" not in source
    assert "prompt_runtime.list_assistant_presets" in source
    assert "prompt_runtime.resolve_active_prompt_runtime" in source
    assert "require_workspace_session=require_workspace_session" in source
    assert "_sync_external_identity_payload_builder(ctx)" in source
    assert "_session_phase_summary_generator(ctx)" in source
    assert "ctx._list_assistant_presets" not in source
    assert "document_runtime.build_doc_pipeline" in source
    assert "document_runtime.build_langchain_document" in source
    assert "ctx._build_doc_pipeline" not in source
    assert "ctx._build_langchain_document" not in source
    assert "app_config_runtime.sync_runtime_secret_from_store" in source
    assert "app_config_runtime.upsert_cloud_model_api_key" in source
    assert "ctx._sync_runtime_secret_from_store" not in source
    assert "ctx._upsert_cloud_model_api_key" not in source
    assert "env_runtime.integrator_scheduler_config" in source
    assert "ctx._integrator_scheduler_config_from_env" not in source
    assert "model_config_runtime.base_model_payload" in source
    assert "model_config_runtime.normalize_model_config" in source
    assert "model_config_runtime.model_config_payload" in source
    assert "model_config_runtime.resolve_runtime_model_config" in source
    assert "ctx._base_model_payload" not in source
    assert "ctx._normalize_model_config" not in source
    assert "ctx._model_config_payload" not in source
    assert "ctx._resolve_runtime_model_config" not in source
    assert "build_download_content_disposition=build_download_content_disposition" in source
    assert "ctx._build_download_content_disposition" not in source
    assert "request_field_set=request_field_set" in source
    assert "ctx._request_field_set" not in source
    assert "artifact_payload=lambda artifact: build_artifact_payload(" in source
    assert "ctx._artifact_payload" not in source
    assert "content_hash=content_hash" in source
    assert "token_fingerprint=token_fingerprint" in source
    assert "ctx._content_hash" not in source
    assert "ctx._token_fingerprint" not in source
    assert "auth_whoami_payload=lambda auth: build_auth_whoami_payload(" in source
    assert "role_permission_matrix_payload=build_role_permission_matrix_payload" in source
    assert (
        "security_audit_action_catalog_payload="
        "build_security_audit_action_catalog_payload"
    ) in source
    assert "kb_runtime.resolve_project_subdir(" in source
    assert (
        "kb_runtime.resolve_deletable_knowledge_base("
    ) in source
    assert "kb_runtime.faiss_safe_store_path(" in source
    assert "ctx._resolve_project_subdir" not in source
    assert "ctx._resolve_deletable_knowledge_base" not in source
    assert "ctx._faiss_safe_store_path" not in source
    assert "request_runtime.request_client_ip" in source
    assert "request_runtime.request_user_agent" in source
    assert "runtime_request_metrics_payload(" in source
    assert "build_runtime_task_summary_payload(" in source
    assert "runtime_operations_summary_payload(" in source
    assert "build_share_link_audit_payload(" in source
    assert "security_runtime._current_share_link_secret(" in source
    assert "security_runtime._auth_token_catalog_payload(" in source
    assert "security_runtime._sso_config_payload(" in source
    assert "security_runtime._save_sso_config_payload(" in source
    assert "security_runtime._security_audit_events_payload(" in source
    assert "security_runtime._security_audit_summary_payload(" in source
    assert "security_runtime._security_audit_siem_export_payload(" in source
    assert "security_runtime._security_audit_aggregate_report_payload(" in source
    assert "security_runtime._security_audit_archive_policy_payload(" in source
    assert "security_runtime._security_audit_legal_hold_payload(" in source
    assert "security_runtime._cleanup_security_audit_events(" in source
    assert "security_runtime._audit_security_event(" in source
    assert "ctx._audit_security_event" not in source
    assert "ctx._require_remote_viewer" not in source
    assert "ctx._require_remote_editor" not in source
    assert "ctx._require_remote_admin" not in source
    assert "ctx._require_remote_share_secret" not in source
    assert "ctx._current_share_link_secret" not in source
    assert "ctx._share_link_audit_payload" not in source
    assert "ctx._auth_token_catalog_payload" not in source
    assert "ctx._security_audit_events_payload" not in source
    assert "ctx._security_audit_summary_payload" not in source
    assert "ctx._security_audit_siem_export_payload" not in source
    assert "ctx._security_audit_aggregate_report_payload" not in source
    assert "ctx._security_audit_archive_policy_payload" not in source
    assert "ctx._security_audit_legal_hold_payload" not in source
    assert "ctx._cleanup_security_audit_events" not in source
    assert "ctx._runtime_request_metrics_payload" not in source
    assert "ctx._runtime_task_summary_payload" not in source
    assert "ctx._runtime_operations_payload" not in source
    assert "ctx._normalize_auth_role" not in source
    assert "ctx._role_rank" not in source
    assert "ctx._role_permission_matrix_payload" not in source
    assert "ctx.build_auth_whoami_payload" not in source
    assert "ctx._get_identity_store" not in source
    assert "ctx._get_resource_access_store" not in source
    assert "ctx._get_app_config_store" not in source
    assert "_identity_store_getter(ctx)" in source
    assert "_resource_access_store_getter(ctx)" in source
    assert "_app_config_store_getter(ctx)" in source
    assert "_deck_artifacts_syncer(ctx)" in source
    assert "_attachment_promotion_task_getter(ctx)" in source
    assert "resolve_langchain_report_messages" in source
    assert "ctx._resolve_report_messages" not in source
    assert "ctx._sync_deck_artifacts" not in source
    assert "ctx._get_attachment_promotion_task" not in source
    assert "ctx._resolve_active_prompt_runtime" not in source
    assert "ctx._require_workspace_session" not in source
    assert "ctx._sync_external_identity_payload" not in source
    assert "ctx._sso_config_payload" not in source
    assert "ctx._save_sso_config_payload" not in source
    assert "ctx._generate_session_phase_summary_memory" not in source


def test_backend_runtime_imports_chat_store_by_package_path():
    all_files = [
        Path("backend/api_server.py"),
        Path("backend/core/session_summary_runtime.py"),
        Path("backend/routes/chat_routes.py"),
        Path("backend/routes/session_routes.py"),
    ]

    for path in all_files:
        source = path.read_text(encoding="utf-8")
        assert "from chat_store import" not in source

    files_with_direct_chat_store_dependency = [
        Path("backend/core/session_summary_runtime.py"),
        Path("backend/routes/chat_routes.py"),
        Path("backend/routes/session_routes.py"),
    ]
    for path in files_with_direct_chat_store_dependency:
        source = path.read_text(encoding="utf-8")
        assert "from backend.chat_store import" in source


def test_tests_do_not_reintroduce_backend_short_import_path():
    test_sources = Path("tests").glob("test_*.py")

    for path in test_sources:
        if path.name == "test_api_server_alias_cleanup.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert 'import_module("chat_store")' not in source
        assert "sys.path.insert(0, str(BACKEND_DIR))" not in source


def test_non_compat_tests_do_not_import_legacy_api_modules():
    allowed_files = {
        "test_api_server_alias_cleanup.py",
        "test_backend_module_compat.py",
    }

    for path in Path("tests").glob("test_*.py"):
        if path.name in allowed_files:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    assert not (
                        name.startswith("backend.api_")
                        and name != "backend.api_server"
                    ), f"{path} imports legacy module {name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert not (
                    module.startswith("backend.api_")
                    and module != "backend.api_server"
                ), f"{path} imports legacy module {module}"


def test_runtime_code_uses_misc_helpers_without_api_prefix():
    for path in Path("backend").rglob("*.py"):
        if path.as_posix() in {
            "backend/api_misc_helpers.py",
            "backend/helpers/api_misc_helpers.py",
        }:
            continue
        source = path.read_text(encoding="utf-8")
        assert "backend.helpers.api_misc_helpers" not in source


def test_security_runtime_uses_env_runtime_for_env_helpers():
    source = Path("backend/core/security_runtime.py").read_text(encoding="utf-8")

    assert "from backend.core import env_runtime" in source
    assert "env_runtime.cors_settings" in source
    assert "env_runtime.is_loopback_host" in source
    assert "ctx._cors_settings" not in source
    assert "ctx._is_loopback_host" not in source


def test_session_summary_runtime_uses_model_config_runtime_for_api_keys():
    source = Path("backend/core/session_summary_runtime.py").read_text(encoding="utf-8")

    assert "model_config_runtime.resolve_model_api_key(" in source
    assert "model_config_runtime.normalize_model_config(" in source
    assert "ctx._resolve_model_api_key" not in source
    assert "ctx._normalize_model_config" not in source


def test_session_summary_runtime_keeps_pure_helpers_out_of_context():
    source = Path("backend/core/session_summary_runtime.py").read_text(encoding="utf-8")

    for dependency in (
        "_build_phase_summary_content",
        "_build_phase_summary_llm_prompt",
        "_clip_text",
        "_generate_session_phase_summary_memory",
        "_normalize_llm_text_content",
        "_summary_llm_enabled",
        "_summary_llm_timeout_seconds",
        "_summary_turns",
        "_try_llm_phase_summary_content",
    ):
        assert f'"{dependency}"' not in source
        assert f"ctx.{dependency}" not in source


def test_security_runtime_keeps_pure_helpers_out_of_context():
    source = Path("backend/core/security_runtime.py").read_text(encoding="utf-8")

    for dependency in (
        "_auth_token_preview",
        "HTTPException",
        "os",
        "_auth_token_is_weak",
        "_auth_token_hygiene_summary",
        "_build_auth_capabilities_for_role",
        "_build_auth_token_catalog_payload",
        "_build_security_status_payload",
        "_build_security_audit_summary_payload",
        "_ceil_seconds",
        "_content_hash",
        "_hash_secret",
        "_normalize_auth_role",
        "_role_rank",
        "_sanitize_log_value",
        "_sanitize_request_path",
        "_current_admin_api_token",
        "_current_share_link_secret",
        "_remote_management_rate_limit_applies",
        "_remote_management_rate_limit_principal",
        "_remote_management_rate_limit_status",
        "_require_remote_role",
        "_audit_security_event",
        "_share_link_secret_is_weak",
        "_share_link_secret_uses_default",
        "_configured_auth_token_map",
        "_configured_auth_token_records",
        "_request_auth_mode",
        "_request_auth_source",
        "_request_user_id",
        "_request_user_role",
        "_resolve_request_auth",
        "_extract_request_token",
        "_token_fingerprint",
        "_token_preview",
    ):
        assert f'"{dependency}"' not in source
        assert f"ctx.{dependency}" not in source
    assert "ctx.json" not in source
