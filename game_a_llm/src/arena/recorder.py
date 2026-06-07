"""对战调度模块 - 对局记录器

负责保存和加载完整的对局回放。
使用JSON格式存储，支持压缩（可选）。
"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from engine.game_state import GameState
from .match import MatchResult


class Recorder:
    """
    对局记录器。

    保存完整的对局数据（包括双方最终棋盘、每步决策等），
    支持后续分析和回放。

    用法:
        recorder = Recorder("data/replays")
        recorder.save(match_result, game_state)

        # 加载回放
        data = recorder.load("match_abc123.json")
    """

    def __init__(self, replay_dir: str = "data/replays"):
        self.replay_dir = Path(replay_dir)
        self.replay_dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: MatchResult, game: GameState) -> str:
        """
        保存一局完整回放。

        Args:
            result: 对局结果
            game: 游戏终局状态

        Returns:
            str: 保存的文件路径
        """
        # 构建完整回放数据
        replay = {
            "match_id": result.match_id,
            "timestamp": time.time(),
            "agent1": {
                "name": result.agent1_name,
                "type": result.agent1_type,
            },
            "agent2": {
                "name": result.agent2_name,
                "type": result.agent2_type,
            },
            "result": {
                "winner": result.winner,
                "winner_name": result.winner_name,
                "total_turns": result.total_turns,
                "p1_final_lines": result.p1_final_lines,
                "p2_final_lines": result.p2_final_lines,
                "duration_seconds": result.duration_seconds,
                "first_player": result.first_player,
            },
            "called_numbers": result.called_numbers,
            "move_timeline": result.move_timeline,
            "final_state": game.to_dict() if game.is_terminal() else {},
        }

        filename = f"match_{result.match_id}.json"
        filepath = self.replay_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(replay, f, ensure_ascii=False, indent=2, default=str)

        return str(filepath)

    def load(self, filename: str) -> Optional[dict]:
        """
        加载一局回放。

        Args:
            filename: 回放文件名或完整路径

        Returns:
            dict | None: 回放数据，文件不存在返回None
        """
        filepath = self.replay_dir / filename
        if not filepath.exists():
            # 尝试作为完整路径
            filepath = Path(filename)

        if not filepath.exists():
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all(self) -> list[dict]:
        """
        加载所有回放。

        Returns:
            list[dict]: 所有回放数据列表
        """
        replays = []
        for filepath in sorted(self.replay_dir.glob("match_*.json")):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    replays.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                continue
        return replays

    def list_replays(self) -> list[str]:
        """列出所有回放文件名"""
        return sorted([
            f.name for f in self.replay_dir.glob("match_*.json")
        ])

    def delete_replay(self, match_id: str) -> bool:
        """删除指定回放"""
        filepath = self.replay_dir / f"match_{match_id}.json"
        if filepath.exists():
            filepath.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """清空所有回放，返回删除数量"""
        count = 0
        for filepath in self.replay_dir.glob("match_*.json"):
            filepath.unlink()
            count += 1
        return count

    def get_summary(self) -> dict:
        """
        获取所有回放的摘要统计。

        Returns:
            dict: 摘要统计
        """
        replays = self.load_all()
        if not replays:
            return {"total": 0}

        agents = set()
        total_turns = 0
        for r in replays:
            agents.add(r["agent1"]["name"])
            agents.add(r["agent2"]["name"])
            total_turns += r["result"]["total_turns"]

        return {
            "total_replays": len(replays),
            "unique_agents": sorted(list(agents)),
            "total_turns": total_turns,
            "avg_turns": total_turns / len(replays) if replays else 0,
        }
