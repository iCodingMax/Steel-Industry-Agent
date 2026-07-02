import request from './index'

export interface TermForm {
  term: string
  code: string
  definition?: string
  category?: string
  synonyms?: string[]
  datasourceId?: number
  relatedTerms?: string[]
}

export function getTerms(params?: { page?: number; pageSize?: number; keyword?: string }) {
  return request.get<{ list: any[]; total: number }>('/terms', { params })
}

export function getTerm(id: number) {
  return request.get<any>(`/terms/${id}`)
}

export function createTerm(data: TermForm) {
  return request.post<any>('/terms', data)
}

export function updateTerm(id: number, data: Partial<TermForm>) {
  return request.put<any>(`/terms/${id}`, data)
}

export function deleteTerm(id: number) {
  return request.delete<any>(`/terms/${id}`)
}
