"""
FastAPI 后端 API 服务
提供 REST + SSE 端点，包装现有 agent_core / chat_store / doc_pipeline 模块
"""

import asyncio
import base64
import binascii
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import logging
import os
import pickle
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import uuid
from urllib.parse import unquote_to_bytes
from typing import Any, AsyncGenerator, Optional

import requests
from deck_service import (
    DeckSlide,
    SQLiteDeckStore,
    build_deck,
    build_report_markdown,
    build_export_filename,
    ensure_deckable_chat,
    export_deck_to_pptx,
)
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
UPLOAD_CHUNK_SIZE = 1024 * 1024
TASK_HISTORY_LIMIT = 200
KB_METADATA_TTL_SECONDS = 30
CHAT_FILE_CONTEXT_START_MARKER = "[[CHAT_FILE_CONTEXT_START]]"
CHAT_FILE_CONTEXT_END_MARKER = "[[CHAT_FILE_CONTEXT_END]]"
CHAT_FILE_MAX_COUNT = int(os.getenv("CHAT_FILE_MAX_COUNT", "6"))
CHAT_FILE_MAX_BYTES = int(os.getenv("CHAT_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
CHAT_FILE_MAX_CHARS_PER_FILE = int(
    os.getenv("CHAT_FILE_MAX_CHARS_PER_FILE", "8000")
)
CHAT_FILE_MAX_TOTAL_CHARS = int(os.getenv("CHAT_FILE_MAX_TOTAL_CHARS", "24000"))
SUPPORTED_CHAT_FILE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xls",
    ".xlsx",
}


@dataclass
class KBMetadataCacheEntry:
    expires_at: float
    value: dict[str, Any]


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _cors_settings() -> tuple[list[str], bool]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if not raw:
        return (
            [
                "http://127.0.0.1:5173",
                "http://localhost:5173",
                "http://127.0.0.1:8000",
                "http://localhost:8000",
            ],
            True,
        )

    origins = [item.strip() for item in raw.split(",") if item.strip()]
    if "*" in origins:
        return ["*"], False
    return origins, True


def _is_loopback_host(host: Optional[str]) -> bool:
    if not host:
        return False
    if host in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _hash_secret(secret: str) -> str:
    if not secret:
        return "no-key"
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]


