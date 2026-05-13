from __future__ import annotations

import re
from urllib.parse import quote


def build_download_content_disposition(filename: str) -> str:
    raw_filename = str(filename or "").strip() or "download"
    ascii_only = all(ord(char) < 128 for char in raw_filename)
    if ascii_only:
        escaped = raw_filename.replace("\\", "\\\\").replace('"', r"\"")
        return f'attachment; filename="{escaped}"'

    ascii_fallback = re.sub(r"[^A-Za-z0-9._-]+", "_", raw_filename).strip("._")
    if not ascii_fallback:
        ascii_fallback = "download"
    encoded = quote(raw_filename, safe="")
    return f"attachment; filename={ascii_fallback}; filename*=UTF-8''{encoded}"


def classify_runtime_error(exc: Exception) -> dict[str, str]:
    msg = str(exc)
    if isinstance(exc, ConnectionError) or any(
        keyword in msg
        for keyword in ("Connection refused", "ConnectError", "connect ECONNREFUSED")
    ):
        return {
            "code": "MODEL_UNAVAILABLE",
            "message": "模型服务暂时不可用",
            "suggestion": "请检查 Ollama 是否已启动，或稍后重试",
        }
    if any(
        keyword in msg
        for keyword in ("API Key", "api_key", "401", "Unauthorized", "authentication")
    ):
        return {
            "code": "AUTH_FAILED",
            "message": "API 认证失败",
            "suggestion": "请在设置中检查 API Key 是否正确",
        }
    if any(keyword in msg for keyword in ("timeout", "Timeout", "TimeoutError", "timed out")):
        return {
            "code": "TIMEOUT",
            "message": "请求超时，模型响应过慢",
            "suggestion": "请稍后重试，或尝试切换为响应更快的模型",
        }
    if any(keyword in msg for keyword in ("rate limit", "429", "quota")):
        return {
            "code": "RATE_LIMIT",
            "message": "API 调用频率已达上限",
            "suggestion": "请稍等片刻后重试",
        }
    if any(
        keyword in msg.lower()
        for keyword in (
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
    if any(keyword in msg for keyword in ("Invalid model", "model not found", "404")):
        return {
            "code": "MODEL_NOT_FOUND",
            "message": "指定的模型不存在",
            "suggestion": "请在面板顶部的模型选择器中确认模型名称是否正确",
        }
    if any(keyword in msg for keyword in ("max iterations", "Agent stopped", "iteration limit")):
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
