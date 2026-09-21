<template>
  <div class="er-canvas-wrap">
    <!-- 顶栏：搜索定位 + 视图控制 -->
    <div class="canvas-toolbar">
      <el-input
        v-model="searchName"
        placeholder="搜索表名，回车定位..."
        size="small"
        clearable
        style="width: 220px"
        @keyup.enter="handleSearchLocate"
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>
      <el-button
        size="small"
        @click="handleAutoLayout"
        title="dagre LR 分层布局（工序流水线方向）"
      >
        <el-icon><Grid /></el-icon>
        自动布局
      </el-button>
      <el-button size="small" @click="handleFit">
        <el-icon><FullScreen /></el-icon>
        适应画布
      </el-button>
      <span class="toolbar-tip"
        >从字段圆点拖拽到目标字段即可创建关系；点击边打开确认抽屉</span
      >
    </div>

    <div class="canvas-body">
      <div ref="containerRef" class="x6-container"></div>

      <!-- 图例 -->
      <div class="legend-panel">
        <div class="legend-title">图例</div>
        <div class="legend-item">
          <span class="legend-line solid blue"></span>外键（已生效 🔒）
        </div>
        <div class="legend-item">
          <span class="legend-line solid green"></span>人工确认（已生效 ✓）
        </div>
        <div class="legend-item">
          <span class="legend-line dashed gray"></span>同名推荐（待确认 ?，确认后 ✓）
        </div>
        <div class="legend-item">
          <span class="legend-line dotted light"></span>已忽略
        </div>
      </div>
    </div>

    <!-- 确认抽屉：单条关系确认动线 -->
    <el-drawer
      v-model="drawerVisible"
      :title="drawerMode === 'create' ? '确认新建表关系' : '编辑表关系'"
      size="420px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <template v-if="drawerData">
        <div class="drawer-pair">
          <div class="pair-row">
            <span class="pair-table">{{ drawerData.leftTable }}</span>
            <span class="pair-dot">.</span>
            <span class="pair-col">{{ drawerData.leftColumn }}</span>
            <el-tag v-if="leftColType" size="small" effect="plain">{{
              leftColType
            }}</el-tag>
          </div>
          <div class="pair-vs">↕</div>
          <div class="pair-row">
            <span class="pair-table">{{ drawerData.rightTable }}</span>
            <span class="pair-dot">.</span>
            <span class="pair-col">{{ drawerData.rightColumn }}</span>
            <el-tag v-if="rightColType" size="small" effect="plain">{{
              rightColType
            }}</el-tag>
          </div>
          <div v-if="typeMismatch" class="type-mismatch-warning">
            ⚠ 两侧字段类型不一致，请确认关联语义
          </div>
        </div>

        <!-- SQL 探测区 -->
        <div class="probe-section">
          <el-button
            size="small"
            @click="handleDrawerProbe"
            :loading="drawerProbing"
          >
            <el-icon><Odometer /></el-icon>
            运行 SQL 探测
          </el-button>
          <div v-if="probeResult" class="probe-result" :class="probeClass">
            <div class="probe-line">
              左表 {{ probeResult.leftDistinct }} 行 · 右表
              {{ probeResult.rightDistinct }} 行 · JOIN 后
              {{ probeResult.joinedRows }} 行
            </div>
            <div class="probe-line">
              判定 {{ probeResult.verdict }} · 放大系数 {{ probeFactorText }}
              <span v-if="probeResult.factor <= 1.05">✓</span>
              <span v-else-if="probeResult.factor > 1.5">⚠ 数据放大</span>
            </div>
          </div>
        </div>

        <el-form label-width="90px" size="default" class="drawer-form">
          <el-form-item label="基数">
            <el-radio-group v-model="drawerForm.cardinality">
              <el-radio value="1:1">1:1</el-radio>
              <el-radio value="1:N">1:N</el-radio>
              <el-radio value="N:1">N:1</el-radio>
              <el-radio value="M:N">M:N</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="JOIN类型">
            <el-radio-group v-model="drawerForm.joinType">
              <el-radio value="inner">INNER</el-radio>
              <el-radio value="left">LEFT</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="drawerForm.relationDesc"
              placeholder="如：一炉次一次打分"
              maxlength="255"
            />
          </el-form-item>
        </el-form>

        <el-alert
          v-if="probeResult && probeResult.factor > 1.5"
          title="JOIN 后行数大于左表，可能产生数据放大，请确认基数"
          type="error"
          show-icon
          :closable="false"
        />
      </template>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button
            v-if="drawerMode === 'edit' && drawerData.status !== 'ignored'"
            type="warning"
            plain
            @click="handleDrawerIgnore"
          >
            忽略此推荐
          </el-button>
          <el-button
            type="primary"
            @click="handleDrawerSave"
            :loading="drawerSaving"
          >
            {{ drawerMode === "create" ? "确认并生效" : "保存" }}
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Search, Grid, FullScreen, Odometer } from "@element-plus/icons-vue";
import { Graph } from "@antv/x6";
import type { Edge, Node } from "@antv/x6";
import { Snapline } from "@antv/x6-plugin-snapline";
import { Selection } from "@antv/x6-plugin-selection";
import dagre from "dagre";
import {
  getRelationGraph,
  createRelation,
  updateRelation,
  deleteRelation,
  batchIgnoreRelations,
  probeRelation,
} from "@/api/datasource";

