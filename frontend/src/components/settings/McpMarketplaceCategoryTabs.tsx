import React from 'react'

import type { McpMarketplaceCategory } from '../../api/client'
import type { McpMarketplaceSummaryView } from './mcpMarketplaceModel'

interface McpMarketplaceCategoryTabsProps {
  marketplaceSummary: McpMarketplaceSummaryView
  marketplaceCategories: McpMarketplaceCategory[]
  marketplaceCategoryId: string
  onMarketplaceCategoryChange: (categoryId: string) => void
}

export const McpMarketplaceCategoryTabs: React.FC<McpMarketplaceCategoryTabsProps> = ({
  marketplaceSummary,
  marketplaceCategories,
  marketplaceCategoryId,
  onMarketplaceCategoryChange,
}) => {
  const buttonClassName = (categoryId: string): string => (
    `rounded-md border px-2.5 py-1 text-left text-[11px] transition ${
      marketplaceCategoryId === categoryId
        ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
        : 'border-bg-border bg-bg-secondary/30 text-text-secondary hover:text-text-primary'
    }`
  )

  return (
    <div
      className="mt-3 flex flex-wrap gap-2"
      data-testid="settings-mcp-marketplace-categories"
    >
      <button
        type="button"
        onClick={() => onMarketplaceCategoryChange('all')}
        className={buttonClassName('all')}
        data-testid="settings-mcp-marketplace-category-all"
      >
        All {marketplaceSummary.total}
      </button>
      {marketplaceCategories.map((category) => (
        <button
          key={category.id}
          type="button"
          onClick={() => onMarketplaceCategoryChange(category.id)}
          className={buttonClassName(category.id)}
          data-testid={`settings-mcp-marketplace-category-${category.id}`}
        >
          {category.label} {category.healthy}/{category.total} healthy
          {category.requires_approval ? `, approval ${category.requires_approval}` : ''}
        </button>
      ))}
    </div>
  )
}
