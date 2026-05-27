import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
const STEP_ORDER = ['basedata', 'fpa', 'spec', 'cosmic', 'list'];
const STEP_LABELS = {
    basedata: '基础数据',
    fpa: 'FPA工作量评估',
    spec: '项目需求说明书',
    cosmic: '项目功能点拆分表',
    list: '项目需求清单',
};
export const useStepsStore = defineStore('steps', () => {
    const activeKey = ref(null);
    const doneKeys = ref(new Set());
    const steps = computed(() => {
        return STEP_ORDER.map((key) => ({
            key,
            label: STEP_LABELS[key] || key,
            state: doneKeys.value.has(key) ? 'done'
                : activeKey.value === key ? 'active'
                    : 'pending',
        }));
    });
    function setActive(key) {
        // 将当前 active 标记为 done，新 key 设为 active
        if (activeKey.value && activeKey.value !== key) {
            doneKeys.value.add(activeKey.value);
        }
        activeKey.value = key;
    }
    function finishAll() {
        if (activeKey.value) {
            doneKeys.value.add(activeKey.value);
            activeKey.value = null;
        }
    }
    function reset() {
        activeKey.value = null;
        doneKeys.value = new Set();
    }
    return { steps, setActive, finishAll, reset };
});