// relationGraph：父组件下发的聚合数据（三视图共享一份，切换零请求）；缺省时组件自行拉取
const props = defineProps<{
  dsId: number;
  relationGraph?: { nodes: any[]; edges: any[]; stats?: any } | null;
}>();
const emit = defineEmits<{ (e: "refresh"): void }>();

// ===================== 状态定义 =====================
const containerRef = ref<HTMLDivElement>();
const searchName = ref("");

let graph: Graph | null = null;
let graphData: { nodes: any[]; edges: any[]; stats?: any } | null = null;
// 列类型映射：`${table}.${column}` -> type（探测抽屉与连线校验共用）
let colTypeMap: Record<string, string> = {};
// 表名 -> 已连边字段集合（节点折叠时保留已连边字段可见）
let connectedColMap: Record<string, Set<string>> = {};
// 表名 -> 展开状态（默认折叠：仅主键 + 已连边字段；点击表头 +/− 切换）
const expandedTables = new Set<string>();

// 抽屉状态
const drawerVisible = ref(false);
const drawerMode = ref<"create" | "edit">("create");
const drawerData = ref<any>(null);
const drawerForm = ref({
  cardinality: "1:1",
  joinType: "inner",
  relationDesc: "",
});
const drawerProbing = ref(false);
const drawerSaving = ref(false);
const probeResult = ref<any>(null);

// 节点尺寸常量
const NODE_WIDTH = 220;
const ROW_HEIGHT = 26;
const HEADER_HEIGHT = 36;

// ===================== 三来源视觉编码（方案 4.4.4） =====================
const EDGE_STYLE: Record<string, { stroke: string; dasharray: string | null }> =
  {
    foreign_key_active: { stroke: "#2F54EB", dasharray: null },
    manual_active: { stroke: "#52C41A", dasharray: null },
    auto_guess_inactive: { stroke: "#BFBFBF", dasharray: "6 4" },
    auto_guess_ignored: { stroke: "#D9D9D9", dasharray: "2 4" },
  };

function edgeStyleKey(source: string, status: string): string {
  if (status === "ignored") return "auto_guess_ignored";
  if (status === "active")
    return source === "manual" ? "manual_active" : "foreign_key_active";
  return "auto_guess_inactive";
}

// ===================== 计算属性 =====================
const leftColType = computed(() =>
  drawerData.value
    ? colTypeMap[
        `${drawerData.value.leftTable}.${drawerData.value.leftColumn}`
      ] || ""
    : "",
);
const rightColType = computed(() =>
  drawerData.value
    ? colTypeMap[
        `${drawerData.value.rightTable}.${drawerData.value.rightColumn}`
      ] || ""
    : "",
);
const typeMismatch = computed(
  () =>
    !!leftColType.value &&
    !!rightColType.value &&
    leftColType.value.toLowerCase() !== rightColType.value.toLowerCase(),
);
const probeFactorText = computed(() =>
  probeResult.value
    ? `${Math.round((probeResult.value.factor ?? 1) * 10) / 10}x`
    : "",
);
const probeClass = computed(() => {
  if (!probeResult.value) return "";
  const f = probeResult.value.factor ?? 1;
  if (f <= 1.05) return "probe-ok";
  if (f > 1.5) return "probe-bad";
  return "probe-warn";
});

// ===================== 工具函数 =====================
const portId = (colName: string) => `col_${colName}`;
const portIdR = (colName: string) => `colr_${colName}`;
/** 解析端口 id 为字段名（兼容左端口 col_ / 右端口 colr_ 两种前缀） */
const decodePort = (pid: string) => {
  if (pid.startsWith("colr_")) return pid.slice(5);
  if (pid.startsWith("col_")) return pid.slice(4);
  return "";
};

/** 类型大类归并（连线实时校验用，宽匹配避免过严误拒） */
function typeFamily(t: string): string {
  if (/char|text|enum|uuid/.test(t)) return "string";
  if (/int|serial|number|decimal|numeric|float|double|bit/.test(t))
    return "number";
  if (/date|time|year/.test(t)) return "datetime";
  return t;
}

