"""
测试 LangGraph 轻量 Agent
验证小模型（qwen3.5, phi4-mini）的速度和稳定性
"""

import asyncio
import sys
import time
from agent_core import build_agent


async def test_langgraph_with_model(model_name: str):
    """测试指定模型的 LangGraph agent"""
    print("\n" + "=" * 70)
    print(f"测试模型: {model_name}")
    print("=" * 70)
    
    try:
        start_time = time.time()
        agent = await build_agent(
            provider="local",
            model_name=model_name,
            base_url="http://localhost:11434",
            temperature=0.3,
            agent_mode="langgraph",
            verbose=True,
        )
        init_time = time.time() - start_time
        print(f"\n✓ Agent 初始化完成 (耗时: {init_time:.2f}s)")
        
    except Exception as e:
        print(f"\n✗ Agent 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    test_queries = [
        "你好",
        "知识库里有多少文档?",
        "今天的新闻有什么?",
    ]
    
    session_id = f"test-{model_name}"
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─' * 70}")
        print(f"测试 {i}/{len(test_queries)}: {query}")
        print("─" * 70)
        
        try:
            start_time = time.time()
            result = await agent.ainvoke(
                {"input": query},
                config={"configurable": {"session_id": session_id}}
            )
            elapsed = time.time() - start_time
            
            answer = result.get("output", str(result))
            print(f"\n✓ 回答 (耗时: {elapsed:.2f}s):")
            print(answer)
            
        except Exception as e:
            print(f"\n✗ 查询失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print("\n" + "=" * 70)
    print(f"✓ 模型 {model_name} 测试通过")
    print("=" * 70)
    return True


async def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("LangGraph 轻量 Agent 测试")
    print("=" * 70)
    
    models_to_test = [
        "qwen2.5:7b",
    ]
    
    results = {}
    
    for model in models_to_test:
        success = await test_langgraph_with_model(model)
        results[model] = success
    
    print("\n\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    
    for model, success in results.items():
        status = "✓ 通过" if success else "✗ 失败"
        print(f"{model}: {status}")
    
    print("=" * 70)
    print("\n提示:")
    print("- 如果要测试 qwen3.5 或 phi4-mini，请先运行:")
    print("  ollama pull qwen3.5:4b")
    print("  ollama pull phi4-mini")
    print("- 然后在上面的 models_to_test 列表中添加模型名称")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
