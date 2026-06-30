<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ClipboardPaste, Eye, FileArchive, FileUp, RefreshCcw, Trash2, UploadCloud, X } from 'lucide-vue-next'
import { api, errorMessage } from '@/api/client'
import { useAppStore } from '@/stores/app'
import type { Chunk } from '@/types'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
const store = useAppStore()
const input = ref<HTMLInputElement>()
const chunks = ref<Chunk[]>([])
const chunksVisible = ref(false)
const busyId = ref<string>()
const pasteVisible = ref(false)
const pastedTitle = ref('')
const pastedText = ref('')
const pasting = ref(false)

async function choose(event: Event) {
  const files = Array.from((event.target as HTMLInputElement).files || [])
  if (!files.length) return
  try {
    for (const file of files) await store.upload(file)
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { if (input.value) input.value.value = '' }
}
async function importPastedText() {
  const content = pastedText.value.trim()
  if (!content) { ElMessage.warning('请先粘贴或输入正文内容'); return }
  const safeTitle = (pastedTitle.value.trim() || '粘贴文本').replace(/[\\/:*?"<>|]/g, '-')
  const file = new File([content], `${safeTitle}.txt`, { type: 'text/plain;charset=utf-8' })
  pasting.value = true
  try {
    await store.upload(file)
    pasteVisible.value = false
    pastedTitle.value = ''
    pastedText.value = ''
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { pasting.value = false }
}
async function remove(id: string) {
  await ElMessageBox.confirm('确定删除该文档及其全部向量切片？', '删除文档', { type: 'warning' })
  try { await store.removeDocument(id) } catch (error) { ElMessage.error(errorMessage(error)) }
}
async function reindex(id: string) {
  busyId.value = id
  try { await store.reindexDocument(id); ElMessage.success('索引重建完成') }
  catch (error) { ElMessage.error(errorMessage(error)) }
  finally { busyId.value = undefined }
}
async function inspect(id: string) {
  try { chunks.value = await api.chunks(id); chunksVisible.value = true } catch (error) { ElMessage.error(errorMessage(error)) }
}
function size(value: number) { return value > 1024 * 1024 ? `${(value / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, value / 1024).toFixed(0)} KB` }
</script>

<template>
  <el-drawer :model-value="modelValue" size="560px" class="document-drawer" :show-close="false" @update:model-value="emit('update:modelValue', $event)">
    <template #header>
      <div class="drawer-title"><div><span>DATA INGESTION</span><strong>{{ store.selectedKnowledgeBase?.name || '文档管理' }}</strong></div><button class="icon-button" @click="emit('update:modelValue', false)"><X :size="19" /></button></div>
    </template>
    <button class="upload-zone" :disabled="!store.selectedKnowledgeBaseId || store.uploadProgress > 0" @click="input?.click()">
      <UploadCloud :size="29" /><strong>{{ store.uploadProgress ? `上传与索引中 ${store.uploadProgress}%` : '直接上传文件并建立索引' }}</strong>
      <span>支持多选 · TXT · MD · PDF · DOCX · CSV · XLSX · 单文件最大 50 MB</span>
      <i v-if="store.uploadProgress" :style="{ width: `${store.uploadProgress}%` }" />
    </button>
    <input ref="input" type="file" hidden multiple accept=".txt,.md,.pdf,.docx,.csv,.xlsx" @change="choose" />
    <div class="quick-ingest-actions">
      <span>没有现成文件？可把网页、笔记或业务资料直接粘贴进来。</span>
      <button :disabled="!store.selectedKnowledgeBaseId" @click="pasteVisible = true"><ClipboardPaste :size="16" /> 粘贴文本建立知识</button>
    </div>
    <div class="document-summary"><span><FileArchive :size="15" /> {{ store.documents.length }} FILES</span><span>{{ store.selectedKnowledgeBase?.chunk_count || 0 }} CHUNKS</span><span>{{ store.selectedKnowledgeBase?.embedding_model }}</span></div>
    <div class="document-list">
      <div v-if="!store.documents.length" class="document-empty"><FileUp :size="32" /><strong>等待数据接入</strong><span>上传文档后会自动解析、切片并向量化</span></div>
      <article v-for="doc in store.documents" :key="doc.id" class="document-card">
        <div class="file-type">{{ doc.source_type.toUpperCase() }}</div>
        <div class="document-info"><strong>{{ doc.name }}</strong><span>{{ size(doc.file_size) }} · {{ doc.chunk_count }} chunks · {{ new Date(doc.created_at).toLocaleDateString() }}</span><small v-if="doc.error_message">{{ doc.error_message }}</small></div>
        <span class="doc-status" :class="doc.status">{{ doc.status }}</span>
        <div class="document-actions">
          <button title="查看切片" @click="inspect(doc.id)"><Eye :size="14" /></button>
          <button title="重建索引" :class="{ spinning: busyId === doc.id }" @click="reindex(doc.id)"><RefreshCcw :size="14" /></button>
          <button title="删除" @click="remove(doc.id)"><Trash2 :size="14" /></button>
        </div>
      </article>
    </div>

    <el-dialog v-model="chunksVisible" title="文档切片检查器" width="720px" append-to-body>
      <div class="chunk-list"><article v-for="chunk in chunks" :key="chunk.id"><header><b>#{{ chunk.chunk_index + 1 }}</b><span>{{ chunk.section_title || '未命名章节' }} · {{ chunk.page ? `P${chunk.page}` : 'N/A' }}</span></header><p>{{ chunk.content }}</p><code>{{ chunk.id }}</code></article></div>
    </el-dialog>

    <el-dialog
      v-model="pasteVisible"
      title="粘贴文本建立知识"
      width="min(640px, calc(100vw - 32px))"
      class="paste-dialog"
      append-to-body
      align-center
      :close-on-click-modal="false"
    >
      <label class="field-label">资料标题</label>
      <el-input v-model="pastedTitle" maxlength="120" placeholder="例如：产品售后服务规范" />
      <label class="field-label">正文内容</label>
      <el-input v-model="pastedText" type="textarea" :rows="12" maxlength="200000" show-word-limit placeholder="在这里粘贴网页、笔记、制度说明或其他纯文本……" />
      <div class="paste-note">系统会将内容保存为 TXT 文档，并自动完成解析、切片、向量化和索引。</div>
      <template #footer><el-button @click="pasteVisible = false">取消</el-button><el-button type="primary" :loading="pasting" :disabled="!pastedText.trim()" @click="importPastedText">导入并建立索引</el-button></template>
    </el-dialog>
  </el-drawer>
</template>
