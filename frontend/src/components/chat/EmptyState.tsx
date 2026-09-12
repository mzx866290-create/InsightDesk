import React from 'react'
import { Bot } from 'lucide-react'
import type { SystemPrompt } from '../../api/client'
import { getStartersForPrompt } from './chatPanelModel'

interface EmptyStateProps {
  modelName: string
  activePrompt: SystemPrompt | null
  onSelectStarter: (text: string) => void
}

export const EmptyState: React.FC<EmptyStateProps> = ({ modelName, activePrompt, onSelectStarter }) => {
  const starters = getStartersForPrompt(activePrompt)
  return (
    <div className="flex flex-col items-center justify-center h-full text-center gap-4 py-10">
      <div className="w-12 h-12 rounded-2xl bg-accent-blue/10 flex items-center justify-center">
        <Bot size={24} className="text-accent-blue/60" />
      </div>
      <div>
        <p className="text-text-secondary text-sm font-medium">
          {activePrompt ? activePrompt.name : '准备就绪'}
        </p>
        <p className="text-text-secondary/50 text-xs mt-0.5">{modelName}</p>
      </div>
      <div className="grid grid-cols-1 gap-2 w-full max-w-xs mt-1">
        {starters.map((starter) => (
          <button
            key={starter}
            type="button"
            onClick={() => onSelectStarter(starter)}
            className="text-left rounded-xl border border-bg-border bg-bg-tertiary/40 px-3 py-2.5 text-xs text-text-secondary transition-colors hover:border-accent-blue/40 hover:bg-accent-blue/5 hover:text-text-primary"
          >
            {starter}
          </button>
        ))}
      </div>
    </div>
  )
}
