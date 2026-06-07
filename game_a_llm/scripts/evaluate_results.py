"""评估分析脚本

分析对战结果，生成统计报告。
可作为命令行工具或Python模块使用。

用法:
    python scripts/evaluate_results.py data/results/tournament_001.json
"""

import json
import sys
import os
from pathlib import Path
from collections import defaultdict
from typing import Optional

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class Evaluator:
    """
    对战结果评估器。

    功能:
    - 胜率统计
    - 先手/后手分析
    - ELO评分计算
    - 回合数分布
    - 趋势分析
    - 生成Markdown/文本报告
    """

    def __init__(self):
        self.results = []
        self.agent_stats = defaultdict(lambda: {
            "wins": 0, "losses": 0, "total": 0,
            "as_first": 0, "as_first_wins": 0,
            "as_second": 0, "as_second_wins": 0,
            "turn_counts": [],
        })

    def load(self, path: str) -> None:
        """加载结果文件"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.results = data.get("results", [])

    def load_from_results(self, results: list) -> None:
        """直接从结果列表加载"""
        self.results = [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]

    def analyze(self) -> dict:
        """执行完整分析"""
        if not self.results:
            return {"error": "没有对战数据"}

        self._compute_agent_stats()
        elo = self._compute_elo()

        return {
            "total_matches": len(self.results),
            "agents": self._get_agent_summary(),
            "elo_ratings": elo,
            "first_move_advantage": self._analyze_first_move(),
            "turn_distribution": self._analyze_turns(),
            "head_to_head": self._analyze_head_to_head(),
        }

    def _compute_agent_stats(self) -> None:
        """计算每个代理的详细统计"""
        self.agent_stats.clear()

        for r in self.results:
            a1 = r["agent1_name"]
            a2 = r["agent2_name"]
            winner = r["winner"]
            first = r.get("first_player", "player_1")

            for name in [a1, a2]:
                self.agent_stats[name]["total"] += 1

            if winner == "player_1":
                self.agent_stats[a1]["wins"] += 1
                self.agent_stats[a2]["losses"] += 1
                self.agent_stats[a1]["turn_counts"].append(r["total_turns"])
            elif winner == "player_2":
                self.agent_stats[a2]["wins"] += 1
                self.agent_stats[a1]["losses"] += 1
                self.agent_stats[a2]["turn_counts"].append(r["total_turns"])

            # 先手统计
            if first == "player_1":
                self.agent_stats[a1]["as_first"] += 1
                self.agent_stats[a2]["as_second"] += 1
                if winner == "player_1":
                    self.agent_stats[a1]["as_first_wins"] += 1
            else:
                self.agent_stats[a2]["as_first"] += 1
                self.agent_stats[a1]["as_second"] += 1
                if winner == "player_2":
                    self.agent_stats[a2]["as_first_wins"] += 1

    def _get_agent_summary(self) -> list[dict]:
        """代理摘要（按胜率排序）"""
        summary = []
        for name, stats in self.agent_stats.items():
            total = stats["total"]
            wins = stats["wins"]
            avg_turns = (
                sum(stats["turn_counts"]) / len(stats["turn_counts"])
                if stats["turn_counts"] else 0
            )
            first_rate = (
                stats["as_first_wins"] / stats["as_first"]
                if stats["as_first"] > 0 else 0
            )

            summary.append({
                "name": name,
                "total": total,
                "wins": wins,
                "losses": stats["losses"],
                "win_rate": wins / total if total > 0 else 0,
                "avg_turns": round(avg_turns, 1),
                "first_win_rate": round(first_rate, 3),
            })

        return sorted(summary, key=lambda x: x["win_rate"], reverse=True)

    def _compute_elo(self, initial: int = 1500, k: int = 32) -> dict[str, float]:
        """
        计算ELO评分。

        Args:
            initial: 初始ELO分数
            k: K因子

        Returns:
            dict[str, float]: 代理名称到ELO分数的映射
        """
        elo = defaultdict(lambda: initial)

        for r in self.results:
            a1 = r["agent1_name"]
            a2 = r["agent2_name"]
            winner = r["winner"]

            ra = elo[a1]
            rb = elo[a2]

            ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
            eb = 1.0 - ea

            if winner == "player_1":
                sa, sb = 1.0, 0.0
            elif winner == "player_2":
                sa, sb = 0.0, 1.0
            else:
                sa, sb = 0.5, 0.5

            elo[a1] = ra + k * (sa - ea)
            elo[a2] = rb + k * (sb - eb)

        return dict(elo)

    def _analyze_first_move(self) -> dict:
        """先手优势分析"""
        first_wins = 0
        second_wins = 0
        total = 0

        for r in self.results:
            total += 1
            first = r.get("first_player", "player_1")
            if r["winner"] == first:
                first_wins += 1
            else:
                second_wins += 1

        return {
            "total": total,
            "first_player_wins": first_wins,
            "second_player_wins": second_wins,
            "first_win_rate": first_wins / total if total > 0 else 0,
        }

    def _analyze_turns(self) -> dict:
        """回合数分布分析"""
        all_turns = [r["total_turns"] for r in self.results]
        if not all_turns:
            return {}

        return {
            "min": min(all_turns),
            "max": max(all_turns),
            "mean": sum(all_turns) / len(all_turns),
            "median": sorted(all_turns)[len(all_turns) // 2],
            "histogram": self._make_histogram(all_turns, bins=5),
        }

    def _analyze_head_to_head(self) -> list[dict]:
        """两两对战分析"""
        h2h = defaultdict(lambda: {"wins": 0, "losses": 0})

        for r in self.results:
            a1 = r["agent1_name"]
            a2 = r["agent2_name"]
            pair = (a1, a2)

            if r["winner"] == "player_1":
                h2h[pair]["wins"] += 1
                h2h[(a2, a1)]["losses"] += 1
            else:
                h2h[(a2, a1)]["wins"] += 1
                h2h[pair]["losses"] += 1

        result = []
        for (a1, a2), record in h2h.items():
            total = record["wins"] + record["losses"]
            if total > 0:
                result.append({
                    "agent1": a1,
                    "agent2": a2,
                    "a1_wins": record["wins"],
                    "total": total,
                    "dominance": record["wins"] / total,
                })

        return sorted(result, key=lambda x: x["total"], reverse=True)

    @staticmethod
    def _make_histogram(values: list, bins: int = 5) -> list[dict]:
        """创建直方图数据"""
        if not values:
            return []
        vmin, vmax = min(values), max(values)
        if vmin == vmax:
            return [{"range": f"{vmin}", "count": len(values)}]

        bin_width = (vmax - vmin) / bins
        counts = [0] * bins
        for v in values:
            idx = min(int((v - vmin) / bin_width), bins - 1)
            counts[idx] += 1

        hist = []
        for i in range(bins):
            low = int(vmin + i * bin_width)
            high = int(vmin + (i + 1) * bin_width)
            hist.append({
                "range": f"{low}-{high}",
                "count": counts[i],
            })
        return hist

    def report(self, analysis: dict = None) -> str:
        """生成文本报告"""
        if analysis is None:
            analysis = self.analyze()

        if "error" in analysis:
            return f"无法生成报告: {analysis['error']}"

        lines = []
        lines.append("=" * 60)
        lines.append("  游戏A - 对战评估报告")
        lines.append("=" * 60)
        lines.append(f"  总局数: {analysis['total_matches']}")
        lines.append("")

        # 排名
        lines.append("--- 代理排名 ---")
        lines.append(f"{'排名':<6}{'代理':<20}{'胜率':<10}{'胜/负':<12}{'ELO':<8}{'均回合':<10}")
        lines.append("-" * 66)

        elo = analysis.get("elo_ratings", {})
        for i, agent in enumerate(analysis["agents"]):
            elo_score = elo.get(agent["name"], 1500)
            line = "{:<6}{:<20}{:<10}{:<12}{:<8}{:<10}".format(
                i + 1,
                agent["name"],
                "{:.1%}".format(agent["win_rate"]),
                "{}/{}".format(agent["wins"], agent["losses"]),
                "{:.0f}".format(elo_score),
                str(agent["avg_turns"]),
            )
            lines.append(line)

        lines.append("")

        # 先手优势
        fm = analysis["first_move_advantage"]
        lines.append("--- 先手优势 ---")
        lines.append(f"  先手胜: {fm['first_player_wins']} ({fm['first_win_rate']:.1%})")
        lines.append(f"  后手胜: {fm['second_player_wins']} ({1-fm['first_win_rate']:.1%})")
        lines.append("")

        # 回合分布
        td = analysis["turn_distribution"]
        if td:
            lines.append("--- 回合分布 ---")
            lines.append(f"  最短: {td['min']}  最长: {td['max']}")
            lines.append(f"  平均: {td['mean']:.1f}  中位: {td['median']}")
            lines.append("  分布:")
            for bar in td["histogram"]:
                pct = bar["count"] / analysis["total_matches"] * 100
                lines.append(f"    {bar['range']:>10}: {'█' * int(pct)} {bar['count']}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def save_report(self, analysis: dict, path: str) -> None:
        """保存报告到文件"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # 保存JSON
        json_path = path.replace(".txt", ".json").replace(".md", ".json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)

        # 保存文本报告
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.report(analysis))


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="游戏A对战结果评估")
    parser.add_argument("input", help="结果JSON文件路径")
    parser.add_argument("-o", "--output", default=None, help="报告输出路径")
    parser.add_argument("--text", action="store_true", help="只输出文本报告")

    args = parser.parse_args()

    evaluator = Evaluator()
    evaluator.load(args.input)
    analysis = evaluator.analyze()

    if args.text or args.output:
        report = evaluator.report(analysis)
        print(report)
        if args.output:
            evaluator.save_report(analysis, args.output)
            print(f"\n报告已保存到: {args.output}")
    else:
        print(json.dumps(analysis, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
