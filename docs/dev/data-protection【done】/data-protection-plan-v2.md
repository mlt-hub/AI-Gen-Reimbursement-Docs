# Data 目录保护方案 v2

日期：2026-05-29

关联文档：[data-protection-plan.md](./data-protection-plan.md)

## 1. 结论

原方案的目标是正确的：

- `data/` 原始文件不进入安装包。
- 私钥不进入仓库、不进入安装包。
- winget、官网下载、ZIP 分发使用同一套应用层激活逻辑。
- 用户首次启动时输入授权材料，成功后才能使用受保护数据。

但原方案中“短授权码直接派生 AES 密钥”和“同一个公开安装包支持多个客户授权”存在结构冲突；同时，截断 Ed25519 签名无法通过标准验签，也不适合作为安全凭据。

本 v2 方案采用更清晰的安全边界：

- `data.enc` 由随机内容密钥 `CEK` 加密。
- 客户授权不直接等于 AES 密钥。
- 授权材料是一个签名 license 文件或较长 license token。
- license 中包含被授权方可解开的 `wrapped_key`。
- 客户端只内置公钥，用于验签 license。
- 私钥和主密钥只保存在发行方离线环境。

推荐先实现“离线单包 + license 文件”模型。它最适合 winget、官网、ZIP 三种分发方式共用同一个安装包。

## 2. 保护目标与非目标

### 2.1 保护目标

本方案保护的是：

- 安装包中不直接包含明文 `data/`。
- 未拿到有效 license 的用户不能通过正常应用流程解密 `data.enc`。
- license 可区分客户、批次、有效期和功能范围。
- 私钥不进入仓库、不进入安装包。
- 同一个安装包可以发给多个客户，授权通过单独渠道发放。

### 2.2 非目标

必须明确以下非目标，避免误判安全边界：

- 不能阻止已授权用户在本机读取解密后的数据。
- 不能阻止拥有本机管理员权限的用户调试进程、dump 内存或复制明文文件。
- 不能在纯离线场景下可靠阻止授权文件被复制到另一台机器，除非引入机器绑定。
- 不能替代法律协议、合同约束和客户管理流程。

本方案的实际定位是：

```text
防止未授权用户从安装包直接获得 data 明文；
提高授权分发和客户追踪能力；
降低误分发、误打包、公开渠道泄露 data 的风险。
```

## 3. 推荐分发模型

### 3.1 推荐模型：离线单包 + license 文件

适用场景：

- winget。
- 官网下载安装包。
- ZIP 分发。
- 希望所有渠道使用同一个安装包。
- 希望授权通过另一个渠道发放。

分发物：

```text
公开安装包:
  app.exe
  data.enc
  public_key.pem

单独发给客户:
  license.ard.json
```

特点：

- 所有客户可以下载同一个安装包。
- 每个客户拿到不同 license。
- license 中包含客户信息、有效期、data 包 hash、wrapped CEK 和签名。
- 客户端用内置公钥验签 license。
- 验签通过后，客户端从 license 中解出 `CEK`，再解密 `data.enc`。

### 3.2 不推荐模型：短授权码直接派生 AES 密钥

不推荐原因：

- 短授权码熵不足，离线暴力破解风险高。
- 截断签名不能用 Ed25519 标准验签。
- 一个 `data.enc` 只能匹配一个授权码，无法自然支持 winget 统一包。
- 授权码一旦泄露，无法携带足够元数据做审计和策略控制。

### 3.3 可选模型：按客户分包

适用场景：

- 不需要 winget 统一公开安装包。
- 每个客户单独交付 ZIP 或安装器。

特点：

- 每个客户的 `data.enc` 用不同授权材料加密。
- 构建流程更简单。
- 分发和版本管理更复杂。

本项目当前目标包含 winget，因此不建议优先采用按客户分包。

## 4. 加密与授权结构

### 4.1 核心术语

- `CEK`：Content Encryption Key，随机 256-bit 内容密钥，用于加密 `data/`。
- `KEK`：Key Encryption Key，用于包装 `CEK`。
- `data.enc`：加密后的数据包。
- `license.ard.json`：客户授权文件。
- `private_key.pem`：Ed25519 私钥，只在发行方离线环境。
- `public_key.pem`：Ed25519 公钥，进入仓库和安装包，用于验签。

### 4.2 data.enc 格式

建议使用二进制头 + AES-GCM 密文。

逻辑结构：

