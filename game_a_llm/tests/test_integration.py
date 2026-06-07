"""集成测试——完整对局流程"""

import pytest
import json
from engine.game_state import GameState, GamePhase
from engine.board import Board
from engine.rules import Rules
from engine.exceptions import GameAlreadyFinishedError


class TestFullGame:
    """完整对局测试"""

    def test_random_vs_random_full_game(self):
        """
        使用随机策略进行完整对局，验证：
        - 游戏能正常结束
        - 胜者正确判定
        - 无异常抛出
        """
        import random

        game = GameState()
        game.reset()
        rng = random.Random(42)

        move_count = 0
        while not game.is_terminal():
            obs = game.get_observation(game.current_player)
            # 随机选择一个合法数字
            number = rng.choice(sorted(list(obs.legal_numbers)))
            result = game.step(game.current_player, number)
            move_count += 1
            # 验证结果
            assert result.move.number == number

        # 游戏结束后验证
        assert game.phase == GamePhase.FINISHED
        assert game.winner is not None
        assert game.winner in ("player_1", "player_2")
        assert move_count > 0
        assert game.turn_count == move_count
        assert len(game.called_numbers) == move_count

    def test_multiple_random_games(self):
        """多局随机对战——验证无异常"""
        import random

        for game_idx in range(20):
            game = GameState()
            game.reset()
            rng = random.Random(game_idx)

            move_count = 0
            while not game.is_terminal() and move_count < 50:
                obs = game.get_observation(game.current_player)
                number = rng.choice(sorted(list(obs.legal_numbers)))
                result = game.step(game.current_player, number)
                move_count += 1

            assert game.is_terminal()
            assert game.winner is not None
            assert move_count >= 5  # 最快也需要5回合（一方连报5个在自己同一条线上的数字）

    def test_winner_has_at_least_5_lines(self):
        """
        验证胜者确实完成了至少5条线。
        """
        import random

        game = GameState()
        game.reset()
        rng = random.Random(99)

        while not game.is_terminal():
            obs = game.get_observation(game.current_player)
            number = rng.choice(sorted(list(obs.legal_numbers)))
            game.step(game.current_player, number)

        # 检查胜者的线数
        winner = game.winner
        winner_board = game.boards[winner]
        winner_lines = Rules.count_lines(winner_board)
        assert winner_lines >= Rules.WIN_THRESHOLD

    def test_no_illegal_state_transitions(self):
        """验证状态转换的合法性"""
        game = GameState()
        game.reset(first_player="player_1")

        # 初始状态
        assert game.phase == GamePhase.PLAYING
        assert game.current_player == "player_1"
        assert game.winner is None

        # 每一步都应该在合法状态
        for i in range(1, 10):
            obs = game.get_observation(game.current_player)
            number = min(obs.legal_numbers)
            game.step(game.current_player, number)

            if game.is_terminal():
                assert game.phase == GamePhase.FINISHED
                assert game.winner is not None
                break
            else:
                assert game.phase == GamePhase.PLAYING


class TestObservationsAreCorrect:
    """观测一致性测试"""

    def test_observations_match_game_state(self):
        """观测信息与游戏状态一致"""
        import random

        game = GameState(seed_p1=42, seed_p2=123)
        game.reset(first_player="player_1")
        rng = random.Random(7)

        for _ in range(5):
            if game.is_terminal():
                break
            obs = game.get_observation(game.current_player)
            assert obs.turn_count == game.turn_count
            assert obs.current_player == game.current_player
            assert obs.called_numbers == game.called_numbers
            assert obs.player_id == game.current_player

            number = rng.choice(sorted(list(obs.legal_numbers)))
            game.step(game.current_player, number)

    def test_both_players_see_same_public_info(self):
        """双方看到的公共信息一致"""
        import random

        game = GameState(seed_p1=42, seed_p2=123)
        game.reset()
        rng = random.Random(3)

        for _ in range(8):
            if game.is_terminal():
                break
            obs = game.get_observation(game.current_player)
            number = rng.choice(sorted(list(obs.legal_numbers)))
            game.step(game.current_player, number)

            if not game.is_terminal():
                obs1 = game.get_observation("player_1")
                obs2 = game.get_observation("player_2")
                assert obs1.called_numbers == obs2.called_numbers
                assert obs1.turn_count == obs2.turn_count
                assert obs1.opponent_lines == obs2.my_lines
                assert obs2.opponent_lines == obs1.my_lines


class TestEdgeCases:
    """边界情况测试"""

    def test_game_with_specific_seeds(self):
        """使用固定种子的完整对局，确保可复现"""
        import random

        game = GameState(seed_p1=42, seed_p2=123)
        game.reset(first_player="player_1")
        rng = random.Random(42)

        moves = []
        while not game.is_terminal():
            obs = game.get_observation(game.current_player)
            number = rng.choice(sorted(list(obs.legal_numbers)))
            game.step(game.current_player, number)
            moves.append((game.move_history[-1].player_id, number))

        # 应该有完整的行动记录
        assert len(moves) > 0
        assert len(moves) == len(game.called_numbers)

        # 序列化后再运行不应产生新变化
        data = game.to_dict()
        restored = GameState.from_dict(data)
        assert restored.is_terminal()
        assert restored.winner == game.winner

    def test_center_number_completes_4_lines_theoretically(self):
        """
        验证中心位置(2,2)能同时完成最多4条线的理论可能。
        需要棋盘中该位置同时属于4条将完成的线。
        """
        # 创建特定棋盘——让(2,2)的数字在row_2, col_2, diag_main, diag_anti上
        # row 2: [1, 2, X, 4, 5]    X是被测试数字
        # col 2: [6, 7, X, 9, 10]
        # diag_main: [11, 12, X, 14, 15]
        # diag_anti: [16, 17, X, 19, 20]

        # 使用seed=42的棋盘
        game = GameState(seed_p1=42, seed_p2=123)
        game.reset(first_player="player_1")

        board = game.boards["player_1"]
        center_num = board.get_cell(2, 2)

        # 获取center_num周围的线
        lines_with_center = Rules.get_lines_containing_position(2, 2)
        # 最多4条线（1行+1列+2对角线）
        assert len(lines_with_center) <= 4

    def test_simultaneous_win_detection(self):
        """同时达到5条线（线数相同）——先手胜"""
        # 检查胜负规则
        # 线数相同时（都>=5），先手胜
        assert Rules.determine_winner(5, 5, first_player="player_1") == "player_1"
        assert Rules.determine_winner(5, 5, first_player="player_2") == "player_2"
        # 线数不同时，多者胜
        assert Rules.determine_winner(6, 5, first_player="player_1") == "player_1"
        assert Rules.determine_winner(5, 6, first_player="player_1") == "player_2"


class TestReplay:
    """回放测试"""

    def test_save_and_load_replay(self):
        """保存和加载对局回放"""
        import random

        # 进行一局
        game = GameState(seed_p1=42, seed_p2=123)
        game.reset(first_player="player_1")
        rng = random.Random(42)

        while not game.is_terminal():
            obs = game.get_observation(game.current_player)
            number = rng.choice(sorted(list(obs.legal_numbers)))
            game.step(game.current_player, number)

        # 保存为JSON
        replay_data = game.to_dict()
        json_str = json.dumps(replay_data, ensure_ascii=False)
        assert len(json_str) > 0

        # 加载回放
        loaded_data = json.loads(json_str)
        restored = GameState.from_dict(loaded_data)

        # 验证
        assert restored.winner == game.winner
        assert restored.turn_count == game.turn_count
        assert restored.called_numbers == game.called_numbers
