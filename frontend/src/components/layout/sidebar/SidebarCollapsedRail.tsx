import { Plus } from 'lucide-react'

interface SidebarCollapsedRailProps {
  onToggleSidebar: () => void
  onNewChat: () => void | Promise<void>
}

export function SidebarCollapsedRail({
  onToggleSidebar,
  onNewChat,
}: SidebarCollapsedRailProps) {
  return (
    <div className="flex w-14 shrink-0 flex-col items-center gap-4 border-r border-bg-border bg-bg-primary py-4">
      <button
        onClick={onToggleSidebar}
        className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        title="Expand sidebar"
      >
        <div className="h-6 w-6 overflow-hidden rounded-lg bg-white/6 ring-1 ring-white/8">
          <img
            src="/sidebar-logo.png"
            alt="InsightDesk logo"
            className="h-full w-full scale-[2.05] object-cover object-[center_18%]"
          />
        </div>
      </button>
      <button
        onClick={() => {
          void onNewChat()
        }}
        className="rounded-lg p-2 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        title="新建对话"
      >
        <Plus size={20} />
      </button>
    </div>
  )
}
