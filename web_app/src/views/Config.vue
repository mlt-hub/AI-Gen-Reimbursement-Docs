<template>
  <div class="mx-auto box-border w-full max-w-5xl space-y-6 overflow-x-hidden px-4 py-6 sm:px-6">
    <section class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-lg font-semibold">环境诊断</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">检查后端连接、版本、工作模式和关键能力状态。</p>
        </div>
        <button class="btn-secondary w-fit" :disabled="healthLoading" @click="refreshHealth">
          {{ healthLoading ? '检查中...' : '重新检查' }}
        </button>
      </div>

      <div class="grid min-w-0 gap-3 sm:grid-cols-2">
        <div v-for="item in diagnosticItems" :key="item.label" class="min-w-0 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2">
          <div class="flex min-w-0 items-center justify-between gap-3">
            <span class="min-w-0 text-sm text-[var(--color-ink-muted)]">{{ item.label }}</span>
            <span :class="['status-badge shrink-0', item.className]">{{ item.value }}</span>
          </div>
        </div>
      </div>

      <p v-if="healthError" class="mt-3 text-sm text-[var(--color-warning)]">{{ healthError }}</p>
      <p v-else-if="fpaRuntimeConfigMissingText" class="mt-3 text-sm text-[var(--color-warning)]">
        {{ fpaRuntimeConfigMissingText }}
      </p>
      <p v-else-if="healthCheckedAt" class="mt-3 text-xs text-[var(--color-ink-soft)]">最近检查：{{ healthCheckedAt }}</p>
    </section>

    <nav class="flex flex-wrap gap-2 border-b border-[var(--color-rule)] pb-3" aria-label="配置分区" role="tablist">
      <button
        v-for="section in configSectionTabs"
        :key="section.key"
        :id="configTabId(section.key)"
        type="button"
        role="tab"
        :aria-selected="activeConfigSection === section.key"
        :aria-controls="configPanelId(section.key)"
        :class="['nav-link', activeConfigSection === section.key ? 'nav-link-active' : '']"
        @click="activeConfigSection = section.key"
      >
        {{ section.label }}
      </button>
    </nav>

    <div
      :id="configPanelId(activeConfigSection)"
      :aria-labelledby="configTabId(activeConfigSection)"
      class="space-y-6"
      role="tabpanel"
    >
    <section v-if="activeConfigSection === 'common'" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">AI 配置</p>
          <h2 class="mt-1 text-lg font-semibold">模型与凭据</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="webConfigLoading || webConfigSaving" @click="loadWebConfig">
          {{ webConfigLoading ? '加载中...' : '刷新配置' }}
        </button>
      </div>

      <p v-if="webConfigError" class="text-sm text-[var(--color-warning)]">{{ webConfigError }}</p>
      <div v-else-if="webConfig" class="space-y-4">
        <div class="grid gap-3 md:grid-cols-2">
          <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-2">
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm text-[var(--color-ink-muted)]">API Key</span>
              <span :class="['status-badge', webConfig.ai.api_key_configured ? statusClass.ok : statusClass.warn]">
                {{ webConfig.ai.api_key_configured ? '已配置' : '未配置' }}
              </span>
            </div>
            <p class="mt-1 text-xs text-[var(--color-ink-soft)]">来源：{{ sourceLabel(webConfig.ai.api_key_source) }}</p>
          </div>

          <ConfigValueCard label="接口地址" :field="webConfig.ai.base_url" />
          <ConfigValueCard label="模型" :field="webConfig.ai.model" />
          <ConfigValueCard label="最大 Token 数" :field="webConfig.ai.max_tokens" />
          <ConfigValueCard label="共享系统 API Key" :field="webConfig.ai.allow_shared_ai_credentials" :format="formatEnabled" />
        </div>

        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
          <div class="grid gap-4 md:grid-cols-2">
            <div class="md:col-span-2">
              <label for="web-api-key" class="field-label text-xs">API Key</label>
              <input
                id="web-api-key"
                ref="webApiKeyInput"
                v-model.trim="webAiForm.apiKey"
                type="password"
                placeholder="留空保留已保存的 API Key"
                autocomplete="new-password"
                autocapitalize="off"
                autocorrect="off"
                spellcheck="false"
                data-lpignore="true"
                data-1p-ignore="true"
                :name="webApiKeyInputName"
                :readonly="webApiKeyReadonly"
                class="field-control"
                :disabled="webAiForm.clearApiKey"
                @focus="activateWebApiKeyInput"
                @pointerdown="activateWebApiKeyInput"
              />
            </div>

            <div>
              <label for="web-base-url" class="field-label text-xs">接口地址</label>
              <input id="web-base-url" v-model.trim="webAiForm.baseUrl" type="text" class="field-control" />
            </div>

            <div>
              <label for="web-model" class="field-label text-xs">模型</label>
              <input id="web-model" v-model.trim="webAiForm.model" type="text" class="field-control" />
            </div>

            <div>
              <label for="web-max-tokens" class="field-label text-xs">最大 Token 数</label>
              <input id="web-max-tokens" v-model.trim="webAiForm.maxTokens" type="text" class="field-control" />
            </div>

            <label class="flex cursor-pointer items-center gap-2 self-end text-sm text-[var(--color-ink-muted)]">
              <input
                v-model="webAiForm.clearApiKey"
                type="checkbox"
                class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]"
                @change="handleClearWebApiKeyChange"
              />
              清空已保存的 API Key
            </label>

            <label v-if="webConfig.scope.mode === 'local'" class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)] md:col-span-2">
              <input
                v-model="webAiForm.allowSharedAiCredentials"
                type="checkbox"
                class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]"
              />
              允许远程用户使用共享系统 API Key
            </label>
          </div>

          <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', webConfigSaveStatusClass]">{{ webConfigSaveStatusText }}</span>
            <button class="btn-primary w-fit" :disabled="webConfigSaving || !hasWebConfigChanges" @click="saveWebConfig">
              {{ webConfigSaving ? '保存中...' : '保存 AI 配置' }}
            </button>
          </div>
          <p v-if="webConfigSaveMsg" :class="['mt-2 text-sm', webConfigSaveOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ webConfigSaveMsg }}</p>
        </div>
      </div>
      <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中...</p>
    </section>

    <section v-if="activeConfigSection === 'common'" class="surface rounded-lg p-5">
      <div class="mb-4 border-b border-[var(--color-rule)] pb-4">
        <p class="text-xs font-semibold text-[var(--color-ink-soft)]">Web 与运行配置</p>
        <h2 class="mt-1 text-lg font-semibold">运行默认值</h2>
      </div>

      <p v-if="webConfigError" class="text-sm text-[var(--color-warning)]">{{ webConfigError }}</p>
      <div v-else-if="webConfig" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
        <div class="grid gap-4 md:grid-cols-2">
          <div>
            <label for="web-project-name" class="field-label text-xs">项目名称（留空自动读取）</label>
            <input id="web-project-name" v-model.trim="webRunForm.projectName" type="text" class="field-control" />
          </div>

          <div>
            <label for="web-fpa-profile" class="field-label text-xs">FPA 方案</label>
            <select id="web-fpa-profile" v-model="webRunForm.fpaProfile" class="field-control">
              <option v-for="profile in fpaOptions.profiles" :key="profile.name" :value="profile.name">
                {{ profile.label }}
              </option>
            </select>
          </div>

          <div>
            <label for="web-fpa-strategy" class="field-label text-xs">FPA 执行策略</label>
            <select id="web-fpa-strategy" v-model="webRunForm.fpaStrategy" class="field-control">
              <option value="">跟随方案默认</option>
              <option v-for="strategy in fpaOptions.strategies" :key="strategy.name" :value="strategy.name">
                {{ strategy.label }}
              </option>
            </select>
          </div>

          <div>
            <label for="web-fpa-rule-set" class="field-label text-xs">FPA 规则集</label>
            <select id="web-fpa-rule-set" v-model="webRunForm.fpaRuleSet" class="field-control">
              <option value="">跟随方案默认</option>
              <option v-for="ruleSet in fpaOptions.rule_sets" :key="ruleSet.name" :value="ruleSet.name">
                {{ ruleSet.label }}
              </option>
            </select>
          </div>

          <div>
            <label for="web-fpa-confirmation-mode" class="field-label text-xs">FPA 生成模式</label>
            <select id="web-fpa-confirmation-mode" v-model="webRunForm.fpaConfirmationMode" class="field-control">
              <option v-for="mode in fpaOptions.confirmation_modes" :key="mode.name" :value="mode.name">
                {{ mode.label }}
              </option>
            </select>
          </div>
        </div>

        <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', webSectionStatusClass(hasWebRunChanges)]">{{ webSectionStatusText(hasWebRunChanges) }}</span>
          <button class="btn-primary w-fit" :disabled="webConfigSaving || !hasWebRunChanges" @click="saveRunDefaults">
            {{ webConfigSaving ? '保存中...' : '保存运行默认值' }}
          </button>
        </div>
      </div>
      <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中...</p>
    </section>

    <section v-if="activeConfigSection === 'fpa' && !showUserConfig" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">FPA 策略</p>
          <h2 class="mt-1 text-lg font-semibold">方案与规则集</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="fpaStrategyLoading || fpaStrategySaving" @click="loadFpaStrategySettings">
          {{ fpaStrategyLoading ? '加载中...' : '刷新策略' }}
        </button>
      </div>

      <p v-if="fpaStrategyError" class="text-sm text-[var(--color-warning)]">{{ fpaStrategyError }}</p>
      <div v-else-if="fpaStrategyForm.profiles.length" class="space-y-4">
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
          <label for="fpa-default-profile" class="field-label text-xs">默认 FPA 方案</label>
          <select id="fpa-default-profile" v-model="fpaStrategyForm.defaultProfile" class="field-control">
            <option v-for="profile in fpaStrategyForm.profiles" :key="profile.name" :value="profile.name">
              {{ profileLabel(profile.name) }}
            </option>
          </select>
        </div>

        <div class="overflow-x-auto rounded-lg border border-[var(--color-rule)]">
          <table class="w-full min-w-[720px] text-left text-sm">
            <thead class="border-b border-[var(--color-rule)] bg-[var(--color-surface-muted)] text-xs text-[var(--color-ink-soft)]">
              <tr>
                <th class="px-3 py-2 font-semibold">方案</th>
                <th class="px-3 py-2 font-semibold">类型</th>
                <th class="px-3 py-2 font-semibold">执行策略</th>
                <th class="px-3 py-2 font-semibold">规则集</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="profile in fpaStrategyForm.profiles" :key="profile.name" class="border-b border-[var(--color-rule)] last:border-b-0">
                <td class="px-3 py-2">
                  <div class="font-semibold text-[var(--color-ink)]">{{ profileLabel(profile.name) }}</div>
                  <div class="mt-0.5 font-mono text-xs text-[var(--color-ink-soft)]">{{ profile.name }}</div>
                </td>
                <td class="px-3 py-2 text-[var(--color-ink-muted)]">{{ profile.kind || '-' }}</td>
                <td class="px-3 py-2">
                  <select v-model="profile.strategy" class="field-control min-w-[10rem]">
                    <option v-for="strategy in fpaOptions.strategies" :key="strategy.name" :value="strategy.name">
                      {{ strategy.label }}
                    </option>
                  </select>
                </td>
                <td class="px-3 py-2">
                  <select v-model="profile.rule_set" class="field-control min-w-[12rem]">
                    <option v-for="ruleSet in fpaStrategyForm.ruleSets" :key="ruleSet.name" :value="ruleSet.name">
                      {{ ruleSet.name }}{{ ruleSet.extends ? ` / extends ${ruleSet.extends}` : '' }}
                    </option>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', fpaStrategyStatusClass]">{{ fpaStrategyStatusText }}</span>
            <p v-if="fpaStrategyMsg" :class="['mt-2 text-sm', fpaStrategyOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ fpaStrategyMsg }}</p>
          </div>
          <button class="btn-primary w-fit" :disabled="fpaStrategySaving || !hasFpaStrategyChanges" @click="saveFpaStrategySettings">
            {{ fpaStrategySaving ? '保存中...' : '保存 FPA 策略' }}
          </button>
        </div>
      </div>
      <p v-else-if="fpaStrategyLoading" class="text-sm text-[var(--color-ink-soft)]">加载中...</p>
      <p v-else class="text-sm text-[var(--color-ink-soft)]">暂无 FPA 策略配置。</p>
    </section>

    <section v-if="activeConfigSection === 'fpa' && !showUserConfig" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">FPA 判定规则</p>
          <h2 class="mt-1 text-lg font-semibold">计算依据归类判定原则</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="fpaJudgementRulesLoading || fpaJudgementRulesSaving" @click="loadFpaJudgementRules">
          {{ fpaJudgementRulesLoading ? '加载中...' : '刷新规则' }}
        </button>
      </div>

      <p v-if="fpaJudgementRulesError" class="text-sm text-[var(--color-warning)]">{{ fpaJudgementRulesError }}</p>
      <div v-else class="space-y-3">
        <div
          v-for="(rule, index) in fpaJudgementRules"
          :key="rule.id"
          class="grid gap-2 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-3 sm:grid-cols-[auto,1fr,auto]"
        >
          <div class="pt-2 text-xs font-semibold text-[var(--color-ink-soft)]">{{ index + 1 }}</div>
          <textarea
            v-model="rule.text"
            rows="2"
            class="field-control resize-y text-sm"
            spellcheck="false"
          />
          <div class="flex flex-wrap gap-1 sm:flex-col">
            <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="index === 0" @click="moveFpaJudgementRule(index, -1)">上移</button>
            <button class="btn-secondary min-h-0 px-2 py-1 text-xs" :disabled="index === fpaJudgementRules.length - 1" @click="moveFpaJudgementRule(index, 1)">下移</button>
            <button class="btn-danger min-h-0 px-2 py-1 text-xs" :disabled="fpaJudgementRules.length <= 1" @click="removeFpaJudgementRule(index)">删除</button>
          </div>
        </div>

        <button class="btn-secondary w-fit" @click="addFpaJudgementRule">新增判定原则</button>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', fpaJudgementRulesStatusClass]">{{ fpaJudgementRulesStatusText }}</span>
            <p v-if="fpaJudgementRulesMsg" :class="['mt-2 text-sm', fpaJudgementRulesOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ fpaJudgementRulesMsg }}</p>
          </div>
          <button class="btn-primary w-fit" :disabled="fpaJudgementRulesSaving || !hasFpaJudgementRulesChanges" @click="saveFpaJudgementRules">
            {{ fpaJudgementRulesSaving ? '保存中...' : '保存判定原则' }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="activeConfigSection === 'advanced' && !showUserConfig" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">业务规则</p>
          <h2 class="mt-1 text-lg font-semibold">CFP 计算公式</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="businessRulesLoading || businessRulesSaving" @click="loadBusinessRulesSettings">
          {{ businessRulesLoading ? '加载中...' : '刷新业务规则' }}
        </button>
      </div>

      <p v-if="businessRulesError" class="text-sm text-[var(--color-warning)]">{{ businessRulesError }}</p>
      <div v-else class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
        <label for="business-cfp-formula" class="field-label text-xs">CFP 计算公式</label>
        <textarea
          id="business-cfp-formula"
          v-model="businessRulesForm.cfpFormula"
          rows="4"
          class="field-control font-mono text-xs leading-relaxed"
          spellcheck="false"
        />
        <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', businessRulesStatusClass]">{{ businessRulesStatusText }}</span>
            <p v-if="businessRulesMsg" :class="['mt-2 text-sm', businessRulesOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ businessRulesMsg }}</p>
          </div>
          <button class="btn-primary w-fit" :disabled="businessRulesSaving || !hasBusinessRulesChanges" @click="saveBusinessRulesSettings">
            {{ businessRulesSaving ? '保存中...' : '保存业务规则' }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="activeConfigSection === 'fpa' && !showUserConfig" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">领域上下文</p>
          <h2 class="mt-1 text-lg font-semibold">FPA 稳定边界</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="domainContextLoading || domainContextSaving" @click="loadDomainContextSettings">
          {{ domainContextLoading ? '加载中...' : '刷新上下文' }}
        </button>
      </div>

      <p v-if="domainContextError" class="text-sm text-[var(--color-warning)]">{{ domainContextError }}</p>
      <div v-else class="space-y-4">
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
          <label for="domain-system-boundary" class="field-label text-xs">系统边界</label>
          <textarea
            id="domain-system-boundary"
            v-model="domainContextForm.systemBoundary"
            rows="4"
            class="field-control text-sm leading-relaxed"
            spellcheck="false"
          />
        </div>

        <div
          v-for="section in domainContextSections"
          :key="section.key"
          class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4"
        >
          <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 class="text-sm font-semibold">{{ section.title }}</h3>
              <p class="mt-0.5 text-xs text-[var(--color-ink-soft)]">{{ section.description }}</p>
            </div>
            <button class="btn-secondary w-fit min-h-0 px-3 py-1.5 text-xs" @click="addDomainContextItem(section.key)">新增</button>
          </div>

          <div v-if="section.items.length" class="space-y-3">
            <div
              v-for="(item, index) in section.items"
              :key="item.id"
              class="grid gap-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-3 md:grid-cols-2"
            >
              <div>
                <label :for="`domain-${section.key}-name-${item.id}`" class="field-label text-xs">名称</label>
                <input :id="`domain-${section.key}-name-${item.id}`" v-model.trim="item.name" type="text" class="field-control" />
              </div>
              <div v-if="section.requireSource">
                <label :for="`domain-${section.key}-source-${item.id}`" class="field-label text-xs">来源系统</label>
                <input :id="`domain-${section.key}-source-${item.id}`" v-model.trim="item.source" type="text" class="field-control" />
              </div>
              <div :class="section.requireSource ? 'md:col-span-2' : ''">
                <label :for="`domain-${section.key}-aliases-${item.id}`" class="field-label text-xs">别名</label>
                <textarea
                  :id="`domain-${section.key}-aliases-${item.id}`"
                  v-model="item.aliasesText"
                  rows="2"
                  class="field-control text-sm"
                  spellcheck="false"
                />
              </div>
              <div class="md:col-span-2">
                <label :for="`domain-${section.key}-description-${item.id}`" class="field-label text-xs">说明</label>
                <textarea
                  :id="`domain-${section.key}-description-${item.id}`"
                  v-model="item.description"
                  rows="2"
                  class="field-control text-sm"
                  spellcheck="false"
                />
              </div>
              <div class="md:col-span-2">
                <button class="btn-danger w-fit min-h-0 px-3 py-1.5 text-xs" @click="removeDomainContextItem(section.key, index)">删除</button>
              </div>
            </div>
          </div>
          <p v-else class="rounded-lg border border-dashed border-[var(--color-rule-strong)] bg-[var(--color-surface-muted)] p-3 text-sm text-[var(--color-ink-muted)]">
            暂无{{ section.title }}。
          </p>
        </div>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', domainContextStatusClass]">{{ domainContextStatusText }}</span>
            <p v-if="domainContextMsg" :class="['mt-2 text-sm', domainContextOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ domainContextMsg }}</p>
          </div>
          <button class="btn-primary w-fit" :disabled="domainContextSaving || !hasDomainContextChanges" @click="saveDomainContextSettings">
            {{ domainContextSaving ? '保存中...' : '保存领域上下文' }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="activeConfigSection === 'advanced' && !showUserConfig" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">Prompt 配置</p>
          <h2 class="mt-1 text-lg font-semibold">AI 场景提示词</h2>
        </div>
        <button class="btn-secondary w-fit" :disabled="aiPromptsLoading || aiPromptsSaving" @click="loadAiPromptSettings">
          {{ aiPromptsLoading ? '加载中...' : '刷新 Prompt' }}
        </button>
      </div>

      <p v-if="aiPromptsError" class="text-sm text-[var(--color-warning)]">{{ aiPromptsError }}</p>
      <div v-else class="space-y-4">
        <div
          v-for="(prompt, index) in aiPrompts"
          :key="prompt.id"
          class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4"
        >
          <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <div class="text-sm font-semibold text-[var(--color-ink)]">场景 {{ index + 1 }}</div>
              <div class="mt-0.5 truncate font-mono text-xs text-[var(--color-ink-soft)]">{{ prompt.name || '未命名' }}</div>
            </div>
            <button class="btn-danger w-fit min-h-0 px-2 py-1 text-xs" @click="removeAiPrompt(index)">删除</button>
          </div>

          <div class="grid gap-3 md:grid-cols-2">
            <div>
              <label :for="`ai-prompt-name-${prompt.id}`" class="field-label text-xs">场景名称</label>
              <input :id="`ai-prompt-name-${prompt.id}`" v-model.trim="prompt.name" type="text" class="field-control font-mono text-sm" />
            </div>
            <div>
              <label :for="`ai-prompt-scene-${prompt.id}`" class="field-label text-xs">显示名称</label>
              <input :id="`ai-prompt-scene-${prompt.id}`" v-model.trim="prompt.scene" type="text" class="field-control" />
            </div>
            <div class="md:col-span-2">
              <label :for="`ai-prompt-system-${prompt.id}`" class="field-label text-xs">System Prompt</label>
              <textarea
                :id="`ai-prompt-system-${prompt.id}`"
                v-model="prompt.system"
                rows="6"
                class="field-control font-mono text-xs leading-relaxed"
                spellcheck="false"
              />
            </div>
            <div class="md:col-span-2">
              <label :for="`ai-prompt-examples-${prompt.id}`" class="field-label text-xs">Examples</label>
              <textarea
                :id="`ai-prompt-examples-${prompt.id}`"
                v-model="prompt.examples"
                rows="4"
                class="field-control font-mono text-xs leading-relaxed"
                spellcheck="false"
              />
            </div>
          </div>
        </div>

        <div v-if="!aiPrompts.length" class="rounded-lg border border-dashed border-[var(--color-rule-strong)] bg-[var(--color-surface)] p-4 text-sm text-[var(--color-ink-muted)]">
          暂无 AI 场景提示词。
        </div>

        <button class="btn-secondary w-fit" @click="addAiPrompt">新增 Prompt 场景</button>

        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', aiPromptsStatusClass]">{{ aiPromptsStatusText }}</span>
            <p v-if="aiPromptsMsg" :class="['mt-2 text-sm', aiPromptsOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ aiPromptsMsg }}</p>
          </div>
          <button class="btn-primary w-fit" :disabled="aiPromptsSaving || !hasAiPromptsChanges" @click="saveAiPromptSettings">
            {{ aiPromptsSaving ? '保存中...' : '保存 Prompt 配置' }}
          </button>
        </div>
      </div>
    </section>

    <section v-if="activeConfigSection === 'templates'" class="surface rounded-lg p-5">
      <div class="mb-4 border-b border-[var(--color-rule)] pb-4">
        <p class="text-xs font-semibold text-[var(--color-ink-soft)]">模板配置</p>
        <h2 class="mt-1 text-lg font-semibold">输出与下载模板</h2>
      </div>
      <div class="mb-4 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
        <label for="web-out-templates" class="field-label text-xs">out_templates 映射</label>
        <textarea
          id="web-out-templates"
          v-model="webTemplateForm.outTemplatesJson"
          rows="8"
          class="field-control font-mono text-xs"
          spellcheck="false"
        />
        <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', webSectionStatusClass(hasWebTemplateChanges)]">{{ webSectionStatusText(hasWebTemplateChanges) }}</span>
          <button class="btn-primary w-fit" :disabled="webConfigSaving || !hasWebTemplateChanges" @click="saveTemplateSettings">
            {{ webConfigSaving ? '保存中...' : '保存模板映射' }}
          </button>
        </div>
      </div>
      <div class="grid gap-4 lg:grid-cols-2">
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-4">
          <TemplateUpload />
        </div>
        <div class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-4">
          <TemplateDownload />
        </div>
      </div>
    </section>

    <section v-if="activeConfigSection === 'advanced'" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">高级配置</p>
          <h2 class="mt-1 text-lg font-semibold">YAML / JSON 配置文件</h2>
        </div>
        <button
          v-if="!showUserConfig"
          class="btn-secondary w-fit"
          :disabled="advancedConfigLoading || advancedConfigSaving"
          @click="loadAdvancedConfigFiles"
        >
          {{ advancedConfigLoading ? '加载中...' : '刷新文件' }}
        </button>
      </div>

      <p v-if="showUserConfig" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-4 py-3 text-sm text-[var(--color-ink-muted)]">
        高级配置文件由本机管理员维护。远程用户可在上方维护个人 AI 配置、模板和运行默认值。
      </p>

      <div v-else class="space-y-4">
        <p v-if="advancedConfigError" class="text-sm text-[var(--color-warning)]">{{ advancedConfigError }}</p>
        <div v-else-if="advancedConfigFiles.length" class="grid gap-2 sm:grid-cols-2">
          <button
            v-for="item in advancedConfigFiles"
            :key="item.id"
            type="button"
            :class="[
              'flex min-w-0 items-center justify-between gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors',
              activeAdvancedFileId === item.id
                ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]'
                : 'border-[var(--color-rule)] bg-[var(--color-surface)] text-[var(--color-ink-muted)] hover:border-[var(--color-rule-strong)] hover:text-[var(--color-ink)]',
            ]"
            @click="selectAdvancedFile(item.id)"
          >
            <span class="min-w-0">
              <span class="block truncate font-semibold">{{ item.label }}</span>
              <span class="mt-0.5 block truncate text-xs">{{ item.file }}</span>
            </span>
            <span :class="['status-badge shrink-0', item.exists ? statusClass.ok : statusClass.neutral]">
              {{ item.exists ? item.format.toUpperCase() : '未创建' }}
            </span>
          </button>
        </div>
        <p v-else-if="advancedConfigLoading" class="text-sm text-[var(--color-ink-soft)]">加载中...</p>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">暂无可编辑配置文件。</p>

        <div v-if="activeAdvancedFile" class="rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
          <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div class="min-w-0">
              <h3 class="truncate text-sm font-semibold text-[var(--color-ink)]">{{ activeAdvancedFile.label }}</h3>
              <p class="mt-1 text-xs text-[var(--color-ink-soft)]">{{ activeAdvancedFile.file }} · {{ activeAdvancedFile.format.toUpperCase() }} · 第{{ activeAdvancedFile.phase }}期</p>
            </div>
            <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', advancedConfigStatusClass]">{{ advancedConfigStatusText }}</span>
          </div>

          <textarea
            v-model="advancedConfigContent"
            rows="18"
            class="field-control min-h-[24rem] resize-y font-mono text-xs leading-relaxed"
            spellcheck="false"
          />

          <div class="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <p v-if="advancedConfigMessage" :class="['text-sm', advancedConfigOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ advancedConfigMessage }}</p>
            <span v-else class="text-sm text-[var(--color-ink-soft)]">保存前会先校验，通过后自动备份当前文件。</span>
            <div class="flex flex-wrap gap-2">
              <button class="btn-secondary w-fit" :disabled="advancedConfigLoading || advancedConfigSaving || !activeAdvancedFileId" @click="loadAdvancedConfigFile(activeAdvancedFileId)">
                重新读取
              </button>
              <button class="btn-secondary w-fit" :disabled="advancedConfigSaving || !activeAdvancedFileId" @click="validateAdvancedConfig">
                {{ advancedConfigSaving ? '校验中...' : '校验' }}
              </button>
              <button class="btn-primary w-fit" :disabled="advancedConfigSaving || !hasAdvancedConfigChanges" @click="saveAdvancedConfig">
                {{ advancedConfigSaving ? '保存中...' : '保存配置文件' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section v-if="activeConfigSection === 'maintenance'" class="surface rounded-lg p-5">
      <div class="mb-4 flex flex-col gap-3 border-b border-[var(--color-rule)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p class="text-xs font-semibold text-[var(--color-ink-soft)]">配置备份</p>
          <h2 class="mt-1 text-lg font-semibold">备份与恢复</h2>
          <p class="mt-1 text-sm text-[var(--color-ink-muted)]">每次保存前自动生成备份；恢复前也会先备份当前配置。</p>
        </div>
        <button class="btn-secondary w-fit" :disabled="configBackupsLoading || configRestoreLoading" @click="loadConfigBackups">
          {{ configBackupsLoading ? '加载中...' : '刷新备份' }}
        </button>
      </div>

      <p v-if="configBackupsError" class="text-sm text-[var(--color-warning)]">{{ configBackupsError }}</p>
      <div v-else-if="configBackups.length" class="overflow-x-auto">
        <table class="w-full min-w-[680px] text-left text-sm">
          <thead class="border-b border-[var(--color-rule)] text-xs text-[var(--color-ink-soft)]">
            <tr>
              <th class="px-3 py-2 font-semibold">配置文件</th>
              <th class="px-3 py-2 font-semibold">备份时间</th>
              <th class="px-3 py-2 font-semibold">大小</th>
              <th class="px-3 py-2 font-semibold">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in configBackups" :key="item.id" class="border-b border-[var(--color-rule)] last:border-b-0">
              <td class="px-3 py-2 font-mono text-xs text-[var(--color-ink-muted)]">{{ item.file }}</td>
              <td class="px-3 py-2 text-[var(--color-ink-muted)]">{{ formatTime(item.created_at) }}</td>
              <td class="px-3 py-2 text-[var(--color-ink-soft)]">{{ formatBytes(item.size_bytes) }}</td>
              <td class="px-3 py-2">
                <button
                  class="btn-secondary mr-2 min-h-0 px-3 py-1.5 text-xs"
                  :disabled="configBackupDiffLoading || configRestoreLoading"
                  @click="loadConfigBackupDiff(item)"
                >
                  {{ configBackupDiffLoading && configBackupDiffId === item.id ? '读取中...' : '查看差异' }}
                </button>
                <button
                  class="btn-secondary min-h-0 px-3 py-1.5 text-xs"
                  :disabled="configRestoreLoading"
                  @click="restoreConfigBackup(item)"
                >
                  {{ configRestoreLoading && restoringBackupId === item.id ? '恢复中...' : '恢复' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="text-sm text-[var(--color-ink-soft)]">暂无可恢复备份。</p>
      <div v-if="configBackupDiff || configBackupDiffError" class="mt-4 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] p-4">
        <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p class="text-xs font-semibold text-[var(--color-ink-soft)]">备份差异</p>
            <h3 class="mt-1 text-sm font-semibold">{{ configBackupDiff?.file || '读取失败' }}</h3>
            <p v-if="configBackupDiff" class="mt-1 text-xs text-[var(--color-ink-soft)]">备份时间：{{ formatTime(configBackupDiff.backup_created_at) }}</p>
          </div>
          <button class="btn-secondary w-fit min-h-0 px-3 py-1.5 text-xs" @click="clearConfigBackupDiff">关闭</button>
        </div>
        <p v-if="configBackupDiffError" class="text-sm text-[var(--color-warning)]">{{ configBackupDiffError }}</p>
        <pre v-else class="max-h-[24rem] overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-4 font-mono text-xs leading-relaxed text-slate-300">{{ configBackupDiff?.diff || '当前文件与备份一致。' }}</pre>
      </div>
      <p v-if="configRestoreMsg" :class="['mt-3 text-sm', configRestoreOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ configRestoreMsg }}</p>
    </section>

    <section v-if="activeConfigSection === 'maintenance' && !showUserConfig" class="surface rounded-lg p-5">
      <div class="mb-4 border-b border-[var(--color-rule)] pb-4">
        <p class="text-xs font-semibold text-[var(--color-ink-soft)]">配置导入导出</p>
        <h2 class="mt-1 text-lg font-semibold">配置包</h2>
      </div>
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p class="text-sm text-[var(--color-ink-muted)]">导出包不包含 API Key 原文、API Key 密文或本机加密主密钥。</p>
        <div class="flex flex-wrap gap-2">
          <button class="btn-secondary w-fit" :disabled="configPackageLoading" @click="exportConfigPackage">
            {{ configPackageLoading ? '导出中...' : '导出配置包' }}
          </button>
          <button class="btn-primary w-fit" :disabled="configPackageLoading" @click="importConfigPackage">
            {{ configPackageLoading ? '导入中...' : '导入配置包' }}
          </button>
        </div>
      </div>
      <p v-if="configPackageMsg" :class="['mt-3 text-sm', configPackageOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ configPackageMsg }}</p>
    </section>

    <nav v-if="activeConfigSection === 'advanced'" class="flex flex-wrap gap-2 border-b border-[var(--color-rule)] pb-3" aria-label="原始配置分区">
      <button
        v-for="tab in configTabs"
        :key="tab.key"
        type="button"
        :class="['nav-link', activeTab === tab.key ? 'nav-link-active' : '']"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- 个人配置（可编辑，远程模式） -->
    <template v-if="activeConfigSection === 'advanced' && showUserConfig">
      <section v-if="activeTab === 'personal'">
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 class="text-lg font-semibold">个人配置</h2>
            <p class="mt-1 text-xs text-[var(--color-ink-soft)]">~/.ai-gen-reimbursement-docs/users/{{ auth.username }}/</p>
          </div>
          <span :class="['w-fit rounded-md px-2 py-1 text-xs font-semibold', saveStatusClass]">{{ saveStatusText }}</span>
        </div>
        <!-- .env -->
        <div class="surface mb-4 space-y-3 rounded-lg p-5">
          <div class="flex items-center justify-between gap-3">
            <h3 class="text-sm font-medium text-[var(--color-ink-muted)]">环境变量 .env</h3>
          </div>
          <div>
            <label class="field-label text-xs">ANTHROPIC_BASE_URL</label>
            <input v-model="envFields.baseUrl" type="text"
              class="field-control" />
          </div>
          <div>
            <label class="field-label text-xs">ANTHROPIC_MODEL</label>
            <input v-model="envFields.model" type="text"
              class="field-control" />
          </div>
        </div>

        <!-- system_config.yaml -->
        <div class="surface mb-4 space-y-4 rounded-lg p-5">
          <h3 class="text-sm font-medium text-[var(--color-ink-muted)]">system_config.yaml</h3>

          <!-- 布尔字段：4 列 grid -->
          <div class="grid grid-cols-4 gap-x-4 gap-y-2">
            <label v-for="f in boolFields" :key="f.key"
              class="flex cursor-pointer items-center gap-2 text-sm text-[var(--color-ink-muted)]">
              <input type="checkbox" v-model="f.value" class="rounded border-[var(--color-rule-strong)] text-[var(--color-accent)] focus:ring-[var(--color-focus)]" />
              {{ f.key }}
            </label>
          </div>

          <hr class="border-[var(--color-rule)]" />

          <!-- 枚举/数字/文本：2 列 grid -->
          <div class="grid grid-cols-2 gap-4">
            <div v-for="f in scalarFields" :key="f.key">
              <label class="field-label text-xs">{{ f.key }}</label>
              <select v-if="f.type === 'select'" v-model="f.value"
                class="field-control">
                <option v-for="opt in f.options" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <input v-else-if="f.type === 'number'" v-model.number="f.value" type="number"
                class="field-control" />
              <input v-else v-model="f.value" type="text"
                class="field-control" />
            </div>
          </div>

          <!-- 嵌套对象：textarea -->
          <template v-if="nestedFields.length">
            <hr class="border-[var(--color-rule)]" />
            <div v-for="f in nestedFields" :key="f.key">
              <label class="field-label text-xs">{{ f.key }}</label>
              <textarea v-model="f.yamlText" rows="6"
                class="field-control font-mono"></textarea>
            </div>
          </template>
        </div>

        <div class="flex gap-3">
          <button @click="saveUserConfig" :disabled="saving || !hasUnsavedChanges"
            class="btn-primary">
            {{ saving ? '保存中...' : '保存' }}
          </button>
          <button @click="exportSettings"
            class="btn-secondary">
            导出
          </button>
          <button @click="importSettings"
            class="btn-secondary">
            导入
          </button>
        </div>
        <p v-if="saveMsg" :class="['mt-2 text-sm', saveOk ? 'text-[var(--color-success)]' : 'text-[var(--color-danger)]']">{{ saveMsg }}</p>
        <p v-if="lastSavedAt" class="mt-2 text-xs text-[var(--color-ink-soft)]">上次保存：{{ lastSavedAt }}</p>
      </section>

      <!-- 服务端全局默认（只读参考） -->
      <section v-if="activeTab === 'global' && globalSystemConfig">
        <h2 class="text-lg font-semibold mb-4">服务端全局默认 (system_config.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">只读参考，文件位置: ~/.ai-gen-reimbursement-docs/system_config.yaml</p>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ globalSystemConfig || '（空）' }}</pre>
      </section>
      <section v-if="activeTab === 'global' && globalEnvContent">
        <h2 class="text-lg font-semibold mb-4">服务端全局默认 (.env)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">只读参考，敏感值已遮罩</p>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ globalEnvContent || '（空）' }}</pre>
      </section>
      <section v-if="activeTab === 'rules' && businessRules !== null">
        <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">只读</p>
        <pre class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ businessRules || '（空）' }}</pre>
      </section>
    </template>

    <!-- 本机模式：只读 -->
    <template v-else-if="activeConfigSection === 'advanced'">
      <section v-if="activeTab === 'env'">
        <h2 class="text-lg font-semibold mb-4">环境变量 (.env)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">~/.ai-gen-reimbursement-docs/.env</p>
        <pre v-if="envContent !== null" class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ envContent || '（空）' }}</pre>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中…</p>
      </section>
      <section v-if="activeTab === 'system'">
        <h2 class="text-lg font-semibold mb-4">系统配置 (system_config.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">~/.ai-gen-reimbursement-docs/system_config.yaml</p>
        <pre v-if="systemConfig !== null" class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ systemConfig || '（空）' }}</pre>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中…</p>
      </section>
      <section v-if="activeTab === 'rules'">
        <h2 class="text-lg font-semibold mb-4">业务规则 (business_rules.yaml)</h2>
        <p class="mb-3 text-sm text-[var(--color-ink-muted)]">~/.ai-gen-reimbursement-docs/business_rules.yaml</p>
        <pre v-if="businessRules !== null" class="overflow-x-auto whitespace-pre-wrap rounded-lg bg-[var(--color-console)] p-5 font-mono text-sm text-slate-300">{{ businessRules || '（空）' }}</pre>
        <p v-else class="text-sm text-[var(--color-ink-soft)]">加载中…</p>
      </section>
    </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { defineComponent, h, ref, computed, onMounted, reactive, type PropType } from 'vue'
