import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// 安装 Pinia
const pinia = createPinia()
app.use(pinia)

// 安装 Router
app.use(router)

app.mount('#app')
