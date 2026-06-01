# Data 目录保护方案

## 1. 目标

- `data/` 目录下的文件仅授权用户可查看
- 三种分发方式（winget / 官网下载 / ZIP）使用**同一套激活逻辑**
- 安装包不加锁，winget 兼容
- 私钥不进仓库、不进安装包，仅在你手中

---

## 2. 核心原理：Ed25519 签名 + AES 解密

```
┌─────────────────────────────────────────────────────┐
│                    构建阶段（你本地）                    │
│                                                       │
│  data/ ──→ AES加密 ──→ data.enc                       │
│  私钥 ──→ 对 prefix 签名 ──→ 密钥列表                  │
│  公钥 ──→ 写入源码 key.pub                            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    分发阶段                            │
│                                                       │
│  安装包: app.exe + data.enc（无密钥，无公钥泄露风险）     │
│  授权码: ARD-A3F8-A1B2C3D4（另一个渠道发给客户）         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                    首次启动                            │
│                                                       │
│  用户输密钥 → 公钥验签 → 通过 → AES解密data.enc → data/ │
│  后续启动跳过，直接使用 data/                           │
└─────────────────────────────────────────────────────┘
```

---

## 3. 密钥体系

### 3.1 文件结构（你本机，不进仓库）

```
~/.ard-keys/
  private_key.pem      ← Ed25519 私钥（仅你持有）
  public_key.pem       ← 公钥（仓库里的 key.pub 内容）
  keys.txt             ← 已生成的授权码列表（分发给客户后记录）
  generate.py          ← 密钥生成脚本
```

### 3.2 授权码格式

```
ARD-{4位随机}-{8位签名}
例: ARD-A3F8-1A2B3C4D
```

- ARD: 固定前缀
- A3F8: 随机标识（用于区分不同客户/批次）
- 1A2B3C4D: 对前缀 `ARD-A3F8` 的 Ed25519 签名 hex

### 3.3 密钥生成脚本

`~/.ard-keys/generate.py`：

```python
#!/usr/bin/env python3
"""生成授权码"""
import sys
import secrets
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

def generate_keys():
    """生成公私钥对（只需执行一次）"""
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    
    with open("private_key.pem", "wb") as f:
        f.write(sk.private_bytes_raw())
    with open("public_key.pem", "wb") as f:
        f.write(pk.public_bytes_raw())
    print("密钥对已生成: private_key.pem / public_key.pem")

def sign(prefix: str) -> str:
    """对前缀签名，返回签名的 hex"""
    with open("private_key.pem", "rb") as f:
        sk = Ed25519PrivateKey.from_private_bytes(f.read())
    sig = sk.sign(prefix.encode())
    return sig.hex()[:8]  # 取前8位，够用且短

def generate_license() -> str:
    """生成一个授权码"""
    rid = secrets.token_hex(2).upper()  # 4位
    prefix = f"ARD-{rid}"
    sig = sign(prefix)
    return f"{prefix}-{sig}"

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "init":
        generate_keys()
    else:
        # 列出可用授权码
        count = int(sys.argv[1]) if len(sys.argv) > 1 else 1
        for _ in range(count):
            lic = generate_license()
            print(lic)
            with open("keys.txt", "a") as f:
                f.write(lic + "\n")
```

**操作**：

```bash
# 首次：生成公私钥
python generate.py init

# 每次需要授权码时：生成10个
python generate.py 10
# 输出: ARD-A3F8-1B2C3D4
#       ARD-7B12-9E4F5A6C
#       ...
# 同时追加到 keys.txt，记录已分配及其对应的客户
```

---

## 4. 源码集成（进仓库）

### 4.1 依赖

`pyproject.toml` 的 `dependencies` 需包含：

```toml
dependencies = [
    "cryptography>=41.0",
]
```

### 4.2 公钥文件（进仓库）

把公钥写入源码目录下的一个文件，例如 `ai_gen_reimbursement_docs/auth/key.pub`。

```bash
cp ~/.ard-keys/public_key.pem ai_gen_reimbursement_docs/auth/key.pub
```

### 4.3 校验模块

新建 `ai_gen_reimbursement_docs/auth/__init__.py`：

```python
"""授权校验模块"""
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_public_key = None

def _load_public_key() -> Ed25519PublicKey:
    global _public_key
    if _public_key is None:
        key_path = Path(__file__).parent / "key.pub"
        _public_key = Ed25519PublicKey.from_public_bytes(key_path.read_bytes())
    return _public_key

def validate_license(license_key: str) -> bool:
    """校验授权码是否有效。
    格式: ARD-XXXX-XXXXXXXX
    """
    try:
        parts = license_key.strip().split("-")
        if len(parts) != 3 or parts[0] != "ARD":
            return False
        prefix = f"{parts[0]}-{parts[1]}"
        sig_hex = parts[2]
        sig = bytes.fromhex(sig_hex)
        pk = _load_public_key()
        pk.verify(sig, prefix.encode())
        return True
    except Exception:
        return False

def is_activated() -> bool:
    """检查 data 目录是否已解密"""
    data_dir = Path(__file__).parent.parent.parent / "data"
    indicator = data_dir / ".activated"
    return indicator.exists()

def mark_activated() -> None:
    data_dir = Path(__file__).parent.parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / ".activated").touch()

def decrypt_data(enc_path: Path, output_dir: Path, license_key: str) -> bool:
    """解密 data.enc 到 data/。
    使用 AES-GCM，密钥从授权码派生（scrypt 防暴力）。
    
    加密参数：写死在代码里（非秘密，仅用于密钥派生）
      - salt: 硬编码16字节盐
      - scrypt N: 2^14
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.backends import default_backend

    if not enc_path.exists():
        raise FileNotFoundError(f"未找到加密数据包: {enc_path}")

    data = enc_path.read_bytes()
    salt = data[:16]
    nonce = data[16:28]
    ciphertext = data[28:]

    # 从授权码派生对称密钥
    license_bytes = license_key.strip().encode()
    # 盐 = 硬编码 + 文件头 salt 混合，增加唯一性
    fixed_salt = b"ard-data-v1-salt"
    combined_salt = fixed_salt + salt
    
    aes_key = Scrypt(
        salt=combined_salt,
        length=32,
        n=2**14,
        r=8,
        p=1,
        backend=default_backend(),
    ).derive(license_bytes)

    aesgcm = AESGCM(aes_key)
    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        output_dir.mkdir(parents=True, exist_ok=True)
        # plaintext 是 tar，解压到 output_dir
        import tarfile, io
        with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:") as tar:
            tar.extractall(output_dir)
        mark_activated()
        return True
    except Exception:
        return False
```

