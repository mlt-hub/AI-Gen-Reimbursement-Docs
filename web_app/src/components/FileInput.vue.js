import { ref } from 'vue';
import { useConfigStore } from '@/stores/config';
const config = useConfigStore();
const selectedName = ref('');
function onFileChange(e) {
    const input = e.target;
    if (input.files?.length) {
        config.selectedFile = input.files[0];
        selectedName.value = input.files[0].name;
    }
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3" },
});
if (__VLS_ctx.config.workMode === 'local') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        for: "xlsx-path",
        ...{ class: "field-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        id: "xlsx-path",
        type: "text",
        value: (__VLS_ctx.config.xlsxPath),
        placeholder: "\u0043\u003a\u005c\u002e\u002e\u002e\u005c\u529f\u80fd\u6e05\u5355\u002e\u0078\u006c\u0073\u0078\u0020\u0020\u6216\u0020\u0020\u0043\u003a\u005c\u002e\u002e\u002e\u005c\u9879\u76ee\u76ee\u5f55\u005c",
        ...{ class: "field-control" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        for: "output-dir",
        ...{ class: "field-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        id: "output-dir",
        type: "text",
        value: (__VLS_ctx.config.outputDir),
        placeholder: "留空使用默认：xlsx 同级或目录/项目名",
        ...{ class: "field-control" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "field-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "relative rounded-lg border border-dashed border-[var(--color-rule-strong)] bg-[var(--color-surface)] p-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onChange: (__VLS_ctx.onFileChange) },
        type: "file",
        accept: ".xlsx",
        ...{ class: "w-full text-sm text-[var(--color-ink-muted)] file:mr-4 file:rounded-md file:border-0 file:bg-[var(--color-accent-soft)] file:px-4 file:py-2 file:text-sm file:font-semibold file:text-[var(--color-accent-strong)] hover:file:bg-[var(--color-surface-muted)]" },
    });
    if (__VLS_ctx.selectedName) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "mt-2 text-xs text-[var(--color-accent-strong)]" },
        });
        (__VLS_ctx.selectedName);
    }
}
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-control']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['field-control']} */ ;
/** @type {__VLS_StyleScopedClasses['field-label']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
/** @type {__VLS_StyleScopedClasses['border-[var(--color-rule-strong)]']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-[var(--color-surface)]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-ink-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['file:mr-4']} */ ;
/** @type {__VLS_StyleScopedClasses['file:rounded-md']} */ ;
/** @type {__VLS_StyleScopedClasses['file:border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['file:bg-[var(--color-accent-soft)]']} */ ;
/** @type {__VLS_StyleScopedClasses['file:px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['file:py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['file:text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['file:font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['file:text-[var(--color-accent-strong)]']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:file:bg-[var(--color-surface-muted)]']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[var(--color-accent-strong)]']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            config: config,
            selectedName: selectedName,
            onFileChange: onFileChange,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