import { useAuthStore } from '@/stores/auth.ts'
import { normalizeApiKeyInput, useConfigStore } from '@/stores/config.ts'
import { useSensitiveInputGuard } from '@/composables/useSensitiveInputGuard.ts'
import { useFpaOptions } from '@/composables/useFpaOptions.ts'
import { apiFetch, isBackendUnavailableMessage, normalizeApiError } from '@/lib/api.ts'
import TemplateDownload from '@/components/TemplateDownload.vue'
import TemplateUpload from '@/components/TemplateUpload.vue'

// ── 类型 ──────────────────────────────────────────────────

type FieldType = 'bool' | 'number' | 'select' | 'text'

interface ScalarField {
  key: string
  type: FieldType
  value: any
  options?: string[]
}

interface NestedField {
  key: string
  yamlText: string
}

interface ConfigReadResponse {
  env?: string
  system_config?: string
  business_rules?: string
  global_env?: string
  global_system?: string
}

interface UserConfigResponse {
  _system?: Record<string, any>
}

interface HealthResponse {
  ok?: boolean
  version?: string
  work_mode?: string
  api?: Record<string, boolean | null>
  paths?: Record<string, boolean | null>
  features?: Record<string, boolean | null>
  config?: {
    fpa_runtime?: {
      config_dir?: string
      files?: Record<string, boolean>
      missing?: string[]
      present?: boolean
    }
  }
}

