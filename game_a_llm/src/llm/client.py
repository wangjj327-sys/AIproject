"""LLM服务模块 - 抽象客户端基类

定义与LLM API交互的统一接口，所有具体实现（OpenAI、Anthropic等）都继承此类。
"""

from abc import ABC, abstractmethod
from typing import Optional


class LLMClient(ABC):
    """
    LLM客户端的抽象基类。

    封装了与不同LLM提供商API的交互细节，
    向上层代理提供统一的调用接口。

    Attributes:
        model: 模型名称（如 "gpt-4o", "claude-sonnet-4-6"）
        temperature: 生成温度参数
        max_tokens: 最大输出token数
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        timeout: int = 30,
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        **kwargs,
    ) -> str:
        """
        发送对话请求，返回文本响应。

        Args:
            messages: 对话消息列表 [{"role": "system"|"user"|"assistant", "content": "..."}]
            **kwargs: 额外的API参数

        Returns:
            str: 模型返回的文本内容
        """
        pass

    @abstractmethod
    async def chat_with_json(
        self,
        messages: list[dict],
        **kwargs,
    ) -> dict:
        """
        发送对话请求，要求模型返回结构化JSON。

        Args:
            messages: 对话消息列表
            **kwargs: 额外的API参数

        Returns:
            dict: 解析后的JSON对象
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        估算文本的token数量。

        Args:
            text: 要估算的文本

        Returns:
            int: 估算的token数
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """返回模型名称"""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """返回提供商名称"""
        pass
