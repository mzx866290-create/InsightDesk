import { clampKbRetrievalNumber } from './KbRetrievalControlsModel'

function getClampedKbRetrievalInput(rawValue: string, fallback: number, min: number, max: number) {
  return clampKbRetrievalNumber(Number(rawValue) || fallback, min, max)
}

interface KbRetrievalNumberControlProps {
  label: string
  value: number
  min: number
  max: number
  fallback: number
  className: string
  testId?: string
  onChange: (value: number) => void
}

export function KbRetrievalNumberControl({
  label,
  value,
  min,
  max,
  fallback,
  className,
  testId,
  onChange,
}: KbRetrievalNumberControlProps) {
  return (
    <label className="flex items-center gap-1.5 text-text-secondary">
      {label}
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(getClampedKbRetrievalInput(event.target.value, fallback, min, max))}
        className={className}
        data-testid={testId}
      />
    </label>
  )
}
