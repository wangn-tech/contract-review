<template>
  <div>
    <el-row :gutter="16" class="stat-row">
      <el-col v-for="card in statCards" :key="card.label" :span="6">
        <el-card shadow="hover">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header>审阅/问答趋势（近 30 天）</template>
          <div ref="trendRef" class="chart" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header>风险点维度分布</template>
          <div ref="dimRef" class="chart" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])
import { dashboardApi } from '@/api/dashboard'
import type { DashboardOverview } from '@/types/api'

const overview = ref<DashboardOverview | null>(null)
const trendRef = ref<HTMLElement>()
const dimRef = ref<HTMLElement>()

const statCards = computed(() => [
  { label: '合同总数', value: overview.value?.total_contracts ?? 0, color: '#409eff' },
  { label: '已审阅合同', value: overview.value?.reviewed_contracts ?? 0, color: '#67c23a' },
  { label: '风险点总数', value: overview.value?.risk_points ?? 0, color: '#e6a23c' },
  { label: '今日审阅', value: overview.value?.today_reviews ?? 0, color: '#f56c6c' },
])

onMounted(async () => {
  overview.value = await dashboardApi.overview()
  const trends = await dashboardApi.trends('month')
  const dims = await dashboardApi.riskDims()
  renderTrend(trends)
  renderDims(dims)
})

function renderTrend(trends: { date: string; review_count: number; chat_count: number }[]) {
  const chart = echarts.init(trendRef.value!)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['审阅', '问答'] },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: trends.map((t) => t.date) },
    yAxis: { type: 'value' },
    series: [
      { name: '审阅', type: 'line', smooth: true, areaStyle: { opacity: 0.15 }, data: trends.map((t) => t.review_count) },
      { name: '问答', type: 'line', smooth: true, areaStyle: { opacity: 0.15 }, data: trends.map((t) => t.chat_count) },
    ],
  })
}

function renderDims(dims: { risk_dim: string; count: number }[]) {
  const chart = echarts.init(dimRef.value!)
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '65%'],
        data: dims.map((d) => ({ name: d.risk_dim, value: d.count })),
        label: { formatter: '{b}: {c}' },
      },
    ],
  })
}
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-label { color: #666; font-size: 13px; }
.stat-value { font-size: 28px; font-weight: 700; margin-top: 8px; }
.chart { height: 320px; }
</style>
