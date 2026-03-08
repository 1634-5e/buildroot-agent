<template>
  <nav class="navbar">
    <div class="navbar-brand">Buildroot Agent</div>
    <ul class="nav-links">
      <li>
        <router-link to="/" class="nav-link" :class="{ active: isActive('/') }">
          <span class="icon">📊</span>
          <span>Dashboard</span>
        </router-link>
      </li>
      <li>
        <router-link to="/terminal" class="nav-link" :class="{ active: isActive('/terminal') }">
          <span class="icon">💻</span>
          <span>Terminal</span>
        </router-link>
      </li>
      <li>
        <router-link to="/filemanager" class="nav-link" :class="{ active: isActive('/filemanager') }">
          <span class="icon">📁</span>
          <span>FileManager</span>
        </router-link>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

function isActive(path: string): boolean {
  return route.path === path
}
</script>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
}

.navbar-brand {
  font-size: 20px;
  font-weight: 600;
  color: white;
  letter-spacing: 0.5px;
}

.nav-links {
  display: flex;
  list-style: none;
  margin: 0;
  padding: 0;
  gap: 8px;
}

.nav-links li {
  margin: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 8px;
  text-decoration: none;
  color: rgba(255, 255, 255, 0.8);
  transition: all 0.3s ease;
  font-size: 14px;
  font-weight: 500;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.15);
  color: white;
}

.nav-link.active {
  background: rgba(255, 255, 255, 0.25);
  color: white;
  font-weight: 600;
}

.icon {
  font-size: 18px;
}
</style>