def _content_hash(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        payload = value
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_project_subdir(candidate: str) -> Path:
    raw_path = Path(candidate).expanduser()
    if not raw_path.is_absolute():
        raw_path = PROJECT_ROOT / raw_path
    resolved = raw_path.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise HTTPException(
            status_code=403, detail="不允许访问项目目录之外的路径"
        ) from exc
    if resolved == PROJECT_ROOT:
        raise HTTPException(status_code=403, detail="不允许直接操作项目根目录")
    return resolved


def _faiss_safe_store_path(path: str | Path) -> str:
    target = Path(path)
    if not target.is_absolute():
        target = (PROJECT_ROOT / target).resolve()
    else:
        target = target.resolve()

    try:
        return str(target.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(target)


def _resolve_deletable_knowledge_base(candidate: str) -> Path:
    target_path = _resolve_project_subdir(candidate)

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Knowledge base path does not exist")
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Knowledge base path must be a directory")
    if not (target_path / "index.faiss").is_file():
        raise HTTPException(
            status_code=400,
            detail="Only directories containing index.faiss can be deleted",
        )

    return target_path


ALLOW_REMOTE_CLIENTS = _env_flag("ALLOW_REMOTE_CLIENTS", False)
_cors_origins, _cors_allow_credentials = _cors_settings()

app = FastAPI(title="AI 知识库 API", version="2.0.0")
_deck_store = SQLiteDeckStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def restrict_remote_clients(request: Request, call_next):
    if ALLOW_REMOTE_CLIENTS:
        return await call_next(request)

    client_host = request.client.host if request.client else None
    if _is_loopback_host(client_host):
        return await call_next(request)

    logger.warning(
        "Blocked non-local request host=%s path=%s", client_host, request.url.path
    )
    return JSONResponse(
        status_code=403,
        content={
            "code": "LOCAL_ONLY",
            "message": "当前服务默认只允许本机访问",
            "suggestion": "请使用 localhost/127.0.0.1 访问，或显式设置 ALLOW_REMOTE_CLIENTS=true 后再对外暴露",
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err = _classify_error(exc)
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "code": err["code"],
            "message": err["message"],
            "suggestion": err["suggestion"],
        },
    )


def _classify_error(e: Exception) -> dict:
    """将异常映射为用户友好的错误信息 + 错误码 + 恢复建议"""
    msg = str(e)
    if isinstance(e, ConnectionError) or any(
        kw in msg
        for kw in ("Connection refused", "ConnectError", "connect ECONNREFUSED")
    ):
        return {
            "code": "MODEL_UNAVAILABLE",
            "message": "模型服务暂时不可用",
            "suggestion": "请检查 Ollama 是否已启动，或稍后重试",
        }
    if any(
        kw in msg
        for kw in ("API Key", "api_key", "401", "Unauthorized", "authentication")
    ):
        return {
            "code": "AUTH_FAILED",
            "message": "API 认证失败",
            "suggestion": "请在设置中检查 API Key 是否正确",
        }
    if any(kw in msg for kw in ("timeout", "Timeout", "TimeoutError", "timed out")):
        return {
            "code": "TIMEOUT",
            "message": "请求超时，模型响应过慢",
            "suggestion": "请稍后重试，或尝试切换为响应更快的模型",
        }
    if any(kw in msg for kw in ("rate limit", "429", "quota")):
        return {
            "code": "RATE_LIMIT",
            "message": "API 调用频率已达上限",
            "suggestion": "请稍等片刻后重试",
        }
    if any(
        kw in msg.lower()
        for kw in (
            "does not support image",
            "doesn't support image",
            "image input",
            "vision",
            "multimodal",
            "input image",
            "unsupported image",
            "invalid image",
            "content type image_url",
            "image_url",
        )
    ):
        return {
            "code": "MODEL_NO_VISION",
            "message": "当前模型未接受图片输入，可能不支持视觉能力或当前接入方式不兼容。",
            "suggestion": "系统已实际尝试发送图片。请检查模型本身是否支持读图，以及当前 API/Base URL 是否支持多模态输入。",
        }
    if any(kw in msg for kw in ("Invalid model", "model not found", "404")):
        return {
            "code": "MODEL_NOT_FOUND",
            "message": "指定的模型不存在",
            "suggestion": "请在面板顶部的模型选择器中确认模型名称是否正确",
        }
    if any(kw in msg for kw in ("max iterations", "Agent stopped", "iteration limit")):
        return {
            "code": "MAX_ITERATIONS",
            "message": "模型工具调用次数超限，无法完成任务",
            "suggestion": "请尝试简化问题、减少工具依赖，或切换至其他模型后重试",
        }
    return {
        "code": "INTERNAL_ERROR",
        "message": "处理请求时发生异常",
        "suggestion": "请尝试清除上下文或新建对话后重试",
    }


def _is_max_iterations_output(text: str) -> bool:
    """检测 AgentExecutor 返回的 max iterations 错误字符串"""
    lower = text.lower()
    return (
        "agent stopped due to max iterations" in lower
        or "agent stopped due to iteration limit" in lower
        or (lower.startswith("agent stopped") and "iteration" in lower)
    )


async def _fallback_generate(
    mc: "ModelConfig", user_message: str, tool_outputs: str
) -> str:
    """当 Agent 达到迭代上限时，用单次 LLM 调用基于已有工具结果生成回答"""
    from agent_core import get_llm

    try:
        llm = get_llm(
            provider=mc.provider,
            model_name=mc.model,
            base_url=mc.base_url,
            api_key=mc.api_key if mc.api_key else None,
            temperature=mc.temperature,
        )
        fallback_prompt = f"""你是一个企业知识库助手。以下是工具已收集到的信息，请基于这些信息直接回答用户问题，用中文作答。

用户问题：{user_message}

工具收集到的信息：
{tool_outputs[:4000]}

请基于以上信息给出完整、清晰的回答："""
        response = await llm.ainvoke(fallback_prompt)
        return response.content.strip()
    except Exception as exc:
        logger.warning("Fallback generate failed: %s", exc)
        return (
            "抱歉，模型处理时间过长，未能生成完整回答。请尝试简化问题或切换模型后重试。"
        )


# ─────────────────────────────────────────────
# Pydantic 请求/响应模型
# ─────────────────────────────────────────────


class ModelConfig(BaseModel):
    panel_id: str
    provider: str = "local"
    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.3
    agent_mode: str = "auto"


class ImageInput(BaseModel):
    name: str
    media_type: str
    data_url: str


class FileInput(BaseModel):
    name: str
    media_type: str
    data_url: str
    size_bytes: int = 0


class ChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)
    models: list[ModelConfig]
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True


class SingleChatRequest(BaseModel):
    session_id: str
    message: str = ""
    images: list[ImageInput] = Field(default_factory=list)
    files: list[FileInput] = Field(default_factory=list)
    panel_config: ModelConfig
    web_search_enabled: bool = False
    knowledge_base_enabled: bool = True


class CreateSessionRequest(BaseModel):
    title: str = ""


class SaveConfigRequest(BaseModel):
    tavily_api_key: Optional[str] = None
    embedding_model: Optional[str] = None


class CreatePromptRequest(BaseModel):
    name: str
    content: str
    vector_store_id: Optional[str] = None
    dashboard_template: dict[str, Any] = Field(default_factory=dict)


class UpdatePromptRequest(BaseModel):
    name: str
    content: str
    vector_store_id: Optional[str] = None
    dashboard_template: dict[str, Any] = Field(default_factory=dict)


class GenerateReportRequest(BaseModel):
    session_id: str


class CreateDeckRequest(BaseModel):
    session_id: str
    panel_config: ModelConfig
    knowledge_base_enabled: bool = True
    target_slide_count: int = Field(default=8, ge=4, le=10)


class UpdateDeckRequest(BaseModel):
    title: Optional[str] = None
    slides: Optional[list[DeckSlide]] = None


class TestRetrievalRequest(BaseModel):
    query: str


class CreateTaskRequest(BaseModel):
    task_type: str  # e.g. "analyze_knowledge_base", "generate_report"
    params: dict = {}
    session_id: Optional[str] = None


# ─────────────────────────────────────────────
# 异步任务状态机
# ─────────────────────────────────────────────

from enum import Enum
from dataclasses import dataclass, field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskRecord:
    task_id: str
    task_type: str
    status: TaskStatus
    params: dict
    session_id: Optional[str]
    created_at: float
    updated_at: float
    result: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0  # 0–100


def _update_task_progress(record: TaskRecord, progress: int) -> None:
    """线程安全之外的轻量进度更新，供同步处理阶段回调使用。"""
    record.progress = max(0, min(100, progress))
    record.updated_at = time.time()


_tasks: dict[str, TaskRecord] = {}
_tasks_lock = asyncio.Lock()


async def _run_task(record: TaskRecord) -> None:
    """后台执行任务并更新状态"""
    async with _tasks_lock:
        record.status = TaskStatus.RUNNING
        record.updated_at = time.time()
        record.progress = 10

    try:
        task_type = record.task_type

        if task_type == "analyze_knowledge_base":
            from doc_pipeline import DocPipeline

            pipeline = DocPipeline()

            async with _tasks_lock:
                record.progress = 30
                record.updated_at = time.time()

            await asyncio.sleep(0)  # yield to event loop
            stats = pipeline.get_stats()

            async with _tasks_lock:
                record.progress = 80
                record.updated_at = time.time()

            total = stats.get("total_docs", 0)
            store_path = stats.get("store_path", "N/A")
            record.result = (
                f"知识库分析完成。共 {total} 个文档片段，存储路径：{store_path}"
            )

        elif task_type == "generate_report":
            session_id = record.session_id or "default"
            from chat_store import SQLiteChatMessageHistory

            history = SQLiteChatMessageHistory(session_id=session_id)

            async with _tasks_lock:
                record.progress = 40
                record.updated_at = time.time()

            messages = list(history.messages)
            msg_count = len(messages)

            async with _tasks_lock:
                record.progress = 90
                record.updated_at = time.time()

            record.result = f"报告生成完成。本次会话共 {msg_count} 条消息记录。"

        elif task_type == "upload_documents":
            from doc_pipeline import DocPipeline

            file_paths = [str(p) for p in record.params.get("temp_paths", []) if p]
            original_names = [str(n) for n in record.params.get("file_names", []) if n]

            if not file_paths:
                raise ValueError("未找到可导入的临时文件")

            pipeline = DocPipeline()

            async with _tasks_lock:
                record.progress = 15
                record.updated_at = time.time()

            count = await asyncio.to_thread(
                pipeline.ingest,
                file_paths,
                lambda progress: _update_task_progress(record, progress),
            )

            for temp_path in file_paths:
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.warning(
                        "task_id=%s 临时文件删除失败: %s", record.task_id, temp_path
                    )

            uploaded_count = len(original_names) or len(file_paths)
            record.result = f"已导入 {uploaded_count} 个文件，共 {count} 个文档片段"

        else:
            # Generic async placeholder for unknown task types
            for pct in (20, 50, 80):
                await asyncio.sleep(0.5)
                async with _tasks_lock:
                    record.progress = pct
                    record.updated_at = time.time()
            record.result = f"任务 '{task_type}' 已完成（通用执行路径）"

        async with _tasks_lock:
            record.status = TaskStatus.COMPLETED
            record.progress = 100
            record.updated_at = time.time()

    except Exception as exc:
        logger.exception(
            "task_id=%s task_type=%s 执行失败", record.task_id, record.task_type
        )
        if record.task_type == "upload_documents":
            for temp_path in record.params.get("temp_paths", []):
                try:
                    os.remove(str(temp_path))
                except OSError:
                    pass
        async with _tasks_lock:
            record.status = TaskStatus.FAILED
            record.error = str(exc)
            record.updated_at = time.time()


# ─────────────────────────────────────────────
# 内部工具函数
# ─────────────────────────────────────────────

# 缓存已构建的 agent 实例，key = (provider, model, base_url, api_key, temperature, agent_mode)
_agent_cache: dict[str, Any] = {}
_agent_cache_lock = asyncio.Lock()


def _validate_chat_payload(
    message: str,
    images: list[ImageInput],
    files: list[FileInput],
) -> None:
    if message.strip() or images or files:
        return
    raise HTTPException(
        status_code=400,
        detail="Message content, images, and files cannot all be empty.",
    )


def _chat_file_suffix(name: str) -> str:
    base_name = (name or "").replace("\\", "/").split("/")[-1]
    return Path(base_name).suffix.lower()


def _decode_data_url(data_url: str, file_name: str) -> bytes:
    if not data_url.startswith("data:") or "," not in data_url:
        raise HTTPException(
            status_code=400,
            detail=f"Attachment payload is invalid: {file_name}",
        )

    header, encoded = data_url.split(",", 1)
    try:
        if ";base64" in header:
            return base64.b64decode(encoded, validate=True)
        return unquote_to_bytes(encoded)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Attachment payload is corrupted: {file_name}",
        ) from exc


