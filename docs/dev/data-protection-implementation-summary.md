# Data 目录保护实现说明

日期：2026-05-29

关联方案：[data-protection-plan-v2.md](./data-protection-plan-v2.md)

## 已实现范围

本次实现采用 v2 方案中的“离线单包 + license 文件”模型：

- 公开安装包包含应用、`data.enc` 和 Ed25519 公钥。
- 客户单独获得 `license.ard.json` 和高熵 `license_secret`。
- 客户端只内置公钥，不包含私钥、CEK、master secret 或客户授权记录。
- 激活成功后解密数据包并写入激活元数据。

## 代码结构

新增模块：

```text
ai_gen_reimbursement_docs/licensing/
  __init__.py
  _crypto.py
  activation.py
  data_package.py
  exceptions.py
  license_file.py
```

新增脚本：

```text
scripts/build_data_package.py
scripts/generate_license_keypair.py
scripts/issue_license.py
scripts/check_release_data_protection.ps1
scripts/check_release.ps1
```

新增 Web API：

```text
GET  /api/license/status
POST /api/license/activate
```

新增 Web UI：

```text
web_app/src/views/License.vue
/license
```

新增测试：

```text
tests/test_licensing.py
```

## 核心流程

### 1. 生成签名密钥

私钥只允许保存在发行方受控环境，不要提交到仓库。

```powershell
python scripts/generate_license_keypair.py `
  --private-key "$env:USERPROFILE\.ard-keys\signing_private_key.pem" `
  --public-key "$env:USERPROFILE\.ard-keys\signing_public_key.pem"
```

将公钥复制到客户端包路径：

```powershell
Copy-Item "$env:USERPROFILE\.ard-keys\signing_public_key.pem" `
  ".\ai_gen_reimbursement_docs\licensing\public_key.pem" -Force
```

### 2. 构建 data.enc

```powershell
python scripts/build_data_package.py `
  .\data `
  .\data.enc `
  --cek-out "$env:USERPROFILE\.ard-keys\data_cek.b64" `
  --metadata-out "$env:USERPROFILE\.ard-keys\data_package_metadata.json"
```

注意：

- `data_cek.b64` 是敏感文件，只能留在发行方环境。
- `data_package_metadata.json` 可用于记录本次数据包 hash。
- `data.enc` 可以进入公开安装包。

### 3. 签发客户 license

```powershell
python scripts/issue_license.py `
  --private-key "$env:USERPROFILE\.ard-keys\signing_private_key.pem" `
  --data-package .\data.enc `
  --cek-file "$env:USERPROFILE\.ard-keys\data_cek.b64" `
  --customer "客户名称" `
  --output "$env:USERPROFILE\.ard-keys\licenses\license.ard.json" `
  --secret-out "$env:USERPROFILE\.ard-keys\licenses\license.secret.txt" `
  --issued-record "$env:USERPROFILE\.ard-keys\issued_licenses.jsonl"
```

`issued_licenses.jsonl` 只记录非密钥元数据：

```text
issued_at
license_id
customer
license
data_package
data_hash
expires_at
features
```

不会记录：

```text
license_secret
CEK
private_key
```

交付客户：

```text
license.ard.json
license.secret.txt 中的 secret
```

不得交付：

```text
signing_private_key.pem
data_cek.b64
issued_licenses.jsonl
master_secret
```

### 4. 客户端激活

```powershell
ard --activate `
  --license .\license.ard.json `
  --license-secret "客户 secret"
```

可选参数：

```powershell
--data-enc .\data.enc
--data-output .\data
--public-key .\ai_gen_reimbursement_docs\licensing\public_key.pem
--activation-path .\activation.json
```

激活成功后会写入：

```text
~/.ai-gen-reimbursement-docs/license/activation.json
```

## Web API

### 查询授权状态

```http
GET /api/license/status
```

返回字段：

```json
{
  "activated": false,
  "crypto_available": true,
  "data_package_present": false,
  "public_key_present": false,
  "activation_metadata_present": false,
  "paths": {
    "data_enc": "...",
    "data_output": "...",
    "public_key": "...",
    "activation_metadata": "..."
  }
}
```

