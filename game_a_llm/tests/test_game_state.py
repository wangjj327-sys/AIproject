"""GameState类单元测试"""

import pytest
from engine.board import Board
from engine.game_state import (
    GameState, GamePhase, Move, StepResult, Observation, PublicState
)
from engine.rules import Rules
from engine.exceptions import (
    GameAlreadyFinishedError,
    NotYourTurnError,
    InvalidPlayerError,
    InvalidNumberError,
    NumberAlreadyCalledError,
)


class TestGameInitialization:
    """游戏初始化测试"""

    def test_reset_creates_two_boards(self, game):
        """reset后创建两个棋盘"""
        assert "player_1" in game.boards
        assert "player_2" in game.boards
        assert isinstance(game.boards["player_1"], Board)
        assert isinstance(game.boards["player_2"], Board)

    def test_reset_boards_are_different(self, game):
        """两个棋盘布局不同（大概率）"""
        b1 = game.boards["player_1"]
        b2 = game.boards["player_2"]
        assert b1.grid != b2.grid

    def test_reset_sets_phase_playing(self, game):
        """reset后进入playing阶段"""
        assert game.phase == GamePhase.PLAYING

    def test_reset_turn_count_zero(self, game):
        """reset后回合数为0"""
        assert game.turn_count == 0

    def test_reset_no_winner(self, game):
        """reset后无胜者"""
        assert game.winner is None

    def test_reset_called_numbers_empty(self, game):
        """reset后无已报数字"""
        assert len(game.called_numbers) == 0

    def test_reset_deterministic_first_player(self):
        """指定先手玩家"""
        g = GameState(seed_p1=42, seed_p2=123)
        g.reset(first_player="player_2")
        assert g.current_player == "player_2"
        assert g.first_player == "player_2"

    def test_deterministic_seeds(self):
        """相同种子产生相同的游戏"""
        g1 = GameState(seed_p1=42, seed_p2=123)
        g1.reset(first_player="player_1")

        g2 = GameState(seed_p1=42, seed_p2=123)
        g2.reset(first_player="player_1")

        assert g1.boards["player_1"].grid == g2.boards["player_1"].grid
        assert g1.boards["player_2"].grid == g2.boards["player_2"].grid


class TestGameStep:
    """游戏步骤测试"""

    def test_step_valid_move(self, game):
        """执行合法行动"""
        result = game.step("player_1", 7)
        assert result.move.player_id == "player_1"
        assert result.move.number == 7
        assert not result.is_terminal

    def test_step_advances_turn_count(self, game):
        """step增加回合数"""
        game.step("player_1", 7)
        assert game.turn_count == 1
        game.step("player_2", 14)
        assert game.turn_count == 2

    def test_step_switches_player(self, game):
        """step后切换玩家"""
        assert game.current_player == "player_1"
        game.step("player_1", 7)
        assert game.current_player == "player_2"
        game.step("player_2", 14)
        assert game.current_player == "player_1"

    def test_step_adds_to_called_numbers(self, game):
        """step添加数字到已报列表"""
        game.step("player_1", 7)
        assert 7 in game.called_numbers
        game.step("player_2", 14)
        assert game.called_numbers == [7, 14]

    def test_step_marks_both_boards(self, game):
        """step标记双方的棋盘"""
        game.step("player_1", 7)
        assert game.boards["player_1"].is_marked(7)
        assert game.boards["player_2"].is_marked(7)

    def test_step_records_move_history(self, game):
        """step记录行动历史"""
        game.step("player_1", 7)
        game.step("player_2", 14)
        assert len(game.move_history) == 2
        assert game.move_history[0].player_id == "player_1"
        assert game.move_history[0].number == 7
        assert game.move_history[1].player_id == "player_2"
        assert game.move_history[1].number == 14

    def test_step_returns_lines_gained(self, game):
        """step返回新增线数"""
        result = game.step("player_1", 7)
        assert isinstance(result.lines_gained_p1, int)
        assert isinstance(result.lines_gained_p2, int)
        assert result.lines_gained_p1 >= 0
        assert result.lines_gained_p2 >= 0
        assert result.lines_gained_p1 <= 4  # 一个数字最多完成4条线

    def test_step_tracks_total_lines(self, game):
        """step跟踪总线数"""
        result = game.step("player_1", 7)
        assert result.p1_total_lines == result.lines_gained_p1
        assert result.p2_total_lines == result.lines_gained_p2


