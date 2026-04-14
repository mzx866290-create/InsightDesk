# 会话工作台实现规格

目标：把当前“会话列表”升级为“会话工作台第一版”，支撑高频用户长期管理项目型会话。

---

## 1. 目标范围

本期只做第一版，明确包含：

- 会话搜索
- 会话改名
- 会话收藏
- 会话归档
- 标签管理
- 列表筛选

本期不做：

- 项目树
- 多级文件夹
- 跨用户共享
- 批量操作
- 复杂权限模型

---

## 2. 当前实现状态

当前已有能力：

- `GET /api/sessions`
- `POST /api/sessions`
- `DELETE /api/sessions/{session_id}`
- 前端侧边栏可打开 / 删除会话

当前限制：

- `sessions` 表仅有 `session_id / created_at / updated_at / title`
- API 不支持 patch
- 列表不支持 query / favorite / archived / tag 过滤
- `Session` 前端类型缺少管理属性
- 侧边栏只适合少量会话

关键现状文件：

- `chat_store.py`
- `api_server.py`
- `frontend/src/api/client.ts`
- `frontend/src/stores/chatStore.ts`
- `frontend/src/components/layout/Sidebar.tsx`

---

## 3. 数据结构改造

### 3.1 `sessions` 表新增字段

建议新增：

- `is_archived INTEGER DEFAULT 0`
- `is_favorite INTEGER DEFAULT 0`
- `tags_json TEXT DEFAULT '[]'`

可选新增：

- `project_name TEXT DEFAULT ''`

第一版建议先不加 `project_name`，避免 UI 设计过早扩散。

### 3.2 迁移策略

在 `chat_store.py` 的 `_init_sessions_table` 中补迁移：

- 检查 `is_archived` 是否存在
- 检查 `is_favorite` 是否存在
- 检查 `tags_json` 是否存在

### 3.3 数据约束

- `is_archived` 只允许 `0 / 1`
- `is_favorite` 只允许 `0 / 1`
- `tags_json` 必须是 JSON array
- 标签值去重、trim、限制最大数量

建议约束：

- 每个会话最多 8 个 tag
- 每个 tag 最长 20 个字符

---

## 4. API 设计

### 4.1 `GET /api/sessions`

新增 query params：

- `query: str = ''`
- `archived: Optional[bool] = None`
- `favorite: Optional[bool] = None`
- `tag: str = ''`

返回结构：

```json
{
  "sessions": [
    {
      "session_id": "xxx",
      "title": "采购流程答疑",
      "created_at": 1710000000,
      "updated_at": 1710000100,
      "message_count": 18,
      "is_archived": false,
      "is_favorite": true,
      "tags": ["采购", "流程"]
    }
  ]
}
```

实现建议：

- SQL 仍基于 SQLite
- `query` 先用 `LOWER(title) LIKE ?`
- `tag` 先在 Python 层过滤，第一版足够

### 4.2 `PATCH /api/sessions/{session_id}`

请求体：

```json
{
  "title": "新的标题",
  "is_archived": false,
  "is_favorite": true,
  "tags": ["知识库", "周报"]
}
```

规则：

- 全字段可选
- 至少一个字段存在
- `title` 为空串时不允许清空为纯空白
- `tags` 做 trim + 去重

返回结构：

```json
{
  "ok": true,
  "session": {
    "session_id": "xxx",
    "title": "新的标题",
    "created_at": 1710000000,
    "updated_at": 1710000200,
    "message_count": 18,
    "is_archived": false,
    "is_favorite": true,
    "tags": ["知识库", "周报"]
  }
}
```

错误返回：

- session 不存在：404
- 参数非法：400

---

## 5. 后端实现拆分

### 5.1 `chat_store.py`

新增或改造函数：

- `update_session_meta(session_id, patch)`
- `get_all_sessions(...filters)`
- `_normalize_tags(tags)`
- `_row_to_session(row)`

建议实现顺序：

1. 扩 sessions 表迁移
2. 扩 `get_all_sessions`
3. 增 `update_session_meta`
4. 补 JSON tags 解析与序列化

### 5.2 `api_server.py`

新增内容：