def _extract_chat_file_context(files: list[FileInput]) -> str:
    if not files:
        return ""
    if len(files) > CHAT_FILE_MAX_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"You can attach up to {CHAT_FILE_MAX_COUNT} files per message.",
        )

    from doc_pipeline import DocPipeline

    pipeline = DocPipeline()
    sections: list[str] = []
    remaining_chars = CHAT_FILE_MAX_TOTAL_CHARS

    for index, chat_file in enumerate(files, start=1):
        suffix = _chat_file_suffix(chat_file.name)
        if suffix not in SUPPORTED_CHAT_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type: {chat_file.name}",
            )

        payload = _decode_data_url(chat_file.data_url, chat_file.name)
        if not payload:
            raise HTTPException(
                status_code=400,
                detail=f"Attachment is empty: {chat_file.name}",
            )
        if len(payload) > CHAT_FILE_MAX_BYTES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Attachment is too large: {chat_file.name} "
                    f"(max {CHAT_FILE_MAX_BYTES // (1024 * 1024)} MB)"
                ),
            )

        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)

        text_parts: list[str] = []
        try:
            try:
                docs = pipeline.load_file(temp_path)
                text_parts = [
                    str(getattr(doc, "page_content", "")).strip()
                    for doc in docs
                    if str(getattr(doc, "page_content", "")).strip()
                ]
            except Exception as exc:
                if suffix in {".txt", ".md", ".csv"}:
                    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
                        try:
                            direct_text = Path(temp_path).read_text(encoding=encoding)
                            if direct_text.strip():
                                text_parts = [direct_text.strip()]
                                break
                        except UnicodeDecodeError:
                            continue
                if not text_parts:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to parse attachment: {chat_file.name}",
                    ) from exc
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Failed to delete chat attachment temp file: %s", temp_path)
        extracted_text = re.sub(r"\n{3,}", "\n\n", "\n\n".join(text_parts)).strip()
        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail=f"No readable text found in attachment: {chat_file.name}",
            )

        allowed_chars = min(CHAT_FILE_MAX_CHARS_PER_FILE, remaining_chars)
        if allowed_chars <= 0:
            break

        clipped_text = extracted_text[:allowed_chars].rstrip()
        if len(extracted_text) > allowed_chars:
            clipped_text += "\n...[Attachment content truncated]"
        sections.append(
            "\n".join(
                [
                    f"[Attachment {index}]",
                    f"File name: {chat_file.name}",
                    "Content:",
                    clipped_text,
                ]
            )
        )
        remaining_chars -= len(clipped_text)

    if not sections:
        raise HTTPException(
            status_code=400,
            detail="The selected attachments did not provide readable text.",
        )

    return (
        f"{CHAT_FILE_CONTEXT_START_MARKER}\n"
        "The following text was extracted from the user's attached files. "
        "Use it as high-priority context when answering.\n\n"
        + "\n\n---\n\n".join(sections)
        + f"\n{CHAT_FILE_CONTEXT_END_MARKER}"
    )


def _build_message_with_files(message: str, files: list[FileInput]) -> str:
    attachment_context = _extract_chat_file_context(files)
    base_message = message.strip()
    if not attachment_context:
        return base_message

    parts = []
    if base_message:
        parts.append(base_message)
    else:
        parts.append("Please read the attached files and answer based on their contents.")
    parts.append(attachment_context)
    return "\n\n".join(parts).strip()


