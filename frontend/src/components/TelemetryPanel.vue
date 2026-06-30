<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Activity, Box, Cpu, Gauge, RefreshCcw } from 'lucide-vue-next'
import { useAppStore } from '@/stores/app'
import { errorMessage } from '@/api/client'

const store = useAppStore()
const mismatch = computed(() => store.selectedKnowledgeBase && store.selectedKnowledgeBase.embedding_model !== store.config.embedding_model)
async function persist() { try { await store.saveConfig() } catch (error) { ElMessage.error(errorMessage(error)) } }
async function rebuild() {
  await ElMessageBox.confirm('将删除旧向量集合，并使用当前 Embedding 模型重新向量化全部文档。', '重建索引', { type: 'warning' })
  try { await store.rebuildKnowledgeBase() } catch (error) { ElMessage.error(errorMessage(error)) }
}
</script>

<template>
  <aside class="telemetry-panel glass-panel">
    <div class="panel-heading"><div><Activity :size="16" /><span>检索控制台</span></div><em>LIVE</em></div>
    <section class="metric-hero">
      <span>SYSTEM LATENCY</span><strong>{{ store.metrics.total_ms ? (store.metrics.total_ms / 1000).toFixed(2) : '0.00' }}<small>s</small></strong>
      <div class="signal-bars"><i v-for="n in 18" :key="n" :style="{ height: `${15 + ((n * 17) % 28)}%` }" /></div>
    </section>
    <section class="telemetry-section">
      <div class="section-caption"><Gauge :size="14" /> RETRIEVAL PARAMETERS</div>
      <label class="range-field"><span>召回数量 <b>{{ store.config.top_k }}</b></span><el-slider v-model="store.config.top_k" :min="1" :max="40" @change="persist" /></label>
      <label class="range-field"><span>重排保留 <b>{{ store.config.rerank_top_n }}</b></span><el-slider v-model="store.config.rerank_top_n" :min="1" :max="15" @change="persist" /></label>
      <label class="range-field"><span>Temperature <b>{{ store.config.temperature.toFixed(1) }}</b></span><el-slider v-model="store.config.temperature" :min="0" :max="2" :step="0.1" @change="persist" /></label>
      <label class="range-field"><span>Top P <b>{{ store.config.top_p.toFixed(1) }}</b></span><el-slider v-model="store.config.top_p" :min="0.1" :max="1" :step="0.1" @change="persist" /></label>
      <label class="number-field"><span>MAX OUTPUT</span><el-input-number v-model="store.config.max_length" :min="128" :max="32768" :step="256" controls-position="right" @change="persist" /></label>
    </section>
    <section class="telemetry-section pipeline-section">
      <div class="section-caption"><Cpu :size="14" /> PIPELINE STATUS</div>
      <div class="pipeline-row"><span><i class="cyan" />Query Rewrite</span><b>{{ store.config.enable_query_rewrite ? 'ON' : 'OFF' }}</b></div>
      <div class="pipeline-row"><span><i class="violet" />Hybrid Search</span><el-switch v-model="store.config.enable_hybrid_search" size="small" @change="persist" /></div>
      <div class="pipeline-row"><span><i class="green" />Evidence Hits</span><b>{{ store.metrics.hit_count }}</b></div>
    </section>
    <section class="timing-grid">
      <div><span>检索</span><b>{{ store.metrics.retrieval_ms.toFixed(0) }}ms</b></div>
      <div><span>生成</span><b>{{ store.metrics.generation_ms.toFixed(0) }}ms</b></div>
    </section>
    <section v-if="mismatch" class="index-warning">
      <Box :size="17" /><div><strong>向量模型已变化</strong><span>当前知识库仍使用 {{ store.selectedKnowledgeBase?.embedding_model }}</span></div>
      <button @click="rebuild"><RefreshCcw :size="14" /> 重建</button>
    </section>
    <div class="panel-footnote"><i /> API KEY 仅保留在后端 · 文档片段会发送至所选云模型</div>
  </aside>
</template>
