"""LLM代理 v2 —— 增强决策能力

相比v1的改进:
- 预计算策略分析（最优数字排行、攻防评分）
- 增强系统提示词（数字价值体系、对手建模指导）
- 贪心策略兜底（替代随机降级）
- 更清晰的上下文呈现
"""

import asyncio
import logging
import random
from typing import Optional

from engine.game_state import Observation, PublicState
from engine.rules import Rules
from agents.base import BaseAgent
from llm.client import LLMClient
from llm.openai_client import OpenAIClient
from llm.anthropic_client import AnthropicClient
from llm.response_parser import ResponseParser, ResponseParseError

logger = logging.getLogger(__name__)

PERSONAS = {
    "balanced": {"name": "均衡策略家", "description": "攻守动态平衡"},
    "aggressive": {"name": "激进进攻者", "description": "快速完成自己的线"},
    "defensive": {"name": "谨慎防守者", "description": "优先阻断对手"},
}

# ====================================================================
# 增强版系统提示词
# ====================================================================

SYSTEM_PROMPT_V2 = """你是一个精通博弈论的策略AI，正在玩一个双人竞速连线游戏"游戏A"。

## 游戏规则
- 你有5x5私有网格（1-25随机排列），对手也有自己的私有网格
- 轮流报一个1-25中未报过的数字，双方都在各自网格中标记
- 某行/列/对角线5个全标记 = 1条线完成
- 率先完成≥5条线的玩家获胜
- 你只能看到自己的网格和对手的已完成线数

## 数字价值评估体系
- 🔴 致命级：能一次完成2-4条线 → 绝对首选
- 🟠 优秀级：能完成1条线 → 优先选择
- 🟡 良好级：虽不能立即成线，但处于缺1-2个数字的线中 → 次选
- 🟢 阻碍级：对手接近获胜(≥4线)时，报对对手可能的关键数字
- ⚪ 普通级：其他合法数字 → 最后考虑

## 决策框架
1. 看「推荐数字」——我们已经帮你算好了最有价值的数字
2. 如果对手≥4线，优先考虑标记为「防守」的数字
3. 如果有标注「多线完成」的数字，优先选它们
4. 在reasoning中简述：为什么选这个数字（进攻/防守/兼备）

## 输出格式（严格JSON）
{"number": <整数>, "reasoning": "<简短推理>"}
"""


