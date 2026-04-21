import argparse
import asyncio

from backend.agent_core import build_agent


async def run_react_smoke(model_name: str, base_url: str) -> bool:
    print("=" * 60)
    print("ReAct-style smoke test")
    print("=" * 60)

    agent = await build_agent(
        provider="local",
        model_name=model_name,
        base_url=base_url,
        temperature=0.3,
        verbose=True,
    )

    query = "How many documents are currently in the knowledge base?"
    result = await agent.ainvoke(
        {"input": query},
        config={"configurable": {"session_id": "manual-react-smoke"}},
    )
    print(result.get("output", str(result)))
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a ReAct smoke test.")
    parser.add_argument("--model", default="qwen2.5:7b", help="Ollama model name")
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_react_smoke(args.model, args.base_url))
