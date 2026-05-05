import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Database, RefreshCw, ShieldCheck, Trash2, Users } from 'lucide-react'

import {
  deleteResourceGrant,
  getArtifacts,
  getDecks,
  getIdentityCatalog,
  getResourceGrants,
  getSessions,
  getWorkspaces,
  upsertResourceGrant,
} from '../../api/client'
import type {
  ArtifactRecord,
  DeckSpec,
  IdentityOrganization,
  IdentityUser,
  ResourceGrant,
  ResourceGrantListQuery,
  ResourceGrantRole,
  ResourceGrantSubjectType,
  Session,
  Workspace,
} from '../../api/client'
import { IDENTITY_CATALOG_UPDATED_EVENT } from './adminEvents'
import { Button } from '../ui/Button'

type SubjectChoice = ResourceGrantSubjectType
type ManagedResourceType = 'workspace' | 'session' | 'deck' | 'artifact'

interface ResourceOption {
  type: ManagedResourceType
  id: string
  label: string
  meta?: string
}

interface SubjectOption {
  type: SubjectChoice
  id: string
  label: string
  meta?: string
}

interface GrantFormState {
  resourceType: string
  resourceId: string
  subjectType: SubjectChoice
  subjectId: string
  role: ResourceGrantRole
}

const ROLE_OPTIONS: ResourceGrantRole[] = ['viewer', 'editor', 'admin', 'owner']
const SUBJECT_OPTIONS: SubjectChoice[] = ['user', 'org']
const PAGE_SIZE = 20

const initialForm: GrantFormState = {
  resourceType: '',
  resourceId: '',
  subjectType: 'user',
  subjectId: '',
  role: 'viewer',
}

function getSubjectLabel(grant: ResourceGrant): string {
  if (grant.user_id?.trim()) return `user:${grant.user_id}`
  if (grant.org_id?.trim()) return `org:${grant.org_id}`
  return '-'
}

function normalizeApiError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error)
  if (message.includes('last owner') && message.includes('downgrade')) {
    return '不能降级该资源最后一个 owner 授权。请先添加另一个 owner。'
  }
  if (message.includes('last owner') && message.includes('delete')) {
    return '不能删除该资源最后一个 owner 授权。请先添加另一个 owner。'
  }
  return message || '操作失败'
}

function buildMutationPayload(form: GrantFormState) {
  return {
    resource_type: form.resourceType.trim(),
    resource_id: form.resourceId.trim(),
    role: form.role,
    ...(form.subjectType === 'user'
      ? { user_id: form.subjectId.trim() }
      : { org_id: form.subjectId.trim() }),
  }
}

function workspaceToOption(workspace: Workspace): ResourceOption {
  return {
    type: 'workspace',
    id: workspace.workspace_id,
    label: workspace.name || workspace.workspace_id,
    meta: workspace.is_active ? '当前工作区' : `${workspace.session_count} 个会话`,
  }
}

function sessionToOption(session: Session): ResourceOption {
  return {
    type: 'session',
    id: session.session_id,
    label: session.title || session.session_id,
    meta: session.workspace_id,
  }
}

function deckToOption(deck: DeckSpec): ResourceOption {
  return {
    type: 'deck',
    id: deck.deck_id,
    label: deck.meta?.title || deck.deck_id,
    meta: deck.meta?.session_id,
  }
}

function artifactToOption(artifact: ArtifactRecord): ResourceOption {
  return {
    type: 'artifact',
    id: artifact.artifact_id,
    label: artifact.title || artifact.artifact_id,
    meta: `${artifact.artifact_type} · ${artifact.session_id}`,
  }
}

function userToSubjectOption(user: IdentityUser): SubjectOption {
  return {
    type: 'user',
    id: user.user_id,
    label: user.display_name || user.user_id,
    meta: user.email,
  }
}

function orgToSubjectOption(org: IdentityOrganization): SubjectOption {
  return {
    type: 'org',
    id: org.org_id,
    label: org.name || org.org_id,
    meta: org.description,
  }
}

function optionValue(option: ResourceOption): string {
  return `${option.type}:${option.id}`
}