type ConfigSource = 'personal' | 'global' | 'default'

interface WebConfigField<T = unknown> {
  value: T
  source: ConfigSource
}

interface WebConfigResponse {
  scope: {
    mode: 'local' | 'remote'
    username: string
  }
  ai: {
    api_key_configured: boolean
    api_key_source: ConfigSource
    base_url: WebConfigField<string>
    model: WebConfigField<string>
    max_tokens: WebConfigField<string | number>
    allow_shared_ai_credentials: WebConfigField<boolean>
  }
  templates: {
    out_templates: WebConfigField<Record<string, string>>
  }
  run_defaults: Record<string, WebConfigField<unknown>>
}

interface ConfigBackupItem {
  id: string
  file: string
  created_at: string
  size_bytes: number
}

interface ConfigBackupsResponse {
  items: ConfigBackupItem[]
}

interface ConfigBackupDiffResponse {
  id: string
  file: string
  current_exists: boolean
  backup_created_at: string
  diff: string
  has_changes: boolean
}

interface ConfigPackageImportResponse {
  ok: boolean
  imported: string[]
  backed_up: string[]
}

interface AdvancedConfigFileItem {
  id: string
  label: string
  file: string
  format: 'yaml' | 'json'
  phase: number
  exists: boolean
  updated_at?: string
  size_bytes?: number
}

