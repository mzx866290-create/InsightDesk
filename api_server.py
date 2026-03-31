"""
FastAPI 后端 API 服务
提供 REST + SSE 端点，包装现有 agent_core / chat_store / doc_pipeline 模块
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
import uuid
from typing import Any, AsyncGenerator, Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI 知识库 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    err = _classify_error(exc)
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": err["code"], "message": err["message"], "suggestion": err["suggestion"]},
    )


def _classify_error(e: Exception) -> dict:
    """将异常映射为用户友好的错误信息 + 错误码 + 恢复建议"""
    msg = str(e)
    if isinstance(e, ConnectionError) or any(
        kw in msg for kw in ("Connection refused", "ConnectError", "connect ECONNREFUSED")
    ):
        return {
            "code": "MODEL_UNAVAILABLE",
            "message": "模型服务暂时不可用",
            "suggestion": "请检查 Ollama 是否已启动，或稍后重试",
        }
    if any(kw in msg for kw in ("API Key", "api_key", "401", "Unauthorized", "authentication")):
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
    if any(kw in msg for kw in ("Invalid model", "model not found", "404")):
        return {
            "code": "MODEL_NOT_FOUND",
            "message": "指定的模型不存在",
            "suggestion": "请在面板顶部的模型选择器中确认模型名称是否正确",
        }
    return {
        "code": "INTERNAL_ERROR",
        "message": "处理请求时发生异常",
        "suggestion": "请尝试清除上下文或新建对话后重试",
    }

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


class ChatRequest(BaseModel):
    session_id: str
    message: str
    models: list[ModelConfig]
    web_search_enabled: bool = False


class SingleChatRequest(BaseModel):
    session_id: str
    message: str
    panel_config: ModelConfig
    web_search_enabled: bool = False


class CreateSessionRequest(BaseModel):
    title: str = ""


class SaveConfigRequest(BaseModel):
    tavily_api_key: Optional[str] = None
    embedding_model: Optional[str] = None


class CreatePromptRequest(BaseModel):
    name: str
    content: str


class UpdatePromptRequest(BaseModel):
    name: str
    content: str


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

            record.result = (
                f"报告生成完成。本次会话共 {msg_count} 条消息记录。"
            )

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
        logger.exception("task_id=%s task_type=%s 执行失败", record.task_id, record.task_type)
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


async def _get_or_build_agent(mc: ModelConfig, system_prompt: Optional[str] = None):
    """获取或构建 Agent（带缓存）"""
    from agent_core import build_agent

    prompt_key = (system_prompt or "")[:64]
    cache_key = f"{mc.provider}|{mc.model}|{mc.base_url}|{mc.api_key}|{mc.temperature}|{mc.agent_mode}|{prompt_key}"
    async with _agent_cache_lock:
        if cache_key not in _agent_cache:
            logger.info("Building new agent: %s", cache_key[:80])
            _agent_cache[cache_key] = await build_agent(
                provider=mc.provider,
                model_name=mc.model,
                base_url=mc.base_url,
                api_key=mc.api_key if mc.api_key else None,
                temperature=mc.temperature,
                agent_mode=mc.agent_mode,
                system_prompt=system_prompt,
            )
        return _agent_cache[cache_key]


async def _invoke_agent_stream(
    panel_id: str,
    mc: ModelConfig,
    message: str,
    session_id: str,
    web_search_enabled: bool,
    system_prompt: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """调用单个 agent，将结果封装为 SSE 事件流"""
    from agent_core import set_web_search_enabled

    try:
        set_web_search_enabled(web_search_enabled)
        agent = await _get_or_build_agent(mc, system_prompt=system_prompt)

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
                        {"panel_id": panel_id, "type": "sources", "sources": item.get("sources", [])},
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
async def chat_parallel(request: ChatRequest):
    """
    多模型并行对话 SSE 端点。
    每个面板的事件包含 panel_id 字段，前端据此路由到对应面板。
    """
    from chat_store import get_active_system_prompt

    active_prompt = get_active_system_prompt()
    system_prompt_content = active_prompt["content"] if active_prompt else None

    async def event_generator() -> AsyncGenerator[str, None]:
        # 为每个模型创建独立的异步生成器
        generators = [
            _invoke_agent_stream(
                mc.panel_id,
                mc,
                request.message,
                request.session_id,
                request.web_search_enabled,
                system_prompt=system_prompt_content,
            )
            for mc in request.models
        ]

        # 将多个异步生成器合并为一个（使用 asyncio.Queue）
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        pending = len(generators)

        async def feed(gen):
            nonlocal pending
            async for item in gen:
                await queue.put(item)
            pending -= 1
            if pending == 0:
                await queue.put(None)  # 终止信号

        tasks = [asyncio.create_task(feed(g)) for g in generators]

        finished_producers = 0
        while True:
            item = await queue.get()
            if item is None:
                finished_producers += 1
                # 检查是否所有生产者都完成了
                remaining = sum(1 for t in tasks if not t.done())
                all_done = all(t.done() for t in tasks)
                if all_done and queue.empty():
                    break
                continue
            yield item

        # 发送全局完成信号
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
async def chat_single(request: SingleChatRequest):
    """单模型对话 SSE 端点"""
    from chat_store import get_active_system_prompt

    active_prompt = get_active_system_prompt()
    system_prompt_content = active_prompt["content"] if active_prompt else None

    async def event_generator():
        async for chunk in _invoke_agent_stream(
            request.panel_config.panel_id,
            request.panel_config,
            request.message,
            request.session_id,
            request.web_search_enabled,
            system_prompt=system_prompt_content,
        ):
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
    from chat_store import SQLiteChatMessageHistory

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
    for msg in history.messages:
        if hasattr(msg, "type"):
            role = "user" if msg.type == "human" else "assistant"
        else:
            role = (
                "user"
                if msg.__class__.__name__ == "HumanMessage"
                else "assistant"
            )
        messages.append({"role": role, "content": msg.content})
    return {"messages": messages, "context_limit": CONTEXT_HISTORY_MESSAGES}


@app.delete("/api/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str):
    from agent_core import clear_session_history

    clear_session_history(session_id)
    return {"ok": True}


# ── 文档管理 ──────────────────────────────────


@app.post("/api/documents/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    from doc_pipeline import DocPipeline

    def _safe_filename(name: str | None) -> str:
        # 在 Windows 上，上传时浏览器有时会带上完整路径，例如 C:\Users\foo\bar.pdf
        # 这里只保留基础文件名，并移除 Windows 不允许的字符，避免出现 [Errno 22] Invalid argument
        base = os.path.basename(name or "") or "upload"
        invalid_chars = '<>:"/\\|?*'
        for ch in invalid_chars:
            base = base.replace(ch, "_")
        # 防止全被替换为空
        base = base.strip() or "upload"
        return base

    pipeline = DocPipeline()
    temp_paths: list[str] = []
    try:
        for f in files:
            safe_name = _safe_filename(f.filename)
            temp_path = os.path.join(tempfile.gettempdir(), safe_name)
            content = await f.read()
            with open(temp_path, "wb") as fp:
                fp.write(content)
            temp_paths.append(temp_path)

        count = pipeline.ingest(temp_paths)
        return {"ok": True, "count": count, "message": f"已导入 {count} 个文档片段"}
    except Exception as e:
        logger.exception("Document upload failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in temp_paths:
            try:
                os.remove(p)
            except OSError:
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

    prompt = create_system_prompt(request.name, request.content)
    return prompt


@app.put("/api/prompts/{prompt_id}")
async def update_prompt(prompt_id: str, request: UpdatePromptRequest):
    from chat_store import update_system_prompt

    prompt = update_system_prompt(prompt_id, request.name, request.content)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt


@app.delete("/api/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    from chat_store import delete_system_prompt

    ok = delete_system_prompt(prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Prompt not found or is the last default")
    # Rebuild agents since active prompt may have changed
    _agent_cache.clear()
    return {"ok": True}


@app.post("/api/prompts/{prompt_id}/activate")
async def activate_prompt(prompt_id: str):
    from chat_store import activate_system_prompt

    ok = activate_system_prompt(prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Prompt not found")
    # Clear agent cache so next request rebuilds with new prompt
    _agent_cache.clear()
    return {"ok": True}


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


# ── 静态文件（生产模式）─────────────────────────

_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_frontend_dist):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        index = os.path.join(_frontend_dist, "index.html")
        return FileResponse(index)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
