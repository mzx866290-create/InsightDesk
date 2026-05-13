import type { Workspace } from '../../../api/client'

interface WorkspaceDeleteDialogProps {
  deleteTargets: Workspace[]
  targetId: string
  deleting: boolean
  onTargetChange: (workspaceId: string) => void
  onCancel: () => void
  onDelete: () => Promise<void>
}

export function WorkspaceDeleteDialog({
  deleteTargets,
  targetId,
  deleting,
  onTargetChange,
  onCancel,
  onDelete,
}: WorkspaceDeleteDialogProps) {
  return (
    <div className="mt-3 space-y-2 rounded-xl border border-accent-red/20 bg-accent-red/5 p-2.5">
      <div className="text-xs font-medium text-text-primary">Delete workspace</div>
      <div className="text-[11px] leading-relaxed text-text-secondary">
        Before deleting, all conversations in this workspace will be moved to the selected target.
      </div>
      <select
        value={targetId}
        onChange={(event) => onTargetChange(event.target.value)}
        className="w-full rounded-lg border border-bg-border bg-bg-secondary px-2.5 py-2 text-xs text-text-primary outline-none"
      >
        {deleteTargets.map((workspace) => (
          <option key={workspace.workspace_id} value={workspace.workspace_id}>
            Move to {workspace.name}
          </option>
        ))}
      </select>
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg px-2 py-1 text-[11px] text-text-secondary transition-colors hover:text-text-primary"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => {
            void onDelete()
          }}
          disabled={deleting || deleteTargets.length === 0}
          className="rounded-lg border border-accent-red/30 px-2.5 py-1 text-[11px] text-accent-red transition-colors hover:bg-accent-red/10 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {deleting ? 'Deleting...' : 'Confirm delete'}
        </button>
      </div>
    </div>
  )
}
