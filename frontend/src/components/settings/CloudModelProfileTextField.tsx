import React from 'react'

import type { TranslationKey } from '../../i18n'

interface CloudModelProfileTextFieldProps {
  className?: string
  labelKey: TranslationKey
  placeholder: string
  testId: string
  value: string
  onChange: (value: string) => void
  t: (key: TranslationKey) => string
}

export const CloudModelProfileTextField: React.FC<CloudModelProfileTextFieldProps> = ({
  className,
  labelKey,
  placeholder,
  testId,
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
      className="input-base w-full text-sm"
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={placeholder}
    />
  </div>
)
