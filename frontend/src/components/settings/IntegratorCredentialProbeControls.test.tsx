import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { IntegratorCredentialProbeControls } from './IntegratorCredentialProbeControls'

describe('IntegratorCredentialProbeControls', () => {
  afterEach(() => {
    cleanup()
  })

  it('forwards external probe checkbox, timeout changes, and blur events', () => {
    const onExternalProbeEnabledChange = vi.fn()
    const onExternalProbeTimeoutSecondsChange = vi.fn()
    const onExternalProbeTimeoutBlur = vi.fn()

    render(
      <IntegratorCredentialProbeControls
        externalProbeEnabled
        externalProbeTimeoutSeconds={2.5}
        onExternalProbeEnabledChange={onExternalProbeEnabledChange}
        onExternalProbeTimeoutSecondsChange={onExternalProbeTimeoutSecondsChange}
        onExternalProbeTimeoutBlur={onExternalProbeTimeoutBlur}
      />,
    )

    const checkbox = screen.getByTestId('settings-integrator-external-probe-enabled')
    const timeout = screen.getByTestId('settings-integrator-external-probe-timeout')

    fireEvent.click(checkbox)
    expect(onExternalProbeEnabledChange).toHaveBeenCalledWith(false)

    fireEvent.change(timeout, { target: { value: '4.2' } })
    expect(onExternalProbeTimeoutSecondsChange).toHaveBeenCalledWith(4.2)

    fireEvent.blur(timeout)
    expect(onExternalProbeTimeoutBlur).toHaveBeenCalledTimes(1)
  })

  it('disables timeout input when external probing is disabled', () => {
    render(
      <IntegratorCredentialProbeControls
        externalProbeEnabled={false}
        externalProbeTimeoutSeconds={3}
        onExternalProbeEnabledChange={vi.fn()}
        onExternalProbeTimeoutSecondsChange={vi.fn()}
        onExternalProbeTimeoutBlur={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-integrator-external-probe-timeout')).toBeDisabled()
  })
})