interface AdvancedConfigFilesResponse {
  items: AdvancedConfigFileItem[]
}

interface AdvancedConfigFileResponse extends AdvancedConfigFileItem {
  content: string
}

interface FpaStrategyProfile {
  name: string
  kind: string
  strategy: string
  rule_set: string
  core_rules?: string
  system_prompt?: string
  user_prompt?: string
}

interface FpaStrategyRuleSet {
  name: string
  extends: string
}

interface FpaStrategySettingsResponse {
  default_profile: string
  profiles: FpaStrategyProfile[]
  rule_sets: FpaStrategyRuleSet[]
}

interface FpaJudgementRuleItem {
  id: number
  text: string
}

interface FpaJudgementRulesResponse {
  rules: string[]
  exists: boolean
}

interface BusinessRulesResponse {
  cfp_formula: string
  exists: boolean
}

interface AiPromptItem {
  id: number
  name: string
  scene: string
  system: string
  examples: string
}

interface AiPromptsResponse {
  prompts: Omit<AiPromptItem, 'id'>[]
  exists: boolean
}

type DomainContextSectionKey = 'internal_data_groups' | 'external_data_groups' | 'external_services'

interface DomainContextItem {
  id: number
  name: string
  aliasesText: string
  description: string
  source: string
}

interface DomainContextItemPayload {
  name: string
  aliases?: string[]
  description?: string
  source?: string
}

interface DomainContextResponse {
  system_boundary: string
  internal_data_groups: DomainContextItemPayload[]
  external_data_groups: DomainContextItemPayload[]
  external_services: DomainContextItemPayload[]
  exists: boolean
}

// ── stores ────────────────────────────────────────────────

const auth = useAuthStore()
const configStore = useConfigStore()
const { fpaOptions, loadFpaOptions } = useFpaOptions()

const showUserConfig = computed(() => auth.isRemote)
const backendOffline = computed(() => configStore.backendStatus === 'offline')
type ConfigSectionKey = 'common' | 'fpa' | 'templates' | 'advanced' | 'maintenance'
const activeConfigSection = ref<ConfigSectionKey>('common')
const configSectionTabs = computed<{ key: ConfigSectionKey; label: string }[]>(() => [
  { key: 'common', label: '常用' },
  ...(!showUserConfig.value ? [{ key: 'fpa' as const, label: 'FPA' }] : []),
  { key: 'templates', label: '模板' },
  { key: 'advanced', label: '高级' },
  { key: 'maintenance', label: '维护' },
])
type ConfigTabKey = 'personal' | 'global' | 'env' | 'system' | 'rules'
const activeTab = ref<ConfigTabKey>(showUserConfig.value ? 'personal' : 'env')
const configTabs = computed<{ key: ConfigTabKey; label: string }[]>(() => {
  if (showUserConfig.value) {
    return [
      { key: 'personal', label: '个人配置' },
      { key: 'global', label: '全局默认' },
      { key: 'rules', label: '业务规则' },
    ]
  }
  return [
    { key: 'env', label: '环境变量' },
    { key: 'system', label: '系统配置' },
    { key: 'rules', label: '业务规则' },
  ]
})

// ── 只读内容 ──────────────────────────────────────────────

const envContent = ref<string | null>(null)
const systemConfig = ref<string | null>(null)
const businessRules = ref<string | null>(null)
const globalEnvContent = ref('')
const globalSystemConfig = ref('')

// ── 可编辑字段 ────────────────────────────────────────────

const envFields = reactive({ baseUrl: '', model: '' })
const boolFields = ref<ScalarField[]>([])
const scalarFields = ref<ScalarField[]>([])
const nestedFields = ref<NestedField[]>([])
const saving = ref(false)
const saveMsg = ref('')
const saveOk = ref(false)
const savedSnapshot = ref('')
const lastSavedAt = ref('')
const health = ref<HealthResponse | null>(null)
const healthLoading = ref(false)
const healthError = ref('')
const healthCheckedAt = ref('')
const webConfig = ref<WebConfigResponse | null>(null)
const webConfigLoading = ref(false)
const webConfigError = ref('')
const webConfigSaving = ref(false)
const webConfigSaveMsg = ref('')
const webConfigSaveOk = ref(false)
const webConfigSnapshot = ref('')
const configBackups = ref<ConfigBackupItem[]>([])
const configBackupsLoading = ref(false)
const configBackupsError = ref('')
const configRestoreLoading = ref(false)
const configRestoreMsg = ref('')
const configRestoreOk = ref(false)
const restoringBackupId = ref('')
const configBackupDiff = ref<ConfigBackupDiffResponse | null>(null)
const configBackupDiffLoading = ref(false)
const configBackupDiffError = ref('')
const configBackupDiffId = ref('')
const configPackageLoading = ref(false)
const configPackageMsg = ref('')
const configPackageOk = ref(false)
const advancedConfigFiles = ref<AdvancedConfigFileItem[]>([])
const activeAdvancedFileId = ref('')
const advancedConfigContent = ref('')
const advancedConfigSnapshot = ref('')
const advancedConfigLoading = ref(false)
const advancedConfigSaving = ref(false)
const advancedConfigError = ref('')
const advancedConfigMessage = ref('')
const advancedConfigOk = ref(false)
const fpaStrategyLoading = ref(false)
const fpaStrategySaving = ref(false)
const fpaStrategyError = ref('')
const fpaStrategyMsg = ref('')
const fpaStrategyOk = ref(false)
const fpaStrategySnapshot = ref('')
const fpaStrategyForm = reactive({
  defaultProfile: '',
  profiles: [] as FpaStrategyProfile[],
  ruleSets: [] as FpaStrategyRuleSet[],
})
const fpaJudgementRules = ref<FpaJudgementRuleItem[]>([])
const fpaJudgementRuleNextId = ref(1)
const fpaJudgementRulesSnapshot = ref('')
const fpaJudgementRulesLoading = ref(false)
const fpaJudgementRulesSaving = ref(false)
const fpaJudgementRulesError = ref('')
const fpaJudgementRulesMsg = ref('')
const fpaJudgementRulesOk = ref(false)
const businessRulesLoading = ref(false)
const businessRulesSaving = ref(false)
const businessRulesError = ref('')
const businessRulesMsg = ref('')
const businessRulesOk = ref(false)
const businessRulesSnapshot = ref('')
const businessRulesForm = reactive({
  cfpFormula: '',
})
const aiPrompts = ref<AiPromptItem[]>([])
const aiPromptNextId = ref(1)
const aiPromptsSnapshot = ref('')
const aiPromptsLoading = ref(false)
const aiPromptsSaving = ref(false)
const aiPromptsError = ref('')
const aiPromptsMsg = ref('')
const aiPromptsOk = ref(false)
const domainContextForm = reactive({
  systemBoundary: '',
})
const domainContextInternalDataGroups = ref<DomainContextItem[]>([])
const domainContextExternalDataGroups = ref<DomainContextItem[]>([])
const domainContextExternalServices = ref<DomainContextItem[]>([])
const domainContextNextId = ref(1)
const domainContextSnapshot = ref('')
const domainContextLoading = ref(false)
const domainContextSaving = ref(false)
const domainContextError = ref('')
const domainContextMsg = ref('')
const domainContextOk = ref(false)
const webAiForm = reactive({
  apiKey: '',
  baseUrl: '',
  model: '',
  maxTokens: '',
  allowSharedAiCredentials: false,
  clearApiKey: false,
})
const webRunForm = reactive({
  projectName: '',
  fpaProfile: '',
  fpaStrategy: '',
  fpaRuleSet: '',
  fpaConfirmationMode: 'cautious',
})
const webTemplateForm = reactive({
  outTemplatesJson: '{}',
})
const webApiKeyInput = ref<HTMLInputElement | null>(null)
const {
  inputName: webApiKeyInputName,
  readonly: webApiKeyReadonly,
  activateSensitiveInput: activateWebApiKeyInput,
} = useSensitiveInputGuard('web-api-key', {
  inputRef: webApiKeyInput,
  getValue: () => webAiForm.apiKey,
  setValue: value => { webAiForm.apiKey = value },
})