- `UpdateSessionRequest`
- `PATCH /api/sessions/{session_id}`
- 扩展 `GET /api/sessions`

建议保持兼容：

- 老前端不带 query params 时，行为不变
- 新字段缺失时，默认值返回完整

### 5.3 测试建议

新增测试：

- `tests/test_sessions_list_filters.py`
- `tests/test_session_patch_api.py`

覆盖点：

- title 更新
- favorite 更新
- archived 更新
- tags 更新
- query 过滤
- archived 过滤
- favorite 过滤
- tag 过滤

---

## 6. 前端实现拆分

### 6.1 `frontend/src/api/client.ts`

新增或修改：

- 扩展 `Session` 类型
- `getSessions(params?)`
- `updateSessionMeta(sessionId, patch)`

`Session` 新字段：

- `is_archived?: boolean`
- `is_favorite?: boolean`
- `tags?: string[]`

### 6.2 `frontend/src/stores/chatStore.ts`

修改点：

- `updateSession` patch 类型扩大
- 本地排序仍以 `updated_at` 为主
- 会话元数据更新后可直接反映到列表

建议新增：

- `replaceSession(session)`

这样 PATCH 成功后可以直接覆盖服务端最新结果。

### 6.3 `frontend/src/components/layout/Sidebar.tsx`

需要新增的 UI：

- 搜索输入框
- 过滤标签：
  - 全部
  - 收藏
  - 归档
- 行级动作：
  - 改名
  - 收藏 / 取消收藏
  - 归档 / 取消归档
  - 删除
- tag badge 展示

建议交互：

- hover 显示次级操作
- 移动端只保留最核心动作
- 改名采用 inline edit，不开 modal

### 6.4 UI 状态建议

新增本地状态：

- `search`
- `viewMode: all | favorite | archived`
- `editingSessionId`
- `editingTitle`
- `busySessionId`

---

## 7. 交互细节建议

### 7.1 搜索

第一版直接前端驱动服务端请求即可，不需要防抖很复杂：

- 300ms debounce
- 搜索空串时回到默认列表

### 7.2 改名

规则：

- Enter 保存
- Esc 取消
- blur 自动保存

### 7.3 收藏

规则：

- 收藏会话仍保留在默认列表中
- 收藏视图只显示 `is_favorite = true`

### 7.4 归档

规则：

- 归档后默认列表不再展示
- 归档视图可恢复会话
- 当前活跃会话被归档时，不强制关闭，仅从默认列表移除

### 7.5 标签

第一版建议做轻量：

- 改名区域下方显示 tags
- 在 session action 里提供简单 tag 编辑入口
- 暂不做 tag 体系管理页

---

## 8. 验收标准

必须满足：

1. 会话列表支持搜索
2. 会话支持改名
3. 会话支持收藏
4. 会话支持归档与恢复
5. 会话支持标签展示与保存
6. 刷新页面后状态不丢失
7. 100+ 会话下交互仍流畅

推荐补充：

1. 收藏视图和归档视图切换顺畅
2. 活跃会话状态与侧边栏筛选不冲突

---

## 9. 风险点

### 9.1 SQLite tags 过滤不适合做复杂查询

第一版接受：

- title 搜索走 SQL
- tag 过滤走 Python 层

后续如果 tag 使用量变高，再做规范化表。

### 9.2 侧边栏交互容易变复杂

控制方式：

- 第一版不做批量操作
- 第一版不做 project tree
- 第一版不做多层文件夹

### 9.3 当前 store 与服务端状态可能短暂不一致

解决方式：

- PATCH 返回完整 session 对象
- 前端使用返回值覆盖本地对象

---

## 10. 推荐开发顺序

最推荐的执行顺序：

1. `chat_store.py` 扩表与读写函数
2. `api_server.py` 扩会话查询与 PATCH
3. `frontend/src/api/client.ts` 扩类型与请求
4. `frontend/src/stores/chatStore.ts` 扩 session patch
5. `frontend/src/components/layout/Sidebar.tsx` 做搜索 + 收藏 + 归档
6. 再补 inline rename
7. 最后补 tags

这个顺序的好处是：

- 每一步都能单独验证
- 后端先稳定，前端不会反复返工
- tags 放最后，避免影响前面主链路

