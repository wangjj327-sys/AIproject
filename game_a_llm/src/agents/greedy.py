"""贪心代理——启发式策略基准

策略：
1. 优先选择能立即完成一条线的数字（完成越多线越好）
2. 若无能完成线的数字，选择最接近完成的线中最需要的数字
3. 纯贪心，不考虑防守（不关注对手状态）
"""

from engine.game_state import Observation, PublicState
from engine.rules import Rules
from .base import BaseAgent


class GreedyAgent(BaseAgent):
    """
    贪心策略代理。

    总是选择能最大化自己即时收益的数字。
    不进行前瞻搜索，不做防守。

    决策优先级:
      1. 能完成最多条线的数字
      2. 最接近完成的线中的缺失数字
      3. 随机选择（保证总有合法输出）
    """

    def __init__(self, player_id: str = "player_1", name: str = None):
        super().__init__(player_id=player_id, name=name or "GreedyAgent")

    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        """
        贪心决策。

        Args:
            observation: 私有观测（包含棋盘和线详情）
            public_state: 公共状态

        Returns:
            (数字, 理由)
        """
        legal = sorted(list(observation.legal_numbers))
        board = observation.my_board
        line_details = observation.line_details

        # 第一步：评估每个合法数字的价值
        # 价值 = 选择该数字后能新完成多少条线
        best_number = None
        best_value = -1
        best_reason = ""

        for number in legal:
            value = Rules.count_new_lines_for_number(board, number)

            if value > best_value:
                best_value = value
                best_number = number

            if value > 0:
                # 记录最优先的选择
                pass

        if best_value > 0:
            return best_number, (
                f"贪心选择了数字 {best_number}，"
                f"预计可完成 {best_value} 条新线"
            )

        # 第二步：没有能直接完成线的数字
        # 选择最接近完成（缺最少数字）的线中的缺失数字
        incomplete_lines = [d for d in line_details if not d.is_complete]
        if incomplete_lines:
            # 按缺失数量升序排列（最接近完成的排最前）
            incomplete_lines.sort(key=lambda d: len(d.missing_numbers))

            # 取最接近完成的线（可能有多条同样接近的）
            best_line = incomplete_lines[0]
            min_missing = len(best_line.missing_numbers)

            # 从这些最接近完成的线中选一个缺失数字
            candidate_numbers = set()
            for line in incomplete_lines:
                if len(line.missing_numbers) == min_missing:
                    for num in line.missing_numbers:
                        if num in legal:
                            candidate_numbers.add(num)

            if candidate_numbers:
                # 如果有多个候选，检查是否有一个数字能同时接近多条线
                scored_candidates = []
                for num in candidate_numbers:
                    # 计算这个数字能帮助多少条接近完成的线
                    helps = 0
                    for line in incomplete_lines[:3]:  # 只看最接近的3条
                        if num in line.missing_numbers:
                            helps += 1
                    scored_candidates.append((helps, num))

                scored_candidates.sort(reverse=True)
                best_number = scored_candidates[0][1]
                return best_number, (
                    f"贪心选择了数字 {best_number}，"
                    f"最接近完成的线缺 {min_missing} 个数字"
                )

        # 第三步：兜底——随机选一个
        # （理论上前面两步已经覆盖所有情况，但保持安全）
        if best_number is None:
            best_number = legal[0]

        return best_number, f"贪心兜底选择了数字 {best_number}"


class AggressiveGreedyAgent(GreedyAgent):
    """
    激进贪心代理——只专注进攻。

    与GreedyAgent行为相同，但更适合作为"激进"风格的基准。
    用于对比LLM不同persona的表现。
    """

    def __init__(self, player_id: str = "player_1", name: str = None):
        super().__init__(player_id=player_id, name=name or "AggressiveGreedy")


class DefensiveGreedyAgent(BaseAgent):
    """
    防守型贪心代理——在进攻同时尝试阻断对手。

    如果对手即将获胜（线数>=4），优先尝试猜测并阻断对手可能完成的线。
    这是对GreedyAgent的防守增强版本。
    """

    def __init__(self, player_id: str = "player_1", name: str = None):
        super().__init__(player_id=player_id, name=name or "DefensiveGreedy")

    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        """防守型决策：对手接近胜利时优先阻断"""
        legal = sorted(list(observation.legal_numbers))
        board = observation.my_board
        line_details = observation.line_details

        # 检查是否需要防守
        opponent_lines = observation.opponent_lines
        need_defense = opponent_lines >= 4

        # 先用贪心找最佳进攻数字
        best_offense = None
        best_offense_value = -1

        for number in legal:
            value = Rules.count_new_lines_for_number(board, number)
            if value > best_offense_value:
                best_offense_value = value
                best_offense = number

        # 如果能直接完成线，优先进攻
        if best_offense_value > 0:
            return best_offense, (
                f"防守贪心进攻选择了数字 {best_offense}，"
                f"可完成 {best_offense_value} 条新线"
            )

        # 防守模式：对手接近胜利时
        if need_defense:
            # 简单策略：报那些"看起来可能"阻碍对手的数字
            # 由于不知道对手棋盘，只能凭公共信息猜测
            # 策略：报最近对手报过的数字附近的数字（对手可能在build某条线）
            if public_state.called_numbers:
                # 对手最近报的数字
                recent_calls = public_state.called_numbers[-3:]  # 最近3个
                # 选择与对手最近报数相近的合法数字
                candidate = None
                for recent in reversed(recent_calls):
                    # 相邻数字（可能是对手线的相邻位置）
                    for offset in [-5, -1, 1, 5]:
                        neighbor = recent + offset
                        if neighbor in legal:
                            candidate = neighbor
                            break
                    if candidate:
                        break

                if candidate:
                    return candidate, (
                        f"防守贪心阻断选择了数字 {candidate}，"
                        f"对手已有 {opponent_lines} 条线"
                    )

        # 正常贪心逻辑
        incomplete_lines = [d for d in line_details if not d.is_complete]
        if incomplete_lines:
            incomplete_lines.sort(key=lambda d: len(d.missing_numbers))
            min_missing = len(incomplete_lines[0].missing_numbers)
            candidates = set()
            for line in incomplete_lines:
                if len(line.missing_numbers) == min_missing:
                    for num in line.missing_numbers:
                        if num in legal:
                            candidates.add(num)
            if candidates:
                return min(candidates), (
                    f"防守贪心选择了数字 {min(candidates)}，"
                    f"最接近完成的线缺 {min_missing} 个"
                )

        return legal[0], f"防守贪心兜底选择了数字 {legal[0]}"
