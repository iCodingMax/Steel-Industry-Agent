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

/**
 * 导出图表为 base64 图片（直接从页面渲染实例导出，100%还原显示效果）
 * @param options 导出配置
 */
function exportImage(options?: {
  type?: 'png' | 'jpeg' | 'svg'
  pixelRatio?: number
  backgroundColor?: string
}): string | null {
  if (!chartInstance) return null
  try {
    return chartInstance.getDataURL({
      type: options?.type || 'png',
      pixelRatio: options?.pixelRatio || 2,
      backgroundColor: options?.backgroundColor || '#fff',
    })
  } catch (e) {
    console.error('图表导出失败:', e)
    return null
  }
}

/** 获取 echarts 实例 */
function getInstance(): echarts.ECharts | null {
  return chartInstance
}

/** 暴露方法给父组件调用 */
defineExpose({
  exportImage,
  getInstance,
  resizeChart,
})

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
