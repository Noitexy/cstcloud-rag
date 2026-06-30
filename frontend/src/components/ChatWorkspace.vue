<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { ArrowUp, Bot, Brain, DatabaseZap, FileText, Square, UserRound } from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import type { Citation } from '@/types'

const emit = defineEmits<{ openDocuments: [] }>()
const store = useAppStore()
const draft = ref('')
const scrollArea = ref<HTMLElement>()
const activeCitation = ref<Citation>()
const citationVisible = ref(false)
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: true })
const suggestions = ['概括知识库中的核心内容', '提取文档中的关键数据与结论', '对比不同文档的主要差异']

const title = computed(() => store.selectedKnowledgeBase?.name || '通用智能问答')
const needsRagData = computed(() => !store.selectedKnowledgeBase || store.selectedKnowledgeBase.chunk_count === 0)
function render(content: string) { return DOMPurify.sanitize(markdown.render(content || '')) }
function openCitation(item: Citation) { activeCitation.value = item; citationVisible.value = true }
function submit() { const value = draft.value; draft.value = ''; store.sendMessage(value) }
function keydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); submit() }
}
watch(
  () => store.messages.map((item) => `${item.id}:${item.content.length}`).join('|'),
  async () => { await nextTick(); scrollArea.value?.scrollTo({ top: scrollArea.value.scrollHeight, behavior: 'smooth' }) },
)
</script>

<template>
  <main class="chat-workspace">
    <div class="workspace-heading">
      <div><span class="eyebrow"><i /> ACTIVE KNOWLEDGE CHANNEL</span><h1>{{ title }}</h1></div>
      <div class="context-badge" :class="{ empty: needsRagData }"><DatabaseZap :size="16" /><span>{{ store.selectedKnowledgeBase?.chunk_count || 0 }} 个知识切片</span></div>
    </div>

    <section v-if="needsRagData" class="rag-data-notice">
      <div class="rag-notice-icon"><DatabaseZap :size="20" /></div>
      <div>
        <strong>{{ store.selectedKnowledgeBase ? '当前知识库还没有专属数据' : '当前未选择知识库，RAG 尚未生效' }}</strong>
        <span v-if="store.selectedKnowledgeBase">上传你的 PDF、Word、Markdown、TXT、CSV 或 Excel，系统会自动解析、切片并建立向量索引。</span>
        <span v-else>此时回答来自通用大模型。请先在左侧创建知识库，再上传你的专属资料。</span>
      </div>
      <button v-if="store.selectedKnowledgeBase" @click="emit('openDocuments')">上传专属数据</button>
      <em v-else>步骤：创建知识库 → 上传文档 → 开始提问</em>
    </section>

    <div ref="scrollArea" class="message-scroll">
      <div v-if="!store.messages.length" class="welcome-state">
        <div class="orb-wrap"><div class="orb-ring" /><div class="ai-orb"><Brain :size="35" /></div></div>
        <span class="overline">CSTCLOUD KNOWLEDGE ENGINE</span>
        <h2>让企业知识，开始思考</h2>
        <p>RAG 数据就是你上传的专属文档。选择知识库后，我会完成混合检索、证据重排与可追溯回答。</p>
        <div class="suggestions">
          <button v-for="item in suggestions" :key="item" @click="draft = item; submit()"><span>↗</span>{{ item }}</button>
        </div>
      </div>

      <article v-for="message in store.messages" :key="message.id" class="message" :class="message.role">
        <div class="avatar"><UserRound v-if="message.role === 'user'" :size="18" /><Bot v-else :size="19" /></div>
        <div class="message-body">
          <div class="message-meta">
            <strong>{{ message.role === 'user' ? 'YOU' : 'CSTCloud AI' }}</strong>
            <span v-if="message.model">{{ message.model }}</span>
            <i v-if="message.streaming">GENERATING</i>
          </div>
          <details v-if="message.reasoning" class="reasoning-block">
            <summary><Brain :size="14" /> 思考过程</summary><div>{{ message.reasoning }}</div>
          </details>
          <div class="markdown-body" v-html="render(message.content)" />
          <span v-if="message.streaming" class="stream-cursor" />
          <div v-if="message.citations?.length" class="citation-list">
            <button v-for="citation in message.citations" :key="citation.chunk_id" @click="openCitation(citation)">
              <span class="citation-index">{{ citation.index }}</span>
              <span><b>{{ citation.file_name }}</b><small>{{ citation.page ? `第 ${citation.page} 页` : '页码未知' }} · score {{ (citation.rerank_score ?? citation.score ?? 0).toFixed(3) }}</small></span>
              <FileText :size="15" />
            </button>
          </div>
        </div>
      </article>
    </div>

    <div class="composer-shell">
      <div class="composer-glow" />
      <textarea v-model="draft" rows="1" :disabled="store.generating" placeholder="向知识库提问，支持多轮追问…" @keydown="keydown" />
      <div class="composer-footer">
        <div class="active-flags">
          <span :class="{ on: store.config.enable_rag }">RAG</span><span :class="{ on: store.config.enable_rerank }">RERANK</span>
          <em>Shift + Enter 换行</em>
        </div>
        <button v-if="store.generating" class="send-button stop" @click="store.stopGeneration"><Square :size="14" /></button>
        <button v-else class="send-button" :disabled="!draft.trim()" @click="submit"><ArrowUp :size="19" /></button>
      </div>
    </div>

    <el-drawer v-model="citationVisible" title="证据切片" size="430px" class="citation-drawer">
      <template v-if="activeCitation">
        <div class="source-identity"><FileText :size="20" /><div><strong>{{ activeCitation.file_name }}</strong><span>{{ activeCitation.page ? `第 ${activeCitation.page} 页` : '页码未知' }}</span></div></div>
        <div class="score-grid"><span>融合分数<b>{{ activeCitation.score?.toFixed(4) || '—' }}</b></span><span>重排分数<b>{{ activeCitation.rerank_score?.toFixed(4) || '—' }}</b></span></div>
        <label class="field-label">CHUNK ID</label><code class="chunk-id">{{ activeCitation.chunk_id }}</code>
        <label class="field-label">原始内容</label><div class="chunk-content">{{ activeCitation.content }}</div>
      </template>
    </el-drawer>
  </main>
</template>
