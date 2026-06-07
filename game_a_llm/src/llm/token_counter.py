"""LLM服务模块 - Token用量统计"""

from dataclasses import dataclass, field
import time


@dataclass
class TokenUsage:
    """单次API调用的token用量"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    timestamp: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "timestamp": self.timestamp,
        }


@dataclass
class TokenStats:
    """累积统计"""
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    usages: list[TokenUsage] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    def record(self, usage: TokenUsage) -> None:
        """记录一次用量"""
        self.total_calls += 1
        self.total_prompt_tokens += usage.prompt_tokens
        self.total_completion_tokens += usage.completion_tokens
        self.usages.append(usage)

    def get_average_tokens_per_call(self) -> float:
        """每次调用的平均token数"""
        if self.total_calls == 0:
            return 0.0
        return self.total_tokens / self.total_calls

    def to_dict(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "average_tokens_per_call": self.get_average_tokens_per_call(),
            "usages": [u.to_dict() for u in self.usages],
        }

    def reset(self) -> None:
        """重置统计"""
        self.total_calls = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.usages = []


# 各大模型每百万token的价格（美元），用于成本估算
PRICING = {
    # OpenAI
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "o4-mini": {"prompt": 1.10, "completion": 4.40},
    # Anthropic
    "claude-opus-4-8": {"prompt": 15.00, "completion": 75.00},
    "claude-sonnet-4-6": {"prompt": 3.00, "completion": 15.00},
    "claude-haiku-4-5": {"prompt": 0.80, "completion": 4.00},
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    估算API调用成本（美元）。

    Args:
        model: 模型名称
        prompt_tokens: 输入token数
        completion_tokens: 输出token数

    Returns:
        float: 估算成本（美元）
    """
    if model not in PRICING:
        return 0.0

    pricing = PRICING[model]
    cost = (
        prompt_tokens / 1_000_000 * pricing["prompt"]
        + completion_tokens / 1_000_000 * pricing["completion"]
    )
    return round(cost, 6)
