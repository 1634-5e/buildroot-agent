<script setup lang="ts">
// 告警中心 - 占位
import Card from 'primevue/card'
import Button from 'primevue/button'
</script>

<template>
  <div class="alerts-page">
    <Card>
      <template #title>告警中心</template>
      <template #content>
        <div class="text-center py-12 text-secondary">
          <i class="pi pi-bell text-4xl mb-4 block"></i>
          <p>暂无告警</p>
          <p class="text-sm mt-2">设备异常时会在此显示告警信息</p>
        </div>
      </template>
    </Card>
  </div>
</template>