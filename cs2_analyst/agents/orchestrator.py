"""
Orchestrator Agent — ประสานงานระหว่าง agents ทั้งหมด
รับ input จากผู้ใช้ แจกงาน และรวมผลลัพธ์
"""

import json
import os
from groq import Groq
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from rich.table import Table

from agents.data_agent import DataAgent
from agents.analysis_agent import AnalysisAgent
from agents.comparison_agent import ComparisonAgent
from agents.coach_agent import CoachAgent
from tools import faceit_tools

console = Console()
MODEL = "llama-3.3-70b-versatile"

# ── Pro player stats แบบ hardcoded (fallback ถ้าไม่มี FACEIT key) ──
# ข้อมูลจาก HLTV lifetime stats ปี 2024
KNOWN_PROS: dict[str, dict] = {
    "s1mple": {
        "kd_ratio": 1.37, "headshots_pct": 47.0,
        "win_rate": 58.0, "avg_kills": 23.5, "adr": 84.0,
        "source": "HLTV 2024",
    },
    "zywoo": {
        "kd_ratio": 1.34, "headshots_pct": 44.0,
        "win_rate": 57.0, "avg_kills": 22.8, "adr": 82.0,
        "source": "HLTV 2024",
    },
    "niko": {
        "kd_ratio": 1.24, "headshots_pct": 52.0,
        "win_rate": 56.0, "avg_kills": 22.0, "adr": 80.0,
        "source": "HLTV 2024",
    },
    "device": {
        "kd_ratio": 1.19, "headshots_pct": 36.0,
        "win_rate": 59.0, "avg_kills": 20.5, "adr": 76.0,
        "source": "HLTV 2024",
    },
    "electronic": {
        "kd_ratio": 1.16, "headshots_pct": 50.0,
        "win_rate": 57.0, "avg_kills": 21.0, "adr": 78.0,
        "source": "HLTV 2024",
    },
}


