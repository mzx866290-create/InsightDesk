# Manual Checks

These scripts are optional smoke checks for local development.
They are intentionally kept out of `pytest` discovery and are not part of CI.

Available scripts:

- `langgraph_agent_smoke.py`
  Quick multi-turn smoke test for a local LangGraph agent.
- `ollama_tool_support.py`
  Inspect whether installed Ollama models appear to expose tool/function support.
- `react_format_smoke.py`
  Quick check for a simple ReAct-style local agent invocation.
- `upgrade_features_smoke.py`
  Manual check for rerank and memory-related upgrade behavior.

Run examples:

```powershell
python scripts/manual_checks/langgraph_agent_smoke.py --model qwen2.5:7b
python scripts/manual_checks/ollama_tool_support.py qwen2.5:7b llama3.1:8b
python scripts/manual_checks/react_format_smoke.py --model qwen2.5:7b
python scripts/manual_checks/upgrade_features_smoke.py --model qwen2.5:7b
```
