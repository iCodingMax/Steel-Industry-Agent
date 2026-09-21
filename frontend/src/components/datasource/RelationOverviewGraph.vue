<template>
  <div class="relation-overview-wrap">
    <!-- 顶栏：宏观体检统计 + 提示 -->
    <div class="overview-toolbar">
      <span class="stat-item">
        表 <b class="num">{{ overviewStats.tables }}</b> 张
        <span class="sub">（孤立表 {{ overviewStats.isolated }}）</span>
      </span>
      <el-divider direction="vertical" />
      <span class="stat-item">已生效 <b class="num active">{{ overviewStats.active }}</b></span>
      <span class="stat-item">待确认 <b class="num inactive">{{ overviewStats.inactive }}</b></span>
      <span class="stat-item">已忽略 <b class="num ignored">{{ overviewStats.ignored }}</b></span>
      <el-tag v-if="overviewStats.isolated > 0" size="small" type="danger" effect="plain" class="isolated-tip">
        {{ overviewStats.isolated }} 张孤立表未建立任何关系
      </el-tag>
      <span class="toolbar-tip">只读浏览 · 拖拽移动 · 滚轮缩放 · 悬停节点聚焦邻域</span>
      <el-button size="small" @click="handleRerender">
        <el-icon><Refresh /></el-icon>
        重新布局
      </el-button>
    </div>

    <div class="chart-body">
      <div ref="chartRef" class="echarts-container"></div>

      <!-- 三来源视觉编码图例（与画布模式一致） -->
      <div class="legend-panel">
        <div class="legend-title">关系图例</div>
        <div class="legend-item"><span class="legend-line solid blue"></span>外键（已生效）</div>
        <div class="legend-item"><span class="legend-line solid green"></span>人工确认（已生效）</div>
        <div class="legend-item"><span class="legend-line dashed gray"></span>同名推荐（待确认）</div>
        <div class="legend-item"><span class="legend-line dotted light"></span>已忽略</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import { getRelationGraph } from '@/api/datasource'

// relationGraph：父组件下发的聚合数据（三视图共享一份，切换零请求）；缺省时组件自行拉取
const props = defineProps<{
  dsId: number
  relationGraph?: { nodes: any[]; edges: any[]; stats?: any } | null
}>()

// ===================== 状态定义 =====================
const chartRef = ref<HTMLDivElement>()
const overviewStats = ref({ tables: 0, isolated: 0, active: 0, inactive: 0, ignored: 0 })

let chartInstance: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null
let graphData: { nodes: any[]; edges: any[]; stats?: any } | null = null

// ===================== 工序域分类（方案 4.4.2：按工序域着色） =====================
const DOMAIN_RULES: Array<{ domain: string; color: string; pattern: RegExp }> = [
  { domain: '原料烧结', color: '#8B5CF6', pattern: /(raw|material|sinter|ore|fuel|原料|烧结|焦|矿)/i },
  { domain: '炼铁', color: '#EA580C', pattern: /(iron|^bf|blast|hot.?metal|炼铁|高炉|铁水|烧结矿)/i },
  { domain: '炼钢', color: '#2F54EB', pattern: /(steel|bof|convert|^ld_|refin|^lf_|精炼|炼钢|转炉|钢水|连铸|cast)/i },
  { domain: '轧钢', color: '#0D9488', pattern: /(roll|mill|^hr_|^cr_|轧|热轧|冷轧|轧机|线材|棒材|板材|卷)/i },
  { domain: '检化验', color: '#D97706', pattern: /(quality|^qc|chem|lab|analy|检验|化验|性能|成分|sample)/i },
  { domain: '能源设备', color: '#64748B', pattern: /(energy|power|device|equip|spare|能耗|设备|备件|能源|计量)/i },
  { domain: '系统通用', color: '#94A3B8', pattern: /(sys|user|log|config|dict|系统|日志|用户|字典|权限)/i },
]

/** 按表名 + 表注释匹配工序域，未命中归入“其他” */
function classifyDomain(node: any): { name: string; index: number } {
  const text = `${node.id || ''} ${node.label || ''} ${node.comment || node.description || ''}`
  for (let i = 0; i < DOMAIN_RULES.length; i++) {
    if (DOMAIN_RULES[i].pattern.test(text)) return { name: DOMAIN_RULES[i].domain, index: i }
  }
  return { name: '其他', index: DOMAIN_RULES.length }
}

