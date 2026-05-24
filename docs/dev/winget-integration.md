# winget 包管理集成

> 2026-05-23，通过 `/grill-me` 决策确定。

## 配置

| 配置项 | 值 |
|---|---|
| 包名 | `mlt-hub.ard` |
| 安装范围 | `user` |
| CI 工具 | `vedantmgoyal9/winget-releaser` |
| 触发方式 | 发布仓独立 workflow |
| 安装命令 | `winget install mlt-hub.ard` |

## 工作流程

```
推 tag v*.*.* → CI 构建 → 发布到发布仓 → winget-releaser 触发 → 自动向 winget-pkgs 提 PR
```

## 手动配置步骤

1. 复制 `.github/workflows/winget.yml` 到发布仓 `mlt-hub/ai-gen-reimbursement-docs-release`
2. 创建 [GitHub Personal Access Token](https://github.com/settings/tokens)（classic），勾选 `public_repo`
3. 在发布仓 Settings → Secrets → Actions 添加 `WINGET_TOKEN`

## 用户安装方式汇总

| 方式 | 命令 / 操作 |
|---|---|
| winget | `winget install mlt-hub.ard` |
| Inno Setup 安装包 | 下载 `ard-setup-vX.X.X.exe`，双击安装 |
| zip 便携版 | 下载 `ard-vX.X.X.zip`，解压即用 |
