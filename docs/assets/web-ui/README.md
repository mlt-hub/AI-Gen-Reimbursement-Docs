# Web UI 验证截图

本目录用于归档 Web UI 审计、整改和响应式验证截图。

命名建议：

- `YYYY-MM-DD-home-before-desktop.png`
- `YYYY-MM-DD-home-after-desktop.png`
- `YYYY-MM-DD-home-after-mobile.png`
- `YYYY-MM-DD-config-after-desktop.png`
- `YYYY-MM-DD-config-after-mobile.png`
- `YYYY-MM-DD-config-after-narrow.png`

约定：

- 不再将 `ui-*.png` 放在仓库根目录。
- 临时截图如果只用于当次人工检查，可以在验证结束后删除。
- 需要长期保留的截图应移动到本目录，并在对应审计或总结文档中引用。
- 当前 Windows + Edge headless 环境可能存在 DPI 换算差异；如果 375px 截图出现物理裁切，应保留实际无裁切的 narrow 截图，并在验证记录中说明。
