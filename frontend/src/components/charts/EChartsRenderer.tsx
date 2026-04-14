import React, { Suspense } from 'react'

import type {
  ChartData,
  ChartDataset,
  EChartsRendererProps,
} from './EChartsRendererInner'

const EChartsRendererInner = React.lazy(() => import('./EChartsRendererInner'))

export type { ChartData, ChartDataset }

export const EChartsRenderer: React.FC<EChartsRendererProps> = (props) => {
  return (
    <Suspense
      fallback={
        <div
          className="flex w-full items-center justify-center rounded-xl border border-bg-border bg-bg-primary/30 text-xs text-text-secondary/70"
          style={{ height: props.height ?? 280 }}
        >
          图表加载中...
        </div>
      }
    >
      <EChartsRendererInner {...props} />
    </Suspense>
  )
}