function escapeHtml(s: string): string {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ===================== 数据加载 =====================
/** 从聚合数据构建 colTypeMap / connectedColMap（节点折叠与连线校验依据） */
function applyGraphData(data: { nodes: any[]; edges: any[]; stats?: any }) {
  graphData = data;
  colTypeMap = {};
  connectedColMap = {};
  for (const n of graphData.nodes) {
    for (const c of n.columns || []) {
      colTypeMap[`${n.id}.${c.name}`] = String(c.type || "");
    }
  }
  for (const e of graphData.edges) {
    const sp = decodePort(e.source_port || "");
    const tp = decodePort(e.target_port || "");
    (connectedColMap[e.source] ||= new Set()).add(sp);
    (connectedColMap[e.target] ||= new Set()).add(tp);
  }
}

async function loadGraphData() {
  // 父组件下发优先（三视图共享一份聚合数据，切换零请求）
  if (props.relationGraph) {
    applyGraphData(props.relationGraph);
    return;
  }
  const res: any = await getRelationGraph(props.dsId);
  if (res.code === 0 && res.data) {
    applyGraphData({
      nodes: res.data.nodes || [],
      edges: res.data.edges || [],
      stats: res.data.stats,
    });
  }
}

// ===================== 自定义表节点注册 =====================
/** 注册 ER 表节点基型：rect 主体 + 表头标题（字段行由 buildTableNode 动态 markup 生成，全 SVG 渲染） */
function registerTableNode() {
  Graph.registerNode(
    "er-table",
    {
      inherit: "rect",
      width: NODE_WIDTH,
      height: HEADER_HEIGHT + ROW_HEIGHT,
      attrs: {
        body: {
          refWidth: "100%",
          refHeight: "100%",
          rx: 8,
          ry: 8,
          fill: "#ffffff",
          stroke: "#94a3b8",
          strokeWidth: 1.2,
          filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.06))",
        },
      },
      ports: {
        groups: {
          // absolute 定位 + 每端口独立 args.x/y（buildTableNode 计算），确保圆点精确贴字段行边缘
          col: {
            position: "absolute",
            // 注意：magnet 不能放在 group 顶层（X6 不会自动 merge 到 DOM），
            // 必须放在 attrs.<selector>.magnet 中才能被 kebablizeAttrs → setAttribute 落到 SVG 元素上，
            // 这样 X6 的事件委托选择器 ".x6-cell [magnet]" 才能命中
            markup: [
              {
                tagName: "rect",
                selector: "portHit",
                attrs: { width: 14, height: 20, x: -7, y: -10 },
              },
              { tagName: "circle", selector: "portDot", attrs: { r: 5 } },
            ],
            attrs: {
              portHit: {
                magnet: true,
                fill: "transparent",
                stroke: "none",
                cursor: "crosshair",
              },
              portDot: {
                magnet: true,
                r: 5,
                stroke: "#2F54EB",
                strokeWidth: 1.5,
                fill: "#ffffff",
                cursor: "crosshair",
              },
            },
          },
        },
      },
    },
    true, // 覆盖注册（热更新场景）
  );
}

/** 构建单个表节点数据（默认折叠：仅主键 + 已连边字段；展开后全量字段，方案 4.4.6） */
function buildTableNode(node: any): Node.Metadata {
  const columns: any[] = node.columns || [];
  const connected = connectedColMap[node.id] || new Set<string>();
  const isExpanded = expandedTables.has(node.id);
  const visibleCols = isExpanded
    ? columns
    : columns.filter(
        (c) => connected.has(c.name) || c.is_pk || c.isPk || c.primaryKey,
      );
  const bodyRows = Math.max(visibleCols.length, 1);
  const height = HEADER_HEIGHT + bodyRows * ROW_HEIGHT;

  // 动态 markup：rect 主体 + 表头背景 + 表头文字 + 每字段两列 text
  const markup: any[] = [
    { tagName: "rect", selector: "body" },
    { tagName: "rect", selector: "headerBg" },
    { tagName: "text", selector: "header" },
    { tagName: "rect", selector: "expandBtn" },
    { tagName: "text", selector: "expandIcon" },
    { tagName: "line", selector: "divider" },
  ];
  const attrs: any = {
    body: {
      refWidth: "100%",
      refHeight: "100%",
      rx: 8,
      ry: 8,
      fill: "#ffffff",
      stroke: "#94a3b8",
      strokeWidth: 1.2,
      filter: "drop-shadow(0 2px 4px rgba(0,0,0,0.06))",
    },
    // 表头背景：浅蓝渐变，突出表名区域
    headerBg: {
      refX: 0,
      refY: 0,
      refWidth: "100%",
      height: HEADER_HEIGHT,
      rx: 8,
      ry: 8,
      fill: "#2F54EB",
    },
    header: {
      refX: 12,
      refY: 22,
      // 显式左对齐，覆盖 Base 基类默认 textAnchor:'middle'（否则表名以 x=12 为中心居中）
      textAnchor: "start",
      text: node.label || node.id,
      fill: "#ffffff",
      fontSize: 13,
      fontWeight: "bold",
      fontFamily: "JetBrains Mono, Fira Code, monospace",
    },
    // 表头右侧 +/− 按钮：event 属性触发 node:customevent（X6 data-event 机制）
    expandBtn: {
      refX: NODE_WIDTH - 30,
      refY: 10,
      width: 20,
      height: 20,
      rx: 4,
      ry: 4,
      fill: "rgba(255,255,255,0.2)",
      stroke: "rgba(255,255,255,0.4)",
      event: "toggle-expand",
      cursor: "pointer",
    },
    expandIcon: {
      refX: NODE_WIDTH - 20,
      refY: 24,
      text: isExpanded ? "−" : "+",
      fill: "#ffffff",
      fontSize: 14,
      fontWeight: "bold",
      textAnchor: "middle",
      event: "toggle-expand",
      cursor: "pointer",
    },
    divider: {
      refX: 0,
      refY: HEADER_HEIGHT,
      refWidth: "100%",
      stroke: "#2F54EB",
      strokeWidth: 1.5,
      opacity: 0.5,
    },
  };
  visibleCols.forEach((c, idx) => {
    // 文字 y 直接取行中心（与端口圆点一致），配合 textVerticalAnchor: 'middle' 实现精确垂直居中
    const y = HEADER_HEIGHT + idx * ROW_HEIGHT + ROW_HEIGHT / 2;
    const nameSelector = `col_name_${idx}`;
    const typeSelector = `col_type_${idx}`;
    markup.push({ tagName: "text", selector: nameSelector });
    markup.push({ tagName: "text", selector: typeSelector });
    attrs[nameSelector] = {
      x: 16,
      y,
      text: c.name,
      // 必须显式覆盖 X6 Base 基类 selector="text" 的默认 attrs（refX:0.5/refY:0.5/textAnchor:'middle'）：
      // 该默认值会经 CSS 选择器兜底（querySelectorAll('text')）命中节点下全部文本元素，
      // 使字段文本被额外平移(宽/2, 高/2)至节点中心，与端口圆点错位；refX/refY 置 null 即可禁用
      refX: null,
      refY: null,
      textAnchor: "start",
      fill: c.is_pk || c.isPk || c.primaryKey ? "#d97706" : "#334155",
      fontSize: 11,
      fontWeight: c.is_pk || c.isPk || c.primaryKey ? "bold" : "normal",
      fontFamily: "JetBrains Mono, Fira Code, monospace",
      textVerticalAnchor: "middle",
    };
    attrs[typeSelector] = {
      x: NODE_WIDTH - 12,
      y,
      text: String(c.type || ""),
      refX: null,
      refY: null,
      fill: "#94a3b8",
      fontSize: 10,
      textAnchor: "end",
      textVerticalAnchor: "middle",
      fontFamily: "JetBrains Mono, Fira Code, monospace",
    };
  });
  if (visibleCols.length === 0) {
    markup.push({ tagName: "text", selector: "col_empty" });
    attrs.col_empty = {
      x: 16,
      y: HEADER_HEIGHT + ROW_HEIGHT / 2,
      text: isExpanded ? "（无字段）" : "点击 + 展开全部字段",
      // 同上：覆盖 Base 基类经 CSS 选择器兜底污染的默认 attrs
      refX: null,
      refY: null,
      textAnchor: "start",
      fill: "#cbd5e1",
      fontSize: 11,
      textVerticalAnchor: "middle",
    };
  }

  return {
    id: node.id,
    shape: "er-table",
    x: 0,
    y: 0,
    width: NODE_WIDTH,
    height,
    markup,
    attrs,
    ports: {
      items: visibleCols.flatMap((c, idx) => {
        const rowCenterY = HEADER_HEIGHT + idx * ROW_HEIGHT + ROW_HEIGHT / 2;
        return [
          // 双侧端口：左圆点贴左边缘、右圆点贴右边缘，均与字段行垂直居中对齐
          { id: portId(c.name), group: "col", args: { x: 0, y: rowCenterY } },
          {
            id: portIdR(c.name),
            group: "col",
            args: { x: NODE_WIDTH, y: rowCenterY },
          },
        ];
      }),
    },
    data: { tableName: node.id },
  };
}

