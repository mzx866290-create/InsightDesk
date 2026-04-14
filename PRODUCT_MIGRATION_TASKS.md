# 产品迁移开发任务表

目标：把当前项目从“可用的 AI 聊天 + 知识库原型”推进为“重度用户迁移后不愿回退的知识工作台”。

原则：
- 优先做会显著提升高频使用黏性的功能，而不是先补齐低频边角功能。
- 优先把已有能力做成完整工作流，而不是继续堆分散能力点。
- 每个阶段都要求可演示、可测试、可量化。

## 当前进度（2026-04-07）

- `阶段 1 / 任务 1 多面板对比资产化`：MVP 已完成
  - 已打通多 panel 持久化、按 panel 恢复、`answer_group_id` 分组、设为主答案、单 panel 重跑、并发锁定。
  - 已补充重跑可停止的最小闭环，用户不会在重跑时被完全锁死。
- `阶段 1 / 任务 2 附件工作区`：MVP 已启动
  - 已完成：附件随消息持久化、刷新后恢复附件卡片、文本附件预览、模型历史可重新读到附件提取文本。
  - 未完成：独立附件工作区面板、附件级引用跳转、附件转知识库。
- `阶段 1 / 任务 3 检索控制台`：未开始
- `阶段 2 / 任务 6 停止、重试、分叉`：已启动最小闭环
  - 已完成：Stop 按钮覆盖主发送流和单 panel 重跑流。
  - 未完成：继续生成、重试本轮、分叉新会话、后端级取消与持久化对齐。

当前判断：
- 项目整体仍处于 `阶段 1`，其中 `任务 1` 已完成 MVP，`任务 2` 已进入第一轮实现。
- 下一优先建议是继续完成 `阶段 1 / 任务 2 附件工作区`，把附件从“消息级恢复”推进到“独立工作区 + 引用回跳”。

---

## 阶段 1：先把核心迁移动机做出来

### 1. 多面板对比资产化

用户价值：
- 不只是“同时问多个模型”，而是能沉淀、复看、复跑、选优。
- 让多模型能力从演示功能变成日常工作流。

当前问题：
- 只有首个 panel 持久化历史。
- 重新打开会话时，所有 panel 被加载同一份消息。
- 数据层虽然有 `model_id` 字段，但没有真正形成按 panel / 模型保存的完整链路。

改动范围：
- [api_server.py](f:/项目/AI智能体/api_server.py)
- [agent_core.py](f:/项目/AI智能体/agent_core.py)
- [chat_store.py](f:/项目/AI智能体/chat_store.py)
- [frontend/src/stores/chatStore.ts](f:/项目/AI智能体/frontend/src/stores/chatStore.ts)
- [frontend/src/components/layout/Sidebar.tsx](f:/项目/AI智能体/frontend/src/components/layout/Sidebar.tsx)
- [frontend/src/components/chat/ChatPanel.tsx](f:/项目/AI智能体/frontend/src/components/chat/ChatPanel.tsx)

建议拆分：
- 数据层
  - 为消息补充 `panel_id`、`model_id`、`answer_group_id`。
  - 同一轮用户提问生成一个 `answer_group_id`，把多个 panel 的回答挂到同一组下。
- API 层
  - 新增“按会话获取多 panel 消息结构”的接口。
  - 新增“设为主答案 / 复制到主线 / 重新运行某个 panel”的接口。
- 前端层
  - 为每轮回答增加“设为主答案”“仅重跑当前模型”“查看差异”。
  - 会话恢复时按 panel 恢复，不再把同一内容灌给所有 panel。

接口建议：
- `GET /api/sessions/{session_id}/panel-messages`
- `POST /api/messages/{answer_group_id}/promote`
- `POST /api/messages/{answer_group_id}/rerun`

数据表建议：
- `messages`
  - 新增 `panel_id TEXT DEFAULT ''`
  - 新增 `answer_group_id TEXT DEFAULT ''`
