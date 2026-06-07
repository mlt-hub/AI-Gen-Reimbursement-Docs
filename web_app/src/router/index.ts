import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import Login from '@/views/Login.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: Login,
      meta: { shell: false },
    },
    {
      path: '/',
      name: 'home',
      component: Home,
      meta: { nav: 'generate' },
    },
    {
      path: '/config',
      name: 'config',
      component: () => import('@/views/Config.vue'),
      meta: { nav: 'config' },
    },
    {
      path: '/license',
      name: 'license',
      component: () => import('@/views/License.vue'),
      meta: { nav: 'license' },
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('@/views/History.vue'),
      meta: { nav: 'history' },
    },
    {
      path: '/preview/fpa',
      name: 'preview-fpa',
      component: () => import('@/views/FpaPreviewPage.vue'),
      meta: { nav: 'preview' },
    },
    {
      path: '/sessions/:sessionId/fpa/debug',
      name: 'fpa-ai-debug',
      component: () => import('@/views/FpaAiDebugPage.vue'),
      meta: { nav: 'preview' },
    },
    {
      path: '/prompt-debug',
      name: 'prompt-debug',
      component: () => import('@/views/PromptDebug.vue'),
      meta: { nav: 'prompt-debug' },
    },
  ],
})

export default router
