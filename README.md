# 🎮 游戏A — LLM决策代理系统

一个基于大语言模型的双人不完全信息博弈实验平台。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-208%20passed-success.svg)](.)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 游戏规则

| | |
|---|---|
| **棋盘** | 双方各有独立的 5×5 私有网格，数字 1-25 随机排列 |
| **回合** | 轮流报出一个 1-25 中未被报过的数字 |
| **标记** | 报数后，双方在各自网格中标记该数字 |
| **连线** | 某行 / 列 / 对角线 5 个数字全标记 = 完成 1 条线 |
| **获胜** | **率先完成 ≥5 条线的玩家获胜** |
| **信息** | 你只能看到自己的网格，对手的网格不可见；知道对手已完成多少条线 |

游戏有 12 条可能的线（5 行 + 5 列 + 2 对角线），这是一个典型的不完全信息扩展式博弈，适合作为 LLM 推理与策略决策能力的试验场。

---

## 项目结构

```
game_a_llm/
├── src/
│   ├── engine/          # 🎯 游戏引擎
│   │   ├── board.py         # 5×5棋盘（随机生成、标记、序列化）
│   │   ├── rules.py         # 规则引擎（12条线检测、胜负判定、增量更新）
│   │   ├── game_state.py    # 游戏状态管理（step、观测、回放）
│   │   └── exceptions.py    # 自定义异常类
│   │
│   ├── agents/          # 🤖 玩家代理
│   │   ├── base.py          # 代理抽象基类
│   │   ├── random.py        # 随机代理（基准线）
│   │   ├── greedy.py        # 贪心代理 + 激进/防守变体
│   │   ├── human.py         # 人类玩家（CLI输入）
│   │   ├── llm_agent.py     # LLM代理（核心决策引擎）
│   │   └── agent_factory.py # 代理工厂
│   │
│   ├── llm/             # 🧠 LLM服务层
│   │   ├── client.py        # 客户端抽象基类
│   │   ├── openai_client.py # OpenAI适配器（JSON Mode）
│   │   ├── anthropic_client.py # Anthropic适配器（Tool Use）
│   │   ├── mock_client.py   # 模拟客户端（测试用，无需API key）
│   │   ├── response_parser.py # 响应解析器（JSON提取+容错+重试）
│   │   └── token_counter.py # Token用量统计 + 成本估算
│   │
│   ├── arena/           # ⚔️ 竞技场
│   │   ├── match.py         # 单局对战管理
│   │   ├── tournament.py    # 锦标赛（循环赛、批量对战）
│   │   └── recorder.py      # 对局回放记录器
│   │
│   └── ui/              # 🖥️ 用户界面
│       ├── cli.py           # 命令行双人对战
│       ├── streamlit_app.py # Streamlit Web界面
│       └── renderer.py      # 棋盘渲染器（Text/HTML）
│
├── config/prompts/      # 📝 系统提示词模板（5套人格）
│   ├── system_base.txt
│   ├── system_balanced.txt
│   ├── system_aggressive.txt
│   ├── system_defensive.txt
│   └── system_cot.txt
│
├── scripts/             # 🔧 工具脚本
│   └── evaluate_results.py # 评估分析（胜率/ELO/报告生成）
│
├── tests/               # 🧪 测试（208个，100%通过）
│   ├── test_board.py
│   ├── test_rules.py
│   ├── test_game_state.py
│   ├── test_integration.py
│   ├── test_agents.py
│   ├── test_llm.py
│   ├── test_arena.py
│   └── test_ui.py
│
├── data/                # 📊 运行时数据
│   ├── logs/
│   ├── replays/
│   └── results/
│
├── PROJECT_OUTLINE.txt  # 详细项目大纲
├── requirements.txt     # Python依赖
└── README.md
```

---

## 快速开始

### 环境要求

- Python ≥ 3.11
- pip

### 安装

```bash
cd game_a_llm
pip install -r requirements.txt
```

### 运行测试

```bash
python -m pytest tests/ -v
# 208 passed in ~1.5s
```

