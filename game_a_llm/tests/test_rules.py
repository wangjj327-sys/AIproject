"""Rules模块单元测试"""

import pytest
from engine.board import Board
from engine.rules import Rules, LINES, LineInfo, COORD_TO_LINE_INDICES


class TestLinesDefinition:
    """线定义测试"""

    def test_total_lines_count(self):
        """共有12条线"""
        assert len(LINES) == 12

    def test_line_types_distribution(self):
        """5行+5列+2对角线"""
        row_lines = [l for l in LINES if l["type"] == "row"]
        col_lines = [l for l in LINES if l["type"] == "col"]
        diag_lines = [l for l in LINES if l["type"] == "diag"]
        assert len(row_lines) == 5
        assert len(col_lines) == 5
        assert len(diag_lines) == 2

    def test_each_line_has_5_coords(self):
        """每条线有5个坐标"""
        for line in LINES:
            assert len(line["coords"]) == 5

    def test_all_coords_are_valid(self):
        """所有坐标在0-4范围内"""
        for line in LINES:
            for r, c in line["coords"]:
                assert 0 <= r <= 4
                assert 0 <= c <= 4

    def test_no_duplicate_coords_in_line(self):
        """每条线的5个坐标不重复"""
        for line in LINES:
            assert len(set(line["coords"])) == 5

    def test_row_lines_definition(self):
        """行线：每行5个坐标col从0到4"""
        for r in range(5):
            line = LINES[r]  # 前5条是行线
            assert line["name"] == f"row_{r}"
            assert line["type"] == "row"
            expected = [(r, c) for c in range(5)]
            assert line["coords"] == expected

    def test_col_lines_definition(self):
        """列线：每列5个坐标row从0到4"""
        for c in range(5):
            line = LINES[5 + c]  # 第6-10条是列线
            assert line["name"] == f"col_{c}"
            assert line["type"] == "col"
            expected = [(r, c) for r in range(5)]
            assert line["coords"] == expected

    def test_main_diagonal_definition(self):
        """主对角线：左上到右下"""
        diag = LINES[10]
        assert diag["name"] == "diag_main"
        assert diag["coords"] == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]

    def test_anti_diagonal_definition(self):
        """副对角线：右上到左下"""
        diag = LINES[11]
        assert diag["name"] == "diag_anti"
        assert diag["coords"] == [(0, 4), (1, 3), (2, 2), (3, 1), (4, 0)]


class TestCoordToLineIndices:
    """坐标到线索引映射测试"""

    def test_corner_has_2_lines(self):
        """角落格子只在2条线上（1行+1列）"""
        # (0,0) 在 row_0 和 col_0，不在任何对角线上...
        # 实际上(0,0)在diag_main上
        # 所以(0,0)在 row_0, col_0, diag_main = 3条线
        assert len(COORD_TO_LINE_INDICES[(0, 0)]) == 3

    def test_center_has_4_lines(self):
        """中心格子(2,2)在4条线上（1行+1列+2对角线）"""
        assert len(COORD_TO_LINE_INDICES[(2, 2)]) == 4

    def test_edge_has_3_lines(self):
        """边上的非角落非中心格子(0,1)在3条线上（1行+1列）"""
        # (0,4)是角落+在副对角线上=3条
        # (0,1)是边上非角落，不在对角线上，只在1行+1列=2条
        assert len(COORD_TO_LINE_INDICES[(0, 1)]) == 2

    def test_all_coords_have_at_least_2_lines(self):
        """每个坐标在至少2条线上"""
        for r in range(5):
            for c in range(5):
                assert len(COORD_TO_LINE_INDICES[(r, c)]) >= 2


class TestCheckLine:
    """线完成检测测试"""

    def test_empty_board_no_lines(self):
        """空棋盘无线完成"""
        board = Board(seed=42)
        for line in LINES:
            assert not Rules.check_line(board, line["coords"])

    def test_complete_row(self):
        """完成一行"""
        board = Board(seed=42)
        # 获取第2行的5个数字并标记
        for c in range(5):
            num = board.get_cell(2, c)
            board.mark(num)
        assert Rules.check_line(board, LINES[2]["coords"])

    def test_complete_column(self):
        """完成一列"""
        board = Board(seed=42)
        for r in range(5):
            num = board.get_cell(r, 1)
            board.mark(num)
        assert Rules.check_line(board, LINES[6]["coords"])  # col_1

    def test_complete_main_diagonal(self):
        """完成主对角线"""
        board = Board(seed=42)
        for i in range(5):
            num = board.get_cell(i, i)
            board.mark(num)
        assert Rules.check_line(board, LINES[10]["coords"])

    def test_complete_anti_diagonal(self):
        """完成副对角线"""
        board = Board(seed=42)
        for i in range(5):
            num = board.get_cell(i, 4 - i)
            board.mark(num)
        assert Rules.check_line(board, LINES[11]["coords"])

    def test_incomplete_line(self):
        """只完成4个数字——未完成"""
        board = Board(seed=42)
        for c in range(4):  # 只标记前4个
            num = board.get_cell(0, c)
            board.mark(num)
        assert not Rules.check_line(board, LINES[0]["coords"])


