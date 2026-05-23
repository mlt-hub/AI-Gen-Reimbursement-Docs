import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: Home,
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('@/views/Config.vue'),
    },
    {
      path: '/prompt-debug',
      name: 'prompt-debug',
      component: () => import('@/views/PromptDebug.vue'),
    },
  ],
})

export default router
