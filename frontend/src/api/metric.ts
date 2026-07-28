import request from './index'

export interface MetricForm {
  name: string
  code: string
  description?: string
  datasourceId?: number
  sqlExpression: string
  resultType?: string
  unit?: string
  groupName?: string
  tags?: string[]
}

export interface MetricListResponse {
  total: number
  list: any[]
}

export function getMetrics(params?: { page?: number; pageSize?: number; datasourceId?: number; keyword?: string }) {
  return request.get<{ data: MetricListResponse }>('/metrics', { params })
}

export function getMetric(id: number) {
  return request.get<any>(`/metrics/${id}`)
}

export function createMetric(data: MetricForm) {
  return request.post<any>('/metrics', data)
}

export function updateMetric(id: number, data: Partial<MetricForm>) {
  return request.put<any>(`/metrics/${id}`, data)
}

export function deleteMetric(id: number) {
  return request.delete<any>(`/metrics/${id}`)
}
