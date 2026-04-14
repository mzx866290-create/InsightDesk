# 按 NotebookLM 思路重做 PPT 功能的完整改造方案

## 1. 先说结论

这次改造不应该继续沿着“对话历史 -> 一次性吐 Markdown/PPTX 文件”的路径打补丁，而应该把 PPT 功能升级成一条四层流水线：

1. `Source Selection`：用户明确选中哪些资料、哪些会话结论进入本次演示稿。
2. `Deck Planning`：LLM 只负责生成可审阅、可编辑、可追溯的 `Deck Spec` 中间层。
3. `Preview & Edit`：前端按 `Deck Spec` 渲染成可视化演示稿编辑器，用户先改内容，再看版式。
4. `Export Rendering`：最后一步才调用专门渲染引擎导出为 `pptx/pdf/html`。

核心思想不是“让模型直接生成 PPT”，而是“让模型生成一个有来源约束的演示稿语义结构”。

---

## 2. 当前实现的真实问题

基于当前代码，现状大致是：

- 后端把会话历史直接拼成 Slidev Markdown。
- 前端只做一个 Markdown 切页预览。
- 导出时再用 `python-pptx` 把 Q&A 粗暴塞进 PPT 页里。

这条链路的优点是快，但天然有三个硬伤：

### 2.1 生成对象错了

当前 `/api/reports/generate` 生成的是 Markdown 字符串，而不是结构化 deck 数据。  
这意味着：

- 不能稳定编辑单页结构。
- 不能对某一页做局部重生成。
- 不能让不同渲染器复用同一份内容。

### 2.2 预览不是“真实预览”

现在的预览本质上是 Markdown viewer，不是 presentation editor。  
用户看到的不是最终 PPT 的内容结构和布局系统，而只是一个过渡文本态。

### 2.3 来源可追溯能力没有进入报告层

你现有 Agent 已经有来源元数据能力，前端聊天也能展示 citation，但报告生成链路没有把这部分能力沉淀到 slide/block 级别。

结果就是：

- 聊天答案可引用。
- 报告导出不可核查。
- 演示稿里每一页的结论无法追溯到具体文档片段。

---

## 3. 与现有项目的衔接点

这次改造不是推倒重来，当前项目里已经有几块非常适合复用：

### 3.1 可直接复用

- 会话与历史管理：`chat_store.py`
- RAG 检索与 source metadata：`agent_core.py`、`doc_pipeline.py`
- 前端 source 展示组件：`frontend/src/components/chat/CitationPanel.tsx`
- 报告入口按钮与弹窗容器：`frontend/src/components/layout/Header.tsx`、`frontend/src/components/reports/ReportPreviewModal.tsx`

### 3.2 需要被替换的核心链路

- `api_server.py` 里当前 `_build_slidev_markdown()` 和 `/api/reports/download/{session_id}` 只能作为过渡能力保留。
- 新系统里，`generate_report` 不再返回 `markdown`，而是返回 `deck_id + deck_spec + generation_state`。

---

## 4. 新的产品目标

这套新 PPT 功能建议明确围绕五个产品原则：

1. `Source-grounded`
   每一页、每个关键结论都能追溯来源。
2. `Preview-first`
   用户先看、先改、先确认，再导出。
3. `Content/Layout 分层`
   LLM 生成语义结构，不直接负责坐标和样式细节。
4. `Composable`
   同一份 `Deck Spec` 能导出为 PPTX、PDF、Web slides。
5. `Regenerable`
   可以只重写一页、一个 block、一个标题，而不是整份重来。

---

## 5. 产品交互流（UX Flow）

这里按你要求，把页面流转完整展开。

### 5.1 入口一：从“选中资料”开始

用户动作：

- 在知识库文档列表中勾选若干文档。
- 或在聊天中勾选若干回答/引用片段“加入演示稿”。
- 点击“生成汇报/PPT”。

系统动作：

- 创建一个 `Deck Draft Session`。
- 收集用户显式选中的 `source_ids / excerpt_ids / session_message_ids`。
- 进入配置面板。

