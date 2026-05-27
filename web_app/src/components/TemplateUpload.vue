<template>
  <details class="group">
    <summary class="subtle-link cursor-pointer select-none text-sm">自定义输出模板</summary>
    <div class="mt-3 flex flex-col gap-3 border-t border-[var(--color-rule)] pt-3">
      <div>
        <label class="field-label text-xs">FPA工作量评估-输出模板</label>
        <input type="file" accept=".xlsx,.xlsm" class="text-xs text-[var(--color-ink-muted)] file:mr-2 file:rounded file:border-0 file:bg-[var(--color-surface-raised)] file:px-3 file:py-1 file:text-xs file:text-[var(--color-ink-muted)] hover:file:bg-[var(--color-surface-muted)]" />
      </div>
      <div>
        <label class="field-label text-xs">项目需求说明书-输出模板</label>
        <input type="file" accept=".docx" class="text-xs text-[var(--color-ink-muted)] file:mr-2 file:rounded file:border-0 file:bg-[var(--color-surface-raised)] file:px-3 file:py-1 file:text-xs file:text-[var(--color-ink-muted)] hover:file:bg-[var(--color-surface-muted)]" />
      </div>
      <div>
        <label class="field-label text-xs">项目功能点拆分表-输出模板</label>
        <input type="file" accept=".xlsx,.xlsm" class="text-xs text-[var(--color-ink-muted)] file:mr-2 file:rounded file:border-0 file:bg-[var(--color-surface-raised)] file:px-3 file:py-1 file:text-xs file:text-[var(--color-ink-muted)] hover:file:bg-[var(--color-surface-muted)]" />
      </div>
      <div>
        <label class="field-label text-xs">项目需求清单-输出模板</label>
        <input type="file" accept=".xlsx,.xlsm" class="text-xs text-[var(--color-ink-muted)] file:mr-2 file:rounded file:border-0 file:bg-[var(--color-surface-raised)] file:px-3 file:py-1 file:text-xs file:text-[var(--color-ink-muted)] hover:file:bg-[var(--color-surface-muted)]" />
      </div>
      
    </div>
  </details>
</template>
