"""UI模块 - 棋盘可视化渲染器

支持多种渲染模式：文本、Rich终端、HTML（Streamlit）

所有渲染器都是纯函数，接收Board和LineInfo列表，返回渲染结果。
"""

from engine.board import Board
from engine.rules import Rules, LineInfo


class BoardRenderer:
    """棋盘渲染器"""

    @staticmethod
    def render_text(board: Board, line_details: list[LineInfo] = None) -> str:
        """ASCII文本渲染"""
        lines = []
        lines.append("     C1    C2    C3    C4    C5")
        lines.append("   ┌──────┬──────┬──────┬──────┬──────┐")

        for row in range(5):
            cells = []
            for col in range(5):
                num = board.get_cell(row, col)
                if num in board.marked:
                    cells.append("  ✗   ")
                else:
                    cells.append(f" {num:3d}  ")
            lines.append(f" R{row+1} │" + "│".join(cells) + "│")
            if row < 4:
                lines.append("   ├──────┼──────┼──────┼──────┼──────┤")
        lines.append("   └──────┴──────┴──────┴──────┴──────┘")
        return "\n".join(lines)

    @staticmethod
    def render_html(board: Board, line_details: list[LineInfo] = None) -> str:
        """
        HTML/CSS渲染，供Streamlit使用。

        返回包含完整样式的HTML字符串。
        """
        # 生成CSS
        css = """
        <style>
        .board-table { border-collapse: collapse; margin: 10px 0; }
        .board-table td {
            width: 60px; height: 60px; text-align: center;
            font-size: 20px; font-weight: bold;
            border: 2px solid #ccc; transition: all 0.3s;
        }
        .board-table td.marked {
            background: #ff4444; color: white; font-size: 24px;
            border-color: #cc0000;
        }
        .board-table td.unmarked {
            background: #f8f9fa; color: #333;
        }
        .board-table td.unmarked:hover { background: #e3f2fd; }
        .board-table td.highlight {
            background: #fff3cd; border-color: #ffc107;
        }
        </style>
        """

        # 生成表格
        html = '<table class="board-table">'
        for row in range(5):
            html += "<tr>"
            for col in range(5):
                num = board.get_cell(row, col)
                if num in board.marked:
                    html += f'<td class="marked">✗</td>'
                else:
                    html += f'<td class="unmarked">{num}</td>'
            html += "</tr>"
        html += "</table>"

        return css + html

    @staticmethod
    def render_html_highlight(
        board: Board,
        line_details: list[LineInfo] = None,
        highlight_number: int = None,
    ) -> str:
        """
        HTML渲染，可高亮指定数字。
        """
        css = """
        <style>
        .board-table-hl { border-collapse: collapse; margin: 10px 0; }
        .board-table-hl td {
            width: 55px; height: 55px; text-align: center;
            font-size: 18px; font-weight: bold;
            border: 2px solid #ddd; border-radius: 8px;
            transition: all 0.2s;
        }
        .board-table-hl td.marked {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            color: white; font-size: 22px;
        }
        .board-table-hl td.unmarked {
            background: white; color: #2c3e50;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .board-table-hl td.highlight {
            background: #ffeaa7; border-color: #fdcb6e;
            box-shadow: 0 0 10px rgba(253,203,110,0.5);
            transform: scale(1.05);
        }
        </style>
        """
        html = '<table class="board-table-hl">'
        for row in range(5):
            html += "<tr>"
            for col in range(5):
                num = board.get_cell(row, col)
                if num in board.marked:
                    html += f'<td class="marked">✗</td>'
                elif highlight_number and num == highlight_number:
                    html += f'<td class="highlight">{num}</td>'
                else:
                    html += f'<td class="unmarked">{num}</td>'
            html += "</tr>"
        html += "</table>"
        return css + html

    @staticmethod
    def render_line_summary(line_details: list[LineInfo]) -> str:
        """渲染线进度摘要（HTML）"""
        html = '<div style="font-family: monospace; margin: 10px 0;">'

        # 行进度
        html += '<div style="margin: 5px 0;"><b>行: </b>'
        for d in line_details:
            if d.line_type != "row":
                continue
            if d.is_complete:
                html += '<span style="color: #27ae60;">■■■■■</span> '
            else:
                bar = "■" * d.marked_count + "□" * (5 - d.marked_count)
                html += f'<span style="color: #95a5a6;">{bar}</span> '
        html += "</div>"

        # 列进度
        html += '<div style="margin: 5px 0;"><b>列: </b>'
        for d in line_details:
            if d.line_type != "col":
                continue
            if d.is_complete:
                html += '<span style="color: #27ae60;">■■■■■</span> '
            else:
                bar = "■" * d.marked_count + "□" * (5 - d.marked_count)
                html += f'<span style="color: #95a5a6;">{bar}</span> '
        html += "</div>"

        # 对角线
        html += '<div style="margin: 5px 0;"><b>对角: </b>'
        for d in line_details:
            if d.line_type != "diag":
                continue
            name = "主" if d.name == "diag_main" else "副"
            if d.is_complete:
                html += f'<span style="color: #27ae60;">{name}■■■■■</span> '
            else:
                bar = "■" * d.marked_count + "□" * (5 - d.marked_count)
                html += f'<span style="color: #95a5a6;">{name}{bar}</span> '
        html += "</div></div>"

        return html

    @staticmethod
    def render_progress_bar(value: int, total: int, label: str = "") -> str:
        """渲染进度条（HTML）"""
        pct = value / total * 100 if total > 0 else 0
        color = "#27ae60" if pct >= 100 else "#3498db" if pct >= 50 else "#f39c12"
        html = f"""
        <div style="margin: 5px 0;">
            <span style="display: inline-block; width: 60px;">{label}</span>
            <div style="display: inline-block; width: 200px; height: 20px;
                 background: #ecf0f1; border-radius: 10px; overflow: hidden;">
                <div style="width: {pct}%; height: 100%; background: {color};
                     border-radius: 10px; transition: width 0.5s;">
                </div>
            </div>
            <span style="margin-left: 8px;">{value}/{total}</span>
        </div>
        """
        return html
