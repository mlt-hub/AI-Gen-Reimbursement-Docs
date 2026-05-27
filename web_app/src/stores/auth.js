import { ref, computed } from 'vue';
import { defineStore } from 'pinia';
export const useAuthStore = defineStore('auth', () => {
    const username = ref('');
    const isLocal = ref(true);
    const allowRegister = ref(true);
    const loading = ref(true);
    const isLoggedIn = computed(() => !!username.value);
    const isRemote = computed(() => !isLocal.value);
    async function init() {
        try {
            const resp = await fetch('/api/auth/me');
            if (resp.ok) {
                const data = await resp.json();
                username.value = data.username || '';
                isLocal.value = data.is_local;
                allowRegister.value = data.allow_register;
            }
        }
        catch { /* 忽略 */ }
        loading.value = false;
    }
    async function login(user, password) {
        const resp = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password }),
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '登录失败');
        }
        const data = await resp.json();
        username.value = data.username;
        return data;
    }
    async function register(user, password) {
        const resp = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: user, password }),
        });
        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.detail || '注册失败');
        }
    }
    async function logout() {
        await fetch('/api/auth/logout', { method: 'POST' });
        username.value = '';
    }
    return { username, isLocal, allowRegister, loading, isLoggedIn, isRemote, init, login, register, logout };
});