/** 构建关系边数据（三来源视觉编码 + 中点 Label 基数 + 目标端箭头） */
function buildEdge(edge: any): Edge.Metadata {
  const key = edgeStyleKey(edge.source_type || edge.source, edge.status);
  const style = EDGE_STYLE[key];
  const cardinality = edge.cardinality || "";
  const sourceLabel = sourceBadge(edge.source_type || edge.source, edge.status);
  return {
    id: `rel_${edge.id}`,
    shape: "edge",
    source: { cell: edge.source, port: edge.source_port || undefined },
    target: { cell: edge.target, port: edge.target_port || undefined },
    attrs: {
      line: {
        stroke: style.stroke,
        strokeWidth: 2,
        strokeDasharray: style.dasharray || undefined,
        cursor: "pointer",
        // 目标端箭头：classic 是 X6 内置三角箭头，颜色跟随连线（marker attr 会自动继承 stroke）
        targetMarker: {
          name: "classic",
          args: { size: 6 },
        },
      },
    },
    labels: [
      {
        position: 0.5,
        // 注意：selector 必须使用 X6 默认 label 的 body/label 命名。
        // 用户 label 会与 Edge.defaultLabel（attrs: {text, rect:{ref:'label'}}）深合并，
        // 若用自定义 selector 名，默认 attrs 的 rect:{ref:'label'} 会经 CSS 兜底命中 rect 元素，
        // 渲染时找不到 'label' 元素抛 "label reference does not exist"，
        // 导致 X6 异步渲染队列冻结（flushJobs 无 try-catch），其余边全部不渲染
        markup: [
          { tagName: "rect", selector: "body" },
          { tagName: "text", selector: "label" },
        ],
        attrs: {
          body: {
            // 清除默认 rect attrs 残留的 ref 自适应定位，改用固定样式
            ref: null,
            refX: null,
            refY: null,
            refWidth: null,
            refHeight: null,
            fill: "#ffffff",
            stroke: style.stroke,
            strokeWidth: 1,
            rx: 4,
            ry: 4,
          },
          label: {
            text: `${cardinality} ${sourceLabel}`.trim(),
            fill: style.stroke,
            fontSize: 10,
            fontWeight: "bold",
            textAnchor: "middle",
            textVerticalAnchor: "middle",
            pointerEvents: "none",
          },
        },
      },
    ],
    connector: { name: "rounded", args: { radius: 8 } },
    zIndex: 1,
    data: edge,
  };
}

