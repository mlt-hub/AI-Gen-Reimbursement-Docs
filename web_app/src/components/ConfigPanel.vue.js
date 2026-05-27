import { computed } from 'vue';
import { useConfigStore } from '@/stores/config';
import { useSessionStore } from '@/stores/session';
import FileInput from './FileInput.vue';
import AdvancedOptions from './AdvancedOptions.vue';
import TemplateUpload from './TemplateUpload.vue';
import TemplateDownload from './TemplateDownload.vue';
import { ref, onMounted } from 'vue';
const __VLS_emit = defineEmits();
const config = useConfigStore();
const session = useSessionStore();
const modes = ref({});
onMounted(async () => {
    try {
        const resp = await fetch('/api/modes');
        modes.value = await resp.json();
    }
    catch {
        modes.value = {};
    }
});
const statusText = computed(() => {
    const map = { idle: '就绪', running: '运行中...', done: '完成', error: '出错' };
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
    ...{ class: "block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
    value: (__VLS_ctx.config.pipelineMode),
    ...{ class: "w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent bg-white" },
});
for (const [info, value] of __VLS_getVForSourceType((__VLS_ctx.modes))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        key: (value),
        value: (value),
    });
    (info.label);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-xs text-gray-400 mt-1" },
});
(__VLS_ctx.modes[__VLS_ctx.config.pipelineMode]?.desc);
/** @type {[typeof FileInput, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(FileInput, new FileInput({}));
const __VLS_1 = __VLS_0({}, ...__VLS_functionalComponentArgsRest(__VLS_0));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3" },
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
    ...{ class: "w-full py-3 bg-primary-500 text-white font-semibold rounded-lg hover:bg-primary-600 disabled:bg-primary-300 disabled:cursor-not-allowed transition-colors text-base" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: (['text-center text-sm font-medium',
            __VLS_ctx.session.runState === 'idle' ? 'text-gray-400' :
                __VLS_ctx.session.runState === 'running' ? 'text-primary-500' :
                    __VLS_ctx.session.runState === 'done' ? 'text-green-500' : 'text-red-500']) },
});
(__VLS_ctx.statusText);
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-5']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['uppercase']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-wide']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
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
/** @type {__VLS_StyleScopedClasses['focus:border-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-primary-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-primary-600']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:bg-primary-300']} */ ;
/** @type {__VLS_StyleScopedClasses['disabled:cursor-not-allowed']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
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
