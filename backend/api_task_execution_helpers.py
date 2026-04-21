import asyncio
import os
import tempfile
from dataclasses import asdict
from typing import Any, Awaitable, Callable

from backend.api_task_store import TaskRecord
from search_runtime import run_deep_research
from search_runtime.service import describe_runtime_error, run_web_research

WEB_RESEARCH_PLACEHOLDER_TEXT = (
    "已发起联网研究任务，系统会整理实时网页来源，并在任务完成后展示摘要。"
)


def _web_research_message_context(record: TaskRecord) -> dict[str, str]:
    return {
        "query": str(record.params.get("query") or "").strip(),
        "panel_id": str(record.params.get("panel_id") or "").strip(),
        "answer_group_id": str(record.params.get("answer_group_id") or "").strip(),
        "model_id": str(record.params.get("model_id") or "web_research").strip()
        or "web_research",
    }


def persist_web_research_task_placeholder(
    record: TaskRecord,
    *,
    db_path: str = "./chat_history.db",
) -> None:
    from backend.chat_store import SQLiteChatMessageHistory

    session_id = str(record.session_id or "").strip()
    if not session_id:
        return

    context = _web_research_message_context(record)
    query = context["query"]
    panel_id = context["panel_id"]
    answer_group_id = context["answer_group_id"]

    if not query or not panel_id or not answer_group_id:
        return

    history = SQLiteChatMessageHistory(session_id=session_id, db_path=db_path)
    history.add_user_message_once(query, answer_group_id=answer_group_id)
    history.delete_ai_messages_for_answer_group(panel_id, answer_group_id)
    history.add_ai_message(
        WEB_RESEARCH_PLACEHOLDER_TEXT,
        model_id=context["model_id"],
        panel_id=panel_id,
        answer_group_id=answer_group_id,
        task_id=record.task_id,
        task_type=record.task_type,
    )


def persist_web_research_task_result(
    record: TaskRecord,
    *,
    content: str,
    sources: list[dict[str, Any]] | None = None,
    workflow_nodes: list[dict[str, Any]] | None = None,
    db_path: str = "./chat_history.db",
) -> None:
    from backend.chat_store import SQLiteChatMessageHistory

    session_id = str(record.session_id or "").strip()
    if not session_id:
        return

    context = _web_research_message_context(record)
    panel_id = context["panel_id"]
    answer_group_id = context["answer_group_id"]

    if not panel_id or not answer_group_id or not str(content or "").strip():
        return

    history = SQLiteChatMessageHistory(session_id=session_id, db_path=db_path)
    history.delete_ai_messages_for_answer_group(panel_id, answer_group_id)
    history.add_ai_message(
        str(content).strip(),
        model_id=context["model_id"],
        panel_id=panel_id,
        answer_group_id=answer_group_id,
        sources=sources or [],
        workflow_nodes=workflow_nodes or [],
        task_id=record.task_id,
        task_type=record.task_type,
    )


def _model_config_value(config: Any, key: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _artifact_value(artifact: Any, key: str, default: Any = None) -> Any:
    if isinstance(artifact, dict):
        return artifact.get(key, default)
    return getattr(artifact, key, default)


def _build_research_knowledge_search(
    vector_store_path: str | None,
) -> Callable[[str], list[Any]] | None:
    normalized_path = str(vector_store_path or "").strip()
    if not normalized_path:
        return None

    def _search(query: str) -> list[Any]:
        from backend.doc_pipeline import DocPipeline

        pipeline = DocPipeline(vector_store_path=normalized_path)
        try:
            pipeline.load_store()
        except Exception:
            return []
        try:
            return pipeline.search_with_rerank(query, k=3, fetch_k=8)
        except Exception:
            return []

    return _search


async def run_analyze_knowledge_base_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    effective_vector_store_path: Callable[[str | None], str],
) -> None:
    from backend.doc_pipeline import DocPipeline

    vector_store_path = effective_vector_store_path(
        str(record.params.get("vector_store_path") or "").strip() or None
    )
    pipeline = DocPipeline(vector_store_path=vector_store_path)

    await set_progress(30)
    await asyncio.sleep(0)
    pipeline.load_store()
    stats = pipeline.get_stats()
    await set_progress(80)

    total = stats.get("total_docs", 0)
    store_path = stats.get("store_path", vector_store_path)
    record.result = f"知识库分析完成，共 {total} 个文档片段，存储路径：{store_path}"


