"""UI模块测试——棋盘渲染与展示"""

import pytest
from engine.board import Board
from engine.rules import Rules, LINES
from ui.renderer import BoardRenderer


class TestBoardRenderer:
    """棋盘渲染器测试"""

    def test_render_text_basic(self):
        """文本渲染基础测试"""
        board = Board(seed=42)
        rendered = BoardRenderer.render_text(board)
        assert len(rendered) > 0
        assert "C1" in rendered or "R1" in rendered  # 列/行标签

    def test_render_text_with_marked(self):
        """标记后渲染"""
        board = Board(seed=42)
        board.mark(board.get_cell(0, 0))
        rendered = BoardRenderer.render_text(board)
        assert "✗" in rendered

    def test_render_html_basic(self):
        """HTML渲染基础测试"""
        board = Board(seed=42)
        rendered = BoardRenderer.render_html(board)
        assert "<table" in rendered
        assert "board-table" in rendered

    def test_render_html_marked_cells(self):
        """HTML标记单元格"""
        board = Board(seed=42)
        num = board.get_cell(2, 2)
        board.mark(num)
        rendered = BoardRenderer.render_html(board)
        assert "marked" in rendered

    def test_render_html_highlight(self):
        """HTML高亮测试"""
        board = Board(seed=42)
        num = board.get_cell(1, 1)
        rendered = BoardRenderer.render_html_highlight(board, highlight_number=num)
        assert "highlight" in rendered
        assert str(num) in rendered

    def test_render_line_summary(self):
        """线进度摘要渲染"""
        board = Board(seed=42)
        line_details = Rules.get_all_line_details(board)
        rendered = BoardRenderer.render_line_summary(line_details)
        assert len(rendered) > 0
        assert "行" in rendered or "row" in rendered.lower()
        assert "■" in rendered or "□" in rendered

    def test_render_line_summary_completed_lines(self):
        """完成线的摘要渲染"""
        board = Board(seed=42)
        # 完成一行
        for c in range(5):
            board.mark(board.get_cell(2, c))
        line_details = Rules.get_all_line_details(board)
        rendered = BoardRenderer.render_line_summary(line_details)
        assert "27ae60" in rendered  # 绿色（完成）

    def test_render_progress_bar(self):
        """进度条渲染"""
        rendered = BoardRenderer.render_progress_bar(3, 5, "测试")
        assert "60%" in rendered or "60" in rendered
        assert "测试" in rendered

    def test_render_progress_bar_complete(self):
        """满进度条"""
        rendered = BoardRenderer.render_progress_bar(5, 5)
        assert "100%" in rendered or "100" in rendered

    def test_render_text_all_formats(self):
        """各种棋盘状态的文本渲染不崩溃"""
        board = Board(seed=42)

        # 空棋盘
        assert len(BoardRenderer.render_text(board)) > 0

        # 部分标记
        for i in [1, 5, 10, 15, 20, 25]:
            board.mark(i)
        assert len(BoardRenderer.render_text(board)) > 0

        # 全部标记
        for i in range(1, 26):
            board.mark(i)
        assert len(BoardRenderer.render_text(board)) > 0
