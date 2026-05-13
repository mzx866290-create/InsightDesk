import {
  getKbRetrievalTestId,
  type KbRetrievalControlsConfig,
  type KbRetrievalControlsVariant,
} from './KbRetrievalControlsModel'
import { KbRetrievalRunButton } from './KbRetrievalControlRunButton'

interface KbRetrievalQueryRowProps {
  config: KbRetrievalControlsConfig
  query: string
  loading: boolean
  variant: KbRetrievalControlsVariant
  testIdPrefix?: string
  onQueryChange: (value: string) => void
  onTest: () => void | Promise<void>
}

export function KbRetrievalQueryRow({
  config,
  query,
  loading,
  variant,
  testIdPrefix,
  onQueryChange,
  onTest,
}: KbRetrievalQueryRowProps) {
  return (
    <div className={config.queryRowClassName}>
      <input
        data-testid={getKbRetrievalTestId(testIdPrefix, 'query')}
        className={config.queryInputClassName}
        placeholder={config.placeholder}
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') void onTest()
        }}
      />
      <KbRetrievalRunButton
        variant={variant}
        loading={loading}
        disabled={!query.trim()}
        label={config.submitLabel}
        testId={getKbRetrievalTestId(testIdPrefix, 'run')}
        onClick={onTest}
      />
    </div>
  )
}
