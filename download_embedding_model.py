"""
下载 BAAI/bge-large-zh-v1.5 到指定目录
使用国内镜像加速
"""

import os

# 使用国内镜像
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from huggingface_hub import snapshot_download

# 下载到 E:\AI_Models\huggingface\hub
local_dir = r"E:\AI_Models\huggingface\hub\bge-large-zh-v1.5"
os.makedirs(local_dir, exist_ok=True)

print("开始下载 BAAI/bge-large-zh-v1.5 ...")
print(f"目标目录: {local_dir}")
print("使用镜像: https://hf-mirror.com")
print("-" * 50)

snapshot_download(
    repo_id="BAAI/bge-large-zh-v1.5",
    local_dir=local_dir,
    local_dir_use_symlinks=False,
)

print("-" * 50)
print("下载完成!")
print(f"模型已保存到: {local_dir}")
print("\n在 .env 中配置:")
print(f"EMBEDDING_MODEL={local_dir}")