const statusClass = {
  ok: 'status-badge--success',
  warn: 'status-badge--warning',
  neutral: 'status-badge--neutral',
}

const diagnosticItems = computed(() => {
  const data = health.value
  return [
    {
      label: '后端连接',
      value: data ? (data.ok === false ? '部分异常' : '正常') : '未连接',
      className: data ? (data.ok === false ? statusClass.warn : statusClass.ok) : statusClass.warn,
    },
    {
      label: '后端版本',
      value: data?.version || '未知',
      className: data?.version ? statusClass.neutral : statusClass.warn,
    },
    {
      label: '工作模式',
      value: data?.work_mode === 'remote' ? '远程服务' : data?.work_mode === 'local' ? '本机模式' : '未知',
      className: data?.work_mode ? statusClass.neutral : statusClass.warn,
    },
    {
      label: '模板目录',
      value: formatStatus(data?.paths?.templates_readable),
      className: statusClassFor(data?.paths?.templates_readable),
    },
    {
      label: 'FPA 运行配置',
      value: formatStatus(data?.paths?.fpa_runtime_config_present),
      className: statusClassFor(data?.paths?.fpa_runtime_config_present),
    },
    {
      label: '配置接口',
      value: formatStatus(data?.api?.config),
      className: statusClassFor(data?.api?.config),
    },
    {
      label: '提示词调试',
      value: formatStatus(data?.features?.prompt_debug),
      className: statusClassFor(data?.features?.prompt_debug),
    },
  ]
})

const fpaRuntimeConfigMissingText = computed(() => {
  const missing = health.value?.config?.fpa_runtime?.missing || []
  if (!missing.length) return ''
  return `缺少 FPA 运行配置：${missing.join('、')}`
})

const currentConfigSnapshot = computed(() => JSON.stringify({
  env: {
    baseUrl: envFields.baseUrl,
    model: envFields.model,
  },
  boolFields: boolFields.value.map(f => ({ key: f.key, value: f.value })),
  scalarFields: scalarFields.value.map(f => ({ key: f.key, value: f.value })),
  nestedFields: nestedFields.value.map(f => ({ key: f.key, yamlText: f.yamlText })),
}))

const hasUnsavedChanges = computed(() => {
  return showUserConfig.value && savedSnapshot.value !== '' && currentConfigSnapshot.value !== savedSnapshot.value
})

const saveStatusText = computed(() => {
  if (saving.value) return '保存中'
  if (saveMsg.value && !saveOk.value) return '保存失败'
  if (hasUnsavedChanges.value) return '有未保存修改'
  return '已保存'
})

const saveStatusClass = computed(() => {
  if (saving.value) return statusClass.neutral
  if (saveMsg.value && !saveOk.value) return statusClass.warn
  if (hasUnsavedChanges.value) return statusClass.warn
  return statusClass.ok
})

const webConfigFormSnapshot = computed(() => JSON.stringify({
  apiKey: normalizeApiKeyInput(webAiForm.apiKey),
  baseUrl: webAiForm.baseUrl,
  model: webAiForm.model,
  maxTokens: webAiForm.maxTokens,
  allowSharedAiCredentials: webAiForm.allowSharedAiCredentials,
  clearApiKey: webAiForm.clearApiKey,
}))
const webRunFormSnapshot = computed(() => JSON.stringify(webRunForm))
const webTemplateFormSnapshot = computed(() => webTemplateForm.outTemplatesJson.trim())

const hasWebConfigChanges = computed(() => (
  webConfigSnapshot.value !== '' && webConfigFormSnapshot.value !== webConfigSnapshot.value
))
const webRunSnapshot = ref('')
const webTemplateSnapshot = ref('')
const hasWebRunChanges = computed(() => webRunSnapshot.value !== '' && webRunFormSnapshot.value !== webRunSnapshot.value)
const hasWebTemplateChanges = computed(() => (
  webTemplateSnapshot.value !== '' && webTemplateFormSnapshot.value !== webTemplateSnapshot.value
))
const activeAdvancedFile = computed(() => (
  advancedConfigFiles.value.find(item => item.id === activeAdvancedFileId.value) || null
))
const hasAdvancedConfigChanges = computed(() => (
  activeAdvancedFileId.value !== '' && advancedConfigContent.value !== advancedConfigSnapshot.value
))
const fpaStrategyFormSnapshot = computed(() => JSON.stringify({
  defaultProfile: fpaStrategyForm.defaultProfile,
  profiles: fpaStrategyForm.profiles.map(profile => ({
    name: profile.name,
    strategy: profile.strategy,
    rule_set: profile.rule_set,
  })),
}))
const hasFpaStrategyChanges = computed(() => (
  fpaStrategySnapshot.value !== '' && fpaStrategyFormSnapshot.value !== fpaStrategySnapshot.value
))
const fpaJudgementRulesSnapshotCurrent = computed(() => JSON.stringify(
  fpaJudgementRules.value.map(rule => rule.text),
))
const hasFpaJudgementRulesChanges = computed(() => (
  fpaJudgementRulesSnapshot.value !== '' && fpaJudgementRulesSnapshotCurrent.value !== fpaJudgementRulesSnapshot.value
))
const businessRulesFormSnapshot = computed(() => JSON.stringify({
  cfpFormula: businessRulesForm.cfpFormula,
}))
const hasBusinessRulesChanges = computed(() => (
  businessRulesSnapshot.value !== '' && businessRulesFormSnapshot.value !== businessRulesSnapshot.value
))
const aiPromptsSnapshotCurrent = computed(() => JSON.stringify(
  aiPrompts.value.map(({ name, scene, system, examples }) => ({ name, scene, system, examples })),
))
const hasAiPromptsChanges = computed(() => (
  aiPromptsSnapshot.value !== '' && aiPromptsSnapshotCurrent.value !== aiPromptsSnapshot.value
))
const domainContextSections = computed(() => [
  {
    key: 'internal_data_groups' as DomainContextSectionKey,
    title: '本系统数据组',
    description: '本系统维护和拥有的数据组。',
    items: domainContextInternalDataGroups.value,
    requireSource: false,
  },
  {
    key: 'external_data_groups' as DomainContextSectionKey,
    title: '外部数据组',
    description: '由外部系统维护、本系统引用的数据组。',
    items: domainContextExternalDataGroups.value,
    requireSource: true,
  },
  {
    key: 'external_services' as DomainContextSectionKey,
    title: '外部服务',
    description: '不作为数据组计数的外部能力或平台。',
    items: domainContextExternalServices.value,
    requireSource: false,
  },
])
const domainContextSnapshotCurrent = computed(() => JSON.stringify(buildDomainContextPayload()))
const hasDomainContextChanges = computed(() => (
  domainContextSnapshot.value !== '' && domainContextSnapshotCurrent.value !== domainContextSnapshot.value
))

const webConfigSaveStatusText = computed(() => {
  if (webConfigSaving.value) return '保存中'
  if (webConfigSaveMsg.value && !webConfigSaveOk.value) return '保存失败'
  if (hasWebConfigChanges.value) return '有未保存修改'
  return '已保存'
})

const webConfigSaveStatusClass = computed(() => {
  if (webConfigSaving.value) return statusClass.neutral
  if (webConfigSaveMsg.value && !webConfigSaveOk.value) return statusClass.warn
  if (hasWebConfigChanges.value) return statusClass.warn
  return statusClass.ok
})
const advancedConfigStatusText = computed(() => {
  if (advancedConfigSaving.value) return '处理中'
  if (advancedConfigMessage.value && !advancedConfigOk.value) return '校验失败'
  if (hasAdvancedConfigChanges.value) return '有未保存修改'
  return '已保存'
})
const advancedConfigStatusClass = computed(() => {
  if (advancedConfigSaving.value) return statusClass.neutral
  if (advancedConfigMessage.value && !advancedConfigOk.value) return statusClass.warn
  if (hasAdvancedConfigChanges.value) return statusClass.warn
  return statusClass.ok
})
const fpaStrategyStatusText = computed(() => {
  if (fpaStrategySaving.value) return '保存中'
  if (fpaStrategyMsg.value && !fpaStrategyOk.value) return '保存失败'
  if (hasFpaStrategyChanges.value) return '有未保存修改'
  return '已保存'
})
const fpaStrategyStatusClass = computed(() => {
  if (fpaStrategySaving.value) return statusClass.neutral
  if (fpaStrategyMsg.value && !fpaStrategyOk.value) return statusClass.warn
  if (hasFpaStrategyChanges.value) return statusClass.warn
  return statusClass.ok
})
const fpaJudgementRulesStatusText = computed(() => {
  if (fpaJudgementRulesSaving.value) return '保存中'
  if (fpaJudgementRulesMsg.value && !fpaJudgementRulesOk.value) return '保存失败'
  if (hasFpaJudgementRulesChanges.value) return '有未保存修改'
  return '已保存'
})
const fpaJudgementRulesStatusClass = computed(() => {
  if (fpaJudgementRulesSaving.value) return statusClass.neutral
  if (fpaJudgementRulesMsg.value && !fpaJudgementRulesOk.value) return statusClass.warn
  if (hasFpaJudgementRulesChanges.value) return statusClass.warn
  return statusClass.ok
})
const businessRulesStatusText = computed(() => {
  if (businessRulesSaving.value) return '保存中'
  if (businessRulesMsg.value && !businessRulesOk.value) return '保存失败'
  if (hasBusinessRulesChanges.value) return '有未保存修改'
  return '已保存'
})
const businessRulesStatusClass = computed(() => {
  if (businessRulesSaving.value) return statusClass.neutral
  if (businessRulesMsg.value && !businessRulesOk.value) return statusClass.warn
  if (hasBusinessRulesChanges.value) return statusClass.warn
  return statusClass.ok
})
const aiPromptsStatusText = computed(() => {
  if (aiPromptsSaving.value) return '保存中'
  if (aiPromptsMsg.value && !aiPromptsOk.value) return '保存失败'
  if (hasAiPromptsChanges.value) return '有未保存修改'
  return '已保存'
})
const aiPromptsStatusClass = computed(() => {
  if (aiPromptsSaving.value) return statusClass.neutral
  if (aiPromptsMsg.value && !aiPromptsOk.value) return statusClass.warn
  if (hasAiPromptsChanges.value) return statusClass.warn
  return statusClass.ok
})
const domainContextStatusText = computed(() => {
  if (domainContextSaving.value) return '保存中'
  if (domainContextMsg.value && !domainContextOk.value) return '保存失败'
  if (hasDomainContextChanges.value) return '有未保存修改'
  return '已保存'
})
const domainContextStatusClass = computed(() => {
  if (domainContextSaving.value) return statusClass.neutral
  if (domainContextMsg.value && !domainContextOk.value) return statusClass.warn
  if (hasDomainContextChanges.value) return statusClass.warn
  return statusClass.ok
})

// ── 初始化 ────────────────────────────────────────────────

