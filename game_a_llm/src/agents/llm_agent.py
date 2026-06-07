"""LLM代理 - 使用大语言模型进行游戏决策

这是整个项目的核心代理，利用LLM的推理能力在游戏A中进行策略决策。
支持多种LLM后端（OpenAI、Anthropic）和多种人格配置。
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

# ============================================================================
# 预定义人格
# ============================================================================

PERSONAS = {
    "balanced": {
        "name": "均衡策略家",
        "description": "在进攻和防守之间动态平衡",
    },
    "aggressive": {
        "name": "激进进攻者",
        "description": "专注快速完成自己的线，较少防守",
    },
    "defensive": {
        "name": "谨慎防守者",
        "description": "优先阻断对手，稳中求胜",
    },
}


class LLMAgent(BaseAgent):
    """
    使用LLM进行决策的游戏代理。

    决策流程:
    1. 将游戏状态格式化为自然语言提示
    2. 构建system + user消息
    3. 调用LLM API获取决策
    4. 解析JSON响应，提取number和reasoning
    5. 校验合法性
    6. 失败则重试（最多max_retries次），仍失败则降级为随机选择

    用法:
        client = OpenAIClient(model="gpt-4o", api_key="...")
        agent = LLMAgent(
            player_id="player_1",
            llm_client=client,
            persona="balanced",
        )
        number, reasoning = agent.decide(observation, public_state)
    """

    def __init__(
        self,
        player_id: str = "player_1",
        llm_client: Optional[LLMClient] = None,
        model: str = "gpt-4o",
        persona: str = "balanced",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
        history_window: int = 6,
        name: str = None,
        provider: str = "openai",
        api_key: Optional[str] = None,
    ):
        """
        初始化LLM代理。

        Args:
            player_id: 玩家ID
            llm_client: LLM客户端实例（优先使用，有则忽略model/provider/api_key）
            model: 模型名称
            persona: 人格类型（"balanced", "aggressive", "defensive"）
            system_prompt: 自定义系统提示词（覆盖persona）
            temperature: 模型温度
            max_retries: 响应解析失败时的最大重试次数
            history_window: 保留的最近历史回合数
            name: 代理名称
            provider: LLM提供商（"openai"或"anthropic"）
            api_key: API密钥
        """
        persona_info = PERSONAS.get(persona, PERSONAS["balanced"])
        super().__init__(
            player_id=player_id,
            name=name or f"LLM-{persona_info['name']}",
        )

        self.persona = persona
        self.max_retries = max_retries
        self.history_window = history_window
        self.temperature = temperature

        # 初始化LLM客户端
        if llm_client:
            self._llm_client = llm_client
        elif provider == "anthropic":
            self._llm_client = AnthropicClient(
                model=model,
                api_key=api_key,
                temperature=temperature,
            )
        else:
            self._llm_client = OpenAIClient(
                model=model,
                api_key=api_key,
                temperature=temperature,
            )

        # 提示词
        self.system_prompt = system_prompt or self._build_default_prompt()

        # 对话历史
        self._history: list[dict] = []

        # Token统计
        self._total_tokens = 0
        self._total_calls = 0

    def _build_default_prompt(self) -> str:
        """根据人格构建默认系统提示词"""
        prompts = {
            "balanced": self._load_prompt("system_balanced.txt"),
            "aggressive": self._load_prompt("system_aggressive.txt"),
            "defensive": self._load_prompt("system_defensive.txt"),
        }
        return prompts.get(self.persona, prompts["balanced"])

    @staticmethod
    def _load_prompt(filename: str) -> str:
        """从配置文件加载提示词"""
        import os
        config_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "config", "prompts"
        )
        filepath = os.path.join(config_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return LLMAgent._get_fallback_prompt()

    @staticmethod
    def _get_fallback_prompt() -> str:
        """备用基础提示词（当配置文件不可用时）"""
        return """你正在玩"游戏A"，一个双人策略游戏。

规则：双方各有5x5私有网格（1-25随机排列），轮流报数，双方标记。
某行/列/对角线5个全标记=1条线完成。率先完成5条线获胜。

