import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PromptDashboardTemplateFields } from './PromptDashboardTemplateFields'
import type { PromptDashboardTemplateFieldsProps } from './PromptDashboardTemplateFields'

const enabledProps: PromptDashboardTemplateFieldsProps = {
  enabled: true,
  titleHint: 'Revenue dashboard',
  audienceTone: 'Executive summary',
  focusMetrics: 'MRR\nChurn',
  sectionOrder: 'summary\nmetrics\ncharts',
  preferredCharts: ['bar'],
  onEnabledChange: vi.fn(),
  onTitleHintChange: vi.fn(),
  onAudienceToneChange: vi.fn(),
  onFocusMetricsChange: vi.fn(),
  onSectionOrderChange: vi.fn(),
  onToggleChart: vi.fn(),
}

function renderFields(overrides: Partial<PromptDashboardTemplateFieldsProps> = {}) {
  const props = {
    ...enabledProps,
    onEnabledChange: vi.fn(),
    onTitleHintChange: vi.fn(),
    onAudienceToneChange: vi.fn(),
    onFocusMetricsChange: vi.fn(),
    onSectionOrderChange: vi.fn(),
    onToggleChart: vi.fn(),
    ...overrides,
  }

  return {
    props,
    ...render(<PromptDashboardTemplateFields {...props} />),
  }
}

describe('PromptDashboardTemplateFields', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders controlled field values and forwards edits', () => {
    const { props } = renderFields()

    const titleHint = screen.getByTestId('settings-prompt-dashboard-title-hint')
    const audienceTone = screen.getByTestId('settings-prompt-dashboard-audience-tone')
    const focusMetrics = screen.getByTestId('settings-prompt-dashboard-focus-metrics')
    const sectionOrder = screen.getByTestId('settings-prompt-dashboard-section-order')

    expect(titleHint).toHaveValue('Revenue dashboard')
    expect(audienceTone).toHaveValue('Executive summary')
    expect(focusMetrics).toHaveValue('MRR\nChurn')
    expect(sectionOrder).toHaveValue('summary\nmetrics\ncharts')

    fireEvent.change(titleHint, { target: { value: 'New dashboard' } })
    fireEvent.change(audienceTone, { target: { value: 'Board concise' } })
    fireEvent.change(focusMetrics, { target: { value: 'ARR' } })
    fireEvent.change(sectionOrder, { target: { value: 'warnings' } })
    fireEvent.click(screen.getByTestId('settings-prompt-dashboard-chart-line'))

    expect(props.onTitleHintChange).toHaveBeenCalledWith('New dashboard')
    expect(props.onAudienceToneChange).toHaveBeenCalledWith('Board concise')
    expect(props.onFocusMetricsChange).toHaveBeenCalledWith('ARR')
    expect(props.onSectionOrderChange).toHaveBeenCalledWith('warnings')
    expect(props.onToggleChart).toHaveBeenCalledWith('line')
  })

  it('keeps the enable toggle active while disabling dashboard fields', () => {
    const { props } = renderFields({ enabled: false })

    const toggle = screen.getByTestId('settings-prompt-dashboard-enabled')
    fireEvent.click(toggle)

    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(props.onEnabledChange).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('settings-prompt-dashboard-title-hint')).toBeDisabled()
    expect(screen.getByTestId('settings-prompt-dashboard-audience-tone')).toBeDisabled()
    expect(screen.getByTestId('settings-prompt-dashboard-focus-metrics')).toBeDisabled()
    expect(screen.getByTestId('settings-prompt-dashboard-section-order')).toBeDisabled()
    expect(screen.getByTestId('settings-prompt-dashboard-chart-bar')).toBeDisabled()
    expect(screen.getByTestId('settings-prompt-dashboard-chart-line')).toBeDisabled()
    expect(screen.getByTestId('settings-prompt-dashboard-chart-pie')).toBeDisabled()
  })
})
