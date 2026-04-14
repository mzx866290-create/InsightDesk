import argparse
import asyncio
import time

from agent_core import build_agent


async def run_smoke_test(model_name: str, base_url: str) -> bool:
    print("=" * 70)
    print(f"LangGraph smoke test for model: {model_name}")
    print("=" * 70)

    started_at = time.time()
    agent = await build_agent(
        provider="local",
        model_name=model_name,
        base_url=base_url,
        temperature=0.3,
        agent_mode="langgraph",
        verbose=True,
    )
    print(f"Agent initialized in {time.time() - started_at:.2f}s")

    queries = [
        "Hello",
        "How many documents are in the knowledge base?",
        "Summarize the latest context you can access.",
    ]
    session_id = f"manual-smoke-{model_name.replace(':', '-')}"

    for index, query in enumerate(queries, start=1):
        print("-" * 70)
        print(f"Query {index}/{len(queries)}: {query}")
        query_started_at = time.time()
        result = await agent.ainvoke(
            {"input": query},
            config={"configurable": {"session_id": session_id}},
        )
        answer = result.get("output", str(result))
        print(f"Answered in {time.time() - query_started_at:.2f}s")
        print(answer)

    print("=" * 70)
    print("Smoke test completed")
    print("=" * 70)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local LangGraph smoke test.")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_smoke_test(args.model, args.base_url))