- 可选新增 `answer_groups`
  - `id`, `session_id`, `user_message_id`, `created_at`, `promoted_panel_id`

验收标准：
- 同一轮提问的多个 panel 回答能独立保存并恢复。
- 用户可以把任一 panel 回答设为主答案。
- 用户可以单独重跑某个 panel，不影响其他 panel。

测试建议：
- 后端
  - 同一 session 多 panel 回答写入后，查询结果结构正确。
  - promote 后主答案标记正确。
  - rerun 只影响指定 panel。
- 前端
  - 刷新页面后 panel 消息仍能正确恢复。
  - 设为主答案后 UI 状态更新正确。

优先级：`P0`
预估工期：`5-7 天`

---

### 2. 附件工作区

用户价值：
- 上传资料后可以连续围绕资料追问，而不是一次性读完就丢。
- 用户会感觉这不是“发一段 prompt”，而是在“操作自己的工作材料”。

当前问题：
- 附件仅被抽取文本后拼到 prompt。
- 历史中只保留“上传了几个文件”的摘要。
- 重新加载会话时看不到附件内容与引用关系。

改动范围：
- [api_server.py](f:/项目/AI智能体/api_server.py)
- [chat_store.py](f:/项目/AI智能体/chat_store.py)
- [frontend/src/api/client.ts](f:/项目/AI智能体/frontend/src/api/client.ts)
- [frontend/src/components/chat/MessageInput.tsx](f:/项目/AI智能体/frontend/src/components/chat/MessageInput.tsx)
- [frontend/src/components/chat/MessageBubble.tsx](f:/项目/AI智能体/frontend/src/components/chat/MessageBubble.tsx)
- [frontend/src/components/chat/DocumentPreviewModal.tsx](f:/项目/AI智能体/frontend/src/components/chat/DocumentPreviewModal.tsx)

建议拆分：
- 数据层
  - 为消息存储附件元信息，不只保存文本摘要。
  - 为附件生成 `attachment_id`，后续引用来源可回跳到附件。
- 能力层
  - 增加“消息级临时资料库”，先不强制进入全局知识库。
  - 支持“将附件加入知识库”。
- 前端层
  - 在消息气泡下展示附件卡片和可预览内容。
  - 在引用来源中区分“知识库来源”和“当前会话附件来源”。

接口建议：
- `POST /api/chat/attachments/prepare`
- `GET /api/sessions/{session_id}/attachments`
- `POST /api/attachments/{attachment_id}/promote-to-kb`

数据表建议：
- 新增 `attachments`
  - `attachment_id`, `session_id`, `message_id`, `name`, `media_type`, `size_bytes`, `extracted_text`, `created_at`
- 新增 `message_attachments`
  - `message_id`, `attachment_id`

验收标准：
- 刷新页面后仍可看到历史消息上的附件。
- 助手引用附件内容时，用户可直接预览被引用片段。
- 用户可将附件一键转入知识库。

测试建议：
- PDF、DOCX、TXT、XLSX 附件解析成功。
- 附件超限、空内容、不可读内容时返回明确错误。
- 附件转知识库后可通过知识库检索命中。

优先级：`P0`
预估工期：`4-6 天`

---

### 3. 检索控制台

用户价值：
- 让知识库回答从“偶尔答得好”变成“稳定可信、可调可查”。
- 这是企业用户长期留下来的关键能力。

当前问题：
- 当前主链路仍以向量检索 + rerank 为主。
- 缺少 query 解释、参数调节、混合检索、命中诊断。

改动范围：
- [doc_pipeline.py](f:/项目/AI智能体/doc_pipeline.py)
- [agent_core.py](f:/项目/AI智能体/agent_core.py)
- [api_server.py](f:/项目/AI智能体/api_server.py)
- [frontend/src/components/settings/SettingsModal.tsx](f:/项目/AI智能体/frontend/src/components/settings/SettingsModal.tsx)

