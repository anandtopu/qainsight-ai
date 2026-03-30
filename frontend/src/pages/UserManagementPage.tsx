import { useState } from 'react'
import { FolderOpen, Key, Plus, RefreshCw, Shield, Trash2, UserCheck, UserPlus, UserX, Users } from 'lucide-react'
import toast from 'react-hot-toast'
import { useUsers, useApiKeys, refreshUsers, refreshApiKeys } from '@/hooks/useUserManagement'
import { userManagementService, type UserRole } from '@/services/userManagementService'
import { usePermissions } from '@/hooks/usePermissions'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { ProjectMembersTab } from './ProjectMembersTab'

const ROLES: UserRole[] = ['VIEWER', 'TESTER', 'QA_ENGINEER', 'QA_LEAD', 'ADMIN']

const ROLE_COLORS: Record<UserRole, string> = {
  VIEWER: 'bg-slate-700 text-slate-300',
  TESTER: 'bg-blue-900/50 text-blue-300',
  QA_ENGINEER: 'bg-emerald-900/50 text-emerald-300',
  QA_LEAD: 'bg-amber-900/50 text-amber-300',
  ADMIN: 'bg-red-900/50 text-red-300',
}

export default function UserManagementPage() {
  const [tab, setTab] = useState<'users' | 'apikeys' | 'project-members'>('users')
  const { canManageUsers, canGenerateApiKeys, isAdmin } = usePermissions()

  const tabClass = (t: typeof tab) =>
    `px-4 py-2 text-sm font-medium transition-colors ${
      tab === t ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-400 hover:text-slate-200'
    }`

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-100">User Management</h1>
          <p className="text-sm text-slate-400 mt-0.5">Manage users, roles, project access, and API keys</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-700">
        <button onClick={() => setTab('users')} className={tabClass('users')}>
          <span className="flex items-center gap-2"><Users className="h-4 w-4" /> Users</span>
        </button>
        <button onClick={() => setTab('project-members')} className={tabClass('project-members')}>
          <span className="flex items-center gap-2"><FolderOpen className="h-4 w-4" /> Project Access</span>
        </button>
        <button onClick={() => setTab('apikeys')} className={tabClass('apikeys')}>
          <span className="flex items-center gap-2"><Key className="h-4 w-4" /> API Keys</span>
        </button>
      </div>

      {tab === 'users' && <UsersTab canManageUsers={canManageUsers} isAdmin={isAdmin} />}
      {tab === 'project-members' && <ProjectMembersTab isAdmin={isAdmin} canManageUsers={canManageUsers} />}
      {tab === 'apikeys' && <ApiKeysTab canGenerateApiKeys={canGenerateApiKeys} />}
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────

function UsersTab({ canManageUsers, isAdmin }: { canManageUsers: boolean; isAdmin: boolean }) {
  const { data: users, isLoading } = useUsers()
  const [showInviteModal, setShowInviteModal] = useState(false)
  const [showAddUserModal, setShowAddUserModal] = useState(false)
  const [filterRole, setFilterRole] = useState<UserRole | ''>('')
  const [filterActive, setFilterActive] = useState<'all' | 'active' | 'inactive'>('all')

  const filtered = (users ?? []).filter((u) => {
    if (filterRole && u.role !== filterRole) return false
    if (filterActive === 'active' && !u.is_active) return false
    if (filterActive === 'inactive' && u.is_active) return false
    return true
  })

  async function handleRoleChange(userId: string, role: UserRole) {
    try {
      await userManagementService.updateUserRole(userId, role)
      refreshUsers()
      toast.success('Role updated')
    } catch {
      toast.error('Failed to update role')
    }
  }

  async function handleToggleStatus(userId: string, currentActive: boolean) {
    try {
      await userManagementService.updateUserStatus(userId, !currentActive)
      refreshUsers()
      toast.success(currentActive ? 'User deactivated' : 'User activated')
    } catch {
      toast.error('Failed to update status')
    }
  }

  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner /></div>

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex gap-2">
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value as UserRole | '')}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-1.5"
          >
            <option value="">All roles</option>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select
            value={filterActive}
            onChange={(e) => setFilterActive(e.target.value as 'all' | 'active' | 'inactive')}
            className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-1.5"
          >
            <option value="all">All status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
        {isAdmin && (
          <div className="flex gap-2">
            <button
              onClick={() => setShowAddUserModal(true)}
              className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm px-3 py-1.5 rounded transition-colors"
            >
              <UserPlus className="h-4 w-4" /> Add User
            </button>
            {canManageUsers && (
              <button
                onClick={() => setShowInviteModal(true)}
                className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1.5 rounded transition-colors"
              >
                <Plus className="h-4 w-4" /> Invite User
              </button>
            )}
          </div>
        )}
      </div>

      {/* Table */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-800/80">
              <th className="text-left px-4 py-3 text-slate-400 font-medium">User</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Role</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Status</th>
              {isAdmin && <th className="text-left px-4 py-3 text-slate-400 font-medium">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {filtered.map((user) => (
              <tr key={user.id} className="hover:bg-slate-700/30 transition-colors">
                <td className="px-4 py-3">
                  <div className="font-medium text-slate-200">{user.full_name || user.username}</div>
                  <div className="text-xs text-slate-500">{user.email}</div>
                </td>
                <td className="px-4 py-3">
                  {isAdmin ? (
                    <select
                      value={user.role}
                      onChange={(e) => handleRoleChange(user.id, e.target.value as UserRole)}
                      className="bg-slate-700 border border-slate-600 text-slate-200 text-xs rounded px-2 py-1"
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  ) : (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${ROLE_COLORS[user.role]}`}>
                      <Shield className="h-3 w-3" />{user.role}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                    user.is_active ? 'bg-emerald-900/50 text-emerald-300' : 'bg-slate-700 text-slate-400'
                  }`}>
                    {user.is_active ? <UserCheck className="h-3 w-3" /> : <UserX className="h-3 w-3" />}
                    {user.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                {isAdmin && (
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggleStatus(user.id, user.is_active)}
                      className={`text-xs px-2 py-1 rounded transition-colors ${
                        user.is_active
                          ? 'text-red-400 hover:bg-red-900/30'
                          : 'text-emerald-400 hover:bg-emerald-900/30'
                      }`}
                    >
                      {user.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">No users found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showInviteModal && (
        <InviteUserModal onClose={() => setShowInviteModal(false)} />
      )}
      {showAddUserModal && (
        <AddUserModal onClose={() => setShowAddUserModal(false)} />
      )}
    </div>
  )
}

// ── Add User Modal (admin direct create) ──────────────────────

function AddUserModal({ onClose }: { onClose: () => void }) {
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState<UserRole>('QA_ENGINEER')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ username: string; temp_password: string } | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await userManagementService.createUser(email, username, role, fullName || undefined)
      setResult({ username: res.username, temp_password: res.temp_password })
      refreshUsers()
      toast.success('User created')
    } catch {
      toast.error('Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Add User</h2>
        {result ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-300">
              User <strong className="text-slate-100">{result.username}</strong> created. Share the temporary password:
            </p>
            <div className="bg-slate-900 border border-amber-700/50 rounded p-3">
              <p className="text-xs text-slate-400 mb-1">Temporary password (shown once):</p>
              <code className="text-sm text-amber-300 font-bold break-all">{result.temp_password}</code>
            </div>
            <p className="text-xs text-slate-500">The user should change this password after first login.</p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(result.temp_password)
                  toast.success('Copied!')
                }}
                className="text-sm text-blue-400 hover:text-blue-300 px-3 py-1.5"
              >
                Copy Password
              </button>
              <button
                onClick={onClose}
                className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm px-4 py-2 rounded"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Email address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
                placeholder="user@company.com"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Username</label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
                placeholder="jdoe"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Full name (optional)</label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
                placeholder="Jane Doe"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="text-sm text-slate-400 hover:text-slate-200 px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
              >
                {loading ? 'Creating…' : 'Create User'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ── Invite Modal ──────────────────────────────────────────────

function InviteUserModal({ onClose }: { onClose: () => void }) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<UserRole>('QA_ENGINEER')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ invitation_link: string } | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await userManagementService.inviteUser(email, role)
      setResult(res)
      refreshUsers()
      toast.success('Invitation created')
    } catch {
      toast.error('Failed to create invitation')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Invite User</h2>
        {result ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-300">Invitation created. Share this link with the user:</p>
            <div className="bg-slate-900 border border-slate-700 rounded p-3">
              <code className="text-xs text-emerald-400 break-all">
                {window.location.origin}{result.invitation_link}
              </code>
            </div>
            <div className="flex justify-end">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(window.location.origin + result.invitation_link)
                  toast.success('Copied!')
                }}
                className="text-sm text-blue-400 hover:text-blue-300 mr-3"
              >
                Copy link
              </button>
              <button
                onClick={onClose}
                className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm px-4 py-2 rounded"
              >
                Close
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Email address</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
                placeholder="user@company.com"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              >
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="text-sm text-slate-400 hover:text-slate-200 px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
              >
                {loading ? 'Sending…' : 'Send Invitation'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ── API Keys Tab ──────────────────────────────────────────────

function ApiKeysTab({ canGenerateApiKeys }: { canGenerateApiKeys: boolean }) {
  const { data: keys, isLoading } = useApiKeys()
  const [showCreateModal, setShowCreateModal] = useState(false)

  async function handleRevoke(keyId: string, name: string) {
    if (!confirm(`Revoke key "${name}"? This cannot be undone.`)) return
    try {
      await userManagementService.revokeApiKey(keyId)
      refreshApiKeys()
      toast.success('API key revoked')
    } catch {
      toast.error('Failed to revoke key')
    }
  }

  if (isLoading) return <div className="flex justify-center py-12"><LoadingSpinner /></div>

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        {canGenerateApiKeys && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1.5 rounded transition-colors"
          >
            <Plus className="h-4 w-4" /> Generate Key
          </button>
        )}
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 bg-slate-800/80">
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Name</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Key</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Scopes</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Expires</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Last Used</th>
              <th className="text-left px-4 py-3 text-slate-400 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {(keys ?? []).map((k) => (
              <tr key={k.id} className="hover:bg-slate-700/30 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-200">{k.name}</td>
                <td className="px-4 py-3">
                  <code className="text-xs text-emerald-400 bg-slate-900 px-2 py-0.5 rounded">
                    {k.key_hint}
                  </code>
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1">
                    {k.scopes.length > 0 ? (
                      k.scopes.map((s) => (
                        <span key={s} className="text-xs bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
                          {s}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-slate-500">all</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {k.expires_at ? (
                    new Date(k.expires_at).toLocaleDateString()
                  ) : (
                    <span className="text-slate-500">Never</span>
                  )}
                </td>
                <td className="px-4 py-3 text-slate-400 text-xs">
                  {k.last_used_at ? (
                    new Date(k.last_used_at).toLocaleDateString()
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleRevoke(k.id, k.name)}
                    className="text-red-400 hover:text-red-300 hover:bg-red-900/20 p-1 rounded transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            ))}
            {(keys ?? []).length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                  No API keys yet. Generate one to authenticate CI/CD pipelines.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showCreateModal && (
        <CreateApiKeyModal onClose={() => setShowCreateModal(false)} />
      )}
    </div>
  )
}

// ── Create API Key Modal ──────────────────────────────────────

const AVAILABLE_SCOPES = ['test:read', 'test:write', 'report:read', 'report:write', 'admin:read']

function CreateApiKeyModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [scopes, setScopes] = useState<string[]>([])
  const [expiresDays, setExpiresDays] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)

  function toggleScope(s: string) {
    setScopes((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    try {
      const result = await userManagementService.createApiKey(
        name,
        scopes,
        expiresDays ? parseInt(expiresDays) : undefined,
      )
      setCreatedKey(result.raw_key)
      refreshApiKeys()
    } catch {
      toast.error('Failed to generate API key')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-800 border border-slate-700 rounded-lg w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-100">Generate API Key</h2>
        {createdKey ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 p-3 bg-amber-900/30 border border-amber-700/50 rounded text-amber-300 text-xs">
              <RefreshCw className="h-4 w-4 flex-shrink-0" />
              <span>Copy this key now — it will not be shown again.</span>
            </div>
            <div className="bg-slate-900 border border-slate-700 rounded p-3">
              <code className="text-xs text-emerald-400 break-all">{createdKey}</code>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(createdKey)
                  toast.success('Copied!')
                }}
                className="text-sm text-blue-400 hover:text-blue-300 px-3 py-1.5"
              >
                Copy
              </button>
              <button
                onClick={onClose}
                className="bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm px-4 py-2 rounded"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Key name</label>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. GitHub Actions CI"
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-2">
                Scopes (leave empty for full access)
              </label>
              <div className="flex flex-wrap gap-2">
                {AVAILABLE_SCOPES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleScope(s)}
                    className={`text-xs px-2 py-1 rounded border transition-colors ${
                      scopes.includes(s)
                        ? 'bg-blue-600/30 border-blue-500 text-blue-300'
                        : 'bg-slate-700 border-slate-600 text-slate-400 hover:border-slate-500'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Expiry (days, optional)</label>
              <input
                type="number"
                min={1}
                max={365}
                value={expiresDays}
                onChange={(e) => setExpiresDays(e.target.value)}
                placeholder="Never expires"
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="text-sm text-slate-400 hover:text-slate-200 px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !name}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm px-4 py-2 rounded transition-colors"
              >
                {loading ? 'Generating…' : 'Generate'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}