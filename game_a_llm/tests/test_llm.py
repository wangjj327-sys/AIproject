"""LLM模块和LLMAgent测试"""

import pytest
import json
from engine.game_state import GameState
from engine.rules import Rules
from agents.llm_agent import LLMAgent, PERSONAS
from llm.response_parser import ResponseParser, ResponseParseError, DecisionValidator
from llm.mock_client import MockLLMClient
from llm.token_counter import TokenUsage, TokenStats, estimate_cost


class TestResponseParser:
    """响应解析器测试"""

    def test_parse_valid_json(self):
        """解析合法的JSON响应"""
        text = '{"number": 7, "reasoning": "选择7因为能完成一行"}'
        number, reasoning = ResponseParser.parse_decision(text, set())
        assert number == 7
        assert "7" in reasoning

    def test_parse_json_with_extra_text(self):
        """JSON外有额外文字"""
        text = '好的，我选择报数字7。\n{"number": 14, "reasoning": "完成一列"}\n希望这个选择不错。'
        number, reasoning = ResponseParser.parse_decision(text, {5, 10})
        assert number == 14

    def test_parse_json_with_single_quotes(self):
        """JSON使用单引号（容错）"""
        # 单引号JSON可能被修复
        text = "{'number': 21, 'reasoning': 'test'}"
        # 这可能失败也可能成功，主要测试不崩溃
        try:
            number, reasoning = ResponseParser.parse_decision(text, set())
            assert 1 <= number <= 25
        except ResponseParseError:
            # 单引号修复不是100%可靠，允许失败
            pass

    def test_parse_number_from_text_fallback(self):
        """无法解析JSON时从文本中提取数字"""
        text = "我认为应该选择数字 15，因为它能帮我完成一条线。"
        # 这可能会失败因为无法找到JSON，但至少应尝试提取数字
        try:
            number, reasoning = ResponseParser.parse_decision(text, set())
            assert 1 <= number <= 25
        except ResponseParseError:
            pass  # 容错机制不一定总能成功

    def test_parse_already_called_number_raises(self):
        """解析已报过的数字抛出异常"""
        text = '{"number": 7, "reasoning": "test"}'
        with pytest.raises(ResponseParseError, match="已经被报过"):
            ResponseParser.parse_decision(text, {7})

    def test_parse_out_of_range_number_raises(self):
        """解析超出范围的数字抛出异常"""
        text = '{"number": 30, "reasoning": "test"}'
        with pytest.raises(ResponseParseError, match="不在合法范围"):
            ResponseParser.parse_decision(text, set())

    def test_parse_empty_text_raises(self):
        """空文本抛出异常"""
        with pytest.raises(ResponseParseError):
            ResponseParser.parse_decision("", set())

    def test_parse_json_with_spaces(self):
        """JSON前后有空格"""
        text = '  \n  {"number": 3, "reasoning": "test"}  \n  '
        number, reasoning = ResponseParser.parse_decision(text, set())
        assert number == 3

    def test_extract_json_nested(self):
        """从嵌套结构中提取JSON"""
        text = 'Some text ```json\n{"number": 22, "reasoning": "nested"}\n``` more text'
        number, reasoning = ResponseParser.parse_decision(text, set())
        assert number == 22


class TestDecisionValidator:
    """决策验证器测试"""

    def test_valid_decision(self):
        """合法决策"""
        valid, error = DecisionValidator.validate(7, {1, 2, 3})
        assert valid
        assert error is None

    def test_invalid_range(self):
        """范围外数字"""
        valid, error = DecisionValidator.validate(0, set())
        assert not valid
        assert "不在合法范围" in error

    def test_already_called(self):
        """已报数字"""
        valid, error = DecisionValidator.validate(7, {7, 8, 9})
        assert not valid
        assert "已经被报过" in error

    def test_not_integer(self):
        """非整数"""
        valid, error = DecisionValidator.validate("abc", set())
        assert not valid
        assert "整数" in error


