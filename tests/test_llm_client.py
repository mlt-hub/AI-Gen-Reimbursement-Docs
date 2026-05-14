"""LLM 公共客户端单元测试 —— 使用 mock 验证 API 调用和重试逻辑。"""
import pytest
from unittest.mock import patch, MagicMock

from ai_gen_reimbursement_docs.llm_client import call_llm, _extract_text, _extract_thinking
from ai_gen_reimbursement_docs.exceptions import AIError


class TestExtractText:
    def test_extracts_text_block(self):
        block = MagicMock()
        block.text = "COSMIC 分析结果..."
        assert _extract_text([block]) == "COSMIC 分析结果..."

    def test_skips_non_text_blocks(self):
        thinking = MagicMock(spec=[])  # 无 text 属性
        text_block = MagicMock()
        text_block.text = "响应文本"
        assert _extract_text([thinking, text_block]) == "响应文本"

    def test_empty_blocks(self):
        assert _extract_text([]) == ""


class TestExtractThinking:
    def test_extracts_thinking_block(self):
        block = MagicMock()
        block.type = "thinking"
        block.thinking = "分析中..."
        assert _extract_thinking([block]) == "分析中..."

    def test_empty_when_no_thinking(self):
        text_block = MagicMock()
        text_block.type = "text"
        assert _extract_thinking([text_block]) == ""


class TestCallLLM:
    @patch("anthropic.Anthropic")
    def test_successful_call(self, mock_client_class):
        """模拟成功调用。"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_text = MagicMock()
        mock_text.text = "COSMIC 拆分结果..."
        mock_response = MagicMock()
        mock_response.content = [mock_text]
        mock_client.messages.create.return_value = mock_response

        result = call_llm(
            prompt="分析以下需求...",
            system="你是 COSMIC 分析师",
            api_key="test-key",
            tag="test",
        )
        assert "COSMIC 拆分结果" in result
        mock_client.messages.create.assert_called_once()

    @patch("anthropic.Anthropic")
    def test_retry_on_transient_failure(self, mock_client_class):
        """前两次失败，第三次成功。"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_text = MagicMock()
        mock_text.text = "最终成功"
        mock_response = MagicMock()
        mock_response.content = [mock_text]

        mock_client.messages.create.side_effect = [
            Exception("网络超时"),
            Exception("服务不可用"),
            mock_response,
        ]

        result = call_llm(
            prompt="测试重试",
            api_key="test-key",
            tag="retry-test",
            save_logs=False,
        )
        assert "最终成功" in result
        assert mock_client.messages.create.call_count == 3

    @patch("anthropic.Anthropic")
    def test_raises_ai_error_after_all_retries(self, mock_client_class):
        """全部重试耗尽后抛出 AIError。"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("持续失败")

        with pytest.raises(AIError, match="持续失败"):
            call_llm(
                prompt="测试",
                api_key="test-key",
                tag="fail-test",
                save_logs=False,
            )
        assert mock_client.messages.create.call_count == 3

    @patch("anthropic.Anthropic")
    def test_passes_temperature(self, mock_client_class):
        """验证 temperature 参数传递到 API。"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_text = MagicMock()
        mock_text.text = "OK"
        mock_response = MagicMock()
        mock_response.content = [mock_text]
        mock_client.messages.create.return_value = mock_response

        call_llm(prompt="test", api_key="k", temperature=0.7, save_logs=False)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["temperature"] == 0.7

    @patch("anthropic.Anthropic")
    def test_no_temperature_when_none(self, mock_client_class):
        """不传 temperature 时不应出现在 API 参数中。"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_text = MagicMock()
        mock_text.text = "OK"
        mock_response = MagicMock()
        mock_response.content = [mock_text]
        mock_client.messages.create.return_value = mock_response

        call_llm(prompt="test", api_key="k", save_logs=False)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert "temperature" not in call_kwargs

    @patch("anthropic.Anthropic")
    def test_raises_ai_error_without_api_key(self, mock_client_class):
        """无 API Key 时抛出 AIError（不经重试）。"""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(AIError, match="未配置 API Key"):
                call_llm(prompt="test", api_key="", save_logs=False)
