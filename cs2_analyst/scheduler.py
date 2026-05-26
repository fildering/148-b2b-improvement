"""
CS2 Analyst Scheduler — รัน analysis อัตโนมัติทุกวัน/หลังเล่น
ไม่ต้องทำอะไรเลย มันทำเองทั้งหมด:
  - ดึง matches ใหม่จาก FACEIT
  - download demos อัตโนมัติ
  - วิเคราะห์และ save report
  - แจ้งเตือนผ่าน Windows notification
"""

import os
import sys
import time
import json
import schedule
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

STATE_FILE = Path("data/last_check.json")
REPORT_DIR = Path("output/reports")


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_match_ids": [], "last_run": None}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def notify_windows(title: str, message: str):
    """แจ้งเตือนผ่าน Windows Toast Notification"""
    try:
        # ใช้ PowerShell ส่ง notification
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
$notify = New-Object System.Windows.Forms.NotifyIcon
$notify.Icon = [System.Drawing.SystemIcons]::Information
$notify.Visible = $true
$notify.ShowBalloonTip(5000, '{title}', '{message}', [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Seconds 6
$notify.Dispose()
"""
        subprocess.run(["powershell", "-Command", script],
                       capture_output=True, timeout=10)
    except Exception:
        pass  # ไม่มี notification ก็ไม่เป็นไร


def run_analysis(nickname: str, compare_with: str | None = None,
                 save_report: bool = True) -> bool:
    """รัน analysis 1 ครั้ง"""
    console.print(f"\n[bold cyan]🕐 {datetime.now().strftime('%H:%M:%S')} — กำลังรัน analysis...[/bold cyan]")

    cmd = [sys.executable, "main.py", "--nickname", nickname]
    if compare_with:
        cmd += ["--compare-with", compare_with]
    if save_report:
        cmd.append("--save-report")

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def check_new_matches_and_analyze(nickname: str, compare_with: str | None = None):
    """
    ตรวจสอบ matches ใหม่ — ถ้ามีให้รัน analysis อัตโนมัติ
    """
    if not os.environ.get("FACEIT_API_KEY"):
        console.print("[yellow]⚠️  ไม่มี FACEIT_API_KEY — ข้ามการตรวจสอบ matches ใหม่[/yellow]")
        return

    from tools import faceit_tools
    state = load_state()

    # ดึง player id
    player = faceit_tools.get_player_by_nickname(nickname)
    if "error" in player:
        console.print(f"[red]❌ ไม่พบ player: {nickname}[/red]")
        return

    player_id = player["player_id"]

    # ดึง matches ล่าสุด
    matches = faceit_tools.get_recent_matches(player_id, limit=5)
    if "error" in matches:
        return

    recent_ids = [m["match_id"] for m in matches.get("matches", [])]
    known_ids = set(state.get("last_match_ids", []))
    new_ids = [mid for mid in recent_ids if mid not in known_ids]

    if not new_ids:
        console.print(f"[dim]{datetime.now().strftime('%H:%M')} — ไม่มี match ใหม่[/dim]")
        return

    console.print(f"[bold green]🎮 พบ {len(new_ids)} match ใหม่! กำลังวิเคราะห์...[/bold green]")

    # รัน analysis
    ok = run_analysis(nickname, compare_with)

    if ok:
        state["last_match_ids"] = recent_ids
        state["last_run"] = datetime.now().isoformat()
        save_state(state)
        notify_windows("CS2 Analysis เสร็จแล้ว! 🎮",
                       f"วิเคราะห์ {len(new_ids)} match ใหม่เรียบร้อย ดูที่ output\\reports")
        console.print("[bold green]✅ Analysis เสร็จ! บันทึก report แล้ว[/bold green]")
    else:
        console.print("[red]❌ Analysis ล้มเหลว[/red]")


def start_scheduler(nickname: str, compare_with: str | None = None,
                    interval_minutes: int = 30):
    """
    เริ่ม scheduler — ตรวจสอบ matches ใหม่ทุก N นาที
    รันค้างไว้ใน background ได้เลย
    """
    console.print(f"""
[bold cyan]╔══════════════════════════════════╗
║   CS2 Auto Analyst — Running     ║
╚══════════════════════════════════╝[/bold cyan]
Player  : [yellow]{nickname}[/yellow]
Compare : [yellow]{compare_with or 'benchmark'}[/yellow]
Interval: ทุก [yellow]{interval_minutes} นาที[/yellow]
[dim]กด Ctrl+C เพื่อหยุด[/dim]
""")

    # ตรวจสอบทันที 1 ครั้งแรก
    check_new_matches_and_analyze(nickname, compare_with)

    # แล้ว schedule ทุก N นาที
    schedule.every(interval_minutes).minutes.do(
        check_new_matches_and_analyze, nickname, compare_with
    )

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹  หยุด scheduler แล้ว[/yellow]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CS2 Auto Analyst Scheduler")
    parser.add_argument("--nickname", "-n", required=True, help="FACEIT nickname ของคุณ")
    parser.add_argument("--compare-with", "-c", default=None, help="Pro เปรียบเทียบ เช่น s1mple")
    parser.add_argument("--interval", "-i", type=int, default=30,
                        help="ตรวจสอบทุกกี่นาที (default: 30)")
    parser.add_argument("--once", action="store_true",
                        help="รันแค่ครั้งเดียวแล้วออก")

    args = parser.parse_args()

    if args.once:
        run_analysis(args.nickname, args.compare_with)
    else:
        start_scheduler(args.nickname, args.compare_with, args.interval)
