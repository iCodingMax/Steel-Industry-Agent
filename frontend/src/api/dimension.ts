import request from './index'

export interface DimensionForm {
  name: string
  code: string
  description?: string
  datasourceId: number
  tableName: string
  columnName: string
  dataType?: string
  level?: number
  parentId?: number
}

export function getDimensions(params?: { page?: number; pageSize?: number }) {
  return request.get<{ list: any[]; total: number }>('/dimensions', { params })
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