建议拆分：
- 检索层
  - 暴露 `fetch_k`、`top_k`。
  - 增加 BM25 / keyword 检索。
  - 增加 hybrid 检索融合。
- 诊断层
  - 返回 query rewrite 结果。
  - 返回粗排候选、重排后结果、命中来源覆盖率。
  - 对回答附加简单置信度标识。
- 前端层
  - 提供检索调试面板。
  - 支持输入测试 query 后查看 top results。

接口建议：
- `POST /api/knowledge-base/test-retrieval`
  - 增加返回 `rewrite_query`, `fetch_k`, `top_k`, `retrieval_mode`, `coverage`
- `POST /api/knowledge-base/test-hybrid-retrieval`
- `POST /api/knowledge-base/search-debug`

数据结构建议：
- 不一定先改表，可先扩展接口返回结构。

验收标准：
- 用户可看到 query 改写后的检索词。
- 用户可调整 `fetch_k/top_k` 并即时观察结果差异。
- hybrid 检索对关键词类问题效果明显优于当前基线。

测试建议：
- 构建固定测试题集。
- 对比 semantic / keyword / hybrid 三种模式下的命中表现。
- 为返回结构补充 API 测试。

优先级：`P0`
预估工期：`6-8 天`

---

## 阶段 2：把高频使用体验补完整

### 4. 会话工作台

用户价值：
- 会话不再只是历史记录，而是项目资产。

改动范围：
- [chat_store.py](f:/项目/AI智能体/chat_store.py)
- [api_server.py](f:/项目/AI智能体/api_server.py)
- [frontend/src/components/layout/Sidebar.tsx](f:/项目/AI智能体/frontend/src/components/layout/Sidebar.tsx)

建议功能：
- 会话改名
- 会话搜索
- 置顶 / 收藏
- 归档
- 按项目或标签分组

接口建议：
- `PATCH /api/sessions/{session_id}`
- `GET /api/sessions?query=&archived=&favorite=`

数据表建议：
- `sessions`
  - 新增 `is_archived INTEGER DEFAULT 0`
  - 新增 `is_favorite INTEGER DEFAULT 0`
  - 新增 `tags_json TEXT DEFAULT '[]'`

验收标准：
- 100+ 会话下仍可快速定位目标会话。
- 用户能手动维护长期重要会话。

优先级：`P1`
预估工期：`3-5 天`

---

### 5. 长会话记忆治理

用户价值：
- 减少“它明明聊过却忘了”的挫败感。

改动范围：
- [chat_store.py](f:/项目/AI智能体/chat_store.py)
- [agent_core.py](f:/项目/AI智能体/agent_core.py)

建议功能：
- 自动阶段总结
- 固定事实卡
- 重要结论 pin 到会话记忆
- 主题检索历史轮次

接口建议：
- `POST /api/sessions/{session_id}/memory/summarize`
- `GET /api/sessions/{session_id}/memory`
- `POST /api/sessions/{session_id}/memory/pin`

数据表建议：
- 新增 `session_memory`
  - `id`, `session_id`, `kind`, `content`, `created_at`, `updated_at`

验收标准：
- 长会话下关键事实仍能稳定被引用。
- 历史轮数增长后回答质量不明显下降。

优先级：`P1`
预估工期：`5-7 天`

---

### 6. 停止、重试、分叉

用户价值：
- 更符合高频用户的真实工作方式。

改动范围：
- [frontend/src/components/chat/MessageInput.tsx](f:/项目/AI智能体/frontend/src/components/chat/MessageInput.tsx)
- [frontend/src/components/chat/ChatPanel.tsx](f:/项目/AI智能体/frontend/src/components/chat/ChatPanel.tsx)
- [api_server.py](f:/项目/AI智能体/api_server.py)

建议功能：
- Stop 后保留已生成内容
- 继续生成
- 重试本轮
- 基于任意回答分叉新会话

接口建议：
- `POST /api/messages/{message_id}/continue`
- `POST /api/messages/{message_id}/retry`
- `POST /api/messages/{message_id}/fork`

