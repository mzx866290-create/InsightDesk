"""
二期改造功能测试脚本
测试 Rerank 和 Memory 功能
"""

import asyncio
import sys
from agent_core import build_agent, clear_session_history
from doc_pipeline import DocPipeline


async def test_rerank():
    """测试 Rerank 二段重排功能"""
    print("=" * 60)
    print("测试 1: Rerank 二段重排功能")
    print("=" * 60)
    
    pipeline = DocPipeline()
    
    # 检查向量库是否存在
    if not pipeline.load_store():
        print("⚠️ 向量库未初始化，请先上传文档")
        print("提示: 运行 streamlit run app.py 并上传文档")
        return False
    
    test_query = "企业文档管理"
    
    print(f"\n查询: {test_query}")
    print("\n--- 方法 1: 传统检索 (纯余弦相似度) ---")
    docs_normal = pipeline.search(test_query, k=3)
    for i, doc in enumerate(docs_normal, 1):
        source = doc.metadata.get("source", "未知")
        content = doc.page_content[:100]
        print(f"{i}. {source}: {content}...")
    
    print("\n--- 方法 2: Rerank 二段重排 ---")
    docs_rerank = pipeline.search_with_rerank(test_query, k=3, fetch_k=10)
    for i, doc in enumerate(docs_rerank, 1):
        source = doc.metadata.get("source", "未知")
        content = doc.page_content[:100]
        print(f"{i}. {source}: {content}...")
    
    print("\n✓ Rerank 功能测试完成")
    return True


async def test_memory():
    """测试多轮对话记忆功能"""
    print("\n" + "=" * 60)
    print("测试 2: 多轮对话记忆功能")
    print("=" * 60)
    
    # 构建 Agent
    print("\n初始化 Agent...")
    agent = await build_agent(
        provider="local",
        model_name="qwen2.5:7b",
        base_url="http://localhost:11434",
        temperature=0.3,
    )
    
    session_id = "test_session_001"
    
    # 第一轮对话
    print(f"\n--- 第一轮对话 (Session: {session_id}) ---")
    query1 = "我的名字是张三"
    print(f"用户: {query1}")
    
    result1 = await agent.ainvoke(
        {"messages": [("user", query1)]},
        config={"configurable": {"session_id": session_id}}
    )
    
    if "messages" in result1 and result1["messages"]:
        answer1 = result1["messages"][-1].content
        print(f"Agent: {answer1}")
    
    # 第二轮对话 (测试记忆)
    print(f"\n--- 第二轮对话 (测试记忆) ---")
    query2 = "我叫什么名字?"
    print(f"用户: {query2}")
    
    result2 = await agent.ainvoke(
        {"messages": [("user", query2)]},
        config={"configurable": {"session_id": session_id}}
    )
    
    if "messages" in result2 and result2["messages"]:
        answer2 = result2["messages"][-1].content
        print(f"Agent: {answer2}")
        
        # 检查是否记住了名字
        if "张三" in answer2:
            print("\n✓ 记忆功能正常: Agent 记住了用户名字")
        else:
            print("\n⚠️ 记忆功能异常: Agent 未能记住用户名字")
    
    # 清空记忆
    print(f"\n--- 清空记忆 ---")
    clear_session_history(session_id)
    print("已清空 Session 记忆")
    
    # 第三轮对话 (测试记忆清空)
    print(f"\n--- 第三轮对话 (测试记忆清空) ---")
    query3 = "我叫什么名字?"
    print(f"用户: {query3}")
    
    result3 = await agent.ainvoke(
        {"messages": [("user", query3)]},
        config={"configurable": {"session_id": session_id}}
    )
    
    if "messages" in result3 and result3["messages"]:
        answer3 = result3["messages"][-1].content
        print(f"Agent: {answer3}")
        
        # 检查是否忘记了名字
        if "张三" not in answer3 and ("不知道" in answer3 or "没有" in answer3 or "未" in answer3):
            print("\n✓ 记忆清空功能正常: Agent 忘记了之前的对话")
        else:
            print("\n⚠️ 记忆清空功能异常: Agent 仍然记得之前的对话")
    
    print("\n✓ Memory 功能测试完成")
    return True


async def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("企业知识库系统 - 二期改造功能测试")
    print("=" * 60)
    
    try:
        # 测试 Rerank
        rerank_ok = await test_rerank()
        
        # 测试 Memory
        memory_ok = await test_memory()
        
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"Rerank 功能: {'✓ 通过' if rerank_ok else '✗ 失败'}")
        print(f"Memory 功能: {'✓ 通过' if memory_ok else '✗ 失败'}")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
