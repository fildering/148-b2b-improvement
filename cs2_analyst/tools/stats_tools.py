"""
Stats Analysis Tools — คำนวณและวิเคราะห์ performance metrics
"""

import math
from typing import Any


def calculate_kd_ratio(kills: int, deaths: int) -> float:
    """คำนวณ K/D ratio"""
    if deaths == 0:
        return float(kills)
    return round(kills / deaths, 2)


def calculate_hs_percentage(hs_kills: int, total_kills: int) -> float:
    """คำนวณ headshot percentage"""
    if total_kills == 0:
        return 0.0
    return round((hs_kills / total_kills) * 100, 1)


def calculate_impact_score(kills: int, deaths: int, assists: int,
                            adr: float, rounds: int) -> float:
    """
    Impact Score — วัดผลกระทบต่อเกม
    ดัดแปลงจากสูตร HLTV Rating 2.0
    """
    if rounds == 0:
        return 0.0
    kpr = kills / rounds        # kills per round
    dpr = deaths / rounds       # deaths per round
    apr = assists / rounds      # assists per round
    impact = 2.13 * kpr + 0.42 * apr - 0.41 * dpr
    adr_factor = adr / 100.0 if adr > 0 else 1.0
    return round((impact * 0.7 + adr_factor * 0.3) * 1.0, 3)


def analyze_weapon_usage(kills: list[dict]) -> dict:
    """วิเคราะห์ weapon ที่ใช้บ่อยและ effective"""
    weapon_stats: dict[str, dict] = {}
    for kill in kills:
        w = kill.get("weapon", "unknown")
        if w not in weapon_stats:
            weapon_stats[w] = {"total": 0, "headshots": 0}
        weapon_stats[w]["total"] += 1
        if kill.get("headshot", False):
            weapon_stats[w]["headshots"] += 1

    result = []
    for weapon, data in weapon_stats.items():
        total = data["total"]
        hs = data["headshots"]
        result.append({
            "weapon": weapon,
            "kills": total,
            "hs_pct": round((hs / total) * 100, 1) if total > 0 else 0,
        })

    result.sort(key=lambda x: x["kills"], reverse=True)
    return {"weapons": result, "most_used": result[0]["weapon"] if result else "N/A"}


def analyze_round_performance(match_history: list[dict]) -> dict:
    """
    วิเคราะห์ pattern ชนะ/แพ้
    ดูว่า pistol rounds, eco rounds แม่แต่ละประเภทเป็นยังไง
    """
    wins = sum(1 for m in match_history if m.get("won", False))
    total = len(match_history)
    win_rate = round((wins / total) * 100, 1) if total > 0 else 0

    # score differential
    score_diffs = []
    for m in match_history:
        t1 = m.get("score_t1", 0)
        t2 = m.get("score_t2", 0)
        score_diffs.append(t1 - t2)

    avg_diff = round(sum(score_diffs) / len(score_diffs), 1) if score_diffs else 0
    close_games = sum(1 for d in score_diffs if abs(d) <= 3)

    return {
        "total_matches": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate_pct": win_rate,
        "avg_score_diff": avg_diff,
        "close_games": close_games,
        "close_game_rate": round((close_games / total) * 100, 1) if total else 0,
    }


def compare_stats(your_stats: dict, reference_stats: dict, label: str = "Pro") -> dict:
    """
    เปรียบเทียบ stats ของเรากับ reference (pro หรือค่าเฉลี่ย)
    ส่งกลับ percentage difference และ rating
    """
    metrics = ["kd_ratio", "headshots_pct", "win_rate", "avg_kills", "adr"]
    comparison = []

    for metric in metrics:
        your_val = _safe_float(your_stats.get(metric, 0))
        ref_val = _safe_float(reference_stats.get(metric, 0))

        if ref_val == 0:
            continue

        diff_pct = round(((your_val - ref_val) / ref_val) * 100, 1)
        rating = _rate_diff(diff_pct)

        comparison.append({
            "metric": metric,
            "yours": your_val,
            f"{label.lower()}_avg": ref_val,
            "diff_pct": diff_pct,
            "rating": rating,
        })

    # Overall score (ค่าเฉลี่ย rating)
    scores = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
    avg_score = sum(scores.get(c["rating"], 3) for c in comparison) / max(len(comparison), 1)
    overall = ["D", "C", "B", "A", "S"][min(int(avg_score) - 1, 4)]

    return {
        "comparison": comparison,
        "overall_rating": overall,
        "reference_label": label,
        "strengths": [c["metric"] for c in comparison if c["diff_pct"] >= 10],
        "weaknesses": [c["metric"] for c in comparison if c["diff_pct"] < -15],
    }


