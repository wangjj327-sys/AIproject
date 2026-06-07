"""游戏A引擎 - 棋盘/网格数据结构"""

import random
from typing import Optional


class Board:
    """
    游戏A的5x5棋盘。

    每个玩家拥有一个独立的Board实例，包含1-25的随机排列。
    游戏过程中，根据报出的数字标记相应的格子。

    Attributes:
        grid: 5x5矩阵，行优先存储，grid[row][col]
        marked: 已标记（打叉）的数字集合
        size: 棋盘尺寸（固定为5）
    """

    SIZE: int = 5
    NUM_COUNT: int = 25  # 1到25

    def __init__(self, seed: Optional[int] = None):
        """
        初始化棋盘，随机生成1-25的排列填入5x5网格。

        Args:
            seed: 可选随机种子，用于复现测试
        """
        self.size = self.SIZE
        self.grid: list[list[int]] = []
        self.marked: set[int] = set()
        self._seed = seed
        self._generate_grid(seed)

    def _generate_grid(self, seed: Optional[int] = None) -> None:
        """生成随机排列的5x5网格"""
        numbers = list(range(1, self.NUM_COUNT + 1))  # [1, 2, ..., 25]
        rng = random.Random(seed)
        rng.shuffle(numbers)

        self.grid = []
        for row in range(self.SIZE):
            start = row * self.SIZE
            end = start + self.SIZE
            self.grid.append(numbers[start:end])

    def mark(self, number: int) -> None:
        """
        标记一个数字（打叉）。

        Args:
            number: 要标记的数字（1-25）

        Raises:
            ValueError: 如果数字不在棋盘上（理论上不会发生）
        """
        if number < 1 or number > self.NUM_COUNT:
            raise ValueError(f"数字 {number} 不在合法范围(1-{self.NUM_COUNT})内")
        self.marked.add(number)

    def is_marked(self, number: int) -> bool:
        """检查数字是否已被标记"""
        return number in self.marked

    def get_position(self, number: int) -> tuple[int, int]:
        """
        获取数字在网格中的位置。

        Args:
            number: 要查找的数字

        Returns:
            (row, col) 元组

        Raises:
            ValueError: 如果数字不在网格中
        """
        for row in range(self.SIZE):
            for col in range(self.SIZE):
                if self.grid[row][col] == number:
                    return (row, col)
        raise ValueError(f"数字 {number} 不在棋盘中")

    def get_display_grid(self) -> list[list[dict]]:
        """
        返回带标记状态的可显示网格。

        Returns:
            list[list[dict]]: 每个格子包含 {'number': int, 'marked': bool}
        """
        return [
            [
                {
                    "number": self.grid[row][col],
                    "marked": self.grid[row][col] in self.marked,
                }
                for col in range(self.SIZE)
            ]
            for row in range(self.SIZE)
        ]

    def get_cell(self, row: int, col: int) -> int:
        """获取指定坐标的数字"""
        return self.grid[row][col]

    def get_unmarked_numbers(self) -> set[int]:
        """获取所有未被标记的数字"""
        all_numbers = set(range(1, self.NUM_COUNT + 1))
        return all_numbers - self.marked

    def to_dict(self) -> dict:
        """
        序列化为字典。

        Returns:
            dict: 包含grid和marked的字典
        """
        return {
            "grid": [row[:] for row in self.grid],
            "marked": sorted(list(self.marked)),
            "seed": self._seed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Board":
        """
        从字典反序列化创建Board实例。

        Args:
            data: to_dict()生成的字典

        Returns:
            Board: 新的Board实例
        """
        board = cls.__new__(cls)
        board.size = cls.SIZE
        board.grid = data["grid"]
        board.marked = set(data["marked"])
        board._seed = data.get("seed")
        return board

    def __repr__(self) -> str:
        lines_count = self.marked_count()
        return f"Board(marked={lines_count}/{self.NUM_COUNT})"

    def __str__(self) -> str:
        """格式化打印棋盘"""
        result = []
        result.append("┌──────┬──────┬──────┬──────┬──────┐")
        for row in range(self.SIZE):
            cells = []
            for col in range(self.SIZE):
                num = self.grid[row][col]
                if num in self.marked:
                    cells.append("  ✗   ")
                else:
                    cells.append(f" {num:3d}  ")
            result.append("│" + "│".join(cells) + "│")
            if row < self.SIZE - 1:
                result.append("├──────┼──────┼──────┼──────┼──────┤")
        result.append("└──────┴──────┴──────┴──────┴──────┘")
        return "\n".join(result)

    def marked_count(self) -> int:
        """已标记数字的数量"""
        return len(self.marked)

    def all_marked(self) -> bool:
        """是否所有数字都已标记"""
        return len(self.marked) == self.NUM_COUNT
