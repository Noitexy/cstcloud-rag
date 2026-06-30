export interface ModelInfo { id: string; object?: string; owned_by?: string }
export interface ModelsResponse {
  data: ModelInfo[]
  source: 'remote' | 'fallback'
  api_key_configured: boolean
  warning?: string
}

export interface AppConfig {
  chat_model: string
  embedding_model: string
  rerank_model: string
  temperature: number
  top_p: number
  max_length: number
  top_k: number
  rerank_top_n: number
  chunk_size: number
  chunk_overlap: number
  stream: boolean
  enable_rag: boolean
  enable_rerank: boolean
  enable_hybrid_search: boolean
  enable_query_rewrite: boolean
  enable_thinking: boolean
}

export interface KnowledgeBase {
  id: string
  name: string
  description: string
  embedding_model: string
  created_at: string
  document_count: number
  chunk_count: number
}

export interface DocumentItem {
  id: string
  knowledge_base_id: string
  name: string
  source_type: string
  file_size: number
  status: 'processing' | 'ready' | 'failed'
  error_message?: string
  chunk_count: number
  created_at: string
}

export interface Chunk {
  id: string
  document_id: string
  chunk_index: number
  content: string
  page?: number
  section_title?: string
}

export interface Citation {
  index: number
  file_name: string
  page?: number
  chunk_id: string
  content: string
  score?: number
  rerank_score?: number
}

export interface ChatMessage {
  id: string
  conversation_id?: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  model?: string
  retrieval_ms?: number
  generation_ms?: number
  created_at?: string
  streaming?: boolean
  reasoning?: string
}

export interface Conversation {
  id: string
  title: string
  knowledge_base_id?: string
  created_at: string
  updated_at: string
}

export interface RuntimeMetrics {
  retrieval_ms: number
  generation_ms: number
  total_ms: number
  hit_count: number
}

export interface StreamCallbacks {
  onEvent: (event: string, data: Record<string, unknown>) => void
}