### 启动 Web 界面

```bash
streamlit run src/ui/streamlit_app.py
```

支持三种模式：
- 🧑‍🤝‍🧑 **人类 vs 人类** — 两人在同一台电脑上轮流操作
- 🧑‍💻 **人类 vs AI** — 与贪心/防守/随机/LLM代理对战
- ⚔️ **AI vs AI** — 观战模式，观看两个AI对弈

### 命令行双人对战

```bash
python -m src.ui.cli
```

---

## 使用指南

### 1. 游戏引擎

```python
from engine import GameState

# 创建并初始化游戏
game = GameState()
game.reset(first_player="player_1")

# 执行行动
result = game.step("player_1", 7)
print(f"P1线数: {result.p1_total_lines}, P2线数: {result.p2_total_lines}")

# 获取玩家观测
obs = game.get_observation("player_1")
print(f"我的线数: {obs.my_lines}, 对手线数: {obs.opponent_lines}")

# 检查游戏是否结束
if game.is_terminal():
    print(f"胜者: {game.winner}")
```

### 2. 使用代理对战

```python
from engine import GameState
from agents import GreedyAgent, RandomAgent
from arena import Match

game = GameState()
game.reset()

agent1 = GreedyAgent("player_1", name="贪心一号")
agent2 = RandomAgent("player_2", seed=42, name="随机二号")

match = Match(game, agent1, agent2)
result = match.run()

print(f"胜者: {result.winner_name}")
print(f"回合数: {result.total_turns}")
print(f"耗时: {result.duration_seconds:.2f}s")
```

### 3. LLM 代理（模拟模式）

```python
from agents import LLMAgent
from llm import MockLLMClient

# 使用Mock客户端（无需API key，自动生成合法响应）
mock = MockLLMClient(auto_mode=True)
agent = LLMAgent(
    player_id="player_1",
    llm_client=mock,
    persona="balanced",  # balanced | aggressive | defensive
)

# 决策
obs = game.get_observation("player_1")
pub = game.get_public_state()
number, reasoning = agent.decide(obs, pub)
print(f"LLM选择: {number}, 推理: {reasoning}")
```

### 4. LLM 代理（真实API）

```bash
# 设置环境变量
export OPENAI_API_KEY="sk-..."
# 或
export ANTHROPIC_API_KEY="sk-ant-..."
```

```python
from agents import LLMAgent
from llm import OpenAIClient, AnthropicClient

# 使用OpenAI GPT-4o
client = OpenAIClient(model="gpt-4o")
agent = LLMAgent("player_1", llm_client=client, persona="balanced")

# 使用Anthropic Claude
client = AnthropicClient(model="claude-sonnet-4-6")
agent = LLMAgent("player_1", llm_client=client, persona="defensive")
```

### 5. 批量对战与评估

```python
from arena import Tournament, TournamentConfig
from agents import GreedyAgent, RandomAgent

config = TournamentConfig(
    n_games_per_pair=100,  # 每组对战100局
    swap_sides=True,       # 交换先手/后手
)

tournament = Tournament(config)

agents = [
    GreedyAgent(name="贪心"),
    RandomAgent(name="随机A", seed=1),
    RandomAgent(name="随机B", seed=2),
]

# 循环赛
stats = tournament.run_round_robin(agents)

# 查看排名
for r in stats.get_rankings():
    print(f"{r['rank']}. {r['name']}: 胜率 {r['win_rate']}")

# 保存结果
tournament.save_results("data/results/tournament_001.json")
```

### 6. 分析评估报告

```bash
python scripts/evaluate_results.py data/results/tournament_001.json --text
```

输出示例：
```
============================================================
  游戏A - 对战评估报告
============================================================
  总局数: 150

--- 代理排名 ---
排名  代理                  胜率      胜/负       ELO     均回合
------------------------------------------------------------------
1     贪心                  85.0%     85/15       1623    12.3
2     随机B                 48.0%     48/52       1487    14.8
3     随机A                 45.0%     45/55       1456    15.1

--- 先手优势 ---
  先手胜: 82 (54.7%)

--- 回合分布 ---
  最短: 5  最长: 42  平均: 14.2
============================================================
```

