# 资源级访问控制基础

本项目当前已经具备账号、组织、成员关系、资源授权、资源级鉴权和前端管理入口。资源权限已覆盖会话、工作区、报告、卡片、产物、任务和关键写入操作；现阶段重点从“后端能力”推进到“企业权限管理闭环”。

## 数据模型

- `organizations`：组织目录。
- `users`：用户目录。
- `memberships`：用户在组织内的角色。
- `resource_grants`：资源对用户或组织的显式授权。

`resource_grants` 使用 `(resource_type, resource_id, subject_type, subject_id)` 作为唯一键，避免 SQLite 对 `NULL` 组合唯一约束不可靠的问题。

## 角色规则

角色等级沿用身份体系：

1. `viewer`
2. `editor`
3. `admin`
4. `owner`

系统会通过 `GET /api/access/role-matrix` 暴露当前制度化权限矩阵，前端和运维文档可复用同一份后端定义，避免 UI 文案与实际路由约束漂移。

用户访问资源时会综合两类授权：

- 用户直授：`user_id` 直接命中资源授权。
- 组织授权：用户属于某个组织，且该组织拥有资源授权。

组织授权的有效角色会被组织成员角色上限裁剪。例如：组织对资源是 `admin`，成员在组织内是 `editor`，则该用户对资源的有效角色为 `editor`。

## 已接入的业务资源

当前资源级鉴权已经接入以下 API：

- `workspace`：列表过滤、创建自动 owner 授权、更新/激活/删除校验。
- `session`：列表过滤、创建自动 owner 授权、更新/删除校验；聊天写入、消息导入/反馈/截断/清空、检索反馈、书签、记忆、附件、答案组操作、分享创建和关联任务都会校验会话资源权限。
- `deck`：创建前校验来源会话，创建后自动 owner 授权，读取/更新/导出/重生成校验。
- `artifact`：报告和卡片产物创建后自动 owner 授权，读取/更新/导出校验。
- `report`：生成和下载前校验来源会话访问权。
- `task`：创建、详情和列表会按关联 `session_id` 做可见性校验；无会话任务仍使用远程角色校验。

为了兼容历史数据，校验策略是“有显式授权记录才强制资源级校验”。老数据没有 grant 时仍按原来的远程角色/本地模式行为放行；新创建的会话、工作区、卡片和产物会自动写入 owner grant，因此天然进入隔离模式。

## 授权继承

派生资源创建时会从来源会话复制显式授权，避免只给创建者授权导致团队协作断裂：

- `session -> task`：关联会话任务创建后继承会话的用户/组织 grant，并额外给创建者 `owner`。
- `session -> deck`：卡片生成后继承来源会话 grant，并额外给创建者 `owner`。
- `session -> artifact`：报告/卡片产物生成后继承来源会话 grant，并额外给创建者 `owner`。

继承只复制显式 grant，不会复制“无 ACL 的历史兼容放行”状态。因此老资源仍保持兼容，新派生资源会在来源会话进入 ACL 模式后自动进入同一隔离边界。

## 审计事件

资源权限相关动作会写入现有安全审计流水，方便后续排查访问与授权链路：

- `resource_access_denied`：资源级权限不足时记录，`result` 为 `rejected`。
- `resource_owner_granted`：新资源自动给创建者写入 `owner` grant 时记录。
- `resource_grants_inherited`：派生资源从来源会话复制 grant 时记录复制数量与资源映射。

这些事件复用 `/api/security/audit-events` 查询能力，不新增独立审计存储。

可通过 `GET /api/security/audit-actions?category=access` 获取权限相关审计动作目录，当前覆盖授权变更、访问拒绝、owner 自动授权和派生资源授权继承。

权限审计闭环可通过安全审计汇总接口完成：

```http
GET /api/security/audit-summary?category=access
```

该接口按 `action` / `result` 聚合权限相关审计事件，并返回所选分类的最近事件数量，适合设置页或运维面板快速呈现授权变更、访问拒绝和继承授权的总体趋势。响应只包含聚合计数和非敏感摘要，不暴露 secret、token 或其它原始凭据。

## API

### 列出资源授权

```http
GET /api/access/resource-grants?resource_type=session&resource_id=session-1&role=editor&subject_type=user&limit=100&offset=0
```

需要 `viewer` 或更高角色。

### 查询当前用户对资源的访问结果

```http
GET /api/access/resources/{resource_type}/{resource_id}/me?minimum_role=viewer
```

需要 `viewer` 或更高角色。本地模式保持兼容，返回 `local_bypass` 且拥有 `admin` 访问。

### 查询角色权限矩阵

```http
GET /api/access/role-matrix
```

需要 `viewer` 或更高角色。响应包含角色顺序、角色等级、各操作的最低角色，以及组织授权会被成员角色上限裁剪的继承规则。

### 创建或更新资源授权

```http
POST /api/access/resource-grants
Content-Type: application/json

{
  "resource_type": "session",
  "resource_id": "session-1",
  "user_id": "user-1",
  "role": "editor"
}
```

或授权给组织：

```json
{
  "resource_type": "workspace",
  "resource_id": "workspace-1",
  "org_id": "org-acme",
  "role": "admin"
}
```

需要 `admin` 或更高角色。`org_id` 与 `user_id` 必须且只能传一个。

### 删除资源授权

```http
DELETE /api/access/resource-grants
Content-Type: application/json

{
  "resource_type": "session",
  "resource_id": "session-1",
  "user_id": "user-1"
}
```

需要 `admin` 或更高角色。

### 列出可授权资源

资源授权面板会读取可见资源目录，避免管理员手动复制资源 ID。列表接口会按资源 ACL 做可见性过滤：

```http
GET /api/decks?limit=100
GET /api/artifacts?artifact_type=deck&limit=100
GET /api/sessions
GET /api/workspaces
```

当前前端资源选择器覆盖：

- `workspace`
- `session`
- `deck`
- `artifact`

### 身份与组织管理

```http
GET /api/identity?limit=200
POST /api/identity/orgs
POST /api/identity/users
POST /api/identity/memberships
```

设置页的“身份与组织管理”面板可维护组织、用户和组织成员角色；“资源访问控制”面板会复用该身份目录，支持直接选择用户或组织作为授权主体。

## 后续接入建议

1. 在前端增加权限变更审计筛选视图，消费 `GET /api/security/audit-summary?category=access` 并支持下钻到 `resource_access_denied`、`resource_owner_granted`、`resource_grants_inherited` 和授权变更事件。
2. 在资源详情页增加“当前资源授权”快捷入口，减少管理员必须进入设置页的路径成本。
3. 补充 E2E 测试，覆盖身份创建、组织成员设置、资源授权、owner 保护和受限用户访问。
4. 后续如接入外部 SSO，需要把外部身份映射到 `users` / `memberships`，再复用现有资源授权模型。
