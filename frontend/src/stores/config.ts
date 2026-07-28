import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Datasource {
  id: number
  name: string
  type: 'mysql' | 'postgresql' | 'sqlserver'
  host: string
  port: number
  database: string
  username: string
  createdAt: string
  status: 'active' | 'inactive'
}

export interface Metric {
  id: number
  name: string
  description: string
  datasourceId: number
  sqlExpression: string
  group: string
  createdAt: string
}

export const useConfigStore = defineStore('config', () => {
  const datasources = ref<Datasource[]>([])
  const metrics = ref<Metric[]>([])

  return {
    datasources,
    metrics,
  }
})
