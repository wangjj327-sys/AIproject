"""玩家代理模块 - 抽象基类"""

from abc import ABC, abstractmethod
from typing import Optional
from engine.game_state import Observation, PublicState


class BaseAgent(ABC):
    """
    游戏A玩家代理的抽象基类。

    所有代理（人类、随机、贪心、LLM）都继承此类，
    实现 decide() 方法。

    Attributes:
        player_id: 玩家标识（"player_1" 或 "player_2"）
        name: 代理名称（用于显示和统计）
    """

    def __init__(self, player_id: str = "player_1", name: Optional[str] = None):
        self.player_id = player_id
        self._name = name or self.__class__.__name__

    @abstractmethod
    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        """
        根据当前观测做出决策。

        Args:
            observation: 代理的私有观测（自己的棋盘、线详情等）
            public_state: 双方都能看到的公共状态

        Returns:
            tuple[int, str]: (报出的数字, 决策理由/说明)
        """
        pass

    def reset(self) -> None:
        """
        重置代理状态（在新一局开始前调用）。

        对于无状态代理（如Random、Greedy），默认无需操作。
        有状态代理（如LLM带历史记录的）应重写此方法。
        """
        pass

    def get_name(self) -> str:
        """返回代理名称"""
        return self._name

    def get_type(self) -> str:
        """返回代理类型"""
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f"{self.get_type()}(name='{self._name}', player_id='{self.player_id}')"
