# 自动更新方案设计

## 版本

v1.0 — 2026-05-17

## 目标

为 PyInstaller 打包的 exe 程序添加完整的自动更新能力：后台检查 + 一键更新 + 回滚。

---

## 整体流程

```
ard --update
  │
  ├─ ① 检查更新
  │    GET /repos/{owner}/{repo}/releases/latest
  │    比对 tag_name (如 v5.1.0) 与当前版本
  │    ├─ 相同 → "已是最新版本"，退出
  │    └─ 有新版本 → 显示 changelog，用户确认
  │
  ├─ ② 下载
  │    下载 zip 到 %TEMP%/ard-update/
  │    显示进度条（百分比 + 大小）
  │
  ├─ ③ 校验（可选）
  │    如果 Release 附带 .sha256 文件，校验下载完整性
  │
  ├─ ④ 解压
  │    解压到 %TEMP%/ard-update/new/
  │    快速验证：运行 ard.exe --version 确认版本号匹配
  │
  ├─ ⑤ 生成替换脚本
  │    replace.bat:
  │      等待所有 ard.exe 进程退出
  │      备份旧文件到 .backup/
  │      xcopy 新文件覆盖
  │      清理临时目录
  │      重新启动 ard.exe（携带原命令行参数）
  │      自删除
  │
  └─ ⑥ 启动脚本 → 退出当前进程
       └─ 替换脚本完成 → 新版本启动
```

## 启动时静默检查

```
ard --from-excel xxx --gen-all
  │
  ├─ 后台线程请求 GitHub API（3 秒超时）
  │    ├─ 无新版本 → 什么都不输出
  │    ├─ 网络失败 → 静默跳过
  │    └─ 有新版本 → 缓存结果，不立即输出
  │
  ├─ 主流程正常执行（不等待检查结果）
  │
  └─ 所有结果输出完毕 → 末尾打印更新提醒
       ╔══════════════════════════════════════════════════╗
       ║  发现新版本 v5.1.0（当前 v5.0.0）                ║
       ║  更新日志: https://github.com/.../tag/v5.1.0     ║
       ║  运行 ard --update 进行更新                      ║
       ╚══════════════════════════════════════════════════╝
```

### 关键设计

- **非阻塞**：后台线程 + 3 秒超时，网络慢不影响主流程
- **延迟输出**：主流程期间不输出任何更新相关内容，全结束后统一打印
- **频率控制**：缓存上次检查时间到 `~/.ai-gen-reimbursement-docs/.update_cache`，24 小时内不重复检查
- **静默失败**：网络异常或超时静默跳过，不影响用户操作

---

## 替换脚本

```batch
@echo off
setlocal enabledelayedexpansion

:: 等待所有 ard.exe 进程退出
:loop
timeout /t 1 /nobreak >nul
tasklist /fi "IMAGENAME eq %EXE_NAME%" 2>nul | find /i "%EXE_NAME%" >nul
if not errorlevel 1 goto loop

:: 备份旧版本
if exist "%~dp0.backup" rmdir /s /q "%~dp0.backup"
mkdir "%~dp0.backup"
xcopy /Y /E /Q "%~dp0*" "%~dp0.backup\" >nul

:: 覆盖新版本
xcopy /Y /E /Q "%NEW_DIR%\*" "%~dp0" >nul

:: 清理临时目录
rmdir /s /q "%TEMP_DIR%"

:: 重新启动（携带原命令行参数）
start "" "%~dp0%EXE_NAME%" %ORIG_ARGS%

:: 自删除
del "%~f0"
```

---

## 回滚

```
ard --rollback
```

从 `.backup/` 目录恢复上一个版本的文件。同样生成替换脚本执行（因 exe 运行时不可覆盖自身）。

更新审计日志中记录回滚行为。

---

## CLI 使用方式

```
ard --update               # 手动检查并更新到最新版
ard --update --dry-run     # 仅检查，不下载
ard --update --prerelease  # 包含预发布版
ard --rollback             # 回退到上一个版本
ard --from-excel ...       # 正常使用，后台静默检查（如启用）
```

---

## 配置

`system_config.yaml` 新增：

```yaml
updater:
  repo: "mlt-hub/cosmic-tool-release"   # GitHub 仓库（owner/repo）
  check_on_startup: true                 # 启动时自动检查更新
```

---

## 文件变更清单

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `ai_gen_reimbursement_docs/cli/updater.py` | 核心更新逻辑（~250 行） |
| 修改 | `ai_gen_reimbursement_docs/cli/main.py` | 添加 `--update`、`--rollback` 参数 + 调用入口 + 启动检查（~40 行） |
| 修改 | `config/system_config.yaml.example` | 增加 `updater` 配置节 |
| 修改 | `.github/workflows/release.yml` | 统一 exe 名称为 `ard`，增加 `.sha256` 校验文件 |
| 修改 | `build_exe.ps1` | 增加 `.sha256` 生成 |

---

## 关键设计决策

### 1. 完全使用标准库

`updater.py` 只用 `urllib.request` + `json` + `zipfile` + `subprocess`，不引入第三方依赖，避免 PyInstaller 打包膨胀。

### 2. 替换方案：批处理中转

Windows 上运行中的 exe 无法被覆盖。生成 `.bat` 脚本等待进程退出后执行替换，是 PyInstaller 生态的标准做法。

### 3. 版本获取

exe 模式下从内嵌的 `pyproject.toml` 读取；源码模式下从项目根读取。复用已有 `_get_version()`。

### 4. GitHub API 免认证

查询公开 Release 不需要 token，但未认证限速 60 次/小时。可选项：从 `.env` 读取 `GITHUB_TOKEN` 提升至 5000 次/小时。

### 5. exe 名称自适应

从 `sys.executable` 获取当前 exe 名称，替换脚本不硬编码。

---

## 功能清单

| 优先级 | 功能 | 说明 |
|--------|------|------|
| 必须 | `--update` 手动更新 | 核心功能 |
| 必须 | 启动时静默检查 + 结束提醒 | 用户感知 |
| 必须 | 替换脚本 + 备份回滚 | 安全底线 |
| 必须 | exe 名称自适应 | CI/本地兼容 |
| 建议 | 多实例检测 | 防止文件占用 |
| 建议 | 审计日志 | 排查更新问题 |
| 建议 | 完成后自动启动原任务 | 无感衔接 |
| 可选 | 断点续传 | 大文件体验 |

---

## 审计日志格式

`~/.ai-gen-reimbursement-docs/update.log`：

```
2026-05-17 14:30:22  v5.0.0 → v5.1.0  成功
2026-05-20 09:12:05  v5.1.0 → v5.1.1  失败（下载超时）
2026-05-20 09:15:00  v5.1.1 → v5.1.0  回滚
```