说明：

- 状态接口不会强制导入 `cryptography`。
- 未发现 `data.enc` 时直接返回未激活。
- 如果存在 `data.enc` 但运行环境缺少 `cryptography`，`crypto_available` 会返回 `false`。

### 提交离线激活

```http
POST /api/license/activate
Content-Type: application/json
```

请求体：

```json
{
  "license_path": "C:/path/license.ard.json",
  "license_text": "",
  "license_secret": "客户 secret",
  "data_enc": "",
  "data_output": "",
  "public_key": "",
  "activation_path": ""
}
```

说明：

- 仅本机请求允许激活。
- `license_path` 和 `license_text` 二选一；Web UI 文件选择器使用 `license_text`。
- `data_enc`、`data_output`、`public_key`、`activation_path` 为空时使用默认路径。

## Web UI

已新增“授权”页面：

```text
/license
```

入口：

```text
顶部导航：授权
```

页面能力：

- 展示激活状态、加密依赖、数据包、公钥、激活元数据状态。
- 展示默认 `data.enc`、`data` 输出目录、公钥和激活元数据路径。
- 支持选择 `license.ard.json` 文件，由浏览器读取 JSON 内容提交。
- 支持拖拽上传 `license.ard.json`，拖入后直接读取 license JSON 内容。
- 支持输入 `license.ard.json` 路径和 `license secret`，作为路径备用模式。
- 支持展开高级路径，覆盖 `data.enc`、`data_output`、`public_key` 和 `activation_path`。
- 支持 license JSON 结构预检查，提前识别 `payload.format`、`payload.license_id`、`payload.customer`、`payload.data_hash`、`payload.wrapped_key`、`signature.alg`、`signature.value` 缺失或异常。
- 支持更明确的就绪提示，包括缺少 `cryptography`、缺少 `data.enc`、缺少 `public_key.pem`。
- 支持更细的激活错误提示，包括授权过期、数据包不匹配、`license secret` 不正确、签名无效、路径缺失。
- 激活成功后自动刷新授权状态。

后端已补充 `/license` SPA 回退路由，避免生产构建下刷新页面 404。

开发态 Vite 使用 `/static/dist/` base，直接访问页面时使用：

```text
http://127.0.0.1:5173/static/dist/license
```

## 发布包检查

新增一键发布前检查脚本：

```powershell
.\scripts\check_release.ps1
```

默认串联执行：

```text
1. Python 回归测试
2. Web 前端生产构建
3. PowerShell 脚本语法检查
4. 发布产物数据保护检查
```

默认测试目标：

```text
tests/test_web_system.py
tests/test_config_utils.py
tests/test_licensing.py
tests/test_logging_handler.py
```

常用参数：

```powershell
.\scripts\check_release.ps1 -ArtifactDir .\dist\ard
.\scripts\check_release.ps1 -RequireProtectedData
.\scripts\check_release.ps1 -SkipArtifactCheck
.\scripts\check_release.ps1 -PythonTestTargets tests/test_licensing.py
```

新增检查脚本：

```powershell
.\scripts\check_release_data_protection.ps1 -ArtifactDir .\dist\ard
```

开发构建模式下：

- 缺少 `data.enc` 只提示。
- 缺少 `public_key.pem` 只提示。
- 如果发现私钥、CEK、license secret 等敏感文件，会失败。

正式发布模式下：

```powershell
.\scripts\check_release_data_protection.ps1 -ArtifactDir .\dist\ard -RequireProtectedData
```

会强制要求：

- 存在 `data.enc`。
- 存在 `ai_gen_reimbursement_docs/licensing/public_key.pem`。
- 不存在私钥、CEK、master secret、license secret、签发记录等敏感文件。
- 不存在明文 `data/` 内容，包括 `data/in_templates`、`data/out_templates` 和 `data/audio`。
- 允许公开提示音位于 `web_app/static/audio/ticktick_pop.wav`。

