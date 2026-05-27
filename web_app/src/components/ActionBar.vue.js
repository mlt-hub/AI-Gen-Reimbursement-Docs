import { ref, watch } from 'vue';
import { FolderOpenIcon, ArrowDownTrayIcon, ChatBubbleLeftEllipsisIcon, XCircleIcon } from '@heroicons/vue/24/outline';
import { useSessionStore } from '@/stores/session';
import { useConfigStore } from '@/stores/config';
import { useLogStore } from '@/stores/log';
import { useToastStore } from '@/stores/toast';
const emit = defineEmits();
const session = useSessionStore();
const config = useConfigStore();
const log = useLogStore();
const toast = useToastStore();
function openFolder() {
    if (!session.sessionId)
        return;
    fetch('/api/open-folder?session=' + session.sessionId).catch(() => { });
}
function downloadZip() {
    if (!session.sessionId)
        return;
    const a = document.createElement('a');
    a.href = '/api/download/' + session.sessionId;
    a.click();
}
function showAI() { emit('ai'); }
function cancelTask() {
    if (!session.sessionId)
        return;
    fetch('/api/cancel/' + session.sessionId, { method: 'POST' }).catch(() => { });
    toast.show('info', '正在停止任务，如当前有 AI 调用正在执行，需等待其完成后停止', 6000);
}
function resetTask() {
    session.reset();
    log.clear();
}
// ── 完成提示音 ──
const lastNotifiedSession = ref('');
const _audio = new Audio('/static/audio/ticktick_pop.wav');
watch(() => session.isDone, (done) => {
    if (!done || !session.sessionId || session.sessionId === lastNotifiedSession.value)
        return;
    lastNotifiedSession.value = session.sessionId;
    if (config.workMode === 'local') {
        fetch('/api/play-notify', { method: 'POST' }).catch(() => { });
    }
    else {
        _audio.play().catch(() => { });
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "border-t border-[var(--color-rule)] bg-[var(--color-surface-raised)]" },
});
if (__VLS_ctx.session.isDone && __VLS_ctx.session.doneFiles.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "border-b border-[var(--color-rule)] px-5 py-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-2 text-xs font-semibold text-[var(--color-ink-muted)]" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex flex-wrap gap-2" },
    });
    for (const [f] of __VLS_getVForSourceType((__VLS_ctx.session.doneFiles))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            key: (f.path),
            ...{ class: (['inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold',
                    f.is_temp ? 'border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]' : 'border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]']) },
            title: (f.is_temp ? '文件被占用，已保存到临时文件 — 关闭占用程序后重命名替换原文件即可' : f.path),
        });
        if (f.is_temp) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        (f.label);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "opacity-60" },
        });
        (f.size_kb);
    }
    if (__VLS_ctx.session.doneFiles.some(f => f.is_temp)) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-2 text-xs text-[var(--color-warning)]" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({
            ...{ class: "rounded bg-[var(--color-warning-soft)] px-1" },
        });
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-col gap-3 px-5 py-3 md:flex-row md:items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "min-w-0 flex-1 truncate text-sm text-[var(--color-ink-muted)]" },
});
if (__VLS_ctx.session.outputDir) {
    (__VLS_ctx.session.outputDir);
}
if (__VLS_ctx.session.isRunning) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.cancelTask) },
        ...{ class: "btn-danger" },
    });
    const __VLS_0 = {}.XCircleIcon;
    /** @type {[typeof __VLS_components.XCircleIcon, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        ...{ class: "w-4 h-4" },
    }));
    const __VLS_2 = __VLS_1({
        ...{ class: "w-4 h-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
if (__VLS_ctx.config.workMode === 'local') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.openFolder) },
        disabled: (!__VLS_ctx.session.sessionId),
        ...{ class: "btn-secondary" },
    });
    const __VLS_4 = {}.FolderOpenIcon;
    /** @type {[typeof __VLS_components.FolderOpenIcon, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        ...{ class: "w-4 h-4" },
    }));
    const __VLS_6 = __VLS_5({
        ...{ class: "w-4 h-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.downloadZip) },
        disabled: (!__VLS_ctx.session.sessionId),
        ...{ class: "btn-secondary" },
    });
    const __VLS_8 = {}.ArrowDownTrayIcon;
    /** @type {[typeof __VLS_components.ArrowDownTrayIcon, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ class: "w-4 h-4" },
    }));
    const __VLS_10 = __VLS_9({
        ...{ class: "w-4 h-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.showAI) },
    disabled: (!__VLS_ctx.session.isDone),
    ...{ class: "btn-secondary" },
});
const __VLS_12 = {}.ChatBubbleLeftEllipsisIcon;
/** @type {[typeof __VLS_components.ChatBubbleLeftEllipsisIcon, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "w-4 h-4" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "w-4 h-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
if (__VLS_ctx.session.isDone) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.resetTask) },
        ...{ class: "btn-quiet" },
    });
}
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-surface-raised)]']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-md']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2.5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['opacity-60']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-warning)]']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-warning-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['px-5']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['md:flex-row']} */ ;
/** @type {__VLS_StyleScopedClasses['md:items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-danger']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-quiet']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            FolderOpenIcon: FolderOpenIcon,
            ArrowDownTrayIcon: ArrowDownTrayIcon,
            ChatBubbleLeftEllipsisIcon: ChatBubbleLeftEllipsisIcon,
            XCircleIcon: XCircleIcon,
            session: session,
            config: config,
            openFolder: openFolder,
            downloadZip: downloadZip,
            showAI: showAI,
            cancelTask: cancelTask,
            resetTask: resetTask,
        };
    },
    __typeEmits: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
});
; /* PartiallyEnd: #4569/main.vue */
