"""游戏A引擎 - 游戏状态管理

GameState是整个游戏引擎的核心类，负责：
- 管理双方棋盘
- 处理每回合的行动
- 提供观测信息
- 判定游戏结束
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time

from .board import Board
from .rules import Rules, LINES, LineInfo
from .exceptions import (
    GameAlreadyFinishedError,
    NotYourTurnError,
    InvalidPlayerError,
)


class GamePhase(str, Enum):
    """游戏阶段"""
    INIT = "init"
    PLAYING = "playing"
    FINISHED = "finished"


@dataclass
class Move:
    """一次行动记录"""
    player_id: str
    number: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "number": self.number,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Move":
        return cls(
            player_id=data["player_id"],
            number=data["number"],
            timestamp=data.get("timestamp", 0),
        )


@dataclass
class StepResult:
    """执行一步后的结果"""
    move: Move
    lines_gained_p1: int           # P1本轮新增线数
    lines_gained_p2: int           # P2本轮新增线数
    p1_total_lines: int            # P1当前总线数
    p2_total_lines: int            # P2当前总线数
    is_terminal: bool              # 游戏是否结束
    winner: Optional[str]          # 胜者ID（若结束）
    next_player: Optional[str]     # 下一回合玩家（若未结束）

    def to_dict(self) -> dict:
        return {
            "move": self.move.to_dict(),
            "lines_gained_p1": self.lines_gained_p1,
            "lines_gained_p2": self.lines_gained_p2,
            "p1_total_lines": self.p1_total_lines,
            "p2_total_lines": self.p2_total_lines,
            "is_terminal": self.is_terminal,
            "winner": self.winner,
            "next_player": self.next_player,
        }


@dataclass
class Observation:
    """
    一个玩家的私有观测。

    包含该玩家能看到的所有信息（自己的完整棋盘+公共信息）。
    """
    player_id: str
    my_board: Board                           # 自己的完整棋盘
    my_lines: int                             # 自己的已完成线数
    opponent_lines: int                       # 对手的已完成线数
    called_numbers: list[int]                 # 已报数字序列
    current_player: str                       # 当前回合玩家
    turn_count: int                           # 当前回合数
    line_details: list[LineInfo]              # 自己各条线的详情
    legal_numbers: set[int]                   # 剩余可报数字

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "my_board": self.my_board.to_dict(),
            "my_lines": self.my_lines,
            "opponent_lines": self.opponent_lines,
            "called_numbers": list(self.called_numbers),
            "current_player": self.current_player,
            "turn_count": self.turn_count,
            "legal_numbers": sorted(list(self.legal_numbers)),
        }


@dataclass
class PublicState:
    """
    公共状态——所有玩家都能看到的信息。
    """
    called_numbers: list[int]                 # 已报数字序列
    p1_lines: int                             # 玩家1已完成线数
    p2_lines: int                             # 玩家2已完成线数
    current_player: str                       # 当前回合玩家
    turn_count: int                           # 当前回合数
    total_numbers_left: int                   # 剩余可选数字数
    phase: str                                # 游戏阶段
    winner: Optional[str]                     # 胜者（若结束）
    first_player: str                         # 先手玩家

    def to_dict(self) -> dict:
        return {
            "called_numbers": list(self.called_numbers),
            "p1_lines": self.p1_lines,
            "p2_lines": self.p2_lines,
            "current_player": self.current_player,
            "turn_count": self.turn_count,
            "total_numbers_left": self.total_numbers_left,
            "phase": self.phase,
            "winner": self.winner,
            "first_player": self.first_player,
        }


class GameState:
    """
    游戏A的游戏状态管理器。

    用法示例:
        game = GameState()
        game.reset()

        # 玩家1报数字7
        result = game.step("player_1", 7)

        # 获取玩家2的观测
        obs = game.get_observation("player_2")

        if game.is_terminal():
            print(f"胜者: {game.winner}")
    """

    PLAYER_IDS = ("player_1", "player_2")
    MAX_TURNS = 50  # 防止无限循环的安全上限

    def __init__(self, seed_p1: Optional[int] = None, seed_p2: Optional[int] = None):
        """
        初始化游戏状态（不生成棋盘，需调用 reset()）。

        Args:
            seed_p1: 玩家1的棋盘随机种子
            seed_p2: 玩家2的棋盘随机种子
        """
        self._seed_p1 = seed_p1
        self._seed_p2 = seed_p2
        self.boards: dict[str, Board] = {}
        self.called_numbers: list[int] = []
        self._called_set: set[int] = set()
        self.current_player: str = "player_1"
        self.phase: GamePhase = GamePhase.INIT
        self.winner: Optional[str] = None
        self.turn_count: int = 0
        self.move_history: list[Move] = []
        self.first_player: str = "player_1"
        self._p1_lines: int = 0
        self._p2_lines: int = 0

    def reset(
        self,
        first_player: Optional[str] = None,
        seed_p1: Optional[int] = None,
        seed_p2: Optional[int] = None,
    ) -> None:
        """
        重置游戏到初始状态，生成两个随机棋盘。

        Args:
            first_player: 指定先手玩家，None则随机决定
            seed_p1: 玩家1棋盘随机种子
            seed_p2: 玩家2棋盘随机种子
        """
        import random as rand

        # 生成双方棋盘
        s1 = seed_p1 if seed_p1 is not None else self._seed_p1
        s2 = seed_p2 if seed_p2 is not None else self._seed_p2
        self.boards["player_1"] = Board(seed=s1)
        self.boards["player_2"] = Board(seed=s2)

        # 重置游戏状态
        self.called_numbers = []
        self._called_set = set()
        self.move_history = []
        self.turn_count = 0
        self.winner = None
        self.phase = GamePhase.PLAYING
        self._p1_lines = 0
        self._p2_lines = 0

        # 决定先手
        if first_player and first_player in self.PLAYER_IDS:
            self.first_player = first_player
        else:
            self.first_player = rand.choice(self.PLAYER_IDS)
        self.current_player = self.first_player

    def step(self, player_id: str, number: int) -> StepResult:
        """
        执行一步游戏操作：当前玩家报出一个数字。

        流程:
        1. 校验游戏状态和玩家回合
        2. 校验数字合法性
        3. 双方标记数字
        4. 计算新增线数
        5. 判定胜负
        6. 切换回合

        Args:
            player_id: 执行操作的玩家ID
            number: 报出的数字

        Returns:
            StepResult: 操作结果

        Raises:
            GameAlreadyFinishedError: 游戏已结束
            NotYourTurnError: 不是该玩家的回合
            InvalidNumberError: 数字不合法
            NumberAlreadyCalledError: 数字已被报过
        """
        # 1. 校验
        if self.phase == GamePhase.FINISHED:
            raise GameAlreadyFinishedError()
        if player_id not in self.PLAYER_IDS:
            raise InvalidPlayerError(player_id)
        if player_id != self.current_player:
            raise NotYourTurnError(player_id, self.current_player)

        Rules.validate_number(number, self._called_set)

        # 2. 记录行动
        move = Move(player_id=player_id, number=number)
        self.move_history.append(move)
        self.called_numbers.append(number)
        self._called_set.add(number)
        self.turn_count += 1

        # 3. 双方标记数字并计算新增线数
        board1 = self.boards["player_1"]
        board2 = self.boards["player_2"]

        # 标记数字
        board1.mark(number)
        board2.mark(number)

        # 计算新增线数（使用增量更新优化）
        lines_gained_p1 = Rules.get_lines_gained(board1, number)
        lines_gained_p2 = Rules.get_lines_gained(board2, number)

        self._p1_lines += lines_gained_p1
        self._p2_lines += lines_gained_p2

        # 4. 判定胜负
        winner = Rules.determine_winner(
            self._p1_lines, self._p2_lines, self.first_player
        )

        is_terminal = winner is not None
        if is_terminal:
            self.phase = GamePhase.FINISHED
            self.winner = winner

        # 5. 切换回合
        next_player = None
        if not is_terminal:
            next_player = "player_2" if self.current_player == "player_1" else "player_1"
            self.current_player = next_player

        return StepResult(
            move=move,
            lines_gained_p1=lines_gained_p1,
            lines_gained_p2=lines_gained_p2,
            p1_total_lines=self._p1_lines,
            p2_total_lines=self._p2_lines,
            is_terminal=is_terminal,
            winner=winner,
            next_player=next_player,
        )

    def get_observation(self, player_id: str) -> Observation:
        """
        获取指定玩家的私有观测。

        Args:
            player_id: 玩家ID

        Returns:
            Observation: 该玩家能看到的游戏状态

        Raises:
            InvalidPlayerError: 无效的玩家ID
        """
        if player_id not in self.PLAYER_IDS:
            raise InvalidPlayerError(player_id)

        my_board = self.boards[player_id]
        opponent_id = "player_2" if player_id == "player_1" else "player_1"
        opp_lines = self._p1_lines if player_id == "player_2" else self._p2_lines

        # 计算自己的线详情
        line_details = Rules.get_all_line_details(my_board)

        # 计算合法数字
        legal_numbers = set(range(1, 26)) - self._called_set

        return Observation(
            player_id=player_id,
            my_board=my_board,
            my_lines=self._p1_lines if player_id == "player_1" else self._p2_lines,
            opponent_lines=opp_lines,
            called_numbers=list(self.called_numbers),
            current_player=self.current_player,
            turn_count=self.turn_count,
            line_details=line_details,
            legal_numbers=legal_numbers,
        )

    def get_public_state(self) -> PublicState:
        """
        获取公共状态——所有玩家都能看到的信息。

        Returns:
            PublicState: 公共游戏状态
        """
        return PublicState(
            called_numbers=list(self.called_numbers),
            p1_lines=self._p1_lines,
            p2_lines=self._p2_lines,
            current_player=self.current_player,
            turn_count=self.turn_count,
            total_numbers_left=25 - len(self._called_set),
            phase=self.phase.value,
            winner=self.winner,
            first_player=self.first_player,
        )

    def is_terminal(self) -> bool:
        """游戏是否已结束"""
        return self.phase == GamePhase.FINISHED

    def get_winner(self) -> Optional[str]:
        """获取胜者ID（若游戏已结束）"""
        return self.winner

    def get_opponent(self, player_id: str) -> str:
        """获取对手ID"""
        if player_id == "player_1":
            return "player_2"
        elif player_id == "player_2":
            return "player_1"
        else:
            raise InvalidPlayerError(player_id)

    def to_dict(self) -> dict:
        """
        序列化为字典，用于保存对局回放。

        Returns:
            dict: 完整的游戏状态
        """
        return {
            "boards": {
                "player_1": self.boards["player_1"].to_dict(),
                "player_2": self.boards["player_2"].to_dict(),
            },
            "called_numbers": list(self.called_numbers),
            "current_player": self.current_player,
            "phase": self.phase.value,
            "winner": self.winner,
            "turn_count": self.turn_count,
            "move_history": [m.to_dict() for m in self.move_history],
            "first_player": self.first_player,
            "p1_lines": self._p1_lines,
            "p2_lines": self._p2_lines,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        """
        从字典反序列化，用于加载对局回放。

        Args:
            data: to_dict()生成的字典

        Returns:
            GameState: 恢复的游戏状态
        """
        game = cls.__new__(cls)
        game.boards = {
            "player_1": Board.from_dict(data["boards"]["player_1"]),
            "player_2": Board.from_dict(data["boards"]["player_2"]),
        }
        game.called_numbers = data["called_numbers"]
        game._called_set = set(data["called_numbers"])
        game.current_player = data["current_player"]
        game.phase = GamePhase(data["phase"])
        game.winner = data["winner"]
        game.turn_count = data["turn_count"]
        game.move_history = [Move.from_dict(m) for m in data["move_history"]]
        game.first_player = data.get("first_player", "player_1")
        game._p1_lines = data.get("p1_lines", 0)
        game._p2_lines = data.get("p2_lines", 0)
        return game

    def __repr__(self) -> str:
        return (
            f"GameState(phase={self.phase.value}, turn={self.turn_count}, "
            f"current={self.current_player}, p1_lines={self._p1_lines}, "
            f"p2_lines={self._p2_lines})"
        )
