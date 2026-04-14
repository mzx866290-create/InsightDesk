import argparse
import asyncio
import sys

from agent_core import build_agent, clear_session_history
from doc_pipeline import DocPipeline


async def test_rerank() -> bool:
    pipeline = DocPipeline()
    if not pipeline.load_store():
        print("Vector store is not initialized yet. Upload documents first.")
        return False

    query = "enterprise document management"
    print("=" * 60)
    print("Rerank smoke test")
    print("=" * 60)
    print(f"Query: {query}")

    print("Standard search:")
    for index, doc in enumerate(pipeline.search(query, k=3), start=1):
        print(f"{index}. {doc.metadata.get('source', 'unknown')}: {doc.page_content[:100]}")

    print("Rerank search:")
    for index, doc in enumerate(
        pipeline.search_with_rerank(query, k=3, fetch_k=10),
        start=1,
    ):
        print(f"{index}. {doc.metadata.get('source', 'unknown')}: {doc.page_content[:100]}")

    return True


async def test_memory(model_name: str, base_url: str) -> bool:
    print("=" * 60)
    print("Memory smoke test")
    print("=" * 60)

    agent = await build_agent(
        provider="local",
        model_name=model_name,
        base_url=base_url,
        temperature=0.3,
    )
    session_id = "manual-upgrade-memory"

    first = await agent.ainvoke(
        {"input": "My name is Alex."},
        config={"configurable": {"session_id": session_id}},
    )
    print(first.get("output", str(first)))

    second = await agent.ainvoke(
        {"input": "What is my name?"},
        config={"configurable": {"session_id": session_id}},
    )
    print(second.get("output", str(second)))

    clear_session_history(session_id)

    third = await agent.ainvoke(
        {"input": "What is my name?"},
        config={"configurable": {"session_id": session_id}},
    )
    print(third.get("output", str(third)))
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run upgrade-related smoke checks.")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    rerank_ok = await test_rerank()
    memory_ok = await test_memory(args.model, args.base_url)
    print("=" * 60)
    print(f"Rerank: {'ok' if rerank_ok else 'needs setup'}")
    print(f"Memory: {'ok' if memory_ok else 'failed'}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Smoke check failed: {exc}", file=sys.stderr)
        raise
