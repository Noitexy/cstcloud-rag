<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import ControlBar from '@/components/ControlBar.vue'
import ChatWorkspace from '@/components/ChatWorkspace.vue'
import TelemetryPanel from '@/components/TelemetryPanel.vue'
import DocumentManager from '@/components/DocumentManager.vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const documentsVisible = ref(false)
onMounted(() => store.initialize())
</script>

<template>
  <div class="app-shell" v-loading="store.loading" element-loading-background="rgba(3, 6, 13, .8)">
    <div class="grid-bg" /><div class="aurora aurora-one" /><div class="aurora aurora-two" /><div class="noise" />
    <AppSidebar @open-documents="documentsVisible = true" />
    <div class="center-column"><ControlBar /><ChatWorkspace @open-documents="documentsVisible = true" /></div>
    <TelemetryPanel />
    <DocumentManager v-model="documentsVisible" />
  </div>
</template>