async def run_generate_report_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    resolve_report_messages: Callable[..., list[Any]],
    ensure_deckable_chat: Callable[[list[Any]], Any],
    build_chat_report_title: Callable[[list[Any]], str],
    build_report_markdown: Callable[[list[Any], str], str],
    build_report_artifact: Callable[..., Any],
    save_artifact: Callable[[Any], Any],
) -> None:
    from backend.chat_store import SQLiteChatMessageHistory

    session_id = record.session_id or "default"
    history = SQLiteChatMessageHistory(session_id=session_id)
    answer_group_id = str(record.params.get("answer_group_id") or "").strip()
    panel_id = str(record.params.get("panel_id") or "").strip()

    await set_progress(25)
    try:
        messages = resolve_report_messages(
            history,
            answer_group_id=answer_group_id,
            panel_id=panel_id,
        )
    except KeyError as exc:
        raise ValueError("未找到对应的报告消息范围。") from exc

    if not messages:
        raise ValueError("该会话没有可用于生成报告的消息。")

    await set_progress(55)
    qa_pairs = ensure_deckable_chat(messages)
    title = build_chat_report_title(messages)
    markdown = build_report_markdown(messages, title)
    artifact = build_report_artifact(
        session_id=session_id,
        title=title,
        markdown=markdown,
        qa_pairs=qa_pairs,
        answer_group_id=answer_group_id,
        panel_id=panel_id,
    )
    save_artifact(artifact)

    params = dict(record.params or {})
    params["report_title"] = title
    params["report_markdown"] = markdown
    params["artifact_id"] = str(_artifact_value(artifact, "artifact_id", "") or "")
    params["report_scope"] = "answer_group" if answer_group_id else "session"
    if answer_group_id:
        params["answer_group_id"] = answer_group_id
    if panel_id:
        params["panel_id"] = panel_id
    record.params = params

    await set_progress(90)
    record.result = f"报告《{title}》已生成，可预览或下载。"


async def run_generate_deck_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    resolve_report_messages: Callable[..., list[Any]],
    normalize_model_config: Callable[[Any], Any],
    resolve_active_prompt_runtime: Callable[[bool], tuple[Any, Any, Any]],
    build_deck: Callable[..., Awaitable[Any]],
    save_deck: Callable[[Any], Any],
    build_deck_artifact: Callable[[Any], Any],
    save_artifact: Callable[[Any], Any],
) -> None:
    from backend.chat_store import SQLiteChatMessageHistory

    session_id = str(record.session_id or "").strip()
    if not session_id:
        raise ValueError("generate_deck task requires a session_id.")

    raw_panel_config = record.params.get("panel_config")
    if raw_panel_config is None:
        raise ValueError("generate_deck task requires panel_config.")

    answer_group_id = str(record.params.get("answer_group_id") or "").strip()
    panel_id = str(record.params.get("panel_id") or "").strip()
    knowledge_base_enabled = bool(record.params.get("knowledge_base_enabled", True))
    theme = str(record.params.get("theme") or "default").strip() or "default"

    target_slide_count_raw = record.params.get("target_slide_count", 8)
    try:
        target_slide_count = max(4, min(10, int(target_slide_count_raw)))
    except (TypeError, ValueError):
        target_slide_count = 8

    await set_progress(20)
    history = SQLiteChatMessageHistory(session_id=session_id)
    try:
        messages = resolve_report_messages(
            history,
            answer_group_id=answer_group_id,
            panel_id=panel_id,
        )
    except KeyError as exc:
        raise ValueError("Requested deck scope was not found.") from exc

    if not messages:
        raise ValueError("No usable messages were found for deck generation.")

    await set_progress(45)
    panel_config = normalize_model_config(raw_panel_config)
    system_prompt, vector_store_path, _ = resolve_active_prompt_runtime(
        knowledge_base_enabled
    )
    deck = await build_deck(
        session_id=session_id,
        messages=messages,
        panel_config=panel_config,
        knowledge_base_enabled=knowledge_base_enabled,
        target_slide_count=target_slide_count,
        vector_store_path=vector_store_path,
        system_prompt=system_prompt,
        theme=theme,
        source_answer_group_id=answer_group_id,
        source_panel_id=panel_id,
    )

    await set_progress(85)
    save_deck(deck)
    artifact = build_deck_artifact(deck)
    save_artifact(artifact)

    params = dict(record.params or {})
    params["deck_id"] = getattr(deck, "deck_id", "")
    params["deck_title"] = getattr(getattr(deck, "meta", None), "title", "")
    params["artifact_id"] = str(_artifact_value(artifact, "artifact_id", "") or "")
    params["deck_scope"] = "answer_group" if answer_group_id else "session"
    if answer_group_id:
        params["answer_group_id"] = answer_group_id
    if panel_id:
        params["panel_id"] = panel_id
    record.params = params
    record.result = (
        f"Deck '{params['deck_title'] or params['deck_id'] or 'draft'}' is ready to review."
    )


