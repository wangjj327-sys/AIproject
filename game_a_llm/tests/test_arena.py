"""竞技场模块测试——批量对战与评估"""

import json
import tempfile
import os
import sys
from pathlib import Path

# 确保能导入scripts模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from engine.game_state import GameState
from agents.random import RandomAgent
from agents.greedy import GreedyAgent
from arena.match import Match, MatchResult
from arena.tournament import Tournament, TournamentConfig, TournamentStats
from arena.recorder import Recorder


class TestTournament:
    """锦标赛测试"""

    def test_run_pair_basic(self):
        """基础配对对战"""
        config = TournamentConfig(n_games_per_pair=5, save_replays=False, verbose=False)
        tournament = Tournament(config)

        a1 = GreedyAgent("player_1", name="贪心A")
        a2 = RandomAgent("player_2", name="随机B", seed=42)

        results = tournament.run_pair(a1, a2, n_games=10)
        assert len(results) == 10
        for r in results:
            assert r.winner in ("player_1", "player_2")
            assert r.total_turns > 0

    def test_run_pair_swap_sides(self):
        """交换先手/后手"""
        config = TournamentConfig(
            n_games_per_pair=20, swap_sides=True, save_replays=False
        )
        tournament = Tournament(config)

        a1 = RandomAgent("player_1", name="随机A", seed=1)
        a2 = RandomAgent("player_2", name="随机B", seed=2)

        results = tournament.run_pair(a1, a2)

        # 检查是否有先手交换
        first_players = [r.move_timeline[0]["player"] for r in results]
        assert "player_1" in first_players
        assert "player_2" in first_players

    def test_round_robin(self):
        """循环赛"""
        config = TournamentConfig(n_games_per_pair=10, save_replays=False)
        tournament = Tournament(config)

        agents = [
            GreedyAgent("player_1", name="贪心"),
            RandomAgent("player_1", name="随机A", seed=1),
            RandomAgent("player_1", name="随机B", seed=2),
        ]

        stats = tournament.run_round_robin(agents)
        assert stats.total_matches == 30  # 3选2 * 10局 = 30

        rankings = stats.get_rankings()
        assert len(rankings) == 3

        # 贪心应该排第一
        assert rankings[0]["name"] == "贪心"

    def test_single_agent_vs_all(self):
        """单代理vs所有对手"""
        config = TournamentConfig(n_games_per_pair=5, save_replays=False)
        tournament = Tournament(config)

        test_agent = GreedyAgent("player_1", name="贪心")
        opponents = [
            RandomAgent("player_2", name="随机A", seed=i)
            for i in range(3)
        ]

        stats = tournament.run_single_agent_vs_all(test_agent, opponents, n_games=5)
        assert stats.total_matches == 15
        assert "贪心" in stats.agent_stats

    def test_save_and_load_results(self, tmp_path):
        """保存和加载结果"""
        config = TournamentConfig(n_games_per_pair=3, save_replays=False)
        tournament = Tournament(config)

        a1 = RandomAgent("player_1", name="随机A", seed=1)
        a2 = RandomAgent("player_2", name="随机B", seed=2)

        tournament.run_pair(a1, a2)

        result_path = tmp_path / "results.json"
        tournament.save_results(str(result_path))

        assert result_path.exists()

        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        assert "stats" in data
        assert "results" in data
        assert len(data["results"]) == 3

    def test_tournament_reset(self):
        """重置锦标赛"""
        config = TournamentConfig(n_games_per_pair=2, save_replays=False)
        tournament = Tournament(config)

        a1 = RandomAgent("player_1", seed=1)
        a2 = RandomAgent("player_2", seed=2)
        tournament.run_pair(a1, a2)

        assert len(tournament.get_results()) == 2
        tournament.reset()
        assert len(tournament.get_results()) == 0

    def test_tournament_stats_ranking(self):
        """统计排名"""
        config = TournamentConfig(n_games_per_pair=10, save_replays=False)
        tournament = Tournament(config)

        greedy = GreedyAgent("player_1", name="贪心")
        random_agent = RandomAgent("player_1", name="随机", seed=1)

        tournament.run_pair(greedy, random_agent)
        stats = TournamentStats(results=tournament.get_results())
        stats.compute()

        rankings = stats.get_rankings()
        assert len(rankings) >= 1

        # 贪心应该有更高的胜率
        greedy_rank = [r for r in rankings if r["name"] == "贪心"]
        random_rank = [r for r in rankings if r["name"] == "随机"]
        if greedy_rank and random_rank:
            assert greedy_rank[0]["rank"] < random_rank[0]["rank"]