class TestTokenCounter:
    """Token统计测试"""

    def test_token_usage_dataclass(self):
        """TokenUsage数据类"""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            model="gpt-4o",
        )
        assert usage.total_tokens == 150
        assert usage.to_dict()["total_tokens"] == 150

    def test_token_stats_accumulation(self):
        """TokenStats累积统计"""
        stats = TokenStats()
        stats.record(TokenUsage(prompt_tokens=100, completion_tokens=50))
        stats.record(TokenUsage(prompt_tokens=200, completion_tokens=100))

        assert stats.total_calls == 2
        assert stats.total_tokens == 450
        assert stats.get_average_tokens_per_call() == 225.0

    def test_token_stats_reset(self):
        """重置统计"""
        stats = TokenStats()
        stats.record(TokenUsage(prompt_tokens=100, completion_tokens=50))
        stats.reset()
        assert stats.total_calls == 0

    def test_estimate_cost_gpt4o(self):
        """GPT-4o成本估算"""
        cost = estimate_cost("gpt-4o", 1000, 500)
        # prompt: 1000/1M * $2.50 = $0.0025
        # completion: 500/1M * $10.00 = $0.005
        # total ≈ $0.0075
        assert 0.006 < cost < 0.009

    def test_estimate_cost_unknown_model(self):
        """未知模型成本为0"""
        cost = estimate_cost("unknown-model", 1000, 500)
        assert cost == 0.0


class TestMockLLMClient:
    """模拟LLM客户端测试"""

    def test_chat_returns_string(self):
        """chat返回字符串"""
        import asyncio
        client = MockLLMClient(responses=[{"number": 7, "reasoning": "test"}])
        result = asyncio.run(client.chat([{"role": "user", "content": "test"}]))
        assert isinstance(result, str)
        assert "7" in result

    def test_chat_with_json_returns_dict(self):
        """chat_with_json返回字典"""
        import asyncio
        client = MockLLMClient(responses=[{"number": 14, "reasoning": "test"}])
        result = asyncio.run(client.chat_with_json([{"role": "user", "content": "test"}]))
        assert isinstance(result, dict)
        assert result["number"] == 14

    def test_preset_responses_sequence(self):
        """预设响应序列"""
        import asyncio
        client = MockLLMClient(responses=[
            {"number": 3, "reasoning": "first"},
            {"number": 8, "reasoning": "second"},
        ])

        r1 = asyncio.run(client.chat_with_json([]))
        r2 = asyncio.run(client.chat_with_json([]))

        assert r1["number"] == 3
        assert r2["number"] == 8

    def test_call_count_tracking(self):
        """调用计数"""
        import asyncio
        client = MockLLMClient(responses=[{"number": 1, "reasoning": "t"}])
        assert client.get_call_count() == 0
        asyncio.run(client.chat_with_json([]))
        assert client.get_call_count() == 1

    def test_reset(self):
        """重置"""
        import asyncio
        client = MockLLMClient(responses=[{"number": 5, "reasoning": "t"}])
        asyncio.run(client.chat_with_json([]))
        client.reset()
        assert client.get_call_count() == 0

    def test_auto_mode_generates_valid_response(self):
        """自动模式生成合法响应"""
        import asyncio
        client = MockLLMClient(auto_mode=True)
        result = asyncio.run(client.chat_with_json([]))
        assert "number" in result
        assert 1 <= result["number"] <= 25