### 5.2 配置面板

目标：让用户给模型的是“意图约束”，不是一句模糊 prompt。

建议配置项：

- 演示目标：汇报 / 提案 / 培训 / 复盘 / 研究总结
- 受众：老板 / 客户 / 团队 / 学术评审 / 通用
- 页数范围：5 / 8 / 12 / 20 页
- 风格：正式商务 / 学术 / 科技感 / 极简
- 语言：中文 / 英文 / 双语
- 内容策略：保守引用 / 平衡 / 强概括
- 是否允许补充联网信息
- 是否必须逐页显示引用
- 是否输出附录页

点击“生成大纲”后，不直接出 PPT，而是只生成：

- 标题
- 一句话主结论
- 目录结构
- 每页目标

### 5.3 Deck 预览与编辑

这是整个产品的核心界面，建议采用三栏布局：

- 左栏：页缩略图和章节树
- 中栏：当前 slide 可视化预览
- 右栏：属性与来源面板

中间页面支持两种编辑模式：

- `Structure mode`
  调整页顺序、增删页、切换版式、重生成单页。
- `Content mode`
  直接编辑标题、要点、备注、图表说明、引用。

右侧来源面板展示：

- 本页使用了哪些 source
- 每条结论对应哪些 excerpt
- 是否存在低置信度表述
- 一键“替换为原文措辞”
- 一键“显示引用脚注”

用户在这个阶段可以做的动作：

- 改标题
- 改 bullet
- 删掉 AI 生成的废话
- 追加自己写的备注
- 锁定某页内容，后续不再被重生成覆盖
- 只重生成当前页
- 只重生成“更适合老板汇报”的表达
- 切换主题模板

### 5.4 最终导出

导出前给一个明确确认页：

- 最终页数
- 模板主题
- 是否包含附录
- 是否显示页脚引用
- 导出格式：`PPTX / PDF / Web Share Link`

导出完成后提供：

- 下载文件
- 复制分享链接
- 另存为模板
- 回到 deck editor 继续修改

---

## 6. 页面级交互状态设计

为了避免“开盲盒”，建议把生成过程拆成三个可见阶段：

### 6.1 Planning

显示：

- “正在提炼核心观点”
- “正在按资料分组章节”
- “正在为每页绑定证据”

产物：

- 大纲草案

### 6.2 Drafting

显示：

- 每页生成进度
- 已绑定来源数
- 风险提示，例如“第 4 页缺少直接证据”

产物：

- 完整 `Deck Spec`

### 6.3 Review

显示：

- 每页内容
- 引用覆盖度
- 可导出状态

产物：

- 可编辑 deck

---

## 7. 核心中间层数据结构：Deck Spec

这是这次改造最关键的部分。  
`Deck Spec` 不应该是 PPT 坐标语言，而应该是“演示稿领域模型”。

建议分成六层：

1. `deck meta`
2. `generation meta`
3. `theme & layout`
4. `slides`
5. `blocks`
6. `citations / evidence`

### 7.1 顶层结构建议

```json
{
  "version": "1.0",
  "deck_id": "deck_01hxyz...",
  "status": "draft",
  "meta": {},
  "generation": {},
  "theme": {},
  "outline": {},
  "slides": [],
  "assets": [],
  "source_registry": [],
  "export_options": {}
}
```

### 7.2 关键字段说明

#### `meta`

描述业务语义，不描述渲染细节。

```json
{
  "title": "Q2 知识库建设复盘与下阶段计划",
  "subtitle": "基于内部文档与会议纪要自动整理",
  "language": "zh-CN",
  "audience": "management",
  "purpose": "status_review",
  "author": "system",
  "created_at": "2026-04-01T18:00:00+08:00",
  "source_scope": {
    "knowledge_base_ids": ["kb_default"],
    "session_ids": ["session_xxx"],
    "document_ids": ["doc_a", "doc_b"]
  }
}
```

