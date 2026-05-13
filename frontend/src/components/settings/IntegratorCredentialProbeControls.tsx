import React from 'react'

import {
  MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS,
  MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS,
} from './integratorCredentialsModel'

export interface IntegratorCredentialProbeControlsProps {
  externalProbeEnabled: boolean
  externalProbeTimeoutSeconds: number
  onExternalProbeEnabledChange: (enabled: boolean) => void
  onExternalProbeTimeoutSecondsChange: (value: number) => void
  onExternalProbeTimeoutBlur: () => void
}

export const IntegratorCredentialProbeControls: React.FC<IntegratorCredentialProbeControlsProps> = ({
  externalProbeEnabled,
  externalProbeTimeoutSeconds,
  onExternalProbeEnabledChange,
  onExternalProbeTimeoutSecondsChange,
  onExternalProbeTimeoutBlur,
}) => (
  <div
    className="grid gap-3 rounded-lg border border-bg-border bg-bg-secondary/30 px-3 py-2 sm:grid-cols-[minmax(0,1fr)_8rem]"
    data-testid="settings-integrator-external-probe-controls"
  >
    <label className="flex items-start gap-2 text-xs text-text-secondary">
      <input
        type="checkbox"
        className="mt-0.5"
        checked={externalProbeEnabled}
        onChange={(event) => onExternalProbeEnabledChange(event.target.checked)}
        data-testid="settings-integrator-external-probe-enabled"
      />
      <span>
        <span className="block font-medium text-text-primary">External probe opt-in</span>
        <span className="mt-1 block text-[11px] leading-4">
          Sends one outbound webhook request. Leave off for the default static dry-run.
        </span>
      </span>
    </label>
    <label className="space-y-1 text-xs text-text-secondary">
      Timeout seconds
      <input
        type="number"
        min={MIN_EXTERNAL_PROBE_TIMEOUT_SECONDS}
        max={MAX_EXTERNAL_PROBE_TIMEOUT_SECONDS}
        step={0.1}
        className="input-base h-9 w-full"
        value={externalProbeTimeoutSeconds}
        disabled={!externalProbeEnabled}
        onChange={(event) => onExternalProbeTimeoutSecondsChange(Number(event.target.value))}
        onBlur={onExternalProbeTimeoutBlur}
        data-testid="settings-integrator-external-probe-timeout"
      />
    </label>
  </div>
)
