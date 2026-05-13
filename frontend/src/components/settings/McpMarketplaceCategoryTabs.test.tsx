import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { McpMarketplaceCategory } from '../../api/client'
import type { McpMarketplaceSummaryView } from './mcpMarketplaceModel'
import { McpMarketplaceCategoryTabs } from './McpMarketplaceCategoryTabs'

const marketplaceSummary: McpMarketplaceSummaryView = {
  total: 3,
  enabled: 2,
  healthy: 2,
  approval: 1,
  builtin: 2,
  custom: 1,
  categories: 2,
}

const marketplaceCategories: McpMarketplaceCategory[] = [
  {
    id: 'developer-tools',
    label: 'Developer Tools',
    total: 2,
    enabled: 2,
    healthy: 1,
    requires_approval: 1,
    connectors: ['filesystem', 'github'],
  },
  {
    id: 'search',
    label: 'Search',
    total: 1,
    enabled: 0,
    healthy: 1,
    requires_approval: 0,
    connectors: ['tavily'],
  },
]

describe('McpMarketplaceCategoryTabs', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders all and category buttons with existing labels', () => {
    render(
      <McpMarketplaceCategoryTabs
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={marketplaceCategories}
        marketplaceCategoryId="all"
        onMarketplaceCategoryChange={vi.fn()}
      />,
    )

    expect(screen.getByTestId('settings-mcp-marketplace-categories')).toBeInTheDocument()
    expect(screen.getByTestId('settings-mcp-marketplace-category-all')).toHaveTextContent('All 3')
    expect(screen.getByTestId('settings-mcp-marketplace-category-developer-tools')).toHaveTextContent(
      'Developer Tools 1/2 healthy, approval 1',
    )
    expect(screen.getByTestId('settings-mcp-marketplace-category-search')).toHaveTextContent(
      'Search 1/1 healthy',
    )
  })

  it('forwards category click callbacks without changing ids', () => {
    const onMarketplaceCategoryChange = vi.fn()

    render(
      <McpMarketplaceCategoryTabs
        marketplaceSummary={marketplaceSummary}
        marketplaceCategories={marketplaceCategories}
        marketplaceCategoryId="developer-tools"
        onMarketplaceCategoryChange={onMarketplaceCategoryChange}
      />,
    )

    fireEvent.click(screen.getByTestId('settings-mcp-marketplace-category-all'))
    fireEvent.click(screen.getByTestId('settings-mcp-marketplace-category-search'))

    expect(onMarketplaceCategoryChange).toHaveBeenNthCalledWith(1, 'all')
    expect(onMarketplaceCategoryChange).toHaveBeenNthCalledWith(2, 'search')
  })
})