function subjectValue(option: SubjectOption): string {
  return `${option.type}:${option.id}`
}

export const ResourceAccessPanel: React.FC = () => {
  const [filters, setFilters] = useState<ResourceGrantListQuery>({ limit: PAGE_SIZE, offset: 0 })
  const [form, setForm] = useState<GrantFormState>(initialForm)
  const [grants, setGrants] = useState<ResourceGrant[]>([])
  const [resourceOptions, setResourceOptions] = useState<ResourceOption[]>([])
  const [subjectOptions, setSubjectOptions] = useState<SubjectOption[]>([])
  const [resourcePick, setResourcePick] = useState('')
  const [filterResourcePick, setFilterResourcePick] = useState('')
  const [subjectPick, setSubjectPick] = useState('')
  const [filterSubjectPick, setFilterSubjectPick] = useState('')
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadingResources, setLoadingResources] = useState(false)
  const [loadingSubjects, setLoadingSubjects] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const offset = typeof filters.offset === 'number' ? filters.offset : 0
  const canPrev = offset > 0
  const canNext = offset + grants.length < total

  const filteredSubjectOptions = useMemo(
    () => subjectOptions.filter((option) => option.type === form.subjectType),
    [form.subjectType, subjectOptions],
  )

  const query = useMemo<ResourceGrantListQuery>(() => ({
    ...filters,
    limit: PAGE_SIZE,
    offset,
  }), [filters, offset])

  const loadResources = useCallback(async () => {
    setLoadingResources(true)
    try {
      const [workspaceData, sessions, decks, artifacts] = await Promise.all([
        getWorkspaces(),
        getSessions(),
        getDecks(100),
        getArtifacts({ limit: 100 }),
      ])
      setResourceOptions([
        ...workspaceData.workspaces.map(workspaceToOption),
        ...sessions.map(sessionToOption),
        ...decks.map(deckToOption),
        ...artifacts.map(artifactToOption),
      ])
    } catch (err) {
      setError(normalizeApiError(err))
    } finally {
      setLoadingResources(false)
    }
  }, [])

  const loadSubjects = useCallback(async () => {
    setLoadingSubjects(true)
    try {
      const catalog = await getIdentityCatalog(200)
      setSubjectOptions([
        ...catalog.users.map(userToSubjectOption),
        ...catalog.organizations.map(orgToSubjectOption),
      ])
    } catch (err) {
      setError(normalizeApiError(err))
    } finally {
      setLoadingSubjects(false)
    }
  }, [])

  const loadGrants = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getResourceGrants(query)
      setGrants(data.grants)
      setTotal(data.total)
    } catch (err) {
      setError(normalizeApiError(err))
    } finally {
      setLoading(false)
    }
  }, [query])

  useEffect(() => {
    void loadResources()
    void loadSubjects()
  }, [loadResources, loadSubjects])

  useEffect(() => {
    // 身份面板保存组织/用户/成员后，同步刷新主体列表，保证授权表单选项是最新的。
    const handleIdentityCatalogUpdated = () => {
      void loadSubjects()
    }

    window.addEventListener(IDENTITY_CATALOG_UPDATED_EVENT, handleIdentityCatalogUpdated)
    return () => {
      window.removeEventListener(IDENTITY_CATALOG_UPDATED_EVENT, handleIdentityCatalogUpdated)
    }
  }, [loadSubjects])

  useEffect(() => {
    void loadGrants()
  }, [loadGrants])

  const updateFilter = (key: keyof ResourceGrantListQuery, value: string) => {
    setFilters((current) => ({
      ...current,
      [key]: value.trim() ? value : undefined,
      offset: 0,
    }))
  }

  const updateForm = <K extends keyof GrantFormState>(key: K, value: GrantFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }

  const applyResourceToForm = (rawValue: string) => {
    setResourcePick(rawValue)
    const option = resourceOptions.find((item) => optionValue(item) === rawValue)
    if (!option) return
    setForm((current) => ({
      ...current,
      resourceType: option.type,
      resourceId: option.id,
    }))
  }

  const applyResourceToFilter = (rawValue: string) => {
    setFilterResourcePick(rawValue)
    const option = resourceOptions.find((item) => optionValue(item) === rawValue)
    if (!option) return
    setFilters((current) => ({
      ...current,
      resource_type: option.type,
      resource_id: option.id,
      offset: 0,
    }))
  }

  const applySubjectToForm = (rawValue: string) => {
    setSubjectPick(rawValue)
    const option = subjectOptions.find((item) => subjectValue(item) === rawValue)
    if (!option) return
    setForm((current) => ({
      ...current,
      subjectType: option.type,
      subjectId: option.id,
    }))
  }

  const applySubjectToFilter = (rawValue: string) => {
    setFilterSubjectPick(rawValue)
    const option = subjectOptions.find((item) => subjectValue(item) === rawValue)
    if (!option) return
    setFilters((current) => ({
      ...current,
      subject_type: option.type,
      user_id: option.type === 'user' ? option.id : undefined,
      org_id: option.type === 'org' ? option.id : undefined,
      offset: 0,
    }))
  }

  const handleSubmit = async () => {
    const payload = buildMutationPayload(form)
    if (!payload.resource_type || !payload.resource_id || !form.subjectId.trim()) {
      setError('请填写资源类型、资源 ID 和授权主体。')
      return
    }

    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      await upsertResourceGrant(payload)
      setNotice('资源授权已保存。')
      setForm(initialForm)
      setResourcePick('')
      setSubjectPick('')
      await loadGrants()
    } catch (err) {
      setError(normalizeApiError(err))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (grant: ResourceGrant) => {
    const subject = getSubjectLabel(grant)
    if (!window.confirm(`确认删除 ${grant.resource_type}:${grant.resource_id} 的 ${subject} 授权？`)) return

    setError(null)
    setNotice(null)
    try {
      await deleteResourceGrant({
        resource_type: grant.resource_type,
        resource_id: grant.resource_id,
        ...(grant.user_id?.trim() ? { user_id: grant.user_id } : { org_id: grant.org_id ?? '' }),
      })
      setNotice('资源授权已删除。')
      await loadGrants()
    } catch (err) {
      setError(normalizeApiError(err))
    }
  }

  const copyGrantToForm = (grant: ResourceGrant) => {
    const nextSubjectType = grant.user_id?.trim() ? 'user' : 'org'
    const nextSubjectId = grant.user_id?.trim() || grant.org_id?.trim() || ''
    setForm({
      resourceType: grant.resource_type,
      resourceId: grant.resource_id,
      subjectType: nextSubjectType,
      subjectId: nextSubjectId,
      role: grant.role,
    })
    setResourcePick(`${grant.resource_type}:${grant.resource_id}`)
    setSubjectPick(nextSubjectId ? `${nextSubjectType}:${nextSubjectId}` : '')
  }

  return (
    <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4" data-testid="resource-access-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-accent-blue" />
            <h3 className="text-sm font-semibold text-text-primary">资源访问控制</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            管理 session、workspace、artifact、deck 等资源的 user / org 授权，owner 保护由后端兜底。
          </p>
        </div>
        <div className="flex gap-2">
          <Button data-testid="resource-access-refresh-subjects" variant="outline" size="sm" onClick={() => void loadSubjects()} loading={loadingSubjects}>
            <Users size={14} />主体
          </Button>
          <Button data-testid="resource-access-refresh-resources" variant="outline" size="sm" onClick={() => void loadResources()} loading={loadingResources}>
            <Database size={14} />资源
          </Button>
          <Button data-testid="resource-access-refresh-grants" variant="outline" size="sm" onClick={() => void loadGrants()} loading={loading}>
            <RefreshCw size={14} />授权
          </Button>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-bg-border bg-bg-primary/30 p-3">
        <p className="mb-3 text-xs font-medium text-text-primary">资源选择器</p>
        <div className="grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
          <select data-testid="resource-access-filter-resource-pick" className="input-base text-sm" value={filterResourcePick} onChange={(event) => applyResourceToFilter(event.target.value)}>
            <option value="">选择资源后筛选授权</option>
            {resourceOptions.map((option) => (
              <option key={`filter:${optionValue(option)}`} value={optionValue(option)}>
                {option.type} · {option.label} · {option.id}
              </option>
            ))}
          </select>
          <input data-testid="resource-access-filter-resource-type" className="input-base text-sm" placeholder="当前筛选资源类型" value={filters.resource_type ?? ''} onChange={(event) => updateFilter('resource_type', event.target.value)} />
          <input data-testid="resource-access-filter-resource-id" className="input-base text-sm" placeholder="当前筛选资源 ID" value={filters.resource_id ?? ''} onChange={(event) => updateFilter('resource_id', event.target.value)} />
        </div>
        <p className="mt-2 text-[11px] text-text-secondary">
          当前支持自动加载 workspace、session、deck 和 artifact；也可手动输入任意资源类型和 ID。
        </p>
      </div>

      <div className="mt-4 rounded-lg border border-bg-border bg-bg-primary/30 p-3">
        <p className="mb-3 text-xs font-medium text-text-primary">筛选授权</p>
        <div className="grid gap-3 md:grid-cols-[1.4fr_0.8fr_1fr_1fr_0.8fr_auto]">
          <select data-testid="resource-access-filter-subject-pick" className="input-base text-sm" value={filterSubjectPick} onChange={(event) => applySubjectToFilter(event.target.value)}>
            <option value="">选择主体后筛选授权</option>
            {subjectOptions.map((option) => (
              <option key={`filter-subject:${subjectValue(option)}`} value={subjectValue(option)}>
                {option.type} · {option.label} · {option.id}{option.meta ? ` · ${option.meta}` : ''}
              </option>
            ))}
          </select>
          <select data-testid="resource-access-filter-role" className="input-base text-sm" value={filters.role ?? ''} onChange={(event) => updateFilter('role', event.target.value)}>
            <option value="">全部角色</option>
            {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
          </select>
          <input data-testid="resource-access-filter-user-id" className="input-base text-sm" placeholder="用户 ID" value={filters.user_id ?? ''} onChange={(event) => updateFilter('user_id', event.target.value)} />
          <input data-testid="resource-access-filter-org-id" className="input-base text-sm" placeholder="组织 ID" value={filters.org_id ?? ''} onChange={(event) => updateFilter('org_id', event.target.value)} />
          <select data-testid="resource-access-filter-subject-type" className="input-base text-sm" value={filters.subject_type ?? ''} onChange={(event) => updateFilter('subject_type', event.target.value)}>
            <option value="">全部主体</option>
            {SUBJECT_OPTIONS.map((subject) => <option key={subject} value={subject}>{subject}</option>)}
          </select>
          <Button data-testid="resource-access-filter-clear" variant="ghost" size="sm" onClick={() => {
            setFilters({ limit: PAGE_SIZE, offset: 0 })
            setFilterResourcePick('')
            setFilterSubjectPick('')
          }}>清空筛选</Button>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-bg-border bg-bg-primary/30 p-3">
        <p className="mb-3 text-xs font-medium text-text-primary">新增 / 更新授权</p>
        <div className="mb-3 grid gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
          <select data-testid="resource-access-form-resource-pick" className="input-base text-sm" value={resourcePick} onChange={(event) => applyResourceToForm(event.target.value)}>
            <option value="">选择资源后填入表单</option>
            {resourceOptions.map((option) => (
              <option key={`form:${optionValue(option)}`} value={optionValue(option)}>
                {option.type} · {option.label} · {option.id}{option.meta ? ` · ${option.meta}` : ''}
              </option>
            ))}
          </select>
          <input data-testid="resource-access-form-resource-type" className="input-base text-sm" placeholder="资源类型" value={form.resourceType} onChange={(event) => updateForm('resourceType', event.target.value)} />
          <input data-testid="resource-access-form-resource-id" className="input-base text-sm" placeholder="资源 ID" value={form.resourceId} onChange={(event) => updateForm('resourceId', event.target.value)} />
        </div>
        <div className="grid gap-3 md:grid-cols-[0.7fr_1.4fr_1fr_0.7fr_auto]">
          <select data-testid="resource-access-form-subject-type" className="input-base text-sm" value={form.subjectType} onChange={(event) => {
            updateForm('subjectType', event.target.value as SubjectChoice)
            setSubjectPick('')
          }}>
            {SUBJECT_OPTIONS.map((subject) => <option key={subject} value={subject}>{subject}</option>)}
          </select>
          <select data-testid="resource-access-form-subject-pick" className="input-base text-sm" value={subjectPick} onChange={(event) => applySubjectToForm(event.target.value)}>
            <option value="">选择主体后填入表单</option>
            {filteredSubjectOptions.map((option) => (
              <option key={`form-subject:${subjectValue(option)}`} value={subjectValue(option)}>
                {option.label} · {option.id}{option.meta ? ` · ${option.meta}` : ''}
              </option>
            ))}
          </select>
          <input data-testid="resource-access-form-subject-id" className="input-base text-sm" placeholder={form.subjectType === 'user' ? '用户 ID' : '组织 ID'} value={form.subjectId} onChange={(event) => {
            updateForm('subjectId', event.target.value)
            setSubjectPick('')
          }} />
          <select data-testid="resource-access-form-role" className="input-base text-sm" value={form.role} onChange={(event) => updateForm('role', event.target.value as ResourceGrantRole)}>
            {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
          </select>
          <Button data-testid="resource-access-form-save" variant="primary" onClick={() => void handleSubmit()} loading={saving}>保存</Button>
        </div>
      </div>

      {(error || notice) && (
        <div className={`mt-3 rounded-lg border px-3 py-2 text-xs ${error ? 'border-accent-red/30 bg-accent-red/10 text-accent-red' : 'border-accent-green/30 bg-accent-green/10 text-accent-green'}`}>
          {error ?? notice}
        </div>
      )}

      <div className="mt-4 overflow-hidden rounded-lg border border-bg-border" data-testid="resource-access-grant-list">
        <div className="grid grid-cols-[1.1fr_1.4fr_1fr_0.7fr_0.8fr] gap-3 bg-bg-secondary/60 px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-text-secondary">
          <span>资源</span>
          <span>资源 ID</span>
          <span>主体</span>
          <span>角色</span>
          <span className="text-right">操作</span>
        </div>
        {grants.length === 0 ? (
          <div className="px-3 py-6 text-center text-xs text-text-secondary">
            {loading ? '正在加载授权...' : '暂无匹配的资源授权。'}
          </div>
        ) : grants.map((grant) => (
          <div key={`${grant.resource_type}:${grant.resource_id}:${getSubjectLabel(grant)}`} className="grid grid-cols-[1.1fr_1.4fr_1fr_0.7fr_0.8fr] gap-3 border-t border-bg-border px-3 py-2 text-xs text-text-primary">
            <span className="truncate">{grant.resource_type}</span>
            <span className="truncate font-mono text-[11px] text-text-secondary">{grant.resource_id}</span>
            <span className="truncate font-mono text-[11px] text-text-secondary">{getSubjectLabel(grant)}</span>
            <span className="rounded-full bg-bg-secondary px-2 py-0.5 text-center text-[11px] text-text-primary">{grant.role}</span>
            <span className="flex justify-end gap-2">
              <Button variant="ghost" size="sm" onClick={() => copyGrantToForm(grant)}>编辑</Button>
              <Button variant="danger" size="sm" onClick={() => void handleDelete(grant)}><Trash2 size={13} /></Button>
            </span>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-text-secondary">
        <span>共 {total} 条，当前 {total === 0 ? 0 : offset + 1}-{offset + grants.length}</span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" disabled={!canPrev} onClick={() => setFilters((current) => ({ ...current, offset: Math.max(0, offset - PAGE_SIZE) }))}>上一页</Button>
          <Button variant="ghost" size="sm" disabled={!canNext} onClick={() => setFilters((current) => ({ ...current, offset: offset + PAGE_SIZE }))}>下一页</Button>
        </div>
      </div>
    </div>
  )
}
