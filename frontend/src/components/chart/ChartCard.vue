<template>
  <div class="chart-card">
    <div v-if="title" class="chart-header">
      <span class="chart-title">{{ title }}</span>
      <slot name="actions"></slot>
    </div>
    <div ref="chartRef" class="chart-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{
  title?: string
  option: any
}>()

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

function initChart() {
  if (!chartRef.value) return
  chartInstance = echarts.init(chartRef.value)
  if (props.option) {
    chartInstance.setOption(props.option)
  }
}

function resizeChart() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

watch(
  () => props.option,
  (newOption) => {
    if (chartInstance && newOption) {
      chartInstance.setOption(newOption)
      // 选项更新后立即调整大小
      nextTick(() => resizeChart())
    }
  },
  { deep: true }
)

onMounted(() => {
  initChart()
  
  // 使用 ResizeObserver 监听容器大小变化
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => {
      resizeChart()
    })
    resizeObserver.observe(chartRef.value)
  }
  
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style lang="scss" scoped>
.chart-card {
  background: transparent;
  border-radius: 0;
  box-shadow: none;
  padding: 0;
  width: 100%;
  height: 100%;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: $text-primary;
}

.chart-container {
  width: 100%;
  height: 100%;
  min-height: 200px;
}
</style>
