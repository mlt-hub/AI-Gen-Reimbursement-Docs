import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
export const useSessionStore = defineStore('session', () => {
    const sessionId = ref(null);
    const runState = ref('idle');
    const outputDir = ref('');
    const inputPrompt = ref(null);
    const listPrompt = ref(null);
    const doneFiles = ref([]);
    const isRunning = computed(() => runState.value === 'running');
    const isDone = computed(() => runState.value === 'done');
    function start(sid, out) {
        sessionId.value = sid;
        outputDir.value = out;
        runState.value = 'running';
        inputPrompt.value = null;
        listPrompt.value = null;
        doneFiles.value = [];
    }
    function restore(snapshot) {
        sessionId.value = snapshot.session_id;
        outputDir.value = snapshot.output_dir || '';
        runState.value = snapshot.run_state;
        inputPrompt.value = null;
        listPrompt.value = null;
        doneFiles.value = snapshot.done_files || [];
    }
    function finish(files) {
        runState.value = 'done';
        inputPrompt.value = null;
        listPrompt.value = null;
        if (files)
            doneFiles.value = files;
    }
    function setError() {
        runState.value = 'error';
        inputPrompt.value = null;
        listPrompt.value = null;
    }
    function reset() {
        sessionId.value = null;
        outputDir.value = '';
        runState.value = 'idle';
        inputPrompt.value = null;
        listPrompt.value = null;
        doneFiles.value = [];
    }
    function showInputPrompt(prompt) {
        inputPrompt.value = prompt;
    }
    function showListPrompt(prompt) {
        listPrompt.value = prompt;
    }
    return { sessionId, runState, outputDir, inputPrompt, listPrompt, doneFiles, isRunning, isDone, start, restore, finish, setError, reset, showInputPrompt, showListPrompt };
});
