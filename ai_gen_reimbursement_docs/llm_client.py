"""LLM 调用公共模块 —— 统一封装 Anthropic API 调用、重试和日志记录。

消除 cosmic_ai、module_utils、gen_xlsx、gen_spec、main 五处的重复实现。
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional

from ai_gen_reimbursement_docs.config_utils import load_max_tokens, load_llm_timeout
from ai_gen_reimbursement_docs.exceptions import AIError

logger = logging.getLogger(__name__)

# 最大重试次数
_MAX_RETRIES = 3
# 重试延迟基数（秒），按 attempt 倍数递增
_RETRY_DELAY_BASE = 2


def call_llm(
    prompt: str,
    *,
    system: str = "",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    tag: str = "",
    save_logs: bool = True,
    log_dir: Optional[str] = None,
    return_thinking: bool = False,
) -> str | tuple[str, str]:
    """调用 LLM，自动处理重试和日志记录。

    Args:
        prompt: 用户消息内容
        system: 系统提示词（可选）
        api_key: API 密钥，不传则从环境变量 ANTHROPIC_API_KEY 读取
        model: 模型名，不传则从配置加载
        base_url: 自定义 API 地址，不传则从环境变量 ANTHROPIC_BASE_URL 读取
        max_tokens: 最大 token 数，不传则从配置加载
        temperature: 采样温度（0.0-1.0），不传使用 API 默认值
        tag: 日志标签，用于区分不同调用场景
        save_logs: 是否保存 prompt/response 到日志文件
        log_dir: 日志保存目录，不传则使用默认的 log/ 目录

    Returns:
        LLM 响应的文本内容

    Raises:
        AIError: 所有重试耗尽后仍失败
    """
    import anthropic

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise AIError("未配置 API Key，请设置 ANTHROPIC_API_KEY 环境变量或传入 --api-key")

    base_url = base_url or os.environ.get("ANTHROPIC_BASE_URL", "")
    model = model or os.environ.get("ANTHROPIC_MODEL", "")
    if not model:
        raise AIError("未配置模型名，请在 ~/.ai-gen-reimbursement-docs/.env 中设置 ANTHROPIC_MODEL")
    max_tokens = max_tokens or load_max_tokens()

    client_kwargs: dict = {"api_key": api_key, "timeout": load_llm_timeout()}
    if base_url:
        client_kwargs["base_url"] = base_url

    # 保存 prompt 日志
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if save_logs:
        _save_prompt_log(prompt, system, model, tag, timestamp, log_dir)

    last_error = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            client = anthropic.Anthropic(**client_kwargs)
            create_kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperature is not None:
                create_kwargs["temperature"] = temperature
            try:
                from web_app.server import check_cancelled as _cc
                _cc()
            except ImportError:
                pass
            msg = client.messages.create(**create_kwargs)
            resp_text = _extract_text(msg.content)
            thinking_text = _extract_thinking(msg.content)

            if save_logs:
                _save_response_log(resp_text, thinking_text, model, tag, timestamp, log_dir)
                if thinking_text:
                    _save_thinking_log(thinking_text, model, tag, timestamp, log_dir)

            logger.debug("LLM 调用完成 [%s] 长度: %d 字", tag, len(resp_text))
            if return_thinking:
                return resp_text, thinking_text
            return resp_text

        except Exception as e:
            from ai_gen_reimbursement_docs.exceptions import CancelledError
            if isinstance(e, CancelledError):
                raise
            last_error = e
            logger.warning("LLM 调用失败 [%s]（第 %d/%d 次）: %s", tag, attempt, _MAX_RETRIES, e)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY_BASE * attempt)

    raise AIError(
        f"AI 调用失败，已重试 {_MAX_RETRIES} 次仍无法完成。请检查网络连接、API Key 和端点配置。",
        attempt=_MAX_RETRIES,
        model=model,
    ) from last_error


def strip_markdown_code_block(text: str) -> str:
    """去除 AI 响应中的 markdown 代码块标记（```json ... ```）。"""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1]
        if "```" in text:
            text = text.split("```")[0]
    elif "```" in text:
        text = text.split("```")[1]
        if "```" in text:
            text = text.split("```")[0]
    return text.strip()


def _extract_text(content_blocks: list) -> str:
    """从 Anthropic 响应中提取文本（跳过 ThinkingBlock）。"""
    for block in content_blocks:
        if hasattr(block, "text"):
            return block.text.strip()
    return ""


def _extract_thinking(content_blocks: list) -> str:
    """从 Anthropic 响应中提取思考过程。"""
    parts = []
    for block in content_blocks:
        block_type = getattr(block, "type", "") or type(block).__name__
        if "thinking" in block_type.lower() and hasattr(block, "thinking"):
            parts.append(block.thinking)
    return "\n\n".join(parts) if parts else ""


def _resolve_log_dir(sub_dir: str, custom_dir: Optional[str] = None) -> str:
    """解析日志目录路径。"""
    if custom_dir:
        return custom_dir
    base = os.environ.get("AI_REIMBURSEMENT_LOG_DIR", "") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "log"
    )
    return os.path.join(base, sub_dir)


def _save_prompt_log(
    prompt: str,
    system: str,
    model: str,
    tag: str,
    timestamp: str,
    log_dir: Optional[str] = None,
) -> None:
    """保存 prompt 到日志文件。"""
    try:
        dir_path = _resolve_log_dir("ai_prompts", log_dir)
        os.makedirs(dir_path, exist_ok=True)
        tag_str = f"_{tag}" if tag else ""
        filename = f"{timestamp}{tag_str}_prompt.txt"
        filepath = os.path.join(dir_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# AI Prompt: {tag}\n")
            f.write(f"# Model: {model}\n")
            f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            if system:
                f.write(f"[system]\n{system}\n\n")
            f.write(f"[user]\n{prompt}\n")
    except Exception as e:
        logger.debug("保存 prompt 日志失败: %s", e)


def _save_response_log(
    text: str,
    reasoning: str,
    model: str,
    tag: str,
    timestamp: str,
    log_dir: Optional[str] = None,
) -> None:
    """保存 response 到日志文件。"""
    try:
        dir_path = _resolve_log_dir("ai_responses", log_dir)
        os.makedirs(dir_path, exist_ok=True)
        tag_str = f"_{tag}" if tag else ""
        filename = f"{timestamp}{tag_str}_response.txt"
        filepath = os.path.join(dir_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# AI Response: {tag}\n")
            f.write(f"# Model: {model}\n")
            f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            if reasoning:
                f.write(f"[reasoning]\n{reasoning}\n\n")
            f.write(text)
    except Exception as e:
        logger.debug("保存 response 日志失败: %s", e)


def _save_thinking_log(
    thinking: str,
    model: str,
    tag: str,
    timestamp: str,
    log_dir: Optional[str] = None,
) -> None:
    """保存 AI 思考过程到独立日志文件。"""
    try:
        dir_path = _resolve_log_dir("ai_thinking", log_dir)
        os.makedirs(dir_path, exist_ok=True)
        tag_str = f"_{tag}" if tag else ""
        filename = f"{timestamp}{tag_str}_thinking.txt"
        filepath = os.path.join(dir_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# AI Thinking: {tag}\n")
            f.write(f"# Model: {model}\n")
            f.write(f"# Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(thinking)
    except Exception as e:
        logger.debug("保存 thinking 日志失败: %s", e)
