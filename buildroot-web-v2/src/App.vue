<script setup lang="ts">
import { onMounted } from 'vue'
import AppLayout from '@/components/layout/AppLayout.vue'
import { useDeviceStore } from '@/stores'

const deviceStore = useDeviceStore()

onMounted(() => {
  // 初始化加载数据
  deviceStore.fetchDevices()
})
</script>

<template>
  <AppLayout />
</template>