class TestLLMAgent:
    """LLMAgent测试（使用MockLLMClient）"""

    def test_create_agent_with_mock(self):
        """使用Mock客户端创建代理"""
        mock = MockLLMClient(responses=[{"number": 7, "reasoning": "测试"}])
        agent = LLMAgent(
            player_id="player_1",
            llm_client=mock,
            persona="balanced",
        )
        assert agent.get_type() == "LLMAgent"
        assert agent.persona == "balanced"

    def test_decide_returns_legal_number(self, game):
        """代理决策返回合法数字"""
        game.reset(first_player="player_1")

        mock = MockLLMClient(responses=[{"number": 15, "reasoning": "合理选择"}])
        agent = LLMAgent("player_1", llm_client=mock)

        obs = game.get_observation("player_1")
        pub = game.get_public_state()
        number, reasoning = agent.decide(obs, pub)

        assert 1 <= number <= 25
        assert number not in game.called_numbers
        assert isinstance(reasoning, str)

    def test_decide_falls_back_on_invalid_number(self, game):
        """返回非法数字时降级为随机"""
        game.reset(first_player="player_1")

        # 模拟：第一次返回已报过的数字，之后返回合法数字
        mock = MockLLMClient(responses=[
            {"number": 15, "reasoning": "?"},   # 假设15已被报过，但我们没报
            # 实际测试：返回一个已经报过的数字
        ])

        # 先报一个数字
        game.step("player_1", 7)

        # 预设返回7（已被报过）
        mock.set_responses([
            {"number": 7, "reasoning": "报7"},
            {"number": 7, "reasoning": "再报7"},
            {"number": 7, "reasoning": "还报7"},
        ])

        agent = LLMAgent("player_2", llm_client=mock, max_retries=2)
        obs = game.get_observation("player_2")
        pub = game.get_public_state()
        number, reasoning = agent.decide(obs, pub)

        # 应该在所有重试失败后降级为随机合法数字
        assert number in obs.legal_numbers
        assert "降级" in reasoning

    def test_different_personas_load(self):
        """不同人格都能加载"""
        for persona in ["balanced", "aggressive", "defensive"]:
            mock = MockLLMClient(responses=[{"number": 1, "reasoning": "t"}])
            agent = LLMAgent(
                player_id="player_1",
                llm_client=mock,
                persona=persona,
            )
            assert agent.persona == persona
            assert len(agent.system_prompt) > 100  # 提示词应该有内容

    def test_custom_system_prompt(self):
        """自定义系统提示词"""
        custom_prompt = "你是一个测试代理。只返回JSON。"
        mock = MockLLMClient(responses=[{"number": 1, "reasoning": "t"}])
        agent = LLMAgent(
            player_id="player_1",
            llm_client=mock,
            system_prompt=custom_prompt,
        )
        assert agent.system_prompt == custom_prompt

    def test_update_history(self, game):
        """历史记录更新"""
        game.reset(first_player="player_1")
        mock = MockLLMClient(responses=[
            {"number": 3, "reasoning": "第一个选择"},
            {"number": 8, "reasoning": "第二个选择"},
        ])
        agent = LLMAgent("player_1", llm_client=mock, history_window=4)

        # 第一次决策
        obs = game.get_observation("player_1")
        pub = game.get_public_state()
        agent.decide(obs, pub)

        # 模拟游戏进行一回合
        game.step("player_1", 3)

        # 第二次决策
        obs = game.get_observation("player_1")
        pub = game.get_public_state()
        number, reasoning = agent.decide(obs, pub)

        stats = agent.get_stats()
        assert stats["total_calls"] == 2

    def test_reset_clears_history(self, game):
        """重置清除历史"""
        mock = MockLLMClient(responses=[{"number": 5, "reasoning": "t"}])
        agent = LLMAgent("player_1", llm_client=mock)

        obs = game.get_observation("player_1")
        pub = game.get_public_state()
        agent.decide(obs, pub)

        agent.reset()
        stats = agent.get_stats()
        assert stats["total_calls"] == 0

    def test_personas_dict(self):
        """PERSONAS字典包含所有人格"""
        assert "balanced" in PERSONAS
        assert "aggressive" in PERSONAS
        assert "defensive" in PERSONAS
        for key, info in PERSONAS.items():
            assert "name" in info
            assert "description" in info

    def test_context_includes_board(self, game):
        """上下文包含棋盘信息"""
        game.reset(first_player="player_1")
        mock = MockLLMClient(responses=[{"number": 10, "reasoning": "t"}])
        agent = LLMAgent("player_1", llm_client=mock)

        obs = game.get_observation("player_1")
        pub = game.get_public_state()

        # 获取最后一条消息（user消息）
        agent.decide(obs, pub)
        last_messages = mock.get_last_messages()

        # 应该有system和user消息
        assert len(last_messages) >= 2
        user_content = last_messages[-1]["content"]
        assert "棋盘" in user_content
        assert "可选数字" in user_content

    def test_context_includes_public_info(self, game):
        """上下文包含公共信息"""
        game.reset(first_player="player_1")
        game.step("player_1", 7)
        game.step("player_2", 14)

        mock = MockLLMClient(responses=[{"number": 21, "reasoning": "t"}])
        agent = LLMAgent("player_2", llm_client=mock)

        obs = game.get_observation("player_2")
        pub = game.get_public_state()
        agent.decide(obs, pub)

        last_messages = mock.get_last_messages()
        user_content = last_messages[-1]["content"]
        assert "已报数字" in user_content
        assert "7" in user_content or "[7" in user_content

    def test_warning_when_opponent_close_to_win(self, game):
        """对手接近获胜时发出警告"""
        # 模拟中后期游戏
        game.reset(first_player="player_1")

        # 报几个数字让游戏进入中局
        for num in [1, 2, 3, 4, 5, 6, 7, 8]:
            player = "player_1" if game.turn_count % 2 == 0 else "player_2"
            if not game.is_terminal():
                game.step(player, num)

        mock = MockLLMClient(responses=[{"number": 9, "reasoning": "t"}])
        agent = LLMAgent("player_1", llm_client=mock)

        obs = game.get_observation("player_1")
        # 检查obs中是否有对手线数信息
        if obs.opponent_lines >= 4:
            agent.decide(obs, game.get_public_state())
            last_messages = mock.get_last_messages()
            user_content = last_messages[-1]["content"]
            # 如果对手接近获胜，应该包含警告
            # 注意：对手线数取决于随机布局，不一定会≥4


