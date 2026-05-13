import React from 'react'

import type {
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeResponse,
} from '../../api/client'
import {
  formatFieldList,
  safeProbeEntries,
} from './integratorCredentialsModel'

export interface IntegratorCredentialResultsProps {
  rotationResult: IntegratorConnectorCredentialsRotationResponse | null
  probeResult: IntegratorConnectorProbeResponse | null
}

export const IntegratorCredentialResults: React.FC<IntegratorCredentialResultsProps> = ({
  rotationResult,
  probeResult,
}) => (
  <>
    {rotationResult && (
      <div
        className="bg-bg-secondary/40 px-3 py-2 text-xs text-text-secondary"
        data-testid="settings-integrator-rotation-result"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-medium text-text-primary">Rotation {rotationResult.status}</span>
          <span>{rotationResult.summary.rotated_count} rotated / {rotationResult.summary.preserved_count} preserved</span>
        </div>
        <div className="mt-2 grid gap-1 text-[11px] sm:grid-cols-2">
          <span>
            Rotated: <b className="text-text-primary">{formatFieldList(rotationResult.rotated_fields)}</b>
          </span>
          <span>
            Preserved: <b className="text-text-primary">{formatFieldList(rotationResult.preserved_fields)}</b>
          </span>
        </div>
        <p className="mt-2 text-[11px] text-text-secondary">
          Connector settings returned redacted; sensitive input was cleared.
        </p>
      </div>
    )}

    {probeResult && (
      <div
        className="bg-bg-secondary/40 px-3 py-2 text-xs text-text-secondary"
        data-testid="settings-integrator-probe-result"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="font-medium text-text-primary">
            {probeResult.probe.mode === 'external' ? 'External probe' : 'Static dry-run probe'}
          </span>
          <span className={probeResult.ok ? 'text-accent-green' : 'text-accent-red'}>
            {probeResult.status}
          </span>
        </div>
        <div className="mt-2 grid gap-1 text-[11px] sm:grid-cols-2">
          <span>Mode: <b className="text-text-primary" data-testid="settings-integrator-probe-mode">{probeResult.probe.mode}</b></span>
          <span>
            Outbound request:{' '}
            <b className="text-text-primary" data-testid="settings-integrator-probe-outbound">
              {probeResult.probe.outbound_request_sent ? 'sent' : 'not sent'}
            </b>
          </span>
          <span>
            Timeout:{' '}
            <b className="text-text-primary" data-testid="settings-integrator-probe-timeout">
              {probeResult.probe.timeout_seconds ?? '-'}s
            </b>
          </span>
          <span>Checks: <b className="text-text-primary">{probeResult.summary.check_count}</b></span>
          <span>Failures: <b className="text-text-primary">{probeResult.summary.failed_count}</b></span>
        </div>
        {safeProbeEntries(probeResult.probe.endpoint).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5" data-testid="settings-integrator-probe-endpoint">
            {safeProbeEntries(probeResult.probe.endpoint).map(([key, value]) => (
              <span key={key} className="rounded-md bg-bg-hover px-2 py-1 text-[11px] text-text-secondary">
                {key}: {value}
              </span>
            ))}
          </div>
        )}
        {safeProbeEntries(probeResult.probe.response).length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5" data-testid="settings-integrator-probe-response">
            {safeProbeEntries(probeResult.probe.response).map(([key, value]) => (
              <span key={key} className="rounded-md bg-bg-hover px-2 py-1 text-[11px] text-text-secondary">
                {key}: {value}
              </span>
            ))}
          </div>
        )}
        <div className="mt-2 space-y-1">
          {probeResult.checks.map((check) => (
            <div
              key={check.name}
              className="flex items-start gap-2 text-[11px] text-text-secondary"
            >
              <span className={check.ok ? 'text-accent-green' : 'text-accent-red'}>
                {check.ok ? 'OK' : 'FAIL'}
              </span>
              <span>{check.message}</span>
            </div>
          ))}
        </div>
      </div>
    )}
  </>
)
