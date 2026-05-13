import { getKbRetrievalTestId } from './KbRetrievalControlsModel'

interface KbRetrievalRerankControlProps {
  label: string
  checked: boolean
  testIdPrefix?: string
  onChange: (value: boolean) => void
}

export function KbRetrievalRerankControl({
  label,
  checked,
  testIdPrefix,
  onChange,
}: KbRetrievalRerankControlProps) {
  return (
    <label className="flex items-center gap-1.5 text-text-secondary">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="accent-accent-blue"
        data-testid={getKbRetrievalTestId(testIdPrefix, 'rerank')}
      />
      {label}
    </label>
  )
}
