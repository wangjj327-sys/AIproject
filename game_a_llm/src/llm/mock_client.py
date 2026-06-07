"""LLM服务模块 - 模拟客户端（用于测试）

模拟LLM API响应，使测试不需要真实的API密钥。
"""

import json
import random
from .client import LLMClient


class MockLLMClient(LLMClient):
    """
    模拟LLM客户端，用于测试。

    返回预定义的或随机生成的合法响应。
    可以通过responses参数预设响应序列。

    用法:
        # 预设响应
        client = MockLLMClient(responses=[
            {"number": 7, "reasoning": "测试响应"},
            {"number": 14, "reasoning": "第二个响应"},
        ])

        # 自动生成合法响应
        client = MockLLMClient(model="mock", auto_mode=True)
    """

    def __init__(
        self,
        model: str = "mock-model",
        responses: list[dict] = None,
        auto_mode: bool = True,
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
        self._responses = responses or []
        self._response_index = 0
        self.auto_mode = auto_mode
        self._call_history: list[list[dict]] = []

    def set_responses(self, responses: list[dict]) -> None:
        """预设响应序列"""
        self._responses = responses
        self._response_index = 0

    def add_response(self, response: dict) -> None:
        """添加单个预设响应"""
        self._responses.append(response)

    async def chat(self, messages: list[dict], **kwargs) -> str:
        """返回文本响应"""
        self._call_history.append(messages)
        response = self._get_response()
        return json.dumps(response, ensure_ascii=False)

    async def chat_with_json(self, messages: list[dict], **kwargs) -> dict:
        """返回结构化响应"""
        self._call_history.append(messages)
        return self._get_response()

    def _get_response(self) -> dict:
        """获取下一个响应"""
        if self._response_index < len(self._responses):
            response = self._responses[self._response_index]
            self._response_index += 1
            return response

        if self.auto_mode:
            # 自动生成一个合法响应
            # 从用户消息中提取called_numbers（如果有的话）
            number = random.randint(1, 25)
            return {
                "number": number,
                "reasoning": f"模拟自动决策: 选择数字 {number}",
            }

        return {"number": 1, "reasoning": "无预设响应"}

    def count_tokens(self, text: str) -> int:
        """粗略token估算"""
        return len(text) // 4

    def get_model_name(self) -> str:
        return self.model

    def get_provider_name(self) -> str:
        return "mock"

    def get_call_count(self) -> int:
        """获取调用次数"""
        return len(self._call_history)

    def get_last_messages(self) -> list[dict]:
        """获取最后一次调用的消息"""
        return self._call_history[-1] if self._call_history else []

    def reset(self) -> None:
        """重置状态"""
        self._response_index = 0
        self._call_history = []
