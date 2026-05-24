# AI生成项目报账文档 — 打包发布方案

> 2026-05-22，通过 `/grill-me` 逐项决策确定。

## 1. 目标与约束

| 项目 | 说明 |
|---|---|
| 目标用户 | 非技术用户（业务人员） |
| 平台 | Windows |
| 仓库结构 | 代码仓 `mlt-hub/AI-Gen-Reimbursement-Docs`（私有），发布仓 `mlt-hub/ai-gen-reimbursement-docs-release`（公开） |

## 2. 分发形式

两种：

| 形式 | 文件名 | 说明 |
|---|---|---|
| zip 便携版 | `ard-vX.X.X.zip` | 解压即用，根目录平铺 |
| Inno Setup 安装包 | `ard-setup-vX.X.X.exe` | 安装引导，含快捷方式和 PATH |

不含自解压 exe。

### winget 安装

| 配置项 | 值 |
|---|---|
| 包名 | `mlt-hub.ard` |
| 安装范围 | `user`（`%LOCALAPPDATA%\Programs\ard\`） |
| 清单仓库 | [microsoft/winget-pkgs](https://github.com/microsoft/winget-pkgs) |
| CI 工具 | `vedantmgoyal9/winget-releaser` |
| 安装命令 | `winget install mlt-hub.ard` |

CI 发布时自动向 winget-pkgs 提 PR（更新版本号 + 下载 URL），微软审核通过后用户即可通过 winget 安装。

## 3. 安装包行为（Inno Setup）

| 配置项 | 值 |
|---|---|
| 默认安装目录 | `%LOCALAPPDATA%\Programs\ard\`（用户级别，可自定义） |
| 用户 PATH | 添加安装目录到用户级 PATH，无需管理员权限 |
| 桌面快捷方式 | 「启动 Web 界面」→ `ard.exe --web`、「命令行方式」→ 打开终端并打印 `ard.exe --help` |
| 开始菜单 | 程序组：启动 Web 界面 / 命令行方式 / 卸载 |
| 覆盖安装 | 支持，用户配置在 `~/.ai-gen-reimbursement-docs/` 不受影响 |

## 4. Python 运行时

- PyInstaller `--onedir`：exe + 依赖放在同一目录，启动无需解压
- 附加文件（`web_app/`、`data/`、`config/`）通过构建脚本 `Copy-Item` 拷贝到输出的目录

## 5. 配置文件处理

已实现，无需改动：

- 首次运行自动复制 `.example` → `~/.ai-gen-reimbursement-docs/`
- 后续运行 `migrate_config()` 自动追加模板中的新键到用户配置
- 程序目录放只读示例，用户数据与程序分离

## 6. 更新机制

- 手动覆盖安装（Inno Setup 支持升级安装）
- 启动时检查发布仓 GitHub Releases API → 提示新版本

## 7. 代码签名

暂不签名。

## 8. CI/CD

- 触发器：推 tag `v*.*.*` 或手动 `workflow_dispatch`
- Runner：`windows-latest`
- 流程：
  1. 安装 Node.js + Python + 依赖
  2. 前端 `npm run build`
  3. PyInstaller `--onedir` 构建
  4. `Copy-Item` 拷贝 `web_app/`、`data/`、`config/`
  5. 压缩 zip
  6. Inno Setup 命令行（`iscc.exe`）编译安装包
  7. 发布到代码仓 + 发布仓 GitHub Releases
  8. `winget-releaser` 自动向 winget-pkgs 提 PR

## 9. 发布产物

| 产物 | 说明 |
|---|---|
| `ard-vX.X.X.zip` | 便携版 |
| `ard-setup-vX.X.X.exe` | Inno Setup 安装包 |

## 10. 目录结构（安装后 / zip 解压后）

```
ard/
├── ard.exe
├── python3.dll / python312.dll / ...   (PyInstaller 依赖)
├── _internal/                           (PyInstaller bundles)
├── web_app/
│   ├── server.py
│   └── static/
│       ├── index.html
│       ├── config.html
│       └── prompt-debug.html
├── data/
│   ├── out_templates/
│   ├── in_templates/
│   └── audio/
├── config/
│   ├── .env.example
│   └── system_config.yaml.example
├── README.md
└── CHANGELOG.md
```

用户配置文件位置：`~/.ai-gen-reimbursement-docs/`
