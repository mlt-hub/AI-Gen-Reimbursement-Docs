import { ref, computed, onMounted, reactive } from 'vue';
import { useAuthStore } from '@/stores/auth';
import { useConfigStore } from '@/stores/config';
import { apiFetch, normalizeApiError } from '@/lib/api';
// ── stores ────────────────────────────────────────────────
const auth = useAuthStore();
const configStore = useConfigStore();
const showUserConfig = computed(() => auth.isRemote);
// ── 只读内容 ──────────────────────────────────────────────
const envContent = ref(null);
const systemConfig = ref(null);
const businessRules = ref(null);
const globalEnvContent = ref('');
const globalSystemConfig = ref('');
// ── 可编辑字段 ────────────────────────────────────────────
const envFields = reactive({ apiKey: '', baseUrl: '', model: '' });
const boolFields = ref([]);
const scalarFields = ref([]);
const nestedFields = ref([]);
const saving = ref(false);
const saveMsg = ref('');
const saveOk = ref(false);
// ── 初始化 ────────────────────────────────────────────────
onMounted(async () => {
    if (showUserConfig.value) {
        await loadUserConfig();
    }
    else {
        await loadLocalConfig();
    }
});
async function loadLocalConfig() {
    try {
        const data = await apiFetch('/api/config-read');
        envContent.value = data.env || '';
        systemConfig.value = data.system_config || '';
        businessRules.value = data.business_rules || '';
    }
    catch (e) {
        const msg = normalizeApiError(e);
        envContent.value = '读取失败';
        systemConfig.value = msg;
        businessRules.value = msg;
    }
}
async function loadUserConfig() {
    // 加载原始文本（用于 nested textarea 和 全局参考）
    const [readResult, cfgResult] = await Promise.allSettled([
        apiFetch('/api/config-read'),
        apiFetch('/api/user/config'),
    ]);
    if (readResult.status === 'fulfilled') {
        const d = readResult.value;
        globalEnvContent.value = d.global_env || '';
        globalSystemConfig.value = d.global_system || '';
        businessRules.value = d.business_rules || '';
        // 解析个人 env
        if (d.env) {
            for (const line of d.env.split('\n')) {
                const m = line.match(/^(\w+)=(.+)/);
                if (m) {
                    const k = m[1].trim();
                    const v = m[2].trim();
                    if (k === 'ANTHROPIC_API_KEY')
                        envFields.apiKey = v;
                    else if (k === 'ANTHROPIC_BASE_URL')
                        envFields.baseUrl = v;
                    else if (k === 'ANTHROPIC_MODEL')
                        envFields.model = v;
                }
            }
        }
    }
    if (cfgResult.status === 'fulfilled') {
        const data = cfgResult.value;
        const sys = data._system || {};
        buildFormFields(sys);
    }
}
// ── 从 YAML dict 构建表单字段 ──────────────────────────────
const SELECT_OPTIONS = {
    web_work_mode: ['auto', 'local', 'remote'],
    log_level: ['DEBUG', 'INFO', 'WARNING', 'ERROR'],
};
const NESTED_KEYS = new Set(['sheets', 'out_templates']);
function buildFormFields(sys) {
    const bools = [];
    const scalars = [];
    const nesteds = [];
    for (const [key, val] of Object.entries(sys)) {
        if (typeof val === 'boolean') {
            bools.push({ key, type: 'bool', value: val });
        }
        else if (NESTED_KEYS.has(key) || typeof val === 'object') {
            nesteds.push({ key, yamlText: toYamlLike(val) });
        }
        else if (SELECT_OPTIONS[key]) {
            scalars.push({ key, type: 'select', value: String(val), options: SELECT_OPTIONS[key] });
        }
        else if (typeof val === 'number') {
            scalars.push({ key, type: 'number', value: val });
        }
        else {
            scalars.push({ key, type: 'text', value: String(val) });
        }
    }
    boolFields.value = bools;
    scalarFields.value = scalars;
    nestedFields.value = nesteds;
}
/** 把对象转成接近 YAML 风格的纯文本（缩进 2 空格）。 */
function toYamlLike(obj, indent = 0) {
    if (obj === null || obj === undefined)
        return '';
    if (typeof obj !== 'object')
        return String(obj);
    const pad = '  '.repeat(indent);
    const lines = [];
    for (const [k, v] of Object.entries(obj)) {
        if (typeof v === 'object' && v !== null) {
            lines.push(`${pad}${k}:`);
            lines.push(toYamlLike(v, indent + 1));
        }
        else {
            lines.push(`${pad}${k}: ${v}`);
        }
    }
    return lines.join('\n');
}
/** 把 textarea 的 YAML 风格文本解析回对象。 */
function fromYamlLike(text) {
    // 简单解析 — 仅支持嵌套 dict，值均为字符串
    const result = {};
    const stack = [{ indent: -1, obj: result }];
    for (const line of text.split('\n')) {
        if (!line.trim() || line.trim().startsWith('#'))
            continue;
        const indent = line.search(/\S/);
        const content = line.trim();
        const colonIdx = content.indexOf(':');
        // 回退栈
        while (stack.length > 1 && stack[stack.length - 1].indent >= indent) {
            stack.pop();
        }
        if (colonIdx > 0) {
            const key = content.substring(0, colonIdx).trim();
            const val = content.substring(colonIdx + 1).trim();
            if (val) {
                stack[stack.length - 1].obj[key] = val;
            }
            else {
                // 嵌套对象开始
                const child = {};
                stack[stack.length - 1].obj[key] = child;
                stack.push({ indent, obj: child });
            }
        }
    }
    return result;
}
// ── 保存 ──────────────────────────────────────────────────
async function saveUserConfig() {
    saving.value = true;
    saveMsg.value = '';
    // 构建 _env
    const env = {};
    if (envFields.apiKey)
        env['ANTHROPIC_API_KEY'] = envFields.apiKey;
    if (envFields.baseUrl)
        env['ANTHROPIC_BASE_URL'] = envFields.baseUrl;
    if (envFields.model)
        env['ANTHROPIC_MODEL'] = envFields.model;
    // 构建 _system
    const system = {};
    for (const f of boolFields.value) {
        system[f.key] = f.value;
    }
    for (const f of scalarFields.value) {
        if (f.type === 'number') {
            system[f.key] = Number(f.value);
        }
        else {
            system[f.key] = f.value;
        }
    }
    for (const f of nestedFields.value) {
        try {
            system[f.key] = fromYamlLike(f.yamlText);
        }
        catch {
            saveOk.value = false;
            saveMsg.value = `${f.key} 格式错误，请检查`;
            saving.value = false;
            return;
        }
    }
    try {
        await apiFetch('/api/user/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ _env: env, _system: system }),
        });
        saveOk.value = true;
        saveMsg.value = '保存成功';
    }
    catch (e) {
        saveOk.value = false;
        saveMsg.value = normalizeApiError(e);
    }
    saving.value = false;
}
// ── 导出/导入 ─────────────────────────────────────────────
function exportSettings() {
    const json = configStore.exportSettings();
    const blob = new Blob([json], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `ard-settings-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
}
async function importSettings() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target?.files?.[0];
        if (!file)
            return;
        const text = await file.text();
        if (configStore.importSettings(text)) {
            saveMsg.value = '导入成功，请点保存';
            saveOk.value = true;
        }
        else {
            saveMsg.value = '导入失败：文件格式不正确';
            saveOk.value = false;
        }
    };
    input.click();
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-3xl mx-auto p-6 space-y-8" },
});
if (__VLS_ctx.showUserConfig) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
        ...{ class: "text-lg font-semibold mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-xs text-gray-400 mb-4" },
    });
    (__VLS_ctx.auth.username);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-white border border-gray-200 rounded-lg p-5 mb-4 space-y-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-sm font-medium text-gray-500" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "block text-xs text-gray-500 mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "password",
        ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" },
    });
    (__VLS_ctx.envFields.apiKey);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "block text-xs text-gray-500 mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        value: (__VLS_ctx.envFields.baseUrl),
        type: "text",
        ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "block text-xs text-gray-500 mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        value: (__VLS_ctx.envFields.model),
        type: "text",
        ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-white border border-gray-200 rounded-lg p-5 mb-4 space-y-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-sm font-medium text-gray-500" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-4 gap-x-4 gap-y-2" },
    });
    for (const [f] of __VLS_getVForSourceType((__VLS_ctx.boolFields))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
            key: (f.key),
            ...{ class: "flex items-center gap-2 text-sm text-gray-600 cursor-pointer" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            type: "checkbox",
            ...{ class: "rounded border-gray-300 text-primary-600 focus:ring-primary-500" },
        });
        (f.value);
        (f.key);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.hr)({
        ...{ class: "border-gray-100" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-2 gap-4" },
    });
    for (const [f] of __VLS_getVForSourceType((__VLS_ctx.scalarFields))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (f.key),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
            ...{ class: "block text-xs text-gray-500 mb-1" },
        });
        (f.key);
        if (f.type === 'select') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
                value: (f.value),
                ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 bg-white" },
            });
            for (const [opt] of __VLS_getVForSourceType((f.options))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
                    key: (opt),
                    value: (opt),
                });
                (opt);
            }
        }
        else if (f.type === 'number') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                type: "number",
                ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" },
            });
            (f.value);
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
                value: (f.value),
                type: "text",
                ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500" },
            });
        }
    }
    if (__VLS_ctx.nestedFields.length) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.hr)({
            ...{ class: "border-gray-100" },
        });
        for (const [f] of __VLS_getVForSourceType((__VLS_ctx.nestedFields))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (f.key),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
                ...{ class: "block text-xs text-gray-500 mb-1" },
            });
            (f.key);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
                value: (f.yamlText),
                rows: "6",
                ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary-500" },
            });
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.saveUserConfig) },
        disabled: (__VLS_ctx.saving),
        ...{ class: "px-4 py-2 bg-primary-500 text-white text-sm font-medium rounded-lg hover:bg-primary-600 disabled:bg-primary-300 transition-colors" },
    });
    (__VLS_ctx.saving ? '保存中...' : '保存');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.exportSettings) },
        ...{ class: "px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.importSettings) },
        ...{ class: "px-4 py-2 bg-gray-100 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-200 transition-colors" },
    });
    if (__VLS_ctx.saveMsg) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: (['text-sm mt-2', __VLS_ctx.saveOk ? 'text-green-500' : 'text-red-500']) },
        });
        (__VLS_ctx.saveMsg);
    }
    if (__VLS_ctx.globalSystemConfig) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
            ...{ class: "text-lg font-semibold mb-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-sm text-gray-500 mb-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono" },
        });
        (__VLS_ctx.globalSystemConfig || '（空）');
    }
    if (__VLS_ctx.globalEnvContent) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
            ...{ class: "text-lg font-semibold mb-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-sm text-gray-500 mb-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono" },
        });
        (__VLS_ctx.globalEnvContent || '（空）');
    }
    if (__VLS_ctx.businessRules !== null) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
            ...{ class: "text-lg font-semibold mb-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-sm text-gray-500 mb-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono" },
        });
        (__VLS_ctx.businessRules || '（空）');
    }
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-500 mb-3" },
    });
    if (__VLS_ctx.envContent !== null) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono" },
        });
        (__VLS_ctx.envContent || '（空）');
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-400 text-sm" },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-500 mb-3" },
    });
    if (__VLS_ctx.systemConfig !== null) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono" },
        });
        (__VLS_ctx.systemConfig || '（空）');
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-400 text-sm" },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-500 mb-3" },
    });
    if (__VLS_ctx.businessRules !== null) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "bg-gray-900 text-gray-300 text-sm p-5 rounded-lg overflow-x-auto whitespace-pre-wrap font-mono" },
        });
        (__VLS_ctx.businessRules || '（空）');
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-400 text-sm" },
        });
    }
}
/** @type {__VLS_StyleScopedClasses['max-w-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-primary-600']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:ring-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-primary-600']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:bg-primary-300']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            auth: auth,
            showUserConfig: showUserConfig,
            envContent: envContent,
            systemConfig: systemConfig,
            businessRules: businessRules,
            globalEnvContent: globalEnvContent,
            globalSystemConfig: globalSystemConfig,
            envFields: envFields,
            boolFields: boolFields,
            scalarFields: scalarFields,
            nestedFields: nestedFields,
            saving: saving,
            saveMsg: saveMsg,
            saveOk: saveOk,
            saveUserConfig: saveUserConfig,
            exportSettings: exportSettings,
            importSettings: importSettings,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
