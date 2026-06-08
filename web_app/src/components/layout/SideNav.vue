<template>
  <nav class="flex h-full min-h-0 flex-col">
    <div class="min-w-0 px-3 py-3">
      <div class="flex min-w-0 items-center gap-3 rounded-lg px-2 py-2">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)] text-sm font-black text-[var(--color-accent-strong)]">
          ARD
        </div>
        <div class="min-w-0">
          <div class="truncate text-sm font-bold text-[var(--color-ink)]">AI 报账文档生成</div>
          <div class="mt-0.5 truncate text-xs text-[var(--color-ink-soft)]">{{ modeLabel }}</div>
        </div>
      </div>
    </div>

    <div class="min-h-0 flex-1 overflow-y-auto px-3 py-2">
      <p class="px-2 text-xs font-semibold text-[var(--color-ink-soft)]">工作台</p>
      <div class="mt-2 space-y-1">
        <RouterLink
          v-for="item in primaryItems"
          :key="item.to"
          :to="item.to"
          :class="navClass(item)"
          @click="$emit('navigate')"
        >
          <component :is="item.icon" class="h-4 w-4 shrink-0" />
          <span class="min-w-0 truncate">{{ item.label }}</span>
        </RouterLink>
        <div>
          <button
            type="button"
            :class="previewParentClass"
            :aria-expanded="previewOpen"
            aria-controls="preview-nav-children"
            @click="previewOpen = !previewOpen"
          >
            <DocumentMagnifyingGlassIcon class="h-4 w-4 shrink-0" />
            <span class="min-w-0 flex-1 truncate text-left">预览</span>
            <ChevronDownIcon :class="['h-4 w-4 shrink-0 transition-transform', previewOpen ? '' : '-rotate-90']" />
          </button>
          <div v-show="previewOpen" id="preview-nav-children" class="mt-1 space-y-1 pl-6">
            <RouterLink
              v-for="item in previewItems"
              :key="item.to"
              :to="item.to"
              :class="childNavClass(item)"
              @click="$emit('navigate')"
            >
              <span class="min-w-0 truncate">{{ item.label }}</span>
            </RouterLink>
          </div>
        </div>
      </div>

      <div class="mt-6 border-t border-[var(--color-rule)] pt-4">
        <p class="px-2 text-xs font-semibold text-[var(--color-ink-soft)]">高级工具</p>
        <div class="mt-2 space-y-1">
          <RouterLink
            v-for="item in visibleSecondaryItems"
            :key="item.to"
            :to="item.to"
            :class="navClass(item)"
            @click="$emit('navigate')"
          >
            <component :is="item.icon" class="h-4 w-4 shrink-0" />
            <span class="min-w-0 truncate">{{ item.label }}</span>
          </RouterLink>
        </div>
      </div>
    </div>

    <div class="border-t border-[var(--color-rule)] px-3 py-3">
      <div class="rounded-lg bg-[var(--color-surface-muted)] px-3 py-2">
        <div class="flex items-center justify-between gap-3 text-xs">
          <span class="text-[var(--color-ink-muted)]">后端</span>
          <span :class="['inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-semibold', backendStatusClass]">
            <span class="h-1.5 w-1.5 rounded-full" :class="backendDotClass" />
            {{ backendStatusText }}
          </span>
        </div>
        <div class="mt-2 flex items-center justify-between gap-3 text-xs text-[var(--color-ink-soft)]">
          <span>v{{ version }}</span>
          <slot name="account" />
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  ChevronDownIcon,
  ClockIcon,
  Cog6ToothIcon,
  DocumentMagnifyingGlassIcon,
  HomeIcon,
  KeyIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/vue/24/outline'

interface NavItem {
  label: string
  to: string
  icon: object
  match: (path: string) => boolean
}

const props = defineProps<{
  modeLabel: string
  version: string
  backendStatusText: string
  backendStatusClass: string
  backendDotClass: string
  showPromptDebug: boolean
}>()

defineEmits<{ navigate: [] }>()

const route = useRoute()

const primaryItems: NavItem[] = [
  { label: '生成', to: '/', icon: HomeIcon, match: path => path === '/' || path === '/static/dist/' },
  { label: '历史', to: '/history', icon: ClockIcon, match: path => path.startsWith('/history') },
  { label: '配置', to: '/config', icon: Cog6ToothIcon, match: path => path.startsWith('/config') },
]

const previewItems: NavItem[] = [
  { label: 'FPA 预览', to: '/preview/fpa', icon: DocumentMagnifyingGlassIcon, match: path => path.startsWith('/preview/fpa') || path.startsWith('/sessions/') || path.startsWith('/static/dist/sessions/') },
  { label: 'COSMIC 预览', to: '/preview/cosmic', icon: DocumentMagnifyingGlassIcon, match: path => path.startsWith('/preview/cosmic') },
  { label: 'SPEC 预览', to: '/preview/spec', icon: DocumentMagnifyingGlassIcon, match: path => path.startsWith('/preview/spec') },
]

const secondaryItems: NavItem[] = [
  { label: '授权', to: '/license', icon: KeyIcon, match: path => path.startsWith('/license') },
  { label: '提示词调试', to: '/prompt-debug', icon: WrenchScrewdriverIcon, match: path => path.startsWith('/prompt-debug') },
]

const activePath = computed(() => route.path)
const previewOpen = ref(isPreviewPath(activePath.value))
const previewActive = computed(() => isPreviewPath(activePath.value))
const visibleSecondaryItems = computed(() => (
  secondaryItems.filter(item => item.to !== '/prompt-debug' || props.showPromptDebug)
))

watch(activePath, path => {
  if (isPreviewPath(path)) {
    previewOpen.value = true
  }
})

function isPreviewPath(path: string): boolean {
  return path.startsWith('/preview') || path.startsWith('/sessions/') || path.startsWith('/static/dist/sessions/')
}

const previewParentClass = computed(() => [
  'flex w-full min-w-0 items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors',
  previewActive.value
    ? 'bg-[var(--color-accent-soft)] font-semibold text-[var(--color-accent-strong)]'
    : 'text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-ink)]',
])

function navClass(item: NavItem) {
  const active = item.match(activePath.value)
  return [
    'flex min-w-0 items-center gap-2 rounded-md px-2.5 py-2 text-sm transition-colors',
    active
      ? 'bg-[var(--color-accent-soft)] font-semibold text-[var(--color-accent-strong)]'
      : 'text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-ink)]',
  ]
}

function childNavClass(item: NavItem) {
  const active = item.match(activePath.value)
  return [
    'flex min-w-0 items-center rounded-md px-2.5 py-1.5 text-sm transition-colors',
    active
      ? 'bg-[var(--color-accent-soft)] font-semibold text-[var(--color-accent-strong)]'
      : 'text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-ink)]',
  ]
}
</script>
