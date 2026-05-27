import { ref } from 'vue';
import { defineStore } from 'pinia';
let _nextId = 0;
export const useToastStore = defineStore('toast', () => {
    const toasts = ref([]);
    function show(type, message, duration = 4000) {
        const id = ++_nextId;
        toasts.value.push({ id, type, message });
        setTimeout(() => remove(id), duration);
    }
    function remove(id) {
        toasts.value = toasts.value.filter(t => t.id !== id);
    }
    return { toasts, show, remove };
});
