"""
CS2 Data Extractor — รันแค่ local เพื่อดึงข้อมูล
แล้ว copy output มาวางใน Claude chat ให้วิเคราะห์

รัน: python extract.py --nickname CRACK3R
"""

import json
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("FACEIT_API_KEY", "")
BASE = "https://open.faceit.com/data/v4"

def headers():
    return {"Authorization": f"Bearer {API_KEY}"}

def get(url):
    r = requests.get(url, headers=headers(), timeout=10)
    return r.json() if r.ok else {}

def extract(nickname: str, matches: int = 20):
    print(f"🔍 กำลังดึงข้อมูล {nickname}...")

    # ── Player info ──
    p = get(f"{BASE}/players?nickname={nickname}&game=cs2")
    if not p.get("player_id"):
        print(f"❌ ไม่พบ player: {nickname}")
        sys.exit(1)

    pid = p["player_id"]
    game = p.get("games", {}).get("cs2", {})

    result = {
        "nickname": p.get("nickname"),
        "country": p.get("country"),
        "elo": game.get("faceit_elo"),
        "level": game.get("skill_level"),
    }

    # ── Lifetime stats ──
    s = get(f"{BASE}/players/{pid}/stats/cs2")
    lt = s.get("lifetime", {})
    result["lifetime"] = {
        "matches":       lt.get("Matches"),
        "wins":          lt.get("Wins"),
        "win_rate":      lt.get("Win Rate %"),
        "kd":            lt.get("Average K/D Ratio"),
        "hs_pct":        lt.get("Average Headshots %"),
        "avg_kills":     lt.get("Average Kills"),
        "avg_deaths":    lt.get("Average Deaths"),
        "avg_assists":   lt.get("Average Assists"),
        "streak_best":   lt.get("Longest Win Streak"),
        "recent_streak": lt.get("Current Win Streak"),
    }

    # ── Per-map stats ──
    maps = {}
    for seg in s.get("segments", []):
        if seg.get("type") != "Map":
            continue
        ms = seg.get("stats", {})
        maps[seg.get("label", "?")] = {
            "matches": ms.get("Matches"),
            "wins":    ms.get("Wins"),
            "kd":      ms.get("Average K/D Ratio"),
            "hs_pct":  ms.get("Average Headshots %"),
            "kr":      ms.get("Average K/R Ratio"),
        }
    result["maps"] = dict(sorted(maps.items(),
        key=lambda x: int(x[1].get("matches") or 0), reverse=True)[:8])

    # ── Recent matches detail ──
    hist = get(f"{BASE}/players/{pid}/history?game=cs2&limit={matches}")
    match_ids = [m["match_id"] for m in hist.get("items", [])]

    print(f"  → ดึง {len(match_ids)} matches ล่าสุด...")

    recent = []
    for mid in match_ids[:matches]:
        ms = get(f"{BASE}/matches/{mid}/stats")
        for rnd in ms.get("rounds", []):
            for team in rnd.get("teams", []):
                for pl in team.get("players", []):
                    if pl.get("nickname", "").lower() != nickname.lower():
                        continue
                    ps = pl.get("player_stats", {})
                    recent.append({
                        "map":      rnd.get("round_stats", {}).get("Map"),
                        "result":   rnd.get("round_stats", {}).get("Winner"),
                        "score":    rnd.get("round_stats", {}).get("Score"),
                        "kills":    ps.get("Kills"),
                        "deaths":   ps.get("Deaths"),
                        "assists":  ps.get("Assists"),
                        "hs":       ps.get("Headshots"),
                        "hs_pct":   ps.get("Headshots %"),
                        "kd":       ps.get("K/D Ratio"),
                        "kr":       ps.get("K/R Ratio"),
                        "adr":      ps.get("ADR"),
                        "mvps":     ps.get("MVPs"),
                        "rating":   ps.get("HLTV Rating"),
                        "triple":   ps.get("Triple Kills"),
                        "quad":     ps.get("Quadro Kills"),
                        "ace":      ps.get("Penta Kills"),
                        "first_kills": ps.get("First Kills"),
                    })
        if recent:
            print(f"  ✓ {len(recent)} matches", end="\r")

    result["recent_matches"] = recent

    # ── Summary stats from recent matches ──
    if recent:
        def avg(key):
            vals = [float(m[key]) for m in recent if m.get(key) is not None]
            return round(sum(vals)/len(vals), 2) if vals else 0

        result["recent_avg"] = {
            "kd":       avg("kd"),
            "adr":      avg("adr"),
            "hs_pct":   avg("hs_pct"),
            "kr":       avg("kr"),
            "kills":    avg("kills"),
            "deaths":   avg("deaths"),
            "rating":   avg("rating"),
            "mvps":     avg("mvps"),
            "first_kills": avg("first_kills"),
        }

        wins = sum(1 for m in recent
                   if m.get("result") and nickname.lower() in str(m.get("result", "")).lower())
        result["recent_win_rate"] = round(wins / len(recent) * 100, 1)

    print(f"\n✅ เสร็จแล้ว!")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--nickname", "-n", required=True)
    parser.add_argument("--matches", "-m", type=int, default=20)
    parser.add_argument("--compare", "-c", default=None,
                        help="nickname คนที่ 2 เพื่อเปรียบเทียบ")
    args = parser.parse_args()

    data = {"player": extract(args.nickname, args.matches)}

    if args.compare:
        print(f"\n🔍 กำลังดึงข้อมูล {args.compare}...")
        data["compare"] = extract(args.compare, args.matches)

    # บันทึกไฟล์
    out = f"output/{args.nickname}_data.json"
    os.makedirs("output", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n📄 บันทึกที่: {out}")
    print("\n" + "="*60)
    print("📋 COPY ข้อความด้านล่างนี้ไปวางใน Claude chat:")
    print("="*60)
    print(json.dumps(data, ensure_ascii=False, indent=2))
