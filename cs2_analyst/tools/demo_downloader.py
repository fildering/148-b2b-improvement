"""
Demo Auto-Downloader
ดาวน์โหลด demo อัตโนมัติจาก FACEIT API — ไม่ต้องโหลดเองเลย!

FACEIT API จะให้ demo_url ตรงๆ ใน match details
"""

import os
import gzip
import shutil
import hashlib
import requests
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, DownloadColumn, BarColumn, TextColumn, TimeRemainingColumn

console = Console()

FACEIT_API_BASE = "https://open.faceit.com/data/v4"
DEFAULT_DEMO_DIR = Path("data/demos")


def _headers() -> dict:
    api_key = os.environ.get("FACEIT_API_KEY", "")
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def get_match_demo_url(match_id: str) -> dict:
    """
    ดึง demo download URL จาก FACEIT match
    FACEIT ให้ URL มาตรงๆ เป็น .dem.gz
    """
    if not os.environ.get("FACEIT_API_KEY"):
        return {
            "source": "mock",
            "match_id": match_id,
            "demo_url": None,
            "note": "ต้องมี FACEIT_API_KEY เพื่อดาวน์โหลด demo จริง",
        }

    url = f"{FACEIT_API_BASE}/matches/{match_id}"
    resp = requests.get(url, headers=_headers(), timeout=15)

    if resp.status_code != 200:
        return {"error": f"API error: {resp.status_code}"}

    data = resp.json()
    demo_urls = data.get("demo_url", [])

    return {
        "match_id": match_id,
        "map": data.get("voting", {}).get("map", {}).get("pick", ["unknown"])[0] if data.get("voting") else "unknown",
        "demo_url": demo_urls[0] if demo_urls else None,
        "all_urls": demo_urls,
        "status": data.get("status"),
        "finished_at": data.get("finished_at"),
    }


