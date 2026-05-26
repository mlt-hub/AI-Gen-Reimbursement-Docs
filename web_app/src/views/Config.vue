<template>
  <div class="max-w-3xl mx-auto p-6 space-y-8">
    <section>
      <h2 class="text-lg font-semibold mb-4">环境变量 (.env)</h2>
      <p class="text-sm text-gray-500 mb-3">管理 API Key、端点地址等环境配置。文件位置: ~/.ai-gen-reimbursement-docs/.env</p>
      <pre v-if="envContent" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ envContent }}</pre>
      <p v-else class="text-gray-400 text-sm">加载中…</p>
    </section>

    <section>
      <h2 class="text-lg font-semibold mb-4">系统配置 (system_config.yaml)</h2>
      <p class="text-sm text-gray-500 mb-3">文件位置: ~/.ai-gen-reimbursement-docs/system_config.yaml</p>
      <pre v-if="systemConfig" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ systemConfig }}</pre>
      <p v-else class="text-gray-400 text-sm">加载中…</p>
    </section>

    <section>
      <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
      <p class="text-sm text-gray-500 mb-3">文件位置: ~/.ai-gen-reimbursement-docs/business_rules.yaml</p>
      <pre v-if="businessRules" class="bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono">{{ businessRules }}</pre>
      <p v-else class="text-gray-400 text-sm">加载中…</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const envContent = ref('')
const systemConfig = ref('')
const businessRules = ref('')

onMounted(async () => {
  try {
    const resp = await fetch('/api/config-read')
    if (resp.ok) {
      const data = await resp.json()
      envContent.value = data.env || '（空）'
      systemConfig.value = data.system_config || '（空）'
      businessRules.value = data.business_rules || '（空）'
    }
  } catch (e) {
    envContent.value = '读取失败'
    systemConfig.value = '读取失败'
    businessRules.value = '读取失败'
  }
})
</script>
