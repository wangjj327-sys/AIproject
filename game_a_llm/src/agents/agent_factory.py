"""代理工厂——从配置创建代理实例"""

from typing import Optional
from .base import BaseAgent
from .random import RandomAgent
from .greedy import GreedyAgent, AggressiveGreedyAgent, DefensiveGreedyAgent
from .human import HumanAgent


# 已注册的代理类型映射
AGENT_REGISTRY = {
    "random": RandomAgent,
    "greedy": GreedyAgent,
    "aggressive_greedy": AggressiveGreedyAgent,
    "defensive_greedy": DefensiveGreedyAgent,
    "human": HumanAgent,
    # LLM代理将在阶段3注册
}


class AgentFactory:
    """
    代理工厂类。

    根据代理类型字符串创建对应的代理实例。
    支持通过配置文件（YAML）或直接参数创建。

    用法:
        agent = AgentFactory.create("greedy", player_id="player_1")
        agent = AgentFactory.create("random", player_id="player_2", seed=42)
    """

    @staticmethod
    def create(
        agent_type: str,
        player_id: str = "player_1",
        name: Optional[str] = None,
        **kwargs,
    ) -> BaseAgent:
        """
        创建代理实例。

        Args:
            agent_type: 代理类型（"random", "greedy", "human"等）
            player_id: 玩家ID
            name: 代理名称（可选）
            **kwargs: 传递给代理构造函数的额外参数

        Returns:
            BaseAgent: 代理实例

        Raises:
            ValueError: 未知的代理类型
        """
        agent_type_lower = agent_type.lower()

        if agent_type_lower not in AGENT_REGISTRY:
            available = ", ".join(AGENT_REGISTRY.keys())
            raise ValueError(
                f"未知的代理类型: '{agent_type}'。可用类型: {available}"
            )

        agent_class = AGENT_REGISTRY[agent_type_lower]
        return agent_class(player_id=player_id, name=name, **kwargs)

    @staticmethod
    def list_available() -> list[str]:
        """列出所有可用的代理类型"""
        return list(AGENT_REGISTRY.keys())

    @staticmethod
    def register(agent_type: str, agent_class: type) -> None:
        """
        注册新的代理类型。

        Args:
            agent_type: 代理类型名称
            agent_class: 代理类（需继承BaseAgent）
        """
        if not issubclass(agent_class, BaseAgent):
            raise TypeError(f"{agent_class} 必须继承 BaseAgent")
        AGENT_REGISTRY[agent_type.lower()] = agent_class