def _build_user_input(
    message: str,
    images: list[ImageInput],
    files: list[FileInput],
) -> Any:
    message_with_files = _build_message_with_files(message, files)
    if not images:
        return message_with_files

    content: list[dict[str, Any]] = []
    if message_with_files.strip():
        content.append({"type": "text", "text": message_with_files})

    for image in images:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": image.data_url},
            }
        )

    return content


def _user_input_has_images(user_input: Any) -> bool:
    if not isinstance(user_input, list):
        return False
    return any(
        isinstance(item, dict) and item.get("type") == "image_url"
        for item in user_input
    )


def _model_supports_images(provider: str, model_name: str) -> bool:
    model = (model_name or "").strip().lower()
    if not model:
        return False

    positive_hints = (
        "llava",
        "vision",
        "minicpm-v",
        "minicpmv",
        "internvl",
        "qwen-vl",
        "qwen2-vl",
        "qwen2.5-vl",
        "qwen2vl",
        "qwen2.5vl",
        "gpt-4o",
        "gpt-4.1",
        "o4-mini",
        "claude-3",
        "claude-4",
        "gemini-1.5",
        "gemini-2",
        "gemma3",
        "pixtral",
        "moondream",
    )
    return any(hint in model for hint in positive_hints)


def _stringify_user_input(user_input: Any) -> str:
    if isinstance(user_input, str):
        return user_input
    if isinstance(user_input, list):
        text_parts: list[str] = []
        image_count = 0
        for item in user_input:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and item.get("text"):
                text_parts.append(str(item["text"]))
            elif item.get("type") == "image_url":
                image_count += 1
        if image_count:
            text_parts.append(f"[用户上传了 {image_count} 张图片]")
        return "\n".join(part for part in text_parts if part).strip()
    return str(user_input)


async def _get_or_build_agent(
    mc: ModelConfig,
    system_prompt: Optional[str] = None,
    web_search_enabled: bool = True,
    knowledge_base_enabled: bool = True,
    vector_store_path: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
):
    """获取或构建 Agent（带缓存）"""
    from agent_core import build_agent

    api_key_hash = _hash_secret(mc.api_key)
    cache_key = _content_hash(
        {
            "provider": mc.provider,
            "model": mc.model,
            "base_url": mc.base_url,
            "api_key_hash": api_key_hash,
            "temperature": mc.temperature,
            "agent_mode": mc.agent_mode,
            "web_search_enabled": web_search_enabled,
            "knowledge_base_enabled": knowledge_base_enabled,
            "vector_store_path": str(_resolve_project_subdir(vector_store_path))
            if vector_store_path
            else "",
            "system_prompt": system_prompt or "",
            "dashboard_template": dashboard_template or {},
        }
    )
    async with _agent_cache_lock:
        if cache_key not in _agent_cache:
            logger.info("Building new agent: %s", cache_key[:12])
            _agent_cache[cache_key] = await build_agent(
                provider=mc.provider,
                model_name=mc.model,
                base_url=mc.base_url,
                api_key=mc.api_key if mc.api_key else None,
                temperature=mc.temperature,
                agent_mode=mc.agent_mode,
                system_prompt=system_prompt,
                web_search_enabled=web_search_enabled,
                knowledge_base_enabled=knowledge_base_enabled,
                vector_store_path=vector_store_path,
                dashboard_template=dashboard_template,
            )
        return _agent_cache[cache_key]


