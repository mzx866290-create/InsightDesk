# 留存改造 Sprint Backlog

目标：把 [PRODUCT_RETENTION_EXECUTION_BLUEPRINT.md](f:/项目/AI智能体/PRODUCT_RETENTION_EXECUTION_BLUEPRINT.md) 进一步拆成可执行 backlog，便于直接排期、分工和验收。

---

## Sprint 1

主题：会话工作台 + 长会话记忆治理第一版

### S1-1 会话元数据扩展

结果：
- 会话支持收藏、归档、标签
- 后端能按条件过滤会话列表

涉及文件：
- `chat_store.py`
- `api_server.py`
- `frontend/src/api/client.ts`
- `frontend/src/stores/chatStore.ts`

具体任务：
- 为 `sessions` 表增加 `is_archived`
- 为 `sessions` 表增加 `is_favorite`
- 为 `sessions` 表增加 `tags_json`
- 为 `Session` 类型补充对应字段
- 为会话列表接口增加过滤参数

验收：
- 可以返回 `favorite / archived / tags`
- 列表接口支持 `query / archived / favorite / tag`

---

### S1-2 侧边栏升级为会话工作台第一版

结果：
- 用户可在侧边栏搜索会话、改名会话、收藏会话、归档会话

涉及文件：
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/stores/chatStore.ts`
- `frontend/src/api/client.ts`

具体任务：
- 顶部增加搜索框
- 每个 session 增加收藏、归档、改名入口
- 增加“全部 / 收藏 / 归档”切换
- 增加标签展示

验收：
- 100+ 会话下仍可快速定位目标会话
- 收藏与归档状态刷新后不丢失

---

### S1-3 会话 Patch 接口

结果：
- 前端所有会话编辑动作都走统一 PATCH 接口

涉及文件：
- `api_server.py`
- `chat_store.py`
- `frontend/src/api/client.ts`

具体任务：
- 新增 `PATCH /api/sessions/{session_id}`
- 支持更新 `title`
- 支持更新 `is_archived`
- 支持更新 `is_favorite`
- 支持更新 `tags`

验收：
- 单字段修改可用
- 多字段同时修改可用
- 非法 session 返回 404

---

### S1-4 结构化会话记忆表

结果：
- 系统拥有独立于消息历史的记忆层

涉及文件：
- `chat_store.py`
- `api_server.py`
- `agent_core.py`

具体任务：
- 新增 `session_memory` 表
- 封装 memory CRUD
- 设计 `summary / fact / decision / todo` 四类记忆

验收：
- 可读写记忆条目
- 每条记忆可带时间戳和类型

---

### S1-5 手动 pin 记忆第一版

结果：
- 用户能把一段重要事实固定为记忆

涉及文件：
- `api_server.py`
- `chat_store.py`
- `frontend/src/components/chat/MessageBubble.tsx`

具体任务：
- 增加 `POST /api/sessions/{session_id}/memory/pin`
- 在消息操作里增加“固定到记忆”
- pin 后在 session 级可读

验收：
- 能从消息内容生成 pin 记忆
- pin 后刷新仍保留

---

### S1-6 记忆读取注入第一版

结果：
- Agent 在长会话中不只依赖最近 N 条消息

涉及文件：
- `agent_core.py`
- `chat_store.py`

具体任务：
- 在会话上下文构造时注入 `pinned memory + recent turns`
- 先不做自动总结，只接入手动 pin

验收：
- pin 的关键信息能在后续轮次稳定被引用

---

## Sprint 2

主题：检索控制台 + 附件工作区 2.0 第一版

### S2-1 检索调试接口升级

结果：
- 检索调试接口与主链路更一致

涉及文件：
- `doc_pipeline.py`
- `agent_core.py`
- `api_server.py`

具体任务：
- 扩展 `POST /api/knowledge-base/test-retrieval`
- 返回 `fetch_k`
- 返回 `top_k`
- 返回 `rewrite_query`
- 返回粗排候选
- 返回重排结果
- 返回简单 coverage

验收：
- 调试接口能够解释主链路结果

---

### S2-2 Keyword / BM25 检索第一版

结果：
- 关键词问题不再完全依赖向量召回

涉及文件：
- `doc_pipeline.py`
- `api_server.py`

具体任务：
- 增加 keyword 检索器
- 设计统一返回结构
- 允许 `semantic / keyword / hybrid` 三种模式

验收：
- 关键词命中类 query 明显优于当前 baseline

---

### S2-3 检索控制台 UI

结果：
- 用户可在设置区直接调试检索

涉及文件：
- `frontend/src/components/settings/SettingsModal.tsx`
- `frontend/src/api/client.ts`

具体任务：
- 增加 retrieval debug tab
- 输入 query 后查看 top results
- 比较不同检索模式
- 可调 `fetch_k / top_k`

验收：
- 用户可在 UI 里完成调参与结果观察

---

### S2-4 附件工作区独立数据层

结果：
- 附件不再完全依赖从消息 JSON 聚合

涉及文件：
- `chat_store.py`
- `api_server.py`

具体任务：
- 新增 `attachments`
- 新增 `message_attachments`
- 为历史消息迁移附件元信息

验收：
- 历史附件可独立查询
- 可按 `attachment_id` 稳定引用

---

### S2-5 附件引用回跳

结果：
- 用户能从附件项跳回来源轮次和引用片段

涉及文件：
- `frontend/src/components/chat/AttachmentWorkspace.tsx`
- `frontend/src/components/chat/MessageBubble.tsx`
- `frontend/src/components/chat/CitationPanel.tsx`

具体任务：
- 附件项增加“跳到对话”
- 引用来源区分“知识库来源 / 会话资料来源”
- 附件片段级 excerpt 可预览

验收：
- 用户可以直接回到原上下文

---

## Sprint 3

主题：多模型工作流化 + Continue/Retry/Fork

### S3-1 多模型差异视图

结果：
- 同轮多 panel 回答可比较而不是只能手动读

涉及文件：
- `frontend/src/components/chat/ChatPanel.tsx`
- `frontend/src/components/chat/MessageBubble.tsx`

具体任务：
- 增加“查看差异”
- 高亮结构差异与来源差异

---

### S3-2 多模型合成最佳答案

结果：
- 用户可基于多个 panel 结果生成最终版本

涉及文件：
- `api_server.py`
- `agent_core.py`
- `frontend/src/components/chat/ChatPanel.tsx`

具体任务：
- 增加 synthesis 接口
- 保存合成结果的来源说明

---

### S3-3 Continue / Retry / Fork

结果：
- 中断、失败、分支都进入完整工作流

涉及文件：
- `api_server.py`
- `chat_store.py`
- `frontend/src/components/chat/MessageInput.tsx`
- `frontend/src/components/chat/ChatPanel.tsx`

具体任务：
- `POST /api/messages/{message_id}/continue`
- `POST /api/messages/{message_id}/retry`
- `POST /api/messages/{message_id}/fork`

验收：
- Stop 后可继续
- 失败后可快速重试
- 任意回答可分叉为新会话

---

## Sprint 4

主题：交付物矩阵 + Workspace 预设

### S4-1 Artifacts 统一抽象

结果：
- Deck、报告、纪要、复盘共享统一对象层

涉及文件：
- `deck_service.py`
- `api_server.py`
- `frontend/src/components/reports/`

---

### S4-2 交付物矩阵第一版

结果：
- 同一会话支持多个交付物类型

类型建议：
- deck
- weekly_report
- research_summary
- meeting_notes
- retro
- proposal_draft

---

### S4-3 Workspace 预设第一版

结果：
- 用户可以保存一套工作模式

涉及文件：
- `chat_store.py`
- `api_server.py`
- `frontend/src/components/settings/SettingsModal.tsx`

---

## Sprint 5+

主题：连接器与体验打磨

### S5-1 MCP / 连接器产品化

优先顺序：
1. 飞书 / 钉钉文档
2. GitHub
3. Jira / 禅道
4. Notion
5. 数据库查询

---

### S5-2 体验去原型化

结果：
- 系统从“工程原型”升级到“高频可用产品”

具体任务：
- 清理 `alert / window.alert`
- 统一中英文文案
- 统一错误反馈
- 优化空态、加载态、成功反馈

---

## 并行建议

推荐第一轮并行方式：

- 后端 A：会话工作台数据层 + API
- 前端 A：Sidebar 工作台 UI
- 后端 B：session_memory 表 + pin 接口
- 前端 B：消息 pin 入口

推荐第二轮并行方式：

- 后端 A：检索调试接口
- 前端 A：检索控制台 UI
- 后端 B：附件独立表
- 前端 B：附件回跳与引用区分

---

## 验收顺序建议

每个 Sprint 都按这个顺序验收：

1. 数据结构稳定
2. API 返回结构稳定
3. 前端主路径可用
4. 刷新恢复正常
5. 异常路径可解释
6. 有最小自动化测试

