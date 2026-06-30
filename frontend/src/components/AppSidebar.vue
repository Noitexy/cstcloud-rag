<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { BookOpen, Database, FileUp, MessageSquarePlus, Plus, Trash2 } from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/api/client'

const emit = defineEmits<{ openDocuments: [] }>()
const store = useAppStore()
const createVisible = ref(false)
const name = ref('')
const description = ref('')

async function createKb() {
  if (!name.value.trim()) return
  try {
    await store.createKnowledgeBase(name.value, description.value)
    name.value = ''
    description.value = ''
    createVisible.value = false
    emit('openDocuments')
  } catch (error) { ElMessage.error(errorMessage(error)) }
}

async function removeKb(id: string) {
  await ElMessageBox.confirm('将同时删除文档、切片与向量索引，是否继续？', '删除知识库', { type: 'warning' })
  await store.removeKnowledgeBase(id)
}

async function removeConversation(id: string) {
  await store.removeConversation(id)
}
</script>

<template>
  <aside class="app-sidebar glass-panel">
    <div class="brand">
      <div class="brand-mark"><Database :size="22" /></div>
      <div><strong>CSTCloud<span>·RAG</span></strong><small>KNOWLEDGE INTELLIGENCE</small></div>
    </div>

    <button class="primary-action" @click="store.newConversation()">
      <MessageSquarePlus :size="17" /> 新建对话 <span>⌘ K</span>
    </button>

    <section class="sidebar-section conversations-section">
      <div class="section-title"><span>会话记录</span><em>{{ store.conversations.length }}</em></div>
      <div class="sidebar-scroll">
        <div v-if="!store.conversations.length" class="empty-mini">还没有对话，问点什么吧</div>
        <button
          v-for="item in store.conversations"
          :key="item.id"
          class="conversation-item"
          :class="{ active: store.selectedConversationId === item.id }"
          @click="store.selectConversation(item.id)"
        >
          <span class="pulse-dot" />
          <span class="truncate">{{ item.title }}</span>
          <Trash2 class="row-delete" :size="14" @click.stop="removeConversation(item.id)" />
        </button>
      </div>
    </section>

    <section class="sidebar-section kb-section">
      <div class="section-title">
        <span>知识空间</span>
        <button class="icon-button" title="新建知识库" @click="createVisible = true"><Plus :size="15" /></button>
      </div>
      <div class="kb-list">
        <div
          v-for="kb in store.knowledgeBases"
          :key="kb.id"
          class="kb-item"
          :class="{ active: store.selectedKnowledgeBaseId === kb.id }"
          @click="store.selectKnowledgeBase(kb.id)"
        >
          <div class="kb-icon"><BookOpen :size="17" /></div>
          <div class="kb-copy"><strong>{{ kb.name }}</strong><small>{{ kb.document_count }} 文档 · {{ kb.chunk_count }} 切片</small></div>
          <button class="row-delete icon-button" @click.stop="removeKb(kb.id)"><Trash2 :size="14" /></button>
        </div>
        <button v-if="!store.knowledgeBases.length" class="empty-kb" @click="createVisible = true">
          <Plus :size="18" /><span>创建第一个知识库</span>
        </button>
      </div>
    </section>

    <button class="document-button" :disabled="!store.selectedKnowledgeBaseId" @click="emit('openDocuments')">
      <FileUp :size="16" /><span>文档与索引管理</span><b>{{ store.documents.length }}</b>
    </button>
    <div class="sidebar-footer"><span class="status-led" /> CORE ONLINE <em>v1.0</em></div>

    <el-dialog
      v-model="createVisible"
      title="创建知识空间"
      width="min(500px, calc(100vw - 32px))"
      class="neon-dialog"
      append-to-body
      align-center
      :close-on-click-modal="false"
    >
      <div class="kb-create-flow" aria-label="创建知识库流程">
        <span class="active"><b>1</b> 创建知识库</span><i />
        <span><b>2</b> 导入资料</span><i />
        <span><b>3</b> 开始提问</span>
      </div>
      <label class="field-label">知识库名称</label>
      <el-input v-model="name" maxlength="200" placeholder="例如：产品技术文档" @keyup.enter="createKb" />
      <label class="field-label">描述</label>
      <el-input v-model="description" type="textarea" :rows="3" placeholder="这个知识库用于……" />
      <div class="embedding-note">将使用 <code>{{ store.config.embedding_model }}</code> 构建向量索引</div>
      <div class="kb-create-help">创建成功后会自动打开资料导入面板，可直接上传文件，也可粘贴一段文本。</div>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :disabled="!name.trim()" @click="createKb">创建并导入资料</el-button></template>
    </el-dialog>
  </aside>
</template>
