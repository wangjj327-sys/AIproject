"""游戏A引擎 - 规则判定模块

负责：
- 12条线的定义与检测
- 胜负判定
- 数字合法性校验
- 线详情计算
"""

from dataclasses import dataclass, field
from typing import Optional
from .board import Board

# ============================================================================
# 12条线的坐标定义
# ============================================================================

BOARD_SIZE = 5

# 5条行线
ROW_LINES: list[list[tuple[int, int]]] = [
    [(r, c) for c in range(BOARD_SIZE)]
    for r in range(BOARD_SIZE)
]

# 5条列线
COL_LINES: list[list[tuple[int, int]]] = [
    [(r, c) for r in range(BOARD_SIZE)]
    for c in range(BOARD_SIZE)
]

# 2条对角线
DIAG_LINES: list[list[tuple[int, int]]] = [
    [(i, i) for i in range(BOARD_SIZE)],              # 主对角线 (左上→右下)
    [(i, BOARD_SIZE - 1 - i) for i in range(BOARD_SIZE)],  # 副对角线 (右上→左下)
]

# 所有12条线的完整列表
LINES: list[dict] = []

# 添加行线
for idx, coords in enumerate(ROW_LINES):
    LINES.append({"name": f"row_{idx}", "type": "row", "index": idx, "coords": coords})

# 添加列线
for idx, coords in enumerate(COL_LINES):
    LINES.append({"name": f"col_{idx}", "type": "col", "index": idx, "coords": coords})

# 添加对角线
LINES.append({"name": "diag_main", "type": "diag", "index": 0, "coords": DIAG_LINES[0]})
LINES.append({"name": "diag_anti", "type": "diag", "index": 1, "coords": DIAG_LINES[1]})

# 数字到所在线的索引（用于增量更新：标记一个数字后只需检查包含它的线）
NUMBER_TO_LINE_INDICES: dict[int, list[int]] = {}
for line_idx, line in enumerate(LINES):
    for (r, c) in line["coords"]:
        # 注意：这里不能直接知道数字，因为每个Board的数字位置不同
        # 改为坐标到线的索引映射
        pass

# 坐标到所在线的索引映射
COORD_TO_LINE_INDICES: dict[tuple[int, int], list[int]] = {}
for line_idx, line in enumerate(LINES):
    for coord in line["coords"]:
        if coord not in COORD_TO_LINE_INDICES:
            COORD_TO_LINE_INDICES[coord] = []
        COORD_TO_LINE_INDICES[coord].append(line_idx)


@dataclass
class LineInfo:
    """一条线的状态信息"""
    name: str                       # 如 "row_0", "col_2", "diag_main"
    line_type: str                  # "row", "col", "diag"
    index: int                      # 该类型中的索引
    coords: list[tuple[int, int]]   # 坐标列表
    marked_count: int = 0           # 已标记格数
    total: int = 5                  # 总格数（始终为5）
    is_complete: bool = False       # 是否已完成
    missing_numbers: list[int] = field(default_factory=list)  # 还缺哪些数字


