<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { BrainCircuit, RefreshCw, SlidersHorizontal } from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/api/client'

const store = useAppStore()
const allIds = computed(() => store.models.map((item) => item.id))
const embeddingIds = computed(() => allIds.value.filter((id) => /embedding|bge-large|gte-qwen/i.test(id)))
const rerankIds = computed(() => allIds.value.filter((id) => /rerank/i.test(id)))
const chatIds = computed(() => allIds.value.filter((id) => !/embedding|rerank|bge-large|gte-qwen/i.test(id)))

async function persist() {
  try { await store.saveConfig() } catch (error) { ElMessage.error(errorMessage(error)) }
}
async function refresh() {
  try { await store.refreshModels() } catch (error) { ElMessage.error(errorMessage(error)) }
}
</script>

<template>
  <header class="control-bar glass-panel">
    <div class="model-control chat-model">
      <span class="control-icon"><BrainCircuit :size="17" /></span>
      <div><label>CHAT ENGINE</label>
        <el-select v-model="store.config.chat_model" filterable allow-create default-first-option @change="persist">
          <el-option v-for="id in chatIds" :key="id" :label="id" :value="id" />
        </el-select>
      </div>
    </div>
    <div class="model-control">
      <div><label>EMBEDDING</label>
        <el-select v-model="store.config.embedding_model" filterable allow-create @change="persist">
          <el-option v-for="id in embeddingIds" :key="id" :label="id" :value="id" />
        </el-select>
      </div>
    </div>
    <div class="model-control">
      <div><label>RERANKER</label>
        <el-select v-model="store.config.rerank_model" filterable allow-create @change="persist">
          <el-option v-for="id in rerankIds" :key="id" :label="id" :value="id" />
        </el-select>
      </div>
    </div>
    <div class="toggle-cluster">
      <label><span>RAG</span><el-switch v-model="store.config.enable_rag" @change="persist" /></label>
      <label><span>RERANK</span><el-switch v-model="store.config.enable_rerank" @change="persist" /></label>
      <label><span>REWRITE</span><el-switch v-model="store.config.enable_query_rewrite" @change="persist" /></label>
      <label><span>THINK</span><el-switch v-model="store.config.enable_thinking" @change="persist" /></label>
    </div>
    <button class="refresh-models" :class="{ warning: !store.modelResponse.api_key_configured }" @click="refresh">
      <RefreshCw :size="16" /><span>{{ store.modelResponse.source === 'remote' ? 'CLOUD SYNC' : 'LOCAL LIST' }}</span>
    </button>
    <SlidersHorizontal class="mobile-settings" :size="19" />
  </header>
</template>
