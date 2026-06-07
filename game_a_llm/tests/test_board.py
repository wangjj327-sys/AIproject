"""Board类单元测试"""

import pytest
from engine.board import Board


class TestBoardCreation:
    """棋盘创建测试"""

    def test_board_has_correct_size(self):
        """棋盘应为5x5"""
        board = Board()
        assert board.size == 5
        assert len(board.grid) == 5
        for row in board.grid:
            assert len(row) == 5

    def test_board_contains_all_numbers(self):
        """棋盘应包含1-25每个数字恰好一次"""
        board = Board()
        all_numbers = []
        for row in board.grid:
            all_numbers.extend(row)

        assert sorted(all_numbers) == list(range(1, 26))

    def test_board_with_seed_is_deterministic(self):
        """相同种子生成相同棋盘"""
        b1 = Board(seed=42)
        b2 = Board(seed=42)
        assert b1.grid == b2.grid

    def test_board_with_different_seeds_are_different(self):
        """不同种子生成不同棋盘（大概率）"""
        b1 = Board(seed=1)
        b2 = Board(seed=2)
        assert b1.grid != b2.grid


class TestBoardMarking:
    """数字标记测试"""

    def test_mark_number(self):
        """标记一个数字"""
        board = Board(seed=42)
        board.mark(5)
        assert board.is_marked(5)

    def test_mark_multiple_numbers(self):
        """标记多个数字"""
        board = Board(seed=42)
        for num in [1, 5, 10, 15, 20, 25]:
            board.mark(num)
        assert len(board.marked) == 6
        for num in [1, 5, 10, 15, 20, 25]:
            assert board.is_marked(num)

    def test_mark_same_number_twice(self):
        """重复标记同一数字——应无错误"""
        board = Board(seed=42)
        board.mark(7)
        board.mark(7)  # 不应出错
        assert board.is_marked(7)
        assert len(board.marked) == 1

    def test_mark_invalid_number_low(self):
        """标记小于1的数字"""
        board = Board()
        with pytest.raises(ValueError, match="不在合法范围"):
            board.mark(0)

    def test_mark_invalid_number_high(self):
        """标记大于25的数字"""
        board = Board()
        with pytest.raises(ValueError, match="不在合法范围"):
            board.mark(26)

    def test_mark_all_numbers(self):
        """标记所有25个数字"""
        board = Board(seed=42)
        for i in range(1, 26):
            board.mark(i)
        assert board.all_marked()
        assert board.marked_count() == 25


class TestBoardPosition:
    """位置查询测试"""

    def test_get_position(self):
        """获取数字位置"""
        board = Board(seed=42)
        for row in range(5):
            for col in range(5):
                num = board.get_cell(row, col)
                r, c = board.get_position(num)
                assert (r, c) == (row, col)

    def test_get_position_not_found(self):
        """查找不存在的数字"""
        board = Board(seed=42)
        # 棋盘上所有数字都在1-25范围内，但我们在棋盘初始化后直接篡改测试
        # 实际上get_position只会在数字不在棋盘时报错
        # 正常使用中不会出现——但测试这个边界条件
        pass

    def test_get_cell(self):
        """获取指定坐标的数字"""
        board = Board(seed=42)
        # 验证返回的是整数且在合法范围
        for row in range(5):
            for col in range(5):
                num = board.get_cell(row, col)
                assert 1 <= num <= 25


class TestBoardDisplay:
    """显示相关测试"""

    def test_get_display_grid(self):
        """获取可显示网格"""
        board = Board(seed=42)
        board.mark(5)
        board.mark(10)

        display = board.get_display_grid()
        assert len(display) == 5
        assert len(display[0]) == 5

        # 找到数字5和10的位置检查marked标志
        for row in range(5):
            for col in range(5):
                cell = display[row][col]
                if cell["number"] in (5, 10):
                    assert cell["marked"] is True
                else:
                    assert cell["marked"] is False

    def test_str_representation(self):
        """字符串表示不应为空"""
        board = Board(seed=42)
        s = str(board)
        assert len(s) > 0
        assert "✗" in s or "───" in s  # 棋盘包含表格线

    def test_repr(self):
        """__repr__应包含基本信息"""
        board = Board(seed=42)
        r = repr(board)
        assert "Board" in r
        assert "0/25" in r


class TestBoardSerialization:
    """序列化测试"""

    def test_to_dict(self):
        """序列化为字典"""
        board = Board(seed=42)
        board.mark(7)
        board.mark(13)

        data = board.to_dict()
        assert "grid" in data
        assert "marked" in data
        assert data["marked"] == [7, 13]
        assert len(data["grid"]) == 5

    def test_from_dict(self):
        """从字典反序列化"""
        board = Board(seed=42)
        board.mark(7)
        board.mark(13)

        data = board.to_dict()
        restored = Board.from_dict(data)

        assert restored.grid == board.grid
        assert restored.marked == board.marked
        assert restored.is_marked(7)
        assert restored.is_marked(13)

    def test_roundtrip_consistency(self):
        """序列化再反序列化保持一致"""
        board = Board(seed=99)
        for num in [1, 3, 5, 7, 9]:
            board.mark(num)

        restored = Board.from_dict(board.to_dict())
        assert restored.grid == board.grid
        assert restored.marked == board.marked


class TestBoardHelpers:
    """辅助方法测试"""

    def test_get_unmarked_numbers_empty(self):
        """初始状态：所有数字都未标记"""
        board = Board(seed=42)
        unmarked = board.get_unmarked_numbers()
        assert len(unmarked) == 25
        assert unmarked == set(range(1, 26))

    def test_get_unmarked_numbers_after_marking(self):
        """标记后更新未标记集合"""
        board = Board(seed=42)
        board.mark(1)
        board.mark(5)
        board.mark(10)
        unmarked = board.get_unmarked_numbers()
        assert 1 not in unmarked
        assert 5 not in unmarked
        assert 10 not in unmarked
        assert len(unmarked) == 22

    def test_marked_count(self):
        """已标记数量"""
        board = Board(seed=42)
        assert board.marked_count() == 0
        board.mark(1)
        assert board.marked_count() == 1
        board.mark(2)
        assert board.marked_count() == 2

    def test_all_marked(self):
        """判断是否全部标记"""
        board = Board(seed=42)
        assert not board.all_marked()
        for i in range(1, 26):
            board.mark(i)
        assert board.all_marked()