onMounted(async () => {
  await refreshHealth()
  await loadFpaOptions()
  await loadWebConfig()
  await loadConfigBackups()
  if (showUserConfig.value) {
    await loadUserConfig()
  } else {
    await loadLocalConfig()
    await loadFpaStrategySettings()
    await loadFpaJudgementRules()
    await loadBusinessRulesSettings()
    await loadDomainContextSettings()
    await loadAiPromptSettings()
    await loadAdvancedConfigFiles()
  }
})

const ConfigValueCard = defineComponent({
  name: 'ConfigValueCard',
  props: {
    label: { type: String, required: true },
    field: { type: Object as PropType<WebConfigField>, required: true },
    format: { type: Function as PropType<(value: unknown) => string>, default: null },
  },
  setup(props) {
    return () => h('div', { class: 'rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] px-3 py-2' }, [
      h('div', { class: 'flex items-center justify-between gap-3' }, [
        h('span', { class: 'text-sm text-[var(--color-ink-muted)]' }, props.label),
        h('span', { class: 'min-w-0 truncate text-sm font-semibold text-[var(--color-ink)]' }, formatConfigValue(props.field.value, props.format)),
      ]),
      h('p', { class: 'mt-1 text-xs text-[var(--color-ink-soft)]' }, `来源：${sourceLabel(props.field.source)}`),
    ])
  },
})

function formatStatus(value: boolean | null | undefined): string {
  if (value === true) return '正常'
  if (value === false) return '异常'
  return '未检测'
}

function statusClassFor(value: boolean | null | undefined): string {
  if (value === true) return statusClass.ok
  if (value === false) return statusClass.warn
  return statusClass.neutral
}

function profileLabel(name: string): string {
  return fpaOptions.value.profiles.find(profile => profile.name === name)?.label || name
}

function configTabId(key: ConfigSectionKey): string {
  return `config-section-tab-${key}`
}

function configPanelId(key: ConfigSectionKey): string {
  return `config-section-panel-${key}`
}

function presentConfigError(error: unknown): string {
  const message = normalizeApiError(error)
  if (backendOffline.value || isBackendUnavailableMessage(message)) {
    return '等待后端连接后加载'
  }
  return message
}

async function refreshHealth() {
  healthLoading.value = true
  healthError.value = ''
  try {
    health.value = await apiFetch<HealthResponse>('/api/health')
    healthCheckedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    health.value = null
    healthError.value = '后端未连接'
    healthCheckedAt.value = new Date().toLocaleTimeString()
  } finally {
    healthLoading.value = false
  }
}

async function loadWebConfig() {
  webConfigLoading.value = true
  webConfigError.value = ''
  try {
    webConfig.value = await apiFetch<WebConfigResponse>('/api/web-config')
    applyWebConfigToForm(webConfig.value)
  } catch (e) {
    webConfig.value = null
    webConfigError.value = presentConfigError(e)
  } finally {
    webConfigLoading.value = false
  }
}

async function loadConfigBackups() {
  configBackupsLoading.value = true
  configBackupsError.value = ''
  try {
    const data = await apiFetch<ConfigBackupsResponse>('/api/web-config/backups')
    configBackups.value = data.items || []
  } catch (e) {
    configBackups.value = []
    configBackupsError.value = presentConfigError(e)
  } finally {
    configBackupsLoading.value = false
  }
}

async function loadConfigBackupDiff(item: ConfigBackupItem) {
  configBackupDiffLoading.value = true
  configBackupDiffError.value = ''
  configBackupDiffId.value = item.id
  try {
    configBackupDiff.value = await apiFetch<ConfigBackupDiffResponse>(`/api/web-config/backups/${encodeURIComponent(item.id)}/diff`)
  } catch (e) {
    configBackupDiff.value = null
    configBackupDiffError.value = presentConfigError(e)
  } finally {
    configBackupDiffLoading.value = false
  }
}

function clearConfigBackupDiff() {
  configBackupDiff.value = null
  configBackupDiffError.value = ''
  configBackupDiffId.value = ''
}

async function refreshLocalConfigSections() {
  await loadWebConfig()
  await loadConfigBackups()
  await loadLocalConfig()
  await loadFpaStrategySettings()
  await loadFpaJudgementRules()
  await loadBusinessRulesSettings()
  await loadDomainContextSettings()
  await loadAiPromptSettings()
  await loadAdvancedConfigFiles()
}

