/**
 * 路由配置
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/Dashboard/index.vue'),
    meta: { title: '仪表盘' },
  },
  {
    path: '/devices',
    name: 'devices',
    component: () => import('@/views/Devices/List.vue'),
    meta: { title: '设备列表' },
  },
  {
    path: '/devices/register',
    name: 'device-register',
    component: () => import('@/views/Devices/Register.vue'),
    meta: { title: '设备注册' },
  },
  {
    path: '/devices/:id',
    name: 'device-detail',
    component: () => import('@/views/Devices/Detail.vue'),
    meta: { title: '设备详情' },
  },
  {
    path: '/devices/:id/twin',
    name: 'device-twin',
    component: () => import('@/views/Devices/Twin.vue'),
    meta: { title: 'Twin 管理' },
  },
  {
    path: '/terminal/:deviceId?',
    name: 'terminal',
    component: () => import('@/views/Terminal/index.vue'),
    meta: { title: '终端' },
  },
  {
    path: '/files/:deviceId?',
    name: 'files',
    component: () => import('@/views/Files/index.vue'),
    meta: { title: '文件管理' },
  },
  {
    path: '/alerts',
    name: 'alerts',
    component: () => import('@/views/Alerts/index.vue'),
    meta: { title: '告警中心' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫 - 设置页面标题
router.beforeEach((to, _from, next) => {
  const title = to.meta.title as string
  document.title = title ? `${title} | Buildroot Agent` : 'Buildroot Agent'
  next()
})

export default router