async def run_upload_documents_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    update_progress: Callable[[TaskRecord, int], None],
    effective_vector_store_path: Callable[[str | None], str],
    clear_agent_cache: Callable[[], Awaitable[None]],
    logger: Any,
) -> None:
    from backend.doc_pipeline import DocPipeline

    file_paths = [str(path) for path in record.params.get("temp_paths", []) if path]
    original_names = [str(name) for name in record.params.get("file_names", []) if name]

    if not file_paths:
        raise ValueError("未找到可导入的临时文件。")

    vector_store_path = effective_vector_store_path(
        str(record.params.get("vector_store_path") or "").strip() or None
    )
    pipeline = DocPipeline(vector_store_path=vector_store_path)

    await set_progress(15)
    count = await asyncio.to_thread(
        pipeline.ingest,
        file_paths,
        lambda progress: update_progress(record, progress),
    )

    for temp_path in file_paths:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("task_id=%s 临时文件删除失败: %s", record.task_id, temp_path)

    uploaded_count = len(original_names) or len(file_paths)
    record.result = (
        f"已导入 {uploaded_count} 个文件，共 {count} 个文档片段，知识库路径：{vector_store_path}"
    )
    await clear_agent_cache()


async def run_promote_attachment_to_kb_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    update_progress: Callable[[TaskRecord, int], None],
    effective_vector_store_path: Callable[[str | None], str],
    chat_file_suffix: Callable[[str], str],
    decode_data_url: Callable[[str, str], bytes],
    clear_agent_cache: Callable[[], Awaitable[None]],
    logger: Any,
) -> None:
    from backend.doc_pipeline import DocPipeline
    from backend.chat_store import DEFAULT_WORKSPACE_ID, get_session

    attachment_name = str(record.params.get("attachment_name") or "").strip()
    attachment_data_url = str(record.params.get("attachment_data_url") or "").strip()
    attachment_kind = str(record.params.get("attachment_kind") or "").strip()
    workspace_id = str(record.params.get("workspace_id") or "").strip()

    if attachment_kind != "file":
        raise ValueError("Only file attachments can be promoted to the knowledge base.")
    if not attachment_name or not attachment_data_url:
        raise ValueError("Attachment payload is incomplete.")
    if workspace_id and str(record.session_id or "").strip():
        session = get_session(str(record.session_id or "").strip())
        if session is None:
            raise ValueError("Attachment source session was not found.")
        session_workspace_id = str(session.get("workspace_id") or DEFAULT_WORKSPACE_ID)
        if session_workspace_id != workspace_id:
            raise ValueError(
                "Attachment source session no longer belongs to the requested workspace."
            )

    suffix = chat_file_suffix(attachment_name)
    payload = decode_data_url(attachment_data_url, attachment_name)
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)

        vector_store_path = effective_vector_store_path(
            str(record.params.get("vector_store_path") or "").strip() or None
        )
        pipeline = DocPipeline(vector_store_path=vector_store_path)

        await set_progress(15)
        count = await asyncio.to_thread(
            pipeline.ingest,
            [temp_path],
            lambda progress: update_progress(record, progress),
        )

        record.result = (
            f"Attachment {attachment_name} has been added to the knowledge base. "
            f"Chunks: {count}. Path: {vector_store_path}"
        )
        await clear_agent_cache()
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning(
                "task_id=%s failed to delete promoted attachment temp file: %s",
                record.task_id,
                temp_path,
            )


async def run_placeholder_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
) -> None:
    for pct in (20, 50, 80):
        await asyncio.sleep(0.5)
        await set_progress(pct)
    record.result = f"任务 '{record.task_type}' 已完成（通用执行路径）"


