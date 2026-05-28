import { computed } from 'vue';
import { useConfigStore } from '@/stores/config';
import { useSessionStore } from '@/stores/session';
import FileInput from './FileInput.vue';
import AdvancedOptions from './AdvancedOptions.vue';
import TemplateUpload from './TemplateUpload.vue';
import TemplateDownload from './TemplateDownload.vue';
import { apiFetch } from '@/lib/api';
import { ref, onMounted } from 'vue';
const __VLS_emit = defineEmits();
const config = useConfigStore();
const session = useSessionStore();
const modes = ref({});
onMounted(async () => {
    try {
        modes.value = await apiFetch('/api/modes');
    }
    catch {
        modes.value = {};
    }
});
const statusText = computed(() => {
    const map = { idle: '就绪', running: '运行中...', done: '完成', error: '出错' };
    return map[session.runState];
});
const statusClass = computed(() => {
    const map = {
        idle: 'text-[var(--color-ink-soft)]',
        running: 'text-[var(--color-accent-strong)]',
        done: 'text-[var(--color-success)]',
        error: 'text-[var(--color-danger)]',
    };
    return map[session.runState];
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-col gap-5" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "field-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
    value: (__VLS_ctx.config.pipelineMode),
    ...{ class: "field-control" },
});
for (const [info, value] of __VLS_getVForSourceType((__VLS_ctx.modes))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        key: (value),
        value: (value),
    });
    (info.label);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "mt-2 text-xs leading-5 text-[var(--color-ink-soft)]" },
});
(__VLS_ctx.modes[__VLS_ctx.config.pipelineMode]?.desc);
/** @type {[typeof FileInput, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(FileInput, new FileInput({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3 rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface-muted)] p-3" },
});
/** @type {[typeof AdvancedOptions, ]} */ ;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent(AdvancedOptions, new AdvancedOptions({}));
const __VLS_4 = __VLS_3({}, ...__VLS_functionalComponentArgsRest(__VLS_3));
/** @type {[typeof TemplateUpload, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(TemplateUpload, new TemplateUpload({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
/** @type {[typeof TemplateDownload, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(TemplateDownload, new TemplateDownload({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.$emit('start');
        } },
    disabled: (!__VLS_ctx.config.isValid || __VLS_ctx.session.isRunning),
    ...{ class: "btn-primary w-full text-base" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-lg border border-[var(--color-rule)] bg-[var(--color-surface)] px-3 py-2 text-sm" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between gap-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-[var(--color-ink-muted)]" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: (['font-semibold', __VLS_ctx.statusClass]) },
});
(__VLS_ctx.statusText);
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-5']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-control']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-surface-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule)]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-surface)]']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            FileInput: FileInput,
            AdvancedOptions: AdvancedOptions,
            TemplateUpload: TemplateUpload,
            TemplateDownload: TemplateDownload,
            config: config,
            session: session,
            modes: modes,
            statusText: statusText,
            statusClass: statusClass,
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
