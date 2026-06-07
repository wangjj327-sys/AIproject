"""LLM服务模块 - 响应解析器

负责从LLM的原始响应中提取、解析和验证决策数据。
支持多种格式容错和自动重试。
"""

import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ResponseParseError(Exception):
    """响应解析失败"""
    pass


class ResponseParser:
    """
    LLM响应解析器。

    功能:
    1. 从原始文本中提取JSON
    2. 解析number和reasoning字段
    3. 校验number合法性
    4. 支持容错和修复
    """

    @staticmethod
    def parse_decision(
        raw_text: str,
        called_numbers: set[int],
    ) -> tuple[int, str]:
        """
        从LLM原始响应中解析决策。

        Args:
            raw_text: LLM返回的原始文本
            called_numbers: 已被报过的数字集合（用于校验）

        Returns:
            tuple[int, str]: (数字, 推理理由)

        Raises:
            ResponseParseError: 无法解析或数字不合法
        """
        data = ResponseParser._extract_json(raw_text)

        number = ResponseParser._extract_number(data, raw_text)
        reasoning = data.get("reasoning", "")

        if not reasoning:
            reasoning = f"从响应中解析: {raw_text[:100]}"

        # 校验
        if not (1 <= number <= 25):
            raise ResponseParseError(
                f"解析出的数字 {number} 不在合法范围(1-25)内"
            )

        if number in called_numbers:
            raise ResponseParseError(
                f"解析出的数字 {number} 已经被报过了"
            )

        return number, reasoning

    @staticmethod
    def _extract_json(text: str) -> dict:
        """从文本中提取JSON对象"""
        if not text:
            raise ResponseParseError("响应为空")

        text = text.strip()

        # 方法1: 直接解析整个文本
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 方法2: 找到第一个{和最后一个}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = text[start:end + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 方法3: 使用正则匹配JSON对象
        json_match = re.search(r'\{[^{}]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # 方法4: 尝试修复常见问题（单引号、尾逗号等）
        try:
            fixed = ResponseParser._fix_json(text)
            return json.loads(fixed)
        except (json.JSONDecodeError, ResponseParseError):
            pass

        raise ResponseParseError(f"无法从响应中提取JSON: {text[:200]}")

    @staticmethod
    def _extract_number(data: dict, raw_text: str) -> int:
        """从解析后的数据中提取数字"""
        # 直接字段名
        for key in ["number", "num", "choice", "value", "pick"]:
            if key in data:
                try:
                    return int(data[key])
                except (ValueError, TypeError):
                    pass

        # 尝试从原始文本中直接找数字
        numbers = re.findall(r'\b([1-9]|1\d|2[0-5])\b', raw_text)
        if numbers:
            # 取最后一个匹配（通常是结论性的数字）
            return int(numbers[-1])

        raise ResponseParseError("无法从响应中提取数字")

    @staticmethod
    def _fix_json(text: str) -> str:
        """尝试修复格式有问题的JSON"""
        # 找到可能的JSON段
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ResponseParseError("找不到JSON边界")

        json_str = text[start:end + 1]

        # 修复单引号
        # 简单策略：将键名和字符串值的单引号替换为双引号
        # 注意：这里用简单的启发式，不保证100%正确
        in_string = False
        quote_char = None
        fixed_chars = []
        i = 0
        while i < len(json_str):
            c = json_str[i]
            if not in_string:
                if c in ('"', "'"):
                    in_string = True
                    quote_char = c
                    fixed_chars.append('"')  # 统一用双引号
                else:
                    fixed_chars.append(c)
            else:
                if c == '\\' and i + 1 < len(json_str):
                    fixed_chars.append(c)
                    fixed_chars.append(json_str[i + 1])
                    i += 1
                elif c == quote_char:
                    in_string = False
                    fixed_chars.append('"')
                else:
                    fixed_chars.append(c)
            i += 1

        return "".join(fixed_chars)


class DecisionValidator:
    """决策校验器"""

    @staticmethod
    def validate(number: int, called_numbers: set[int]) -> tuple[bool, Optional[str]]:
        """
        验证决策数字的合法性。

        Args:
            number: 要验证的数字
            called_numbers: 已被报过的数字集合

        Returns:
            tuple[bool, str|None]: (是否合法, 错误信息)
        """
        if not isinstance(number, int):
            return False, f"数字必须是整数，收到的是 {type(number).__name__}"

        if number < 1 or number > 25:
            return False, f"数字 {number} 不在合法范围(1-25)内"

        if number in called_numbers:
            return False, f"数字 {number} 已经被报过了"

        return True, None
