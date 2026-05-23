import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export interface StepState {
  key: string
  label: string
  state: 'pending' | 'active' | 'done'
}

const STEP_ORDER = ['basedata', 'fpa', 'spec', 'cosmic', 'list']
const STEP_LABELS: Record<string, string> = {
  basedata: '基础数据',
  fpa: 'FPA工作量评估',
  spec: '项目需求说明书',
  cosmic: '项目功能点拆分表',
  list: '项目需求清单',
}

export const useStepsStore = defineStore('steps', () => {
  const activeKey = ref<string | null>(null)
  const doneKeys = ref<Set<string>>(new Set())

  const steps = computed<StepState[]>(() => {
    return STEP_ORDER.map((key) => ({
      key,
      label: STEP_LABELS[key] || key,
      state: doneKeys.value.has(key) ? 'done' as const
           : activeKey.value === key ? 'active' as const
           : 'pending' as const,
    }))
  })

  function setActive(key: string) {
    // 将当前 active 标记为 done，新 key 设为 active
    if (activeKey.value && activeKey.value !== key) {
      doneKeys.value.add(activeKey.value)
    }
    activeKey.value = key
  }

  function finishAll() {
    if (activeKey.value) {
      doneKeys.value.add(activeKey.value)
      activeKey.value = null
    }
  }

  function reset() {
    activeKey.value = null
    doneKeys.value = new Set()
  }

  return { steps, setActive, finishAll, reset }
})