class TestRecorder:
    """对局记录器测试"""

    def test_save_and_load(self, tmp_path):
        """保存和加载回放"""
        recorder = Recorder(str(tmp_path))

        game = GameState(seed_p1=42, seed_p2=123)
        game.reset(first_player="player_1")

        from agents.random import RandomAgent
        match = Match(
            game,
            RandomAgent("player_1", seed=1, name="P1"),
            RandomAgent("player_2", seed=2, name="P2"),
        )
        result = match.run()

        # 保存
        filepath = recorder.save(result, game)
        assert os.path.exists(filepath)

        # 加载
        replay = recorder.load(f"match_{result.match_id}.json")
        assert replay is not None
        assert replay["result"]["total_turns"] == result.total_turns
        assert replay["agent1"]["name"] == "P1"

    def test_list_replays(self, tmp_path):
        """列出回放"""
        recorder = Recorder(str(tmp_path))

        # 创建几个回放
        for i in range(3):
            game = GameState(seed_p1=i, seed_p2=i + 100)
            game.reset()
            match = Match(
                game,
                RandomAgent("player_1", seed=i),
                RandomAgent("player_2", seed=i + 50),
            )
            result = match.run()
            recorder.save(result, game)

        replays = recorder.list_replays()
        assert len(replays) == 3

    def test_delete_replay(self, tmp_path):
        """删除回放"""
        recorder = Recorder(str(tmp_path))

        game = GameState()
        game.reset()
        match = Match(game, RandomAgent("player_1"), RandomAgent("player_2"))
        result = match.run()
        recorder.save(result, game)

        assert len(recorder.list_replays()) == 1
        assert recorder.delete_replay(result.match_id)
        assert len(recorder.list_replays()) == 0

    def test_clear_all(self, tmp_path):
        """清空所有回放"""
        recorder = Recorder(str(tmp_path))

        for i in range(5):
            game = GameState(seed_p1=i, seed_p2=i + 100)
            game.reset()
            match = Match(game, RandomAgent("player_1"), RandomAgent("player_2"))
            result = match.run()
            recorder.save(result, game)

        assert recorder.clear_all() == 5
        assert len(recorder.list_replays()) == 0

    def test_get_summary(self, tmp_path):
        """回放摘要"""
        recorder = Recorder(str(tmp_path))

        game = GameState(seed_p1=1, seed_p2=2)
        game.reset()
        match = Match(
            game,
            RandomAgent("player_1", name="测试A"),
            RandomAgent("player_2", name="测试B"),
        )
        result = match.run()
        recorder.save(result, game)

        summary = recorder.get_summary()
        assert summary["total_replays"] == 1
        assert "测试A" in summary["unique_agents"]

    def test_load_nonexistent(self, tmp_path):
        """加载不存在的回放"""
        recorder = Recorder(str(tmp_path))
        assert recorder.load("nonexistent.json") is None


class TestEvaluator:
    """评估器测试"""

    def test_analyze_from_tournament_results(self):
        """从锦标赛结果分析"""
        from scripts.evaluate_results import Evaluator

        config = TournamentConfig(n_games_per_pair=20, save_replays=False)
        tournament = Tournament(config)

        greedy = GreedyAgent("player_1", name="贪心")
        random_agent = RandomAgent("player_1", name="随机", seed=1)

        tournament.run_pair(greedy, random_agent)

        evaluator = Evaluator()
        evaluator.load_from_results(tournament.get_results())
        analysis = evaluator.analyze()

        assert analysis["total_matches"] == 20
        assert len(analysis["agents"]) == 2
        assert "elo_ratings" in analysis

        # 贪心ELO应该高于随机
        elo = analysis["elo_ratings"]
        assert elo["贪心"] > elo["随机"]

    def test_report_generation(self):
        """报告生成"""
        from scripts.evaluate_results import Evaluator

        config = TournamentConfig(n_games_per_pair=10, save_replays=False)
        tournament = Tournament(config)

        greedy = GreedyAgent("player_1", name="贪心")
        random_agent = RandomAgent("player_1", name="随机", seed=1)

        tournament.run_pair(greedy, random_agent)

        evaluator = Evaluator()
        evaluator.load_from_results(tournament.get_results())
        report = evaluator.report()

        assert "对战评估报告" in report
        assert "贪心" in report
        assert "随机" in report
        assert "胜率" in report or "ELO" in report

    def test_save_report(self, tmp_path):
        """保存报告"""
        from scripts.evaluate_results import Evaluator

        config = TournamentConfig(n_games_per_pair=5, save_replays=False)
        tournament = Tournament(config)

        greedy = GreedyAgent("player_1", name="贪心")
        random_agent = RandomAgent("player_1", name="随机", seed=1)

        tournament.run_pair(greedy, random_agent)

        evaluator = Evaluator()
        evaluator.load_from_results(tournament.get_results())
        analysis = evaluator.analyze()

        report_path = tmp_path / "report.txt"
        evaluator.save_report(analysis, str(report_path))

        assert report_path.exists()
        json_path = tmp_path / "report.json"
        assert json_path.exists()

    def test_empty_results(self):
        """空结果处理"""
        from scripts.evaluate_results import Evaluator
        evaluator = Evaluator()
        analysis = evaluator.analyze()
        assert "error" in analysis