#### `generation`

记录这份 deck 是怎么来的，便于审计、回放和局部重生成。

```json
{
  "model": "qwen / gpt / local",
  "prompt_profile": "ppt_briefing_v1",
  "temperature": 0.2,
  "constraints": {
    "target_slide_count": 8,
    "tone": "formal",
    "citation_mode": "inline_footnote",
    "allow_external_web": false
  },
  "warnings": [
    {
      "code": "weak_evidence",
      "message": "第 5 页结论证据较弱"
    }
  ]
}
```

#### `theme`

只放抽象主题，不放具体导出坐标。

```json
{
  "theme_id": "executive_blue",
  "density": "medium",
  "aspect_ratio": "16:9",
  "tokens": {
    "font_heading": "Source Han Sans",
    "font_body": "Source Han Sans",
    "color_primary": "#0F3D66",
    "color_accent": "#1F7AE0",
    "color_bg": "#F7F9FC"
  },
  "default_layouts": {
    "title": "hero-title",
    "section": "chapter-break",
    "content": "title-bullets",
    "data": "title-chart",
    "compare": "two-column-compare"
  }
}
```

#### `outline`

保留 deck 级逻辑。

```json
{
  "narrative": "problem-analysis-plan",
  "sections": [
    {
      "id": "sec_1",
      "title": "现状与问题",
      "slide_ids": ["s1", "s2"]
    },
    {
      "id": "sec_2",
      "title": "改造方案",
      "slide_ids": ["s3", "s4", "s5"]
    }
  ]
}
```

#### `slides`

每一页是独立、可编辑、可重生成的单元。

```json
{
  "id": "s3",
  "type": "content",
  "title": "为什么现有 AI PPT 工具难以进入生产场景",
  "subtitle": "问题不在生成速度，而在可控性和可追溯性",
  "layout": "title-bullets",
  "intent": "explain_problem",
  "speaker_notes": "先讲行业共性问题，再引出我们的设计原则。",
  "blocks": [],
  "citations": [],
  "status": {
    "locked": false,
    "dirty": false,
    "review_state": "approved"
  }
}
```

#### `blocks`

block 是前端编辑和后端重生成的最小内容单位。

建议支持：

- `heading`
- `paragraph`
- `bullet_list`
- `quote`
- `table`
- `chart`
- `metric_grid`
- `timeline`
- `two_column`
- `image`
- `callout`
- `appendix_refs`

示例：

```json
{
  "id": "b_001",
  "kind": "bullet_list",
  "role": "main_points",
  "content": {
    "items": [
      {
        "text": "现有工具通常把“内容组织”和“页面排版”混为一次 LLM 输出。",
        "citations": ["c1", "c2"]
      },
      {
        "text": "用户拿到的是最终文件，而不是可审阅的中间结构。",
        "citations": ["c3"]
      }
    ]
  },
  "editable": true,
  "regen_key": "problem_statement"
}
```

#### `citations`

citation 不应该只挂在整页，而应该能挂到 block 或 item 级。

```json
{
  "id": "c1",
  "source_id": "src_doc_21",
  "excerpt_id": "ext_903",
  "claim_text": "现有工具把内容组织和排版混为一次输出。",
  "evidence_type": "excerpt",
  "confidence": 0.92,
  "locator": {
    "page": 5,
    "section": "方案比较"
  },
  "snippet": "......",
  "url": null
}
```

#### `source_registry`

把 source registry 单独维护，避免每个 citation 冗余全文。

```json
{
  "id": "src_doc_21",
  "type": "doc",
  "title": "NotebookLM 竞品调研.md",
  "document_id": "doc_21",
  "uri": "kb://default/doc_21",
  "metadata": {
    "source": "NotebookLM 竞品调研.md",
    "uploaded_at": "2026-03-30T12:00:00+08:00"
  }
}
```

### 7.3 Deck Spec 设计原则

这份结构需要满足五个要求：

1. 对 LLM 足够友好
   模型能稳定生成和修补。