### 4.4 加密脚本（你本机，不进仓库）

`~/.ard-keys/encrypt_data.py`：

```python
#!/usr/bin/env python3
"""将 data/ 目录加密为 data.enc"""
import os
import secrets
import io
import tarfile
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.backends import default_backend

def encrypt(data_dir: Path, output: Path, license_key: str) -> None:
    """加密 data/ → data.enc"""
    # 打包 data/ 为 tar
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:") as tar:
        tar.add(data_dir, arcname="data")
    tar_bytes = tar_buf.getvalue()

    # 从授权码派生 AES 密钥
    salt = secrets.token_bytes(16)
    fixed_salt = b"ard-data-v1-salt"
    combined_salt = fixed_salt + salt
    license_bytes = license_key.strip().encode()
    aes_key = Scrypt(
        salt=combined_salt,
        length=32,
        n=2**14, r=8, p=1,
        backend=default_backend(),
    ).derive(license_bytes)

    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, tar_bytes, None)

    output.write_bytes(salt + nonce + ciphertext)
    print(f"加密完成: {output} ({len(ciphertext)} bytes)")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python encrypt_data.py <data目录> <授权码> [输出文件名]")
        sys.exit(1)
    data_dir = Path(sys.argv[1])
    license_key = sys.argv[2]
    output = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("data.enc")
    encrypt(data_dir, output, license_key)
```

---

## 5. 构建流程

```bash
# 1. 生成一个授权码（给本次分发的客户）
python ~/.ard-keys/generate.py 1
# 输出: ARD-A3F8-1B2C3D4

# 2. 用该授权码加密 data/
python ~/.ard-keys/encrypt_data.py ./data "ARD-A3F8-1B2C3D4" ./data.enc

# 3. 打包安装程序（Inno Setup / PyInstaller）
#    包含: app.exe + data.enc
#    不包含: data/（原始文件不打包）
#    不包含: private_key.pem

# 4. 把授权码 ARD-A3F8-1B2C3D4 通过另一个渠道发给客户
```

**关键**：每个客户/每次分发用**不同的授权码**，因为 AES 密钥由授权码派生，不同授权码加密的 `data.enc` 不同。

---

## 6. 首次启动流程

```
启动 app
  ↓
检查 data/.activated 是否存在？
  ├─ 是 → 已激活，正常启动
  └─ 否 → 弹出激活窗口
             ↓
          用户输入授权码
             ↓
          validate_license() 验签
             ├─ 失败 → "无效授权码"
             └─ 通过 → decrypt_data(data.enc, data/, license_key)
                         ├─ 解密成功 → mark_activated() → 正常启动
                         └─ 解密失败 → "解密失败，请联系支持"
```

---

## 7. 分发方式对比

| | winget | 官网下载 | ZIP 分发 |
|------|------|------|------|
| 安装 | 无阻碍 | 无阻碍 | 解压即可 |
| 首次启动 | 弹窗输码 | 弹窗输码 | 弹窗输码 |
| data 保护 | data.enc 加密 | data.enc 加密 | data.enc 加密 |
| 授权码发放 | 另一渠道 | 另一渠道 | 另一渠道 |

三种方式**应用层逻辑完全一致**，同一套代码。

---

## 8. 安全边界

| 资产 | 位置 | 泄露后果 | 防护 |
|------|------|---------|------|
| 私钥 | `~/.ard-keys/private_key.pem` | 可伪造无限授权码 | 不联网、不进仓库、本机保存 |
| 公钥 | 源码 `key.pub` | 无影响 | 仅能验签 |
| 授权码列表 | `~/.ard-keys/keys.txt` | 未使用的码可被冒用 | 标记已分配/已使用 |
| data 原始文件 | 你的开发机 | 核心资产泄露 | 不进仓库、不进安装包 |
| data.enc | 安装包内 | 暴力破解代价高 | AES-256-GCM + scrypt |
| 硬编码盐值 | 源码 | 仅用于 KDF，不单独构成威胁 | 配合授权码才有意义 |

---

## 9. 文件清单

```
仓库内:
  ai_gen_reimbursement_docs/
    auth/
      __init__.py       ← 校验 + 解密模块
      key.pub           ← Ed25519 公钥
    ...

你本机（不进仓库）:
  ~/.ard-keys/
    private_key.pem     ← 私钥
    public_key.pem      ← 公钥（与仓库中 key.pub 一致）
    generate.py         ← 授权码生成脚本
    encrypt_data.py     ← 数据加密脚本
    keys.txt            ← 授权码分发记录

安装包内:
  app.exe
  data.enc             ← 加密后的数据包
  key.pub              ← 公钥（校验用）
```

---

## 10. 依赖

`pyproject.toml` 新增：

```toml
dependencies = [
    "cryptography>=41.0",   # Ed25519 + AES-GCM + scrypt
]
```