// ===================== 三来源视觉编码（与画布模式一致，方案 4.4.4） =====================
const EDGE_STYLE: Record<string, { color: string; type: 'solid' | 'dashed' | 'dotted' }> = {
  foreign_key_active: { color: '#2F54EB', type: 'solid' },
  manual_active: { color: '#52C41A', type: 'solid' },
  auto_guess_inactive: { color: '#BFBFBF', type: 'dashed' },
  auto_guess_ignored: { color: '#D9D9D9', type: 'dotted' },
}

function edgeStyleKey(source: string, status: string): string {
  if (status === 'ignored') return 'auto_guess_ignored'
  if (status === 'active') return source === 'manual' ? 'manual_active' : 'foreign_key_active'
  return 'auto_guess_inactive'
}

// ===================== 工具函数 =====================
const decodePort = (pid: string) => (pid && pid.startsWith('col_') ? pid.slice(4) : pid || '')

const sourceText = (s: string) => ({ foreign_key: '外键', manual: '人工', auto_guess: '同名推荐' }[s] || s)
const statusText = (s: string) => ({ active: '已生效', inactive: '待确认', ignored: '已忽略' }[s] || s)

// ===================== 数据加载与图构建 =====================
async function loadGraphData() {
  // 父组件下发优先（三视图共享一份聚合数据，切换零请求）
  if (props.relationGraph) {
    graphData = props.relationGraph
    return
  }
  const res: any = await getRelationGraph(props.dsId)
  if (res.code === 0 && res.data) {
    graphData = { nodes: res.data.nodes || [], edges: res.data.edges || [], stats: res.data.stats }
  }
}

/** 构建 ECharts 力导向图 option（只读宏观体检，方案 4.4.2） */
function buildOption() {
  if (!graphData) return null
  const nodes: any[] = graphData.nodes
  const edges: any[] = graphData.edges

  // 度数统计（孤立表体检依据：度数为 0 的表）
  const degreeMap: Record<string, number> = {}
  for (const e of edges) {
    degreeMap[e.source] = (degreeMap[e.source] || 0) + 1
    degreeMap[e.target] = (degreeMap[e.target] || 0) + 1
  }

  // 工序域分类 + 节点尺寸（度数映射 14~34）
  const categories = DOMAIN_RULES.map((d) => ({ name: d.domain, itemStyle: { color: d.color } }))
  categories.push({ name: '其他', itemStyle: { color: '#CBD5E1' } })

  const chartNodes = nodes.map((n) => {
    const domain = classifyDomain(n)
    const degree = degreeMap[n.id] || 0
    return {
      id: n.id,
      name: n.label || n.id,
      category: domain.index,
      symbolSize: Math.min(14 + degree * 4, 34),
      value: degree,
      // 悬停 tooltip 数据
      raw: {
        tableName: n.id,
        comment: n.comment || n.description || '',
        columnCount: (n.columns || []).length,
        degree,
        domain: domain.name,
      },
    }
  })

  const chartEdges = edges.map((e) => {
    const key = edgeStyleKey(e.source_type || e.source, e.status)
    const style = EDGE_STYLE[key]
    return {
      source: e.source,
      target: e.target,
      lineStyle: { color: style.color, width: 1.5, type: style.type, curveness: 0.15 },
      // tooltip 数据
      raw: {
        id: e.id,
        left: `${e.source}.${decodePort(e.source_port || '')}`,
        right: `${e.target}.${decodePort(e.target_port || '')}`,
        source: sourceText(e.source_type || e.source),
        status: statusText(e.status),
        cardinality: e.cardinality || '',
        probeFactor: e.probe && typeof e.probe === 'object' ? e.probe.factor : null,
      },
    }
  })

  // 统计回填（顶栏体检数字）
  const s = graphData.stats || {}
  overviewStats.value = {
    tables: nodes.length,
    isolated: nodes.filter((n) => !degreeMap[n.id]).length,
    active: s.active ?? edges.filter((e) => e.status === 'active').length,
    inactive: s.inactive ?? edges.filter((e) => e.status === 'inactive').length,
    ignored: s.ignored ?? edges.filter((e) => e.status === 'ignored').length,
  }

  return {
    tooltip: {
      confine: true,
      formatter: (params: any) => {
        // 节点悬停：表名/注释/字段数/度数/工序域
        if (params.dataType === 'node') {
          const r = params.data.raw
          if (!r) return ''
          const lines = [
            `<b style="font-family:monospace">${r.tableName}</b>`,
            r.comment ? `<span style="color:#94a3b8">${r.comment}</span>` : '',
            `字段 ${r.columnCount} · 关系 ${r.degree} 条 · ${r.domain}`,
          ]
          return lines.filter(Boolean).join('<br/>')
        }
        // 边悬停：关系四元组 + 来源/状态/基数/探测放大
        const r = params.data?.raw
        if (!r) return ''
        const probe =
          r.probeFactor !== null && r.probeFactor !== undefined
            ? ` · 放大 ${Math.round(r.probeFactor * 10) / 10}x${r.probeFactor > 1.5 ? ' ⚠' : ''}`
            : ''
        return [
          `<span style="font-family:monospace">${r.left} ↔ ${r.right}</span>`,
          `${r.source} · ${r.status} · 基数 ${r.cardinality || '-'}${probe}`,
        ].join('<br/>')
      },
    },
    legend: [
      {
        data: categories.map((c) => c.name),
        orient: 'vertical',
        right: 12,
        top: 12,
        icon: 'circle',
        itemWidth: 10,
        itemHeight: 10,
        textStyle: { fontSize: 12, color: '#475569' },
      },
    ],
    series: [
      {
        type: 'graph',
        layout: 'force',
        // 力导向参数：贴合表规模（百表千边量级）
        force: {
          repulsion: 320,
          edgeLength: [60, 160],
          gravity: 0.08,
          friction: 0.6,
          layoutAnimation: true,
        },
        roam: true,
        draggable: true,
        data: chartNodes,
        links: chartEdges,
        categories,
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          color: '#334155',
          fontFamily: 'JetBrains Mono, Fira Code, monospace',
          formatter: (p: any) => (p.data.raw ? p.data.raw.tableName : p.name),
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 3 },
          label: { fontSize: 12, fontWeight: 'bold' },
        },
        blur: {
          itemStyle: { opacity: 0.12 },
          lineStyle: { opacity: 0.06 },
          label: { opacity: 0.1 },
        },
        itemStyle: { borderColor: '#fff', borderWidth: 1.5 },
      },
    ],
  }
}