验收标准：
- 用户中断长回答后仍能保留已生成内容。
- 用户可以快速对失败回答继续修正，而不是从头再来。

优先级：`P1`
预估工期：`3-4 天`

---

## 阶段 3：形成明显差异化

### 7. Workspace 预设

用户价值：
- 一套预设直接决定“用什么模型 + 查哪个库 + 输出什么样式”。
- 这是比普通聊天客户端更接近真实工作的抽象。

改动范围：
- [chat_store.py](f:/项目/AI智能体/chat_store.py)
- [api_server.py](f:/项目/AI智能体/api_server.py)
- [frontend/src/components/settings/SettingsModal.tsx](f:/项目/AI智能体/frontend/src/components/settings/SettingsModal.tsx)

建议功能：
- 在当前 prompt 绑定基础上，继续绑定默认 panel 配置
- 绑定工具开关
- 绑定默认输出模板
- 支持导出 / 导入预设

接口建议：
- `GET /api/workspaces`
- `POST /api/workspaces`
- `PUT /api/workspaces/{workspace_id}`
- `POST /api/workspaces/{workspace_id}/activate`

数据表建议：
- 新增 `workspaces`
  - `id`, `name`, `prompt_id`, `default_panels_json`, `tool_config_json`, `output_preset_json`, `created_at`, `updated_at`

优先级：`P2`
预估工期：`4-6 天`

---

### 8. 交付物矩阵

用户价值：
- 不只会回答，还能稳定产出可交付结果。

改动范围：
- [deck_service.py](f:/项目/AI智能体/deck_service.py)
- [api_server.py](f:/项目/AI智能体/api_server.py)
- [frontend/src/components/reports](f:/项目/AI智能体/frontend/src/components/reports)

建议功能：
- 周报
- 调研报告
- 会议纪要
- 复盘文档
- 方案草稿

接口建议：
- `POST /api/artifacts/generate`
- `GET /api/artifacts/{artifact_id}`
- `PATCH /api/artifacts/{artifact_id}`
- `GET /api/artifacts/{artifact_id}/export`

数据表建议：
- 新增 `artifacts`
  - `id`, `session_id`, `type`, `status`, `content_json`, `created_at`, `updated_at`

优先级：`P2`
预估工期：`5-8 天`

---

### 9. 连接器 / MCP 工具生态

用户价值：
- 真正接入工作现场数据，形成长期壁垒。

改动范围：
- [mcp_servers](f:/项目/AI智能体/mcp_servers)
- [agent_core.py](f:/项目/AI智能体/agent_core.py)
- [api_server.py](f:/项目/AI智能体/api_server.py)

建议优先顺序：
- 飞书 / 钉钉文档
- GitHub
- Jira / 禅道
- Notion
- 数据库查询

验收标准：
- 用户可在同一工作台里调用外部系统内容。
- 工具来源可追溯、结果可引用。

优先级：`P2`
预估工期：`每个连接器 1-2 周`

---

## 建议排期

### Sprint 1
- 多面板对比资产化
- Stop / Retry 最小闭环

### Sprint 2
- 附件工作区
- 检索控制台第一版

### Sprint 3
- 会话工作台
- 长会话记忆治理第一版

### Sprint 4
- Workspace 预设
- 交付物矩阵扩展

---

## 推荐的第一批验收指标

- 多 panel 会话中，使用“设为主答案”的比例
- 带附件会话的二次追问率
- 知识库回答中带来源回答的占比
- 从首次提问到导出 deck 的中位耗时
- 7 日回访用户占比
- 平均单会话轮数

---

## 最后建议

如果资源有限，先只做这三件：
- 多面板对比资产化
- 附件工作区
- 检索控制台

这三项最能直接回答用户为什么要从 Cherry Chat 迁过来，而且做完后用户会明显感觉这是“工作平台”，不是“另一个聊天壳”。
