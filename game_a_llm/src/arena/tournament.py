"""对战调度模块 - 锦标赛/批量对战管理

支持：
- 循环赛（每个组合互相对战）
- 重复对战（同一组合多次对战）
- 结果汇总统计
- 并行对战（未来可用asyncio扩展）
"""

import time
import json
import itertools
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from engine.game_state import GameState
from agents.base import BaseAgent
from agents.agent_factory import AgentFactory
from .match import Match, MatchResult
from .recorder import Recorder


@dataclass
class TournamentConfig:
    """锦标赛配置"""
    n_games_per_pair: int = 10          # 每对组合对战局数
    swap_sides: bool = True             # 是否交换先手/后手
    save_replays: bool = True           # 是否保存回放
    replay_dir: str = "data/replays"    # 回放保存目录
    verbose: bool = False               # 是否打印每局详情
    seed_start: int = 0                 # 随机种子起始值


@dataclass
class TournamentStats:
    """锦标赛统计"""
    total_matches: int = 0
    results: list[MatchResult] = field(default_factory=list)

    # 按代理名称统计
    agent_stats: dict[str, dict] = field(default_factory=dict)

    def compute(self) -> None:
        """计算所有统计数据"""
        self.total_matches = len(self.results)
        if not self.results:
            return

        # 按代理聚合
        agent_data: dict[str, dict] = {}

        for result in self.results:
            for agent_name in [result.agent1_name, result.agent2_name]:
                if agent_name not in agent_data:
                    agent_data[agent_name] = {
                        "name": agent_name,
                        "type": "",
                        "wins": 0,
                        "losses": 0,
                        "draws": 0,
                        "total_games": 0,
                        "as_first": 0,
                        "as_second": 0,
                        "first_win_rate": 0.0,
                        "avg_turns_when_win": 0.0,
                        "win_turns_list": [],
                    }

            # 确定类型
            agent_data[result.agent1_name]["type"] = result.agent1_type
            agent_data[result.agent2_name]["type"] = result.agent2_type

            # 更新统计
            if result.winner == "player_1":
                agent_data[result.agent1_name]["wins"] += 1
                agent_data[result.agent2_name]["losses"] += 1
                agent_data[result.agent1_name]["win_turns_list"].append(result.total_turns)
            elif result.winner == "player_2":
                agent_data[result.agent2_name]["wins"] += 1
                agent_data[result.agent1_name]["losses"] += 1
                agent_data[result.agent2_name]["win_turns_list"].append(result.total_turns)

            agent_data[result.agent1_name]["total_games"] += 1
            agent_data[result.agent2_name]["total_games"] += 1

            # 先手统计
            if result.first_player == "player_1":
                agent_data[result.agent1_name]["as_first"] += 1
                agent_data[result.agent2_name]["as_second"] += 1
                if result.winner == "player_1":
                    agent_data[result.agent1_name]["first_win_rate"] = (
                        (agent_data[result.agent1_name]["first_win_rate"] *
                         (agent_data[result.agent1_name]["as_first"] - 1) + 1)
                        / agent_data[result.agent1_name]["as_first"]
                    )
            else:
                agent_data[result.agent2_name]["as_first"] += 1
                agent_data[result.agent1_name]["as_second"] += 1

        # 计算平均值
        for name, data in agent_data.items():
            if data["win_turns_list"]:
                data["avg_turns_when_win"] = (
                    sum(data["win_turns_list"]) / len(data["win_turns_list"])
                )
            data["win_rate"] = (
                data["wins"] / data["total_games"]
                if data["total_games"] > 0 else 0
            )

        self.agent_stats = agent_data

    def get_rankings(self) -> list[dict]:
        """获取按胜率排序的排名"""
        if not self.agent_stats:
            return []
        sorted_agents = sorted(
            self.agent_stats.values(),
            key=lambda x: x.get("win_rate", 0),
            reverse=True,
        )
        return [
            {
                "rank": i + 1,
                "name": a["name"],
                "type": a["type"],
                "wins": a["wins"],
                "losses": a["losses"],
                "win_rate": f"{a['win_rate']:.1%}",
                "avg_turns": f"{a['avg_turns_when_win']:.1f}" if a['avg_turns_when_win'] > 0 else "N/A",
            }
            for i, a in enumerate(sorted_agents)
        ]

    def to_dict(self) -> dict:
        return {
            "total_matches": self.total_matches,
            "rankings": self.get_rankings(),
            "agent_stats": {
                name: {
                    k: v for k, v in stats.items()
                    if k != "win_turns_list"
                }
                for name, stats in self.agent_stats.items()
            },
        }


