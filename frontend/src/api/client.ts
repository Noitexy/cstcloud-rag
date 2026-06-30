import axios from 'axios'
import type {
  AppConfig,
  Chunk,
  Conversation,
  DocumentItem,
  KnowledgeBase,
  ModelsResponse,
  StreamCallbacks,
} from '@/types'

const http = axios.create({ baseURL: '/api', timeout: 180_000 })

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) return error.response?.data?.detail || error.message
  return error instanceof Error ? error.message : String(error)
}

export const api = {
  models: () => http.get<ModelsResponse>('/models').then((r) => r.data),
  config: () => http.get<AppConfig>('/config').then((r) => r.data),
  saveConfig: (payload: AppConfig) => http.post<AppConfig>('/config', payload).then((r) => r.data),
  knowledgeBases: () => http.get<KnowledgeBase[]>('/knowledge-bases').then((r) => r.data),
  createKnowledgeBase: (payload: { name: string; description?: string; embedding_model?: string }) =>
    http.post<KnowledgeBase>('/knowledge-bases', payload).then((r) => r.data),
  deleteKnowledgeBase: (id: string) => http.delete(`/knowledge-bases/${id}`),
  rebuildKnowledgeBase: (id: string, embeddingModel: string) =>
    http.post<KnowledgeBase>(`/knowledge-bases/${id}/reindex`, undefined, { params: { embedding_model: embeddingModel } }).then((r) => r.data),
  documents: (kbId: string) => http.get<DocumentItem[]>(`/knowledge-bases/${kbId}/documents`).then((r) => r.data),
  uploadDocument: (kbId: string, file: File, onProgress?: (percent: number) => void) => {
    const body = new FormData()
    body.append('file', file)
    return http.post<DocumentItem>(`/knowledge-bases/${kbId}/documents/upload`, body, {
      onUploadProgress: (event) => onProgress?.(event.total ? Math.round((event.loaded / event.total) * 100) : 0),
    }).then((r) => r.data)
  },
  deleteDocument: (id: string) => http.delete(`/documents/${id}`),
  reindexDocument: (id: string) => http.post<DocumentItem>(`/documents/${id}/reindex`).then((r) => r.data),
  chunks: (id: string) => http.get<Chunk[]>(`/documents/${id}/chunks`).then((r) => r.data),
  conversations: () => http.get<Conversation[]>('/conversations').then((r) => r.data),
  createConversation: (knowledgeBaseId?: string) =>
    http.post<Conversation>('/conversations', { title: '新对话', knowledge_base_id: knowledgeBaseId }).then((r) => r.data),
  messages: (id: string) => http.get(`/conversations/${id}/messages`).then((r) => r.data),
  deleteConversation: (id: string) => http.delete(`/conversations/${id}`),
}

export async function streamChat(
  payload: { message: string; conversation_id?: string; knowledge_base_id?: string; config?: Partial<AppConfig> },
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `请求失败 (${response.status})`)
  }
  if (!response.body) throw new Error('浏览器未收到流式响应')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      let event = 'message'
      const dataLines: string[] = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) continue
      const data = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
      if (event === 'error') throw new Error(String(data.message || '流式请求失败'))
      callbacks.onEvent(event, data)
    }
    if (done) break
  }
}
