"""Compatibility facade for agent runtime support helpers.

Focused runtime implementations live in the sibling modules.  This module
keeps the legacy ``from backend.agent.runtime_support import *`` contract alive
while the large historical ``agent_core.py`` surface is split into smaller
units.
"""

import json
import logging
import os
from typing import Any, Callable, Dict, Literal, Optional, TypedDict

from dotenv import load_dotenv

from backend.agent_mcp_helpers import load_mcp_tool_overrides
from backend.agent.connection import (
    OLLAMA_CONNECTION_ALIASES,
    OPENAI_COMPAT_CONNECTION_ALIASES,
    default_base_url_for_connection_type,
    default_model_for_connection_type,
    get_llm,
    normalize_connection_type,
)
from backend.agent.dashboard import (
    DASHBOARD_TRIGGER_KEYWORDS,
    DEFAULT_DASHBOARD_TEMPLATE,
    _build_attachment_dashboard_fallback,
    _build_dashboard_sources,
    _extract_attachment_evidence,
    _extract_attachment_sections,
    _extract_json_payload,
    _generate_dashboard_from_attachment,
    _generate_dashboard_from_knowledge,
    _normalize_dashboard_template,
    _parse_attachment_tables,
    _parse_numeric_dashboard_value,
    _render_attachment_dashboard_card,
    _render_dashboard_card,
    _sanitize_dashboard_payload,
    _should_generate_dashboard,
)
from backend.agent.dashboard_attachments import (
    _coerce_dashboard_cell_value,
    _is_rate_like_metric,
    _looks_like_date_dimension,
)
from backend.agent.fallbacks import (
    _build_generic_timeout_fallback,
    _build_kb_timeout_fallback,
    _build_resume_timeout_fallback,
)
from backend.agent.history import (
    CHAT_FILE_CONTEXT_END_MARKER,
    CHAT_FILE_CONTEXT_START_MARKER,
    _build_session_memory_message,
    _collapse_file_context_for_history,
    create_chat_message_history,
    _preserve_system_messages_with_recent_history,
    _session_memory_kind_label,
    _summarize_user_input_for_history,
    _trim_session_memory_content,
    clear_session_history,
    get_session_history,
)
from backend.agent.llm import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    PLACEHOLDER_SYSTEM_PROMPTS,
    _ThinkTagStreamFilter,
    _ainvoke_llm_with_timeout,
    _astream_llm_with_timeout,
    _compact_tool_result_for_prompt,
    _has_image_input,
    _is_timeout_error,
    _normalize_runtime_system_prompt,
    _record_llm_call_result,
    _stringify_stream_chunk_content,
    _stringify_user_input,
    _strip_think_tags,
)
from backend.agent.prompts import (
    BUSINESS_ANSWER_FORMAT_INSTRUCTIONS,
    BUSINESS_SECTION_ALIASES,
    BUSINESS_SECTION_ORDER,
    _build_missing_sources_business_answer,
    _canonical_business_section_name,
    _fallback_business_conclusion,
    _finalize_agent_result,
    _finalize_business_answer_output,
    _parse_business_sections,
    _render_business_answer,
    _render_business_sources,
)
from backend.agent.retrieval import (
    DEFAULT_KB_DOC_CHAR_LIMIT,
    DEFAULT_KB_FETCH_K,
    DEFAULT_KB_RETRIEVAL_MODE,
    DEFAULT_KB_TOP_K,
    _choose_kb_retrieval_mode,
    _dedupe_documents,
    _merge_same_source_chunks,
    _normalize_kb_retrieval_mode,
    _retrieve_kb_documents,
    _should_prefer_hybrid_retrieval,
    _trim_knowledge_doc_content,
)
from backend.agent.runtime_intent import (
    _looks_like_reasoning_only_output,
    _normalized_intent_text,
)
from backend.agent.runtime_plain_chat import (
    _astream_plain_text_answer,
    _build_plain_text_chat_messages,
    _direct_multimodal_answer,
    _direct_plain_text_answer,
    _heuristic_langgraph_tool_choice,
    _looks_like_resume_request,
    _plain_text_chat_timeout_seconds,
    _should_bypass_tools_for_plain_text_chat,
)
from backend.agent.sources import (
    GROUNDING_SOURCE_TYPES,
    _build_attachment_sources,
    _build_retrieval_meta_from_sources,
    _clip_attachment_source_snippet,
    _extract_sources_from_intermediate_steps,
    _extract_sources_from_marked_result,
    _merge_sources_with_attachments,
    _source_is_grounding_evidence,
)
from backend.agent.tool_registry import (
    BuiltinToolSpec,
    _build_enabled_tool_directory,
    get_builtin_tool_registry,
    list_enabled_builtin_tool_specs,
    register_builtin_tool,
    set_web_search_enabled,
)
from backend.chat_store import SQLiteChatMessageHistory, list_session_memory
from backend.doc_pipeline import DocPipeline

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from search_runtime.service import (
    fetch_webpage_text,
    quick_answer_text,
    rewrite_search_query_for_web,
    search_web_text,
)

load_dotenv()

logger = logging.getLogger(__name__)


# Re-export private helpers when split modules use star imports.
__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
