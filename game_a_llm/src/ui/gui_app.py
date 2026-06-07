"""游戏A - 原生Python GUI应用

基于 tkinter，无需额外安装，直接运行:
    python src/ui/gui_app.py
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tkinter as tk
from tkinter import ttk, messagebox

from engine.game_state import GameState, GamePhase
from engine.rules import Rules
from agents.random import RandomAgent
from agents.greedy import GreedyAgent, DefensiveGreedyAgent


COLORS = {
    "bg": "#1a1a2e",
    "card_bg": "#16213e",
    "p1_accent": "#4fc3f7",
    "p2_accent": "#ef5350",
    "text": "#e0e0e0",
    "text_dim": "#9e9e9e",
    "gold": "#ffd740",
    "green": "#66bb6a",
    "btn_default": "#2c3e6b",
    "btn_hover": "#3d5a99",
    "btn_disabled": "#3a3a4a",
    "marked_bg": "#c62828",
    "unmarked_bg": "#263238",
    "cell_text": "#ffffff",
    "grid_line": "#34515e",
    "header": "#0f3460",
    "progress_fill": "#4fc3f7",
}


class GameAApp:
    def __init__(self, root):
        self.root = root
        self.root.title("游戏A - LLM决策系统")
        self.root.geometry("1100x850")
        self.root.configure(bg=COLORS["bg"])
        self.root.minsize(950, 700)

        self.game = GameState()
        self.agent1 = None
        self.agent2 = None
        self.mode = tk.StringVar(value="human_vs_ai")
        self.ai_type = tk.StringVar(value="greedy")
        self.game_running = False
        self.ai_thinking = False

        self._build_ui()
        self._new_game()

    # ============================================================
    # 界面构建
    # ============================================================

    def _build_ui(self):
        # 顶部标题栏
        header = tk.Frame(self.root, bg=COLORS["header"], height=45)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)
        tk.Label(header, text="🎮  游戏A · LLM决策系统",
                 font=("Microsoft YaHei", 15, "bold"),
                 bg=COLORS["header"], fg=COLORS["gold"]).pack(pady=8)

        # 主区域
        main = tk.Frame(self.root, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左：玩家1
        self._build_player_panel(main, "player_1", "玩家1", COLORS["p1_accent"], 0)
        # 中：信息+设置+数字选择
        center = tk.Frame(main, bg=COLORS["bg"], width=320)
        center.grid(row=0, column=1, sticky="nsew", padx=8)
        center.grid_propagate(False)
        self._build_center_panel(center)
        # 右：玩家2
        self._build_player_panel(main, "player_2", "玩家2", COLORS["p2_accent"], 2)

        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)

        # 底部状态栏
        self.status_bar = tk.Label(
            self.root, text="准备就绪", anchor=tk.W,
            bg="#0d2137", fg=COLORS["text_dim"], font=("Microsoft YaHei", 9),
            padx=10, pady=3,
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _build_player_panel(self, parent, player_id, name, accent, col):
        frame = tk.Frame(parent, bg=COLORS["card_bg"], bd=0,
                         highlightthickness=2, highlightbackground=accent)
        frame.grid(row=0, column=col, sticky="nsew", padx=3)

        # 标题
        hf = tk.Frame(frame, bg=accent, height=32)
        hf.pack(fill=tk.X, side=tk.TOP)
        tk.Label(hf, text=name, font=("Microsoft YaHei", 12, "bold"),
                 bg=accent, fg="white").pack(pady=5)
        setattr(self, f"{player_id}_header", hf)

        # 线数
        lf = tk.Frame(frame, bg=COLORS["card_bg"])
        lf.pack(fill=tk.X, padx=10, pady=4)
        tk.Label(lf, text="已完成:", font=("Microsoft YaHei", 9),
                 bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(side=tk.LEFT)
        label = tk.Label(lf, text="0 / 5 线", font=("Microsoft YaHei", 15, "bold"),
                         bg=COLORS["card_bg"], fg=accent)
        label.pack(side=tk.LEFT, padx=5)
        setattr(self, f"{player_id}_lines_label", label)

        # 棋盘
        canvas = tk.Canvas(frame, width=280, height=280, bg=COLORS["card_bg"],
                           highlightthickness=0)
        canvas.pack(pady=5)
        setattr(self, f"{player_id}_canvas", canvas)

        # 线进度条
        tk.Label(frame, text="线进度", font=("Microsoft YaHei", 8),
                 bg=COLORS["card_bg"], fg=COLORS["text_dim"]).pack(anchor=tk.W, padx=10)
        bar_frame = tk.Frame(frame, bg=COLORS["card_bg"])
        bar_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        bars = []
        for i in range(12):
            c = tk.Canvas(bar_frame, width=270, height=10, bg=COLORS["card_bg"],
                          highlightthickness=0)
            c.pack(pady=1)
            bars.append(c)
        setattr(self, f"{player_id}_bars", bars)

    def _build_center_panel(self, parent):
        # 回合
        self.turn_label = tk.Label(parent, text="回合 1",
                                   font=("Microsoft YaHei", 16, "bold"),
                                   bg=COLORS["bg"], fg=COLORS["text"])
        self.turn_label.pack(pady=(10, 2))
        self.current_label = tk.Label(parent, text="轮到: 玩家1",
                                      font=("Microsoft YaHei", 11),
                                      bg=COLORS["bg"], fg=COLORS["p1_accent"])
        self.current_label.pack(pady=2)

        # --- 5x5 数字选择网格 ---
        ns = tk.LabelFrame(parent, text="🎯 选择数字", bg=COLORS["card_bg"],
                           fg=COLORS["gold"], font=("Microsoft YaHei", 10, "bold"),
                           padx=6, pady=6)
        ns.pack(fill=tk.X, padx=6, pady=(8, 4))

        self.num_grid = tk.Frame(ns, bg=COLORS["card_bg"])
        self.num_grid.pack()

        self.num_buttons = {}
        for i in range(1, 26):
            btn = tk.Button(
                self.num_grid, text=str(i),
                width=3, height=1,
                font=("Microsoft YaHei", 14, "bold"),
                bg=COLORS["btn_default"], fg=COLORS["cell_text"],
                activebackground=COLORS["btn_hover"],
                relief=tk.FLAT, cursor="hand2",
                command=lambda n=i: self._human_pick(n),
            )
            row = (i - 1) // 5
            col = (i - 1) % 5
            btn.grid(row=row, column=col, padx=3, pady=3)
            self.num_buttons[i] = btn

        self.num_label = tk.Label(ns, text="请从上方选择数字",
                                  font=("Microsoft YaHei", 8),
                                  bg=COLORS["card_bg"], fg=COLORS["text_dim"])
        self.num_label.pack(pady=(4, 0))

        # --- 设置 ---
        settings = tk.LabelFrame(parent, text="⚙️ 游戏设置", bg=COLORS["card_bg"],
                                 fg=COLORS["text"], font=("Microsoft YaHei", 9),
                                 padx=8, pady=8)
        settings.pack(fill=tk.X, padx=6, pady=5)

        for text, val in [("👤 人类 vs AI", "human_vs_ai"),
                          ("🧑‍🤝‍🧑 两人对战", "human_vs_human"),
                          ("⚔️  AI 观战", "ai_vs_ai")]:
            tk.Radiobutton(settings, text=text, variable=self.mode, value=val,
                           bg=COLORS["card_bg"], fg=COLORS["text"],
                           selectcolor=COLORS["btn_default"],
                           font=("Microsoft YaHei", 9),
                           command=self._new_game).pack(anchor=tk.W, pady=1)

        tk.Label(settings, text="AI 对手:", bg=COLORS["card_bg"],
                 fg=COLORS["text_dim"], font=("Microsoft YaHei", 8)).pack(pady=(6, 2))
        for text, val in [("贪心策略", "greedy"), ("防守策略", "defensive"),
                          ("随机策略", "random")]:
            tk.Radiobutton(settings, text=text, variable=self.ai_type, value=val,
                           bg=COLORS["card_bg"], fg=COLORS["text"],
                           selectcolor=COLORS["btn_default"],
                           font=("Microsoft YaHei", 8),
                           command=self._new_game).pack(anchor=tk.W, pady=1)

        tk.Button(settings, text="🔄 新游戏", command=self._new_game,
                  bg="#1565c0", fg="white", font=("Microsoft YaHei", 10, "bold"),
                  activebackground="#1976d2", relief=tk.FLAT, padx=12, pady=5,
                  cursor="hand2").pack(fill=tk.X, pady=(8, 0))

        # --- 日志 ---
        lf = tk.LabelFrame(parent, text="📜 操作记录", bg=COLORS["card_bg"],
                           fg=COLORS["text"], font=("Microsoft YaHei", 9))
        lf.pack(fill=tk.BOTH, expand=True, padx=6, pady=5)

        self.log_text = tk.Text(lf, height=6, bg="#1a1a2e", fg=COLORS["text_dim"],
                                font=("Consolas", 8), state=tk.DISABLED,
                                relief=tk.FLAT, padx=6, pady=6, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    # 游戏逻辑
    # ============================================================

    def _new_game(self):
        self.game = GameState()
        self.game.reset()
        self.game_running = True
        self.ai_thinking = False

        mode = self.mode.get()
        ai = self.ai_type.get()

        if mode == "human_vs_human":
            self.agent1 = None
            self.agent2 = None
        elif mode == "human_vs_ai":
            self.agent1 = None
            self.agent2 = self._make_agent("player_2", ai, "AI对手")
        else:
            self.agent1 = self._make_agent("player_1", "greedy", "AI-贪心")
            self.agent2 = self._make_agent("player_2", ai, f"AI-{ai}")

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self._refresh_ui()
        self._log("🎮 新游戏开始！")
        self._auto_ai_turn()

    def _make_agent(self, player_id, agent_type, name):
        if agent_type == "random":
            return RandomAgent(player_id, name=name)
        elif agent_type == "defensive":
            return DefensiveGreedyAgent(player_id, name=name)
        return GreedyAgent(player_id, name=name)

    def _human_pick(self, number):
        if not self.game_running or self.ai_thinking or self.game.is_terminal():
            return
        current = self.game.current_player
        mode = self.mode.get()
        if mode == "human_vs_ai" and current == "player_2":
            return
        if mode == "ai_vs_ai":
            return
        obs = self.game.get_observation(current)
        if number not in obs.legal_numbers:
            return
        self._do_move(current, number, f"玩家{'1' if current == 'player_1' else '2'}")

    def _do_move(self, player_id, number, who):
        try:
            result = self.game.step(player_id, number)
        except Exception as e:
            messagebox.showerror("错误", str(e))
            return

        self._log(f"{who} 报数 {number}  "
                  f"| P1:{result.p1_total_lines}线 P2:{result.p2_total_lines}线")
        if result.lines_gained_p1 > 0:
            self._log(f"  ⚡ 玩家1 +{result.lines_gained_p1}线！")
        if result.lines_gained_p2 > 0:
            self._log(f"  ⚡ 玩家2 +{result.lines_gained_p2}线！")

        self._refresh_ui()

        if self.game.is_terminal():
            self._on_game_end()
        else:
            self._auto_ai_turn()

    def _auto_ai_turn(self):
        if not self.game_running or self.game.is_terminal():
            return
        mode = self.mode.get()
        current = self.game.current_player

        agent = None
        if mode == "human_vs_ai" and current == "player_2":
            agent = self.agent2
        elif mode == "ai_vs_ai":
            agent = self.agent1 if current == "player_1" else self.agent2

        if agent is None:
            self._refresh_ui()
            return

        self.ai_thinking = True
        self.status_bar.configure(text="AI思考中...")
        self._refresh_ui()

        def callback():
            obs = self.game.get_observation(current)
            pub = self.game.get_public_state()
            try:
                number, reasoning = agent.decide(obs, pub)
            except Exception:
                legal = sorted(list(obs.legal_numbers))
                number = legal[0]

            self.ai_thinking = False
            if self.game_running and not self.game.is_terminal():
                self._do_move(current, number, agent.get_name())

        self.root.after(300, callback)

    def _on_game_end(self):
        self.game_running = False
        pub = self.game.get_public_state()
        winner_name = "玩家1" if self.game.winner == "player_1" else "玩家2"
        color = COLORS["p1_accent"] if self.game.winner == "player_1" else COLORS["p2_accent"]
        self._log(f"")
        self._log(f"🏆 {winner_name} 获胜！")
        self._log(f"   比分: P1 {pub.p1_lines}线 - P2 {pub.p2_lines}线 | 共{self.game.turn_count}回合")
        self.status_bar.configure(text=f"🏆 {winner_name} 获胜！点击「新游戏」再来一局")
        self.current_label.configure(text=f"🏆 {winner_name} 胜！", fg=color)
        self._refresh_ui()

    # ============================================================
    # UI刷新
    # ============================================================

    def _refresh_ui(self):
        if self.game is None:
            return
        pub = self.game.get_public_state()
        current = self.game.current_player
        mode = self.mode.get()

        self.turn_label.configure(text=f"回合 {self.game.turn_count + 1}")

        if self.game.is_terminal():
            winner_name = "玩家1" if self.game.winner == "player_1" else "玩家2"
            c = COLORS["p1_accent"] if self.game.winner == "player_1" else COLORS["p2_accent"]
            self.current_label.configure(text=f"🏆 {winner_name} 胜！", fg=c)
        else:
            next_name = "玩家1" if current == "player_1" else "玩家2"
            c = COLORS["p1_accent"] if current == "player_1" else COLORS["p2_accent"]
            self.current_label.configure(text=f"轮到: {next_name}", fg=c)

        self._draw_board("player_1")
        self._draw_board("player_2")
        self._refresh_buttons()

        if self.ai_thinking:
            pass
        elif self.game.is_terminal():
            pass
        else:
            is_human = (mode == "human_vs_human") or \
                       (mode == "human_vs_ai" and current == "player_1")
            if is_human:
                self.status_bar.configure(text="请从中央网格选择一个数字")
            else:
                self.status_bar.configure(text="AI思考中...")

    def _draw_board(self, player_id):
        canvas = getattr(self, f"{player_id}_canvas")
        canvas.delete("all")
        board = self.game.boards[player_id]
        obs = self.game.get_observation(player_id)
        accent = COLORS["p1_accent"] if player_id == "player_1" else COLORS["p2_accent"]

        label = getattr(self, f"{player_id}_lines_label")
        label.configure(text=f"{obs.my_lines} / 5 线", fg=accent)

        cell_size = 50
        pad_left = 15
        pad_top = 15

        for row in range(5):
            for col in range(5):
                x1 = pad_left + col * cell_size
                y1 = pad_top + row * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                num = board.get_cell(row, col)
                if num in board.marked:
                    fill = COLORS["marked_bg"]
                    text = "✗"
                else:
                    fill = COLORS["unmarked_bg"]
                    text = str(num)

                canvas.create_rectangle(x1, y1, x2, y2, fill=fill,
                                        outline=COLORS["grid_line"], width=1)
                canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text,
                                   fill="white", font=("Microsoft YaHei", 13, "bold"))

        # 高亮当前玩家
        mode = self.mode.get()
        if mode != "ai_vs_ai" and not self.game.is_terminal() and \
           self.game.current_player == player_id:
            canvas.create_rectangle(
                pad_left - 2, pad_top - 2,
                pad_left + 5 * cell_size + 2, pad_top + 5 * cell_size + 2,
                outline=COLORS["gold"], width=3,
            )

        # 线进度条
        bars = getattr(self, f"{player_id}_bars")
        for i, d in enumerate(obs.line_details):
            bar = bars[i]
            bar.delete("all")
            w = 270
            fw = int(w * d.marked_count / 5)
            color = COLORS["green"] if d.is_complete else COLORS["progress_fill"]
            if d.marked_count >= 4 and not d.is_complete:
                color = COLORS["gold"]
            bar.create_rectangle(0, 0, fw, 10, fill=color, outline="")
            bar.create_rectangle(0, 0, w, 10, fill="", outline=COLORS["grid_line"])

    def _refresh_buttons(self):
        if self.game.is_terminal():
            for btn in self.num_buttons.values():
                btn.configure(state=tk.DISABLED, bg=COLORS["btn_disabled"])
            return

        mode = self.mode.get()
        current = self.game.current_player
        human_turn = (mode == "human_vs_human") or \
                     (mode == "human_vs_ai" and current == "player_1")

        obs = None
        if not self.game.is_terminal():
            obs = self.game.get_observation(current)

        for i in range(1, 26):
            btn = self.num_buttons[i]
            if not human_turn or self.ai_thinking:
                btn.configure(state=tk.DISABLED, bg=COLORS["btn_disabled"])
            elif obs and i in obs.legal_numbers:
                btn.configure(state=tk.NORMAL, bg=COLORS["btn_default"])
            else:
                btn.configure(state=tk.DISABLED, bg=COLORS["marked_bg"])

        if mode == "ai_vs_ai":
            self.num_label.configure(text="⚔️ AI 自动对战中...")
        elif human_turn:
            self.num_label.configure(text="👆 点击上方数字")
        else:
            self.num_label.configure(text="⏳ 等待 AI 决策...")

    def _log(self, msg):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)


def main():
    root = tk.Tk()
    ttk.Style().theme_use("clam")
    GameAApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
