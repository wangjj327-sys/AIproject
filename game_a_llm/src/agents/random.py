"""随机代理——从剩余合法数字中均匀随机选择"""

import random
from engine.game_state import Observation, PublicState
from .base import BaseAgent


class RandomAgent(BaseAgent):
    """
    随机策略代理。

    从所有合法可选数字中均匀随机选择一个。
    用作评估其他代理表现的基准线（LLM应远优于随机）。
    """

    def __init__(self, player_id: str = "player_1", seed: int = None, name: str = None):
        super().__init__(player_id=player_id, name=name or "RandomAgent")
        self._rng = random.Random(seed)

    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        """
        随机选择一个合法数字。

        Args:
            observation: 私有观测
            public_state: 公共状态

        Returns:
            (数字, 理由)
        """
        legal = sorted(list(observation.legal_numbers))
        number = self._rng.choice(legal)
        return number, f"随机选择了数字 {number}"