你必须严格返回JSON: {"number": <整数>, "reasoning": "<推理>"}
number必须是1-25之间未被报过的整数。"""

    # ====================================================================
    # 核心决策方法
    # ====================================================================

    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        """
        使用LLM进行决策（同步包装）。

        Args:
            observation: 私有观测
            public_state: 公共状态

        Returns:
            tuple[int, str]: (数字, 推理)
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中运行（例如Jupyter）
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self._decide_async(observation, public_state)
                    )
                    return future.result(timeout=self._llm_client.timeout + 10)
            else:
                return loop.run_until_complete(
                    self._decide_async(observation, public_state)
                )
        except RuntimeError:
            return asyncio.run(self._decide_async(observation, public_state))

    async def _decide_async(
        self,
        observation: Observation,
        public_state: PublicState,
    ) -> tuple[int, str]:
        """异步LLM决策核心"""
        # 构建上下文
        user_message = self._build_context(observation, public_state)

        # 构建消息列表
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        # 添加历史
        for h in self._history[-self.history_window * 2:]:
            messages.append(h)
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_message})

        # 尝试LLM调用（带重试）
        for attempt in range(self.max_retries + 1):
            try:
                # 使用结构化输出
                result = await self._llm_client.chat_with_json(
                    messages,
                    temperature=self.temperature,
                )

                number = result.get("number")
                reasoning = result.get("reasoning", "")

                # 校验
                if number is not None:
                    try:
                        number = int(number)
                    except (ValueError, TypeError):
                        logger.warning(f"LLM返回的数字无法转换为int: {number}")
                        continue

                    if Rules.is_valid_number(number, set(public_state.called_numbers)):
                        # 成功！记录历史
                        self._update_history(user_message, number, reasoning)
                        self._total_calls += 1
                        return number, reasoning
                    else:
                        logger.warning(
                            f"LLM返回了非法数字 {number}（第{attempt+1}次尝试），"
                            f"已报: {public_state.called_numbers[-5:]}"
                        )
                        # 在重试消息中告知错误
                        messages.append({
                            "role": "assistant",
                            "content": str(result),
                        })
                        messages.append({
                            "role": "user",
                            "content": (
                                f"错误：数字 {number} 不合法。"
                                f"已被报过的数字: {sorted(list(public_state.called_numbers))[-10:]}。"
                                f"请从剩余可选数字中选择。重新返回JSON。"
                            ),
                        })
                else:
                    logger.warning(f"LLM响应中缺少number字段: {result}")
                    messages.append({
                        "role": "user",
                        "content": "你的响应中缺少number字段。请严格按照JSON格式返回。",
                    })

            except ResponseParseError as e:
                logger.warning(f"响应解析失败（第{attempt+1}次尝试）: {e}")
                messages.append({
                    "role": "user",
                    "content": f"解析错误：{e}。请确保返回正确的JSON格式。",
                })
            except Exception as e:
                logger.error(f"LLM调用异常（第{attempt+1}次尝试）: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)  # 短暂等待后重试
                else:
                    break

        # 降级：所有重试都失败，随机选择一个合法数字
        legal = sorted(list(observation.legal_numbers))
        fallback_number = random.choice(legal)
        fallback_reasoning = (
            f"降级随机选择（LLM调用{self.max_retries+1}次均失败）"
        )
        logger.warning(
            f"LLMAgent降级为随机选择: {fallback_number}，"
            f"合法数字数: {len(legal)}"
        )
        return fallback_number, fallback_reasoning

    # ====================================================================
    # 上下文构建
    # ====================================================================

    def _build_context(
        self,
        observation: Observation,
        public_state: PublicState,
    ) -> str:
        """将游戏状态转换为LLM可理解的自然语言"""
        board = observation.my_board
        line_details = observation.line_details

        lines = []
        lines.append("--- 当前游戏状态 ---")
        lines.append("")
        lines.append(self._format_board(board, line_details))
        lines.append("")
        lines.append(self._format_public_info(observation, public_state))
        lines.append("")
        lines.append(self._format_legal_numbers(observation.legal_numbers))
        lines.append("")
        lines.append("请做出决策。只返回JSON: {\"number\": <数字>, \"reasoning\": \"<推理>\"}")

        return "\n".join(lines)

    def _format_board(self, board, line_details) -> str:
        """格式化棋盘为文本"""
        result = ["【你的棋盘 - 5x5网格】", ""]

        # 表格形式
        result.append("     C1    C2    C3    C4    C5")
        result.append("   ┌──────┬──────┬──────┬──────┬──────┐")

        for row in range(5):
            cells = []
            for col in range(5):
                num = board.get_cell(row, col)
                if num in board.marked:
                    cells.append("  ✗   ")
                else:
                    cells.append(f" {num:3d}  ")
            result.append(f" R{row+1} │" + "│".join(cells) + "│")
            if row < 4:
                result.append("   ├──────┼──────┼──────┼──────┼──────┤")
        result.append("   └──────┴──────┴──────┴──────┴──────┘")
        result.append(f"   已标记: {board.marked_count()}/25")

        # 线进度摘要
        result.append("")
        result.append("【各线完成进度】")
        rows_progress = "/".join(
            str(d.marked_count) for d in line_details if d.line_type == "row"
        )
        cols_progress = "/".join(
            str(d.marked_count) for d in line_details if d.line_type == "col"
        )
        diag_lines = [d for d in line_details if d.line_type == "diag"]
        diag_progress = " 主:" + str(diag_lines[0].marked_count) + "/5" if len(diag_lines) > 0 else ""
        diag_progress += " 副:" + str(diag_lines[1].marked_count) + "/5" if len(diag_lines) > 1 else ""

        result.append(f"  行进度: [{rows_progress}]/5")
        result.append(f"  列进度: [{cols_progress}]/5")
        result.append(f"  对角进度: {diag_progress}")

        # 接近完成的线
        nearly_done = [d for d in line_details if d.marked_count >= 3 and not d.is_complete]
        if nearly_done:
            result.append("")
            result.append("【接近完成的线】")
            for d in sorted(nearly_done, key=lambda x: x.marked_count, reverse=True):
                result.append(
                    f"  {d.name}: {d.marked_count}/5 完成，"
                    f"缺数字: {d.missing_numbers}"
                )

        return "\n".join(result)

    def _format_public_info(
        self,
        observation: Observation,
        public_state: PublicState,
    ) -> str:
        """格式化公共信息"""
        result = ["【公共信息】"]
        result.append(f"  已报数字序列: {public_state.called_numbers}")
        result.append(f"  你的已完成线数: {observation.my_lines}")
        result.append(f"  对手已完成线数: {observation.opponent_lines}")
        result.append(f"  当前回合: 第{public_state.turn_count+1}回合")
        result.append(f"  剩余可选: {public_state.total_numbers_left}个数字")
        result.append(f"  你是{'先手' if public_state.first_player == self.player_id else '后手'}")

        # 战况评估
        my_lines = observation.my_lines
        opp_lines = observation.opponent_lines
        if opp_lines >= 4:
            result.append(f"  ⚠️ 警告: 对手已接近胜利！({opp_lines}条线)")
        elif my_lines > opp_lines:
            result.append(f"  ✅ 你领先: {my_lines} vs {opp_lines}")
        elif my_lines == opp_lines and my_lines > 0:
            result.append(f"  ⚖️ 势均力敌: {my_lines} vs {opp_lines}")

        return "\n".join(result)

    def _format_legal_numbers(self, legal_numbers: set[int]) -> str:
        """格式化可选数字（精简版——不列全部，只列范围）"""
        sorted_nums = sorted(list(legal_numbers))
        if len(sorted_nums) <= 15:
            return f"【可选数字】({len(sorted_nums)}个): {sorted_nums}"
        else:
            return f"【可选数字】({len(sorted_nums)}个)"

    # ====================================================================
    # 历史管理
    # ====================================================================

    def _update_history(self, user_message: str, number: int, reasoning: str) -> None:
        """更新对话历史"""
        self._history.append({"role": "user", "content": user_message})
        self._history.append({
            "role": "assistant",
            "content": f'{{"number": {number}, "reasoning": "{reasoning}"}}',
        })

        # 限制历史长度
        max_messages = self.history_window * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

    def reset(self) -> None:
        """重置代理状态（新一局开始时调用）"""
        self._history = []
        self._total_tokens = 0
        self._total_calls = 0

    # ====================================================================
    # 统计信息
    # ====================================================================

    def get_stats(self) -> dict:
        """获取代理的统计信息"""
        return {
            "total_calls": self._total_calls,
            "total_tokens": self._total_tokens,
            "average_tokens_per_call": (
                self._total_tokens / self._total_calls
                if self._total_calls > 0 else 0
            ),
            "history_length": len(self._history),
            "persona": self.persona,
            "model": self._llm_client.get_model_name(),
            "provider": self._llm_client.get_provider_name(),
        }