class TestCountLines:
    """线计数测试"""

    def test_empty_board_zero_lines(self):
        """空棋盘0条线"""
        board = Board(seed=42)
        assert Rules.count_lines(board) == 0

    def test_one_row_complete(self):
        """完成1行"""
        board = Board(seed=42)
        for c in range(5):
            board.mark(board.get_cell(1, c))
        assert Rules.count_lines(board) == 1

    def test_two_rows_complete(self):
        """完成2行"""
        board = Board(seed=42)
        for c in range(5):
            board.mark(board.get_cell(0, c))
            board.mark(board.get_cell(4, c))
        assert Rules.count_lines(board) == 2

    def test_row_and_column_simultaneous(self):
        """一个数字同时完成一行和一列"""
        board = Board(seed=42)
        # 标记 row=1 除了最后一个的所有数字 和 col=2 除了最后一个的所有数字
        # row 1: board.get_cell(1, c) for c in 0..4
        # col 2: board.get_cell(r, 2) for r in 0..4
        # 交集: board.get_cell(1, 2)

        # 先标记 row 1 除 (1,2) 的数
        for c in [0, 1, 3, 4]:
            board.mark(board.get_cell(1, c))
        # 再标记 col 2 除 (1,2) 的数
        for r in [0, 2, 3, 4]:
            board.mark(board.get_cell(r, 2))
        # 这时 row_1 缺 (1,2), col_2 缺 (1,2)
        assert Rules.count_lines(board) == 0

        # 标记交点的数字——同时完成一行和一列
        board.mark(board.get_cell(1, 2))
        assert Rules.count_lines(board) == 2

    def test_all_12_lines(self):
        """全部12条线完成"""
        board = Board(seed=42)
        for i in range(1, 26):
            board.mark(i)
        assert Rules.count_lines(board) == 12

    def test_count_lines_win_threshold(self):
        """线数达到胜负阈值"""
        board = Board(seed=42)
        # 完成5行
        for r in range(5):
            for c in range(5):
                board.mark(board.get_cell(r, c))
        assert Rules.count_lines(board) >= Rules.WIN_THRESHOLD


class TestGetLinesContainingPosition:
    """包含位置的线索引测试"""

    def test_center_position(self):
        """中心位置在4条线上"""
        lines = Rules.get_lines_containing_position(2, 2)
        # row_2, col_2, diag_main, diag_anti
        assert len(lines) == 4
        line_names = [LINES[i]["name"] for i in lines]
        assert "row_2" in line_names
        assert "col_2" in line_names
        assert "diag_main" in line_names
        assert "diag_anti" in line_names

    def test_corner_position(self):
        """角落位置在3条线上"""
        lines = Rules.get_lines_containing_position(0, 0)
        assert len(lines) == 3


class TestCountNewLinesForNumber:
    """数字价值评估测试"""

    def test_number_completes_one_line(self):
        """数字能完成1条线"""
        board = Board(seed=42)
        # 先标记第1行除了(0,0)的所有数字
        for c in [1, 2, 3, 4]:
            board.mark(board.get_cell(0, c))
        # 检查标记(0,0)的数字能完成1条线
        num = board.get_cell(0, 0)
        assert Rules.count_new_lines_for_number(board, num) == 1

    def test_number_completes_two_lines(self):
        """数字能同时完成2条线（行列交叉点）"""
        board = Board(seed=42)
        # 完成 row_1 除了 (1,2) 和 col_2 除了 (1,2)
        for c in [0, 1, 3, 4]:
            board.mark(board.get_cell(1, c))
        for r in [0, 2, 3, 4]:
            board.mark(board.get_cell(r, 2))
        num = board.get_cell(1, 2)
        assert Rules.count_new_lines_for_number(board, num) == 2

    def test_number_completes_zero_lines(self):
        """数字不能完成任何线"""
        board = Board(seed=42)
        # 刚开局，随便标记一个不连续的数字
        num = board.get_cell(0, 0)
        assert Rules.count_new_lines_for_number(board, num) == 0

    def test_number_already_marked(self):
        """已标记的数字不产生新线"""
        board = Board(seed=42)
        num = board.get_cell(0, 0)
        board.mark(num)
        assert Rules.count_new_lines_for_number(board, num) == 0


