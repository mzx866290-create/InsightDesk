import React, { useCallback, useEffect, useState } from 'react'
import { Building2, RefreshCw, Users } from 'lucide-react'

import {
  getIdentityCatalog,
  setIdentityMembership,
  upsertIdentityOrganization,
  upsertIdentityUser,
} from '../../api/client'
import { dispatchIdentityCatalogUpdated } from './adminEvents'
import type {
  IdentityCatalog,
  IdentityRole,
  SetMembershipPayload,
  UpsertOrganizationPayload,
  UpsertUserPayload,
} from '../../api/client'
import { Button } from '../ui/Button'

const ROLE_OPTIONS: IdentityRole[] = ['viewer', 'editor', 'admin', 'owner']

const emptyCatalog: IdentityCatalog = {
  organizations: [],
  users: [],
  memberships: [],
}

function normalizeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error || '操作失败')
}

export const IdentityAdminPanel: React.FC = () => {
  const [catalog, setCatalog] = useState<IdentityCatalog>(emptyCatalog)
  const [orgForm, setOrgForm] = useState<UpsertOrganizationPayload>({ org_id: '', name: '', description: '' })
  const [userForm, setUserForm] = useState<UpsertUserPayload>({ user_id: '', display_name: '', email: '' })
  const [membershipForm, setMembershipForm] = useState<SetMembershipPayload>({ org_id: '', user_id: '', role: 'viewer' })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState<'org' | 'user' | 'membership' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const loadCatalog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setCatalog(await getIdentityCatalog(200))
    } catch (err) {
      setError(normalizeError(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadCatalog()
  }, [loadCatalog])

  const saveOrg = async () => {
    const payload = {
      org_id: orgForm.org_id.trim(),
      name: orgForm.name.trim(),
      description: orgForm.description?.trim() ?? '',
    }
    if (!payload.org_id || !payload.name) {
      setError('请填写组织 ID 和组织名称。')
      return
    }

    setSaving('org')
    setError(null)
    setNotice(null)
    try {
      await upsertIdentityOrganization(payload)
      setNotice('组织已保存。')
      setOrgForm({ org_id: '', name: '', description: '' })
      await loadCatalog()
      // 通知同页其他管理面板同步最新身份目录，避免主体选择器数据陈旧。
      dispatchIdentityCatalogUpdated()
    } catch (err) {
      setError(normalizeError(err))
    } finally {
      setSaving(null)
    }
  }

  const saveUser = async () => {
    const payload = {
      user_id: userForm.user_id.trim(),
      display_name: userForm.display_name?.trim() ?? '',
      email: userForm.email?.trim() ?? '',
    }
    if (!payload.user_id) {
      setError('请填写用户 ID。')
      return
    }

    setSaving('user')
    setError(null)
    setNotice(null)
    try {
      await upsertIdentityUser(payload)
      setNotice('用户已保存。')
      setUserForm({ user_id: '', display_name: '', email: '' })
      await loadCatalog()
      // 通知同页其他管理面板同步最新身份目录，避免主体选择器数据陈旧。
      dispatchIdentityCatalogUpdated()
    } catch (err) {
      setError(normalizeError(err))
    } finally {
      setSaving(null)
    }
  }

  const saveMembership = async () => {
    const payload = {
      org_id: membershipForm.org_id.trim(),
      user_id: membershipForm.user_id.trim(),
      role: membershipForm.role,
    }
    if (!payload.org_id || !payload.user_id) {
      setError('请填写组织 ID 和用户 ID。')
      return
    }

    setSaving('membership')
    setError(null)
    setNotice(null)
    try {
      await setIdentityMembership(payload)
      setNotice('成员关系已保存。')
      setMembershipForm({ org_id: '', user_id: '', role: 'viewer' })
      await loadCatalog()
      // 通知同页其他管理面板同步最新身份目录，避免主体选择器数据陈旧。
      dispatchIdentityCatalogUpdated()
    } catch (err) {
      setError(normalizeError(err))
    } finally {
      setSaving(null)
    }
  }

  return (
    <div className="rounded-xl border border-bg-border bg-bg-tertiary/30 p-4" data-testid="identity-admin-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Users size={16} className="text-accent-blue" />
            <h3 className="text-sm font-semibold text-text-primary">身份与组织管理</h3>
          </div>
          <p className="mt-1 text-xs leading-5 text-text-secondary">
            维护组织、用户和组织成员角色，供资源授权和组织继承权限使用。
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadCatalog()} loading={loading}>
          <RefreshCw size={14} />刷新
        </Button>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-bg-border bg-bg-primary/30 p-3">
          <p className="mb-3 flex items-center gap-2 text-xs font-medium text-text-primary">
            <Building2 size={14} />组织
          </p>
          <div className="space-y-2">
            <input data-testid="identity-org-id-input" className="input-base w-full text-sm" placeholder="组织 ID，如 org-acme" value={orgForm.org_id} onChange={(e) => setOrgForm((current) => ({ ...current, org_id: e.target.value }))} />
            <input data-testid="identity-org-name-input" className="input-base w-full text-sm" placeholder="组织名称" value={orgForm.name} onChange={(e) => setOrgForm((current) => ({ ...current, name: e.target.value }))} />
            <input data-testid="identity-org-description-input" className="input-base w-full text-sm" placeholder="描述，可选" value={orgForm.description ?? ''} onChange={(e) => setOrgForm((current) => ({ ...current, description: e.target.value }))} />
            <Button data-testid="identity-org-save" variant="primary" size="sm" onClick={() => void saveOrg()} loading={saving === 'org'}>保存组织</Button>
          </div>
        </div>

        <div className="rounded-lg border border-bg-border bg-bg-primary/30 p-3">
          <p className="mb-3 text-xs font-medium text-text-primary">用户</p>
          <div className="space-y-2">
            <input data-testid="identity-user-id-input" className="input-base w-full text-sm" placeholder="用户 ID，如 user-1" value={userForm.user_id} onChange={(e) => setUserForm((current) => ({ ...current, user_id: e.target.value }))} />
            <input data-testid="identity-user-name-input" className="input-base w-full text-sm" placeholder="显示名称，可选" value={userForm.display_name ?? ''} onChange={(e) => setUserForm((current) => ({ ...current, display_name: e.target.value }))} />
            <input data-testid="identity-user-email-input" className="input-base w-full text-sm" placeholder="邮箱，可选" value={userForm.email ?? ''} onChange={(e) => setUserForm((current) => ({ ...current, email: e.target.value }))} />
            <Button data-testid="identity-user-save" variant="primary" size="sm" onClick={() => void saveUser()} loading={saving === 'user'}>保存用户</Button>
          </div>
        </div>

        <div className="rounded-lg border border-bg-border bg-bg-primary/30 p-3">
          <p className="mb-3 text-xs font-medium text-text-primary">成员关系</p>
          <div className="space-y-2">
            <input data-testid="identity-membership-org-input" className="input-base w-full text-sm" list="identity-org-options" placeholder="组织 ID" value={membershipForm.org_id} onChange={(e) => setMembershipForm((current) => ({ ...current, org_id: e.target.value }))} />
            <input data-testid="identity-membership-user-input" className="input-base w-full text-sm" list="identity-user-options" placeholder="用户 ID" value={membershipForm.user_id} onChange={(e) => setMembershipForm((current) => ({ ...current, user_id: e.target.value }))} />
            <select data-testid="identity-membership-role-input" className="input-base w-full text-sm" value={membershipForm.role} onChange={(e) => setMembershipForm((current) => ({ ...current, role: e.target.value as IdentityRole }))}>
              {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
            </select>
            <Button data-testid="identity-membership-save" variant="primary" size="sm" onClick={() => void saveMembership()} loading={saving === 'membership'}>保存成员</Button>
          </div>
        </div>
      </div>

      <datalist id="identity-org-options">
        {catalog.organizations.map((org) => <option key={org.org_id} value={org.org_id}>{org.name}</option>)}
      </datalist>
      <datalist id="identity-user-options">
        {catalog.users.map((user) => <option key={user.user_id} value={user.user_id}>{user.display_name || user.email}</option>)}
      </datalist>

      {(error || notice) && (
        <div className={`mt-3 rounded-lg border px-3 py-2 text-xs ${error ? 'border-accent-red/30 bg-accent-red/10 text-accent-red' : 'border-accent-green/30 bg-accent-green/10 text-accent-green'}`}>
          {error ?? notice}
        </div>
      )}

      <div className="mt-4 grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-bg-border p-3">
          <p className="mb-2 text-xs font-medium text-text-primary">组织列表（{catalog.organizations.length}）</p>
          <div className="max-h-40 space-y-2 overflow-auto text-xs" data-testid="identity-org-list">
            {catalog.organizations.length === 0 ? <p className="text-text-secondary">暂无组织。</p> : catalog.organizations.map((org) => (
              <button key={org.org_id} type="button" className="block w-full rounded-md bg-bg-secondary/50 px-2 py-1.5 text-left hover:bg-bg-hover" onClick={() => setOrgForm({ org_id: org.org_id, name: org.name, description: org.description })}>
                <span className="block text-text-primary">{org.name}</span>
                <span className="font-mono text-[11px] text-text-secondary">{org.org_id}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-bg-border p-3">
          <p className="mb-2 text-xs font-medium text-text-primary">用户列表（{catalog.users.length}）</p>
          <div className="max-h-40 space-y-2 overflow-auto text-xs" data-testid="identity-user-list">
            {catalog.users.length === 0 ? <p className="text-text-secondary">暂无用户。</p> : catalog.users.map((user) => (
              <button key={user.user_id} type="button" className="block w-full rounded-md bg-bg-secondary/50 px-2 py-1.5 text-left hover:bg-bg-hover" onClick={() => setUserForm({ user_id: user.user_id, display_name: user.display_name, email: user.email })}>
                <span className="block text-text-primary">{user.display_name || user.user_id}</span>
                <span className="font-mono text-[11px] text-text-secondary">{user.user_id}{user.email ? ` · ${user.email}` : ''}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-bg-border p-3">
          <p className="mb-2 text-xs font-medium text-text-primary">成员关系（{catalog.memberships.length}）</p>
          <div className="max-h-40 space-y-2 overflow-auto text-xs" data-testid="identity-membership-list">
            {catalog.memberships.length === 0 ? <p className="text-text-secondary">暂无成员关系。</p> : catalog.memberships.map((membership) => (
              <button key={`${membership.org_id}:${membership.user_id}`} type="button" className="block w-full rounded-md bg-bg-secondary/50 px-2 py-1.5 text-left hover:bg-bg-hover" onClick={() => setMembershipForm({ org_id: membership.org_id, user_id: membership.user_id, role: membership.role })}>
                <span className="block font-mono text-[11px] text-text-primary">{membership.org_id} / {membership.user_id}</span>
                <span className="text-text-secondary">{membership.role}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
