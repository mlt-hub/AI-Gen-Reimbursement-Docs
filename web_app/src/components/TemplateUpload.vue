<template>
  <details class="group">
    <summary class="text-sm text-primary-600 cursor-pointer select-none hover:text-primary-700 font-medium">自定义模板</summary>
    <div class="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-gray-100">
      <div>
        <label class="block text-xs text-gray-500 mb-1">FPA 工作量评估模板</label>
        <input type="file" accept=".xlsx,.xlsm" class="text-xs text-gray-500 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200" />
      </div>
      <div>
        <label class="block text-xs text-gray-500 mb-1">COSMIC 拆分表模板</label>
        <input type="file" accept=".xlsx,.xlsm" class="text-xs text-gray-500 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200" />
      </div>
      <div>
        <label class="block text-xs text-gray-500 mb-1">需求清单模板</label>
        <input type="file" accept=".xlsx,.xlsm" class="text-xs text-gray-500 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200" />
      </div>
      <div>
        <label class="block text-xs text-gray-500 mb-1">需求说明书模板</label>
        <input type="file" accept=".docx" class="text-xs text-gray-500 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200" />
      </div>
    </div>
  </details>
</template>