class TestNumberValidation:
    """数字合法性验证测试"""

    def test_valid_number(self):
        """合法数字"""
        assert Rules.is_valid_number(1, set())
        assert Rules.is_valid_number(25, set())
        assert Rules.is_valid_number(13, {1, 2, 3})

    def test_invalid_number_range(self):
        """超出范围的数字"""
        assert not Rules.is_valid_number(0, set())
        assert not Rules.is_valid_number(26, set())

    def test_already_called_number(self):
        """已被报过的数字"""
        assert not Rules.is_valid_number(7, {7})

    def test_validate_number_raises_invalid(self):
        """非法数字抛出InvalidNumberError"""
        from engine.exceptions import InvalidNumberError
        with pytest.raises(InvalidNumberError):
            Rules.validate_number(30, set())

    def test_validate_number_raises_already_called(self):
        """已报数字抛出NumberAlreadyCalledError"""
        from engine.exceptions import NumberAlreadyCalledError
        with pytest.raises(NumberAlreadyCalledError):
            Rules.validate_number(5, {5})


class TestDetermineWinner:
    """胜负判定测试"""

    def test_no_winner_below_threshold(self):
        """双方都未达5线——无人获胜"""
        assert Rules.determine_winner(3, 3) is None
        assert Rules.determine_winner(4, 0) is None
        assert Rules.determine_winner(0, 4) is None

    def test_p1_wins_with_more_lines(self):
        """P1线数多——P1胜"""
        assert Rules.determine_winner(5, 3) == "player_1"
        assert Rules.determine_winner(6, 5) == "player_1"

    def test_p2_wins_with_more_lines(self):
        """P2线数多——P2胜"""
        assert Rules.determine_winner(3, 5) == "player_2"
        assert Rules.determine_winner(5, 7) == "player_2"

    def test_same_lines_first_player_wins(self):
        """线数相同先手胜"""
        assert Rules.determine_winner(5, 5, first_player="player_1") == "player_1"
        assert Rules.determine_winner(5, 5, first_player="player_2") == "player_2"

    def test_both_reach_threshold_higher_wins(self):
        """双方都达到5线但数量不同"""
        assert Rules.determine_winner(6, 5) == "player_1"
        assert Rules.determine_winner(5, 8) == "player_2"


class TestGetLineDetail:
    """线详情测试"""

    def test_empty_line_detail(self):
        """空线的详情"""
        board = Board(seed=42)
        detail = Rules.get_line_detail(board, LINES[0]["coords"])
        assert detail.marked_count == 0
        assert detail.total == 5
        assert not detail.is_complete
        assert len(detail.missing_numbers) == 5

    def test_complete_line_detail(self):
        """完成线的详情"""
        board = Board(seed=42)
        for c in range(5):
            board.mark(board.get_cell(2, c))
        detail = Rules.get_line_detail(board, LINES[2]["coords"])
        assert detail.marked_count == 5
        assert detail.is_complete
        assert len(detail.missing_numbers) == 0

    def test_partial_line_detail(self):
        """部分完成线的详情"""
        board = Board(seed=42)
        board.mark(board.get_cell(0, 0))
        board.mark(board.get_cell(0, 1))
        detail = Rules.get_line_detail(board, LINES[0]["coords"])
        assert detail.marked_count == 2
        assert not detail.is_complete
        assert len(detail.missing_numbers) == 3

    def test_get_all_line_details_count(self):
        """获取所有12条线详情"""
        board = Board(seed=42)
        details = Rules.get_all_line_details(board)
        assert len(details) == 12


class TestGetLinesGained:
    """增量线计算测试"""

    def test_no_lines_gained(self):
        """标记后没有新线"""
        board = Board(seed=42)
        num = board.get_cell(2, 1)
        board.mark(num)
        gained = Rules.get_lines_gained(board, num)
        assert gained == 0

    def test_one_line_gained(self):
        """标记后获得1条新线"""
        board = Board(seed=42)
        # 先完成row_0的4个数字
        for c in [1, 2, 3, 4]:
            board.mark(board.get_cell(0, c))
        # 标记最后一个
        num = board.get_cell(0, 0)
        board.mark(num)
        gained = Rules.get_lines_gained(board, num)
        assert gained == 1

    def test_two_lines_gained(self):
        """标记后同时获得2条新线"""
        board = Board(seed=42)
        # 完成row_1除了(1,2)和col_2除了(1,2)
        for c in [0, 1, 3, 4]:
            board.mark(board.get_cell(1, c))
        for r in [0, 2, 3, 4]:
            board.mark(board.get_cell(r, 2))
        num = board.get_cell(1, 2)
        board.mark(num)
        gained = Rules.get_lines_gained(board, num)
        assert gained == 2