`build_exe.ps1` 已支持：

```powershell
.\build_exe.ps1 -RequireProtectedData
```

本次还补强了 `build_exe.ps1` 的失败门禁：

```text
npm install 失败会立即退出。
npm run build 失败会短暂等待并重试一次，仍失败则立即退出。
旧 build/、dist/ 清理失败会立即退出。
PyInstaller 失败会立即退出。
```

并调整为仅在 `web_app/node_modules` 不存在时才自动执行 `npm install`，避免每次发布构建都改写依赖目录。

该参数会强制要求构建时存在：

```text
data.enc
ai_gen_reimbursement_docs/licensing/public_key.pem
```

发布产物不会复制：

```text
data/in_templates
data/out_templates
data/audio
```

公开提示音会从 `assets/audio` 复制到：

```text
assets/audio/
web_app/static/audio/
```

## 防误提交规则

`.gitignore` 已加入数据保护相关敏感材料规则：

```text
.ard-keys/
private_key.pem
signing_private_key.pem
*private_key*.pem
*.secret.txt
*.secret
*.cek
*.cek.b64
*cek*.b64
issued_licenses.jsonl
license.ard.json
licenses/
.cache/
.tmp_license_e2e*/
.tmp_release_check*/
web_app/tsconfig.tsbuildinfo
```

目的：

- 避免私钥进入仓库。
- 避免 CEK、license secret、客户 license 和签发记录进入仓库。
- 避免本地端到端演练目录和发布检查临时目录进入仓库。
- 避免 TypeScript 增量构建缓存进入仓库。
- 允许仓库只保存客户端所需的公钥和授权验证代码。

## 公开音频资源

`data/audio` 已从保护数据目录中移出，目标公开资源目录为：

```text
assets/audio/ticktick_pop.wav
```

代码引用更新为：

```text
ai_gen_reimbursement_docs/cli/notify.py
ai_gen_reimbursement_docs/cli/main.py
```

发布时 `build_exe.ps1` 会复制到：

```text
dist/ard/assets/audio/
dist/ard/web_app/static/audio/
```

其中：

- CLI 提示音读取 `assets/audio/ticktick_pop.wav`。
- Web 前端继续使用 `/static/audio/ticktick_pop.wav`。
- `data/` 下除开发源数据外，发布包中不再允许出现明文内容。

## 安全边界

已实现的保护：

- `data.enc` 使用随机 256-bit CEK 加密。
- license 使用完整 Ed25519 签名。
- `license_secret` 使用 scrypt 派生 KEK 后包装 CEK。
- license 与 `data.enc` 通过 `data_hash` 绑定。
- 解包时拒绝路径逃逸、绝对路径、Windows 盘符路径、反斜杠路径、符号链接和硬链接。

未实现的保护：

- 未做机器绑定。
- 未做联网撤销。
- 未做运行时不落盘明文数据。
- 未对已授权用户读取本机明文数据做强 DRM。

这些未实现项与 v2 方案一致，属于后续增强。

## 验证情况

### 本次真实数据包准备

已在当前仓库基于真实 `data/` 目录生成：

```text
data.enc
ai_gen_reimbursement_docs/licensing/public_key.pem
```

生成命令：

```powershell
.\.venv\Scripts\python.exe scripts\generate_license_keypair.py `
  --private-key .ard-keys\signing_private_key.pem `
  --public-key ai_gen_reimbursement_docs\licensing\public_key.pem

.\.venv\Scripts\python.exe scripts\build_data_package.py `
  data `
  data.enc `
  --cek-out .ard-keys\data_cek.b64 `
  --metadata-out .ard-keys\data_package_metadata.json
```

生成结果：

```text
data.enc: 1,229,027 bytes
public_key.pem: 113 bytes
cryptography: 48.0.0
```

敏感材料位置：

```text
.ard-keys/signing_private_key.pem
.ard-keys/data_cek.b64
.ard-keys/data_package_metadata.json
```

这些路径已被 `.gitignore` 保护，不应提交。

已通过：