function sourceBadge(source: string, status: string): string {
  // 已生效的推荐关系：人工已确认，不再显示存疑标记
  if (source === "auto_guess" && status === "active") return "✓";
  return { foreign_key: "🔒", manual: "✓", auto_guess: "?" }[source] || "";
}

// ===================== 画布初始化 =====================
function initGraph() {
  if (!containerRef.value) return;
  graph = new Graph({
    container: containerRef.value,
    grid: {
      visible: false,
    },
    background: { color: "#f8fafc" },
    connecting: {
      router: "normal",
      connector: { name: "rounded", args: { radius: 8 } },
      anchor: "center",
      connectionPoint: "anchor",
      allowBlank: false,
      allowLoop: false, // 防自环
      allowNode: false,
      // 复合键场景允许同表对多字段重复连线（同一对端口仍禁止）
      allowMulti: "withPort",
      allowEdge: false,
      // 拖拽连线时高亮全部可连接端口（X6 内置 magnetAvailable/nodeAvailable）
      highlight: true,
      // 注意：createEdge 必须返回 Edge 实例（graph.createEdge 返回值），
      // 因为 X6 在 createEdgeFromMagnet 中会调用 edge.setSource / edge.addTo，
      // 纯元数据对象没有这些方法会直接 TypeError
      createEdge() {
        return graph!.createEdge({
          shape: "edge",
          attrs: {
            line: {
              stroke: "#2F54EB",
              strokeWidth: 2,
              strokeDasharray: "5 5",
              targetMarker: null,
            },
          },
          connector: { name: "rounded", args: { radius: 8 } },
        });
      },
      validateConnection({
        sourceCell,
        targetCell,
        sourcePort,
        targetPort,
      }: any) {
        if (!sourceCell || !targetCell || !sourcePort || !targetPort)
          return false;
        const sourceTable = sourceCell.id as string;
        const targetTable = targetCell.id as string;
        if (sourceTable === targetTable) return false; // 非同表
        const sourceCol = decodePort(sourcePort);
        const targetCol = decodePort(targetPort);
        if (!sourceCol || !targetCol) return false;
        // 重复关系拦截：同表同字段对已存在则不可再连
        const dup = graphData?.edges.some(
          (e) =>
            (e.source === sourceTable &&
              e.target === targetTable &&
              decodePort(e.source_port || "") === sourceCol &&
              decodePort(e.target_port || "") === targetCol) ||
            (e.source === targetTable &&
              e.target === sourceTable &&
              decodePort(e.source_port || "") === targetCol &&
              decodePort(e.target_port || "") === sourceCol),
        );
        if (dup) return false;
        // 类型匹配宽校验（string/number/datetime 大类一致才可连）
        const st = (
          colTypeMap[`${sourceTable}.${sourceCol}`] || ""
        ).toLowerCase();
        const tt = (
          colTypeMap[`${targetTable}.${targetCol}`] || ""
        ).toLowerCase();
        if (st && tt && typeFamily(st) !== typeFamily(tt)) return false;
        return true;
      },
    },
    highlighting: {
      // 拖线时所有合法端口描边高亮（stroke 高亮器沿端口轮廓描边）
      magnetAvailable: {
        name: "stroke",
        args: { padding: 4, attrs: { "stroke-width": 2, stroke: "#3b82f6" } },
      },
      magnetAdsorbed: {
        name: "stroke",
        args: { padding: 4, attrs: { "stroke-width": 2, stroke: "#52c41a" } },
      },
    },
    mousewheel: {
      enabled: true,
      modifiers: "ctrl",
      minScale: 0.2,
      maxScale: 3,
    },
    panning: { enabled: true, eventTypes: ["leftMouseDown", "mouseWheel"] },
  });

  // 插件：对齐线 + 框选
  graph.use(new Snapline({ enabled: true }));
  graph.use(
    new Selection({
      enabled: true,
      rubberband: true,
      movable: false,
      showNodeSelectionBox: false,
    }),
  );

  // 字段端口拖拽连线完成 -> 移除临时边并打开确认抽屉
  // 事件参数为 edge/isNew（X6 源码 notifyConnectionEvent），仅在新建边时触发抽屉
  graph.on("edge:connected", ({ edge, isNew }: any) => {
    if (!isNew) return;
    const sourceNode = edge.getSourceNode();
    const targetNode = edge.getTargetNode();
    const sourcePort = edge.getSourcePortId();
    const targetPort = edge.getTargetPortId();
    graph?.removeCell(edge);
    if (!sourceNode || !targetNode || !sourcePort || !targetPort) return;
    openCreateDrawer({
      leftTable: sourceNode.id as string,
      leftColumn: decodePort(sourcePort),
      rightTable: targetNode.id as string,
      rightColumn: decodePort(targetPort),
    });
  });

  // 表头 +/− 展开按钮（event 属性触发 customevent）-> 重建该节点
  graph.on("node:customevent", ({ e, node, name }: any) => {
    if (name !== "toggle-expand") return;
    e.stopPropagation();
    const tableId = node.id as string;
    if (expandedTables.has(tableId)) {
      expandedTables.delete(tableId);
    } else {
      expandedTables.add(tableId);
    }
    rebuildNode(tableId);
  });

  // 点击边 -> 编辑抽屉
  graph.on("edge:click", ({ edge }: any) => {
    const data = edge.getData();
    if (data) openEditDrawer(data);
  });

  // 边 hover -> 显示删除按钮（仅已持久化的关系边）
  graph.on("edge:mouseenter", ({ edge }: any) => {
    if (!edge.getData()) return;
    edge.addTools([
      {
        name: "button-remove",
        args: {
          distance: -30,
          onClick({ e: evt }: any) {
            evt.stopPropagation();
            handleEdgeRemove(edge);
          },
        },
      },
    ]);
  });
  graph.on("edge:mouseleave", ({ edge }: any) => edge.removeTools());

  // 点击表节点 -> 邻域高亮（一跳邻居，其余淡化 opacity 0.15）
  graph.on("node:click", ({ node }: any) =>
    highlightNeighbors(node.id as string),
  );
  graph.on("blank:click", () => resetHighlight());

  // 节点拖动结束后端口侧跟随修正（用户把左表拖到右侧时边换挂端口）
  let portFixTimer: ReturnType<typeof setTimeout> | null = null;
  graph.on("node:moved", () => {
    if (portFixTimer) clearTimeout(portFixTimer);
    portFixTimer = setTimeout(() => fixEdgePortSides(), 120);
  });
}