async function exportConfigPackage() {
  configPackageLoading.value = true
  configPackageMsg.value = ''
  try {
    const data = await apiFetch<Record<string, unknown>>('/api/web-config/package')
    const json = JSON.stringify(data, null, 2)
    const blob = new Blob([json], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `ard-config-package-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    configPackageOk.value = true
    configPackageMsg.value = '配置包已导出'
  } catch (e) {
    configPackageOk.value = false
    configPackageMsg.value = presentConfigError(e)
  } finally {
    configPackageLoading.value = false
  }
}

async function importConfigPackage() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json,application/json'
  input.onchange = async (event: Event) => {
    const file = (event.target as HTMLInputElement)?.files?.[0]
    if (!file) return
    configPackageLoading.value = true
    configPackageMsg.value = ''
    try {
      const payload = JSON.parse(await file.text())
      const data = await apiFetch<ConfigPackageImportResponse>('/api/web-config/package', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      clearConfigBackupDiff()
      await refreshLocalConfigSections()
      configPackageOk.value = true
      configPackageMsg.value = `导入成功：${data.imported.join(', ')}`
    } catch (e) {
      configPackageOk.value = false
      configPackageMsg.value = presentConfigError(e)
    } finally {
      configPackageLoading.value = false
    }
  }
  input.click()
}

async function loadFpaStrategySettings() {
  fpaStrategyLoading.value = true
  fpaStrategyError.value = ''
  try {
    const data = await apiFetch<FpaStrategySettingsResponse>('/api/web-config/fpa-strategy')
    applyFpaStrategySettings(data)
  } catch (e) {
    fpaStrategyForm.defaultProfile = ''
    fpaStrategyForm.profiles = []
    fpaStrategyForm.ruleSets = []
    fpaStrategySnapshot.value = ''
    fpaStrategyError.value = presentConfigError(e)
  } finally {
    fpaStrategyLoading.value = false
  }
}

function applyFpaStrategySettings(data: FpaStrategySettingsResponse) {
  fpaStrategyForm.defaultProfile = data.default_profile || ''
  fpaStrategyForm.profiles = (data.profiles || []).map(profile => ({ ...profile }))
  fpaStrategyForm.ruleSets = (data.rule_sets || []).map(ruleSet => ({ ...ruleSet }))
  fpaStrategyMsg.value = ''
  fpaStrategyOk.value = true
  fpaStrategySnapshot.value = fpaStrategyFormSnapshot.value
}

async function saveFpaStrategySettings() {
  fpaStrategySaving.value = true
  fpaStrategyMsg.value = ''
  try {
    const data = await apiFetch<FpaStrategySettingsResponse>('/api/web-config/fpa-strategy', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        default_profile: fpaStrategyForm.defaultProfile,
        profiles: fpaStrategyForm.profiles.map(profile => ({
          name: profile.name,
          strategy: profile.strategy,
          rule_set: profile.rule_set,
        })),
      }),
    })
    applyFpaStrategySettings(data)
    fpaStrategyOk.value = true
    fpaStrategyMsg.value = '保存成功'
    await loadFpaOptions()
    await loadConfigBackups()
    await loadLocalConfig()
    if (activeAdvancedFileId.value === 'fpa_config') {
      await loadAdvancedConfigFile('fpa_config')
    } else {
      await loadAdvancedConfigFiles()
    }
  } catch (e) {
    fpaStrategyOk.value = false
    fpaStrategyMsg.value = presentConfigError(e)
  } finally {
    fpaStrategySaving.value = false
  }
}

async function loadFpaJudgementRules() {
  fpaJudgementRulesLoading.value = true
  fpaJudgementRulesError.value = ''
  try {
    const data = await apiFetch<FpaJudgementRulesResponse>('/api/web-config/fpa-judgement-rules')
    applyFpaJudgementRules(data.rules || [])
  } catch (e) {
    fpaJudgementRules.value = []
    fpaJudgementRulesSnapshot.value = ''
    fpaJudgementRulesError.value = presentConfigError(e)
  } finally {
    fpaJudgementRulesLoading.value = false
  }
}

function applyFpaJudgementRules(rules: string[]) {
  fpaJudgementRules.value = rules.length
    ? rules.map(text => ({ id: fpaJudgementRuleNextId.value++, text }))
    : [{ id: fpaJudgementRuleNextId.value++, text: '' }]
  fpaJudgementRulesMsg.value = ''
  fpaJudgementRulesOk.value = true
  fpaJudgementRulesSnapshot.value = fpaJudgementRulesSnapshotCurrent.value
}

function addFpaJudgementRule() {
  fpaJudgementRules.value.push({ id: fpaJudgementRuleNextId.value++, text: '' })
}

function removeFpaJudgementRule(index: number) {
  if (fpaJudgementRules.value.length <= 1) return
  fpaJudgementRules.value.splice(index, 1)
}

function moveFpaJudgementRule(index: number, direction: -1 | 1) {
  const nextIndex = index + direction
  if (nextIndex < 0 || nextIndex >= fpaJudgementRules.value.length) return
  const [item] = fpaJudgementRules.value.splice(index, 1)
  fpaJudgementRules.value.splice(nextIndex, 0, item)
}

async function saveFpaJudgementRules() {
  const rules = fpaJudgementRules.value.map(rule => rule.text.trim()).filter(Boolean)
  if (!rules.length) {
    fpaJudgementRulesOk.value = false
    fpaJudgementRulesMsg.value = '至少保留 1 条计算依据归类判定原则'
    return
  }

  fpaJudgementRulesSaving.value = true
  fpaJudgementRulesMsg.value = ''
  try {
    const data = await apiFetch<FpaJudgementRulesResponse>('/api/web-config/fpa-judgement-rules', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules }),
    })
    applyFpaJudgementRules(data.rules || rules)
    fpaJudgementRulesOk.value = true
    fpaJudgementRulesMsg.value = '保存成功'
    await loadConfigBackups()
    await loadLocalConfig()
    if (activeAdvancedFileId.value === 'fpa_judgement_rules') {
      await loadAdvancedConfigFile('fpa_judgement_rules')
    } else {
      await loadAdvancedConfigFiles()
    }
  } catch (e) {
    fpaJudgementRulesOk.value = false
    fpaJudgementRulesMsg.value = presentConfigError(e)
  } finally {
    fpaJudgementRulesSaving.value = false
  }
}

async function loadBusinessRulesSettings() {
  businessRulesLoading.value = true
  businessRulesError.value = ''
  try {
    const data = await apiFetch<BusinessRulesResponse>('/api/web-config/business-rules')
    businessRulesForm.cfpFormula = data.cfp_formula || ''
    businessRulesMsg.value = ''
    businessRulesOk.value = true
    businessRulesSnapshot.value = businessRulesFormSnapshot.value
  } catch (e) {
    businessRulesForm.cfpFormula = ''
    businessRulesSnapshot.value = ''
    businessRulesError.value = presentConfigError(e)
  } finally {
    businessRulesLoading.value = false
  }
}

async function saveBusinessRulesSettings() {
  if (!businessRulesForm.cfpFormula.trim()) {
    businessRulesOk.value = false
    businessRulesMsg.value = 'CFP 计算公式不能为空'
    return
  }

  businessRulesSaving.value = true
  businessRulesMsg.value = ''
  try {
    const data = await apiFetch<BusinessRulesResponse>('/api/web-config/business-rules', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cfp_formula: businessRulesForm.cfpFormula }),
    })
    businessRulesForm.cfpFormula = data.cfp_formula || businessRulesForm.cfpFormula
    businessRulesSnapshot.value = businessRulesFormSnapshot.value
    businessRulesOk.value = true
    businessRulesMsg.value = '保存成功'
    await loadConfigBackups()
    await loadLocalConfig()
    if (activeAdvancedFileId.value === 'business_rules') {
      await loadAdvancedConfigFile('business_rules')
    } else {
      await loadAdvancedConfigFiles()
    }
  } catch (e) {
    businessRulesOk.value = false
    businessRulesMsg.value = presentConfigError(e)
  } finally {
    businessRulesSaving.value = false
  }
}

function splitAliases(text: string): string[] {
  return text
    .split(/[\n,，]/)
    .map(item => item.trim())
    .filter(Boolean)
}

function domainContextItemFromPayload(item: DomainContextItemPayload): DomainContextItem {
  return {
    id: domainContextNextId.value++,
    name: item.name || '',
    aliasesText: (item.aliases || []).join('\n'),
    description: item.description || '',
    source: item.source || '',
  }
}

function domainContextPayloadFromItems(items: DomainContextItem[], requireSource = false): DomainContextItemPayload[] {
  return items.map(item => {
    const payload: DomainContextItemPayload = {
      name: item.name.trim(),
    }
    const aliases = splitAliases(item.aliasesText)
    if (aliases.length) payload.aliases = aliases
    if (item.description) payload.description = item.description
    if (requireSource) payload.source = item.source.trim()
    return payload
  })
}

function domainContextItemsFor(key: DomainContextSectionKey): DomainContextItem[] {
  if (key === 'internal_data_groups') return domainContextInternalDataGroups.value
  if (key === 'external_data_groups') return domainContextExternalDataGroups.value
  return domainContextExternalServices.value
}

function buildDomainContextPayload(): DomainContextResponse {
  return {
    system_boundary: domainContextForm.systemBoundary,
    internal_data_groups: domainContextPayloadFromItems(domainContextInternalDataGroups.value),
    external_data_groups: domainContextPayloadFromItems(domainContextExternalDataGroups.value, true),
    external_services: domainContextPayloadFromItems(domainContextExternalServices.value),
    exists: true,
  }
}

function applyDomainContextSettings(data: DomainContextResponse) {
  domainContextForm.systemBoundary = data.system_boundary || ''
  domainContextInternalDataGroups.value = (data.internal_data_groups || []).map(domainContextItemFromPayload)
  domainContextExternalDataGroups.value = (data.external_data_groups || []).map(domainContextItemFromPayload)
  domainContextExternalServices.value = (data.external_services || []).map(domainContextItemFromPayload)
  domainContextMsg.value = ''
  domainContextOk.value = true
  domainContextSnapshot.value = domainContextSnapshotCurrent.value
}

function addDomainContextItem(key: DomainContextSectionKey) {
  domainContextItemsFor(key).push({
    id: domainContextNextId.value++,
    name: '',
    aliasesText: '',
    description: '',
    source: '',
  })
}

function removeDomainContextItem(key: DomainContextSectionKey, index: number) {
  domainContextItemsFor(key).splice(index, 1)
}

async function loadDomainContextSettings() {
  domainContextLoading.value = true
  domainContextError.value = ''
  try {
    const data = await apiFetch<DomainContextResponse>('/api/web-config/domain-context')
    applyDomainContextSettings(data)
  } catch (e) {
    domainContextForm.systemBoundary = ''
    domainContextInternalDataGroups.value = []
    domainContextExternalDataGroups.value = []
    domainContextExternalServices.value = []
    domainContextSnapshot.value = ''
    domainContextError.value = presentConfigError(e)
  } finally {
    domainContextLoading.value = false
  }
}

async function saveDomainContextSettings() {
  for (const section of domainContextSections.value) {
    for (const item of section.items) {
      if (!item.name.trim()) {
        domainContextOk.value = false
        domainContextMsg.value = `${section.title}名称不能为空`
        return
      }
      if (section.requireSource && !item.source.trim()) {
        domainContextOk.value = false
        domainContextMsg.value = `${section.title}来源系统不能为空`
        return
      }
    }
  }

  domainContextSaving.value = true
  domainContextMsg.value = ''
  try {
    const data = await apiFetch<DomainContextResponse>('/api/web-config/domain-context', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildDomainContextPayload()),
    })
    applyDomainContextSettings(data)
    domainContextOk.value = true
    domainContextMsg.value = '保存成功'
    await loadConfigBackups()
    await loadLocalConfig()
    if (activeAdvancedFileId.value === 'domain_context') {
      await loadAdvancedConfigFile('domain_context')
    } else {
      await loadAdvancedConfigFiles()
    }
  } catch (e) {
    domainContextOk.value = false
    domainContextMsg.value = presentConfigError(e)
  } finally {
    domainContextSaving.value = false
  }
}

function applyAiPromptSettings(prompts: Omit<AiPromptItem, 'id'>[]) {
  aiPrompts.value = prompts.map(prompt => ({
    id: aiPromptNextId.value++,
    name: prompt.name || '',
    scene: prompt.scene || '',
    system: prompt.system || '',
    examples: prompt.examples || '',
  }))
  aiPromptsMsg.value = ''
  aiPromptsOk.value = true
  aiPromptsSnapshot.value = aiPromptsSnapshotCurrent.value
}

function addAiPrompt() {
  aiPrompts.value.push({
    id: aiPromptNextId.value++,
    name: '',
    scene: '',
    system: '',
    examples: '',
  })
}

function removeAiPrompt(index: number) {
  aiPrompts.value.splice(index, 1)
}

async function loadAiPromptSettings() {
  aiPromptsLoading.value = true
  aiPromptsError.value = ''
  try {
    const data = await apiFetch<AiPromptsResponse>('/api/web-config/ai-prompts')
    applyAiPromptSettings(data.prompts || [])
  } catch (e) {
    aiPrompts.value = []
    aiPromptsSnapshot.value = ''
    aiPromptsError.value = presentConfigError(e)
  } finally {
    aiPromptsLoading.value = false
  }
}

async function saveAiPromptSettings() {
  const names = new Set<string>()
  for (const prompt of aiPrompts.value) {
    const name = prompt.name.trim()
    if (!name) {
      aiPromptsOk.value = false
      aiPromptsMsg.value = '场景名称不能为空'
      return
    }
    if (names.has(name)) {
      aiPromptsOk.value = false
      aiPromptsMsg.value = `场景名称重复：${name}`
      return
    }
    names.add(name)
  }

  aiPromptsSaving.value = true
  aiPromptsMsg.value = ''
  try {
    const data = await apiFetch<AiPromptsResponse>('/api/web-config/ai-prompts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompts: aiPrompts.value.map(({ name, scene, system, examples }) => ({ name, scene, system, examples })),
      }),
    })
    applyAiPromptSettings(data.prompts || [])
    aiPromptsOk.value = true
    aiPromptsMsg.value = '保存成功'
    await loadConfigBackups()
    await loadLocalConfig()
    if (activeAdvancedFileId.value === 'ai_system_prompts_config') {
      await loadAdvancedConfigFile('ai_system_prompts_config')
    } else {
      await loadAdvancedConfigFiles()
    }
  } catch (e) {
    aiPromptsOk.value = false
    aiPromptsMsg.value = presentConfigError(e)
  } finally {
    aiPromptsSaving.value = false
  }
}

async function loadAdvancedConfigFiles() {
  advancedConfigLoading.value = true
  advancedConfigError.value = ''
  try {
    const data = await apiFetch<AdvancedConfigFilesResponse>('/api/web-config/files')
    advancedConfigFiles.value = data.items || []
    if (!activeAdvancedFileId.value && advancedConfigFiles.value.length) {
      await loadAdvancedConfigFile(advancedConfigFiles.value[0].id)
    }
  } catch (e) {
    advancedConfigFiles.value = []
    activeAdvancedFileId.value = ''
    advancedConfigContent.value = ''
    advancedConfigSnapshot.value = ''
    advancedConfigError.value = presentConfigError(e)
  } finally {
    advancedConfigLoading.value = false
  }
}

async function selectAdvancedFile(fileId: string) {
  if (fileId === activeAdvancedFileId.value) return
  if (hasAdvancedConfigChanges.value) {
    const confirmed = window.confirm('当前高级配置有未保存修改，确认切换文件？')
    if (!confirmed) return
  }
  await loadAdvancedConfigFile(fileId)
}

async function loadAdvancedConfigFile(fileId: string) {
  if (!fileId) return
  advancedConfigLoading.value = true
  advancedConfigError.value = ''
  advancedConfigMessage.value = ''
  advancedConfigOk.value = false
  try {
    const data = await apiFetch<AdvancedConfigFileResponse>(`/api/web-config/files/${encodeURIComponent(fileId)}`)
    activeAdvancedFileId.value = data.id
    advancedConfigContent.value = data.content || ''
    advancedConfigSnapshot.value = advancedConfigContent.value
  } catch (e) {
    advancedConfigError.value = presentConfigError(e)
  } finally {
    advancedConfigLoading.value = false
  }
}

async function validateAdvancedConfig() {
  if (!activeAdvancedFileId.value) return
  advancedConfigSaving.value = true
  advancedConfigMessage.value = ''
  try {
    await apiFetch(`/api/web-config/files/${encodeURIComponent(activeAdvancedFileId.value)}/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: advancedConfigContent.value }),
    })
    advancedConfigOk.value = true
    advancedConfigMessage.value = '校验通过'
  } catch (e) {
    advancedConfigOk.value = false
    advancedConfigMessage.value = presentConfigError(e)
  } finally {
    advancedConfigSaving.value = false
  }
}

