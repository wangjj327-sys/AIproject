"""游戏A - 命令行双人对战原型

用法:
    python -m ui.cli
"""

import sys
import os
from typing import Optional

# 将src目录加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from engine.game_state import GameState, GamePhase
from engine.rules import Rules
from engine.exceptions import (
    GameAError,
    InvalidNumberError,
    NumberAlreadyCalledError,
    GameAlreadyFinishedError,
)


# ANSI颜色代码（Windows终端也支持）
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


def clear_screen():
    """清屏"""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(game: GameState):
    """打印游戏标题和状态栏"""
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  游戏A - 双人对战{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print()

    # 状态栏
    p1_color = Colors.GREEN if game.current_player == "player_1" else Colors.RESET
    p2_color = Colors.GREEN if game.current_player == "player_2" else Colors.RESET

    pub = game.get_public_state()
    print(f"  回合: {Colors.YELLOW}{game.turn_count}{Colors.RESET}  |  "
          f"先手: {Colors.BOLD}{'玩家1' if game.first_player == 'player_1' else '玩家2'}{Colors.RESET}")
    print(f"  {p1_color}玩家1: {pub.p1_lines} 条线{Colors.RESET}  vs  "
          f"{p2_color}玩家2: {pub.p2_lines} 条线{Colors.RESET}")
    print()
    print(f"  {Colors.GRAY}已报数字: {', '.join(map(str, game.called_numbers)) if game.called_numbers else '(无)'}{Colors.RESET}")
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")


def print_board(board, player_name: str):
    """渲染一个玩家的棋盘"""
    print(f"\n  {Colors.BOLD}{player_name} 的棋盘:{Colors.RESET}")
    print(f"  {Colors.GRAY}已标记: {board.marked_count()}/25{Colors.RESET}")
    print()
    print("       C1    C2    C3    C4    C5")
    print("     ┌──────┬──────┬──────┬──────┬──────┐")

    for row in range(5):
        cells = []
        for col in range(5):
            num = board.get_cell(row, col)
            if num in board.marked:
                cells.append(f"{Colors.RED}  ✗   {Colors.RESET}")
            else:
                cells.append(f"{Colors.GREEN} {num:3d}  {Colors.RESET}")
        print(f"  R{row+1} │" + "│".join(cells) + "│")
        if row < 4:
            print("     ├──────┼──────┼──────┼──────┼──────┤")
    print("     └──────┴──────┴──────┴──────┴──────┘")
    print()


def print_line_progress(line_details):
    """打印各条线的完成进度"""
    print(f"  {Colors.BOLD}各线进度:{Colors.RESET}")
    print(f"  {Colors.GRAY}行: ", end="")
    row_details = [d for d in line_details if d.line_type == "row"]
    for d in row_details:
        if d.is_complete:
            print(f"{Colors.GREEN}[{'■'*5}]{Colors.RESET} ", end="")
        else:
            bar = "■" * d.marked_count + "□" * (5 - d.marked_count)
            print(f"[{bar}] ", end="")
    print(f"{Colors.RESET}")

    print(f"  {Colors.GRAY}列: ", end="")
    col_details = [d for d in line_details if d.line_type == "col"]
    for d in col_details:
        if d.is_complete:
            print(f"{Colors.GREEN}[{'■'*5}]{Colors.RESET} ", end="")
        else:
            bar = "■" * d.marked_count + "□" * (5 - d.marked_count)
            print(f"[{bar}] ", end="")
    print(f"{Colors.RESET}")

    print(f"  {Colors.GRAY}对角: ", end="")
    diag_details = [d for d in line_details if d.line_type == "diag"]
    for d in diag_details:
        name = "主" if d.name == "diag_main" else "副"
        if d.is_complete:
            print(f"{Colors.GREEN}{name}[{'■'*5}]{Colors.RESET} ", end="")
        else:
            bar = "■" * d.marked_count + "□" * (5 - d.marked_count)
            print(f"{name}[{bar}] ", end="")
    print(f"{Colors.RESET}\n")


def get_legal_numbers(called_numbers: list) -> set[int]:
    """获取所有合法可选数字"""
    return set(range(1, 26)) - set(called_numbers)


def print_available_numbers(legal_numbers: set[int]):
    """打印可选数字"""
    sorted_nums = sorted(list(legal_numbers))
    print(f"  {Colors.BOLD}可选数字 ({len(sorted_nums)}个):{Colors.RESET}")
    for i in range(0, len(sorted_nums), 10):
        chunk = sorted_nums[i:i+10]
        print(f"  " + " ".join(f"{n:3d}" for n in chunk))
    print()


def get_player_input(player_name: str, legal_numbers: set[int]) -> int:
    """获取玩家输入"""
    while True:
        try:
            user_input = input(f"  {Colors.BOLD}{player_name}，请报数字 (1-25): {Colors.YELLOW}").strip()
            print(Colors.RESET, end="")

            if user_input.lower() in ("q", "quit", "exit"):
                print(f"\n  {Colors.YELLOW}游戏退出。{Colors.RESET}")
                sys.exit(0)

            number = int(user_input)
            if number not in legal_numbers:
                if number < 1 or number > 25:
                    print(f"  {Colors.RED}错误: 数字必须在1-25范围内！{Colors.RESET}")
                else:
                    print(f"  {Colors.RED}错误: 数字 {number} 已经被报过了！{Colors.RESET}")
                continue

            return number
        except ValueError:
            print(f"  {Colors.RED}错误: 请输入一个整数！{Colors.RESET}")


def show_game_result(game: GameState):
    """显示游戏结果"""
    clear_screen()
    print()
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}  游戏结束！{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}")
    print()

    winner_name = "玩家1" if game.winner == "player_1" else "玩家2"
    pub = game.get_public_state()

    print(f"  {Colors.BOLD}🏆 胜者: {Colors.GREEN}{winner_name}{Colors.RESET}")
    print()
    print(f"  总回合数: {game.turn_count}")
    print(f"  玩家1 最终线数: {pub.p1_lines}")
    print(f"  玩家2 最终线数: {pub.p2_lines}")
    print()

    # 显示双方最终棋盘
    print_board(game.boards["player_1"], "玩家1 (最终)")
    print_board(game.boards["player_2"], "玩家2 (最终)")

    print(f"{Colors.BOLD}{Colors.MAGENTA}{'='*60}{Colors.RESET}")
    print()


