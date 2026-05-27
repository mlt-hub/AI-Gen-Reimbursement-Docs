import { computed, ref, watch } from 'vue';
import { useSessionStore } from '@/stores/session';
import { useConfigStore } from '@/stores/config';
import { useLogStore } from '@/stores/log';
import { useStepsStore } from '@/stores/steps';
import { useToastStore } from '@/stores/toast';
import ConfigPanel from '@/components/ConfigPanel.vue';
import StepsBar from '@/components/StepsBar.vue';
import LogViewer from '@/components/LogViewer.vue';
import ActionBar from '@/components/ActionBar.vue';
const session = useSessionStore();
const config = useConfigStore();
const log = useLogStore();
const toast = useToastStore();
const runTitle = computed(() => session.outputDir || '等待任务启动');
const runStateText = computed(() => {
    const map = { idle: '就绪', running: '运行中', done: '已完成', error: '异常' };
    return map[session.runState];
});
const runStateClass = computed(() => {
    const map = {
        idle: 'border-[var(--color-rule)] bg-[var(--color-surface-muted)] text-[var(--color-ink-muted)]',
        running: 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]',
        done: 'border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]',
        error: 'border-[var(--color-danger)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]',
    };
    return map[session.runState];
});
const runDotClass = computed(() => {
    const map = {
        idle: 'bg-[var(--color-ink-soft)]',
        running: 'bg-[var(--color-accent)]',
        done: 'bg-[var(--color-success)]',
        error: 'bg-[var(--color-danger)]',
    };
    return map[session.runState];
});
// ── 送审工作量输入 ──
const fpaInputValue = ref(0);
watch(() => session.inputPrompt, (p) => {
    if (p) {
        fpaInputValue.value = p.default;
    }
});
// ── 送审确认（gen-list）──
const listFpaValue = ref(0);
const listCfpValue = ref(0);
watch(() => session.listPrompt, (p) => {
    if (p) {
        listFpaValue.value = p.fpaDefault;
        listCfpValue.value = p.cfpDefault;
    }
});
async function submitFpaInput() {
    if (!session.sessionId)
        return;
    const val = parseFloat(String(fpaInputValue.value)) || 0;
    try {
        await fetch('/api/continue/' + session.sessionId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ field: 'fpa_reduced', fpa_reduced: val }),
        });
    }
    catch {
        toast.show('error', '网络错误，请检查服务是否运行');
        return;
    }
    session.inputPrompt = null;
}
async function submitListInput() {
    if (!session.sessionId)
        return;
    try {
        await fetch('/api/continue/' + session.sessionId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fpa_reduced: parseFloat(String(listFpaValue.value)) || 0,
                cfp_total: parseFloat(String(listCfpValue.value)) || 0,
            }),
        });
    }
    catch {
        toast.show('error', '网络错误，请检查服务是否运行');
        return;
    }
    session.listPrompt = null;
}
async function cancelTask() {
    if (!session.sessionId)
        return;
    try {
        await fetch('/api/cancel/' + session.sessionId, { method: 'POST' });
    }
    catch { /* ignore */ }
}
// ── 任务启动 ──
async function startTask() {
    const mode = config.pipelineMode;
    const body = new FormData();
    body.append('mode', mode);
    if (config.apiKey)
        body.append('api_key', config.apiKey);
    if (config.model)
        body.append('model', config.model);
    if (config.baseUrl)
        body.append('base_url', config.baseUrl);
    if (config.maxTokens)
        body.append('max_tokens', config.maxTokens);
    if (config.projectName)
        body.append('project_name', config.projectName);
    if (config.clean)
        body.append('clean', '1');
    let url;
    if (config.workMode === 'local') {
        if (!config.xlsxPath.trim()) {
            toast.show('error', '请输入功能清单 .xlsx 路径');
            return;
        }
        url = '/api/run-local';
        body.append('xlsx_path', config.xlsxPath);
        body.append('output_dir', config.outputDir);
    }
    else {
        if (!config.selectedFile) {
            toast.show('error', '请选择要上传的 .xlsx 文件');
            return;
        }
        url = '/api/run-upload';
        body.append('file', config.selectedFile);
    }
    log.clear();
    session.reset();
    useStepsStore().reset();
    try {
        const resp = await fetch(url, { method: 'POST', body });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || `请求失败 (${resp.status})`);
        }
        const data = await resp.json();
        session.start(data.session_id, data.output_dir || '');
        log.connect();
    }
    catch (e) {
        const msg = e.message === 'Failed to fetch' ? '无法连接服务，请检查服务是否运行' : e.message;
        log.append({ level: 'ERROR', msg: msg, time: '' });
        toast.show('error', msg);
        session.setError();
    }
}
// ── AI 交互弹窗 ──
const aiModalOpen = ref(false);
const aiTab = ref('list');
const aiLoading = ref(false);
const aiInteractions = ref([]);
const aiCombinedLog = ref('');
async function openAIModal() {
    if (!session.sessionId)
        return;
    aiModalOpen.value = true;
    await loadAIList();
}
function closeAIModal() { aiModalOpen.value = false; }
async function loadAIList() {
    if (!session.sessionId)
        return;
    aiLoading.value = true;
    try {
        const resp = await fetch('/api/ai-interactions/' + session.sessionId);
        if (!resp.ok)
            throw new Error((await resp.json()).detail);
        const data = await resp.json();
        aiInteractions.value = (data.interactions || []).map((i) => ({ ...i, expanded: false }));
    }
    catch (e) {
        aiInteractions.value = [];
    }
    aiLoading.value = false;
}
async function loadAICombined() {
    if (!session.sessionId)
        return;
    aiLoading.value = true;
    try {
        const resp = await fetch('/api/ai-log/' + session.sessionId);
        if (!resp.ok) {
            const err = await resp.json();
            aiCombinedLog.value = resp.status === 404 ? err.detail : '加载失败: ' + err.detail;
            aiLoading.value = false;
            return;
        }
        const data = await resp.json();
        aiCombinedLog.value = data.content || '';
    }
    catch (e) {
        aiCombinedLog.value = '加载失败: ' + e.message;
    }
    aiLoading.value = false;
}
// React to tab changes
watch(aiTab, (t) => {
    if (t === 'list')
        loadAIList();
    else
        loadAICombined();
});
function resetTask() {
    session.reset();
    log.clear();
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex h-full flex-col gap-4 overflow-hidden p-4 lg:flex-row lg:p-5" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
    ...{ class: "surface min-h-0 shrink-0 overflow-y-auto rounded-xl p-4 lg:w-[390px]" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-5 border-b border-[var(--color-rule)] pb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-xs font-semibold uppercase text-[var(--color-ink-soft)]" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "mt-1 text-xl font-bold text-[var(--color-ink)]" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "mt-1 text-sm text-[var(--color-ink-muted)]" },
});
/** @type {[typeof ConfigPanel, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(ConfigPanel, new ConfigPanel({
    ...{ 'onStart': {} },
}));
const __VLS_1 = __VLS_0({
    ...{ 'onStart': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_0));
let __VLS_3;
let __VLS_4;
let __VLS_5;
const __VLS_6 = {
    onStart: (__VLS_ctx.startTask)
};
var __VLS_2;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "surface flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "border-b border-[var(--color-rule)] px-5 py-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-col gap-3 md:flex-row md:items-center md:justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "min-w-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-xs font-semibold uppercase text-[var(--color-ink-soft)]" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "mt-1 truncate text-lg font-bold text-[var(--color-ink)]" },
});
(__VLS_ctx.runTitle);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: (['inline-flex w-fit items-center gap-2 rounded-md border px-3 py-1.5 text-sm font-semibold', __VLS_ctx.runStateClass]) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span)({
    ...{ class: "h-2 w-2 rounded-full" },
    ...{ class: (__VLS_ctx.runDotClass) },
});
(__VLS_ctx.runStateText);
if (__VLS_ctx.session.isRunning || __VLS_ctx.session.isDone) {
    /** @type {[typeof StepsBar, ]} */ ;
    // @ts-ignore
    const __VLS_7 = __VLS_asFunctionalComponent(StepsBar, new StepsBar({}));
    const __VLS_8 = __VLS_7({}, ...__VLS_functionalComponentArgsRest(__VLS_7));
}
/** @type {[typeof LogViewer, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(LogViewer, new LogViewer({}));
const __VLS_11 = __VLS_10({}, ...__VLS_functionalComponentArgsRest(__VLS_10));
/** @type {[typeof ActionBar, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(ActionBar, new ActionBar({
    ...{ 'onAi': {} },
    ...{ 'onReset': {} },
}));
const __VLS_14 = __VLS_13({
    ...{ 'onAi': {} },
    ...{ 'onReset': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onAi: (__VLS_ctx.openAIModal)
};
const __VLS_20 = {
    onReset: (__VLS_ctx.resetTask)
};
var __VLS_15;
const __VLS_21 = {}.Teleport;
/** @type {[typeof __VLS_components.Teleport, typeof __VLS_components.Teleport, ]} */ ;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({
    to: "body",
}));
const __VLS_23 = __VLS_22({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
__VLS_24.slots.default;
if (__VLS_ctx.session.inputPrompt) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "surface w-full max-w-[420px] rounded-xl p-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-semibold mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-500 mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "field-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onKeyup: (__VLS_ctx.submitFpaInput) },
        type: "number",
        step: "0.1",
        min: "0",
        ...{ class: "field-control" },
    });
    (__VLS_ctx.fpaInputValue);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-end gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.cancelTask) },
        ...{ class: "btn-quiet" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.submitFpaInput) },
        ...{ class: "btn-primary" },
    });
}
var __VLS_24;
const __VLS_25 = {}.Teleport;
/** @type {[typeof __VLS_components.Teleport, typeof __VLS_components.Teleport, ]} */ ;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({
    to: "body",
}));
const __VLS_27 = __VLS_26({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_28.slots.default;
if (__VLS_ctx.session.listPrompt) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "surface w-full max-w-[420px] rounded-xl p-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-semibold mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-500 mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "field-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onKeyup: (__VLS_ctx.submitListInput) },
        type: "number",
        step: "0.1",
        min: "0",
        ...{ class: "field-control" },
    });
    (__VLS_ctx.listFpaValue);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "field-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onKeyup: (__VLS_ctx.submitListInput) },
        type: "number",
        step: "0.1",
        min: "0",
        ...{ class: "field-control" },
    });
    (__VLS_ctx.listCfpValue);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-end gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.cancelTask) },
        ...{ class: "btn-quiet" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.submitListInput) },
        ...{ class: "btn-primary" },
    });
}
var __VLS_28;
const __VLS_29 = {}.Teleport;
/** @type {[typeof __VLS_components.Teleport, typeof __VLS_components.Teleport, ]} */ ;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({
    to: "body",
}));
const __VLS_31 = __VLS_30({
    to: "body",
}, ...__VLS_functionalComponentArgsRest(__VLS_30));
__VLS_32.slots.default;
if (__VLS_ctx.aiModalOpen) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.closeAIModal) },
        ...{ class: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "surface flex h-[85vh] w-[92vw] max-w-5xl flex-col overflow-hidden rounded-xl" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "px-5 py-3 border-b border-[var(--color-rule)] flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-semibold" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeAIModal) },
        ...{ class: "btn-quiet min-h-0 px-2 py-1 text-xl leading-none" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex border-b border-[var(--color-rule)] px-5" },
    });
    for (const [tab] of __VLS_getVForSourceType((['list', 'combined']))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.aiModalOpen))
                        return;
                    __VLS_ctx.aiTab = tab;
                } },
            key: (tab),
            ...{ class: (['py-2 px-4 text-sm border-b-2 transition-colors',
                    __VLS_ctx.aiTab === tab ? 'border-[var(--color-accent)] text-[var(--color-accent-strong)] font-medium' : 'border-transparent text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]']) },
        });
        (tab === 'list' ? '交互列表' : '合并日志');
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1 overflow-y-auto bg-[var(--color-page)] p-5" },
    });
    if (__VLS_ctx.aiLoading) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex h-full items-center justify-center text-[var(--color-ink-soft)]" },
        });
    }
    else if (__VLS_ctx.aiTab === 'list' && __VLS_ctx.aiInteractions.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex h-full items-center justify-center text-[var(--color-ink-soft)]" },
        });
    }
    else if (__VLS_ctx.aiTab === 'list') {
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.aiInteractions))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (item.name),
                ...{ class: "mb-3 overflow-hidden rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-raised)]" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.aiModalOpen))
                            return;
                        if (!!(__VLS_ctx.aiLoading))
                            return;
                        if (!!(__VLS_ctx.aiTab === 'list' && __VLS_ctx.aiInteractions.length === 0))
                            return;
                        if (!(__VLS_ctx.aiTab === 'list'))
                            return;
                        item.expanded = !item.expanded;
                    } },
                ...{ class: "flex cursor-pointer select-none items-center justify-between bg-[var(--color-surface)] px-4 py-2 hover:bg-[var(--color-surface-muted)]" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "flex items-center gap-2 text-sm" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: (['rounded px-1.5 py-0.5 text-xs font-bold', item.type === 'prompt' ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent-strong)]' : 'bg-[var(--color-success-soft)] text-[var(--color-success)]']) },
            });
            (item.type === 'prompt' ? 'P' : 'R');
            (item.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-xs text-[var(--color-ink-soft)]" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
                ...{ class: "m-0 max-h-96 overflow-y-auto overflow-x-auto bg-[var(--color-console)] p-4 text-xs leading-relaxed text-slate-300 whitespace-pre-wrap" },
            });
            __VLS_asFunctionalDirective(__VLS_directives.vShow)(null, { ...__VLS_directiveBindingRestFields, value: (item.expanded) }, null, null);
            (item.content);
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "overflow-x-auto rounded-lg bg-[var(--color-console)] p-4 text-xs leading-relaxed text-slate-300 whitespace-pre-wrap" },
        });
        (__VLS_ctx.aiCombinedLog);
    }
}
var __VLS_32;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:flex-row']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['surface']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:w-[390px]']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-5']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['pb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink)]']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['surface']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['md:flex-row']} */ ;
/** @type {__VLS_StyleScopedClasses['md:items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['md:justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink)]']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['w-fit']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-md']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['h-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-black/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['surface']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-[420px]']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-control']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-quiet']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-black/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['surface']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-[420px]']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-control']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-control']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-quiet']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-black/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['surface']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-[85vh]']} */ ;
/** @type {__VLS_StyleScopedClasses['w-[92vw]']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-5xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['px-5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-quiet']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-0']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-none']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b-2']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-page)]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-surface-raised)]']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['select-none']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-surface)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-[var(--color-surface-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['px-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['m-0']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-96']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-console)]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-x-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-console)]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ConfigPanel: ConfigPanel,
            StepsBar: StepsBar,
            LogViewer: LogViewer,
            ActionBar: ActionBar,
            session: session,
            runTitle: runTitle,
            runStateText: runStateText,
            runStateClass: runStateClass,
            runDotClass: runDotClass,
            fpaInputValue: fpaInputValue,
            listFpaValue: listFpaValue,
            listCfpValue: listCfpValue,
            submitFpaInput: submitFpaInput,
            submitListInput: submitListInput,
            cancelTask: cancelTask,
            startTask: startTask,
            aiModalOpen: aiModalOpen,
            aiTab: aiTab,
            aiLoading: aiLoading,
            aiInteractions: aiInteractions,
            aiCombinedLog: aiCombinedLog,
            openAIModal: openAIModal,
            closeAIModal: closeAIModal,
            resetTask: resetTask,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
