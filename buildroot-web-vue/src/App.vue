<template>
  <div class="app-layout">
    <!-- 顶部导航栏 -->
    <header class="topbar">
      <div class="topbar-left">
        <h1 class="logo">
          <span class="logo-icon">🏗️</span>
          <span class="logo-text">Buildroot Agent</span>
        </h1>
      </div>
      
      <nav class="topbar-nav">
        <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
          <span class="nav-icon">📊</span>
          <span class="nav-text">监控</span>
        </router-link>
        <router-link to="/terminal" class="nav-item">
          <span class="nav-icon">💻</span>
          <span class="nav-text">终端</span>
          <span class="nav-badge" v-if="terminalTabsCount > 0">{{ terminalTabsCount }}</span>
        </router-link>
        <router-link to="/filemanager" class="nav-item">
          <span class="nav-icon">📁</span>
          <span class="nav-text">文件</span>
          <span class="nav-badge" v-if="fileManagerTabsCount > 0">{{ fileManagerTabsCount }}</span>
        </router-link>
      </nav>
      
      <div class="topbar-right">
        <span class="status-item">
          <span class="status-dot online"></span>
          {{ onlineDevicesCount }} 设备在线
        </span>
      </div>
    </header>
    
    <!-- 标签栏 -->
    <TabBar v-if="showTabs" />
    
    <!-- 主内容区 -->
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useDeviceStore } from '@/stores/device'
import { useTabStore } from '@/stores/tabs'
import TabBar from '@/components/TabBar.vue'

const route = useRoute()
const deviceStore = useDeviceStore()
const tabStore = useTabStore()

const onlineDevicesCount = computed(() => deviceStore.onlineDevices.length)
const terminalTabsCount = computed(() => tabStore.terminalTabs.length)
const fileManagerTabsCount = computed(() => tabStore.fileManagerTabs.length)
const showTabs = computed(() => tabStore.tabs.length > 0 && route.path !== '/')

onMounted(() => {
  deviceStore.fetchDevices()
})
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: #0d1117;
  color: #c9d1d9;
}

/* 顶部导航栏 */
.topbar {
  height: 50px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 20px;
}

.topbar-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  color: #f0f6fc;
}

.topbar-nav {
  display: flex;
  gap: 4px;
  flex: 1;
  justify-content: center;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  color: #8b949e;
  text-decoration: none;
  border-radius: 6px;
  transition: all 0.2s;
  position: relative;
}

.nav-item:hover {
  background: #21262d;
  color: #c9d1d9;
}

.nav-item.router-link-active {
  background: #21262d;
  color: #f0f6fc;
}

.nav-icon {
  font-size: 16px;
}

.nav-text {
  font-size: 14px;
}

.nav-badge {
  background: #238636;
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #8b949e;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-dot.online {
  background: #238636;
  box-shadow: 0 0 4px #238636;
}

.main-content {
  flex: 1;
  overflow: hidden;
}
</style>