import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface KnowledgeBase {
  id: number
  name: string
  description: string
  documentCount: number
  createdAt: string
  status: 'ready' | 'building' | 'error'
}

export interface DocumentItem {
  id: number
  name: string
  size: number
  status: 'uploading' | 'parsing' | 'indexing' | 'ready' | 'error'
  pages: number
  uploadedAt: string
}

export const useKnowledgeStore = defineStore('knowledge', () => {
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const currentKBId = ref<number | null>(null)
  const documents = ref<DocumentItem[]>([])

  return {
    knowledgeBases,
    currentKBId,
    documents,
  }
})
