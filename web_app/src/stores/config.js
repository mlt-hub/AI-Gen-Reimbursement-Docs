import { ref, computed, watch } from 'vue';
import { defineStore } from 'pinia';
// ── localStorage 持久化 ───────────────────────────────────
function loadStr(key, fallback) {
    try {
        return localStorage.getItem(key) ?? fallback;
    }
    catch {
        return fallback;
    }
}
function saveStr(key, val) {
    try {
        localStorage.setItem(key, val);
    }
    catch { /* 忽略 */ }
}
function loadBool(key, fallback) {
    try {
        const v = localStorage.getItem(key);
        return v === null ? fallback : v === 'true';
    }
    catch {
        return fallback;
    }
}
function saveBool(key, val) {
    try {
        localStorage.setItem(key, String(val));
    }
    catch { /* 忽略 */ }
}
const STORAGE_KEYS = ['apiKey', 'model', 'baseUrl', 'maxTokens', 'projectName', 'pipelineMode', 'clean'];
export const useConfigStore = defineStore('config', () => {
    const workMode = ref('local');
    const pipelineMode = ref(loadStr('pipelineMode', 'from-excel-gen-all'));
    const xlsxPath = ref('');
    const outputDir = ref('');
    const apiKey = ref(loadStr('apiKey', ''));
    const model = ref(loadStr('model', ''));
    const baseUrl = ref(loadStr('baseUrl', ''));
    const maxTokens = ref(loadStr('maxTokens', ''));
    const projectName = ref(loadStr('projectName', ''));
    const clean = ref(loadBool('clean', false));
    const selectedFile = ref(null);
    // ── 自动持久化 ──
    watch(apiKey, v => saveStr('apiKey', v));
    watch(model, v => saveStr('model', v));
    watch(baseUrl, v => saveStr('baseUrl', v));
    watch(maxTokens, v => saveStr('maxTokens', v));
    watch(projectName, v => saveStr('projectName', v));
    watch(pipelineMode, v => saveStr('pipelineMode', v));
    watch(clean, v => saveBool('clean', v));
    const isValid = computed(() => {
        if (workMode.value === 'local')
            return xlsxPath.value.trim().length > 0;
        return selectedFile.value !== null;
    });
    function reset() {
        xlsxPath.value = '';
        outputDir.value = '';
        apiKey.value = '';
        model.value = '';
        baseUrl.value = '';
        maxTokens.value = '';
        projectName.value = '';
        clean.value = false;
        selectedFile.value = null;
    }
    /** 导出用户设置为 JSON 字符串。 */
    function exportSettings() {
        const data = {
            apiKey: apiKey.value,
            model: model.value,
            baseUrl: baseUrl.value,
            maxTokens: maxTokens.value,
            projectName: projectName.value,
            pipelineMode: pipelineMode.value,
            clean: clean.value,
        };
        return JSON.stringify(data, null, 2);
    }
    /** 从 JSON 字符串导入用户设置。 */
    function importSettings(json) {
        try {
            const data = JSON.parse(json);
            if (data.apiKey !== undefined)
                apiKey.value = data.apiKey;
            if (data.model !== undefined)
                model.value = data.model;
            if (data.baseUrl !== undefined)
                baseUrl.value = data.baseUrl;
            if (data.maxTokens !== undefined)
                maxTokens.value = data.maxTokens;
            if (data.projectName !== undefined)
                projectName.value = data.projectName;
            if (data.pipelineMode !== undefined)
                pipelineMode.value = data.pipelineMode;
            if (data.clean !== undefined)
                clean.value = data.clean;
            return true;
        }
        catch {
            return false;
        }
    }
    return { workMode, pipelineMode, xlsxPath, outputDir, apiKey, model, baseUrl,
        maxTokens, projectName, clean, selectedFile, isValid, reset,
        exportSettings, importSettings };
});
