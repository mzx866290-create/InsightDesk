"""
快速测试 ReAct 格式修复效果
不依赖 Reranker 模型下载
"""

import asyncio
import sys
from agent_core import build_agent


async def test_react_format():
    """测试 ReAct 格式解析修复"""
    print("=" * 60)
    print("测试 ReAct 格式解析修复")
    print("=" * 60)
    
    # 构建 Agent
    print("\n初始化 Agent...")
    agent = await build_agent(
        provider="local",
        model_name="qwen3.5:4b",
        base_url="http://localhost:11434",
        temperature=0.3,
        verbose=True,
    )
    
    session_id = "test_react_format"
    
    # 测试简单问题（不需要联网）
    print(f"\n--- 测试问题 ---")
    query = "知识库里有多少文档?"
    print(f"用户: {query}")
    
    try:
        result = await agent.ainvoke(
            {"input": query},
            config={"configurable": {"session_id": session_id}}
        )
        
        print(f"\n✓ 测试成功!")
        print(f"回答: {result['output']}")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("ReAct 格式修复 - 快速测试")
    print("=" * 60)
    
    success = await test_react_format()
    
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    print(f"ReAct 格式解析: {'✓ 通过' if success else '✗ 失败'}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