async def _invoke_agent_stream(
    panel_id: str,
    mc: ModelConfig,
    message: Any,
    session_id: str,
    web_search_enabled: bool,
    knowledge_base_enabled: bool,
    system_prompt: Optional[str] = None,
    vector_store_path: Optional[str] = None,
    dashboard_template: Optional[dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """调用单个 agent，将结果封装为 SSE 事件流"""
    try:
        agent = await _get_or_build_agent(
            mc,
            system_prompt=system_prompt,
            web_search_enabled=web_search_enabled,
            knowledge_base_enabled=knowledge_base_enabled,
            vector_store_path=vector_store_path,
            dashboard_template=dashboard_template,
        )

        # 尝试流式输出（LangGraph wrapper 支持 astream_answer）
        if hasattr(agent, "astream_answer"):
            sources_sent = False
            async for item in agent.astream_answer(
                message,
                config={"configurable": {"session_id": session_id}},
            ):
                # LangGraphAgentWrapper may yield a sources dict first
                if isinstance(item, dict) and item.get("type") == "sources":
                    sources_data = json.dumps(
                        {
                            "panel_id": panel_id,
                            "type": "sources",
                            "sources": item.get("sources", []),
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {sources_data}\n\n"
                    sources_sent = True
                else:
                    chunk = item if isinstance(item, str) else str(item)
                    data = json.dumps(
                        {"panel_id": panel_id, "type": "chunk", "content": chunk},
                        ensure_ascii=False,
                    )
                    yield f"data: {data}\n\n"
        else:
            # 非流式：一次性返回
            result = await agent.ainvoke(
                {"input": message},
                config={"configurable": {"session_id": session_id}},
            )
            answer = result.get("output", str(result))
            sources = result.get("sources", [])

            # 检测 max iterations 错误并降级处理
            if _is_max_iterations_output(answer):
                logger.warning(
                    "panel_id=%s max iterations reached, attempting fallback", panel_id
                )
                intermediate = result.get("intermediate_steps", [])
                if intermediate:
                    tool_outputs = "\n\n".join(
                        str(step[1]) for step in intermediate if len(step) > 1
                    )
                    answer = await _fallback_generate(
                        mc,
                        _stringify_user_input(message),
                        tool_outputs,
                    )
                else:
                    # 无中间步骤时发送结构化错误事件
                    err_data = json.dumps(
                        {
                            "panel_id": panel_id,
                            "type": "error",
                            "content": "模型工具调用次数超限，无法完成任务",
                            "error_code": "MAX_ITERATIONS",
                            "suggestion": "请尝试简化问题或切换至其他模型后重试",
                        },
                        ensure_ascii=False,
                    )
                    yield f"data: {err_data}\n\n"
                    done_data = json.dumps(
                        {"panel_id": panel_id, "type": "done"}, ensure_ascii=False
                    )
                    yield f"data: {done_data}\n\n"
                    return

            # Emit sources before answer chunks
            if sources:
                sources_data = json.dumps(
                    {"panel_id": panel_id, "type": "sources", "sources": sources},
                    ensure_ascii=False,
                )
                yield f"data: {sources_data}\n\n"

            # 将答案分块模拟流式效果（每20字符一块）
            chunk_size = 20
            for i in range(0, len(answer), chunk_size):
                chunk = answer[i : i + chunk_size]
                data = json.dumps(
                    {"panel_id": panel_id, "type": "chunk", "content": chunk},
                    ensure_ascii=False,
                )
                yield f"data: {data}\n\n"
                await asyncio.sleep(0.01)

        # 完成信号
        done_data = json.dumps(
            {"panel_id": panel_id, "type": "done"}, ensure_ascii=False
        )
        yield f"data: {done_data}\n\n"

    except Exception as e:
        logger.exception("Agent invocation failed panel_id=%s", panel_id)
        err = _classify_error(e)
        err_data = json.dumps(
            {
                "panel_id": panel_id,
                "type": "error",
                "content": err["message"],
                "error_code": err["code"],
                "suggestion": err["suggestion"],
            },
            ensure_ascii=False,
        )
        yield f"data: {err_data}\n\n"


# ─────────────────────────────────────────────
# API 端点
# ─────────────────────────────────────────────


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


# ── 聊天 ──────────────────────────────────────


@app.post("/api/chat/parallel")
async def chat_parallel(request: ChatRequest, http_request: Request):
    """
    多模型并行对话 SSE 端点。
    每个面板的事件包含 panel_id 字段，前端据此路由到对应面板。
    """
    from chat_store import get_active_system_prompt

    active_prompt = get_active_system_prompt()
    system_prompt_content = active_prompt["content"] if active_prompt else None
    vector_store_path = (active_prompt.get("vector_store_id") if active_prompt else None) or None
    dashboard_template = (
        active_prompt.get("dashboard_template", {}) if active_prompt else {}
    ) or {}
    if not request.knowledge_base_enabled:
        vector_store_path = None

    _validate_chat_payload(request.message, request.images, request.files)
    user_input = _build_user_input(request.message, request.images, request.files)

    if not request.models:
        raise HTTPException(status_code=400, detail="至少需要选择一个模型")

    async def event_generator() -> AsyncGenerator[str, None]:
        # 为每个模型创建独立的异步生成器
        generators = [
            _invoke_agent_stream(
                mc.panel_id,
                mc,
                user_input,
                request.session_id,
                request.web_search_enabled,
                request.knowledge_base_enabled,
                system_prompt=system_prompt_content,
                vector_store_path=vector_store_path,
                dashboard_template=dashboard_template,
            )
            for mc in request.models
        ]

        # 将多个异步生成器合并为一个（使用 asyncio.Queue）
        queue: asyncio.Queue[Any] = asyncio.Queue()
        producer_count = len(generators)
        producer_done = object()
        disconnected = False

        async def feed(gen):
            try:
                async for item in gen:
                    await queue.put(item)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Parallel SSE producer failed")
            finally:
                await queue.put(producer_done)

        tasks = [asyncio.create_task(feed(g)) for g in generators]
        finished_producers = 0

        try:
            while finished_producers < producer_count:
                if await http_request.is_disconnected():
                    disconnected = True
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                if item is producer_done:
                    finished_producers += 1
                    continue
                yield item
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        # 发送全局完成信号
        if not disconnected:
            yield f"data: {json.dumps({'type': 'all_done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/single")
async def chat_single(request: SingleChatRequest, http_request: Request):
    """单模型对话 SSE 端点"""
    from chat_store import get_active_system_prompt

    active_prompt = get_active_system_prompt()
    system_prompt_content = active_prompt["content"] if active_prompt else None
    vector_store_path = (active_prompt.get("vector_store_id") if active_prompt else None) or None
    dashboard_template = (
        active_prompt.get("dashboard_template", {}) if active_prompt else {}
    ) or {}
    if not request.knowledge_base_enabled:
        vector_store_path = None

    _validate_chat_payload(request.message, request.images, request.files)
    user_input = _build_user_input(request.message, request.images, request.files)

    async def event_generator():
        async for chunk in _invoke_agent_stream(
            request.panel_config.panel_id,
            request.panel_config,
            user_input,
            request.session_id,
            request.web_search_enabled,
            request.knowledge_base_enabled,
            system_prompt=system_prompt_content,
            vector_store_path=vector_store_path,
            dashboard_template=dashboard_template,
        ):
            if await http_request.is_disconnected():
                break
            yield chunk
        yield f"data: {json.dumps({'type': 'all_done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── 会话管理 ──────────────────────────────────


@app.get("/api/sessions")
async def get_sessions():
    from chat_store import get_all_sessions

    sessions = get_all_sessions()
    return {"sessions": sessions}


@app.post("/api/sessions")
async def create_session(request: CreateSessionRequest):
    from chat_store import SQLiteChatMessageHistory, get_active_system_prompt

    session_id = str(uuid.uuid4())
    history = SQLiteChatMessageHistory(session_id=session_id)
    if request.title:
        # 写一个空的系统消息来触发标题设置
        import sqlite3

        with sqlite3.connect(history.db_path) as conn:
            conn.execute(
                "UPDATE sessions SET title = ? WHERE session_id = ?",
                (request.title, session_id),
            )
            conn.commit()
    return {"session_id": session_id, "title": request.title or "新对话"}


@app.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    from chat_store import delete_session

    delete_session(session_id)
    return {"ok": True}


@app.get("/api/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    from chat_store import SQLiteChatMessageHistory, CONTEXT_HISTORY_MESSAGES

    history = SQLiteChatMessageHistory(session_id=session_id)
    messages = []
    all_messages = history.get_all_messages()
    for msg in all_messages:
        if hasattr(msg, "type"):
            role = "user" if msg.type == "human" else "assistant"
        else:
            role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
        messages.append({"role": role, "content": msg.content})
    return {
        "messages": messages,
        "context_limit": CONTEXT_HISTORY_MESSAGES,
        "total_messages": len(messages),
    }


@app.delete("/api/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str):
    from agent_core import clear_session_history

    clear_session_history(session_id)
    return {"ok": True}


# ── 文档管理 ──────────────────────────────────


@app.post("/api/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    def _extract_suffix(name: str | None) -> str:
        """从原始文件名中提取扩展名，供 mkstemp 保留格式标识"""
        if not name:
            return ""
        # 兼容 Windows 完整路径（正斜杠或反斜杠）
        base = name.replace("\\", "/").split("/")[-1]
        _, ext = os.path.splitext(base)
        return ext  # e.g. ".pdf", ".docx"

    temp_paths: list[str] = []
    file_names: list[str] = []
    try:
        for f in files:
            suffix = _extract_suffix(f.filename)
            # 使用 mkstemp 生成安全的临时文件路径，避免文件名含非法字符或 Unicode 导致 [Errno 22]
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            try:
                content = await f.read()
                with os.fdopen(fd, "wb") as fp:
                    fp.write(content)
            except Exception:
                os.close(fd)
                raise
            temp_paths.append(temp_path)
            file_names.append(f.filename or os.path.basename(temp_path))

        task_id = str(uuid.uuid4())
        now = time.time()
        record = TaskRecord(
            task_id=task_id,
            task_type="upload_documents",
            status=TaskStatus.PENDING,
            params={"temp_paths": temp_paths, "file_names": file_names},
            session_id=None,
            created_at=now,
            updated_at=now,
        )
        async with _tasks_lock:
            _tasks[task_id] = record

        asyncio.create_task(_run_task(record))
        logger.info("task_id=%s task_type=upload_documents 已创建", task_id)
        return {
            "ok": True,
            "task_id": task_id,
            "task_type": record.task_type,
            "status": record.status,
            "message": f"已接收 {len(file_names)} 个文件，正在后台构建知识库",
        }
    except Exception as e:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        pass


@app.get("/api/documents/stats")
async def get_document_stats():
    from doc_pipeline import DocPipeline

    pipeline = DocPipeline()
    try:
        pipeline.load_store()
        stats = pipeline.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 模型发现 ──────────────────────────────────


@app.get("/api/models/ollama")
async def get_ollama_models(base_url: str = "http://localhost:11434"):
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        return {"models": [m["name"] for m in models]}
    except Exception as e:
        logger.warning("Cannot reach Ollama: %s", e)
        return {"models": [], "error": str(e)}


# ── 配置管理 ──────────────────────────────────


@app.get("/api/config")
async def get_config():
    return {
        "tavily_api_key_set": bool(os.environ.get("TAVILY_API_KEY")),
        "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
        "ollama_model": os.environ.get("OLLAMA_MODEL", "qwen2.5:7b"),
        "ollama_base_url": os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        "openrouter_model": os.environ.get("OPENROUTER_MODEL", ""),
        "openrouter_base_url": os.environ.get(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ),
    }


@app.post("/api/config")
async def save_config(request: SaveConfigRequest):
    if request.tavily_api_key is not None:
        os.environ["TAVILY_API_KEY"] = request.tavily_api_key
        # 清除 agent cache 以便下次重建时使用新 key
        _agent_cache.clear()
    return {"ok": True}


@app.post("/api/agents/reset")
async def reset_agents():
    """清除 agent 缓存，下次请求时重新构建"""
    _agent_cache.clear()
    return {"ok": True, "message": "Agent cache cleared"}


# ── System Prompts ─────────────────────────────


@app.get("/api/prompts")
async def list_prompts():
    from chat_store import get_all_system_prompts

    return {"prompts": get_all_system_prompts()}


@app.post("/api/prompts")
async def create_prompt(request: CreatePromptRequest):
    from chat_store import create_system_prompt

    prompt = create_system_prompt(
        request.name,
        request.content,
        vector_store_id=request.vector_store_id or "",
        dashboard_template=request.dashboard_template or {},
    )
    return prompt


@app.put("/api/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, request: UpdatePromptRequest):
    from chat_store import update_system_prompt

    prompt = update_system_prompt(
        prompt_id,
        request.name,
        request.content,
        vector_store_id=request.vector_store_id or "",
        dashboard_template=request.dashboard_template or {},
    )
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    from chat_store import delete_system_prompt

    ok = delete_system_prompt(prompt_id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Prompt not found or is the last default"
        )
    # Rebuild agents since active prompt may have changed
    _agent_cache.clear()
    return {"ok": True}


@app.post("/api/prompts/{prompt_id}/activate")
async def activate_prompt(prompt_id: str):
    from chat_store import activate_system_prompt, get_all_system_prompts
    from doc_pipeline import DocPipeline

    ok = activate_system_prompt(prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # Clear agent cache so next request rebuilds with new prompt
    _agent_cache.clear()

    # Load knowledge base bound to this role (if any)
    prompts = get_all_system_prompts()
    target = next((p for p in prompts if p["id"] == prompt_id), None)
    kb_status = "none"
    if target and target.get("vector_store_id"):
        try:
            pipeline = DocPipeline(vector_store_path=target["vector_store_id"])
            loaded = pipeline.load_store()
            kb_status = "loaded" if loaded else "error"
        except Exception as e:
            logger.warning("Failed to load KB for prompt %s: %s", prompt_id, e)
            kb_status = "error"
    return {"ok": True, "kb_status": kb_status}


# ── 异步任务管理 ────────────────────────────────


@app.post("/api/tasks")
async def create_task(request: CreateTaskRequest):
    """创建异步任务，立即返回 task_id，任务在后台执行"""
    task_id = str(uuid.uuid4())
    now = time.time()
    record = TaskRecord(
        task_id=task_id,
        task_type=request.task_type,
        status=TaskStatus.PENDING,
        params=request.params,
        session_id=request.session_id,
        created_at=now,
        updated_at=now,
    )
    async with _tasks_lock:
        _tasks[task_id] = record

    asyncio.create_task(_run_task(record))
    logger.info("task_id=%s task_type=%s 已创建", task_id, request.task_type)

    return {
        "task_id": task_id,
        "status": record.status,
        "task_type": record.task_type,
        "created_at": record.created_at,
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """轮询任务状态"""
    async with _tasks_lock:
        record = _tasks.get(task_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": record.task_id,
        "task_type": record.task_type,
        "status": record.status,
        "progress": record.progress,
        "result": record.result,
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


@app.get("/api/tasks")
async def list_tasks(limit: int = 20):
    """列出最近的任务（按创建时间倒序）"""
    async with _tasks_lock:
        all_tasks = list(_tasks.values())

    all_tasks.sort(key=lambda t: t.created_at, reverse=True)
    return {
        "tasks": [
            {
                "task_id": t.task_id,
                "task_type": t.task_type,
                "status": t.status,
                "progress": t.progress,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t in all_tasks[:limit]
        ]
    }


# ── 会话重置 ──────────────────────────────────


@app.post("/api/sessions/{session_id}/reset")
async def reset_session(session_id: str):
    """彻底清除会话上下文和 Agent 缓存，确保下次是全新起点"""
    from agent_core import clear_session_history

    clear_session_history(session_id)
    _agent_cache.clear()
    return {"ok": True, "message": "会话已完全重置"}


# ── 报告生成 ──────────────────────────────────


def _build_slidev_markdown(messages: list, title: str) -> str:
    """将对话历史转换为 Slidev 规范的 Markdown"""
    lines = [
        "---",
        f"theme: default",
        f"title: {title}",
        "class: text-center",
        "---",
        "",
        f"# {title}",
        "",
        "AI 对话报告",
        "",
    ]
    slide_count = 0
    for msg in messages:
        role = getattr(msg, "__class__", type(msg)).__name__
        content = msg.content if hasattr(msg, "content") else str(msg)
        if not content.strip():
            continue
        is_human = role == "HumanMessage"
        if is_human:
            slide_count += 1
            lines.append("---")
            lines.append("")
            lines.append(f"## Q{slide_count}: {content[:80].strip()}")
            lines.append("")
        else:
            lines.append(content.strip())
            lines.append("")
    return "\n".join(lines)


@app.post("/api/decks")
async def create_deck(request: CreateDeckRequest):
    """Create a structured deck draft from session history."""
    from chat_store import SQLiteChatMessageHistory, get_active_system_prompt

    history = SQLiteChatMessageHistory(session_id=request.session_id)
    messages = history.get_all_messages()
    if not messages:
        raise HTTPException(status_code=400, detail="该会话没有对话记录")

    active_prompt = get_active_system_prompt()
    system_prompt_content = active_prompt["content"] if active_prompt else None
    vector_store_path = None
    if request.knowledge_base_enabled and active_prompt:
        vector_store_path = active_prompt.get("vector_store_id") or None

    try:
        deck = await build_deck(
            session_id=request.session_id,
            messages=messages,
            panel_config=request.panel_config,
            knowledge_base_enabled=request.knowledge_base_enabled,
            target_slide_count=request.target_slide_count,
            vector_store_path=vector_store_path,
            system_prompt=system_prompt_content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _deck_store.save(deck)
    return deck.model_dump(mode="json")


@app.get("/api/decks/{deck_id}")
async def get_deck(deck_id: str):
    """Return a previously generated deck draft."""
    try:
        deck = _deck_store.get(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未找到该演示稿草稿") from exc
    return deck.model_dump(mode="json")


@app.patch("/api/decks/{deck_id}")
async def update_deck(deck_id: str, request: UpdateDeckRequest):
    """Persist edited deck content from the in-app editor."""
    try:
        deck = _deck_store.get(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未找到该演示稿草稿") from exc

    if request.title is not None and request.title.strip():
        deck.meta.title = request.title.strip()
        if deck.slides and deck.slides[0].type == "cover":
            deck.slides[0].title = deck.meta.title
    if request.slides is not None:
        if not request.slides:
            raise HTTPException(status_code=400, detail="演示稿至少需要保留一页")
        deck.slides = request.slides
        deck.generation.actual_slide_count = len(deck.slides)

    _deck_store.save(deck)
    return deck.model_dump(mode="json")


@app.get("/api/decks/{deck_id}/export")
async def export_deck(deck_id: str, format: str = "pptx"):
    """Export a saved deck draft."""
    if format != "pptx":
        raise HTTPException(status_code=400, detail="当前仅支持导出 PPTX")

    try:
        deck = _deck_store.get(deck_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未找到该演示稿草稿") from exc

    try:
        content = export_deck_to_pptx(deck)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = build_export_filename(deck, "pptx")
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/reports/generate")
async def generate_report(request: GenerateReportRequest):
    """根据会话历史生成 Slidev 格式 Markdown 报告"""
    from chat_store import SQLiteChatMessageHistory

    history = SQLiteChatMessageHistory(session_id=request.session_id)
    msgs = history.get_all_messages()
    try:
        qa_pairs = ensure_deckable_chat(msgs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not msgs:
        raise HTTPException(status_code=400, detail="该会话没有对话记录")

    # Use first user message as title
    title = "AI 对话报告"
    for m in msgs:
        if m.__class__.__name__ == "HumanMessage" and m.content.strip():
            title = m.content.strip()[:50]
            break

    try:
        markdown = build_report_markdown(msgs, title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"markdown": markdown, "title": title}


@app.get("/api/reports/download/{session_id}")
async def download_report_pptx(session_id: str):
    """将会话历史转换为 PPTX 文件并下载"""
    from chat_store import SQLiteChatMessageHistory
    import io

    try:
        from pptx import Presentation
        from pptx.util import Pt
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="python-pptx 未安装，请在 requirements.txt 中添加 python-pptx 并重新安装依赖",
        )

    history = SQLiteChatMessageHistory(session_id=session_id)
    msgs = history.get_all_messages()
    try:
        qa_pairs = ensure_deckable_chat(msgs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not msgs:
        raise HTTPException(status_code=400, detail="该会话没有对话记录")

    title = "AI 对话报告"
    for m in msgs:
        if m.__class__.__name__ == "HumanMessage" and m.content.strip():
            title = m.content.strip()[:50]
            break

    prs = Presentation()
    # Title slide
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    slide.shapes.title.text = title
    if len(slide.placeholders) > 1:
        slide.placeholders[1].text = "AI 知识库对话报告"

    for index, (question, answer) in enumerate(qa_pairs, start=1):
        layout = prs.slide_layouts[1]
        sl = prs.slides.add_slide(layout)
        sl.shapes.title.text = f"主题 {index}: {question[:48]}"
        body = sl.placeholders[1]
        tf = body.text_frame
        tf.word_wrap = True
        answer_text = answer[:1200]
        if len(answer) > 1200:
            answer_text += "鈥︼紙鍐呭宸叉埅鏂級"
        tf.text = answer_text
        for para in tf.paragraphs:
            for run in para.runs:
                run.font.size = Pt(12)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)

    safe_title = (
        "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()[:40]
        or "report"
    )
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.pptx"'},
    )


# ── 知识库管理 ─────────────────────────────────


@app.get("/api/knowledge-bases")
async def list_knowledge_bases():
    """列出可用的知识库目录"""
    import glob as glob_module
    from doc_pipeline import DocPipeline

    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Find any directory that contains FAISS index files
    kb_dirs = []
    default_path = os.getenv("VECTOR_STORE_PATH", "./vector_store")
    search_paths = [default_path]
    # Also search any sibling dirs named vector_store*
    for p in glob_module.glob(os.path.join(base_dir, "vector_store*")):
        if os.path.isdir(p) and p not in search_paths:
            search_paths.append(p)

    for path in search_paths:
        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            continue
        index_file = os.path.join(abs_path, "index.faiss")
        doc_count = 0
        if os.path.exists(index_file):
            try:
                pipeline = DocPipeline(vector_store_path=_faiss_safe_store_path(abs_path))
                if pipeline.load_store():
                    stats = pipeline.get_stats()
                    doc_count = stats.get("total_docs", 0)
            except Exception:
                pass
        kb_dirs.append(
            {
                "id": abs_path,
                "name": os.path.basename(abs_path),
                "path": abs_path,
                "doc_count": doc_count,
                "has_index": os.path.exists(index_file),
            }
        )

    return {"knowledge_bases": kb_dirs}


@app.get("/api/knowledge-base/health")
async def get_kb_health():
    """知识库健康检查 - 返回详细状态信息"""
    import glob as glob_module
    from doc_pipeline import DocPipeline
    store_path = os.getenv("VECTOR_STORE_PATH", "./vector_store")
    target_path = _resolve_project_subdir(store_path)
    abs_store = str(target_path)
    index_file = os.path.join(abs_store, "index.faiss")

    if not os.path.exists(abs_store):
        return {
            "index_status": "not_found",
            "total_chunks": 0,
            "store_path": abs_store,
            "store_size_mb": 0,
            "documents": [],
            "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
            "last_updated": None,
        }

    # Compute disk size
    total_size = 0
    for f in glob_module.glob(os.path.join(abs_store, "*")):
        if os.path.isfile(f):
            total_size += os.path.getsize(f)
    size_mb = round(total_size / (1024 * 1024), 2)

    # Last updated time
    last_updated = None
    if os.path.exists(index_file):
        last_updated = os.path.getmtime(index_file)

    documents = []
    total_chunks = 0
    index_status = "empty"

    try:
        pipeline = DocPipeline(vector_store_path=_faiss_safe_store_path(abs_store))
        loaded = pipeline.load_store()
        if loaded and pipeline.vectorstore is not None:
            stats = pipeline.get_stats()
            total_chunks = stats.get("total_docs", 0)
            index_status = "healthy" if total_chunks > 0 else "empty"

            # Extract per-document stats from docstore
            doc_counts: dict = {}
            try:
                docstore = pipeline.vectorstore.docstore
                store_dict = getattr(docstore, "_dict", {})
                for _id, doc in store_dict.items():
                    source = (
                        doc.metadata.get("source", "未知")
                        if hasattr(doc, "metadata")
                        else "未知"
                    )
                    doc_counts[source] = doc_counts.get(source, 0) + 1
            except Exception:
                pass

            documents = [
                {"name": k, "chunks": v} for k, v in sorted(doc_counts.items())
            ]
    except Exception as e:
        index_status = "error"
        logger.warning("KB health check failed: %s", e)

    return {
        "index_status": index_status,
        "total_chunks": total_chunks,
        "store_path": abs_store,
        "store_size_mb": size_mb,
        "documents": documents,
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5"),
        "last_updated": last_updated,
    }


@app.post("/api/knowledge-base/test-retrieval")
async def test_retrieval(request: TestRetrievalRequest):
    """执行测试检索，用于诊断知识库"""
    import time as time_module
    from doc_pipeline import DocPipeline

    if not request.query.strip():
        raise HTTPException(status_code=400, detail="查询内容不能为空")

    pipeline = DocPipeline()
    start = time_module.time()
    try:
        loaded = pipeline.load_store()
        if not loaded:
            return {
                "results_count": 0,
                "top_scores": [],
                "latency_ms": 0,
                "error": "知识库未初始化",
            }
        docs = pipeline.search(request.query, k=5)
        latency = round((time_module.time() - start) * 1000, 1)
        return {
            "results_count": len(docs),
            "latency_ms": latency,
            "top_results": [
                {
                    "source": d.metadata.get("source", "未知"),
                    "snippet": d.page_content[:120],
                }
                for d in docs
            ],
        }
    except Exception as e:
        return {"results_count": 0, "top_scores": [], "latency_ms": 0, "error": str(e)}


@app.delete("/api/knowledge-base")
async def delete_knowledge_base():
    """删除当前默认知识库"""
    store_path = os.getenv("VECTOR_STORE_PATH", "./vector_store")
    target_path = _resolve_deletable_knowledge_base(store_path)
    abs_store = str(target_path)

    if not os.path.exists(abs_store):
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        shutil.rmtree(abs_store)
        _agent_cache.clear()
        logger.info("Knowledge base deleted: %s", abs_store)
        return {"ok": True, "message": f"知识库已删除: {abs_store}"}
    except Exception as e:
        logger.exception("Failed to delete knowledge base")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/knowledge-base/by-path")
async def delete_knowledge_base_by_path(path: str):
    """按路径删除指定知识库"""
    import shutil

    target_path = _resolve_deletable_knowledge_base(path)
    abs_path = str(target_path)
    # Safety: must be under project root
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="指定路径不存在")
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="指定路径不是目录")

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="指定路径不存在")

    if not (target_path / "index.faiss").exists():
        raise HTTPException(
            status_code=400, detail="只允许删除包含 index.faiss 的知识库目录"
        )

    try:
        shutil.rmtree(target_path)
        _agent_cache.clear()
        return {"ok": True, "message": f"已删除: {abs_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 静态文件（生产模式）─────────────────────────

_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    from fastapi.responses import FileResponse

    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_frontend_dist, "assets")),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(_frontend_dist, "index.html")
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("SERVER_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        reload=True,
    )
