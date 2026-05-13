import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { DocumentStatsPanel } from './DocumentStatsPanel'

describe('DocumentStatsPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders document stats', () => {
    render(
      <DocumentStatsPanel
        stats={{
          status: 'ready',
          total_docs: 12,
          store_path: '/tmp/vector-store',
        }}
      />,
    )

    expect(screen.getByTestId('settings-documents-stats')).toBeInTheDocument()
    expect(screen.getByTestId('settings-documents-stats-status')).toHaveTextContent('ready')
    expect(screen.getByTestId('settings-documents-stats-total-docs')).toHaveTextContent('12')
    expect(screen.getByTestId('settings-documents-stats-store-path')).toHaveTextContent('/tmp/vector-store')
  })

  it('omits optional stat rows when values are absent', () => {
    render(<DocumentStatsPanel stats={{ status: 'empty' }} />)

    expect(screen.getByTestId('settings-documents-stats-status')).toHaveTextContent('empty')
    expect(screen.queryByTestId('settings-documents-stats-total-docs')).not.toBeInTheDocument()
    expect(screen.queryByTestId('settings-documents-stats-store-path')).not.toBeInTheDocument()
  })
})
