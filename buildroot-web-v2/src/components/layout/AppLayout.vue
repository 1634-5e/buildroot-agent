<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeviceStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const deviceStore = useDeviceStore()

const sidebarCollapsed = ref(false)

const onlineCount = computed(() => deviceStore.onlineDevices.length)
const totalCount = computed(() => deviceStore.devices.length)

const menuItems = [
  { path: '/', icon: 'pi pi-home', label: '仪表盘' },
  { path: '/devices', icon: 'pi pi-desktop', label: '设备管理' },
  { path: '/terminal', icon: 'pi pi-terminal', label: '终端' },
  { path: '/files', icon: 'pi pi-folder', label: '文件管理' },
  { path: '/alerts', icon: 'pi pi-bell', label: '告警中心' },
]

function isActive(path: string): boolean {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function navigate(path: string) {
  router.push(path)
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>

<template>
  <div class="app-layout flex h-screen bg-surface-950">
    <!-- 侧边栏 -->
    <aside 
      class="sidebar bg-surface-900 border-r border-surface-800 flex flex-col transition-all duration-300"
      :class="sidebarCollapsed ? 'w-16' : 'w-56'"
    >
      <!-- Logo -->
      <div class="sidebar-header h-14 flex items-center px-4 border-b border-surface-800">
        <span class="text-primary-400 text-xl">🏗️</span>
        <span v-if="!sidebarCollapsed" class="ml-2 font-semibold text-surface-100">
          Buildroot
        </span>
      </div>

      <!-- 导航菜单 -->
      <nav class="flex-1 py-4 px-2">
        <ul class="space-y-1">
          <li v-for="item in menuItems" :key="item.path">
            <button
              class="nav-item w-full flex items-center px-3 py-2.5 rounded-lg transition-colors"
              :class="isActive(item.path) 
                ? 'bg-primary-500/10 text-primary-400' 
                : 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'"
              @click="navigate(item.path)"
            >
              <i :class="item.icon" class="text-lg"></i>
              <span v-if="!sidebarCollapsed" class="ml-3 text-sm">{{ item.label }}</span>
            </button>
          </li>
        </ul>
      </nav>

      <!-- 底部状态 -->
      <div class="sidebar-footer p-4 border-t border-surface-800">
        <div v-if="!sidebarCollapsed" class="text-xs text-surface-500">
          <div class="flex items-center gap-2">
            <span class="status-dot status-dot--online"></span>
            <span>{{ onlineCount }}/{{ totalCount }} 在线</span>
          </div>
        </div>
        <div v-else class="flex justify-center">
          <span class="status-dot status-dot--online"></span>
        </div>
      </div>

      <!-- 折叠按钮 -->
      <button
        class="absolute -right-3 top-20 w-6 h-6 bg-surface-800 border border-surface-700 rounded-full flex items-center justify-center text-surface-400 hover:text-surface-200"
        @click="toggleSidebar"
      >
        <i :class="sidebarCollapsed ? 'pi pi-angle-right' : 'pi pi-angle-left'" class="text-xs"></i>
      </button>
    </aside>

    <!-- 主内容区 -->
    <div class="main-area flex-1 flex flex-col overflow-hidden">
      <!-- 顶部栏 -->
      <header class="h-14 bg-surface-900 border-b border-surface-800 flex items-center justify-between px-6">
        <h1 class="page-title">
          {{ route.meta.title || 'Buildroot Agent' }}
        </h1>
        <div class="flex items-center gap-4">
          <span class="text-secondary text-sm">
            {{ new Date().toLocaleDateString('zh-CN', { weekday: 'long', month: 'long', day: 'numeric' }) }}
          </span>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="flex-1 overflow-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  position: relative;
}

.nav-item {
  cursor: pointer;
  border: none;
  background: transparent;
  font-family: inherit;
}
</style>