2. 对前端足够友好
   可以直接映射为编辑器状态。
3. 对渲染器足够友好
   能被不同导出引擎消费。
4. 对审计足够友好
   可以记录来源、置信度、生成参数。
5. 对增量更新足够友好
   可以局部重生成，避免整份覆盖。

---

## 8. 推荐的生成流水线

### 8.1 Step A：Source Pack 构建

把用户选中的文档、对话、检索结果统一整理成一个 `Source Pack`：

```json
{
  "source_pack_id": "sp_xxx",
  "documents": [],
  "excerpts": [],
  "chat_highlights": [],
  "constraints": {}
}
```

这一步做三件事：

- 去重
- 切片
- 排序

输出的是“供生成使用的证据集合”，不是原始全文。

### 8.2 Step B：Outline Planner

LLM 只生成大纲，不直接写全稿。

输出：

- deck 标题
- 章节结构
- 每页 intent
- 每页要回答的问题
- 每页建议引用哪些 source

### 8.3 Step C：Slide Drafter

再按页生成 block 内容。

约束：

- 每个 block 必须引用 source id
- 没证据就标记 `needs_review`
- 不允许跨页自由发散

### 8.4 Step D：Validator

不交给用户之前，先做程序校验：

- slide 数是否超限
- 是否有空页
- 是否有无引用结论
- block 长度是否超出布局容量
- 是否存在重复页

### 8.5 Step E：Human-in-the-loop 编辑

只有通过预览编辑阶段，才允许导出。

---

## 9. 前端编辑器建议

### 9.1 编辑器能力边界

第一版不要做成 Figma，也不要做成 PowerPoint 全功能替代。

第一版建议只支持：

- 页排序
- 页增删
- 标题编辑
- bullet 编辑
- layout 切换
- 引用查看
- 单页重生成
- 模板切换

不要一上来支持：

- 任意拖拽坐标
- 任意图层系统
- 任意画布缩放

因为这会把产品从“AI 演示稿生成器”变成“通用 PPT 编辑器”，复杂度暴涨。

### 9.2 推荐的前端状态拆分

- `deckStore`
  保存完整 `Deck Spec`
- `deckUiStore`
  保存当前选中 slide、缩放、侧栏状态
- `deckOps`
  保存异步动作：重生成、导出、校验

### 9.3 预览渲染方式

建议不要继续用 Markdown 作为预览载体，而是：

- 以 `SlideSpec -> React components` 方式渲染
- 每种 `layout` 对应一个 React 模板
- 每种 `block kind` 对应一个 block renderer

例如：

- `layouts/HeroTitleSlide.tsx`
- `layouts/TitleBulletsSlide.tsx`
- `layouts/TwoColumnCompareSlide.tsx`
- `blocks/BulletListBlock.tsx`
- `blocks/MetricGridBlock.tsx`
- `blocks/CitationFootnotes.tsx`

---

## 10. 技术选型建议

你特别问到了渲染方案，这里直接给结论和取舍。

### 10.1 不建议继续把 `python-pptx` 作为主渲染引擎

原因：

- 更适合程序化填表、简单文本框，不适合现代模板化演示稿。
- 与你当前 React 前端的样式体系割裂。
- 很难做到“前端预览长什么样，导出就基本长什么样”。
- 对复杂主题、图表、富块组合的开发体验较差。

`python-pptx` 可以保留为：

- 兜底导出器
- 简报纯文本模式
- 后台批量任务的低保真通道

但不应该再是核心方案。

### 10.2 推荐主路线：`Deck Spec + React Preview + Node/PptxGenJS Export`

这是最适合你当前技术栈的主方案。

#### 组件拆分

- Python/FastAPI：
  继续负责知识库、RAG、LLM orchestration、Deck Spec 生成
- React/Vite：
  负责 deck 编辑与预览
- Node 渲染服务：
  负责将 `Deck Spec` 转为 `pptx/pdf`

#### 为什么推荐它