async def run_web_research_task(
    record: TaskRecord,
    *,
    set_progress: Callable[[int], Awaitable[None]],
    normalize_model_config: Callable[[Any], Any] | None = None,
    create_llm: Callable[..., Any] | None = None,
) -> None:
    query = str(record.params.get("query") or "").strip()
    if not query:
        raise ValueError("web_research 任务缺少 query 参数。")

    research_mode = str(record.params.get("research_mode") or "").strip().lower() or "quick"
    provider = str(record.params.get("provider") or "").strip() or None
    raw_providers = record.params.get("providers")
    providers = (
        [str(item).strip() for item in raw_providers if str(item).strip()]
        if isinstance(raw_providers, list)
        else None
    )
    search_depth = str(record.params.get("search_depth") or "").strip() or "advanced"
    time_range = str(record.params.get("time_range") or "").strip() or None
    max_results_raw = record.params.get("max_results", 8)
    try:
        max_results = max(1, int(max_results_raw))
    except (TypeError, ValueError):
        max_results = 8

    max_rounds_raw = record.params.get("max_rounds", 2)
    try:
        max_rounds = max(1, min(2, int(max_rounds_raw)))
    except (TypeError, ValueError):
        max_rounds = 2

    max_results_per_query_raw = record.params.get("max_results_per_query", 4)
    try:
        max_results_per_query = max(1, min(8, int(max_results_per_query_raw)))
    except (TypeError, ValueError):
        max_results_per_query = 4

    try:
        if research_mode == "deep":
            raw_panel_config = record.params.get("panel_config")
            if raw_panel_config is None:
                raise ValueError("deep research requires panel_config.")

            panel_config = (
                normalize_model_config(raw_panel_config)
                if callable(normalize_model_config)
                else raw_panel_config
            )
            provider_name = (
                str(
                    _model_config_value(panel_config, "connection_type")
                    or _model_config_value(panel_config, "provider")
                    or "ollama"
                ).strip()
                or "ollama"
            )
            model_name = str(_model_config_value(panel_config, "model") or "").strip()
            base_url = str(_model_config_value(panel_config, "base_url") or "").strip()
            api_key = str(_model_config_value(panel_config, "api_key") or "").strip()
            temperature = float(_model_config_value(panel_config, "temperature", 0.3) or 0.3)

            if callable(create_llm):
                llm = create_llm(
                    provider_name,
                    model_name,
                    base_url,
                    api_key,
                    temperature,
                )
            else:
                from backend.agent_core import get_llm

                llm = get_llm(
                    provider_name,
                    model_name,
                    base_url,
                    api_key,
                    temperature,
                )

            knowledge_search = None
            if bool(record.params.get("use_kb_context", False)):
                knowledge_search = _build_research_knowledge_search(
                    str(record.params.get("vector_store_path") or "").strip() or None
                )

            await set_progress(15)
            research = await run_deep_research(
                query,
                llm=llm,
                providers=providers or ([provider] if provider else None),
                max_rounds=max_rounds,
                max_results_per_query=max_results_per_query,
                time_range=time_range,
                knowledge_search=knowledge_search,
            )
            await set_progress(55)
        else:
            await set_progress(25)
            research = await run_web_research(
                query,
                max_results=max_results,
                provider=provider,
                providers=providers,
                search_depth=search_depth,
                time_range=time_range,
            )
    except Exception as exc:
        raise ValueError(describe_runtime_error(exc)) from exc

    await set_progress(85)
    source_items = [
        source.to_source_item(index)
        for index, source in enumerate(research.sources, start=1)
    ]
    workflow_nodes = [
        dict(node)
        for node in (research.workflow_nodes or [])
        if isinstance(node, dict)
    ]
    record.params["research_mode"] = research_mode
    record.params["research_sources"] = source_items
    record.params["research_provider"] = research.provider
    record.params["research_provider_summary"] = research.provider_summary or research.provider
    record.params["research_summary"] = research.summary or research.answer
    record.params["research_findings"] = [asdict(item) for item in research.findings]
    record.params["research_contradictions"] = [asdict(item) for item in research.contradictions]
    record.params["research_rounds"] = [asdict(item) for item in research.rounds]
    record.params["research_caveats"] = list(research.caveats or [])
    if research.research_intent is not None:
        record.params["research_intent"] = asdict(research.research_intent)
    if research.research_plan is not None:
        record.params["research_plan"] = asdict(research.research_plan)
    record.params["research_workflow_nodes"] = workflow_nodes
    record.result = research.to_text()
    persist_web_research_task_result(
        record,
        content=record.result,
        sources=source_items,
        workflow_nodes=workflow_nodes,
    )