class LLMAgent(BaseAgent):
    """使用LLM进行决策的增强版代理"""

    def __init__(
        self,
        player_id: str = "player_1",
        llm_client: Optional[LLMClient] = None,
        model: str = "gpt-4o",
        persona: str = "balanced",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
        history_window: int = 4,
        name: str = None,
        provider: str = "openai",
        api_key: Optional[str] = None,
    ):
        persona_info = PERSONAS.get(persona, PERSONAS["balanced"])
        super().__init__(
            player_id=player_id,
            name=name or f"LLM-{persona_info['name']}",
        )
        self.persona = persona
        self.max_retries = max_retries
        self.history_window = history_window
        self.temperature = temperature

        if llm_client:
            self._llm_client = llm_client
        elif provider == "anthropic":
            self._llm_client = AnthropicClient(model=model, api_key=api_key, temperature=temperature)
        else:
            self._llm_client = OpenAIClient(model=model, api_key=api_key, temperature=temperature)

        self.system_prompt = system_prompt or SYSTEM_PROMPT_V2
        self._history: list[dict] = []
        self._total_calls = 0

    # ====================================================================
    # 核心决策
    # ====================================================================

    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._decide_async(observation, public_state))
                    return future.result(timeout=self._llm_client.timeout + 10)
            else:
                return loop.run_until_complete(self._decide_async(observation, public_state))
        except RuntimeError:
            return asyncio.run(self._decide_async(observation, public_state))

    async def _decide_async(self, observation, public_state) -> tuple[int, str]:
        # 预计算策略分析
        analysis = self._analyze(observation, public_state)
        user_message = self._build_context_v2(observation, public_state, analysis)

        messages = [{"role": "system", "content": self.system_prompt}]
        for h in self._history[-self.history_window * 2:]:
            messages.append(h)
        messages.append({"role": "user", "content": user_message})

        for attempt in range(self.max_retries + 1):
            try:
                result = await self._llm_client.chat_with_json(messages, temperature=self.temperature)
                number = result.get("number")
                reasoning = result.get("reasoning", "")

                if number is not None:
                    try:
                        number = int(number)
                    except (ValueError, TypeError):
                        continue

                    if Rules.is_valid_number(number, set(public_state.called_numbers)):
                        self._update_history(user_message, number, reasoning)
                        self._total_calls += 1
                        return number, reasoning
                    else:
                        messages.append({"role": "assistant", "content": str(result)})
                        messages.append({"role": "user", "content": (
                            f"错误：{number}不合法。已报数字: "
                            f"{sorted(list(public_state.called_numbers))[-8:]}。重新选择。"
                        )})
                else:
                    messages.append({"role": "user", "content": "缺少number字段，请严格按照JSON返回。"})
            except ResponseParseError as e:
                logger.warning(f"解析失败(尝试{attempt+1}): {e}")
                messages.append({"role": "user", "content": f"解析错误：{e}。请返回正确JSON。"})
            except Exception as e:
                logger.error(f"LLM异常(尝试{attempt+1}): {e}")
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(0.5)

        # 贪心策略兜底
        return self._greedy_fallback(observation, public_state)

    # ====================================================================
    # 预计算策略分析
    # ====================================================================

    def _analyze(self, observation: Observation, public_state: PublicState) -> dict:
        """
        预计算所有策略相关的数值分析，帮助LLM做出更好的决策。
        这相当于给LLM配了一个"计算器"，它只需做高层推理。
        """
        board = observation.my_board
        legal = sorted(list(observation.legal_numbers))
        line_details = observation.line_details
        opp_lines = observation.opponent_lines

        # ---- 1. 数字评分 ----
        scored = []
        for num in legal:
            new_lines = Rules.count_new_lines_for_number(board, num)
            # 计算这个数字在哪些未完成的线中
            try:
                row, col = board.get_position(num)
            except ValueError:
                continue
            line_indices = Rules.get_lines_containing_position(row, col)
            helps_lines = 0
            for li in line_indices:
                d = line_details[li]
                if not d.is_complete:
                    helps_lines += 1

            # 综合评分
            score = new_lines * 100  # 能完成线 = 最高权重
            if new_lines == 0:
                # 处于缺1个数字的线中 → 高价值
                for li in line_indices:
                    d = line_details[li]
                    if not d.is_complete and d.marked_count == 4:
                        score += 50
                    elif not d.is_complete and d.marked_count == 3:
                        score += 20
                    elif not d.is_complete:
                        score += 5

            scored.append({
                "number": num,
                "new_lines": new_lines,
                "helps_lines": helps_lines,
                "score": score,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        # ---- 2. 最佳进攻数字 ----
        top_offense = [s for s in scored if s["new_lines"] > 0][:5]
        multi_line = [s for s in top_offense if s["new_lines"] >= 2]

        # ---- 3. 接近完成的线 ----
        nearly_done = []
        for d in line_details:
            if not d.is_complete and d.marked_count >= 3:
                nearly_done.append({
                    "name": d.name,
                    "marked": d.marked_count,
                    "missing": d.missing_numbers,
                })
        nearly_done.sort(key=lambda x: x["marked"], reverse=True)

        # ---- 4. 防守评估 ----
        urgent_defense = opp_lines >= 4
        defense_candidates = []
        if urgent_defense and public_state.called_numbers:
            # 对手最近报的数——它们可能在build某条线
            recent = public_state.called_numbers[-4:]
            for rn in recent:
                for offset in [-5, -4, -1, 1, 4, 5]:
                    neighbor = rn + offset
                    if neighbor in legal and neighbor not in defense_candidates:
                        defense_candidates.append(neighbor)

        return {
            "scored": scored,
            "top_offense": top_offense,
            "multi_line": multi_line,
            "nearly_done": nearly_done,
            "urgent_defense": urgent_defense,
            "defense_candidates": defense_candidates[:5],
            "opp_lines": opp_lines,
            "my_lines": observation.my_lines,
        }

    # ====================================================================
    # 增强版上下文构建
    # ====================================================================

    def _build_context_v2(self, observation, public_state, analysis) -> str:
        """构建包含策略分析的完整上下文"""
        board = observation.my_board
        line_details = observation.line_details

        lines = []

        # ---- 棋盘 ----
        lines.append("【你的棋盘】")
        lines.append("     C1    C2    C3    C4    C5")
        lines.append("   ┌──────┬──────┬──────┬──────┬──────┐")
        for row in range(5):
            cells = []
            for col in range(5):
                num = board.get_cell(row, col)
                cells.append("  ✗   " if num in board.marked else f" {num:3d}  ")
            lines.append(f" R{row+1} │" + "│".join(cells) + "│")
            if row < 4:
                lines.append("   ├──────┼──────┼──────┼──────┼──────┤")
        lines.append("   └──────┴──────┴──────┴──────┴──────┘")

        # ---- 线进度 ----
        rows_p = "/".join(str(d.marked_count) for d in line_details if d.line_type == "row")
        cols_p = "/".join(str(d.marked_count) for d in line_details if d.line_type == "col")
        diags = [d for d in line_details if d.line_type == "diag"]
        lines.append(f"\n行: [{rows_p}]  列: [{cols_p}]  对角: 主{diags[0].marked_count}/5 副{diags[1].marked_count}/5")
        lines.append(f"已完成: {observation.my_lines}/12线  已标记: {board.marked_count()}/25")

        # ---- 公共信息 ----
        lines.append(f"\n【公共信息】")
        lines.append(f"已报序列: {public_state.called_numbers}")
        lines.append(f"对手线数: {analysis['opp_lines']}/5  |  我的线数: {analysis['my_lines']}/5")
        lines.append(f"回合: {public_state.turn_count+1}  |  剩余可选: {public_state.total_numbers_left}个")
        if public_state.first_player == self.player_id:
            lines.append("你是先手")

        # ---- 策略分析 ----
        lines.append(f"\n【策略分析】")

        if analysis["urgent_defense"]:
            lines.append("⚠️ 对手≥4线！进入紧急防守模式！")
            if analysis["defense_candidates"]:
                lines.append(f"可能的阻断数字: {analysis['defense_candidates']}")

        if analysis["multi_line"]:
            lines.append(f"🔴 能同时完成多条线的数字:")
            for s in analysis["multi_line"]:
                lines.append(f"   → 数字{s['number']}: 一次完成{s['new_lines']}条线！")

        if analysis["top_offense"]:
            lines.append(f"🟠 能完成1条线的数字: {[s['number'] for s in analysis['top_offense']]}")

        if analysis["nearly_done"]:
            lines.append(f"🟡 接近完成的线:")
            for nd in analysis["nearly_done"][:3]:
                lines.append(f"   {nd['name']}: {nd['marked']}/5, 缺{nd['missing']}")

        # ---- Top推荐 ----
        lines.append(f"\n【推荐排名（前10）】")
        for i, s in enumerate(analysis["scored"][:10]):
            tags = []
            if s["new_lines"] >= 2:
                tags.append("🔥多线")
            elif s["new_lines"] == 1:
                tags.append("⚡成线")
            elif s["score"] >= 20:
                tags.append("👌近线")
            tag_str = f" ({', '.join(tags)})" if tags else ""
            lines.append(f"  {i+1}. 数字{s['number']}: 评分{s['score']}{tag_str}")

        lines.append(f"\n请选择一个数字，返回JSON。")
        return "\n".join(lines)

    # ====================================================================
    # 贪心策略兜底
    # ====================================================================

    def _greedy_fallback(self, observation, public_state) -> tuple[int, str]:
        """LLM失败时使用贪心策略兜底（比随机选择强得多）"""
        board = observation.my_board
        legal = sorted(list(observation.legal_numbers))
        line_details = observation.line_details

        # 1. 优先：能完成最多条线的数字
        best = None
        best_lines = -1
        for num in legal:
            nl = Rules.count_new_lines_for_number(board, num)
            if nl > best_lines:
                best_lines = nl
                best = num

        if best is not None and best_lines > 0:
            return best, f"兜底贪心: 数字{best}可完成{best_lines}条线"

        # 2. 次选：最接近完成的线的缺失数字
        incomplete = [d for d in line_details if not d.is_complete]
        if incomplete:
            incomplete.sort(key=lambda d: len(d.missing_numbers))
            for line in incomplete:
                for num in line.missing_numbers:
                    if num in legal:
                        return num, f"兜底贪心: 数字{num}接近完成{line.name}"

        return legal[0], f"兜底: 选{legal[0]}"

    # ====================================================================
    # 辅助方法
    # ====================================================================

    def _update_history(self, user_message: str, number: int, reasoning: str) -> None:
        self._history.append({"role": "user", "content": user_message})
        self._history.append({"role": "assistant",
                              "content": f'{{"number": {number}, "reasoning": "{reasoning}"}}'})
        max_msgs = self.history_window * 2
        if len(self._history) > max_msgs:
            self._history = self._history[-max_msgs:]

    def reset(self) -> None:
        self._history = []
        self._total_calls = 0

    def get_stats(self) -> dict:
        return {
            "total_calls": self._total_calls,
            "history_length": len(self._history),
            "persona": self.persona,
            "model": self._llm_client.get_model_name(),
            "provider": self._llm_client.get_provider_name(),
        }