async function saveAdvancedConfig() {
  if (!activeAdvancedFileId.value) return
  advancedConfigSaving.value = true
  advancedConfigMessage.value = ''
  try {
    const data = await apiFetch<AdvancedConfigFileResponse>(`/api/web-config/files/${encodeURIComponent(activeAdvancedFileId.value)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: advancedConfigContent.value }),
    })
    advancedConfigContent.value = data.content || advancedConfigContent.value
    advancedConfigSnapshot.value = advancedConfigContent.value
    advancedConfigOk.value = true
    advancedConfigMessage.value = '保存成功'
    await loadAdvancedConfigFiles()
    await loadConfigBackups()
    await loadLocalConfig()
  } catch (e) {
    advancedConfigOk.value = false
    advancedConfigMessage.value = presentConfigError(e)
  } finally {
    advancedConfigSaving.value = false
  }
}

function applyWebConfigToForm(data: WebConfigResponse) {
  webAiForm.apiKey = ''
  webAiForm.baseUrl = String(data.ai.base_url.value || '')
  webAiForm.model = String(data.ai.model.value || '')
  webAiForm.maxTokens = String(data.ai.max_tokens.value || '')
  webAiForm.allowSharedAiCredentials = Boolean(data.ai.allow_shared_ai_credentials.value)
  webAiForm.clearApiKey = false
  webConfigSaveMsg.value = ''
  webConfigSaveOk.value = true
  webConfigSnapshot.value = webConfigFormSnapshot.value
  webRunForm.projectName = fieldValue(data.run_defaults.project_name)
  webRunForm.fpaProfile = fieldValue(data.run_defaults.fpa_profile) || 'strict_fpa'
  webRunForm.fpaStrategy = fieldValue(data.run_defaults.fpa_strategy)
  webRunForm.fpaRuleSet = fieldValue(data.run_defaults.fpa_rule_set)
  webRunForm.fpaConfirmationMode = fieldValue(data.run_defaults.fpa_confirmation_mode) || 'cautious'
  webRunSnapshot.value = webRunFormSnapshot.value
  webTemplateForm.outTemplatesJson = JSON.stringify(data.templates.out_templates.value || {}, null, 2)
  webTemplateSnapshot.value = webTemplateFormSnapshot.value
}

function handleClearWebApiKeyChange() {
  if (webAiForm.clearApiKey) {
    webAiForm.apiKey = ''
  }
}

async function saveWebConfig() {
  webConfigSaving.value = true
  webConfigSaveMsg.value = ''

  const ai: Record<string, unknown> = {
    base_url: { value: webAiForm.baseUrl },
    model: { value: webAiForm.model },
    max_tokens: { value: webAiForm.maxTokens },
  }
  const apiKey = normalizeApiKeyInput(webAiForm.apiKey)
  if (apiKey) ai.api_key = apiKey
  if (webAiForm.clearApiKey) ai.clear_api_key = true
  if (webConfig.value?.scope.mode === 'local') {
    ai.allow_shared_ai_credentials = { value: webAiForm.allowSharedAiCredentials }
  }

  try {
    const data = await apiFetch<WebConfigResponse>('/api/web-config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ai }),
    })
    webConfig.value = data
    applySavedWebConfig(data)
    webConfigSaveOk.value = true
    webConfigSaveMsg.value = '保存成功'
    await loadConfigBackups()
    await loadLocalConfig()
    if (showUserConfig.value) {
      await loadUserConfig()
    }
  } catch (e) {
    webConfigSaveOk.value = false
    webConfigSaveMsg.value = presentConfigError(e)
  } finally {
    webConfigSaving.value = false
  }
}

async function saveRunDefaults() {
  await saveWebConfigPayload({
    run_defaults: {
      project_name: { value: webRunForm.projectName },
      fpa_profile: { value: webRunForm.fpaProfile },
      fpa_strategy: { value: webRunForm.fpaStrategy },
      fpa_rule_set: { value: webRunForm.fpaRuleSet },
      fpa_confirmation_mode: { value: webRunForm.fpaConfirmationMode },
    },
  }, '运行默认值保存成功')
}

async function saveTemplateSettings() {
  let outTemplates: Record<string, string>
  try {
    const parsed = JSON.parse(webTemplateForm.outTemplatesJson || '{}')
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('out_templates 必须是 JSON 对象')
    }
    outTemplates = Object.fromEntries(
      Object.entries(parsed).map(([key, value]) => [key, String(value)]),
    )
  } catch (e) {
    webConfigSaveOk.value = false
    webConfigSaveMsg.value = e instanceof Error ? e.message : 'out_templates 格式错误'
    return
  }

  await saveWebConfigPayload({
    templates: {
      out_templates: { value: outTemplates },
    },
  }, '模板映射保存成功')
}

async function saveWebConfigPayload(payload: Record<string, unknown>, successMessage: string) {
  webConfigSaving.value = true
  webConfigSaveMsg.value = ''
  try {
    const data = await apiFetch<WebConfigResponse>('/api/web-config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    webConfig.value = data
    applySavedWebConfig(data)
    webConfigSaveOk.value = true
    webConfigSaveMsg.value = successMessage
    await loadConfigBackups()
    await loadLocalConfig()
    if (showUserConfig.value) {
      await loadUserConfig()
    }
  } catch (e) {
    webConfigSaveOk.value = false
    webConfigSaveMsg.value = presentConfigError(e)
  } finally {
    webConfigSaving.value = false
  }
}

function applySavedWebConfig(data: WebConfigResponse) {
  configStore.baseUrl = String(data.ai.base_url.value || '')
  configStore.model = String(data.ai.model.value || '')
  configStore.maxTokens = String(data.ai.max_tokens.value || '')
  configStore.projectName = fieldValue(data.run_defaults.project_name)
  configStore.fpaProfile = fieldValue(data.run_defaults.fpa_profile) || 'strict_fpa'
  configStore.fpaStrategy = fieldValue(data.run_defaults.fpa_strategy)
  configStore.fpaRuleSet = fieldValue(data.run_defaults.fpa_rule_set)
  configStore.fpaConfirmationMode = (fieldValue(data.run_defaults.fpa_confirmation_mode) || 'cautious') as any
  applyWebConfigToForm(data)
}

function fieldValue(field: WebConfigField<unknown> | undefined): string {
  if (!field || field.value === null || field.value === undefined) return ''
  return String(field.value)
}

function sourceLabel(source: ConfigSource | string): string {
  const labels: Record<string, string> = {
    personal: '个人配置',
    global: '全局配置',
    default: '系统默认',
  }
  return labels[source] || source
}

function formatEnabled(value: unknown): string {
  return value ? '开启' : '关闭'
}

function formatConfigValue(value: unknown, formatter?: ((value: unknown) => string) | null): string {
  if (formatter) return formatter(value)
  if (value === null || value === undefined || value === '') return '未设置'
  if (typeof value === 'boolean') return formatEnabled(value)
  return String(value)
}

function formatTime(value: string): string {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value)) return '-'
  if (value < 1024) return `${value} B`
  return `${(value / 1024).toFixed(1)} KB`
}

async function restoreConfigBackup(item: ConfigBackupItem) {
  const confirmed = window.confirm(`确认恢复 ${item.file} 的这份备份？恢复前会先备份当前配置。`)
  if (!confirmed) return

  configRestoreLoading.value = true
  configRestoreMsg.value = ''
  configRestoreOk.value = false
  restoringBackupId.value = item.id
  try {
    const data = await apiFetch<WebConfigResponse>('/api/web-config/backups/restore', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_id: item.id }),
    })
    webConfig.value = data
    applySavedWebConfig(data)
    configRestoreOk.value = true
    configRestoreMsg.value = '恢复成功'
    clearConfigBackupDiff()
    await loadConfigBackups()
    await loadLocalConfig()
    if (showUserConfig.value) {
      await loadUserConfig()
    } else {
      await loadFpaStrategySettings()
      await loadFpaJudgementRules()
      await loadBusinessRulesSettings()
      await loadDomainContextSettings()
      await loadAiPromptSettings()
      await loadAdvancedConfigFiles()
    }
  } catch (e) {
    configRestoreOk.value = false
    configRestoreMsg.value = presentConfigError(e)
  } finally {
    configRestoreLoading.value = false
    restoringBackupId.value = ''
  }
}

function webSectionStatusText(hasChanges: boolean): string {
  if (webConfigSaving.value) return '保存中'
  if (webConfigSaveMsg.value && !webConfigSaveOk.value) return '保存失败'
  if (hasChanges) return '有未保存修改'
  return '已保存'
}

function webSectionStatusClass(hasChanges: boolean): string {
  if (webConfigSaving.value) return statusClass.neutral
  if (webConfigSaveMsg.value && !webConfigSaveOk.value) return statusClass.warn
  if (hasChanges) return statusClass.warn
  return statusClass.ok
}

async function loadLocalConfig() {
  try {
    const data = await apiFetch<ConfigReadResponse>('/api/config-read')
    envContent.value = data.env || ''
    systemConfig.value = data.system_config || ''
    businessRules.value = data.business_rules || ''
  } catch (e) {
    const msg = presentConfigError(e)
    envContent.value = '读取失败'
    systemConfig.value = msg
    businessRules.value = msg
  }
}

async function loadUserConfig() {
  // 加载原始文本（用于 nested textarea 和 全局参考）
  const [readResult, cfgResult] = await Promise.allSettled([
    apiFetch<ConfigReadResponse>('/api/config-read'),
    apiFetch<UserConfigResponse>('/api/user/config'),
  ])

  if (readResult.status === 'fulfilled') {
    const d = readResult.value
    globalEnvContent.value = d.global_env || ''
    globalSystemConfig.value = d.global_system || ''
    businessRules.value = d.business_rules || ''
    // 解析个人 env
    if (d.env) {
      for (const line of d.env.split('\n')) {
        const m = line.match(/^(\w+)=(.+)/)
        if (m) {
          const k = m[1].trim()
          const v = m[2].trim()
          if (k === 'ANTHROPIC_BASE_URL') envFields.baseUrl = v
          else if (k === 'ANTHROPIC_MODEL') envFields.model = v
        }
      }
    }
  }

  if (cfgResult.status === 'fulfilled') {
    const data = cfgResult.value
    const sys = data._system || {}
    buildFormFields(sys)
  }

  savedSnapshot.value = currentConfigSnapshot.value
}

// ── 从 YAML dict 构建表单字段 ──────────────────────────────

const SELECT_OPTIONS: Record<string, string[]> = {
  web_work_mode: ['auto', 'local', 'remote'],
  log_level: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
}

const NESTED_KEYS = new Set(['sheets', 'out_templates'])

function buildFormFields(sys: Record<string, any>) {
  const bools: ScalarField[] = []
  const scalars: ScalarField[] = []
  const nesteds: NestedField[] = []

  for (const [key, val] of Object.entries(sys)) {
    if (typeof val === 'boolean') {
      bools.push({ key, type: 'bool', value: val })
    } else if (NESTED_KEYS.has(key) || typeof val === 'object') {
      nesteds.push({ key, yamlText: toYamlLike(val) })
    } else if (SELECT_OPTIONS[key]) {
      scalars.push({ key, type: 'select', value: String(val), options: SELECT_OPTIONS[key] })
    } else if (typeof val === 'number') {
      scalars.push({ key, type: 'number', value: val })
    } else {
      scalars.push({ key, type: 'text', value: String(val) })
    }
  }

  boolFields.value = bools
  scalarFields.value = scalars
  nestedFields.value = nesteds
}

/** 把对象转成接近 YAML 风格的纯文本（缩进 2 空格）。 */
function toYamlLike(obj: any, indent = 0): string {
  if (obj === null || obj === undefined) return ''
  if (typeof obj !== 'object') return String(obj)
  const pad = '  '.repeat(indent)
  const lines: string[] = []
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'object' && v !== null) {
      lines.push(`${pad}${k}:`)
      lines.push(toYamlLike(v, indent + 1))
    } else {
      lines.push(`${pad}${k}: ${v}`)
    }
  }
  return lines.join('\n')
}

/** 把 textarea 的 YAML 风格文本解析回对象。 */
function fromYamlLike(text: string): any {
  // 简单解析 — 仅支持嵌套 dict，值均为字符串
  const result: Record<string, any> = {}
  const stack: { indent: number; obj: Record<string, any> }[] = [{ indent: -1, obj: result }]

  for (const line of text.split('\n')) {
    if (!line.trim() || line.trim().startsWith('#')) continue
    const indent = line.search(/\S/)
    const content = line.trim()
    const colonIdx = content.indexOf(':')

    // 回退栈
    while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
      stack.pop()
    }

    if (colonIdx > 0) {
      const key = content.substring(0, colonIdx).trim()
      const val = content.substring(colonIdx + 1).trim()
      if (val) {
        stack[stack.length - 1].obj[key] = val
      } else {
        // 嵌套对象开始
        const child: Record<string, any> = {}
        stack[stack.length - 1].obj[key] = child
        stack.push({ indent, obj: child })
      }
    }
  }
  return result
}

// ── 保存 ──────────────────────────────────────────────────

async function saveUserConfig() {
  saving.value = true
  saveMsg.value = ''

  // 构建 _env
  const env: Record<string, string> = {}
  if (envFields.baseUrl) env['ANTHROPIC_BASE_URL'] = envFields.baseUrl
  if (envFields.model) env['ANTHROPIC_MODEL'] = envFields.model

  // 构建 _system
  const system: Record<string, any> = {}

  for (const f of boolFields.value) {
    system[f.key] = f.value
  }
  for (const f of scalarFields.value) {
    if (f.type === 'number') {
      system[f.key] = Number(f.value)
    } else {
      system[f.key] = f.value
    }
  }
  for (const f of nestedFields.value) {
    try {
      system[f.key] = fromYamlLike(f.yamlText)
    } catch {
      saveOk.value = false
      saveMsg.value = `${f.key} 格式错误，请检查`
      saving.value = false
      return
    }
  }

  try {
    await apiFetch('/api/user/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ _env: env, _system: system }),
    })
    saveOk.value = true
    saveMsg.value = '保存成功'
    savedSnapshot.value = currentConfigSnapshot.value
    lastSavedAt.value = new Date().toLocaleTimeString()
  } catch (e) {
    saveOk.value = false
    saveMsg.value = presentConfigError(e)
  }
  saving.value = false
}

// ── 导出/导入 ─────────────────────────────────────────────

function exportSettings() {
  const json = configStore.exportSettings()
  const blob = new Blob([json], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `ard-settings-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(a.href)
}

async function importSettings() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e: any) => {
    const file = e.target?.files?.[0]
    if (!file) return
    const text = await file.text()
    if (configStore.importSettings(text)) {
      saveMsg.value = '导入成功，请点保存'
      saveOk.value = true
    } else {
      saveMsg.value = '导入失败：文件格式不正确'
      saveOk.value = false
    }
  }
  input.click()
}
</script>
