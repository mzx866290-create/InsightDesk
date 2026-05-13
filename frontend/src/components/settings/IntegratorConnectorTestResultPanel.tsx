import type { IntegratorConnectorTestResult } from '../../api/client'

export interface IntegratorConnectorTestResultPanelProps {
  testResult: IntegratorConnectorTestResult
}

export const IntegratorConnectorTestResultPanel: React.FC<IntegratorConnectorTestResultPanelProps> = ({
  testResult,
}) => (
  <div
    className="rounded-lg border border-bg-border bg-bg-secondary/40 p-3"
    data-testid="settings-integrator-test-result"
  >
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-xs font-medium text-text-primary">Dry-run test</span>
      <span className={`rounded-full px-2 py-0.5 text-[11px] ${
        testResult.ok ? 'bg-accent-green/15 text-accent-green' : 'bg-accent-red/15 text-accent-red'
      }`}>
        {testResult.status}
      </span>
    </div>
    <div className="mt-2 space-y-1">
      {testResult.checks.map((check) => (
        <div
          key={check.name}
          className="flex items-start gap-2 text-xs text-text-secondary"
        >
          <span className={check.ok ? 'text-accent-green' : 'text-accent-red'}>
            {check.ok ? 'OK' : 'FAIL'}
          </span>
          <span>{check.message}</span>
        </div>
      ))}
    </div>
    <p className="mt-2 text-[11px] text-text-secondary">
      No outbound request was sent.
    </p>
  </div>
)