```powershell
.\scripts\test.ps1 tests/test_web_system.py tests/test_config_utils.py tests/test_licensing.py tests/test_logging_handler.py
```

结果：

```text
38 passed
```

说明：

- 生成真实 `data.enc` 后，`GET /api/license/status` 会自然报告 `data_package_present: true`。
- 对应测试已改为使用临时 `base_dir` 创建独立 FastAPI app，继续覆盖“无数据包时状态接口仍可用”的行为，不再依赖仓库根目录是否存在 `data.enc`。

其中授权专项测试：

```powershell
.\scripts\test.ps1 tests/test_licensing.py
```

结果：

```text
13 passed
```

本地验证依赖版本：

```text
cryptography 48.0.0
```

已通过：

```powershell
PowerShell Parser 检查 build_exe.ps1、scripts/check_release.ps1 和 scripts/check_release_data_protection.ps1
```

已通过：

```powershell
Python AST 语法检查 licensing 模块、发行脚本、CLI 激活入口、license 测试文件
```

已通过前端构建：

```powershell
npm run build
```

结果：

```text
vue-tsc -b && vite build 通过
```

已通过最小发布包数据保护检查：

```powershell
.\scripts\check_release_data_protection.ps1 `
  -ArtifactDir .tmp_release_check_artifact `
  -RequireProtectedData
```

最小发布包镜像包含：

```text
data.enc
ai_gen_reimbursement_docs/licensing/public_key.pem
web_app/static/audio/ticktick_pop.wav
```

检查结果：

```text
[通过] 发布包数据保护检查完成
```

未完成项：

```powershell
.\build_exe.ps1 -RequireProtectedData
```

原因：

```text
当前 Codex 沙箱内执行 build_exe.ps1 时，前端构建阶段 Vite/esbuild 子进程 spawn 被系统拒绝：
Error: spawn EPERM
单独在 web_app 下运行 npm run build 已验证通过，说明前端代码本身可构建。
```

建议在本机执行：

```powershell
.\build_exe.ps1 -RequireProtectedData
.\scripts\check_release.ps1 -RequireProtectedData
```

如只想先验证一键检查除发布产物外的部分：

```powershell
.\scripts\check_release.ps1 -SkipArtifactCheck
```

注意：

```text
当前 Codex 沙箱内存在 pytest 临时目录权限限制，直接在沙箱内运行 check_release.ps1 会在 pytest 临时目录阶段失败。
同一组测试在本机提升环境中已验证通过：38 passed。
```

已验证页面可达：

```text
Vite dev server: /static/dist/license -> 200
FastAPI SPA fallback: /license -> 200
GET /api/license/status 返回授权状态结构
```

已完成端到端发行/激活演练：

```text
generate_license_keypair.py
build_data_package.py
issue_license.py --issued-record
ard --activate --activation-path
POST /api/license/activate with license_text
```

演练结果：

```text
CLI 激活成功，解密 sample.txt 内容为 sample data
Web API 激活成功，返回 200，并解密 sample.txt 内容为 sample data
issued_licenses.jsonl 正常写入非密钥签发记录
```

已修复演练暴露的问题：

```text
默认激活元数据目录无权限时，改为明确 ActivationError。
CLI 支持 --activation-path 覆盖激活元数据路径。
Web API 支持 activation_path 覆盖激活元数据路径。
文件日志写入无权限时静默禁用对应 file handler，保留控制台输出。
```

依赖已写入：

```text
pyproject.toml
ai_gen_reimbursement_docs/requirements.txt
```

## 后续建议

1. 在你本机确认 `.ard-keys/` 仅保留在发行方环境，不随仓库或发布包分发。
2. 执行 `.\build_exe.ps1 -RequireProtectedData` 生成真实发布包。
3. 执行 `.\scripts\check_release.ps1 -RequireProtectedData` 对真实 `dist/ard` 做完整发布前检查。
4. 如需要 ZIP 或安装器，再对最终归档产物解压后重复运行 `check_release_data_protection.ps1 -RequireProtectedData`。
