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
