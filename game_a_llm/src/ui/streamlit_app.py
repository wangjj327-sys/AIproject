"""游戏A - Streamlit Web 界面

启动方式:
    streamlit run src/ui/streamlit_app.py

或在项目根目录:
    cd game_a_llm
    streamlit run src/ui/streamlit_app.py
"""

import sys
import os
from pathlib import Path

# 确保 src 目录在路径中（使得 from engine... 等导入生效）
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from engine.game_state import GameState, GamePhase
from engine.rules import Rules
from agents.random import RandomAgent
from agents.greedy import GreedyAgent, DefensiveGreedyAgent
from agents.llm_agent import LLMAgent
from llm.mock_client import MockLLMClient
from arena.match import Match, MatchResult
from ui.renderer import BoardRenderer

# ============================================================================
# 页面配置
# ============================================================================

st.set_page_config(
    page_title="游戏A - LLM决策系统",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# 自定义CSS
# ============================================================================

st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .player-card {
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .player1-card { background: #e3f2fd; border: 2px solid #2196f3; }
    .player2-card { background: #fce4ec; border: 2px solid #e91e63; }
    .current-turn { box-shadow: 0 0 20px rgba(255,193,7,0.5); border: 3px solid #ffc107; }
    .line-counter {
        font-size: 24px; font-weight: bold; text-align: center;
        padding: 10px; border-radius: 8px;
    }
    .winner-banner {
        text-align: center; padding: 20px;
        background: linear-gradient(135deg, #ffd700, #ff8c00);
        color: white; border-radius: 10px; font-size: 28px;
        margin: 20px 0; animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    .number-btn {
        margin: 2px; font-size: 16px;
    }
    .move-log {
        max-height: 300px; overflow-y: auto;
        font-family: monospace; font-size: 13px;
        padding: 10px; background: #f8f9fa;
        border-radius: 5px; border: 1px solid #dee2e6;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# 会话状态初始化
# ============================================================================

SESSION_KEYS = {
    "game": None,
    "mode": "human_vs_human",
    "p1_agent_type": "human",
    "p2_agent_type": "human",
    "p1_llm_persona": "balanced",
    "p2_llm_persona": "balanced",
    "game_started": False,
    "game_message": "",
    "last_move_info": None,
}

for key, default in SESSION_KEYS.items():
    if key not in st.session_state:
        st.session_state[key] = default


def reset_game():
    """重置游戏"""
    st.session_state["game"] = GameState()
    st.session_state["game"].reset()
    st.session_state["game_started"] = True
    st.session_state["game_message"] = ""
    st.session_state["last_move_info"] = None


def create_agent(player_id: str, agent_type: str, persona: str = "balanced"):
    """创建代理"""
    if agent_type == "human":
        # 人类玩家——不创建代理，界面处理
        return None
    elif agent_type == "random":
        return RandomAgent(player_id, name=f"随机-{player_id}")
    elif agent_type == "greedy":
        return GreedyAgent(player_id, name=f"贪心-{player_id}")
    elif agent_type == "defensive":
        return DefensiveGreedyAgent(player_id, name=f"防守贪心-{player_id}")
    elif agent_type == "llm_mock":
        # 使用Mock LLM模拟（不需要API key）
        mock = MockLLMClient(auto_mode=True)
        return LLMAgent(
            player_id=player_id,
            llm_client=mock,
            persona=persona,
            name=f"LLM-{persona}-{player_id}",
        )
    return None


# ============================================================================
# 侧边栏
# ============================================================================

with st.sidebar:
    st.markdown("## 🎮 游戏设置")

    mode = st.selectbox(
        "对战模式",
        ["human_vs_human", "human_vs_ai", "ai_vs_ai"],
        format_func=lambda x: {
            "human_vs_human": "👤 人类 vs 人类",
            "human_vs_ai": "🤖 人类 vs AI",
            "ai_vs_ai": "⚔️ AI vs AI（观战）",
        }[x],
        key="mode_select",
        on_change=lambda: st.session_state.update({"game_started": False}),
    )

    if mode == "human_vs_human":
        p1_type = "human"
        p2_type = "human"
    elif mode == "human_vs_ai":
        p1_type = "human"
        p2_type = st.selectbox(
            "AI对手",
            ["greedy", "defensive", "random", "llm_mock"],
            format_func=lambda x: {
                "greedy": "贪心策略",
                "defensive": "防守策略",
                "random": "随机策略",
                "llm_mock": "LLM模拟",
            }[x],
        )
    else:  # ai_vs_ai
        p1_type = st.selectbox(
            "玩家1 AI",
            ["greedy", "defensive", "random", "llm_mock"],
            format_func=lambda x: {
                "greedy": "贪心策略",
                "defensive": "防守策略",
                "random": "随机策略",
                "llm_mock": "LLM模拟",
            }[x],
        )
        p2_type = st.selectbox(
            "玩家2 AI",
            ["random", "greedy", "defensive", "llm_mock"],
            format_func=lambda x: {
                "greedy": "贪心策略",
                "defensive": "防守策略",
                "random": "随机策略",
                "llm_mock": "LLM模拟",
            }[x],
        )

    st.session_state["mode"] = mode
    st.session_state["p1_agent_type"] = p1_type
    st.session_state["p2_agent_type"] = p2_type

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 新游戏", use_container_width=True):
            reset_game()
    with col2:
        speed = st.selectbox("速度", ["正常", "快速"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown("### 📋 规则说明")
    st.markdown("""
    - 双方各有5x5私有棋盘（1-25随机排列）
    - 轮流报数，双方标记
    - 行/列/对角线全标记 = 1条线
    - **率先完成5条线获胜**
    """)

# ============================================================================
# 主界面
# ============================================================================

st.markdown('<div class="main-header"><h1>🎮 游戏A - LLM决策系统</h1></div>', unsafe_allow_html=True)

# 初始化游戏
if not st.session_state["game_started"]:
    reset_game()

game: GameState = st.session_state["game"]

# 创建代理
p1_type = st.session_state["p1_agent_type"]
p2_type = st.session_state["p2_agent_type"]
agent1 = create_agent("player_1", p1_type, st.session_state.get("p1_llm_persona", "balanced"))
agent2 = create_agent("player_2", p2_type, st.session_state.get("p2_llm_persona", "balanced"))

# ============================================================================
# 游戏逻辑
# ============================================================================

# AI自动行动
if not game.is_terminal():
    current_player = game.current_player
    current_type = p1_type if current_player == "player_1" else p2_type

    if current_type != "human":
        agent = agent1 if current_player == "player_1" else agent2
        if agent is not None:
            # AI自动决策
            obs = game.get_observation(current_player)
            pub = game.get_public_state()

            try:
                number, reasoning = agent.decide(obs, pub)
                result = game.step(current_player, number)
                st.session_state["last_move_info"] = {
                    "player": current_player,
                    "agent": agent.get_name(),
                    "number": number,
                    "reasoning": reasoning,
                    "lines_gained_p1": result.lines_gained_p1,
                    "lines_gained_p2": result.lines_gained_p2,
                }
            except Exception as e:
                st.error(f"AI决策错误: {e}")
            st.rerun()

# ============================================================================
# 游戏面板
# ============================================================================

if game.is_terminal():
    # 游戏结束
    winner = game.winner
    winner_name = "玩家1 🟦" if winner == "player_1" else "玩家2 🟥"
    pub = game.get_public_state()
    st.markdown(
        f'<div class="winner-banner">🏆 {winner_name} 获胜！🏆<br>'
        f'<small>总回合: {game.turn_count} | P1: {pub.p1_lines}线 | P2: {pub.p2_lines}线</small></div>',
        unsafe_allow_html=True,
    )
    if st.button("🔄 再来一局", use_container_width=True):
        reset_game()
        st.rerun()

else:
    # 游戏中
    pub = game.get_public_state()
    current = game.current_player

    # 顶部状态栏
    col_score1, col_turn, col_score2 = st.columns([1, 1, 1])
    with col_score1:
        st.markdown(
            f'<div class="line-counter" style="background: #e3f2fd;">'
            f'玩家1 🟦<br>{pub.p1_lines} / 5 线</div>',
            unsafe_allow_html=True,
        )
    with col_turn:
        next_player_name = "玩家1" if current == "player_1" else "玩家2"
        st.markdown(
            f'<div style="text-align: center; padding: 10px;">'
            f'<div style="font-size: 14px; color: #666;">回合 {game.turn_count + 1}</div>'
            f'<div style="font-size: 18px; font-weight: bold;">轮到: {next_player_name}</div>'
            f'<div style="font-size: 13px; color: #999;">剩余 {pub.total_numbers_left} 个数字</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with col_score2:
        st.markdown(
            f'<div class="line-counter" style="background: #fce4ec;">'
            f'玩家2 🟥<br>{pub.p2_lines} / 5 线</div>',
            unsafe_allow_html=True,
        )

    # 棋盘展示
    col_board1, col_mid, col_board2 = st.columns([2, 1, 2])

    with col_board1:
        p1_card_class = "player-card player1-card"
        if current == "player_1":
            p1_card_class += " current-turn"

        st.markdown(f'<div class="{p1_card_class}">', unsafe_allow_html=True)
        st.markdown("### 🟦 玩家1 的棋盘")

        obs1 = game.get_observation("player_1")
        line_details1 = obs1.line_details
        board1 = game.boards["player_1"]

        # 如果是人类玩家，显示完整棋盘；如果是AI对手，也显示（仅观战模式）
        if mode == "human_vs_ai" and p2_type != "human" and game.current_player == "player_2":
            # AI回合中不暴露AI棋盘（但可以先显示部分信息）
            pass

        html_board1 = BoardRenderer.render_html(board1)
        st.markdown(html_board1, unsafe_allow_html=True)

        # 线进度
        st.markdown("**线进度**")
        html_lines1 = BoardRenderer.render_line_summary(line_details1)
        st.markdown(html_lines1, unsafe_allow_html=True)

        st.markdown(f"已标记: {board1.marked_count()}/25")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_mid:
        st.markdown("<br>" * 5, unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align: center; font-size: 40px;">⚡</div>',
            unsafe_allow_html=True,
        )

        # 移动日志
        if game.move_history:
            st.markdown("**📜 操作记录**")
            log_html = '<div class="move-log">'
            for move in game.move_history[-10:]:
                player_label = "P1" if move.player_id == "player_1" else "P2"
                color = "#2196f3" if move.player_id == "player_1" else "#e91e63"
                log_html += (
                    f'<div style="color: {color}; margin: 2px 0;">'
                    f'回合{move.player_id[-1]}: '
                    f'<b>{move.number}</b>'
                    f'</div>'
                )
            log_html += "</div>"
            st.markdown(log_html, unsafe_allow_html=True)

        # 最后行动信息
        last = st.session_state.get("last_move_info")
        if last:
            st.markdown(f"**上次行动**: {last['agent']} → {last['number']}")
            if last.get("reasoning"):
                with st.expander("查看推理"):
                    st.write(last["reasoning"])

    with col_board2:
        p2_card_class = "player-card player2-card"
        if current == "player_2":
            p2_card_class += " current-turn"

        st.markdown(f'<div class="{p2_card_class}">', unsafe_allow_html=True)
        st.markdown("### 🟥 玩家2 的棋盘")

        obs2 = game.get_observation("player_2")
        line_details2 = obs2.line_details
        board2 = game.boards["player_2"]

        html_board2 = BoardRenderer.render_html(board2)
        st.markdown(html_board2, unsafe_allow_html=True)

        # 线进度
        st.markdown("**线进度**")
        html_lines2 = BoardRenderer.render_line_summary(line_details2)
        st.markdown(html_lines2, unsafe_allow_html=True)

        st.markdown(f"已标记: {board2.marked_count()}/25")
        st.markdown("</div>", unsafe_allow_html=True)

    # 已报数字时间线
    st.markdown("---")
    if game.called_numbers:
        st.markdown("**已报数字序列**")
        cols = st.columns(min(len(game.called_numbers), 25))
        for i, num in enumerate(game.called_numbers):
            if i < len(cols):
                with cols[i]:
                    st.markdown(
                        f'<div style="background: #eee; border-radius: 50%; '
                        f'width: 30px; height: 30px; text-align: center; '
                        f'line-height: 30px; font-size: 12px; margin: 2px;">{num}</div>',
                        unsafe_allow_html=True,
                    )

    # 人类玩家输入
    if (p1_type == "human" and current == "player_1") or \
       (p2_type == "human" and current == "player_2"):
        st.markdown("---")
        st.markdown(f"### 🎯 请 {('玩家1' if current == 'player_1' else '玩家2')} 选择一个数字")

        obs = game.get_observation(current)
        legal = sorted(list(obs.legal_numbers))

        # 用按钮展示可选数字
        cols_per_row = 13
        for i in range(0, len(legal), cols_per_row):
            chunk = legal[i:i + cols_per_row]
            cols = st.columns(len(chunk))
            for j, num in enumerate(chunk):
                with cols[j]:
                    btn_label = str(num)
                    if st.button(
                        btn_label,
                        key=f"num_{num}",
                        use_container_width=True,
                        type="secondary",
                    ):
                        try:
                            result = game.step(current, num)
                            st.session_state["last_move_info"] = {
                                "player": current,
                                "agent": f"玩家{'1' if current == 'player_1' else '2'}",
                                "number": num,
                                "reasoning": "人类玩家选择",
                                "lines_gained_p1": result.lines_gained_p1,
                                "lines_gained_p2": result.lines_gained_p2,
                            }
                            st.rerun()
                        except Exception as e:
                            st.error(f"错误: {e}")

    # AI vs AI 手动步进
    if mode == "ai_vs_ai":
        st.markdown("---")
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn2:
            if st.button("▶️ 下一步", use_container_width=True):
                st.rerun()

# ============================================================================
# 底部
# ============================================================================

st.markdown("---")
st.markdown(
    '<div style="text-align: center; color: #999; font-size: 12px;">'
    '游戏A · LLM决策代理系统 · 双人不完全信息博弈</div>',
    unsafe_allow_html=True,
)
