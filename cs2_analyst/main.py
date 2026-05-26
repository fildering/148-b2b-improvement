"""
CS2 Multi-Agent Performance Analyst

Usage:
  python main.py --nickname <FACEIT_nick>
  python main.py --nickname <nick> --compare-with s1mple
  python main.py --demo mock
  python main.py --nickname <nick> --compare-with zywoo --save-report
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


def check_env():
    if not os.environ.get("GROQ_API_KEY"):
        console.print("[bold red]❌ ต้องตั้งค่า GROQ_API_KEY[/bold red]")
        console.print("[dim]สมัครฟรีที่ https://console.groq.com/ → 'API Keys' → 'Create API Key'[/dim]")
        sys.exit(1)

    if not os.environ.get("FACEIT_API_KEY"):
        console.print("[bold yellow]⚠️  ไม่มี FACEIT_API_KEY — จะใช้ mock data แทน[/bold yellow]")
        console.print("[dim]สมัครฟรีที่ https://developers.faceit.com/[/dim]\n")


def main():
    parser = argparse.ArgumentParser(
        description="CS2 Multi-Agent Performance Analyst",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --nickname yourNick
  python main.py --nickname yourNick --compare-with s1mple
  python main.py --nickname yourNick --compare-with zywoo --save-report
  python main.py --demo mock --current-level 7 --goal-level 10

Known pros (no FACEIT key needed):
  s1mple, zywoo, niko, device, electronic
        """,
    )

    parser.add_argument("--nickname", "-n", type=str, help="FACEIT nickname ของคุณ")
    parser.add_argument("--demo", "-d", type=str, help="Path ไปยัง .dem file (หรือ 'mock')")
    parser.add_argument(
        "--compare-with", "-c", type=str, default=None,
        metavar="PRO_NICK",
        help="เปรียบเทียบกับ pro player เช่น s1mple, zywoo, niko",
    )
    parser.add_argument(
        "--level", "-l",
        type=str, default="faceit_10",
        choices=["faceit_5", "faceit_7", "faceit_10", "pro"],
        help="Benchmark level (ใช้เมื่อไม่ได้ระบุ --compare-with)",
    )
    parser.add_argument("--current-level", type=int, default=8)
    parser.add_argument("--goal-level", type=int, default=10)
    parser.add_argument("--save-report", action="store_true",
                        help="บันทึก report เป็น output/report.md")

    args = parser.parse_args()

    if not args.nickname and not args.demo:
        parser.print_help()
        console.print("\n[red]ต้องระบุ --nickname หรือ --demo อย่างน้อย 1 อย่าง[/red]")
        sys.exit(1)

    check_env()

    demo_path = None
    if args.demo:
        if args.demo.lower() == "mock":
            demo_path = "mock"
            console.print("[dim]🧪 ใช้ mock demo data สำหรับทดสอบ[/dim]")
        elif not Path(args.demo).exists():
            console.print(f"[red]❌ ไม่พบไฟล์: {args.demo}[/red]")
            sys.exit(1)
        else:
            demo_path = args.demo

    from agents.orchestrator import Orchestrator
    orchestrator = Orchestrator()

    results = orchestrator.run(
        nickname=args.nickname,
        demo_path=demo_path,
        target_level=args.level,
        player_current_level=args.current_level,
        player_goal_level=args.goal_level,
        compare_with=args.compare_with,
    )

    if args.save_report:
        orchestrator.save_report(results)


if __name__ == "__main__":
    main()