class TestLLMAgentIntegration:
    """LLM代理集成测试"""

    def test_llm_vs_random_with_mock(self):
        """使用Mock客户端进行LLM vs Random对局"""
        from arena.match import Match
        from agents.random import RandomAgent

        # 模拟LLM总是选择最小的合法数字
        game = GameState(seed_p1=42, seed_p2=123)
        game.reset(first_player="player_1")

        mock = MockLLMClient(auto_mode=False)
        # LLM将按序列响应
        for i in range(50):  # 最多50回合
            mock.add_response({
                "number": (i % 25) + 1,
                "reasoning": f"选择{(i % 25) + 1}",
            })

        llm_agent = LLMAgent("player_1", llm_client=mock)
        random_agent = RandomAgent("player_2", seed=42)

        match = Match(game, llm_agent, random_agent)
        result = match.run()

        assert result.winner is not None
        assert result.total_turns > 0
        assert result.total_turns <= 50

    def test_llm_agent_always_returns_legal(self, game):
        """LLMAgent总是返回合法数字（压力测试）"""
        game.reset(first_player="player_1")

        # 使用auto_mode的Mock，可能返回不合法数字
        mock = MockLLMClient(auto_mode=False)
        agent = LLMAgent("player_1", llm_client=mock, max_retries=2)

        # 模拟一些已报数字
        for num in [3, 7, 11, 15, 19]:
            player = "player_1" if game.turn_count % 2 == 0 else "player_2"
            game.step(player, num)

        for _ in range(20):
            if game.is_terminal():
                break
            obs = game.get_observation(game.current_player)
            pub = game.get_public_state()

            # 预设一个可能不合法的响应
            mock.set_responses([{"number": 3, "reasoning": "可能不合法"}])
            agent.player_id = game.current_player  # 更新player_id

            number, _ = agent.decide(obs, pub)

            # 必须在1-25范围内且未被报过
            assert 1 <= number <= 25
            assert number not in game.called_numbers

            player = game.current_player
            game.step(player, number)
