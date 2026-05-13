import React from 'react'

import type { TranslationKey } from '../../i18n'

interface SsoConfigTextFieldProps {
  className?: string
  inputClassName?: string
  labelKey: TranslationKey
  max?: number
  min?: number
  placeholder?: string
  testId: string
  type?: React.HTMLInputTypeAttribute
  value: number | string
  onChange: (value: string) => void
  t: (key: TranslationKey) => string
}

export const SsoConfigTextField: React.FC<SsoConfigTextFieldProps> = ({
  className,
  inputClassName = 'input-base w-full text-sm',
  labelKey,
  max,
  min,
  placeholder,
  testId,
  type = 'text',
  value,
  onChange,
  t,
}) => (
  <div className={className}>
    <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
      {t(labelKey)}
    </label>
    <input
      data-testid={testId}
      className={inputClassName}
      type={type}
      min={min}
      max={max}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
    />
  </div>
)
