import React, { useMemo, useRef } from 'react'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { useResolvedTheme } from '../../hooks/useResolvedTheme'

export interface ChartDataset {
  label: string
  data: number[]
}

export interface ChartData {
  type: 'bar' | 'pie' | 'line'
  title?: string
  labels: string[]
  datasets: ChartDataset[]
}

export interface EChartsRendererProps {
  chartData: ChartData
  height?: number
}

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  SVGRenderer,
])

interface ChartThemeTokens {
  axisLabel: string
  axisLine: string
  splitLine: string
  legend: string
  label: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
}

function getChartThemeTokens(theme: 'dark' | 'light'): ChartThemeTokens {
  if (theme === 'light') {
    return {
      axisLabel: '#475569',
      axisLine: '#cbd5e1',
      splitLine: '#e2e8f0',
      legend: '#334155',
      label: '#0f172a',
      tooltipBg: 'rgba(255,255,255,0.96)',
      tooltipBorder: '#cbd5e1',
      tooltipText: '#0f172a',
    }
  }

  return {
    axisLabel: '#9ca3af',
    axisLine: '#374151',
    splitLine: '#1f2937',
    legend: '#9ca3af',
    label: '#d1d5db',
    tooltipBg: 'rgba(17,24,39,0.94)',
    tooltipBorder: '#374151',
    tooltipText: '#f3f4f6',
  }
}

function buildBarOption(chartData: ChartData, theme: ChartThemeTokens) {
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.tooltipBg,
      borderColor: theme.tooltipBorder,
      textStyle: { color: theme.tooltipText },
    },
    legend:
      chartData.datasets.length > 1
        ? {
            data: chartData.datasets.map((d) => d.label),
            textStyle: { color: theme.legend, fontSize: 11 },
          }
        : undefined,
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.labels,
      axisLabel: { color: theme.axisLabel, fontSize: 11 },
      axisLine: { lineStyle: { color: theme.axisLine } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: theme.axisLabel, fontSize: 11 },
      splitLine: { lineStyle: { color: theme.splitLine } },
    },
    series: chartData.datasets.map((ds) => ({
      name: ds.label,
      type: 'bar',
      data: ds.data,
      barMaxWidth: 48,
    })),
  }
}

function buildLineOption(chartData: ChartData, theme: ChartThemeTokens) {
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.tooltipBg,
      borderColor: theme.tooltipBorder,
      textStyle: { color: theme.tooltipText },
    },
    legend:
      chartData.datasets.length > 1
        ? {
            data: chartData.datasets.map((d) => d.label),
            textStyle: { color: theme.legend, fontSize: 11 },
          }
        : undefined,
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.labels,
      axisLabel: { color: theme.axisLabel, fontSize: 11 },
      axisLine: { lineStyle: { color: theme.axisLine } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: theme.axisLabel, fontSize: 11 },
      splitLine: { lineStyle: { color: theme.splitLine } },
    },
    series: chartData.datasets.map((ds) => ({
      name: ds.label,
      type: 'line',
      data: ds.data,
      smooth: true,
    })),
  }
}

function buildPieOption(chartData: ChartData, theme: ChartThemeTokens) {
  const ds = chartData.datasets[0]
  const pieData = chartData.labels.map((label, i) => ({
    name: label,
    value: ds?.data[i] ?? 0,
  }))
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{a} <br/>{b}: {c} ({d}%)',
      backgroundColor: theme.tooltipBg,
      borderColor: theme.tooltipBorder,
      textStyle: { color: theme.tooltipText },
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      textStyle: { color: theme.legend, fontSize: 11 },
    },
    series: [
      {
        name: ds?.label ?? '数据',
        type: 'pie',
        radius: '60%',
        data: pieData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0,0,0,0.5)',
          },
        },
        label: { color: theme.label, fontSize: 11 },
      },
    ],
  }
}

const EChartsRendererInner: React.FC<EChartsRendererProps> = ({ chartData, height = 280 }) => {
  const chartRef = useRef(null)
  const { resolvedTheme } = useResolvedTheme()
  const chartTheme = useMemo(() => getChartThemeTokens(resolvedTheme), [resolvedTheme])

  const option = useMemo(
    () =>
    chartData.type === 'pie'
      ? buildPieOption(chartData, chartTheme)
      : chartData.type === 'line'
        ? buildLineOption(chartData, chartTheme)
        : buildBarOption(chartData, chartTheme),
    [chartData, chartTheme],
  )

  return (
    <ReactEChartsCore
      ref={chartRef}
      echarts={echarts}
      option={option}
      style={{ height, width: '100%' }}
      theme={resolvedTheme === 'dark' ? 'dark' : undefined}
      opts={{ renderer: 'svg' }}
    />
  )
}

export default EChartsRendererInner