/** 初始化 / 重绘图表 */
async function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  const option = buildOption()
  if (option) {
    chartInstance.setOption(option, true)
    chartInstance.resize()
  }
}

/** 重新布局（force 重新启动布局动画） */
function handleRerender() {
  if (!graphData) return
  const option = buildOption()
  if (option && chartInstance) {
    chartInstance.setOption(option, true)
  }
}

// ===================== 生命周期 =====================
/** 供父组件调用：重新拉取数据并重绘（视图切换回总览时刷新） */
async function refresh() {
  await loadGraphData()
  await nextTick()
  await renderChart()
}

// 父组件聚合数据变化时重绘（关系增删改后父组件统一刷新下发）
watch(
  () => props.relationGraph,
  (val) => {
    if (val) {
      graphData = val
      renderChart()
    }
  },
  { deep: true }
)

onMounted(async () => {
  await nextTick()
  // 容器尺寸自适应（配合 el-tabs 切换后的容器尺寸变化）
  if (chartRef.value) {
    resizeObserver = new ResizeObserver(() => chartInstance?.resize())
    resizeObserver.observe(chartRef.value)
  }
  await refresh()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chartInstance?.dispose()
  chartInstance = null
})

defineExpose({ refresh })
</script>

<style lang="scss" scoped>
.relation-overview-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.overview-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  flex-shrink: 0;
  flex-wrap: wrap;

  .stat-item {
    font-size: 13px;
    color: #475569;

    .num {
      font-size: 16px;
      margin: 0 2px;

      &.active { color: #16a34a; }
      &.inactive { color: #d97706; }
      &.ignored { color: #94a3b8; }
    }

    .sub {
      font-size: 12px;
      color: #94a3b8;
    }
  }

  .isolated-tip {
    margin-left: 4px;
  }

  .toolbar-tip {
    margin-left: auto;
    font-size: 12px;
    color: #94a3b8;
  }
}

.chart-body {
  flex: 1;
  position: relative;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.echarts-container {
  width: 100%;
  height: 100%;
}

.legend-panel {
  position: absolute;
  right: 12px;
  bottom: 12px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 10px 14px;
  z-index: 10;
  pointer-events: none;

  .legend-title {
    font-size: 12px;
    font-weight: 600;
    color: #475569;
    margin-bottom: 8px;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: #64748b;
    margin-bottom: 6px;

    &:last-child { margin-bottom: 0; }
  }

  .legend-line {
    width: 28px;
    height: 0;
    border-top: 2px solid;

    &.solid.blue { border-top-style: solid; border-color: #2f54eb; }
    &.solid.green { border-top-style: solid; border-color: #52c41a; }
    &.dashed.gray { border-top-style: dashed; border-color: #bfbfbf; }
    &.dotted.light { border-top-style: dotted; border-color: #d9d9d9; }
  }
}
</style>
