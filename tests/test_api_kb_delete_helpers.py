import asyncio
from pathlib import Path

from backend.helpers.kb_delete_helpers import delete_kb_directory


def test_delete_kb_directory_removes_tree_clears_cache_and_formats_message(tmp_path):
    events: list[tuple[str, object]] = []
    target = tmp_path / "vector_store"
    target.mkdir()

    async def clear_agent_cache():
        events.append(("clear_cache", None))

    payload = asyncio.run(
        delete_kb_directory(
            target,
            remove_tree=lambda path: events.append(("remove_tree", str(path))),
            clear_agent_cache=clear_agent_cache,
            success_message="deleted: {path}",
            on_success=lambda abs_path: events.append(("success", abs_path)),
        )
    )

    assert payload == {
        "ok": True,
        "message": f"deleted: {target}",
    }
    assert events == [
        ("remove_tree", str(target)),
        ("clear_cache", None),
        ("success", str(target)),
    ]


def test_delete_kb_directory_calls_failure_hook_and_reraises(tmp_path):
    events: list[tuple[str, object]] = []
    target = Path(tmp_path) / "vector_store"

    async def clear_agent_cache():
        events.append(("clear_cache", None))

    try:
        asyncio.run(
            delete_kb_directory(
                target,
                remove_tree=lambda path: (_ for _ in ()).throw(RuntimeError("boom")),
                clear_agent_cache=clear_agent_cache,
                success_message="deleted: {path}",
                on_failure=lambda: events.append(("failure", None)),
            )
        )
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("delete_kb_directory should re-raise deletion errors")

    assert events == [("failure", None)]
