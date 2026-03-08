import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '@/views/Dashboard/index.vue'
import Terminal from '@/views/Terminal/index.vue'
import FileManager from '@/views/FileManager/index.vue'
import DeviceDetail from '@/views/DeviceDetail.vue'

const routes = [
  { 
    path: '/', 
    component: Dashboard,
    meta: { title: '仪表盘' }
  },
  { 
    path: '/terminal/:deviceId?', 
    component: Terminal,
    meta: { title: '终端' }
  },
  { 
    path: '/filemanager/:deviceId?', 
    component: FileManager,
    meta: { title: '文件管理' }
  },
  { 
    path: '/device/:id', 
    component: DeviceDetail,
    meta: { title: '设备详情' }
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router