class Rules:
    """
    游戏A的规则引擎。

    纯函数设计——所有方法不依赖状态，仅接收输入参数并返回结果。
    这使规则逻辑易于测试和复用。
    """

    WIN_THRESHOLD: int = 5          # 获胜所需线数
    BOARD_SIZE: int = 5
    VALID_NUMBERS: set[int] = set(range(1, 26))

    # ========================================================================
    # 线检测
    # ========================================================================

    @staticmethod
    def check_line(board: Board, line_coords: list[tuple[int, int]]) -> bool:
        """
        检查一条线是否已完成（线上5个数字全部被标记）。

        Args:
            board: 玩家棋盘
            line_coords: 该线的5个坐标列表

        Returns:
            bool: 该线是否已完成
        """
        return all(
            board.get_cell(r, c) in board.marked
            for r, c in line_coords
        )

    @staticmethod
    def count_lines(board: Board) -> int:
        """
        计算棋盘上已完成的线的总数。

        Args:
            board: 玩家棋盘

        Returns:
            int: 已完成的线数（0-12）
        """
        count = 0
        for line in LINES:
            if Rules.check_line(board, line["coords"]):
                count += 1
        return count

    @staticmethod
    def get_line_detail(board: Board, line_coords: list[tuple[int, int]]) -> LineInfo:
        """
        获取一条线的详细信息。

        Args:
            board: 玩家棋盘
            line_coords: 线的坐标列表

        Returns:
            LineInfo: 线的详细状态
        """
        marked_count = 0
        missing = []
        for r, c in line_coords:
            num = board.get_cell(r, c)
            if num in board.marked:
                marked_count += 1
            else:
                missing.append(num)
        return LineInfo(
            name="",
            line_type="",
            index=0,
            coords=line_coords,
            marked_count=marked_count,
            total=5,
            is_complete=(marked_count == 5),
            missing_numbers=sorted(missing),
        )

    @staticmethod
    def get_all_line_details(board: Board) -> list[LineInfo]:
        """
        获取棋盘上所有12条线的详细信息。

        Args:
            board: 玩家棋盘

        Returns:
            list[LineInfo]: 12条线的详细信息列表
        """
        details = []
        for line in LINES:
            info = Rules.get_line_detail(board, line["coords"])
            info.name = line["name"]
            info.line_type = line["type"]
            info.index = line["index"]
            details.append(info)
        return details

    @staticmethod
    def get_lines_containing_position(row: int, col: int) -> list[int]:
        """
        获取包含指定坐标的所有线的索引（用于增量更新）。

        Args:
            row: 行号
            col: 列号

        Returns:
            list[int]: 包含该坐标的线的索引列表（0-11）
        """
        return COORD_TO_LINE_INDICES.get((row, col), [])

    @staticmethod
    def count_new_lines_for_number(board: Board, number: int) -> int:
        """
        计算如果在棋盘上标记某个数字，会新增多少条完成的线。

        用于代理评估不同数字的价值。

        Args:
            board: 玩家棋盘
            number: 要评估的数字

        Returns:
            int: 标记该数字后新增的完成线数
        """
        try:
            row, col = board.get_position(number)
        except ValueError:
            return 0

        if number in board.marked:
            return 0

        new_lines = 0
        line_indices = Rules.get_lines_containing_position(row, col)
        for line_idx in line_indices:
            line = LINES[line_idx]
            # 检查这条线的其他4个数字是否都已标记
            all_marked = True
            for r, c in line["coords"]:
                if (r, c) == (row, col):
                    continue
                if board.get_cell(r, c) not in board.marked:
                    all_marked = False
                    break
            if all_marked:
                new_lines += 1
        return new_lines

    # ========================================================================
    # 数字合法性
    # ========================================================================

    @staticmethod
    def is_valid_number(number: int, called_numbers: set[int]) -> bool:
        """
        验证数字是否可以报出。

        Args:
            number: 要报的数字
            called_numbers: 已被报过的数字集合

        Returns:
            bool: 是否合法
        """
        return (1 <= number <= 25) and (number not in called_numbers)

    @staticmethod
    def validate_number(number: int, called_numbers: set[int]) -> None:
        """
        验证数字合法性，不合法则抛出异常。

        Args:
            number: 要报的数字
            called_numbers: 已被报过的数字集合

        Raises:
            InvalidNumberError: 数字不在1-25范围
            NumberAlreadyCalledError: 数字已被报过
        """
        from .exceptions import InvalidNumberError, NumberAlreadyCalledError

        if not (1 <= number <= 25):
            raise InvalidNumberError(number)
        if number in called_numbers:
            raise NumberAlreadyCalledError(number)

    # ========================================================================
    # 胜负判定
    # ========================================================================

    @staticmethod
    def determine_winner(
        p1_lines: int,
        p2_lines: int,
        first_player: str = "player_1"
    ) -> Optional[str]:
        """
        根据双方已完成线数判定胜负。

        规则：
        - 需要至少一方达到WIN_THRESHOLD(5)条线
        - 线数多者胜
        - 线数相同时先手胜

        Args:
            p1_lines: 玩家1的已完成线数
            p2_lines: 玩家2的已完成线数
            first_player: 先手玩家ID

        Returns:
            str | None: 胜者ID，或None表示游戏继续
        """
        if p1_lines < Rules.WIN_THRESHOLD and p2_lines < Rules.WIN_THRESHOLD:
            return None

        if p1_lines > p2_lines:
            return "player_1"
        elif p2_lines > p1_lines:
            return "player_2"
        else:
            # 线数相同，先手胜
            return first_player

    # ========================================================================
    # 增量更新（性能优化）
    # ========================================================================

    @staticmethod
    def get_lines_gained(
        board: Board,
        number: int
    ) -> int:
        """
        计算标记一个数字后新增的线数。

        优化方法：只检查包含该数字坐标的线（最多4条），
        而非全部12条线。

        Args:
            board: 玩家棋盘（数字已被标记）
            number: 刚被标记的数字

        Returns:
            int: 新增的线数
        """
        try:
            row, col = board.get_position(number)
        except ValueError:
            return 0

        gained = 0
        line_indices = Rules.get_lines_containing_position(row, col)
        for line_idx in line_indices:
            line = LINES[line_idx]
            if Rules.check_line(board, line["coords"]):
                gained += 1
        return gained