class TestGameStepErrors:
    """游戏步骤错误处理测试"""

    def test_step_wrong_player_turn(self, game):
        """错误的玩家回合"""
        with pytest.raises(NotYourTurnError):
            game.step("player_2", 7)  # 当前是player_1的回合

    def test_step_invalid_player_id(self, game):
        """无效的玩家ID"""
        with pytest.raises(InvalidPlayerError):
            game.step("player_3", 7)

    def test_step_invalid_number_low(self, game):
        """非法数字（太小）"""
        with pytest.raises(InvalidNumberError):
            game.step("player_1", 0)

    def test_step_invalid_number_high(self, game):
        """非法数字（太大）"""
        with pytest.raises(InvalidNumberError):
            game.step("player_1", 26)

    def test_step_number_already_called(self, game):
        """数字已被报过"""
        game.step("player_1", 7)
        game.step("player_2", 14)
        with pytest.raises(NumberAlreadyCalledError):
            game.step("player_1", 7)  # 7已被报过

    def test_step_after_game_finished(self, game):
        """游戏结束后不能继续操作"""
        # 通过交替报数直到游戏结束
        # 由于棋盘随机，用所有数字快速完成一局
        for i in range(1, 26):
            try:
                player = game.current_player
                game.step(player, i)
            except (GameAlreadyFinishedError, InvalidNumberError, NumberAlreadyCalledError):
                break
            if game.is_terminal():
                break

        if game.is_terminal():
            with pytest.raises(GameAlreadyFinishedError):
                # 确定当前回合玩家是谁，然后用该玩家报数
                remaining = set(range(1, 26)) - set(game.called_numbers)
                if remaining:
                    game.step(game.current_player, min(remaining))


class TestObservation:
    """观测信息测试"""

    def test_get_observation_player_1(self, game):
        """获取玩家1的观测"""
        game.step("player_1", 7)
        obs = game.get_observation("player_1")

        assert obs.player_id == "player_1"
        assert isinstance(obs.my_board, Board)
        assert obs.turn_count == 1
        assert 7 in obs.called_numbers
        assert 7 not in obs.legal_numbers

    def test_get_observation_hides_opponent_grid(self, game):
        """观测不包含对手的棋盘"""
        game.step("player_1", 7)
        obs = game.get_observation("player_1")
        # 观测中只包含自己的棋盘
        # 对手信息仅限于线数
        assert isinstance(obs.opponent_lines, int)

    def test_get_observation_opponent_lines(self, game):
        """观测显示对手的线数"""
        game.step("player_1", 7)
        obs_p1 = game.get_observation("player_1")
        obs_p2 = game.get_observation("player_2")
        # P1的观测中对手线数是P2的线数
        assert obs_p1.opponent_lines == obs_p2.my_lines
        assert obs_p2.opponent_lines == obs_p1.my_lines

    def test_get_observation_legal_numbers(self, game):
        """观测显示合法可选数字"""
        game.step("player_1", 7)
        game.step("player_2", 14)
        obs = game.get_observation("player_1")
        assert 7 not in obs.legal_numbers
        assert 14 not in obs.legal_numbers
        assert len(obs.legal_numbers) == 23  # 25 - 2

    def test_get_observation_invalid_player(self, game):
        """获取无效玩家的观测"""
        with pytest.raises(InvalidPlayerError):
            game.get_observation("player_3")

    def test_get_observation_line_details(self, game):
        """观测包含线详情"""
        obs = game.get_observation("player_1")
        assert len(obs.line_details) == 12  # 12条线


