"""
CS2 Multi-Agent Performance Analyst
รันจาก: python main.py

Usage:
  python main.py --nickname <FACEIT_nickname>
  python main.py --demo <path/to/demo.dem>
  python main.py --nickname <nick> --demo <path> --level faceit_10
  python main.py --demo mock  # ทดสอบด้วย mock data
"""

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

# Load .env ถ้ามี
load_dotenv()

console = Console()


def check_env():
    """ตรวจสอบ environment variables ที่จำเป็น"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        console.print("[bold red]❌ ต้องตั้งค่า ANTHROPIC_API_KEY[/bold red]")
        console.print("[dim]สร้างไฟล์ .env แล้วใส่: ANTHROPIC_API_KEY=your_key_here[/dim]")
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
  python main.py --nickname s1mple
  python main.py --demo /path/to/match.dem
  python main.py --nickname myNick --level faceit_10
  python main.py --demo mock --current-level 7 --goal-level 10
        """,
    )

    parser.add_argument("--nickname", "-n", type=str, help="FACEIT nickname")
    parser.add_argument("--demo", "-d", type=str, help="Path ไปยัง .dem file (หรือ 'mock')")
    parser.add_argument(
        "--level", "-l",
        type=str, default="faceit_10",
        choices=["faceit_5", "faceit_7", "faceit_10", "pro"],
        help="Benchmark level ที่เปรียบเทียบ (default: faceit_10)",
    )
    parser.add_argument(
        "--current-level", type=int, default=8,
        help="FACEIT level ปัจจุบัน (default: 8)",
    )
    parser.add_argument(
        "--goal-level", type=int, default=10,
        help="FACEIT level เป้าหมาย (default: 10)",
    )
    parser.add_argument(
        "--save-report", action="store_true",
        help="บันทึก report เป็น markdown file",
    )

    args = parser.parse_args()

    # ต้องมี input อย่างน้อย 1 อย่าง
    if not args.nickname and not args.demo:
        parser.print_help()
        console.print("\n[red]ต้องระบุ --nickname หรือ --demo อย่างน้อย 1 อย่าง[/red]")
        sys.exit(1)

    check_env()

    # Handle mock demo
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

    # Import here เพื่อให้ env check ทำงานก่อน
    from agents.orchestrator import Orchestrator

    orchestrator = Orchestrator()

    results = orchestrator.run(
        nickname=args.nickname,
        demo_path=demo_path,
        target_level=args.level,
        player_current_level=args.current_level,
        player_goal_level=args.goal_level,
    )

    if args.save_report:
        orchestrator.save_report(results)


if __name__ == "__main__":
    main()
