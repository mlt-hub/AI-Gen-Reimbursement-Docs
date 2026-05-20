# 更新日志

## v5.0.1

### 新增

- 零参数模式：双击 `ard.exe` 自动搜索当前目录功能清单 xlsx，识别规范文件后自动执行全流程
- Web UI（`ard --web`）：FastAPI 服务端 + 单页面前端，支持本机模式和远程服务模式
- 提示词调试器（`/prompt-debug`）：系统提示词 + 用户提示词输入，显示 AI 思考过程和返回结果
- AI 交互查看：Web UI 任务完成后可查看 AI prompts 和 responses 详细记录
- 思考过程显示：`call_llm()` 支持 `return_thinking` 参数，调试页面展示 AI 推理过程
- 自动读取工单标题：不指定 `--project-name` 时自动从 xlsx 元数据读取，作为输出文件夹名

### 变更

- 项目重命名：`cosmic` → `ard`，CLI 命令改为 `ard`
- 产物输出结构调整：FPA 放置根目录，COSMIC/需求清单/需求说明书归入 `cosmic文档/` 子目录
- FPA 判定原则仅从输出模板附录读取，移除元数据回退逻辑

### 修复

- exe 入口点 `main.py` 未调用 `main()`，导致双击无任何输出
- exe 模式提示音路径解析失败
- exe 模式 `--web` 无法启动（缺少 fastapi/uvicorn 依赖、web_app 未分发）
- 零参数模式 `sys.exit(0)` 跳过 exe 暂停提示
- SSE 日志隔离 logger 级别未设置导致日志过滤丢失

## v3.0.0

- 初始发布
- 支持 docx 解析、AI 生成 COSMIC 拆分、Excel 输出
- 一键全流程、分阶段运行、批量处理
- 模糊匹配检测、数据校验与警告标注
- 配置文件分离（AI 配置 / 业务规则）
