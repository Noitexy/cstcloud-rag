import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { api, errorMessage, streamChat } from '@/api/client'
import type {
  AppConfig,
  ChatMessage,
  Conversation,
  DocumentItem,
  KnowledgeBase,
  ModelInfo,
  ModelsResponse,
  RuntimeMetrics,
} from '@/types'

const defaultConfig: AppConfig = {
  chat_model: 'deepseek-v4-flash',
  embedding_model: 'bge-large-zh:latest',
  rerank_model: 'bge-reranker-v2-m3',
  temperature: 0.7,
  top_p: 0.9,
  max_length: 4096,
  top_k: 12,
  rerank_top_n: 5,
  chunk_size: 800,
  chunk_overlap: 120,
  stream: true,
  enable_rag: true,
  enable_rerank: true,
  enable_hybrid_search: true,
  enable_query_rewrite: true,
  enable_thinking: false,
}

export const useAppStore = defineStore('app', () => {
  const config = ref<AppConfig>({ ...defaultConfig })
  const modelResponse = ref<ModelsResponse>({ data: [], source: 'fallback', api_key_configured: false })
  const knowledgeBases = ref<KnowledgeBase[]>([])
  const documents = ref<DocumentItem[]>([])
  const conversations = ref<Conversation[]>([])
  const messages = ref<ChatMessage[]>([])
  const selectedKnowledgeBaseId = ref<string>()
  const selectedConversationId = ref<string>()
  const loading = ref(true)
  const generating = ref(false)
  const uploadProgress = ref(0)
  const metrics = ref<RuntimeMetrics>({ retrieval_ms: 0, generation_ms: 0, total_ms: 0, hit_count: 0 })
  let abortController: AbortController | undefined

  const selectedKnowledgeBase = computed(() =>
    knowledgeBases.value.find((item) => item.id === selectedKnowledgeBaseId.value),
  )
  const models = computed<ModelInfo[]>(() => modelResponse.value.data)

  async function initialize() {
    loading.value = true
    try {
      const [remoteConfig, remoteModels, kbs, convs] = await Promise.all([
        api.config(), api.models(), api.knowledgeBases(), api.conversations(),
      ])
      config.value = remoteConfig
      modelResponse.value = remoteModels
      knowledgeBases.value = kbs
      conversations.value = convs
      if (kbs.length) await selectKnowledgeBase(kbs[0].id)
      if (convs.length) await selectConversation(convs[0].id)
    } catch (error) {
      ElMessage.error(`初始化失败：${errorMessage(error)}`)
    } finally {
      loading.value = false
    }
  }

  async function refreshModels() {
    modelResponse.value = await api.models()
    ElMessage.success(modelResponse.value.source === 'remote' ? '模型列表已从科技云刷新' : '已载入内置候选模型')
  }

  async function saveConfig() {
    config.value = await api.saveConfig(config.value)
  }

  async function refreshKnowledgeBases() {
    knowledgeBases.value = await api.knowledgeBases()
  }

  async function selectKnowledgeBase(id?: string) {
    selectedKnowledgeBaseId.value = id
    documents.value = id ? await api.documents(id) : []
  }

  async function createKnowledgeBase(name: string, description: string) {
    const kb = await api.createKnowledgeBase({ name, description, embedding_model: config.value.embedding_model })
    await refreshKnowledgeBases()
    await selectKnowledgeBase(kb.id)
    ElMessage.success('知识库已创建')
  }

  async function removeKnowledgeBase(id: string) {
    await api.deleteKnowledgeBase(id)
    if (selectedKnowledgeBaseId.value === id) selectedKnowledgeBaseId.value = undefined
    await refreshKnowledgeBases()
    if (!selectedKnowledgeBaseId.value && knowledgeBases.value.length) await selectKnowledgeBase(knowledgeBases.value[0].id)
  }

  async function upload(file: File) {
    if (!selectedKnowledgeBaseId.value) throw new Error('请先创建或选择知识库')
    uploadProgress.value = 1
    const result = await api.uploadDocument(selectedKnowledgeBaseId.value, file, (value) => (uploadProgress.value = value))
    uploadProgress.value = 0
    await Promise.all([selectKnowledgeBase(selectedKnowledgeBaseId.value), refreshKnowledgeBases()])
    if (result.status === 'failed') throw new Error(result.error_message || '文档索引失败')
    ElMessage.success(`已完成 ${result.chunk_count} 个切片的索引`)
  }

  async function removeDocument(id: string) {
    await api.deleteDocument(id)
    await Promise.all([selectKnowledgeBase(selectedKnowledgeBaseId.value), refreshKnowledgeBases()])
  }

  async function reindexDocument(id: string) {
    const result = await api.reindexDocument(id)
    await selectKnowledgeBase(selectedKnowledgeBaseId.value)
    if (result.status === 'failed') throw new Error(result.error_message || '重建索引失败')
  }

  async function rebuildKnowledgeBase() {
    if (!selectedKnowledgeBaseId.value) return
    await api.rebuildKnowledgeBase(selectedKnowledgeBaseId.value, config.value.embedding_model)
    await Promise.all([selectKnowledgeBase(selectedKnowledgeBaseId.value), refreshKnowledgeBases()])
    ElMessage.success('知识库已使用新 Embedding 模型完成重建')
  }

  async function refreshConversations() {
    conversations.value = await api.conversations()
  }

  async function newConversation() {
    const conversation = await api.createConversation(selectedKnowledgeBaseId.value)
    await refreshConversations()
    await selectConversation(conversation.id)
  }

  async function selectConversation(id?: string) {
    selectedConversationId.value = id
    messages.value = id ? await api.messages(id) : []
    const conversation = conversations.value.find((item) => item.id === id)
    if (conversation?.knowledge_base_id && conversation.knowledge_base_id !== selectedKnowledgeBaseId.value) {
      await selectKnowledgeBase(conversation.knowledge_base_id)
    }
  }

  async function removeConversation(id: string) {
    await api.deleteConversation(id)
    if (selectedConversationId.value === id) {
      selectedConversationId.value = undefined
      messages.value = []
    }
    await refreshConversations()
  }

  async function sendMessage(text: string) {
    const value = text.trim()
    if (!value || generating.value) return
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: value, citations: [] }
    const answer: ChatMessage = {
      id: crypto.randomUUID(), role: 'assistant', content: '', reasoning: '', citations: [], streaming: true,
      model: config.value.chat_model,
    }
    messages.value.push(userMessage, answer)
    generating.value = true
    abortController = new AbortController()
    try {
      await streamChat(
        {
          message: value,
          conversation_id: selectedConversationId.value,
          knowledge_base_id: selectedKnowledgeBaseId.value,
          config: config.value,
        },
        {
          onEvent(event, data) {
            if (event === 'meta') {
              selectedConversationId.value = String(data.conversation_id)
              answer.model = String(data.model)
            } else if (event === 'retrieval') {
              answer.citations = (data.citations || []) as ChatMessage['citations']
              metrics.value.retrieval_ms = Number(data.retrieval_ms || 0)
              metrics.value.hit_count = Number(data.hit_count || 0)
            } else if (event === 'reasoning') {
              answer.reasoning = (answer.reasoning || '') + String(data.content || '')
            } else if (event === 'token') {
              answer.content += String(data.content || '')
            } else if (event === 'done') {
              answer.id = String(data.message_id)
              metrics.value.generation_ms = Number(data.generation_ms || 0)
              metrics.value.total_ms = Number(data.total_ms || 0)
            }
          },
        },
        abortController.signal,
      )
      await refreshConversations()
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        const detail = errorMessage(error)
        answer.content ||= `> 请求失败：${detail}`
        ElMessage.error(detail)
      }
    } finally {
      answer.streaming = false
      generating.value = false
      abortController = undefined
    }
  }

  function stopGeneration() { abortController?.abort() }

  return {
    config, modelResponse, models, knowledgeBases, documents, conversations, messages, selectedKnowledgeBaseId,
    selectedConversationId, selectedKnowledgeBase, loading, generating, uploadProgress, metrics, initialize,
    refreshModels, saveConfig, refreshKnowledgeBases, selectKnowledgeBase, createKnowledgeBase,
    removeKnowledgeBase, upload, removeDocument, reindexDocument, rebuildKnowledgeBase,
    refreshConversations, newConversation, selectConversation, removeConversation, sendMessage, stopGeneration,
  }
})
