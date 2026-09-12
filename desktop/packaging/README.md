# InsightDesk 桌面版打包

两层结构：

```
后端 (PyInstaller onedir)            壳 (Electron + NSIS 安装包)
desktop/pyinstaller/dist/   ──打包──▶ desktop/electron/dist/
insightdesk-backend/                 InsightDesk-Setup-2.0.0.exe
```

## 1. 构建后端 onedir 包

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_backend_exe.ps1
```

产物：`desktop/pyinstaller/dist/insightdesk-backend/insightdesk-backend.exe`
（含 frontend/dist，单端口同时服务 API 与 SPA；数据落在工作目录，Electron
启动时会把 cwd 设为系统 userData 目录。）

## 2. 构建 Windows 安装包

```powershell
cd desktop\electron
npm install
npm run dist
```

产物：`desktop/electron/dist/InsightDesk-Setup-2.0.0.exe`（NSIS 安装器，
后端 onedir 作为 extraResource 打进安装目录的 resources/backend）。

## 运行行为

- 启动时自动选择空闲端口（8000 起），后端仅绑定 127.0.0.1（本地免鉴权路径）；
- 等待 `/api/health` 就绪后加载 UI；关闭窗口即结束后端进程；
- 开发模式：无打包后端时回退到 `venv312\Scripts\python.exe -m uvicorn
  backend.api_server:app`（源码目录下 `npm start`）。

## 注意

- 首次 `npm run dist` 会下载 Electron 与 NSIS 工具链（需网络）；
- 全量打包含 torch/sentence-transformers（本地嵌入与重排），产物体积较大；
  云端精简版可在此基础上加 excludes 裁剪（doc_pipeline 对缺失依赖的降级
  路径见 backend/doc_pipeline_constants 与各 mixin 的延迟导入说明）。
