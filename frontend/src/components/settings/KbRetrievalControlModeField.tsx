import {
  getKbRetrievalTestId,
  type KbRetrievalControlsConfig,
  type KbRetrievalMode,
} from './KbRetrievalControlsModel'

interface KbRetrievalModeControlProps {
  config: KbRetrievalControlsConfig
  mode: KbRetrievalMode
  testIdPrefix?: string
  onModeChange: (value: KbRetrievalMode) => void
}

export function KbRetrievalModeControl({
  config,
  mode,
  testIdPrefix,
  onModeChange,
}: KbRetrievalModeControlProps) {
  return (
    <label className="flex items-center gap-1.5 text-text-secondary">
      {config.modeLabel}
      <select
        data-testid={getKbRetrievalTestId(testIdPrefix, 'mode')}
        value={mode}
        onChange={(event) => onModeChange(event.target.value as KbRetrievalMode)}
        className={config.selectClassName}
      >
        <option value="semantic">{config.modeOptions.semantic}</option>
        <option value="keyword">{config.modeOptions.keyword}</option>
        <option value="hybrid">{config.modeOptions.hybrid}</option>
      </select>
    </label>
  )
}
