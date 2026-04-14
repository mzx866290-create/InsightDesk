# 产品留存改造执行蓝图

目标：把当前项目从“更强一点的 AI Chat”推进为“高频用户迁移后不愿回退的知识工作台”。

适用场景：
- 作为产品排期蓝图
- 作为需求拆分依据
- 作为研发并行协作的模块边界说明

---

## 1. 核心判断

如果用户已经习惯 Cherry Studio / Cherry Chat 这一类产品，那么他愿不愿迁移，不取决于你能不能再做一个聊天框，而取决于你是否能显著提升下面 4 件事：

1. 会话是否能沉淀为工作资产，而不是一次性聊天记录
2. 资料是否能持续被复用，而不是只在本轮 prompt 里生效
3. 知识库回答是否可调、可查、可解释，而不是“偶尔答得好”
4. 对话是否能稳定产出交付物，而不是只给一段答案

基于当前代码，项目最有潜力形成壁垒的能力不是普通 chat，而是：
- 多模型答案资产化
- 附件工作区 / 会话资料库
- 可解释检索
- 证据驱动交付物

这 4 条要优先做深，不建议继续朝“更像 Cherry 的聊天客户端”方向卷功能表面。

---

## 2. 当前基础能力判断

当前仓库已经有较强基础，说明方向是对的：

- 多 panel 对话、主答案提升、单 panel 重跑已经打通
  - 前端：`frontend/src/components/chat/ChatPanel.tsx`
  - 存储：`chat_store.py`
- 附件工作区已经具备初版资产化形态
  - 前端：`frontend/src/components/chat/AttachmentWorkspace.tsx`
  - API：`api_server.py`
- DeckSpec + 编辑器 + PPTX 导出已经形成明显差异化
  - 后端：`deck_service.py`、`api_server.py`
  - 前端：`frontend/src/components/reports/`
- LangGraph 执行流程可视化已经出现
  - 前端：`frontend/src/components/workflow/WorkflowVisualizer.tsx`

但真正阻碍“迁移后不回退”的短板也很明确：

- 会话管理仍然是聊天记录视角，不是项目资产视角
- 长会话记忆治理仍然偏最近 N 条裁剪
- 检索调试接口与真实回答主链路不完全一致
- 附件仍偏“消息附件”，还不是“资料工作区”
- 多模型能力还停留在“选一个更好答案”，没有形成比较和合成工作流
- MCP 能力存在代码储备，但还没有产品化入口
- 交互细节存在原型感，中英文文案和 alert 反馈较多

---

## 3. 优先级重排

相较于当前既有任务表，本蓝图建议把优先级调整为：

### P0：先做“迁移后回不去”的核心层

1. 会话工作台
2. 长会话记忆治理
3. 检索控制台
4. 附件工作区 2.0

### P1：做高频使用闭环

1. 多模型比较 / 裁判 / 合成
2. Stop / Continue / Retry / Fork 完整闭环
3. 交付物矩阵扩展

### P2：做长期壁垒

1. Workspace 预设
2. MCP / 连接器产品化
3. 体验打磨与原型感清理

---

## 4. Phase 1：先把“工作台感”做出来

### 4.1 会话工作台

用户价值：
- 会话不再只是“聊过什么”，而是“这个项目的上下文资产”
- 重度用户在 100+ 会话下仍能快速定位、维护和复用

当前问题：
- 只有会话列表、打开、删除
- 没有搜索、改名、置顶、收藏、归档、标签
- `sessions` 表字段过少，无法支撑长期管理