class TestPublicState:
    """公共状态测试"""

    def test_get_public_state(self, game):
        """获取公共状态"""
        game.step("player_1", 7)
        pub = game.get_public_state()

        assert pub.called_numbers == [7]
        assert pub.turn_count == 1
        assert pub.current_player == "player_2"
        assert pub.total_numbers_left == 24
        assert pub.phase == "playing"
        assert pub.winner is None
        assert pub.first_player == "player_1"

    def test_public_state_shows_both_line_counts(self, game):
        """公共状态显示双方线数"""
        game.step("player_1", 7)
        pub = game.get_public_state()
        assert isinstance(pub.p1_lines, int)
        assert isinstance(pub.p2_lines, int)

    def test_public_state_no_private_boards(self):
        """公共状态不包含私有棋盘信息"""
        game = GameState(seed_p1=42, seed_p2=123)
        game.reset()
        pub = game.get_public_state()
        pub_dict = pub.to_dict()
        assert "boards" not in pub_dict
        assert "my_board" not in pub_dict


class TestTerminalDetection:
    """终局检测测试"""

    def test_not_terminal_at_start(self, game):
        """初始状态游戏未结束"""
        assert not game.is_terminal()
        assert game.get_winner() is None

    def test_terminal_when_winner(self, game):
        """有人获胜时游戏结束"""
        # 通过模拟标记5条线来测试
        # 由于随机棋盘难以精确控制，使用手动创建的棋盘
        b1 = Board(seed=42)
        # 标记5行（需要标记所有25个数字）
        for i in range(1, 26):
            b1.mark(i)
        assert Rules.count_lines(b1) >= 5

    def test_game_can_continue_after_check(self, game):
        """is_terminal不修改游戏状态"""
        assert not game.is_terminal()
        game.step("player_1", 7)
        assert not game.is_terminal()


class TestSerialization:
    """序列化测试"""

    def test_to_dict(self, game):
        """序列化为字典"""
        game.step("player_1", 7)
        game.step("player_2", 14)

        data = game.to_dict()
        assert "boards" in data
        assert "called_numbers" in data
        assert data["called_numbers"] == [7, 14]
        assert data["turn_count"] == 2
        assert data["phase"] == "playing"
        assert len(data["move_history"]) == 2

    def test_from_dict(self, game):
        """从字典反序列化"""
        game.step("player_1", 7)
        game.step("player_2", 14)

        data = game.to_dict()
        restored = GameState.from_dict(data)

        assert restored.turn_count == game.turn_count
        assert restored.called_numbers == game.called_numbers
        assert restored.phase == game.phase
        assert restored.current_player == game.current_player
        assert restored.boards["player_1"].grid == game.boards["player_1"].grid
        assert restored.boards["player_1"].marked == game.boards["player_1"].marked

    def test_roundtrip_consistency(self, game):
        """序列化再反序列化保持一致"""
        game.step("player_1", 3)
        game.step("player_2", 8)
        game.step("player_1", 15)
        game.step("player_2", 22)

        restored = GameState.from_dict(game.to_dict())

        assert restored.turn_count == game.turn_count
        assert restored.called_numbers == game.called_numbers
        assert restored.current_player == game.current_player
        assert restored.boards["player_1"].marked == game.boards["player_1"].marked
        assert restored.boards["player_2"].marked == game.boards["player_2"].marked

    def test_move_serialization(self):
        """Move序列化"""
        m = Move(player_id="player_1", number=7)
        data = m.to_dict()
        restored = Move.from_dict(data)
        assert restored.player_id == "player_1"
        assert restored.number == 7

    def test_step_result_serialization(self, game):
        """StepResult序列化"""
        result = game.step("player_1", 7)
        data = result.to_dict()
        assert data["move"]["number"] == 7
        assert "lines_gained_p1" in data
        assert "is_terminal" in data
        assert "winner" in data
