"""
测试 Ollama 模型是否支持工具调用
"""
import requests
import json

def check_model_tools(model_name: str):
    """检查模型是否支持工具"""
    try:
        response = requests.post(
            "http://localhost:11434/api/show",
            json={"name": model_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"\n{'='*60}")
        print(f"模型: {model_name}")
        print(f"{'='*60}")
        
        # 检查关键字段
        if "model_info" in data:
            model_info = data["model_info"]
            print(f"架构: {model_info.get('general.architecture', 'N/A')}")
            print(f"参数量: {model_info.get('general.parameter_count', 'N/A')}")
        
        # 检查是否支持工具
        template = data.get("template", "")
        modelfile = data.get("modelfile", "")
        
        # 通过模板判断是否支持工具
        supports_tools = False
        if "tool" in template.lower() or "function" in template.lower():
            supports_tools = True
        if "tool" in modelfile.lower():
            supports_tools = True
            
        print(f"\n支持工具调用: {'✓ 是' if supports_tools else '✗ 否'}")
        
        if not supports_tools:
            print("\n⚠️ 此模型不支持工具调用，无法用于当前系统")
        
        return supports_tools
        
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    models = [
        "qwen3.5:4b",
        "qwen3.5-2b:latest",
        "qwen3.5-4b-un:latest"
    ]
    
    print("开始检查已安装模型的工具支持情况...\n")
    
    results = {}
    for model in models:
        results[model] = check_model_tools(model)
    
    print(f"\n{'='*60}")
    print("总结")
    print(f"{'='*60}")
    for model, supports in results.items():
        status = "✓ 支持" if supports else "✗ 不支持"
        print(f"{model}: {status}")
    
    supported = [m for m, s in results.items() if s]
    if supported:
        print(f"\n推荐使用: {supported[0]}")
    else:
        print("\n⚠️ 所有模型都不支持工具，建议下载:")
        print("  ollama pull qwen2.5:7b")
        print("  ollama pull llama3.1:8b")
