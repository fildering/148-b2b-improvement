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

from agents.data_agent import DataAgent
from agents.analysis_agent import AnalysisAgent
from agents.comparison_agent import ComparisonAgent
from agents.coach_agent import CoachAgent

console = Console()
MODEL = "llama-3.3-70b-versatile"


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
    ) -> dict:
        """
        รัน full analysis pipeline

        Args:
            nickname: FACEIT nickname ของผู้เล่น
            demo_path: path ไปยัง .dem file
            target_level: benchmark level ที่เปรียบเทียบ (faceit_5/7/10/pro)
            player_current_level: FACEIT level ปัจจุบัน
            player_goal_level: FACEIT level เป้าหมาย

        Returns:
            dict ที่มีผลลัพธ์จากทุก stage
        """
        results = {}

        console.print(Panel.fit(
            "[bold cyan]🎮 CS2 Performance Analyst[/bold cyan]\n"
            f"[dim]Player: {nickname or 'Demo only'} | Target: {target_level}[/dim]",
            border_style="cyan",
        ))

        # ── Stage 1: Data Collection ─────────────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("📡 Stage 1: กำลังดึงข้อมูล...", total=None)
            data_result = self.data_agent.collect(
                nickname=nickname, demo_path=demo_path
            )
            progress.update(task, description="✅ ดึงข้อมูลสำเร็จ")

        console.print(Panel(
            Markdown(data_result),
            title="[bold blue]📡 Data Collection[/bold blue]",
            border_style="blue",
        ))
        results["data"] = data_result

        # ── Stage 2: Analysis ─────────────────────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold yellow]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("🔬 Stage 2: กำลังวิเคราะห์...", total=None)
            analysis_result = self.analysis_agent.analyze(data_result)
            progress.update(task, description="✅ วิเคราะห์สำเร็จ")

        console.print(Panel(
            Markdown(analysis_result),
            title="[bold yellow]🔬 Performance Analysis[/bold yellow]",
            border_style="yellow",
        ))
        results["analysis"] = analysis_result

        # ── Stage 3: Comparison ───────────────────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("📊 Stage 3: กำลังเปรียบเทียบ...", total=None)

            # ดึง stats จาก analysis result สำหรับ comparison
            your_stats = self._extract_stats_from_analysis(analysis_result)
            comparison_result = self.comparison_agent.compare(
                your_stats=your_stats,
                target_level=target_level,
            )
            progress.update(task, description="✅ เปรียบเทียบสำเร็จ")

        console.print(Panel(
            Markdown(comparison_result),
            title="[bold magenta]📊 Performance Comparison[/bold magenta]",
            border_style="magenta",
        ))
        results["comparison"] = comparison_result

        # ── Stage 4: Coaching ─────────────────────────────────────────────
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("🎓 Stage 4: กำลังสร้าง training plan...", total=None)
            coaching_result = self.coach_agent.create_plan(
                analysis_result=analysis_result,
                comparison_result=comparison_result,
                player_level=player_current_level,
                goal_level=player_goal_level,
            )
            progress.update(task, description="✅ สร้าง plan สำเร็จ")

        console.print(Panel(
            Markdown(coaching_result),
            title="[bold green]🎓 Personal Training Plan[/bold green]",
            border_style="green",
        ))
        results["coaching"] = coaching_result

        # ── Final Summary ─────────────────────────────────────────────────
        console.print(Panel.fit(
            "[bold green]✅ Analysis Complete![/bold green]\n"
            f"[dim]ดู output/report.md สำหรับรายงานฉบับเต็ม[/dim]",
            border_style="green",
        ))

        return results

    def _extract_stats_from_analysis(self, analysis_text: str) -> dict:
        """
        ใช้ Groq แปลง analysis text เป็น structured stats dict
        """
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
                    "content": f"""จากข้อความวิเคราะห์ CS2 นี้ ดึงตัวเลขออกมาเป็น JSON:
{analysis_text}

ต้องการ keys: kd_ratio, headshots_pct, win_rate, avg_kills, adr
ถ้าไม่มีข้อมูลให้ใช้ค่า default ที่สมเหตุสมผล
ตอบแค่ JSON เท่านั้น เช่น {{"kd_ratio": 1.1, "headshots_pct": 42.0, ...}}""",
                },
            ],
        )

        text = response.choices[0].message.content.strip()

        # Clean up JSON ถ้ามี markdown code block หลุดมา
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("```").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {
                "kd_ratio": 1.0,
                "headshots_pct": 40.0,
                "win_rate": 50.0,
                "avg_kills": 18.0,
                "adr": 75.0,
            }

    def save_report(self, results: dict, output_path: str = "output/report.md"):
        """บันทึก report เป็น markdown file"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# 🎮 CS2 Performance Analysis Report\n\n")
            f.write("---\n\n")

            if "data" in results:
                f.write("## 📡 Data Collection\n\n")
                f.write(results["data"] + "\n\n")

            if "analysis" in results:
                f.write("## 🔬 Performance Analysis\n\n")
                f.write(results["analysis"] + "\n\n")

            if "comparison" in results:
                f.write("## 📊 Comparison Results\n\n")
                f.write(results["comparison"] + "\n\n")

            if "coaching" in results:
                f.write("## 🎓 Training Plan\n\n")
                f.write(results["coaching"] + "\n\n")

        console.print(f"[dim]💾 Saved report to: {output_path}[/dim]")
