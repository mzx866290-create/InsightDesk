import React from 'react'

import type { TranslationKey } from '../../i18n'

interface CloudModelProfileTemperatureFieldProps {
  temperature: number
  onTemperatureChange: (value: number) => void
  t: (key: TranslationKey) => string
}

export const CloudModelProfileTemperatureField: React.FC<CloudModelProfileTemperatureFieldProps> = ({
  temperature,
  onTemperatureChange,
  t,
}) => (
  <div>
    <label className="mb-1 block text-[11px] uppercase tracking-wide text-text-secondary">
      {t('settings.cloud.temperature')}
    </label>
    <div className="rounded-lg border border-bg-border bg-bg-primary/60 px-3 py-2 text-sm text-text-primary">
      <div className="mb-2 flex items-center justify-between">
        <span>{t('settings.cloud.currentValue')}</span>
        <span>{temperature.toFixed(1)}</span>
      </div>
      <input
        type="range"
        min="0"
        max="1"
        step="0.1"
        value={temperature}
        onChange={(event) => onTemperatureChange(parseFloat(event.target.value))}
        className="w-full accent-accent-blue"
      />
    </div>
  </div>
)
