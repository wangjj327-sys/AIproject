"""LLM服务模块 - Anthropic适配器

使用Anthropic SDK调用Claude系列模型。
使用Tool Use实现结构化输出。
"""

import json
import os
from typing import Optional

from .client import LLMClient


# 用于结构化输出的Tool定义
DECISION_TOOL = {
    "name": "make_decision",
    "description": "做出游戏决策：选择下一个要报的数字",
    "input_schema": {
        "type": "object",
        "properties": {
            "number": {
                "type": "integer",
                "description": "选择报出的数字，必须是1-25之间的整数",
                "minimum": 1,
                "maximum": 25,
            },
            "reasoning": {
                "type": "string",
                "description": "决策的推理过程：为什么选择这个数字",
            },
        },
        "required": ["number", "reasoning"],
    },
}


class AnthropicClient(LLMClient):
    """
    Anthropic API客户端适配器。

    支持模型: claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5等。
    使用Tool Use功能确保结构化输出。

    用法:
        client = AnthropicClient(model="claude-sonnet-4-6", api_key="sk-ant-...")
        response = await client.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-6",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
        timeout: int = 30,
    ):
        super().__init__(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def _get_client(self):
        """延迟初始化Anthropic客户端"""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise ImportError(
                    "请安装Anthropic SDK: pip install anthropic"
                )
            if not self._api_key:
                raise ValueError(
                    "Anthropic API密钥未设置。请设置环境变量 ANTHROPIC_API_KEY "
                    "或在创建客户端时传入 api_key 参数。"
                )
            self._client = AsyncAnthropic(
                api_key=self._api_key,
                timeout=self.timeout,
            )
        return self._client

    async def chat(
        self,
        messages: list[dict],
        **kwargs,
    ) -> str:
        """发送对话请求"""
        client = self._get_client()

        # 提取系统消息（Anthropic API的system是单独参数）
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        response = await client.messages.create(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        # 提取文本内容
        for block in response.content:
            if block.type == "text":
                return block.text

        return ""

    async def chat_with_json(
        self,
        messages: list[dict],
        **kwargs,
    ) -> dict:
        """
        使用Tool Use确保结构化输出。

        通过要求模型调用 make_decision 工具，
        获得包含 number 和 reasoning 的结构化JSON。
        """
        client = self._get_client()

        # 提取系统消息
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(msg)

        response = await client.messages.create(
            model=self.model,
            system=system_msg,
            messages=chat_messages,
            tools=[DECISION_TOOL],
            tool_choice={"type": "tool", "name": "make_decision"},
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        # 提取tool_use块
        for block in response.content:
            if block.type == "tool_use":
                return block.input

        # 降级：尝试从文本中提取JSON
        for block in response.content:
            if block.type == "text":
                return self._extract_json(block.text)

        return {"number": 1, "reasoning": "无法解析响应"}

    def count_tokens(self, text: str) -> int:
        """估算token数量"""
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key="dummy")
            return client.count_tokens(text)
        except ImportError:
            # 粗略估算
            chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 1.5 + other_chars / 4)

    def get_model_name(self) -> str:
        return self.model

    def get_provider_name(self) -> str:
        return "anthropic"

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取JSON对象（容错处理）"""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"number": 1, "reasoning": f"JSON解析失败，原始响应: {text[:100]}"}