def player_turn(game: GameState, player_id: str):
    """处理一个玩家的完整回合"""
    player_name = "玩家1" if player_id == "player_1" else "玩家2"
    player_color = Colors.GREEN if player_id == "player_1" else Colors.BLUE

    obs = game.get_observation(player_id)
    legal_numbers = obs.legal_numbers

    # 打印当前玩家可以看到的信息
    print(f"\n  {Colors.BOLD}{player_color}>>> {player_name} 的回合 <<<{Colors.RESET}")
    print_board(obs.my_board, f"{player_name}")
    print_line_progress(obs.line_details)
    print_available_numbers(legal_numbers)

    # 获取输入并执行
    number = get_player_input(player_name, legal_numbers)
    result = game.step(player_id, number)

    # 显示本轮结果
    print()
    if result.lines_gained_p1 > 0 or result.lines_gained_p2 > 0:
        print(f"  {Colors.YELLOW}本轮结果:{Colors.RESET}")
        if result.lines_gained_p1 > 0:
            print(f"    玩家1 {Colors.GREEN}+{result.lines_gained_p1} 条线{Colors.RESET} (共{result.p1_total_lines}条)")
        if result.lines_gained_p2 > 0:
            print(f"    玩家2 {Colors.GREEN}+{result.lines_gained_p2} 条线{Colors.RESET} (共{result.p2_total_lines}条)")

    if not result.is_terminal:
        print(f"\n  {Colors.GRAY}按回车键切换到下一位玩家...{Colors.RESET}")
        input()
        clear_screen()
        print_header(game)


def main():
    """主函数——运行双人对战"""
    clear_screen()

    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║              欢迎来到 游戏A！                      ║")
    print("  ║                                                    ║")
    print("  ║  规则简介:                                         ║")
    print("  ║  · 双方各有5x5的私有棋盘，内含1-25随机排列           ║")
    print("  ║  · 轮流报数，双方在各自棋盘上标记该数字              ║")
    print("  ║  · 某行/列/对角线5个全标记 = 1条线                  ║")
    print("  ║  · 率先完成5条线的玩家获胜！                        ║")
    print("  ║  · 输入 q 可随时退出                                ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}")
    print()
    input(f"  {Colors.GRAY}按回车键开始游戏...{Colors.RESET}")

    # 初始化游戏
    game = GameState()
    game.reset()
    clear_screen()
    print_header(game)

    # 游戏主循环
    try:
        while not game.is_terminal():
            player_turn(game, game.current_player)

        # 游戏结束
        show_game_result(game)

    except KeyboardInterrupt:
        print(f"\n\n  {Colors.YELLOW}游戏被中断。{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
