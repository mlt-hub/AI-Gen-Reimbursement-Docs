import { ref, computed, watchEffect, onMounted } from 'vue';
import { useLogStore } from '@/stores/log';
import { useToastStore } from '@/stores/toast';
import { apiFetch, normalizeApiError } from '@/lib/api';
const logStore = useLogStore();
const toast = useToastStore();
const logEl = ref(null);
const filterLevel = ref('INFO');
const levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];
const levelOrder = { DEBUG: 0, INFO: 1, WARNING: 2, ERROR: 3, DONE: -1 };
const filteredEntries = computed(() => {
    const min = levelOrder[filterLevel.value] ?? 1;
    return logStore.entries.filter(e => {
        const lv = levelOrder[e.level];
        return lv === undefined || lv < 0 || lv >= min;
    });
});
watchEffect(() => {
    logStore.logPanelEl = logEl.value;
});
onMounted(async () => {
    try {
        const data = await apiFetch('/api/log-level');
        if (data.level && levels.includes(data.level))
            filterLevel.value = data.level;
    }
    catch { }
});
async function saveLevel() {
    try {
        await apiFetch('/api/log-level', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level: filterLevel.value }),
        });
    }
    catch (e) {
        toast.show('error', normalizeApiError(e));
    }
}
function levelColor(level) {
    const map = {
        INFO: 'text-blue-400',
        DEBUG: 'text-gray-400',
        WARNING: 'text-yellow-400',
        ERROR: 'text-red-400',
        DONE: 'text-green-400',
    };
    return map[level] || 'text-gray-300';
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex-1 flex flex-col min-h-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between gap-3 border-b border-[var(--color-console-line)] bg-[var(--color-console)] px-5 py-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-xs font-semibold text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-xs text-slate-500" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
    ...{ onChange: (__VLS_ctx.saveLevel) },
    value: (__VLS_ctx.filterLevel),
    ...{ class: "rounded-md border border-slate-600 bg-slate-800 px-2 py-1 text-xs text-slate-200 focus:border-[var(--color-focus)] focus:outline-none" },
});
for (const [lv] of __VLS_getVForSourceType((__VLS_ctx.levels))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        key: (lv),
        value: (lv),
    });
    (lv);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "logEl",
    ...{ class: "flex-1 overflow-y-auto bg-[var(--color-console)] p-5 font-mono text-sm leading-6" },
});
/** @type {typeof __VLS_ctx.logEl} */ ;
if (__VLS_ctx.logStore.entries.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex h-full items-center justify-center text-sm text-slate-500" },
    });
}
for (const [entry, i] of __VLS_getVForSourceType((__VLS_ctx.filteredEntries))) {
    (i);
    if (entry.level === 'DONE') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "my-2 rounded-md border border-emerald-400/30 bg-emerald-400/10 px-4 py-2 text-center font-semibold text-emerald-300" },
        });
        (entry.msg);
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex gap-3 py-0.5" },
            ...{ class: ({ 'mt-3': entry.isStep }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "w-20 shrink-0 text-slate-500" },
        });
        (entry.time);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: (['shrink-0 w-14 font-semibold', __VLS_ctx.levelColor(entry.level)]) },
        });
        (entry.level);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: (['break-all whitespace-pre-wrap text-slate-300', { 'font-semibold text-amber-300': entry.isStep }]) },
        });
        (entry.msg);
    }
}
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-console-line)]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-console)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-md']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-[var(--color-focus)]']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:outline-none']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-console)]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['my-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-md']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-400/10']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-20']} */ ;
/** @type {__VLS_StyleScopedClasses['shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['w-14']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['break-all']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-300']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            logStore: logStore,
            logEl: logEl,
            filterLevel: filterLevel,
            levels: levels,
            filteredEntries: filteredEntries,
            saveLevel: saveLevel,
            levelColor: levelColor,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
