"""玩家代理模块"""
from .base import BaseAgent
from .random import RandomAgent
from .greedy import GreedyAgent, AggressiveGreedyAgent, DefensiveGreedyAgent
from .human import HumanAgent
from .llm_agent import LLMAgent, PERSONAS
from .agent_factory import AgentFactory, AGENT_REGISTRY

__all__ = [
    "BaseAgent",
    "RandomAgent",
    "GreedyAgent",
    "AggressiveGreedyAgent",
    "DefensiveGreedyAgent",
    "HumanAgent",
    "LLMAgent",
    "PERSONAS",
    "AgentFactory",
    "AGENT_REGISTRY",
]