- 你现在前端已经是 React/TypeScript，迁移成本低。
- `PptxGenJS` 在 JS/TS 生态里对 PPT 生成能力明显强于 `python-pptx` 的当前使用方式。
- 它天然适合用“模板 + block renderer”来消费 `Deck Spec`。
- 可以定义 slide master、图表、表格、图片、文本等对象，足够支撑生产级汇报模板。

#### 适合的导出模型

- `Deck Spec -> PptxGenJS` 导出可编辑 PPTX
- `Deck Spec -> React HTML -> Playwright` 导出 PDF/图片

这是一条“内容统一、导出分流”的健康架构。

### 10.3 推荐辅路线：`React HTML/CSS + Playwright`

这条路非常适合做：

- 高保真 PDF
- 分享链接
- 封面图、缩略图
- 品牌样式复杂的展示稿

优点：

- 与前端预览一致性最高
- CSS 表达力强
- 适合做截图、海报、PDF

缺点：

- 直接导出“可编辑 PPTX”并不自然
- 更像是 web slide / print slide 方案

所以它很适合当：

- 预览基线
- PDF 输出器
- 缩略图生成器

### 10.4 不建议作为主路线：Slidev / Marp

它们可以保留为“分享模式”或“开发者模式”，但不建议做产品主干。

原因很直接：

- 它们的核心输入仍然偏 Markdown authoring，不是结构化 deck domain model。
- 官方导出的 PPTX 主要是图像化结果，可编辑性弱。
- Marp 的 editable PPTX 仍是实验能力，且依赖额外环境，官方也明确提示保真度更低。

因此：

- 作为辅助导出或演示模式可以
- 作为企业级可编辑 PPT 主链路不合适

### 10.5 最终推荐的技术组合

建议你采用：

- `内容层`：Python + FastAPI + LLM + RAG
- `中间层`：Deck Spec JSON
- `预览层`：React + layout/block renderer
- `PPTX 导出层`：Node + PptxGenJS
- `PDF/图片导出层`：Playwright

这是兼顾：

- 落地速度
- 可维护性
- 前后端一致性
- 多格式扩展性

---

## 11. 推荐的服务边界

### 11.1 Python 后端新增职责

建议新增 `deck_service.py`，负责：

- `build_source_pack()`
- `plan_deck_outline()`
- `draft_deck_spec()`
- `validate_deck_spec()`
- `regenerate_slide()`

新增 API：

- `POST /api/decks`
  创建 deck draft
- `POST /api/decks/{deck_id}/plan`
  生成大纲
- `POST /api/decks/{deck_id}/draft`
  生成完整 deck spec
- `GET /api/decks/{deck_id}`
  获取当前 deck
- `PATCH /api/decks/{deck_id}`
  更新 deck metadata
- `PATCH /api/decks/{deck_id}/slides/{slide_id}`
  编辑某页
- `POST /api/decks/{deck_id}/slides/{slide_id}/regenerate`
  重生成单页
- `POST /api/decks/{deck_id}/export`
  请求导出

### 11.2 Node 渲染服务职责

建议独立一个轻量服务，例如：

- `deck-renderer/package.json`
- `deck-renderer/src/renderPptx.ts`
- `deck-renderer/src/renderPdf.ts`
- `deck-renderer/src/themeRegistry.ts`

职责只做两件事：

- 接收 `Deck Spec`
- 输出 `pptx/pdf/png`

不要让 Node 服务承担 LLM 或知识库逻辑。

---

## 12. 来源可追溯设计（Source-grounded）

这是整个方案的护城河。

### 12.1 引用颗粒度

建议至少做到三层：

- deck 级：本稿使用了哪些资料
- slide 级：本页依赖哪些来源
- block/item 级：这句结论来自哪些证据

### 12.2 引用展示方式

建议支持三种模式：

1. `none`
   预览时隐藏，只在来源面板可见
2. `inline_footnote`
   页脚显示 `[1][2]`
3. `speaker_notes_only`
   只进备注区，不显示在主内容区

