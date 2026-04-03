import React, { useRef } from 'react'
import ReactECharts from 'echarts-for-react'

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

interface EChartsRendererProps {
  chartData: ChartData
  height?: number
}

function buildBarOption(chartData: ChartData) {
  return {
    tooltip: { trigger: 'axis' },
    legend: chartData.datasets.length > 1 ? { data: chartData.datasets.map(d => d.label) } : undefined,
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.labels,
      axisLabel: { color: '#9ca3af', fontSize: 11 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', fontSize: 11 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: chartData.datasets.map((ds) => ({
      name: ds.label,
      type: 'bar',
      data: ds.data,
      barMaxWidth: 48,
    })),
  }
}

function buildLineOption(chartData: ChartData) {
  return {
    tooltip: { trigger: 'axis' },
    legend: chartData.datasets.length > 1 ? { data: chartData.datasets.map(d => d.label) } : undefined,
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      data: chartData.labels,
      axisLabel: { color: '#9ca3af', fontSize: 11 },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#9ca3af', fontSize: 11 },
      splitLine: { lineStyle: { color: '#1f2937' } },
    },
    series: chartData.datasets.map((ds) => ({
      name: ds.label,
      type: 'line',
      data: ds.data,
      smooth: true,
    })),
  }
}

function buildPieOption(chartData: ChartData) {
  const ds = chartData.datasets[0]
  const pieData = chartData.labels.map((label, i) => ({
    name: label,
    value: ds?.data[i] ?? 0,
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', left: 'left', textStyle: { color: '#9ca3af', fontSize: 11 } },
    series: [
      {
        name: ds?.label ?? '数据',
        type: 'pie',
        radius: '60%',
        data: pieData,
        emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } },
        label: { color: '#d1d5db', fontSize: 11 },
      },
    ],
  }
}

export const EChartsRenderer: React.FC<EChartsRendererProps> = ({ chartData, height = 280 }) => {
  const chartRef = useRef(null)

  const option = chartData.type === 'pie'
    ? buildPieOption(chartData)
    : chartData.type === 'line'
    ? buildLineOption(chartData)
    : buildBarOption(chartData)

  return (
    <ReactECharts
      ref={chartRef}
      option={option}
      style={{ height, width: '100%' }}
      theme="dark"
      opts={{ renderer: 'svg' }}
    />
  )
}
