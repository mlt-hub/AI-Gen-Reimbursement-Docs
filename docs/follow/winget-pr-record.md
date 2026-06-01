# Winget 上架记录 — mlt-hub.ard

> 最后更新：2026-06-01

## 仓库信息

| 项目 | 值 |
|------|-----|
| 包名 | mlt-hub.ard |
| Winget 仓库 | microsoft/winget-pkgs |
| Fork | mlt-hub/winget-pkgs |
| 工作分支 | `add-ard-1.0.0-alpha` |
| 安装包 Release | mlt-hub/AI-Gen-Reimbursement-Docs-Release |

## PR 历程

| # | PR | 状态 | 说明 |
|---|-----|------|------|
| 1 | [#378910](https://github.com/microsoft/winget-pkgs/pull/378910) | ❌ 已关闭 | 初版，v1.0.0-alpha，Release 不存在导致 URL 404 |
| 2 | [#381470](https://github.com/microsoft/winget-pkgs/pull/381470) | 🟡 审核中 | v1.0.1-alpha，验证已通过，等人工审核（已等待 7 天） |

## 关键问题与处理

### 1. Release 不存在（根因）
- 清单指向 `v1.0.0-alpha`，但 release 仓库只有 `v1.0.1-alpha`
- **处理**：改为 v1.0.1-alpha，更新 URL、SHA256

### 2. CLA
- `license/cla` 检查通过，但 `Needs-CLA` 标签残留
- **处理**：评论 `@microsoft-github-policy-service agree`，标签已自动移除

### 3. URL Validation
- 首次验证 404 触发 `Validation-Guide` 标签
- URL 修复后验证流水线通过，标签需审核员手动清除

### 4. 5/30 验证重新触发
- wingetbot 自动验证时 URL 检查报错（疑似检查了旧路径 `v1.0.0-alpha`，实际清单已改为 `v1.0.1-alpha`）
- mlt-hub 解释项目背景：开源报账文档工具，SmartScreen 误报属于新未签名二进制常态
- 重新触发 `@wingetbot run` 后验证全部通过
- 重申 CLA 协议

### 5. 等待时间
- PR 创建于 2026-05-26，至今已 7 天无人类审核员介入
- Winget 社区审核队列通常需 1-2 周，仍在正常范围内

## 当前状态 (2026-06-01)

- ✅ 自动验证全部通过（Azure-Pipeline-Passed, Validation-Completed）
- ⏳ 等待社区审核员人工审核（PR 创建于 5/26，已 7 天）
- 📋 标签：`Azure-Pipeline-Passed` `Validation-Completed` `New-Package` `Validation-Guide`
- 🔄 5/30 验证流水线重跑 3 次，最终全部通过
- 📝 已在评论区补充项目说明、SmartScreen 误报解释
- ⚠️ `Validation-Guide` 标签仍在，需审核员手动清除

## 操作备忘

```bash
# winget-pkgs 仓库路径
cd /f/mlt/mlt-projects/winget-pkgs

# 同步上游
git fetch upstream master
git checkout add-ard-1.0.0-alpha
git rebase upstream/master

# 推送并创建 PR
git push origin add-ard-1.0.0-alpha
gh pr create --repo microsoft/winget-pkgs \
  --head mlt-hub:add-ard-1.0.0-alpha \
  --base master \
  --title "Add mlt-hub.ard version X.X.X"

# 查看 PR 状态
gh pr view 381470 --repo microsoft/winget-pkgs --json labels,state
```
