// Project Members Tab component — imported into UserManagementPage
import { useEffect, useState } from 'react'
import { UserMinus, UserPlus } from 'lucide-react'
import toast from 'react-hot-toast'
import { userManagementService, type ProjectMember, type UserItem, type UserRole } from '@/services/userManagementService'
import { projectsService } from '@/services/projectsService'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import type { Project } from '@/types/projects'

const ROLES: UserRole[] = ['VIEWER', 'TESTER', 'QA_ENGINEER', 'QA_LEAD', 'ADMIN']
const ROLE_COLORS: Record<UserRole, string> = {
  VIEWER: 'bg-slate-700 text-slate-300',
  TESTER: 'bg-blue-900/50 text-blue-300',
  QA_ENGINEER: 'bg-emerald-900/50 text-emerald-300',
  QA_LEAD: 'bg-amber-900/50 text-amber-300',
  ADMIN: 'bg-red-900/50 text-red-300',
}

export function ProjectMembersTab({ isAdmin, canManageUsers }: { isAdmin: boolean; canManageUsers: boolean }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState<string>('')
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [allUsers, setAllUsers] = useState<UserItem[]>([])
  const [loading, setLoading] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)

  useEffect(() => {
    projectsService.list()
      .then(setProjects)
      .catch(() => toast.error('Failed to load projects'))
    userManagementService.listUsers()
      .then(setAllUsers)
      .catch(() => toast.error('Failed to load users'))
  }, [])

  useEffect(() => {
    if (!selectedProjectId) { setMembers([]); return }
    setLoading(true)
    userManagementService.listProjectMembers(selectedProjectId)
      .then(setMembers)
      .catch(() => toast.error('Failed to load project members'))
      .finally(() => setLoading(false))
  }, [selectedProjectId])

  async function handleRemove(userId: string) {
    if (!selectedProjectId) return
    if (!confirm('Remove this user from the project?')) return
    try {
      await userManagementService.removeProjectMember(selectedProjectId, userId)
      toast.success('Member removed')
      setMembers(prev => prev.filter(m => m.user_id !== userId))
    } catch { toast.error('Failed to remove member') }
  }

  async function handleRoleChange(userId: string, role: UserRole) {
    if (!selectedProjectId) return
    try {
      const updated = await userManagementService.updateProjectMemberRole(selectedProjectId, userId, role)
      setMembers(prev => prev.map(m => m.user_id === userId ? { ...m, role: updated.role } : m))
      toast.success('Role updated')
    } catch { toast.error('Failed to update role') }
  }

  const selectedProject = projects.find(p => p.id === selectedProjectId)
  const memberUserIds = new Set(members.map(m => m.user_id))
  const nonMembers = allUsers.filter(u => !memberUserIds.has(u.id))

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm text-slate-400 whitespace-nowrap">Select Project:</label>
        <select
          value={selectedProjectId}
          onChange={e => setSelectedProjectId(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-200 text-sm rounded px-3 py-2 focus:outline-none focus:border-blue-500 flex-1 max-w-xs"
        >
          <option value="">— Pick a project —</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {selectedProjectId && canManageUsers && (
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 text-sm bg-blue-600 hover:bg-blue-500 text-white px-3 py-2 rounded-lg font-medium"
          >
            <UserPlus className="h-4 w-4" /> Add Member
          </button>
        )}
      </div>

      {!selectedProjectId ? (
        <div className="text-center py-16 text-slate-500 text-sm">
          Select a project to view and manage its members.
        </div>
      ) : loading ? (
        <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
      ) : members.length === 0 ? (
        <div className="text-center py-16 text-slate-500 text-sm">
          No members assigned to <span className="text-slate-300">{selectedProject?.name}</span> yet.
          {canManageUsers && (
            <button onClick={() => setShowAddModal(true)} className="ml-2 text-blue-400 hover:text-blue-300 underline">
              Add the first member
            </button>
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-800/80">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">User</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Project Role</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">Added</th>
                {isAdmin && <th className="px-4 py-3 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {members.map(m => (
                <tr key={m.id} className="hover:bg-slate-800/40 transition-colors">
                  <td className="px-4 py-3 text-slate-200 font-medium">{m.full_name || m.username}</td>
                  <td className="px-4 py-3 text-slate-400">{m.email}</td>
                  <td className="px-4 py-3">
                    {canManageUsers ? (
                      <select
                        value={m.role}
                        onChange={e => handleRoleChange(m.user_id, e.target.value as UserRole)}
                        className="text-xs rounded px-2 py-1 border border-transparent bg-slate-700 text-slate-300 focus:outline-none"
                      >
                        {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                      </select>
                    ) : (
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${ROLE_COLORS[m.role] || 'bg-slate-700 text-slate-300'}`}>{m.role}</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  {isAdmin && (
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleRemove(m.user_id)}
                        className="text-red-500/70 hover:text-red-400 p-1 rounded transition-colors"
                        title="Remove from project"
                      >
                        <UserMinus className="h-4 w-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAddModal && selectedProjectId && (
        <AddProjectMemberModal
          projectId={selectedProjectId}
          projectName={selectedProject?.name ?? ''}
          nonMembers={nonMembers}
          onClose={() => setShowAddModal(false)}
          onAdded={member => { setMembers(prev => [...prev, member]); setShowAddModal(false) }}
        />
      )}
    </div>
  )
}

interface AddProjectMemberModalProps {
  projectId: string
  projectName: string
  nonMembers: UserItem[]
  onClose: () => void
  onAdded: (member: ProjectMember) => void
}

function AddProjectMemberModal({ projectId, projectName, nonMembers, onClose, onAdded }: AddProjectMemberModalProps) {
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState<UserRole>('TESTER')
  const [saving, setSaving] = useState(false)

  async function handleAdd() {
    if (!userId) { toast.error('Select a user'); return }
    setSaving(true)
    try {
      const member = await userManagementService.addProjectMember(projectId, userId, role)
      toast.success('Member added successfully')
      onAdded(member)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to add member')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
        <h2 className="text-base font-semibold text-slate-100 mb-1">Add Member to {projectName}</h2>
        <p className="text-xs text-slate-400 mb-4">Assign a user to this project with a specific role.</p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-400 mb-1">User</label>
            <select
              value={userId}
              onChange={e => setUserId(e.target.value)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              <option value="">— Select user —</option>
              {nonMembers.map(u => (
                <option key={u.id} value={u.id}>{u.full_name || u.username} ({u.email})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Project Role</label>
            <select
              value={role}
              onChange={e => setRole(e.target.value as UserRole)}
              className="w-full bg-slate-800 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:border-blue-500"
            >
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200">Cancel</button>
          <button
            onClick={handleAdd}
            disabled={saving || !userId}
            className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium flex items-center gap-2"
          >
            {saving ? <LoadingSpinner size="sm" /> : <UserPlus className="h-4 w-4" />}
            {saving ? 'Adding…' : 'Add Member'}
          </button>
        </div>
      </div>
    </div>
  )
}
