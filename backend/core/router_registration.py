"""Router registration helpers for the FastAPI application.

The API server passes its module object as ``ctx`` so existing route builders
can keep using the same runtime functions while this wiring stays out of the
entrypoint.
"""

from __future__ import annotations

_registered_core_app_ids: set[int] = set()


def register_core_routers(ctx) -> None:
    app_id = id(ctx.app)
    if app_id in _registered_core_app_ids:
        return
    ctx.app.include_router(
        ctx.build_security_router(
            security_status_response_model=ctx.SecurityStatusResponse,
            auth_whoami_response_model=ctx.AuthWhoAmIResponse,
            auth_token_catalog_response_model=ctx.AuthTokenCatalogResponse,
            sso_config_response_model=ctx.SsoConfigResponse,
            sso_login_response_model=ctx.SsoLoginResponse,
            sso_callback_response_model=ctx.SsoCallbackResponse,
            security_audit_event_list_response_model=ctx.SecurityAuditEventListResponse,
            security_audit_cleanup_response_model=ctx.SecurityAuditCleanupResponse,
            security_audit_action_catalog_response_model=ctx.SecurityAuditActionCatalogResponse,
            security_audit_summary_response_model=ctx.SecurityAuditSummaryResponse,
            security_audit_siem_export_response_model=ctx.SecurityAuditSiemExportResponse,
            security_audit_aggregate_report_response_model=ctx.SecurityAuditAggregateReportResponse,
            security_audit_archive_policy_response_model=ctx.SecurityAuditArchivePolicyResponse,
            security_audit_legal_hold_response_model=ctx.SecurityAuditLegalHoldResponse,
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_admin=ctx._require_remote_admin,
            security_status_payload=lambda: ctx._security_status_payload(),
            auth_whoami_payload=lambda auth: ctx.build_auth_whoami_payload(
                auth,
                default_role="admin",
                normalize_auth_role=ctx._normalize_auth_role,
                role_rank=ctx._role_rank,
            ),
            auth_token_catalog_payload=lambda: ctx._auth_token_catalog_payload(),
            sso_config_payload=lambda: ctx._sso_config_payload(),
            save_sso_config_payload=lambda payload: ctx._save_sso_config_payload(
                payload
            ),
            sso_login_payload=ctx._sso_login_payload,
            sso_callback_payload=ctx._sso_callback_payload,
            security_audit_events_payload=lambda **kwargs: (
                ctx._security_audit_events_payload(**kwargs)
            ),
            security_audit_action_catalog_payload=lambda **kwargs: (
                ctx._security_audit_action_catalog_payload(**kwargs)
            ),
            security_audit_summary_payload=lambda **kwargs: (
                ctx._security_audit_summary_payload(**kwargs)
            ),
            security_audit_siem_export_payload=lambda **kwargs: (
                ctx._security_audit_siem_export_payload(**kwargs)
            ),
            security_audit_aggregate_report_payload=lambda **kwargs: (
                ctx._security_audit_aggregate_report_payload(**kwargs)
            ),
            security_audit_archive_policy_payload=lambda **kwargs: (
                ctx._security_audit_archive_policy_payload(**kwargs)
            ),
            security_audit_legal_hold_payload=lambda **kwargs: (
                ctx._security_audit_legal_hold_payload(**kwargs)
            ),
            cleanup_security_audit_events=lambda **kwargs: (
                ctx._cleanup_security_audit_events(**kwargs)
            ),
            audit_security_event=ctx._audit_security_event,
            get_security_audit_store_count=lambda: (
                ctx._get_security_audit_store().count_events()
            ),
            get_memory_security_audit_event_count=lambda: len(
                ctx._security_audit_events
            ),
            logger=ctx.logger,
        )
    )
    ctx.app.include_router(
        ctx.build_identity_router(
            identity_catalog_response_model=ctx.IdentityCatalogResponse,
            organization_response_model=ctx.OrganizationResponse,
            user_response_model=ctx.UserResponse,
            membership_response_model=ctx.MembershipResponse,
            sync_external_identity_response_model=ctx.SyncExternalIdentityResponse,
            upsert_organization_request_model=ctx.UpsertOrganizationRequest,
            upsert_user_request_model=ctx.UpsertUserRequest,
            set_membership_request_model=ctx.SetMembershipRequest,
            sync_external_identity_request_model=ctx.SyncExternalIdentityRequest,
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_admin=ctx._require_remote_admin,
            identity_store=ctx._get_identity_store,
            sync_external_identity_payload=ctx._sync_external_identity_payload,
            audit_security_event=ctx._audit_security_event,
            now=ctx.time.time,
            logger=ctx.logger,
        )
    )

    ctx.app.include_router(
        ctx.build_access_router(
            resource_grant_response_model=ctx.ResourceGrantResponse,
            resource_grant_list_response_model=ctx.ResourceGrantListResponse,
            resource_access_response_model=ctx.ResourceAccessResponse,
            role_permission_matrix_response_model=ctx.RolePermissionMatrixResponse,
            upsert_resource_grant_request_model=ctx.UpsertResourceGrantRequest,
            delete_resource_grant_request_model=ctx.DeleteResourceGrantRequest,
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_admin=ctx._require_remote_admin,
            access_store=ctx._get_resource_access_store,
            identity_store=ctx._get_identity_store,
            role_permission_matrix_payload=ctx._role_permission_matrix_payload,
            audit_security_event=ctx._audit_security_event,
            now=ctx.time.time,
            logger=ctx.logger,
        )
    )

    ctx.app.include_router(
        ctx.build_operations_router(
            runtime_operations_response_model=ctx.RuntimeOperationsResponse,
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_admin=ctx._require_remote_admin,
            runtime_request_metrics_payload=lambda: (
                ctx._runtime_request_metrics_payload()
            ),
            runtime_task_summary_payload=lambda: ctx._runtime_task_summary_payload(),
            runtime_operations_payload=lambda: ctx._runtime_operations_payload(),
            get_runtime_started_at=lambda: ctx._runtime_started_at,
            sync_runtime_secret_from_store=lambda env_name, config_key: (
                ctx._sync_runtime_secret_from_store(env_name, config_key)
            ),
            validate_tavily_api_key=lambda api_key: ctx._validate_tavily_api_key(
                api_key
            ),
            get_app_config_store=lambda: ctx._get_app_config_store(),
            upsert_cloud_model_api_key=lambda api_key_ref, api_key: (
                ctx._upsert_cloud_model_api_key(api_key_ref, api_key)
            ),
            delete_cloud_model_api_key=lambda api_key_ref: (
                ctx._delete_cloud_model_api_key(api_key_ref)
            ),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            audit_security_event=ctx._audit_security_event,
            tasks=lambda: ctx._tasks,
            tasks_lock=ctx._tasks_lock,
            prune_task_records_locked=ctx._prune_task_records_locked,
            persist_task_record=ctx._persist_task_record,
            prune_persisted_tasks=ctx._prune_persisted_tasks,
            run_task=ctx._run_task,
            enqueue_task=ctx.enqueue_task,
            spawn_background_task=ctx.asyncio.create_task,
            logger=ctx.logger,
            task_backend=lambda: ctx.TASK_BACKEND,
            enqueue_external_task=ctx.enqueue_external_task,
            integrator_scheduler_tick_lock=ctx._integrator_scheduler_tick_lock,
            integrator_scheduler_config=ctx._integrator_scheduler_config_from_env,
        )
    )
    ctx.app.include_router(
        ctx.build_prompt_router(
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_editor=ctx._require_remote_editor,
            list_system_prompts=lambda: ctx.importlib.import_module(
                "chat_store"
            ).get_all_system_prompts(),
            create_system_prompt=lambda *args, **kwargs: ctx.importlib.import_module(
                "chat_store"
            ).create_system_prompt(*args, **kwargs),
            update_system_prompt=lambda *args, **kwargs: ctx.importlib.import_module(
                "chat_store"
            ).update_system_prompt(*args, **kwargs),
            delete_system_prompt=lambda prompt_id: ctx.importlib.import_module(
                "chat_store"
            ).delete_system_prompt(prompt_id),
            activate_system_prompt=lambda prompt_id: ctx.importlib.import_module(
                "chat_store"
            ).activate_system_prompt(prompt_id),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            build_doc_pipeline=lambda vector_store_path: ctx.importlib.import_module(
                "doc_pipeline"
            ).DocPipeline(vector_store_path=vector_store_path),
            audit_security_event=ctx._audit_security_event,
            logger=ctx.logger,
        )
    )
    ctx.app.include_router(
        ctx.build_kb_router(
            backend_dir=str(ctx.BACKEND_DIR),
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_editor=ctx._require_remote_editor,
            require_remote_admin=ctx._require_remote_admin,
            effective_vector_store_path=lambda path: ctx._effective_vector_store_path(
                path
            ),
            resolve_project_subdir=lambda candidate: ctx._resolve_project_subdir(
                candidate
            ),
            resolve_deletable_knowledge_base=lambda candidate: (
                ctx._resolve_deletable_knowledge_base(candidate)
            ),
            active_vector_store_id=lambda: ctx._active_vector_store_id(),
            faiss_safe_store_path=lambda target_path: ctx._faiss_safe_store_path(
                target_path
            ),
            build_doc_pipeline=lambda vector_store_path: ctx.importlib.import_module(
                "doc_pipeline"
            ).DocPipeline(vector_store_path=vector_store_path),
            list_kb_chunks_payload=lambda **kwargs: ctx.list_kb_chunks_payload(
                **kwargs
            ),
            update_kb_chunk_payload=lambda **kwargs: ctx.update_kb_chunk_payload(
                **kwargs
            ),
            delete_kb_chunk_payload=lambda **kwargs: ctx.delete_kb_chunk_payload(
                **kwargs
            ),
            knowledge_bases_payload=lambda **kwargs: ctx.knowledge_bases_payload(
                **kwargs
            ),
            kb_health_payload=lambda *args, **kwargs: ctx.kb_health_payload(
                *args, **kwargs
            ),
            retrieval_test_payload=lambda *args, **kwargs: ctx.retrieval_test_payload(
                *args, **kwargs
            ),
            kb_collect_chunks=lambda *args, **kwargs: ctx._kb_collect_chunks(
                *args, **kwargs
            ),
            filter_kb_chunks=lambda *args, **kwargs: ctx.filter_kb_chunks(
                *args, **kwargs
            ),
            kb_docstore_dict=lambda *args, **kwargs: ctx._kb_docstore_dict(
                *args, **kwargs
            ),
            kb_safe_metadata=lambda *args, **kwargs: ctx._kb_safe_metadata(
                *args, **kwargs
            ),
            kb_rebuild_from_documents=lambda *args, **kwargs: (
                ctx._kb_rebuild_from_documents(*args, **kwargs)
            ),
            doc_factory=lambda page_content, metadata: ctx.importlib.import_module(
                "langchain_core.documents"
            ).Document(page_content=page_content, metadata=metadata),
            delete_kb_directory=lambda *args, **kwargs: ctx.delete_kb_directory(
                *args, **kwargs
            ),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            content_hash=lambda value: ctx._content_hash(value),
            audit_security_event=ctx._audit_security_event,
            logger=ctx.logger,
        )
    )
    _registered_core_app_ids.add(app_id)


