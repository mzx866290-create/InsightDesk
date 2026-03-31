import React, { useState } from 'react'
import { FileText, ExternalLink, ChevronDown, ChevronUp, BookOpen } from 'lucide-react'
import type { SourceItem } from '../../api/client'

interface SourcesPanelProps {
  sources: SourceItem[]
}

export const SourcesPanel: React.FC<SourcesPanelProps> = ({ sources }) => {
  const [expanded, setExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  const docSources = sources.filter((s) => s.type === 'doc')
  const webSources = sources.filter((s) => s.type === 'web')

  return (
    <div className="mt-3 border border-bg-border rounded-lg overflow-hidden text-xs">
      {/* Header toggle */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-bg-tertiary/60 hover:bg-bg-tertiary transition-colors text-text-secondary"
      >
        <BookOpen size={12} className="text-accent-blue/70 shrink-0" />
        <span className="font-medium text-text-primary/80">
          参考来源
          <span className="ml-1.5 text-text-secondary font-normal">
            ({sources.length} 条)
          </span>
        </span>
        <span className="ml-auto">
          {expanded ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        </span>
      </button>

      {/* Sources list */}
      {expanded && (
        <div className="divide-y divide-bg-border">
          {docSources.map((src, i) => (
            <div key={`doc-${i}`} className="flex items-start gap-2.5 px-3 py-2.5 hover:bg-bg-hover/30 transition-colors">
              <FileText size={12} className="text-accent-blue/60 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <p className="font-medium text-text-primary/90 truncate">{src.title}</p>
                {src.snippet && (
                  <p className="text-text-secondary/70 mt-0.5 line-clamp-2 leading-relaxed">
                    {src.snippet}
                  </p>
                )}
              </div>
            </div>
          ))}
          {webSources.map((src, i) => (
            <div key={`web-${i}`} className="flex items-start gap-2.5 px-3 py-2.5 hover:bg-bg-hover/30 transition-colors">
              <ExternalLink size={12} className="text-accent-green/60 shrink-0 mt-0.5" />
              <div className="min-w-0">
                {src.url ? (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-accent-blue hover:underline underline-offset-2 truncate block"
                  >
                    {src.title}
                  </a>
                ) : (
                  <p className="font-medium text-text-primary/90 truncate">{src.title}</p>
                )}
                {src.snippet && (
                  <p className="text-text-secondary/70 mt-0.5 line-clamp-2 leading-relaxed">
                    {src.snippet}
                  </p>
                )}
                {src.url && (
                  <p className="text-text-secondary/40 mt-0.5 truncate">{src.url}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