/** 渲染全图（节点 + 边）：batchUpdate 合并渲染，fromJSON 直接接受元数据数组 */
function renderGraph() {
  if (!graph || !graphData) return;
  const nodes = graphData.nodes.map(buildTableNode);
  const edges = graphData.edges.map(buildEdge);
  graph.fromJSON([...nodes, ...edges]);
  applyDagreLayout();
  fixEdgePortSides();
  handleFit();
}

/**
 * 端口侧修正：dagre 布局后根据源/目标节点相对位置，把每条边重挂到朝向对方的端口侧
 * （源节点在左 -> 源用右端口 colr_、目标用左端口 col_），避免连线穿过节点主体
 */
function fixEdgePortSides() {
  if (!graph) return;
  for (const edgeView of graph.getEdges()) {
    const data = edgeView.getData();
    if (!data) continue;
    const sourceNode = edgeView.getSourceNode();
    const targetNode = edgeView.getTargetNode();
    if (!sourceNode || !targetNode) continue;
    const sp = sourceNode.getPosition();
    const tp = targetNode.getPosition();
    const sourceLeft = sp.x <= tp.x;
    const leftCol = decodePort(data.source_port || "");
    const rightCol = decodePort(data.target_port || "");
    if (!leftCol || !rightCol) continue;
    // 端口存在性防御：折叠节点仅保留主键+已连边字段，理论上必含；异常时跳过修正
    if (
      !sourceNode.hasPort(portIdR(leftCol)) ||
      !targetNode.hasPort(portId(rightCol))
    )
      continue;
    edgeView.setSource({
      cell: data.source,
      port: sourceLeft ? portIdR(leftCol) : portId(leftCol),
    });
    edgeView.setTarget({
      cell: data.target,
      port: sourceLeft ? portId(rightCol) : portIdR(rightCol),
    });
  }
}

/** 展开状态切换后原地重建单个表节点（保留位置与连线，markup/attrs/ports/尺寸整体替换） */
function rebuildNode(tableId: string) {
  if (!graph || !graphData) return;
  // Graph 无 getNodeById，统一走 getCellById + isNode 类型收窄
  const nodeMeta = graphData.nodes.find((n) => n.id === tableId);
  const cell = graph.getCellById(tableId);
  if (!nodeMeta || !cell || !cell.isNode()) return;
  const meta = buildTableNode(nodeMeta);
  graph.startBatch("rebuild-node");
  // markup 变更触发视图完整重渲染；attrs/ports/size 原地替换，边随端口位置自动重算
  cell.setMarkup(meta.markup as any);
  cell.replaceAttrs(meta.attrs as any);
  // 注意：必须 rewrite: true —— 默认嵌套路径走 lodash merge，数组按索引合并且不截断，
  // 收起（长数组->短数组）时残留旧端口/字段行；rewrite 先 unset 再写入，数组整体替换可收缩
  cell.prop("ports/items", (meta.ports as any).items, { rewrite: true } as any);
  cell.resize(NODE_WIDTH, meta.height as number);
  graph.stopBatch("rebuild-node");
}

/** 边 hover 删除按钮回调：二次确认后调用删除 API 并刷新 */
async function handleEdgeRemove(edge: Edge) {
  const data = edge.getData();
  if (!data) return;
  try {
    await ElMessageBox.confirm(
      `确定删除表关系【${data.leftTable}.${data.leftColumn} ↔ ${data.rightTable}.${data.rightColumn}】吗？`,
      "删除关系",
      { type: "warning" },
    );
  } catch {
    return;
  }
  try {
    const res: any = await deleteRelation(props.dsId, data.id);
    if (res.code === 0) {
      ElMessage.success("关系已删除");
      if (props.relationGraph) {
        emit("refresh");
      } else {
        await refresh();
        emit("refresh");
      }
    }
  } catch (e) {
    console.error("删除关系失败", e);
  }
}

