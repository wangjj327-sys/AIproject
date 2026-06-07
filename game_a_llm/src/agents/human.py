"""人类玩家代理——通过命令行输入"""

from engine.game_state import Observation, PublicState
from engine.rules import Rules
from .base import BaseAgent


class HumanAgent(BaseAgent):
    """
    人类玩家代理。

    通过命令行终端获取玩家的数字输入，带有输入校验。
    适用于人机对战或人类之间的对战。
    """

    def __init__(
        self,
        player_id: str = "player_1",
        name: str = None,
        input_prompt: str = "请输入你要报的数字 (1-25): ",
    ):
        super().__init__(player_id=player_id, name=name or "人类玩家")
        self.input_prompt = input_prompt

    def decide(self, observation: Observation, public_state: PublicState) -> tuple[int, str]:
        """
        从命令行获取人类玩家的输入。

        循环直到用户输入合法数字。

        Args:
            observation: 私有观测
            public_state: 公共状态

        Returns:
            (数字, "人类玩家输入")
        """
        legal = observation.legal_numbers

        while True:
            try:
                user_input = input(self.input_prompt).strip()

                # 特殊命令
                if user_input.lower() in ("q", "quit", "exit"):
                    print("游戏退出。")
                    raise SystemExit(0)

                if user_input.lower() == "help":
                    self._print_help(legal)
                    continue

                number = int(user_input)

                if not Rules.is_valid_number(number, set(public_state.called_numbers)):
                    if number < 1 or number > 25:
                        print(f"错误: 数字必须在1-25范围内！你输入了 {number}")
                    else:
                        print(f"错误: 数字 {number} 已经被报过了！")
                    continue

                return number, f"人类玩家选择了数字 {number}"

            except ValueError:
                print(f"错误: 请输入一个整数！你输入了 '{user_input}'")
            except SystemExit:
                raise
            except Exception as e:
                print(f"未知错误: {e}")

    def _print_help(self, legal_numbers: set[int]) -> None:
        """打印帮助信息"""
        sorted_nums = sorted(list(legal_numbers))
        print(f"\n可选数字 ({len(sorted_nums)}个):")
        for i in range(0, len(sorted_nums), 10):
            chunk = sorted_nums[i:i+10]
            print("  " + " ".join(f"{n:3d}" for n in chunk))
        print()