```json
{
  "format": "ard-data-v1",
  "kdf": "none",
  "cipher": "AES-256-GCM",
  "nonce": "...",
  "data_hash": "sha256:...",
  "ciphertext": "..."
}
```

实际实现可以是：

- 简单二进制格式。
- 或 JSON + base64。
- 或 zip/tar 外层加密。

建议先使用 JSON + base64，便于调试和测试；后续再优化体积。

### 4.3 license 文件格式

推荐 license 文件：

```json
{
  "payload": {
    "format": "ard-license-v1",
    "license_id": "lic_20260529_8X4K2P",
    "customer": "example-customer",
    "issued_at": "2026-05-29T00:00:00Z",
    "expires_at": null,
    "data_hash": "sha256:...",
    "features": [
      "data:default"
    ],
    "wrapped_key": {
      "alg": "AES-256-GCM",
      "kdf": "scrypt",
      "salt": "...",
      "nonce": "...",
      "ciphertext": "..."
    }
  },
  "signature": {
    "alg": "Ed25519",
    "value": "base64..."
  }
}
```

签名规则：

- 对 `payload` 的 canonical JSON 字节签名。
- 使用完整 Ed25519 签名。
- 不截断签名。

canonical JSON 建议：

```python
json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
```

### 4.4 wrapped_key 设计

在纯离线模型中，license 仍需要让客户端恢复 `CEK`。

可选方案：

#### 方案 A：license token 中包含高熵 secret

发行方为每个客户生成一个高熵 secret：

```text
license_secret = 32 bytes random
```

`wrapped_key` 使用从 `license_secret` 派生的 KEK 加密 `CEK`。

客户拿到：

```text
license.ard.json
license secret 或完整 license token
```

优点：

- 真正离线。
- 不依赖服务端。

缺点：

- 用户需要保管较长授权材料。
- 如果 secret 和 license 文件一起泄露，就可以解密。

#### 方案 B：license 文件直接包含加密后的 CEK，客户端内置解包公钥

使用非对称加密包装 `CEK`，例如 X25519 或 RSA-OAEP。

优点：

- 用户只需要 license 文件。

缺点：

- 客户端必须有解包私钥才可离线解密；如果解包私钥进入客户端，就可能被逆向提取。
- 不适合高安全要求。

#### 方案 C：联网激活后换取 CEK

客户端提交 license 到授权服务器，服务器返回短期解密材料。

优点：

- 可撤销。
- 可统计激活。
- 可做机器绑定。

缺点：

- 需要授权服务器。
- 不满足完全离线。

推荐：

```text
短期：方案 A，离线高熵 license token。
长期：如需要撤销和机器绑定，再升级到方案 C。
```

## 5. 激活流程

### 5.1 首次启动

```text
启动应用
  ↓
检查激活元数据
  ├─ 有效 → 正常启动
  └─ 无效或不存在 → 显示激活界面
          ↓
      用户选择 license 文件/输入 license token
          ↓
      验证 license 签名
          ├─ 失败 → 显示“授权文件无效”
          └─ 成功
              ↓
          校验 data_hash 是否匹配当前 data.enc
              ├─ 不匹配 → 显示“授权文件与数据包不匹配”
              └─ 匹配
                  ↓
              解开 CEK
                  ↓
              解密 data.enc
                  ↓
              安全解包到 data/
                  ↓
              写入激活元数据
                  ↓
              正常启动
```

### 5.2 后续启动

后续启动不能只检查 `.activated` 文件是否存在。

建议检查：

- 激活元数据文件存在。
- 激活元数据签名或 HMAC 有效。
- `data.enc` hash 与激活时一致。
- `data/` 关键文件存在。
- license 未过期。

激活元数据建议位置：

```text
~/.ai-gen-reimbursement-docs/license/activation.json
```

示例：

```json
{
  "format": "ard-activation-v1",
  "license_id": "lic_20260529_8X4K2P",
  "customer": "example-customer",
  "data_hash": "sha256:...",
  "activated_at": "2026-05-29T01:23:45Z",
  "expires_at": null
}
```

注意：

- 如果不做机器绑定，这个文件仍可被复制。
- 它的作用是防止简单伪造和误状态，不是强 DRM。

## 6. 解包安全要求

不得直接使用：

```python
tar.extractall(output_dir)
```

必须做安全解包。

要求：

- 禁止绝对路径。
- 禁止 `..` 路径逃逸。
- 禁止符号链接或硬链接逃逸。
- 最终目标路径必须位于 `output_dir` 下。

