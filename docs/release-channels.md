# 发布方式

## 1. CLI（现有）

```bash
ard --from-excel 功能清单.xlsx --gen-all
ard --from-excel 功能清单.xlsx --gen-fpa
```

- 分布式：GitHub Release 下载 `cosmic_v*.zip`，解压即用，无需 Python
- 适用：个人开发者

---

## 2. Web UI（方案已定稿）

见 [web-ui-design.md](web-ui-design.md)

- 浏览器上传文件 → 配置参数 → 实时日志 → 下载产物
- 单文件部署，多人可同时使用
- 适用：团队内部

---

## 3. PyPI 包 `pip install` ★

```bash
pip install ai-gen-reimbursement-docs
ard --from-excel 功能清单.xlsx --gen-all
```

- `pyproject.toml` 已就绪，只需 `twine upload dist/*`
- 优势：Python 生态标准入口，自动处理依赖
- 适用：Python 用户

---

## 4. Docker 镜像 ★

```dockerfile
FROM python:3.11-slim
RUN pip install ai-gen-reimbursement-docs
ENTRYPOINT ["ard"]
```

```bash
docker run -v $(pwd):/data mlt-hub/ard --from-excel /data/功能清单.xlsx --gen-all
```

- 零环境依赖，启动即用
- 可配合 Web UI 一键部署
- 适用：服务器部署、不想装 Python 的用户

---

## 5. Watch 监控模式（建议新增）

```bash
ard --watch ./input/    # 监控目录，有新 Excel 自动处理
ard --watch ./input/ --mode gen-fpa
```

- 用户把 Excel 拖到共享文件夹，过几分钟产物出现在 `./output/`
- 对非技术用户最友好
- 实现：`watchdog` 库监听目录 + 现有处理逻辑

---

## 6. GitHub Action

```yaml
# .github/workflows/ard.yml
- uses: mlt-hub/ard-action@v5
  with:
    source: 功能清单.xlsx
    mode: gen-all
```

- 提交 Excel 到仓库自动触发，产物自动提交回仓库
- 适合需要版本留痕的正式项目

---

## 对比

| 方式 | 用户门槛 | 部署复杂度 | 投入 | 适用场景 |
|------|---------|-----------|------|---------|
| CLI | 中 | 低 | 已完成 | 个人开发者 |
| Web UI | 低 | 中 | 方案已定 | 团队内部 |
| PyPI | 中 | 无 | 极低 | Python 用户 |
| Docker | 低 | 低 | 低 | 一键部署 |
| Watch | 最低 | 低 | 中 | 非技术用户 |
| GitHub Action | 高 | 无 | 中 | CI/CD |

## 优先级建议

1. **PyPI** — 投入最低（`twine upload` 即可），扩大用户面
2. **Web UI** — 方案已有，按 [web-ui-design.md](web-ui-design.md) 实现
3. **Docker** — 基于 PyPI 包构建，几行 Dockerfile
4. **Watch 模式** — 需要新增开发
5. **GitHub Action** — 需要额外开发和维护