/** dagre LR 分层布局（贴合工序流水线：炼铁→炼钢→轧钢从左到右） */
function applyDagreLayout() {
  if (!graph || !graphData) return;
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: "LR",
    nodesep: 60,
    edgesep: 30,
    ranksep: 120,
    marginx: 40,
    marginy: 40,
  });
  g.setDefaultEdgeLabel(() => ({}));
  // 用画布实际节点（Node 实例）取尺寸，避免对 Cell 泛型误用 Node API
  for (const x6Node of graph.getNodes()) {
    const size = x6Node.getSize();
    g.setNode(x6Node.id, { width: size.width, height: size.height });
  }
  for (const edge of graphData.edges) {
    if (graph.hasCell(edge.source) && graph.hasCell(edge.target)) {
      g.setEdge(edge.source, edge.target);
    }
  }
  dagre.layout(g);
  for (const x6Node of graph.getNodes()) {
    const pos = g.node(x6Node.id);
    if (pos) x6Node.position(pos.x - pos.width / 2, pos.y - pos.height / 2);
  }
}

/** 适应画布 */
function handleFit() {
  graph?.zoomToFit({ padding: 60, maxScale: 1 });
}

function handleAutoLayout() {
  applyDagreLayout();
  fixEdgePortSides();
  handleFit();
}

/** 搜索定位：centerCell 定位 + 脉冲高亮 */
function handleSearchLocate() {
  if (!graph || !searchName.value.trim()) return;
  const kw = searchName.value.trim().toLowerCase();
  const cell = graphData?.nodes.find(
    (n) =>
      n.id.toLowerCase().includes(kw) ||
      (n.label || "").toLowerCase().includes(kw),
  );
  if (!cell) {
    ElMessage.warning("未找到匹配的表");
    return;
  }
  const x6Node = graph.getCellById(cell.id);
  if (!x6Node) return;
  graph.centerCell(x6Node);
  // 脉冲高亮：描边加粗 1.6s 后恢复
  (x6Node as any).attr("body/stroke", "#3b82f6");
  (x6Node as any).attr("body/strokeWidth", 3);
  setTimeout(() => {
    (x6Node as any).attr("body/stroke", "#cbd5e1");
    (x6Node as any).attr("body/strokeWidth", 1);
  }, 1600);
}

/** 邻域高亮：一跳邻居保持，其余淡化 */
function highlightNeighbors(tableId: string) {
  if (!graph || !graphData) return;
  const neighborSet = new Set<string>([tableId]);
  for (const e of graphData.edges) {
    if (e.source === tableId) neighborSet.add(e.target);
    if (e.target === tableId) neighborSet.add(e.source);
  }
  graph.getNodes().forEach((n: any) => {
    const inNeighborhood = neighborSet.has(n.id as string);
    n.attr("body/opacity", inNeighborhood ? 1 : 0.15);
    n.attr("header/opacity", inNeighborhood ? 1 : 0.15);
    n.attr("fo/style", inNeighborhood ? "opacity:1" : "opacity:0.15");
  });
  graph.getEdges().forEach((e: any) => {
    const data = e.getData();
    const inNeighborhood =
      data && (data.source === tableId || data.target === tableId);
    e.attr("line/opacity", inNeighborhood ? 1 : 0.1);
  });
}

function resetHighlight() {
  if (!graph) return;
  graph.getNodes().forEach((n: any) => {
    n.attr("body/opacity", 1);
    n.attr("header/opacity", 1);
    n.attr("fo/style", "opacity:1");
  });
  graph.getEdges().forEach((e: any) => e.attr("line/opacity", 1));
}

// ===================== 确认抽屉 =====================
function openCreateDrawer(conn: {
  leftTable: string;
  leftColumn: string;
  rightTable: string;
  rightColumn: string;
}) {
  drawerMode.value = "create";
  drawerData.value = { ...conn, source: "manual", status: "inactive" };
  drawerForm.value = {
    cardinality: "1:1",
    joinType: "inner",
    relationDesc: "",
  };
  probeResult.value = null;
  drawerVisible.value = true;
}

function openEditDrawer(edge: any) {
  drawerMode.value = "edit";
  drawerData.value = edge;
  drawerForm.value = {
    cardinality: edge.cardinality || "1:1",
    joinType: edge.joinType || edge.join_type || "inner",
    relationDesc: edge.relationDesc || edge.relation_desc || edge.desc || "",
  };
  probeResult.value = edge.probe || null;
  drawerVisible.value = true;
}

async function handleDrawerProbe() {
  if (!drawerData.value) return;
  drawerProbing.value = true;
  try {
    const d = drawerData.value;
    const res: any = await probeRelation(props.dsId, {
      leftTable: d.leftTable,
      leftColumn: d.leftColumn,
      rightTable: d.rightTable,
      rightColumn: d.rightColumn,
    });
    if (res.code === 0 && res.data) {
      probeResult.value = res.data;
      // 探测结论驱动基数预选
      if (["1:N", "N:1", "1:1"].includes(res.data.verdict)) {
        drawerForm.value.cardinality = res.data.verdict;
      }
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || e?.message || "探测失败");
  } finally {
    drawerProbing.value = false;
  }
}