示例：

```python
def safe_extract_tar(tar, output_dir: Path) -> None:
    output_root = output_dir.resolve()
    for member in tar.getmembers():
        target = (output_root / member.name).resolve()
        if not str(target).startswith(str(output_root) + os.sep):
            raise ValueError(f"非法路径: {member.name}")
        if member.issym() or member.islnk():
            raise ValueError(f"不允许链接: {member.name}")
    tar.extractall(output_root)
```

如果使用 zip，也需要同样的路径校验。

## 7. 仓库文件结构建议

当前仓库已有：

```text
ai_gen_reimbursement_docs/auth.py
```

因此不应新建：

```text
ai_gen_reimbursement_docs/auth/__init__.py
```

否则会产生 Python 模块/包同名冲突。

推荐新增：

```text
ai_gen_reimbursement_docs/licensing/
  __init__.py
  public_key.pem
  license_models.py
  verifier.py
  decryptor.py
  activation.py
```

或更小的第一版：

```text
ai_gen_reimbursement_docs/licensing.py
ai_gen_reimbursement_docs/licensing_public_key.pem
```

推荐使用包目录，便于后续拆分测试。

## 8. 构建与发行方私有文件

### 8.1 仓库内

```text
ai_gen_reimbursement_docs/licensing/
  __init__.py
  public_key.pem
  verifier.py
  decryptor.py
  activation.py

scripts/
  build_data_package.py
```

仓库内可以包含：

- 公钥。
- 数据包构建脚本。
- license 校验逻辑。
- 解密逻辑。

仓库内不应包含：

- 私钥。
- 客户 license。
- 生产 CEK。
- 原始未授权分发的私有 `data/`，如果 data 目录确实是商业资产。

### 8.2 发行方本机

```text
~/.ard-keys/
  signing_private_key.pem
  signing_public_key.pem
  master_secret.bin
  issued_licenses.jsonl
```

建议：

- 私钥只保存在离线或受控机器。
- `issued_licenses.jsonl` 记录 license id、客户、data hash、签发时间、过期时间。
- 私钥文件设置系统权限，仅当前用户可读。

### 8.3 安装包内

```text
app.exe
data.enc
public_key.pem
```

如果使用 PyInstaller，需要确认：

- `data.enc` 被打包或随安装目录分发。
- `public_key.pem` 可被运行时代码找到。
- 不包含原始 `data/`。
- 不包含私钥和发行方记录。

## 9. 构建流程

### 9.1 生成 data.enc

```text
data/
  ↓
打包为 tar/zip bytes
  ↓
生成随机 CEK
  ↓
AES-256-GCM 加密
  ↓
写出 data.enc
  ↓
记录 data_hash
```

### 9.2 签发 license

```text
输入:
  customer
  data_hash
  features
  expires_at
  license_secret
  CEK

步骤:
  1. 用 license_secret 派生 KEK
  2. 用 KEK 加密 CEK，得到 wrapped_key
  3. 构造 payload
  4. 用 Ed25519 私钥签名 payload
  5. 输出 license.ard.json
```

### 9.3 打包安装程序

安装包包含：

```text
app.exe
data.enc
public_key.pem
```

安装包不包含：

```text
data/
private_key.pem
issued_licenses.jsonl
license_secret
license.ard.json
```

### 9.4 发放授权

通过另一个渠道发给客户：

```text
license.ard.json
license secret 或完整 token
```

如果希望用户只输入一个字符串，可以把 license payload、signature、secret 打包成一个较长 token；但不建议追求 16 位以内的短码。

## 10. 客户端实现建议

### 10.1 模块拆分

```text
licensing/
  license_models.py  # TypedDict/dataclass
  verifier.py        # Ed25519 验签、payload canonicalization
  decryptor.py       # data.enc 解密、安全解包
  activation.py      # 激活元数据读写
```

### 10.2 核心 API

建议提供：

```python
def verify_license_file(path: Path) -> LicensePayload:
    ...

def activate(license_path: Path, secret: str, data_enc: Path, output_dir: Path) -> ActivationResult:
    ...

def is_activated(data_enc: Path, output_dir: Path) -> bool:
    ...
```

### 10.3 激活 UI

首次启动时：

- 如果未激活，显示激活窗口。
- 用户选择 license 文件。
- 用户输入 license secret/token。
- 显示明确错误：
  - 授权文件格式错误。
  - 授权签名无效。
  - 授权已过期。
  - 授权与当前 data 包不匹配。
  - 解密失败。
  - 解包失败。

