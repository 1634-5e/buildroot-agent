<template>
  <div class="tab-bar" v-if="tabs.length > 0">
    <div 
      v-for="tab in tabs" 
      :key="tab.id"
      class="tab-item"
      :class="{ active: tab.id === activeTabId }"
      @click="setActiveTab(tab.id)"
    >
      <span class="tab-icon">
        {{ tab.type === 'terminal' ? '⌨️' : tab.type === 'filemanager' ? '📁' : '📱' }}
      </span>
      <span class="tab-title">{{ tab.deviceName }}</span>
      <button 
        v-if="tab.closable"
        class="tab-close"
        @click.stop="closeTab(tab.id)"
      >
        ×
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTabStore } from '@/stores/tabs'

const router = useRouter()
const tabStore = useTabStore()

const tabs = computed(() => tabStore.tabs)
const activeTabId = computed(() => tabStore.activeTabId)

function setActiveTab(tabId: string) {
  tabStore.setActiveTab(tabId)
  const tab = tabStore.tabs.find(t => t.id === tabId)
  if (tab) {
    router.push(`/${tab.type}/${tab.deviceId}`)
  }
}

function closeTab(tabId: string) {
  const newActiveId = tabStore.closeTab(tabId)
  if (newActiveId) {
    const tab = tabStore.tabs.find(t => t.id === newActiveId)
    if (tab) {
      router.push(`/${tab.type}/${tab.deviceId}`)
    }
  } else {
    router.push('/')
  }
}
</script>

<style scoped>
.tab-bar {
  display: flex;
  align-items: center;
  background: #181825;
  border-bottom: 1px solid #313244;
  padding: 0 8px;
  height: 36px;
  overflow-x: auto;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #1e1e2e;
  border: 1px solid #313244;
  border-radius: 4px 4px 0 0;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 120px;
  max-width: 200px;
}

.tab-item:hover {
  background: #313244;
}

.tab-item.active {
  background: #1e1e2e;
  border-bottom-color: #1e1e2e;
  background: linear-gradient(180deg, #313244 0%, #1e1e2e 100%);
}

.tab-icon {
  font-size: 12px;
}

.tab-title {
  font-size: 12px;
  color: #cdd6f4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.tab-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: none;
  background: transparent;
  color: #6c7086;
  cursor: pointer;
  border-radius: 2px;
  font-size: 14px;
  line-height: 1;
}

.tab-close:hover {
  background: #f38ba8;
  color: #1e1e2e;
}
</style>