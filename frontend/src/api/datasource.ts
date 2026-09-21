import request from './index'

export interface DatasourceForm {
  name: string
  type: string
  host: string
  port: number
  database: string
  username: string
  password?: string
  charset?: string
  poolSize?: number
  maxOverflow?: number
  description?: string
}

export interface DatasourceListResponse {
  total: number
  list: any[]
}

export function getDatasources(params?: { page?: number; pageSize?: number; keyword?: string }) {
  return request.get<{ data: DatasourceListResponse }>('/datasources', { params })
}

export function getDatasource(id: number) {
  return request.get<any>(`/datasources/${id}`)
}

export function createDatasource(data: DatasourceForm) {
  return request.post<any>('/datasources', data)
}

export function updateDatasource(id: number, data: Partial<DatasourceForm>) {
  return request.put<any>(`/datasources/${id}`, data)
}

export function deleteDatasource(id: number) {
  return request.delete<any>(`/datasources/${id}`)
}

export function testConnection(data: any) {
  return request.post<{ success: boolean; message: string }>('/datasources/test-connection', data)
}

export function syncSchema(id: number) {
  return request.post<any[]>(`/datasources/${id}/sync-schema`)
}

export function getSchema(id: number) {
  return request.get<any[]>(`/datasources/${id}/schema`)
}

// ===================== 字段备注（V2.1 双列：原字段备注只读 / 字段备注可编辑） =====================

export interface ColumnRemarkItem {
  name: string
  remark: string
  /** 草稿等于原字段备注时传 true，服务端置 remark_edited=false（后续同步跟随 comment 刷新） */
  reset?: boolean
}

/** 批量保存表字段备注（保存即置 remark_edited=true，后端异步重建该表向量索引） */
export function updateColumnRemarks(dsId: number, tableName: string, remarks: ColumnRemarkItem[]) {
  return request.put<any>(`/datasources/${dsId}/tables/${tableName}/columns/remark`, { remarks })
}

// ===================== 表关系管理（NL2SQL 联表查询关联键白名单） =====================

export interface RelationForm {
  leftTable: string
  leftColumn: string
  rightTable: string
  rightColumn: string
  joinType?: 'inner' | 'left'
  relationDesc?: string
  cardinality?: '1:1' | '1:N' | 'N:1' | 'M:N'
  relationGroup?: string
}

export function getRelations(
  dsId: number,
  params?: { status?: string; source?: string; keyword?: string; page?: number; pageSize?: number }
) {
  return request.get<any>(`/datasources/${dsId}/relations`, { params })
}

export function createRelation(dsId: number, data: RelationForm) {
  return request.post<any>(`/datasources/${dsId}/relations`, data)
}

export function updateRelation(dsId: number, relId: number, data: Partial<RelationForm> & { status?: string }) {
  return request.put<any>(`/datasources/${dsId}/relations/${relId}`, data)
}

export function deleteRelation(dsId: number, relId: number) {
  return request.delete<any>(`/datasources/${dsId}/relations/${relId}`)
}

export function batchConfirmRelations(dsId: number, ids: number[], cardinality?: string) {
  return request.post<any>(`/datasources/${dsId}/relations/batch-confirm`, { ids, cardinality })
}

export function batchIgnoreRelations(dsId: number, ids: number[]) {
  return request.post<any>(`/datasources/${dsId}/relations/batch-ignore`, { ids })
}

export function probeRelation(
  dsId: number,
  data: { leftTable: string; leftColumn: string; rightTable: string; rightColumn: string }
) {
  return request.post<any>(`/datasources/${dsId}/relations/probe`, data)
}

export function collectRelations(dsId: number) {
  return request.post<any>(`/datasources/${dsId}/relations/collect`)
}

export function getRelationGraph(dsId: number) {
  return request.get<any>(`/datasources/${dsId}/relation-graph`)
}

// ===================== 示例SQL库（NL2SQL Few-shot 手工示例） =====================

export interface SqlExampleForm {
  datasourceId?: number
  question: string
  sql: string
  description?: string
  status?: 'active' | 'retired'
}

export function getSqlExamples(
  dsId: number,
  params?: { status?: string; keyword?: string; page?: number; pageSize?: number }
) {
  return request.get<any>(`/datasources/${dsId}/sql-examples`, { params })
}

/** 跨数据源查询全部示例SQL列表 */
export function getAllSqlExamples(
  params?: { status?: string; keyword?: string; page?: number; pageSize?: number }
) {
  return request.get<any>('/datasources/sql-examples', { params })
}

export function createSqlExample(dsId: number, data: SqlExampleForm) {
  return request.post<any>(`/datasources/${dsId}/sql-examples`, data)
}

export function updateSqlExample(dsId: number, exampleId: number, data: Partial<SqlExampleForm>) {
  return request.put<any>(`/datasources/${dsId}/sql-examples/${exampleId}`, data)
}

export function updateSqlExampleStatus(dsId: number, exampleId: number, status: 'active' | 'retired') {
  return request.put<any>(`/datasources/${dsId}/sql-examples/${exampleId}/status`, { status })
}

export function deleteSqlExample(dsId: number, exampleId: number) {
  return request.delete<any>(`/datasources/${dsId}/sql-examples/${exampleId}`)
}

export function dryRunSqlExample(dsId: number, exampleId: number) {
  return request.post<any>(`/datasources/${dsId}/sql-examples/${exampleId}/dry-run`)
}
