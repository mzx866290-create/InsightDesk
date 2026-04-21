from pathlib import Path
from typing import Any, Awaitable, Callable


async def delete_kb_directory(
    target_path: Path,
    *,
    remove_tree: Callable[[Path], None],
    clear_agent_cache: Callable[[], Awaitable[None]],
    success_message: str,
    on_success: Callable[[str], Any] | None = None,
    on_failure: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    abs_path = str(target_path)
    try:
        remove_tree(target_path)
        await clear_agent_cache()
        if on_success is not None:
            on_success(abs_path)
        return {"ok": True, "message": success_message.format(path=abs_path)}
    except Exception:
        if on_failure is not None:
            on_failure()
        raise