CLI 场景建议支持：

```bash
ard activate --license license.ard.json --secret "..."
```

## 11. 依赖

`pyproject.toml`：

```toml
dependencies = [
    "cryptography>=41.0",
]
```

当前项目已经有 Python 3.10+ 要求，`cryptography` 可覆盖：

- Ed25519。
- AES-GCM。
- scrypt。

## 12. 测试计划

### 12.1 单元测试

应覆盖：

- 完整签名 license 验签成功。
- payload 被篡改后验签失败。
- signature 被篡改后验签失败。
- data_hash 不匹配时激活失败。
- license 过期时激活失败。
- secret 错误时解 CEK 失败。
- `data.enc` 被篡改后 AES-GCM 解密失败。
- 安全解包拒绝 `../evil`。
- 安全解包拒绝绝对路径。
- 安全解包拒绝 symlink/hardlink。

### 12.2 集成测试

应覆盖：

1. 临时 `data/`。
2. 构建 `data.enc`。
3. 签发测试 license。
4. 调用 `activate(...)`。
5. 校验输出 `data/` 内容一致。
6. 校验 activation metadata 写入。
7. 再次启动时 `is_activated(...)` 返回 true。

### 12.3 打包测试

应覆盖：

- 安装包中不存在明文 `data/`。
- 安装包中不存在私钥。
- 安装包中存在 `data.enc`。
- 安装包中存在公钥。
- ZIP、官网安装包、winget 安装包的激活流程一致。

## 13. 验收标准

方案实现后，必须满足：

- 原始 `data/` 不进入安装包。
- 私钥不进入仓库。
- 私钥不进入安装包。
- `data.enc` 使用随机 CEK 加密，不从短授权码直接派生。
- license 使用完整 Ed25519 签名，不截断签名。
- 客户端能校验 license 与 `data.enc` 的 hash 绑定关系。
- 解包过程有路径逃逸防护。
- 激活元数据不是单个可伪造 `.activated` 文件。
- 同一个安装包可通过不同 license 授权给不同客户。
- 错误提示能区分授权无效、数据包不匹配、解密失败、解包失败。

## 14. 迁移步骤

建议按以下顺序实施：

1. 确认采用“离线单包 + license 文件”模型。
2. 新增 `ai_gen_reimbursement_docs/licensing/`，避免与现有 `auth.py` 冲突。
3. 实现 canonical JSON + Ed25519 完整签名验签。
4. 实现 `data.enc` 构建脚本，使用随机 CEK。
5. 实现 license 签发脚本，输出 license 文件。
6. 实现客户端激活与安全解包。
7. 补齐单元测试和集成测试。
8. 调整 PyInstaller/Inno Setup/ZIP 打包配置，排除明文 `data/`。
9. 编写用户激活说明。
10. 再评估是否需要机器绑定或联网激活。

## 15. 可选增强

### 15.1 机器绑定

如果需要限制 license 被复制，可以在 license 中加入机器指纹。

风险：

- Windows 用户换机器、重装系统、换硬件会造成支持成本。
- 机器指纹容易误伤合法用户。

建议：

- 第一版不做强机器绑定。
- 如需绑定，先实现“可重新签发”的客服流程。

### 15.2 联网激活

如果后续需要撤销、统计、限制激活次数，可增加授权服务器。

能力：

- license 撤销。
- 激活次数限制。
- 客户状态管理。
- 短期 token。

代价：

- 需要服务器运维。
- 离线客户体验变差。

### 15.3 不落盘明文 data

可以考虑运行时按需解密到临时目录，退出后清理。

代价：

- 性能更差。
- 代码改动更大。
- 文件路径依赖更多。

建议：

- 第一版仍解密到应用数据目录。
- 明确这不是强 DRM。

## 16. 原方案需要删除或改写的点

以下原方案内容不应继续采用：

- `ARD-{4位随机}-{8位签名}` 短码作为核心安全凭据。
- `sig.hex()[:8]` 截断 Ed25519 签名。
- 使用截断签名调用 `pk.verify(...)`。
- 从短授权码直接派生 `AES` 密钥。
- 只用 `data/.activated` 判断是否已授权。
- 直接 `tar.extractall(output_dir)`。
- 新建 `ai_gen_reimbursement_docs/auth/__init__.py`。

这些点应在旧文档中标注为已废弃，或用本 v2 方案替代。
