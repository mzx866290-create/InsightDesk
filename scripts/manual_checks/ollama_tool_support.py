import argparse

import httpx


def check_model_tools(model_name: str, base_url: str) -> bool:
    response = httpx.post(
        f"{base_url.rstrip('/')}/api/show",
        json={"name": model_name},
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    model_info = data.get("model_info", {})
    template = str(data.get("template", "") or "")
    modelfile = str(data.get("modelfile", "") or "")
    supports_tools = any(
        hint in (template + "\n" + modelfile).lower()
        for hint in ("tool", "function")
    )

    print("=" * 60)
    print(f"Model: {model_name}")
    print("=" * 60)
    if isinstance(model_info, dict):
        print(f"Architecture: {model_info.get('general.architecture', 'N/A')}")
        print(f"Parameter count: {model_info.get('general.parameter_count', 'N/A')}")
    print(f"Supports tools: {'yes' if supports_tools else 'no'}")
    return supports_tools


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Ollama model tool support.")
    parser.add_argument(
        "models",
        nargs="*",
        default=["qwen2.5:7b", "llama3.1:8b"],
        help="Model names to inspect",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:11434",
        help="Ollama base URL",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    results = {
        model: check_model_tools(model, args.base_url)
        for model in args.models
    }
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    for model, supported in results.items():
        print(f"{model}: {'supports tools' if supported else 'no tool support detected'}")
