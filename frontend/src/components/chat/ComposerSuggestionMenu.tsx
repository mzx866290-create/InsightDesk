import type { ComposerSuggestion } from './messageInputUtils'

interface ComposerSuggestionMenuProps {
  suggestions: ComposerSuggestion[]
  activeSuggestionIndex: number
  onApplySuggestion: (suggestion: ComposerSuggestion) => void
}

export function ComposerSuggestionMenu({
  suggestions,
  activeSuggestionIndex,
  onApplySuggestion,
}: ComposerSuggestionMenuProps) {
  if (suggestions.length === 0) return null

  return (
    <div className="absolute bottom-full left-0 right-0 z-20 mb-2 overflow-hidden rounded-xl border border-bg-border bg-bg-primary shadow-xl">
      <div className="max-h-56 overflow-y-auto py-1">
        {suggestions.map((suggestion, index) => (
          <button
            key={suggestion.id}
            type="button"
            className={`w-full px-3 py-2 text-left transition-colors ${
              index === activeSuggestionIndex
                ? 'bg-accent-blue/15'
                : 'hover:bg-bg-hover'
            }`}
            onMouseDown={(event) => {
              event.preventDefault()
              onApplySuggestion(suggestion)
            }}
          >
            <div className="flex items-center gap-2 text-xs font-medium text-text-primary">
              <span className="rounded-md bg-bg-tertiary px-1.5 py-0.5 text-[10px] text-text-secondary">
                {suggestion.trigger}
              </span>
              <span>{suggestion.label}</span>
            </div>
            <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-text-secondary">
              {suggestion.description}
            </p>
          </button>
        ))}
      </div>
    </div>
  )
}