### 12.3 证据不足的处理

如果某个 block 没有强证据，不要强行补。

建议状态：

- `supported`
- `weak_support`
- `inferred`
- `manual`

UI 上明确标记：

- 绿色：直接证据
- 黄色：弱支持
- 灰色：人工补充

---

## 13. 内容生成与排版生成分层

这是技术上最重要的解耦点。

### 13.1 LLM 负责什么

- 识别主题
- 规划叙事顺序
- 提炼观点
- 组织成 slide/block 语义结构
- 为 block 绑定引用

### 13.2 渲染器负责什么

- 选择版式模板
- 控制块间距
- 控制文字截断
- 控制图表配色
- 决定页脚、页码、角标位置

### 13.3 为什么一定要分层

如果让 LLM 同时负责“写内容 + 算布局”，会出现三个问题：

- 输出不稳定
- 很难局部编辑
- 换主题基本等于重做

一旦分层：

- 内容可复用
- 模板可复用
- 导出器可替换

---

## 14. 推荐的 layout 系统

第一版建议只定义 8 到 12 个高频 layout：

- `hero-title`
- `section-break`
- `title-bullets`
- `title-paragraph`
- `title-two-column`
- `title-metrics`
- `title-chart`
- `title-table`
- `title-image-right`
- `appendix-sources`

每个 layout 都定义：

- 容量规则
- 支持哪些 block kind
- 最多容纳多少字
- 超长时如何降级

例如 `title-bullets`：

- 1 个标题
- 1 个副标题可选
- 1 个 bullet_list
- bullet 建议 3 到 5 条
- 每条不超过 36 中文字

这样你就能在导出前做自动校验，而不是让内容溢出后才发现。

---

## 15. 图表与数据块策略

如果 deck 里有数据页，建议不要让模型直接“画图”，而是输出 `chart spec`。

例如：

```json
{
  "kind": "chart",
  "chart_type": "bar",
  "title": "各阶段文档处理耗时对比",
  "data": {
    "categories": ["切分", "向量化", "重排", "生成"],
    "series": [
      {
        "name": "当前方案",
        "values": [10, 35, 12, 18]
      },
      {
        "name": "改造后",
        "values": [8, 35, 12, 9]
      }
    ]
  },
  "citations": ["c11"]
}
```

然后由导出器决定：

- 在预览中用 ECharts 渲染
- 在 PPTX 中用原生 chart 对象生成

---

## 16. 导出能力矩阵

建议从第一天起就定义清楚不同导出器的能力边界。

### 16.1 PPTX

目标：

- 可编辑文本
- 基本图表可编辑
- 主题一致
- 页脚和引用保留

适合：

- 企业汇报
- 继续在 PowerPoint 内二次加工

### 16.2 PDF

目标：

- 视觉保真最高
- 适合归档和分享

适合：

- 提交版本
- 发给外部客户

### 16.3 Web Deck

目标：

- 在线查看
- 支持 hover 看来源
- 支持分享链接

适合：

- 内部协同
- 快速审阅

---

## 17. 建议的迭代路线

### Phase 1：把“报告”升级成 `Deck Spec`

目标：

- 保留当前“生成报告”入口
- 后端返回 `deck_spec` 而不是 markdown
- 前端实现基础 slide 预览

这一步先不追求漂亮，只追求结构正确。

### Phase 2：加入来源面板和单页编辑

目标：

- 页级引用展示
- 标题、bullet 编辑
- 单页重生成
- layout 切换

这一阶段产品价值会第一次明显拉开。

### Phase 3：接入 Node/PptxGenJS 导出器

目标：

- 替换现有 `python-pptx` 主链路
- 提供正式版 PPTX 导出
- 增加主题模板

### Phase 4：高保真 PDF / 分享链接

目标：

- React + Playwright 导出 PDF
- deck 在线分享
- 缩略图与封面图生成

### Phase 5：高级智能能力

目标：

