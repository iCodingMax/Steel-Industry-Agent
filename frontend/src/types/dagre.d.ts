// dagre 分层布局库类型声明（官方未提供 @types/dagre，按项目实际用到的 API 声明）
declare module 'dagre' {
  /** dagre 图实例（graphlib.Graph） */
  export interface DagreGraph {
    /** 设置图级布局参数（rankdir/nodesep/ranksep 等） */
    setGraph(label: Record<string, any>): void
    /** 设置/读取节点（含 width/height 输入，layout 后含 x/y 中心坐标输出） */
    setNode(id: string, label: Record<string, any>): void
    node(id: string): { x: number; y: number; width: number; height: number } | undefined
    /** 设置边（v -> w） */
    setEdge(source: string, target: string, label?: Record<string, any>): void
    /** 设置默认边 label 工厂 */
    setDefaultEdgeLabel(factory: () => Record<string, any>): void
  }

  const dagre: {
    graphlib: {
      Graph: new (options?: { multigraph?: boolean; compound?: boolean; directed?: boolean }) => DagreGraph
    }
    /** 执行布局计算（就地写入各节点 x/y 坐标） */
    layout: (graph: DagreGraph) => void
  }

  export default dagre
}