---

## 可用代理一览

| 代理类型 | 类名 | 策略描述 |
|---------|------|---------|
| 随机 | `RandomAgent` | 均匀随机选择数字（基线） |
| 贪心 | `GreedyAgent` | 优先完成线，最接近完成的线次之 |
| 激进贪心 | `AggressiveGreedyAgent` | 纯进攻，不考虑防守 |
| 防守贪心 | `DefensiveGreedyAgent` | 对手接近胜利时尝试阻断 |
| 人类 | `HumanAgent` | CLI 交互输入 |
| LLM均衡 | `LLMAgent(persona="balanced")` | 攻守动态平衡 |
| LLM激进 | `LLMAgent(persona="aggressive")` | 专注进攻 |
| LLM防守 | `LLMAgent(persona="defensive")` | 谨慎防守 |

---

## LLM 提示词架构

每个 LLM 代理使用两段式提示：

1. **系统提示词** — 规则说明 + 人格设定 + 策略指南 + 输出格式要求
2. **用户消息** — 当前游戏上下文
   - 可视化棋盘（文本表格）
   - 各线完成进度（行/列/对角线）
   - 接近完成的线及其缺失数字
   - 公共信息（已报数字、双方线数、领先/落后状态）
   - 剩余可选数字

代理支持自动重试：如果 LLM 返回非法数字或格式错误，会自动发送错误信息并重试（最多 2 次），全部失败则降级为随机选择。

---

## 测试覆盖

| 模块 | 测试文件 | 覆盖领域 |
|------|---------|---------|
| Board | `test_board.py` (23) | 创建、标记、位置查询、显示、序列化 |
| Rules | `test_rules.py` (44) | 12条线检测、胜负判定、数字校验、增量更新 |
| GameState | `test_game_state.py` (30) | 初始化、step、观测、异常、序列化 |
| 集成 | `test_integration.py` (11) | 完整对局、多局随机对战、回放 |
| 代理 | `test_agents.py` (24) | 随机/贪心/防守行为、100局基准对战 |
| LLM | `test_llm.py` (37) | 解析器、校验器、Mock客户端、LLMAgent |
| Arena | `test_arena.py` (17) | 锦标赛、回放记录、评估报告 |
| UI | `test_ui.py` (10) | 文本/HTML渲染、进度条、线摘要 |
| **总计** | **8文件 · 208测试** | **100%通过** |

```bash
python -m pytest tests/ -v
# 208 passed in ~1.5s
```

---

## 技术栈

| 层级 | 技术 | 用途 |
|------|------|------|
| 语言 | Python 3.11+ | 主开发语言 |
| LLM API | OpenAI / Anthropic | 真实LLM决策 |
| Web UI | Streamlit | 可视化界面 |
| 异步 | asyncio + httpx | LLM API异步调用 |
| 测试 | pytest + pytest-cov | 208个测试 |
| 数据 | pydantic | 数据结构校验 |
| 配置 | PyYAML / OmegaConf | 文件配置管理 |
| 日志 | loguru | 结构化日志 |
| 终端 | rich | 彩色终端输出 |
| 分析 | pandas + matplotlib | 数据分析与可视化 |

---

## 环境变量

| 变量 | 用途 | 必需 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | 使用 GPT-4o 时需要 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 使用 Claude 时需要 |

---

## 项目里程碑

- [x] **阶段1** — 游戏引擎核心（Board + Rules + GameState + CLI）
- [x] **阶段2** — 基准代理（Random + Greedy + Match + Factory）
- [x] **阶段3** — LLM接入（OpenAI + Anthropic + Mock + 5套提示词）
- [x] **阶段4** — 批量评估（Tournament + Recorder + Evaluator）
- [x] **阶段5** — 可视化界面（Streamlit Web UI + Renderer）

---

## License

MIT License
