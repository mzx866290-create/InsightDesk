import React from 'react'
import {
  KbRetrievalModeControl,
  KbRetrievalNumberControl,
  KbRetrievalQueryRow,
  KbRetrievalRerankControl,
} from './KbRetrievalControlFields'
import {
  getKbRetrievalTestId,
  KB_RETRIEVAL_CONTROL_CONFIG,
  type KbFetchKVisibility,
  type KbRetrievalControlsVariant,
  type KbRetrievalMode,
} from './KbRetrievalControlsModel'

export type { KbRetrievalMode } from './KbRetrievalControlsModel'

export interface KbRetrievalControlsProps {
  query: string
  loading: boolean
  mode: KbRetrievalMode
  searchK: number
  fetchK: number
  useRerank: boolean
  variant?: KbRetrievalControlsVariant
  fetchKVisibility?: KbFetchKVisibility
  testIdPrefix?: string
  onQueryChange: (value: string) => void
  onModeChange: (value: KbRetrievalMode) => void
  onSearchKChange: (value: number) => void
  onFetchKChange: (value: number) => void
  onUseRerankChange: (value: boolean) => void
  onTest: () => void | Promise<void>
}

export function KbRetrievalControls({
  query,
  loading,
  mode,
  searchK,
  fetchK,
  useRerank,
  variant = 'diagnostic',
  fetchKVisibility,
  testIdPrefix,
  onQueryChange,
  onModeChange,
  onSearchKChange,
  onFetchKChange,
  onUseRerankChange,
  onTest,
}: KbRetrievalControlsProps) {
  const config = KB_RETRIEVAL_CONTROL_CONFIG[variant]
  const shouldShowFetchK = (fetchKVisibility ?? config.fetchKVisibility) === 'always' || useRerank

  const rerankControl = (
    <KbRetrievalRerankControl
      label={config.rerankLabel}
      checked={useRerank}
      testIdPrefix={testIdPrefix}
      onChange={onUseRerankChange}
    />
  )

  return (
    <>
      <div className={config.controlsClassName}>
        <KbRetrievalModeControl
          config={config}
          mode={mode}
          testIdPrefix={testIdPrefix}
          onModeChange={onModeChange}
        />
        {config.rerankPosition === 'after-mode' && rerankControl}
        <KbRetrievalNumberControl
          label={config.searchKLabel}
          value={searchK}
          min={1}
          max={20}
          fallback={1}
          className={config.numberInputClassName}
          testId={getKbRetrievalTestId(testIdPrefix, 'search-k')}
          onChange={onSearchKChange}
        />
        {shouldShowFetchK && (
          <KbRetrievalNumberControl
            label={config.fetchKLabel}
            value={fetchK}
            min={searchK}
            max={50}
            fallback={searchK}
            className={config.numberInputClassName}
            testId={getKbRetrievalTestId(testIdPrefix, 'fetch-k')}
            onChange={onFetchKChange}
          />
        )}
        {config.rerankPosition === 'after-numbers' && rerankControl}
      </div>

      <KbRetrievalQueryRow
        config={config}
        query={query}
        loading={loading}
        variant={variant}
        testIdPrefix={testIdPrefix}
        onQueryChange={onQueryChange}
        onTest={onTest}
      />
    </>
  )
}
