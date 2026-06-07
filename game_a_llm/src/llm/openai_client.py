"""LLM服务模块 - OpenAI适配器

使用OpenAI SDK调用GPT系列模型。
支持JSON Mode确保结构化输出。
"""

import json
import os
from typing import Optional

from .client import LLMClient


class OpenAIClient(LLMClient):
    """
    OpenAI API客户端适配器。

    支持模型: gpt-4o, gpt-4o-mini, o4-mini等。
    使用JSON Mode或response_format保证结构化JSON输出。

    用法:
        client = OpenAIClient(model="gpt-4o", api_key="sk-...")
        response = await client.chat([{"role": "user", "content": "Hello"}])
    """

    def __init__(
        self,
        model: str = "gpt-4o",
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
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None

    def _get_client(self):
        """延迟初始化OpenAI客户端（避免导入时就需要API key）"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise ImportError(
                    "请安装OpenAI SDK: pip install openai"
                )
            if not self._api_key:
                raise ValueError(
                    "OpenAI API密钥未设置。请设置环境变量 OPENAI_API_KEY "
                    "或在创建客户端时传入 api_key 参数。"
                )
            self._client = AsyncOpenAI(
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

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )

        return response.choices[0].message.content or ""

    async def chat_with_json(
        self,
        messages: list[dict],
        **kwargs,
    ) -> dict:
        """
        使用JSON Mode发送请求，确保返回合法JSON。

        注意：使用JSON Mode时，系统提示中必须包含"JSON"字样。
        """
        client = self._get_client()

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试从内容中提取JSON
            return self._extract_json(content)

    def count_tokens(self, text: str) -> int:
        """
        估算token数量。

        使用简单估算：中文约1.5字符/token，英文约4字符/token。
        对于精确计数，建议使用tiktoken库。
        """
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(self.model)
            return len(enc.encode(text))
        except ImportError:
            # 粗略估算
            chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
            other_chars = len(text) - chinese_chars
            return int(chinese_chars / 1.5 + other_chars / 4)

    def get_model_name(self) -> str:
        return self.model

    def get_provider_name(self) -> str:
        return "openai"

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取JSON对象（容错处理）"""
        # 尝试找到第一个{和最后一个}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}
