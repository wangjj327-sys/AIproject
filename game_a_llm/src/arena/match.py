"""对战调度模块 - 单局对战管理"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from engine.game_state import GameState, GamePhase, StepResult
from agents.base import BaseAgent


@dataclass
class MatchResult:
    """
    一局对战的结果摘要。

    Attributes:
        match_id: 对局唯一标识
        agent1_name: 玩家1的代理名称
        agent2_name: 玩家2的代理名称
        agent1_type: 玩家1的代理类型
        agent2_type: 玩家2的代理类型
        winner: 胜者（"player_1" | "player_2" | "draw"）
        winner_name: 胜者代理名称
        total_turns: 总局数
        p1_final_lines: 玩家1最终线数
        p2_final_lines: 玩家2最终线数
        called_numbers: 完整的报数序列
        move_timeline: 每步的详细信息
        duration_seconds: 对局耗时
        first_player: 先手玩家
    """
    match_id: str
    agent1_name: str
    agent2_name: str
    agent1_type: str
    agent2_type: str
    winner: Optional[str]          # "player_1" | "player_2" | None (draw)
    winner_name: Optional[str]
    total_turns: int
    p1_final_lines: int
    p2_final_lines: int
    called_numbers: list[int]
    move_timeline: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    first_player: str = "player_1"

    def to_dict(self) -> dict:
        return {
            "match_id": self.match_id,
            "agent1_name": self.agent1_name,
            "agent2_name": self.agent2_name,
            "agent1_type": self.agent1_type,
            "agent2_type": self.agent2_type,
            "winner": self.winner,
            "winner_name": self.winner_name,
            "total_turns": self.total_turns,
            "p1_final_lines": self.p1_final_lines,
            "p2_final_lines": self.p2_final_lines,
            "called_numbers": self.called_numbers,
            "move_timeline": self.move_timeline,
            "duration_seconds": self.duration_seconds,
            "first_player": self.first_player,
        }


class Match:
    """
    单局对战管理器。

    协调游戏引擎与两个代理之间的交互，运行完整的一局游戏。

    用法:
        game = GameState()
        game.reset()
        agent1 = RandomAgent("player_1", seed=42)
        agent2 = GreedyAgent("player_2")

        match = Match(game, agent1, agent2)
        result = match.run()

        print(f"胜者: {result.winner_name}")
        print(f"回合数: {result.total_turns}")
    """

    def __init__(
        self,
        game: GameState,
        agent1: BaseAgent,
        agent2: BaseAgent,
        verbose: bool = False,
    ):
        """
        初始化对战。

        Args:
            game: 已初始化的游戏状态（需已调用reset()）
            agent1: 玩家1的代理
            agent2: 玩家2的代理
            verbose: 是否打印每步的详细信息
        """
        self.game = game
        self.agent1 = agent1
        self.agent2 = agent2
        self.verbose = verbose

        # 确保代理的player_id与游戏一致
        self.agent1.player_id = "player_1"
        self.agent2.player_id = "player_2"

        self._agents = {
            "player_1": self.agent1,
            "player_2": self.agent2,
        }

    def run(self) -> MatchResult:
        """
        运行完整的一局游戏直到结束。

        Returns:
            MatchResult: 对局结果摘要
        """
        match_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # 重置代理状态
        self.agent1.reset()
        self.agent2.reset()

        move_timeline = []

        # 游戏主循环
        while not self.game.is_terminal():
            current_player = self.game.current_player
            agent = self._agents[current_player]

            # 获取观测
            obs = self.game.get_observation(current_player)
            pub = self.game.get_public_state()

            # 代理决策
            decision_start = time.time()
            try:
                number, reasoning = agent.decide(obs, pub)
            except Exception as e:
                # 代理出错时，降级为随机选择
                print(f"[警告] 代理 {agent.get_name()} 决策失败: {e}，随机选一个")
                legal = sorted(list(obs.legal_numbers))
                number = legal[0]
                reasoning = f"降级随机选择（原错误: {e}）"

            decision_time = time.time() - decision_start

            # 执行行动
            try:
                result = self.game.step(current_player, number)
            except Exception as e:
                # 理论上不应该到这里（代理返回了非法数字）
                print(f"[错误] 代理 {agent.get_name()} 返回了非法数字 {number}: {e}")
                # 降级：随机选一个合法数字
                obs = self.game.get_observation(current_player)
                legal = sorted(list(obs.legal_numbers))
                number = legal[0]
                reasoning = f"降级（原返回非法数字被拦截）"
                result = self.game.step(current_player, number)

            # 记录本步信息
            step_info = {
                "turn": self.game.turn_count,
                "player": current_player,
                "agent_name": agent.get_name(),
                "number": number,
                "reasoning": reasoning,
                "decision_time": round(decision_time, 4),
                "lines_gained_p1": result.lines_gained_p1,
                "lines_gained_p2": result.lines_gained_p2,
            }
            move_timeline.append(step_info)

            if self.verbose:
                print(
                    f"[回合 {self.game.turn_count}] "
                    f"{agent.get_name()}({current_player}) 报数 {number}"
                    f" | P1:{result.p1_total_lines}线 P2:{result.p2_total_lines}线"
                    f" | {reasoning[:50]}"
                )

        # 游戏结束
        duration = time.time() - start_time
        winner = self.game.winner
        pub = self.game.get_public_state()

        # 确定胜者名称
        winner_name = None
        if winner == "player_1":
            winner_name = self.agent1.get_name()
        elif winner == "player_2":
            winner_name = self.agent2.get_name()

        if self.verbose:
            print(f"\n对局结束！胜者: {winner_name}，回合数: {self.game.turn_count}")

        return MatchResult(
            match_id=match_id,
            agent1_name=self.agent1.get_name(),
            agent2_name=self.agent2.get_name(),
            agent1_type=self.agent1.get_type(),
            agent2_type=self.agent2.get_type(),
            winner=winner,
            winner_name=winner_name,
            total_turns=self.game.turn_count,
            p1_final_lines=pub.p1_lines,
            p2_final_lines=pub.p2_lines,
            called_numbers=list(self.game.called_numbers),
            move_timeline=move_timeline,
            duration_seconds=round(duration, 4),
            first_player=self.game.first_player,
        )