def register_deferred_routers(ctx) -> None:
    """Register routers that depend on late-defined helpers or request models."""

    async def _enqueue_external_task(record):
        enqueue = getattr(ctx, "enqueue_external_task", None)
        if enqueue is None:
            from backend.tasks.enqueue import enqueue_arq_task

            return await enqueue_arq_task(record)
        return await enqueue(record)

    async def _stage_upload_files(*args, **kwargs):
        kwargs.setdefault(
            "staging_dir",
            getattr(ctx, "DOCUMENT_UPLOAD_STAGING_DIR", None),
        )
        return await ctx.stage_upload_files(*args, **kwargs)

    ctx.app.include_router(
        ctx.build_chat_router(
            prepare_chat_route_runtime=ctx.prepare_chat_route_runtime,
            sse_streaming_response=ctx.sse_streaming_response,
            stream_parallel_sse=ctx.stream_parallel_sse,
            stream_single_sse=ctx.stream_single_sse,
            build_parallel_agent_streams=ctx.build_parallel_agent_streams,
            build_single_agent_stream=ctx.build_single_agent_stream,
            list_mcp_server_catalog=lambda: ctx.list_mcp_server_catalog(),
            list_mcp_server_runtime_health=lambda: ctx.list_mcp_server_runtime_health(),
            get_mcp_runtime_health_history=lambda limit: (
                ctx.get_mcp_runtime_health_history(limit)
            ),
            default_mcp_server_names=lambda: ctx.default_mcp_server_names(),
            current_mcp_approvals_payload=lambda: (
                ctx.current_mcp_approved_connectors_payload()
            ),
            approve_runtime_mcp_connector=lambda connector_name: (
                ctx.approve_runtime_mcp_connector(connector_name)
            ),
            revoke_runtime_mcp_connector=lambda connector_name: (
                ctx.revoke_runtime_mcp_connector(connector_name)
            ),
            resolve_active_prompt_runtime=ctx._resolve_active_prompt_runtime,
            validate_chat_payload=ctx._validate_chat_payload_impl,
            prepare_chat_files=lambda files: ctx._prepare_chat_files_impl(
                files,
                config=ctx.ChatFileConfig(
                    context_end_marker=ctx.CHAT_FILE_CONTEXT_END_MARKER,
                    context_start_marker=ctx.CHAT_FILE_CONTEXT_START_MARKER,
                    max_bytes=ctx.CHAT_FILE_MAX_BYTES,
                    max_chars_per_file=ctx.CHAT_FILE_MAX_CHARS_PER_FILE,
                    max_count=ctx.CHAT_FILE_MAX_COUNT,
                    max_total_chars=ctx.CHAT_FILE_MAX_TOTAL_CHARS,
                    preview_chars=ctx.CHAT_ATTACHMENT_PREVIEW_CHARS,
                    supported_extensions=frozenset(ctx.SUPPORTED_CHAT_FILE_EXTENSIONS),
                ),
                logger=ctx.logger,
            ),
            build_user_input=ctx._build_user_input_impl,
            base_model_payload=ctx._base_model_payload,
            normalize_model_config=ctx._normalize_model_config,
            model_config_payload=ctx._model_config_payload,
            invoke_agent_stream=lambda *args, **kwargs: ctx._invoke_agent_stream(
                *args, **kwargs
            ),
            clear_agent_cache=lambda: ctx._clear_agent_cache(),
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_admin=ctx._require_remote_admin,
            access_store=ctx._get_resource_access_store,
            identity_store=ctx._get_identity_store,
            audit_security_event=ctx._audit_security_event,
            chat_request_model=ctx.ChatRequest,
            single_chat_request_model=ctx.SingleChatRequest,
            logger=ctx.logger,
        )
    )
    ctx.app.include_router(
        ctx.build_session_router(
            require_remote_share_secret=ctx._require_remote_share_secret,
            current_share_link_secret=ctx._current_share_link_secret,
            share_link_response_model=ctx.ShareLinkResponse,
            share_link_ttl_seconds=lambda: ctx.SHARE_LINK_TTL_SECONDS,
            request_client_ip=ctx._request_client_ip,
            request_user_agent=ctx._request_user_agent,
            audit_security_event=ctx._audit_security_event,
            token_fingerprint=ctx._token_fingerprint,
            encode_share_token=ctx.encode_share_token,
            build_share_url=ctx.build_share_url,
            create_share_link_payload=ctx.create_share_link_payload,
            share_link_store=ctx._share_link_store,
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_editor=ctx._require_remote_editor,
            require_remote_admin=ctx._require_remote_admin,
            access_store=ctx._get_resource_access_store,
            identity_store=ctx._get_identity_store,
            now=ctx.time.time,
            workspaces_payload=ctx.workspaces_payload,
            session_update_requested=ctx.session_update_requested,
            create_session_record=ctx.create_session_record,
            reorder_sessions_payload=ctx.reorder_sessions_payload,
            deck_store=lambda: ctx._deck_store,
            tasks_lock=ctx._tasks_lock,
            tasks=lambda: ctx._tasks,
            suppressed_task_ids=ctx._suppressed_task_ids,
            prune_task_records_locked=ctx._prune_task_records_locked,
            get_task_store=ctx._get_task_store,
            artifact_store=lambda: ctx._artifact_store,
            build_session_messages_payload=ctx._build_session_messages_payload,
            build_answer_group_review_payload=ctx._build_answer_group_review_payload,
            collect_session_attachments=ctx._collect_session_attachments,
            find_session_attachment=ctx._find_session_attachment,
            session_attachments_payload=ctx.session_attachments_payload,
            attach_current_kb_status=ctx.attach_current_kb_status,
            get_attachment_promotion_task=ctx._get_attachment_promotion_task,
            prepare_attachment_promotion=ctx.prepare_attachment_promotion,
            task_record_payload=ctx.task_record_payload,
            enqueue_task=ctx.enqueue_task,
            task_backend=lambda: ctx.TASK_BACKEND,
            enqueue_external_task=ctx.enqueue_external_task,
            persist_task_record=ctx._persist_task_record,
            prune_persisted_tasks=ctx._prune_persisted_tasks,
            run_task=ctx._run_task,
            session_memory_payload=ctx.session_memory_payload,
            pin_session_memory_payload=ctx.pin_session_memory_payload,
            session_memory_updates=ctx.session_memory_updates,
            update_session_memory_payload=ctx.update_session_memory_payload,
            summarize_session_memory_payload=ctx.summarize_session_memory_payload,
            delete_session_memory_payload=ctx.delete_session_memory_payload,
            generate_session_phase_summary_memory=ctx._generate_session_phase_summary_memory,
            validate_chat_payload=ctx._validate_chat_payload_impl,
            base_model_payload=ctx._base_model_payload,
            normalize_model_config=ctx._normalize_model_config,
            model_config_payload=ctx._model_config_payload,
            chat_attachment_preview_chars=ctx.CHAT_ATTACHMENT_PREVIEW_CHARS,
            effective_vector_store_path=lambda path=None: (
                ctx._effective_vector_store_path(path)
            ),
            require_workspace_session=ctx._require_workspace_session,
            request_field_set=ctx._request_field_set,
            artifact_payload=ctx._artifact_payload,
            clear_agent_cache=ctx._clear_agent_cache,
            create_workspace_request_model=ctx.CreateWorkspaceRequest,
            update_workspace_request_model=ctx.UpdateWorkspaceRequest,
            create_session_request_model=ctx.CreateSessionRequest,
            update_session_request_model=ctx.UpdateSessionRequest,
            reorder_sessions_request_model=ctx.ReorderSessionsRequest,
            create_bookmark_request_model=ctx.CreateBookmarkRequest,
            set_message_feedback_request_model=ctx.SetMessageFeedbackRequest,
            truncate_session_messages_request_model=ctx.TruncateSessionMessagesRequest,
            import_session_messages_request_model=ctx.ImportSessionMessagesRequest,
            set_retrieval_feedback_request_model=ctx.SetRetrievalFeedbackRequest,
            pin_session_memory_request_model=ctx.PinSessionMemoryRequest,
            update_session_memory_request_model=ctx.UpdateSessionMemoryRequest,
            logger=ctx.logger,
        )
    )
    ctx.app.include_router(
        ctx.build_content_router(
            artifact_store=lambda: ctx._artifact_store,
            deck_store=lambda: ctx._deck_store,
            share_link_store=ctx._share_link_store,
            access_store=ctx._get_resource_access_store,
            identity_store=ctx._get_identity_store,
            tasks=lambda: ctx._tasks,
            tasks_lock=ctx._tasks_lock,
            suppressed_task_ids=ctx._suppressed_task_ids,
            prune_task_records_locked=ctx._prune_task_records_locked,
            persist_task_record=ctx._persist_task_record,
            prune_persisted_tasks=ctx._prune_persisted_tasks,
            get_app_config_store=ctx._get_app_config_store,
            get_task_store=ctx._get_task_store,
            run_task=ctx._run_task,
            enqueue_task=ctx.enqueue_task,
            task_record_payload=ctx.task_record_payload,
            list_tasks_payload=ctx.list_tasks_payload,
            task_history_limit=ctx.TASK_HISTORY_LIMIT,
            task_backend=lambda: ctx.TASK_BACKEND,
            enqueue_external_task=_enqueue_external_task,
            arq_queue_health_payload=ctx.arq_queue_health_payload,
            artifact_payload=ctx._artifact_payload,
            artifact_export_formats=ctx.artifact_export_formats,
            build_deck_artifact=ctx.build_deck_artifact,
            build_report_artifact=ctx.build_report_artifact,
            sync_deck_artifact=ctx.sync_deck_artifact,
            require_remote_viewer=ctx._require_remote_viewer,
            require_remote_editor=ctx._require_remote_editor,
            require_remote_admin=ctx._require_remote_admin,
            require_remote_share_secret=ctx._require_remote_share_secret,
            current_share_link_secret=ctx._current_share_link_secret,
            audit_security_event=ctx._audit_security_event,
            token_fingerprint=ctx._token_fingerprint,
            encode_share_token=ctx.encode_share_token,
            decode_share_token=ctx.decode_share_token,
            build_share_url=ctx.build_share_url,
            create_share_link_payload_fn=ctx.create_share_link_payload,
            share_link_ttl_seconds=lambda: ctx.SHARE_LINK_TTL_SECONDS,
            request_client_ip=ctx._request_client_ip,
            request_user_agent=ctx._request_user_agent,
            share_link_audit_payload=ctx._share_link_audit_payload,
            share_link_response_model=ctx.ShareLinkResponse,
            revoke_share_link_response_model=ctx.RevokeShareLinkResponse,
            share_link_audit_list_response_model=ctx.ShareLinkAuditListResponse,
            open_shared_resource_payload=ctx.open_shared_resource_payload,
            build_session_messages_payload=ctx._build_session_messages_payload,
            render_shared_session_html=ctx._render_shared_session_html,
            render_shared_deck_html=ctx._render_shared_deck_html,
            build_download_content_disposition=ctx._build_download_content_disposition,
            build_chat_report_title=ctx.build_chat_report_title,
            build_report_markdown=ctx.build_report_markdown,
            ensure_deckable_chat=ctx.ensure_deckable_chat,
            populate_chat_report_presentation=ctx.populate_chat_report_presentation,
            safe_report_filename=ctx.safe_report_filename,
            stage_upload_files=_stage_upload_files,
            build_upload_documents_task_record=lambda **kwargs: (
                ctx.build_upload_documents_task_record(**kwargs)
            ),
            cleanup_temp_paths=ctx.cleanup_temp_paths,
            upload_documents_response=ctx.upload_documents_response,
            effective_vector_store_path=lambda path=None: (
                ctx._effective_vector_store_path(path)
            ),
            resolve_report_messages=ctx._resolve_report_messages,
            resolve_active_prompt_runtime=ctx._resolve_active_prompt_runtime,
            normalize_model_config=ctx._resolve_runtime_model_config,
            build_deck=lambda **kwargs: ctx.build_deck(**kwargs),
            build_create_deck_kwargs=ctx.build_create_deck_kwargs,
            build_regenerate_deck_kwargs=lambda *args, **kwargs: (
                ctx.build_regenerate_deck_kwargs(*args, **kwargs)
            ),
            apply_deck_update=ctx.apply_deck_update,
            replace_deck_slide=ctx.replace_deck_slide,
            export_deck_payload=ctx.export_deck_payload,
            export_deck_to_pptx=ctx.export_deck_to_pptx,
            build_export_filename=ctx.build_export_filename,
            normalize_deck_theme=ctx.normalize_deck_theme,
            regenerate_deck_slide=lambda *args, **kwargs: ctx.regenerate_deck_slide(
                *args, **kwargs
            ),
            sync_deck_artifacts=ctx._sync_deck_artifacts,
            report_download_payload=ctx.report_download_payload,
            resolve_report_messages_fn=ctx._resolve_report_messages,
            persist_web_research_task_placeholder=ctx.persist_web_research_task_placeholder,
            persist_multi_agent_workflow_task_placeholder=(
                ctx.persist_multi_agent_workflow_task_placeholder
            ),
            document_upload_max_count=ctx.DOCUMENT_UPLOAD_MAX_COUNT,
            document_upload_max_file_bytes=ctx.DOCUMENT_UPLOAD_MAX_FILE_BYTES,
            document_upload_max_total_bytes=ctx.DOCUMENT_UPLOAD_MAX_TOTAL_BYTES,
            create_task_request_model=ctx.CreateTaskRequest,
            create_multi_agent_workflow_request_model=ctx.CreateMultiAgentWorkflowTaskRequest,
            approval_policy_request_model=ctx.ApprovalPolicyRequest,
            approval_task_decision_request_model=ctx.ApprovalTaskDecisionRequest,
            create_deck_request_model=ctx.CreateDeckRequest,
            update_deck_request_model=ctx.UpdateDeckRequest,
            regenerate_deck_slide_request_model=ctx.RegenerateDeckSlideRequest,
            generate_report_request_model=ctx.GenerateReportRequest,
            update_artifact_request_model=ctx.UpdateArtifactRequest,
            generate_artifact_request_model=ctx.GenerateArtifactRequest,
            logger=ctx.logger,
        )
    )