涉及模块：
- `chat_store.py`
- `api_server.py`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/stores/chatStore.ts`

建议改造：
- 数据层
  - `sessions` 新增 `is_archived`
  - `sessions` 新增 `is_favorite`
  - `sessions` 新增 `tags_json`
  - 可选新增 `project_name`
- API 层
  - `PATCH /api/sessions/{session_id}`
  - `GET /api/sessions?query=&archived=&favorite=&tag=`
- 前端层
  - 侧边栏支持搜索
  - 支持会话改名
  - 支持收藏 / 归档
  - 支持标签筛选
  - 支持按“最近 / 收藏 / 归档 / 项目”分组

验收标准：
- 100+ 会话可在 5 秒内定位目标会话
- 用户能维护长期重要会话，不需要靠记忆滚动查找

建议优先级：`最高`

---

### 4.2 长会话记忆治理

用户价值：
- 降低“明明聊过却忘了”的挫败感
- 让系统从“有历史”升级成“有持续理解”

当前问题：
- 当前模型上下文仍以最近 N 条为主
- 持久化上限超出后直接裁剪旧消息
- 缺少结构化记忆层

涉及模块：
- `chat_store.py`
- `agent_core.py`
- `api_server.py`

建议改造：
- 数据层
  - 新增 `session_memory`
  - 字段建议：`id`, `session_id`, `kind`, `content`, `created_at`, `updated_at`
- 记忆类型
  - `summary`：阶段摘要
  - `fact`：固定事实
  - `decision`：重要结论
  - `todo`：后续动作
- API 层
  - `POST /api/sessions/{session_id}/memory/summarize`
  - `GET /api/sessions/{session_id}/memory`
  - `POST /api/sessions/{session_id}/memory/pin`
- Agent 层
  - 注入“最近轮次 + 结构化记忆”双层上下文
  - 长会话时优先召回 pin 记忆和阶段摘要，而不是单纯扩历史

验收标准：
- 50+ 轮长会话下，关键事实仍可稳定引用
- 用户能显式 pin 重要上下文
- 回答质量不会随着轮次增长明显下降

建议优先级：`最高`

---

### 4.3 检索控制台

用户价值：
- 把知识库能力从“黑盒”变成“可调、可查、可解释”
- 企业用户愿意长期留存的关键能力之一

当前问题：
- 主链路已使用 rerank，但调试接口仍偏基础向量检索
- 缺少 query rewrite 可见性
- 缺少粗排 / 重排 / coverage 诊断
- 缺少 hybrid 检索

涉及模块：
- `doc_pipeline.py`
- `agent_core.py`
- `api_server.py`
- `frontend/src/components/settings/SettingsModal.tsx`

建议改造：
- 检索层
  - 暴露 `fetch_k`、`top_k`
  - 新增 keyword / BM25 检索
  - 新增 hybrid 融合检索
- 诊断层
  - 返回 `rewrite_query`
  - 返回粗排候选列表
  - 返回重排后结果
  - 返回命中来源覆盖率与简单置信度
- 前端层
  - 提供检索调试面板
  - 同 query 下可切换 `semantic / keyword / hybrid`
  - 展示“真实回答链路使用的检索参数”

接口建议：
- `POST /api/knowledge-base/test-retrieval`
- `POST /api/knowledge-base/test-hybrid-retrieval`
- `POST /api/knowledge-base/search-debug`

验收标准：
- 用户能看到 query 改写结果
- 用户能即时比较不同检索策略的命中差异
- 关键词型问题在 hybrid 下明显优于当前 baseline

建议优先级：`最高`

---

### 4.4 附件工作区 2.0

用户价值：
- 从“上传文件给模型看一次”升级成“围绕资料持续工作”
- 这是从 chat 迁移到工作台的直接体验差异

当前问题：
- 已能恢复附件、复用附件、转知识库
- 但当前更像“附件面板”，还不是“会话资料库”
- 资料的引用、标注、回跳、沉淀还不够完整

涉及模块：
- `api_server.py`
- `chat_store.py`
- `frontend/src/components/chat/AttachmentWorkspace.tsx`
- `frontend/src/components/chat/MessageInput.tsx`
- `frontend/src/components/chat/MessageBubble.tsx`
- `frontend/src/components/chat/DocumentPreviewModal.tsx`

建议改造：
- 数据层
  - 单独引入 `attachments` / `message_attachments` 表
  - 不再只依赖从消息 JSON 聚合附件
- 能力层
  - 明确区分“当前会话资料库”和“全局知识库”
  - 支持附件片段级引用
  - 支持引用回跳到原消息 / 原附件
  - 支持把会话附件批量升级入知识库
- 前端层
  - 增加“资料引用”视图，不只显示文件卡片
  - 引用来源里区分：
    - 知识库来源
    - 当前会话资料来源
  - 支持“摘录到输入框”“固定为项目资料”“加入知识库”

验收标准：
- 用户能连续围绕同一资料多轮工作
- 引用附件内容时可直接预览原片段
- 附件能从当前会话平滑升级为长期知识资产

建议优先级：`最高`

---

## 5. Phase 2：把高频使用闭环补完整

### 5.1 多模型比较 / 裁判 / 合成

用户价值：
- 多模型不再只是“看哪个答得更好”，而是形成真正的比较工作流
- 这是高频重度用户最容易形成依赖的入口之一

当前问题：
- 当前主要动作还是“设为主答案”
- 缺少差异高亮、质量比较、自动合成、选择理由

涉及模块：
- `frontend/src/components/chat/ChatPanel.tsx`
- `frontend/src/components/chat/MessageBubble.tsx`
- `frontend/src/stores/chatStore.ts`
- `api_server.py`
- `chat_store.py`

建议改造：
- 前端层
  - 增加“查看差异”
  - 增加“按事实完整性 / 可执行性 / 来源质量评分”
  - 增加“合成最佳版本”
- 后端层
  - 增加 comparison / synthesis 接口
  - 保存比较结果与最终选择理由
- 数据层
  - 可选新增 `answer_groups`
  - 保存 `selected_panel_id`、`comparison_summary`

验收标准：
- 用户能快速看出 panel 差异
- 用户能把多 panel 结果合成为最终答案
- 最终答案保留来源面板与选择理由

---

### 5.2 Stop / Continue / Retry / Fork 完整闭环

用户价值：
- 贴近真实工作方式
- 用户不会因为一次长回答失败而“重开整轮”

当前问题：
- Stop 已覆盖主要流
- 但 continue / retry / fork 还没有完整产品闭环
- 后端断连与任务取消尚未完全对齐

涉及模块：
- `api_server.py`
- `frontend/src/components/chat/MessageInput.tsx`
- `frontend/src/components/chat/ChatPanel.tsx`
- `chat_store.py`

建议改造：
- API 层
  - `POST /api/messages/{message_id}/continue`
  - `POST /api/messages/{message_id}/retry`
  - `POST /api/messages/{message_id}/fork`
- 前端层
  - Stop 后保留已生成内容
  - 可继续生成
  - 可基于任意消息分叉新会话
- 存储层
  - 持久化被中断状态、分叉来源

验收标准：
- 中断后不丢已生成内容
- 用户可从失败点继续，而不是重来
- 用户可基于任意答案快速分叉项目线

---

### 5.3 交付物矩阵

用户价值：
- 让系统从“回答问题”转向“稳定产出成果”
- 这是最容易形成产品壁垒的能力之一

当前问题：
- Deck 已经很强，但仍偏单一交付物
- 报告、纪要、复盘、方案草稿还未形成统一矩阵

涉及模块：
- `deck_service.py`
- `api_server.py`
- `frontend/src/components/reports/`

建议改造：
- 统一 artifacts 抽象
  - `weekly_report`
  - `research_summary`
  - `meeting_notes`
  - `retro`
  - `proposal_draft`
  - `deck`
- 统一数据层
  - 新增 `artifacts`
- 统一导出层
  - Markdown
  - PPTX
  - 可选 HTML / PDF

验收标准：
- 用户可从同一会话一键生成多种交付物
- 每种交付物都能保留证据状态和可编辑结构

---

## 6. Phase 3：形成长期壁垒

### 6.1 Workspace 预设

用户价值：
- 让“模型 + 工具 + 知识库 + 输出格式”直接绑定成工作模式
- 比普通聊天客户端更接近真实工作台

建议能力：
- 预设默认 panel 组合
- 预设知识库绑定
- 预设工具开关
- 预设输出模板
- 导入 / 导出 workspace

涉及模块：
- `chat_store.py`
- `api_server.py`
- `frontend/src/components/settings/SettingsModal.tsx`

---

### 6.2 MCP / 连接器产品化

用户价值：
- 真正接入工作现场的数据与工具
- 形成长期迁移壁垒

当前判断：
- 代码里已经有 `mcp_servers/` 作为能力储备
- 但还不是用户可配置、可管理、可追溯的产品层

建议优先顺序：
1. 飞书 / 钉钉文档
2. GitHub
3. Jira / 禅道
4. Notion
5. 数据库查询

建议改造：
- 前端增加连接器管理区
- 后端统一 connector registry
- 工具调用结果统一保留来源元数据
- 权限、失败、重试、断线状态可见

---

### 6.3 体验打磨

这部分不是最先做，但必须收尾：

- 清理 `window.alert / alert`，统一成非阻塞反馈
- 统一中英文文案
- 减少“Settings & Upload”这类原型式组合入口
- 强化移动端和窄屏下的信息层级
- 给关键动作增加结果反馈和空态设计

---

## 7. 推荐排期

### Sprint 1

- 会话工作台第一版
- 长会话记忆治理第一版

### Sprint 2

- 检索控制台第一版
- 附件工作区 2.0 第一版

### Sprint 3

- 多模型比较 / 合成
- Continue / Retry / Fork

### Sprint 4

- 交付物矩阵第一版
- Workspace 预设第一版

### Sprint 5+

- MCP / 连接器产品化
- 全链路体验打磨

---

## 8. 第一批核心指标

建议不要只看 DAU，要重点看迁移型指标：

1. 多 panel 会话中，“设为主答案 / 合成答案”的使用率
2. 带附件会话的二次追问率
3. 知识库回答中，带来源引用的占比
4. 检索调试面板的使用率与调参后成功率
5. 长会话中，用户使用 pin 记忆 / 摘要的比率
6. 从会话生成交付物的转化率
7. 单用户周内回访会话数

---

## 9. 最终产品定位建议

一句话定位不建议写成：

“企业 AI 聊天客户端”

更建议写成：

“面向高频知识工作的 AI 工作台”

或者：

“把聊天、资料、检索和交付物串成一个闭环的知识工作台”

因为用户最终愿意留下来，不是因为你更会聊天，而是因为：
- 这里的上下文能沉淀
- 这里的资料能复用
- 这里的检索能解释
- 这里的结果能交付

---

## 10. 执行建议

从实现顺序看，最推荐你下一步直接开工的是：

1. 会话工作台
2. 长会话记忆治理
3. 检索控制台

原因：
- 这 3 个模块决定用户是否愿意把长期工作搬进来
- 附件工作区和交付物已经有较好基础，继续往深处做会更顺
- 如果先补聊天小功能，短期可见，但很难形成“回不去”的迁移动机

