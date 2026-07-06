import request from './index'

export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  embeddingModel: string
  chunkSize: number
  chunkOverlap: number
  status: string
  documentCount?: number
  createdAt: string
  updatedAt: string
  createdBy?: number
}

export interface Document {
  id: number
  knowledgeBaseId: number
  fileName: string
  filePath: string
  fileType: string
  fileSize?: number
  pageCount?: number
  status: string
  errorMessage?: string
  segmentCount: number
  createdAt: string
  updatedAt: string
}

export interface KnowledgeQuery {
  knowledgeBaseId: number
  question: string
  topK?: number
}

export interface KnowledgeQueryResult {
  segmentId: number
  documentId: number
  documentName: string
  content: string
  score: number
  metadata: any
}

export interface KnowledgeAnswer {
  answer: string
  references: KnowledgeQueryResult[]
  queryTime: number
}

export function getKnowledgeBases(params?: { skip?: number; limit?: number }) {
  return request.get<{ list: KnowledgeBase[]; total: number }>('/knowledge-bases', { params })
}

export function getKnowledgeBase(id: number) {
  return request.get<KnowledgeBase>(`/knowledge-bases/${id}`)
}

export function createKnowledgeBase(data: any) {
  return request.post<KnowledgeBase>('/knowledge-bases', data)
}

export function updateKnowledgeBase(id: number, data: any) {
  return request.put<KnowledgeBase>(`/knowledge-bases/${id}`, data)
}

export function deleteKnowledgeBase(id: number) {
  return request.delete(`/knowledge-bases/${id}`)
}

export function getDocuments(kbId: number, params?: { skip?: number; limit?: number }) {
  return request.get<{ list: Document[]; total: number }>(`/knowledge-bases/${kbId}/documents`, { params })
}

export function uploadDocument(kbId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<Document>(`/knowledge-bases/${kbId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function deleteDocument(kbId: number, docId: number) {
  return request.delete(`/knowledge-bases/${kbId}/documents/${docId}`)
}

export interface DocumentDetail extends Document {
  totalChars: number
  avgChunkChars: number
}

export interface DocumentSegment {
  id: number
  documentId: number
  knowledgeBaseId: number
  content: string
  segmentIndex: number
  startChar?: number
  endChar?: number
  metadata: any
  charCount: number
  highlight?: string
  createdAt: string
}

export function getDocumentDetail(kbId: number, docId: number) {
  return request.get<DocumentDetail>(`/knowledge-bases/${kbId}/documents/${docId}`)
}

export function getDocumentSegments(
  kbId: number,
  docId: number,
  params?: { skip?: number; limit?: number; keyword?: string }
) {
  return request.get<{ total: number; segments: DocumentSegment[] }>(
    `/knowledge-bases/${kbId}/documents/${docId}/segments`,
    { params }
  )
}

export function buildIndex(kbId: number) {
  return request.post<{ indexedDocuments: number }>(`/knowledge-bases/${kbId}/build-index`)
}

export function queryKnowledge(kbId: number, data: KnowledgeQuery) {
  return request.post<KnowledgeAnswer>(`/knowledge-bases/${kbId}/query`, data)
}