class Tournament:
    """
    锦标赛管理器。

    支持多种对战模式：
    - 循环赛：所有代理两两对战
    - 重复对战：同一组合多次对战

    用法:
        # 创建代理
        agents = [
            GreedyAgent("player_1", name="贪心-A"),
            RandomAgent("player_2", name="随机-B"),
        ]

        # 循环赛
        tournament = Tournament(TournamentConfig(n_games_per_pair=50))
        stats = tournament.run_round_robin(agents)

        # 查看排名
        for r in stats.get_rankings():
            print(f"{r['rank']}. {r['name']}: {r['win_rate']}")
    """

    def __init__(self, config: Optional[TournamentConfig] = None):
        self.config = config or TournamentConfig()
        self.recorder = Recorder(self.config.replay_dir)
        self._results: list[MatchResult] = []

    def run_pair(
        self,
        agent1: BaseAgent,
        agent2: BaseAgent,
        n_games: int = None,
    ) -> list[MatchResult]:
        """
        两个代理之间进行多局对战。

        Args:
            agent1: 代理1
            agent2: 代理2
            n_games: 局数（默认使用config中的值）

        Returns:
            list[MatchResult]: 所有对局结果
        """
        n = n_games or self.config.n_games_per_pair
        results = []

        for i in range(n):
            seed = self.config.seed_start + i

            # 交换先手/后手
            if self.config.swap_sides and i % 2 == 1:
                first = "player_2"
                a1, a2 = agent2, agent1
                swap = True
            else:
                first = "player_1"
                a1, a2 = agent1, agent2
                swap = False

            # 创建游戏
            game = GameState(seed_p1=seed, seed_p2=seed + 10000)
            game.reset(first_player=first)

            a1.player_id = game.first_player
            a2.player_id = game.get_opponent(game.first_player)

            # 确保Match中的名称与传入顺序一致（方便结果解读）
            if swap:
                match = Match(game, a2, a1, verbose=self.config.verbose)
            else:
                match = Match(game, a1, a2, verbose=self.config.verbose)

            result = match.run()
            results.append(result)
            self._results.append(result)

            # 保存回放
            if self.config.save_replays:
                self.recorder.save(result, game)

            if self.config.verbose:
                print(
                    f"[{i+1}/{n}] {result.agent1_name} vs {result.agent2_name} | "
                    f"胜者: {result.winner_name} | 回合: {result.total_turns}"
                )

        return results

    def run_round_robin(self, agents: list[BaseAgent]) -> TournamentStats:
        """
        循环赛：所有代理两两对战。

        Args:
            agents: 代理列表

        Returns:
            TournamentStats: 统计结果
        """
        pairs = list(itertools.combinations(agents, 2))

        if self.config.verbose:
            print(f"循环赛开始: {len(agents)} 名代理, {len(pairs)} 组对战")
            print(f"每组 {self.config.n_games_per_pair} 局")
            print("-" * 50)

        for i, (a1, a2) in enumerate(pairs):
            if self.config.verbose:
                print(f"\n>>> 第{i+1}/{len(pairs)}组: {a1.get_name()} vs {a2.get_name()}")

            self.run_pair(a1, a2)

        stats = TournamentStats(results=list(self._results))
        stats.compute()
        return stats

    def run_single_agent_vs_all(
        self,
        test_agent: BaseAgent,
        opponents: list[BaseAgent],
        n_games: int = None,
    ) -> TournamentStats:
        """
        单个代理与所有对手对战。

        Args:
            test_agent: 被测试的代理
            opponents: 对手列表
            n_games: 每组对局数

        Returns:
            TournamentStats: 统计结果
        """
        for opponent in opponents:
            self.run_pair(test_agent, opponent, n_games)

        stats = TournamentStats(results=list(self._results))
        stats.compute()
        return stats

    def get_results(self) -> list[MatchResult]:
        """获取所有对局结果"""
        return list(self._results)

    def save_results(self, path: str) -> None:
        """保存统计结果到JSON"""
        stats = TournamentStats(results=list(self._results))
        stats.compute()
        data = {
            "config": {
                "n_games_per_pair": self.config.n_games_per_pair,
                "swap_sides": self.config.swap_sides,
            },
            "stats": stats.to_dict(),
            "results": [r.to_dict() for r in self._results],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def reset(self) -> None:
        """重置所有结果"""
        self._results = []
