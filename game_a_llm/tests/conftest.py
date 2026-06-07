"""测试配置与共享fixtures"""

import pytest
import sys
from pathlib import Path

# 将src目录加入搜索路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from engine.board import Board
from engine.game_state import GameState
from engine.rules import Rules


@pytest.fixture
def board_with_seed():
    """使用固定种子创建的棋盘，确保测试可复现"""
    return Board(seed=42)


@pytest.fixture
def board_random():
    """随机棋盘"""
    return Board()


@pytest.fixture
def game():
    """新建并重置的游戏"""
    g = GameState(seed_p1=42, seed_p2=123)
    g.reset(first_player="player_1")
    return g


@pytest.fixture
def game_midway():
    """
    进行到中局的游戏。
    使用固定种子确保可复现。
    """
    g = GameState(seed_p1=42, seed_p2=123)
    g.reset(first_player="player_1")

    # 模拟报数：交替进行6个回合（3轮每方）
    numbers = [7, 14, 21, 3, 15, 9]
    for i, num in enumerate(numbers):
        player = "player_1" if i % 2 == 0 else "player_2"
        g.step(player, num)
    return g


@pytest.fixture
def full_board():
    """创建一个明确布局的棋盘用于线检测测试

    网格布局（seed=42）:
      5 18 21 14  2
     13 22 20 17 16
     10  4 25 11 19
      8 24  7 12 15
      1  6  3  9 23
    """
    return Board(seed=42)
