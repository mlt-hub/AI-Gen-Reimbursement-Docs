import { ref, computed } from 'vue'
import { defineStore } from 'pinia'

export type WorkMode = 'local' | 'remote'
export type PipelineMode = 'from-excel-gen-all' | 'from-excel-gen-basedata' |
  'from-excel-gen-fpa' | 'from-excel-gen-cosmic' |
  'from-excel-gen-list' | 'from-excel-gen-spec'

export const useConfigStore = defineStore('config', () => {
  const workMode = ref<WorkMode>('local')
  const pipelineMode = ref<PipelineMode>('from-excel-gen-all')
  const xlsxPath = ref('')
  const outputDir = ref('')
  const apiKey = ref('')
  const model = ref('')
  const baseUrl = ref('')
  const maxTokens = ref('')
  const projectName = ref('')
  const clean = ref(false)
  const selectedFile = ref<File | null>(null)

  const isValid = computed(() => {
    if (workMode.value === 'local') return xlsxPath.value.trim().length > 0
    return selectedFile.value !== null
  })

  function reset() {
    xlsxPath.value = ''
    outputDir.value = ''
    apiKey.value = ''
    model.value = ''
    baseUrl.value = ''
    maxTokens.value = ''
    projectName.value = ''
    clean.value = false
    selectedFile.value = null
  }

  return { workMode, pipelineMode, xlsxPath, outputDir, apiKey, model, baseUrl,
           maxTokens, projectName, clean, selectedFile, isValid, reset }
})