class Orchestrator:
    """
    ประสานงาน multi-agent pipeline:
    DataAgent → AnalysisAgent → ComparisonAgent → CoachAgent
    """

    def __init__(self):
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.data_agent = DataAgent()
        self.analysis_agent = AnalysisAgent()
        self.comparison_agent = ComparisonAgent()
        self.coach_agent = CoachAgent()

    def run(
        self,
        nickname: str | None = None,
        demo_path: str | None = None,
        target_level: str = "faceit_10",
        player_current_level: int = 8,
        player_goal_level: int = 10,
        compare_with: str | None = None,      # ← pro FACEIT nickname
    ) -> dict:
        """
        รัน full analysis pipeline

        Args:
            nickname: FACEIT nickname ของผู้เล่น
            demo_path: path ไปยัง .dem file
            target_level: benchmark level ที่เปรียบเทียบ (faceit_5/7/10/pro)
            player_current_level: FACEIT level ปัจจุบัน
            player_goal_level: FACEIT level เป้าหมาย
            compare_with: FACEIT nickname ของ pro ที่ต้องการเปรียบเทียบด้วย
        """
        results = {}

        # ── ดึง pro stats ถ้ามี --compare-with ──────────────────────────
        pro_stats = None
        pro_label = "Pro"
        if compare_with:
            pro_stats, pro_label = self._fetch_pro_stats(compare_with)

        # Header
        compare_str = f" vs {pro_label}" if pro_stats else f" | Target: {target_level}"
        console.print(Panel.fit(
            "[bold cyan]🎮 CS2 Performance Analyst[/bold cyan]\n"
            f"[dim]Player: {nickname or 'Demo only'}{compare_str}[/dim]",
            border_style="cyan",
        ))

        # ── Stage 1: Data Collection ──────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"),
                      console=console, transient=True) as progress:
            task = progress.add_task("📡 Stage 1: กำลังดึงข้อมูล...", total=None)
            data_result = self.data_agent.collect(nickname=nickname, demo_path=demo_path)
            progress.update(task, description="✅ ดึงข้อมูลสำเร็จ")

        console.print(Panel(Markdown(data_result),
                            title="[bold blue]📡 Data Collection[/bold blue]",
                            border_style="blue"))
        results["data"] = data_result

        # ── Stage 2: Analysis ─────────────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[bold yellow]{task.description}"),
                      console=console, transient=True) as progress:
            task = progress.add_task("🔬 Stage 2: กำลังวิเคราะห์...", total=None)
            analysis_result = self.analysis_agent.analyze(data_result)
            progress.update(task, description="✅ วิเคราะห์สำเร็จ")

        console.print(Panel(Markdown(analysis_result),
                            title="[bold yellow]🔬 Performance Analysis[/bold yellow]",
                            border_style="yellow"))
        results["analysis"] = analysis_result

        # ── Stage 3: Comparison ───────────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[bold magenta]{task.description}"),
                      console=console, transient=True) as progress:
            task = progress.add_task("📊 Stage 3: กำลังเปรียบเทียบ...", total=None)

            your_stats = self._extract_stats_from_analysis(analysis_result)

            comparison_result = self.comparison_agent.compare(
                your_stats=your_stats,
                target_level=target_level,
                reference_stats=pro_stats,
                reference_label=pro_label,
            )
            progress.update(task, description="✅ เปรียบเทียบสำเร็จ")

        # ถ้ามี pro stats แสดง side-by-side table
        if pro_stats:
            self._print_pro_comparison_table(your_stats, pro_stats, pro_label)

        console.print(Panel(Markdown(comparison_result),
                            title=f"[bold magenta]📊 Comparison: You vs {pro_label}[/bold magenta]",
                            border_style="magenta"))
        results["comparison"] = comparison_result

        # ── Stage 4: Coaching ─────────────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[bold green]{task.description}"),
                      console=console, transient=True) as progress:
            task = progress.add_task("🎓 Stage 4: กำลังสร้าง training plan...", total=None)
            coaching_result = self.coach_agent.create_plan(
                analysis_result=analysis_result,
                comparison_result=comparison_result,
                player_level=player_current_level,
                goal_level=player_goal_level,
            )
            progress.update(task, description="✅ สร้าง plan สำเร็จ")

        console.print(Panel(Markdown(coaching_result),
                            title="[bold green]🎓 Personal Training Plan[/bold green]",
                            border_style="green"))
        results["coaching"] = coaching_result

        console.print(Panel.fit(
            "[bold green]✅ Analysis Complete![/bold green]\n"
            "[dim]ดู output/report.md สำหรับรายงานฉบับเต็ม[/dim]",
            border_style="green",
        ))
        return results

    # ── Helpers ──────────────────────────────────────────────────────────

    def _fetch_pro_stats(self, pro_nickname: str) -> tuple[dict, str]:
        """
        ดึง stats ของ pro player
        1. ลองดึงจาก FACEIT API ก่อน (ถ้ามี key)
        2. Fallback → hardcoded KNOWN_PROS
        3. Fallback → ค่า pro benchmark เฉลี่ย
        """
        nick_lower = pro_nickname.lower()

        # ── ลอง FACEIT API ก่อน ──
        if os.environ.get("FACEIT_API_KEY"):
            console.print(f"[cyan]🔍 กำลังดึงข้อมูล {pro_nickname} จาก FACEIT...[/cyan]")
            player = faceit_tools.get_player_by_nickname(pro_nickname)

            if "error" not in player and player.get("player_id"):
                stats = faceit_tools.get_player_stats(player["player_id"])
                if "error" not in stats:
                    pro_stats = {
                        "kd_ratio":       float(stats.get("kd_ratio", 1.0)),
                        "headshots_pct":  float(stats.get("headshots_pct", 50.0)),
                        "win_rate":       float(stats.get("win_rate", 55.0)),
                        "avg_kills":      float(stats.get("avg_kills", 22.0)),
                        "adr":            85.0,   # FACEIT ไม่มี ADR ใช้ค่าเฉลี่ย pro
                        "source": "FACEIT",
                        "elo": player.get("elo", "N/A"),
                        "level": player.get("level", "N/A"),
                    }
                    label = f"{player.get('nickname', pro_nickname)} (FACEIT Lv.{player.get('level','?')})"
                    console.print(f"[green]✅ ดึงข้อมูล {label} สำเร็จ[/green]")
                    return pro_stats, label

        # ── Fallback: hardcoded pro stats ──
        if nick_lower in KNOWN_PROS:
            stats = KNOWN_PROS[nick_lower].copy()
            label = f"{pro_nickname} ({stats.pop('source', 'HLTV')})"
            console.print(f"[yellow]📊 ใช้ข้อมูล {label} (hardcoded)[/yellow]")
            return stats, label

        # ── Fallback: pro benchmark เฉลี่ย ──
        from tools.stats_tools import get_benchmark_stats
        console.print(f"[yellow]⚠️  ไม่พบ '{pro_nickname}' — ใช้ค่าเฉลี่ย pro แทน[/yellow]")
        return get_benchmark_stats("pro"), f"{pro_nickname} (Pro avg)"

    def _print_pro_comparison_table(self, your_stats: dict,
                                     pro_stats: dict, pro_label: str):
        """แสดง side-by-side table เปรียบเทียบ"""
        table = Table(title=f"⚡ You vs {pro_label}", border_style="cyan")
        table.add_column("Metric", style="bold white")
        table.add_column("You", justify="center", style="cyan")
        table.add_column(pro_label[:20], justify="center", style="yellow")
        table.add_column("Gap", justify="center")

        metrics = {
            "K/D Ratio":   ("kd_ratio", "{:.2f}"),
            "HS%":         ("headshots_pct", "{:.1f}%"),
            "Win Rate":    ("win_rate", "{:.1f}%"),
            "Avg Kills":   ("avg_kills", "{:.1f}"),
            "ADR":         ("adr", "{:.1f}"),
        }

        for label, (key, fmt) in metrics.items():
            your_val = float(your_stats.get(key, 0))
            pro_val  = float(pro_stats.get(key, 0))
            diff     = your_val - pro_val
            diff_pct = (diff / pro_val * 100) if pro_val else 0

            if diff >= 0:
                gap_str = f"[green]+{diff_pct:.1f}%[/green]"
            else:
                gap_str = f"[red]{diff_pct:.1f}%[/red]"

            table.add_row(label, fmt.format(your_val), fmt.format(pro_val), gap_str)

        console.print(table)

    def _extract_stats_from_analysis(self, analysis_text: str) -> dict:
        """ใช้ Groq แปลง analysis text เป็น structured stats dict"""
        response = self.client.chat.completions.create(
            model=MODEL,
            temperature=0,
            max_tokens=256,
            messages=[
                {
                    "role": "system",
                    "content": "แปลงข้อความวิเคราะห์ CS2 เป็น JSON stats ตอบด้วย JSON เท่านั้น ไม่มี markdown ไม่มีคำอธิบาย",
                },
                {
                    "role": "user",
                    "content": (
                        f"จากข้อความวิเคราะห์ CS2 นี้ ดึงตัวเลขออกมาเป็น JSON:\n{analysis_text}\n\n"
                        "ต้องการ keys: kd_ratio, headshots_pct, win_rate, avg_kills, adr\n"
                        "ถ้าไม่มีข้อมูลให้ใช้ค่า default ที่สมเหตุสมผล\n"
                        'ตอบแค่ JSON เท่านั้น เช่น {"kd_ratio": 1.1, "headshots_pct": 42.0, ...}'
                    ),
                },
            ],
        )

        text = response.choices[0].message.content.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("```").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"kd_ratio": 1.0, "headshots_pct": 40.0,
                    "win_rate": 50.0, "avg_kills": 18.0, "adr": 75.0}

    def save_report(self, results: dict, output_path: str = "output/report.md"):
        """บันทึก report เป็น markdown file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 🎮 CS2 Performance Analysis Report\n\n---\n\n")
            sections = [
                ("data", "📡 Data Collection"),
                ("analysis", "🔬 Performance Analysis"),
                ("comparison", "📊 Comparison Results"),
                ("coaching", "🎓 Training Plan"),
            ]
            for key, title in sections:
                if key in results:
                    f.write(f"## {title}\n\n{results[key]}\n\n")
        console.print(f"[dim]💾 Saved report to: {output_path}[/dim]")
