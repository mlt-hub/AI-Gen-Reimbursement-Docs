<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-50 flex flex-col gap-2">
      <transition-group name="toast" tag="div" class="flex flex-col gap-2">
        <div v-for="t in toastStore.toasts" :key="t.id"
          :class="['px-4 py-3 rounded-lg shadow-lg text-sm font-medium flex items-center gap-2 min-w-[260px] max-w-sm',
            bgClass(t.type)]">
          <component :is="iconMap[t.type]" class="w-5 h-5 shrink-0" />
          <span class="flex-1">{{ t.message }}</span>
          <button @click="toastStore.remove(t.id)" class="text-current opacity-50 hover:opacity-100">&times;</button>
        </div>
      </transition-group>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { useToastStore, type ToastType } from '@/stores/toast'
import {
  CheckCircleIcon, ExclamationCircleIcon,
  InformationCircleIcon, ExclamationTriangleIcon,
} from '@heroicons/vue/24/solid'

const toastStore = useToastStore()

const iconMap: Record<ToastType, any> = {
  success: CheckCircleIcon,
  error: ExclamationCircleIcon,
  info: InformationCircleIcon,
  warning: ExclamationTriangleIcon,
}

const bgMap: Record<ToastType, string> = {
  success: 'bg-green-50 text-green-800 border border-green-200',
  error: 'bg-red-50 text-red-800 border border-red-200',
  info: 'bg-blue-50 text-blue-800 border border-blue-200',
  warning: 'bg-yellow-50 text-yellow-800 border border-yellow-200',
}

function bgClass(t: ToastType) { return bgMap[t] }
</script>

<style scoped>
.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from { opacity: 0; transform: translateX(30px); }
.toast-leave-to { opacity: 0; transform: translateX(30px); }
</style>
