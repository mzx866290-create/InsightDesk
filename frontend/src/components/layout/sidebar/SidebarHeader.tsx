import { ChevronLeft } from 'lucide-react'

interface SidebarHeaderProps {
  onToggleSidebar: () => void
}

export function SidebarHeader({ onToggleSidebar }: SidebarHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-bg-border px-4 py-4">
      <div className="flex min-w-0 items-center gap-2.5">
        <div className="h-9 w-9 shrink-0 overflow-hidden rounded-xl bg-white/6 ring-1 ring-white/8">
          <img
            src="/sidebar-logo.png"
            alt="InsightDesk logo"
            className="h-full w-full scale-[1.9] object-cover object-[center_18%]"
          />
        </div>
        <span className="truncate text-sm font-semibold text-text-primary">InsightDesk</span>
      </div>
      <button
        onClick={onToggleSidebar}
        className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-bg-hover hover:text-text-primary"
        title="Collapse sidebar"
      >
        <ChevronLeft size={16} />
      </button>
    </div>
  )
}