def get_benchmark_stats(level: str = "faceit_10") -> dict:
    """
    ค่า benchmark stats สำหรับแต่ละ level
    ใช้เปรียบเทียบว่าต้อง improve อะไร
    """
    benchmarks = {
        "faceit_5": {
            "kd_ratio": 0.95, "headshots_pct": 38.0,
            "win_rate": 50.0, "avg_kills": 17.0, "adr": 72.0,
        },
        "faceit_7": {
            "kd_ratio": 1.10, "headshots_pct": 44.0,
            "win_rate": 52.0, "avg_kills": 19.5, "adr": 82.0,
        },
        "faceit_10": {
            "kd_ratio": 1.35, "headshots_pct": 52.0,
            "win_rate": 55.0, "avg_kills": 22.0, "adr": 95.0,
        },
        "pro": {
            "kd_ratio": 1.65, "headshots_pct": 60.0,
            "win_rate": 58.0, "avg_kills": 25.0, "adr": 112.0,
        },
    }
    return benchmarks.get(level, benchmarks["faceit_10"])


def identify_improvement_areas(comparison_result: dict) -> list[dict]:
    """
    ระบุจุดที่ต้องพัฒนา พร้อมคำแนะนำเฉพาะเรื่อง
    """
    tips = {
        "kd_ratio": {
            "title": "การเอาชีวิตรอด / Trade",
            "advice": [
                "Peek ทีละ angle อย่า multi-peek",
                "Play off your teammates — อย่า solo push",
                "ถ้า K/D < 1.0 ลอง play passive กว่านี้",
                "Watch demos ของ round ที่ตายโง่ๆ",
            ],
        },
        "headshots_pct": {
            "title": "Aim / Crosshair Placement",
            "advice": [
                "ฝึก aim_training map หรือ Aim Lab",
                "Crosshair ต้องอยู่ที่ head level เสมอ",
                "ลด mouse sensitivity ถ้า spray ไม่นิ่ง",
                "ฝึก flick shots ใน deathmatch",
            ],
        },
        "win_rate": {
            "title": "Team Play / Strategy",
            "advice": [
                "Communicate ข้อมูลกับทีมให้มากขึ้น",
                "เรียน execute standard ของแต่ละ map",
                "อย่า tilt — ถ้าแพ้ติดกัน 2 ให้หยุดพัก",
                "Review economy ของทีมก่อนซื้ออาวุธ",
            ],
        },
        "avg_kills": {
            "title": "Aggressiveness / Impact",
            "advice": [
                "เรียน entry frag — peek เพื่อเปิดทาง",
                "อย่า over-passive — info เฉยๆ ไม่พอ",
                "เรียน off-angles เพื่อ catch คู่แข่ง",
                "Warm up ใน deathmatch ก่อนเล่น ranked",
            ],
        },
        "adr": {
            "title": "Damage Per Round",
            "advice": [
                "Aim ที่ body ถ้า spray — ดีกว่า miss head",
                "Use utility ก่อน engage เพื่อ chip damage",
                "อย่า abandon gun fights กลางคัน",
                "ฝึก spray control ของ AK/M4",
            ],
        },
    }

    areas = []
    for weakness in comparison_result.get("weaknesses", []):
        if weakness in tips:
            areas.append({
                "area": tips[weakness]["title"],
                "metric": weakness,
                "priority": "HIGH",
                "advice": tips[weakness]["advice"],
            })

    return areas


# ── Helpers ──

def _safe_float(val: Any) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _rate_diff(diff_pct: float) -> str:
    if diff_pct >= 20:
        return "S"
    elif diff_pct >= 5:
        return "A"
    elif diff_pct >= -10:
        return "B"
    elif diff_pct >= -20:
        return "C"
    else:
        return "D"