async function handleDrawerSave() {
  if (!drawerData.value) return;
  // 放大系数 > 1.5 时二次确认（方案 4.4.4）
  if (probeResult.value && probeResult.value.factor > 1.5) {
    try {
      await ElMessageBox.confirm(
        "JOIN 后行数大于左表，可能产生数据放大，确认仍要生效此关系吗？",
        "二次确认",
        { type: "warning" },
      );
    } catch {
      return;
    }
  }
  drawerSaving.value = true;
  try {
    let res: any;
    if (drawerMode.value === "create") {
      res = await createRelation(props.dsId, {
        leftTable: drawerData.value.leftTable,
        leftColumn: drawerData.value.leftColumn,
        rightTable: drawerData.value.rightTable,
        rightColumn: drawerData.value.rightColumn,
        cardinality: drawerForm.value.cardinality as any,
        joinType: drawerForm.value.joinType as any,
        relationDesc: drawerForm.value.relationDesc || undefined,
      });
    } else {
      res = await updateRelation(props.dsId, drawerData.value.id, {
        cardinality: drawerForm.value.cardinality as any,
        joinType: drawerForm.value.joinType as any,
        relationDesc: drawerForm.value.relationDesc || undefined,
      });
    }
    if (res.code === 0) {
      ElMessage.success(
        drawerMode.value === "create" ? "关系已创建并生效" : "关系已更新",
      );
      drawerVisible.value = false;
      // 父组件模式下由父组件统一刷新下发；独立模式下本地拉取后仍通知父组件
      if (props.relationGraph) {
        emit("refresh");
      } else {
        await refresh();
        emit("refresh");
      }
    }
  } catch (e) {
    console.error("保存关系失败", e);
  } finally {
    drawerSaving.value = false;
  }
}

async function handleDrawerIgnore() {
  if (!drawerData.value) return;
  try {
    const res: any = await batchIgnoreRelations(props.dsId, [
      drawerData.value.id,
    ]);
    if (res.code === 0) {
      ElMessage.success("关系已忽略");
      drawerVisible.value = false;
      // 父组件模式下由父组件统一刷新下发；独立模式下本地拉取
      if (props.relationGraph) {
        emit("refresh");
      } else {
        await refresh();
        emit("refresh");
      }
    }
  } catch (e) {
    console.error("忽略失败", e);
  }
}

// ===================== 生命周期 =====================
async function refresh() {
  await loadGraphData();
  renderGraph();
}

// 父组件聚合数据变化时重绘（关系增删改后父组件统一刷新下发）
watch(
  () => props.relationGraph,
  (val) => {
    if (val) {
      applyGraphData(val);
      renderGraph();
    }
  },
  { deep: true },
);

onMounted(async () => {
  await nextTick();
  registerTableNode();
  initGraph();
  await refresh();
});

onBeforeUnmount(() => {
  graph?.dispose();
  graph = null;
});

// 暴露刷新方法（父组件视图切换回画布时重绘）
defineExpose({ refresh });
</script>

<style lang="scss" scoped>
.er-canvas-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.canvas-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  flex-shrink: 0;

  .toolbar-tip {
    margin-left: auto;
    font-size: 12px;
    color: #94a3b8;
  }
}

.canvas-body {
  flex: 1;
  position: relative;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.x6-container {
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

    &:last-child {
      margin-bottom: 0;
    }
  }

  .legend-line {
    display: inline-block;
    width: 28px;
    height: 2px;
    flex-shrink: 0;

    &.solid.blue {
      background: #2f54eb;
    }
    &.solid.green {
      background: #52c41a;
    }
    &.dashed.gray {
      background: linear-gradient(
        90deg,
        #bfbfbf 0,
        #bfbfbf 6px,
        transparent 6px,
        transparent 10px
      );
      background-size: 10px 2px;
      background-repeat: repeat-x;
    }
    &.dotted.light {
      height: 1px;
      background: radial-gradient(
        circle,
        #d9d9d9 1px,
        transparent 1px
      );
      background-size: 4px 2px;
      background-repeat: repeat-x;
      background-position: 0 center;
    }
  }
}

.drawer-pair {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;

  .pair-row {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-wrap: wrap;

    .pair-table {
      font-family: "JetBrains Mono", "Fira Code", monospace;
      font-weight: 600;
      color: #1e293b;
      font-size: 13px;
    }

    .pair-dot {
      color: #94a3b8;
    }

    .pair-col {
      font-family: "JetBrains Mono", "Fira Code", monospace;
      color: #3b82f6;
      font-size: 13px;
    }
  }

  .pair-vs {
    text-align: center;
    color: #94a3b8;
    margin: 6px 0;
  }

  .type-mismatch-warning {
    margin-top: 8px;
    font-size: 12px;
    color: #d97706;
  }
}

.probe-section {
  margin-bottom: 16px;

  .probe-result {
    margin-top: 10px;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;

    .probe-line {
      margin-bottom: 4px;
    }
    .probe-line:last-child {
      margin-bottom: 0;
    }

    &.probe-ok {
      background: #f0fdf4;
      color: #16a34a;
      border: 1px solid #bbf7d0;
    }

    &.probe-warn {
      background: #fffbeb;
      color: #d97706;
      border: 1px solid #fde68a;
    }

    &.probe-bad {
      background: #fef2f2;
      color: #dc2626;
      border: 1px solid #fecaca;
    }
  }
}

.drawer-form {
  margin-top: 8px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