def download_demo(match_id: str, demo_url: str,
                  output_dir: Path = DEFAULT_DEMO_DIR,
                  force: bool = False) -> dict:
    """
    ดาวน์โหลดและ extract demo file อัตโนมัติ
    FACEIT demos เป็น .dem.gz → extract เป็น .dem

    Args:
        match_id: FACEIT match ID
        demo_url: URL ของ .dem.gz file
        output_dir: โฟลเดอร์ที่เก็บ demos
        force: ดาวน์โหลดใหม่แม้มีอยู่แล้ว

    Returns:
        dict ที่มี path ไปยัง .dem file ที่พร้อมใช้งาน
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ชื่อไฟล์ output
    dem_path = output_dir / f"{match_id}.dem"
    gz_path = output_dir / f"{match_id}.dem.gz"

    # ถ้ามีอยู่แล้วและไม่ force
    if dem_path.exists() and not force:
        console.print(f"[dim]✅ Demo มีอยู่แล้ว: {dem_path}[/dim]")
        return {"path": str(dem_path), "match_id": match_id, "cached": True}

    # ── Download ──
    console.print(f"[cyan]⬇️  กำลังดาวน์โหลด demo: {match_id}[/cyan]")

    try:
        resp = requests.get(demo_url, stream=True, timeout=60)
        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0))

        with Progress(
            TextColumn("[cyan]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"Downloading {match_id[:12]}...", total=total_size)

            with open(gz_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    progress.update(task, advance=len(chunk))

    except requests.RequestException as e:
        return {"error": f"Download ล้มเหลว: {str(e)}"}

    # ── Extract .gz → .dem ──
    console.print(f"[cyan]📦 กำลัง extract...[/cyan]")
    try:
        with gzip.open(gz_path, "rb") as f_in:
            with open(dem_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        # ลบ .gz หลัง extract แล้ว
        gz_path.unlink()

        size_mb = dem_path.stat().st_size / (1024 * 1024)
        console.print(f"[green]✅ Demo พร้อมใช้งาน: {dem_path} ({size_mb:.1f} MB)[/green]")

        return {
            "path": str(dem_path),
            "match_id": match_id,
            "size_mb": round(size_mb, 1),
            "cached": False,
        }

    except (gzip.BadGzipFile, OSError) as e:
        # บางครั้ง demo ไม่ได้ compress ด้วย gzip
        if gz_path.exists():
            gz_path.rename(dem_path)
            size_mb = dem_path.stat().st_size / (1024 * 1024)
            return {"path": str(dem_path), "match_id": match_id, "size_mb": round(size_mb, 1)}
        return {"error": f"Extract ล้มเหลว: {str(e)}"}


def auto_download_recent_demos(player_id: str, limit: int = 5,
                                output_dir: Path = DEFAULT_DEMO_DIR) -> list[dict]:
    """
    ดาวน์โหลด demo ล่าสุดของ player อัตโนมัติ

    Flow: get matches → get demo URLs → download all → return paths
    """
    if not os.environ.get("FACEIT_API_KEY"):
        console.print("[yellow]⚠️  ไม่มี FACEIT_API_KEY — ไม่สามารถดาวน์โหลด demo ได้[/yellow]")
        return []

    # Step 1: ดึง match history
    console.print(f"[blue]📋 ดึง {limit} matches ล่าสุด...[/blue]")
    url = f"{FACEIT_API_BASE}/players/{player_id}/history?game=cs2&limit={limit}"
    resp = requests.get(url, headers=_headers(), timeout=15)

    if resp.status_code != 200:
        console.print(f"[red]❌ ดึง match history ล้มเหลว: {resp.status_code}[/red]")
        return []

    matches = resp.json().get("items", [])
    results = []

    # Step 2: สำหรับแต่ละ match ดึง demo URL แล้วดาวน์โหลด
    for i, match in enumerate(matches, 1):
        match_id = match.get("match_id")
        console.print(f"\n[bold]Match {i}/{len(matches)}: {match_id}[/bold]")

        demo_info = get_match_demo_url(match_id)
        demo_url = demo_info.get("demo_url")

        if not demo_url:
            console.print(f"[yellow]⚠️  ไม่มี demo URL สำหรับ match นี้[/yellow]")
            results.append({"match_id": match_id, "error": "no demo url"})
            continue

        result = download_demo(match_id, demo_url, output_dir)
        result["map"] = demo_info.get("map", "unknown")
        results.append(result)

    console.print(f"\n[bold green]✅ ดาวน์โหลดเสร็จ: {sum(1 for r in results if 'path' in r)}/{len(matches)} demos[/bold green]")
    return results


def list_cached_demos(demo_dir: Path = DEFAULT_DEMO_DIR) -> list[dict]:
    """แสดงรายการ demos ที่มีอยู่ใน local"""
    demo_dir = Path(demo_dir)
    if not demo_dir.exists():
        return []

    demos = []
    for dem_file in sorted(demo_dir.glob("*.dem"), key=lambda f: f.stat().st_mtime, reverse=True):
        size_mb = dem_file.stat().st_size / (1024 * 1024)
        demos.append({
            "file": dem_file.name,
            "path": str(dem_file),
            "size_mb": round(size_mb, 1),
            "match_id": dem_file.stem,
        })

    return demos


def clear_old_demos(demo_dir: Path = DEFAULT_DEMO_DIR, keep_last: int = 10):
    """ลบ demos เก่า เก็บแค่ล่าสุด N ไฟล์"""
    demos = list_cached_demos(demo_dir)
    to_delete = demos[keep_last:]

    for demo in to_delete:
        Path(demo["path"]).unlink(missing_ok=True)
        console.print(f"[dim]🗑️  ลบ: {demo['file']}[/dim]")

    if to_delete:
        console.print(f"[dim]ลบ {len(to_delete)} demo เก่าออก เก็บ {min(keep_last, len(demos))} ล่าสุด[/dim]")
