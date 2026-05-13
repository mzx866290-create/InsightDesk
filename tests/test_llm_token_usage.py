import asyncio
from types import SimpleNamespace

from backend.agent.llm import (
    _ainvoke_llm_with_timeout,
    _astream_llm_with_timeout,
    finish_llm_usage_capture,
    start_llm_usage_capture,
)


def test_llm_usage_capture_aggregates_provider_usage():
    class FakeLLM:
        model = "fake-model"

        async def ainvoke(self, payload):
            return SimpleNamespace(
                content="answer",
                response_metadata={
                    "token_usage": {
                        "prompt_tokens": 11,
                        "completion_tokens": 4,
                        "total_tokens": 15,
                    }
                },
            )

    async def run():
        token = start_llm_usage_capture()
        await _ainvoke_llm_with_timeout(FakeLLM(), "question")
        return finish_llm_usage_capture(token, panel_id="panel-1", model_id="fake-model")

    usage = asyncio.run(run())

    assert usage["panel_id"] == "panel-1"
    assert usage["model_id"] == "fake-model"
    assert usage["prompt_tokens"] == 11
    assert usage["completion_tokens"] == 4
    assert usage["total_tokens"] == 15
    assert usage["estimated"] is False


def test_streaming_llm_usage_capture_estimates_when_provider_omits_usage():
    class FakeStreamingLLM:
        model = "stream-model"

        async def astream(self, payload):
            yield SimpleNamespace(content="hello")
            yield SimpleNamespace(content=" world")

    async def run():
        token = start_llm_usage_capture()
        chunks = [
            chunk
            async for chunk in _astream_llm_with_timeout(
                FakeStreamingLLM(),
                "short question",
            )
        ]
        usage = finish_llm_usage_capture(
            token,
            panel_id="panel-1",
            model_id="stream-model",
        )
        return chunks, usage

    chunks, usage = asyncio.run(run())

    assert chunks == ["hello", " world"]
    assert usage["total_tokens"] > 0
    assert usage["estimated"] is True
    assert usage["estimated_count"] == 1