- 自动识别“这一页太拥挤”
- 自动建议拆页
- 自动生成附录
- 自动区分“主结论页”和“证据页”

---

## 18. 对现有代码的最小迁移方案

为了降低风险，建议分三刀切：

### 18.0 必须替代的旧功能入口

当前 [ReportPreviewModal.tsx](F:/项目/AI智能体/frontend/src/components/reports/ReportPreviewModal.tsx) 里有两个旧入口：

- `下载 PPTX`
- `Slidev 编辑`

这两个入口在新方案里都不应继续作为主功能保留，而要被新的 deck 工作流替代：

- `下载 PPTX` -> 替换为统一的 `导出` 动作
  由 `Deck Spec` 驱动，支持 `PPTX / PDF / Web Share Link`
- `Slidev 编辑` -> 替换为 `进入 Deck 编辑器`
  用户应在系统内完成预览、修改、单页重生成和来源核查，而不是跳转到外部 Slidev

也就是说，未来用户不再面对“复制 Markdown 去外部改”这条链路，而是在产品内部完成：

- 预览
- 编辑
- 校对来源
- 导出

### 第一刀：保留旧按钮，替换返回值

现在点击“生成报告”后返回：

```json
{
  "markdown": "...",
  "title": "..."
}
```

第一步改成：

```json
{
  "deck_id": "deck_xxx",
  "deck_spec": { "...": "..." },
  "title": "..."
}
```

### 第二刀：把 `ReportPreviewModal` 替换成 `DeckEditorModal`

先复用弹窗入口，不急着重做整页路由。
同时移除当前依赖 Markdown/Slidev 的操作按钮，改为：

- `编辑 Deck`
- `导出`
- `查看来源`

### 第三刀：旧导出保留为 fallback

如果新渲染器失败：

- 仍允许走旧 `python-pptx` 导出
- 但在 UI 标记为“兼容模式”

这样改造不会中断现有功能。

---

## 19. 我对你这个项目的最终建议

如果目标真的是做出“生产力级别”的 AI PPT，而不是演示性质功能，那么最关键的不是“换一个更强的导出库”，而是把产品主语从“文件生成”改成“可审阅的 deck 生成”。

所以我给出的最终判断是：

- 产品上：
  一定要走 `preview-first`
- 架构上：
  一定要引入 `Deck Spec`
- 技术上：
  一定要把 `内容生成` 和 `排版导出` 解耦
- 渲染上：
  主推 `React Preview + PptxGenJS Export + Playwright PDF`
- 定位上：
  把 Slidev/Marp 视为辅助能力，而不是主链路

---

## 20. 参考资料

以下是我在技术选型上参考的官方资料：

- PptxGenJS 官方介绍：https://gitbrent.github.io/PptxGenJS/docs/introduction/
- PptxGenJS Slide Masters：https://gitbrent.github.io/PptxGenJS/docs/masters/
- PptxGenJS Charts：https://gitbrent.github.io/PptxGenJS/docs/api-charts.html
- PptxGenJS HTML to PowerPoint：https://gitbrent.github.io/PptxGenJS/docs/html-to-powerpoint/
- Slidev 导出文档：https://sli.dev/guide/exporting.html
- Marp CLI 官方仓库文档：https://github.com/marp-team/marp-cli
- Playwright 截图文档：https://playwright.dev/docs/next/screenshots
- Playwright `page.pdf()` 文档：https://playwright.dev/docs/api/class-page

---

## 21. 对下一步实现的建议

如果继续往下做，我建议下一步不是直接写导出器，而是先做这三件事：

1. 定义 `Deck Spec` 的 Pydantic 模型和 TS 类型。
2. 把当前报告接口改成 `deck draft` 接口。
3. 在前端做一个最小版 `DeckEditorModal`，先支持：
   - 缩略图列表
   - 当前页预览
   - 标题/要点编辑
   - 来源侧栏

只要这三步跑通，这条产品路线就已经从“玩具 PPT 生成”跨进“可演进的 AI deck system”了。
