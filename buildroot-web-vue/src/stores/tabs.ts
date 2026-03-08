import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Tab {
  id: string
  type: 'terminal' | 'filemanager' | 'device'
  deviceId: string
  deviceName: string
  title: string
  closable: boolean
}

export const useTabStore = defineStore('tabs', () => {
  const tabs = ref<Tab[]>([])
  const activeTabId = ref<string>('')

  // Computed
  const activeTab = computed(() => 
    tabs.value.find(t => t.id === activeTabId.value) || null
  )

  const terminalTabs = computed(() => 
    tabs.value.filter(t => t.type === 'terminal')
  )

  const fileManagerTabs = computed(() => 
    tabs.value.filter(t => t.type === 'filemanager')
  )

  // Actions
  function generateTabId(type: string, deviceId: string): string {
    return `${type}-${deviceId}`
  }

  function openTab(type: Tab['type'], deviceId: string, deviceName: string): Tab {
    const id = generateTabId(type, deviceId)
    
    // Check if tab already exists
    const existingTab = tabs.value.find(t => t.id === id)
    if (existingTab) {
      activeTabId.value = id
      return existingTab
    }

    // Create new tab
    const newTab: Tab = {
      id,
      type,
      deviceId,
      deviceName,
      title: `${type === 'terminal' ? '终端' : type === 'filemanager' ? '文件' : '设备'} - ${deviceName}`,
      closable: true,
    }

    tabs.value.push(newTab)
    activeTabId.value = id

    return newTab
  }

  function closeTab(tabId: string): string | null {
    const index = tabs.value.findIndex(t => t.id === tabId)
    if (index < 0) return null

    tabs.value.splice(index, 1)

    // If closing active tab, switch to another
    if (activeTabId.value === tabId) {
      if (tabs.value.length > 0) {
        // Switch to previous tab, or first tab
        const newIndex = Math.min(index, tabs.value.length - 1)
        activeTabId.value = tabs.value[newIndex].id
      } else {
        activeTabId.value = ''
      }
    }

    return activeTabId.value || null
  }

  function setActiveTab(tabId: string): void {
    if (tabs.value.find(t => t.id === tabId)) {
      activeTabId.value = tabId
    }
  }

  function updateTabTitle(tabId: string, title: string): void {
    const tab = tabs.value.find(t => t.id === tabId)
    if (tab) {
      tab.title = title
    }
  }

  function clearAllTabs(): void {
    tabs.value = []
    activeTabId.value = ''
  }

  return {
    tabs,
    activeTabId,
    activeTab,
    terminalTabs,
    fileManagerTabs,
    openTab,
    closeTab,
    setActiveTab,
    updateTabTitle,
    clearAllTabs,
  }
})