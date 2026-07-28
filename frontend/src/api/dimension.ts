import request from './index'

export interface DimensionForm {
  name: string
  code: string
  description?: string
  datasourceId?: number
  tableName: string
  columnName: string
  dataType?: string
  level?: number
  parentId?: number
}

export interface DimensionListResponse {
  total: number
  list: any[]
}

export function getDimensions(params?: { page?: number; pageSize?: number; datasourceId?: number; keyword?: string }) {
  return request.get<{ data: DimensionListResponse }>('/dimensions', { params })
}

export function getDimension(id: number) {
  return request.get<any>(`/dimensions/${id}`)
}

export function createDimension(data: DimensionForm) {
  return request.post<any>('/dimensions', data)
}

export function updateDimension(id: number, data: Partial<DimensionForm>) {
  return request.put<any>(`/dimensions/${id}`, data)
}

export function deleteDimension(id: number) {
  return request.delete<any>(`/dimensions/${id}`)
}
