import request from './index'

export interface AuditLogStats {
  total: number
  successCount: number
  failedCount: number
  successRate: number
  actionStats: { action: string; count: number }[]
  resourceStats: { resourceType: string; count: number }[]
}

export interface AuditLogItem {
  id: number
  userId: number | null
  username: string | null
  action: string
  resourceType: string
  resourceId: number | null
  resourceName: string | null
  method: string | null
  path: string | null
  ipAddress: string | null
  status: string
  errorMessage: string | null
  detail: any
  createdAt: string | null
}

export function getAuditStats(params?: { startDate?: string; endDate?: string }) {
  return request.get<AuditLogStats>('/audit-logs/stats', { params })
}

export function getAuditLogs(params?: {
  skip?: number
  limit?: number
  action?: string
  resourceType?: string
  status?: string
  startDate?: string
  endDate?: string
  keyword?: string
}) {
  return request.get<{ list: AuditLogItem[]; total: number }>('/audit-logs', { params })
}

export function collectAuditLogs() {
  return request.post<{ collected: number }>('/audit-logs/collect')
}
