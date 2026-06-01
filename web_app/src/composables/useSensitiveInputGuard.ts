import { nextTick, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'

interface SensitiveInputGuardOptions {
  inputRef: Ref<HTMLInputElement | null>
  getValue: () => string
  setValue: (value: string) => void
}

export function useSensitiveInputGuard(
  key: string,
  options: SensitiveInputGuardOptions,
) {
  const inputName = `ard-${key}-${Math.random().toString(36).slice(2)}`
  const readonly = ref(true)
  const userActivated = ref(false)
  const timers: number[] = []

  function clearBrowserFill() {
    if (userActivated.value) return

    const input = options.inputRef.value
    if (input && input.value) input.value = ''
    if (options.getValue()) options.setValue('')
  }

  function scheduleAutofillCleanup() {
    for (const delay of [0, 50, 250, 1000]) {
      timers.push(window.setTimeout(clearBrowserFill, delay))
    }
  }

  function activateSensitiveInput() {
    userActivated.value = true
    readonly.value = false
  }

  onMounted(() => {
    nextTick(scheduleAutofillCleanup)
  })

  onBeforeUnmount(() => {
    for (const timer of timers) window.clearTimeout(timer)
  })

  return {
    inputName,
    readonly,
    activateSensitiveInput,
  }
}
