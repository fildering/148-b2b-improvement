"""
Web Scraper Tools — ดึงข้อมูล CS2 stats จากเว็บไซต์โดยไม่ต้องใช้ API key
รองรับ: HLTV.org, csstats.gg, faceit.com (public pages)

หลักการ:
- ใช้ requests + BeautifulSoup ดึงข้อมูลจาก public HTML
- Header spoofing เพื่อหลีกเลี่ยงการถูก block
- Graceful fallback ถ้า source ใด source หนึ่งใช้ไม่ได้
- Timeout ทุก request เพื่อป้องกันค้าง
"""

import re
import time
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Browser-like headers เพื่อหลีกเลี่ยงการถูก block ──────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,th;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

# Request timeout (seconds) — ป้องกันค้างนาน
REQUEST_TIMEOUT = 12

# ── รายชื่อ pro player IDs ที่รู้จักบน HLTV ──────────────────────────────
HLTV_KNOWN_IDS: dict[str, tuple[int, str]] = {
    # player_name_lower: (hltv_id, hltv_url_name)
    "donk":       (21202, "donk"),
    "s1mple":     (7998,  "s1mple"),
    "zywoo":      (11893, "ZywOo"),
    "niko":       (3741,  "NiKo"),
    "device":     (429,   "device"),
    "electronic": (8032,  "electronic"),
    "ropz":       (11816, "ropz"),
    "broky":      (15477, "broky"),
    "karrigan":   (429,   "karrigan"),
    "gla1ve":     (2099,  "gla1ve"),
    "blameF":     (12788, "blameF"),
    "jl":         (19280, "jL"),
    "twistzz":    (10394, "Twistzz"),
    "nafany":     (15425, "nafany"),
    "m0nesy":     (18575, "m0NESY"),
}


# ══════════════════════════════════════════════════════════════════════════════
# Helper utilities
# ══════════════════════════════════════════════════════════════════════════════

def _safe_get(url: str, extra_headers: Optional[dict] = None,
              retries: int = 2) -> Optional[requests.Response]:
    """
    ส่ง GET request พร้อม error handling และ retry logic

    Args:
        url: URL ที่ต้องการดึง
        extra_headers: headers เพิ่มเติม (เช่น Referer)
        retries: จำนวนครั้งที่ retry เมื่อเกิด error

    Returns:
        Response object หรือ None ถ้าล้มเหลวทั้งหมด
    """
    h = {**HEADERS}
    if extra_headers:
        h.update(extra_headers)

    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=h, timeout=REQUEST_TIMEOUT,
                                allow_redirects=True)
            if resp.status_code == 200:
                return resp
            # 403/429 = blocked — wait แล้ว retry
            if resp.status_code in (403, 429) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            logger.warning("HTTP %s for %s", resp.status_code, url)
            return None
        except requests.exceptions.Timeout:
            logger.warning("Timeout fetching %s (attempt %d)", url, attempt + 1)
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error for %s: %s", url, e)
        except Exception as e:
            logger.warning("Unexpected error fetching %s: %s", url, e)

        if attempt < retries:
            time.sleep(1.5)
    return None


def _parse_float(text: str, default: float = 0.0) -> float:
    """แปลง string เป็น float อย่างปลอดภัย"""
    if not text:
        return default
    cleaned = re.sub(r"[^\d.\-]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return default


def _parse_pct(text: str, default: float = 0.0) -> float:
    """แปลง percentage string (เช่น '47.3%' หรือ '47.3') เป็น float"""
    if not text:
        return default
    cleaned = text.strip().replace("%", "")
    return _parse_float(cleaned, default)


# ══════════════════════════════════════════════════════════════════════════════
# HLTV Scraper
# ══════════════════════════════════════════════════════════════════════════════

def get_hltv_pro_by_id(player_id: int, player_name: str) -> dict:
    """
    ดึง stats ของ pro player จาก HLTV โดยใช้ player ID ที่รู้อยู่แล้ว

    Args:
        player_id: HLTV numeric player ID
        player_name: ชื่อ player ที่ปรากฏใน URL (case-sensitive)

    Returns:
        dict ที่มี: rating, kd, kast, impact, adr, dpr, hs_pct, maps_played, source
    """
    url = f"https://www.hltv.org/stats/players/{player_id}/{player_name}"
    extra_headers = {
        "Referer": "https://www.hltv.org/stats/players",
        "Host": "www.hltv.org",
    }

    resp = _safe_get(url, extra_headers=extra_headers)
    if resp is None:
        return {"error": f"ไม่สามารถเข้าถึง HLTV สำหรับ {player_name}", "source": "hltv"}

    soup = BeautifulSoup(resp.text, "lxml")
    stats: dict = {"source": "hltv", "player_name": player_name, "hltv_id": player_id}

    # ── ดึง Rating 2.0 ──────────────────────────────────────────────────────
    # HLTV แสดง rating ใน element ที่มี class เกี่ยวกับ 'rating'
    rating_el = soup.find("div", class_=re.compile(r"rating", re.I))
    if rating_el:
        # หา number ใน element
        rating_val = rating_el.find(class_=re.compile(r"(statsVal|statVal|number)", re.I))
        if rating_val:
            stats["rating"] = _parse_float(rating_val.get_text())

    # ── ดึง stat boxes (K/D, KAST, Impact, ADR, DPR) ────────────────────────
    # HLTV ใส่ stats ใน div ที่มี class 'summaryStatBreakdownHeader' + 'summaryStatBreakdownDataValue'
    stat_headers = soup.find_all(class_=re.compile(r"summaryStatBreakdownHeader", re.I))
    stat_values = soup.find_all(class_=re.compile(r"summaryStatBreakdownDataValue", re.I))

    # Map: header text → value
    header_map: dict[str, float] = {}
    for h, v in zip(stat_headers, stat_values):
        key = h.get_text(strip=True).lower()
        val = _parse_float(v.get_text(strip=True))
        header_map[key] = val

    if header_map:
        stats["kd_ratio"]  = header_map.get("k/d ratio", header_map.get("k/d", 0.0))
        stats["kast_pct"]  = header_map.get("kast", 0.0)
        stats["impact"]    = header_map.get("impact", 0.0)
        stats["adr"]       = header_map.get("adr", 0.0)
        stats["dpr"]       = header_map.get("dpr", 0.0)

    # ── HS% และ maps played จาก additional stats block ──────────────────────
    stat_rows = soup.find_all(class_=re.compile(r"(statistics-stat|playerStat)", re.I))
    for row in stat_rows:
        label_el = row.find(class_=re.compile(r"(label|header)", re.I))
        value_el = row.find(class_=re.compile(r"(value|data)", re.I))
        if label_el and value_el:
            label = label_el.get_text(strip=True).lower()
            value = value_el.get_text(strip=True)
            if "headshot" in label:
                stats["hs_pct"] = _parse_pct(value)
            elif "maps played" in label or "maps" in label:
                stats["maps_played"] = _parse_float(value)

    # ── Fallback: ลองหา HS% จาก table rows ──────────────────────────────────
    if "hs_pct" not in stats:
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                if "headshot" in label:
                    stats["hs_pct"] = _parse_pct(cells[1].get_text(strip=True))
                    break

    # ── Player profile page เพิ่มเติม (opening duels, multi-kill rounds) ────
    profile_url = f"https://www.hltv.org/stats/players/playerprofile/{player_id}"
    profile_resp = _safe_get(profile_url, extra_headers=extra_headers)
    if profile_resp:
        profile_soup = BeautifulSoup(profile_resp.text, "lxml")
        # Opening duels — มักอยู่ใน section ที่มี 'opening'
        opening_section = profile_soup.find(
            lambda tag: tag.get_text(strip=True) and "opening" in tag.get_text(strip=True).lower()
            and tag.name in ("div", "section", "table")
        )
        if opening_section:
            numbers = re.findall(r"\d+\.?\d*", opening_section.get_text())
            if numbers:
                stats["opening_duel_rating"] = _parse_float(numbers[0])

        # Multi-kill rounds (3k, 4k, 5k)
        for mk_label in ("3k", "4k", "5k", "adr"):
            mk_el = profile_soup.find(string=re.compile(mk_label, re.I))
            if mk_el and mk_el.parent:
                sib = mk_el.parent.find_next_sibling()
                if sib:
                    stats[f"rounds_{mk_label}"] = _parse_float(sib.get_text(strip=True))

    # ── ถ้าไม่ได้ stats เลย ให้ return error ────────────────────────────────
    meaningful_keys = {"rating", "kd_ratio", "kast_pct", "adr", "hs_pct"}
    if not any(k in stats for k in meaningful_keys):
        stats["error"] = "HLTV blocked หรือ HTML structure เปลี่ยน — ลอง source อื่น"
        stats["raw_html_preview"] = resp.text[:500]  # เก็บ preview เพื่อ debug

    return stats


def get_hltv_pro_stats(player_name: str) -> dict:
    """
    ดึง stats จาก HLTV โดยหา ID จาก HLTV_KNOWN_IDS ก่อน
    ถ้าไม่รู้จัก ID จะลองค้นหาผ่าน HLTV search

    Args:
        player_name: ชื่อ in-game ของ pro player

    Returns:
        dict stats หรือ dict ที่มี 'error' key
    """
    name_lower = player_name.lower().strip()

    # ── ลองจาก known IDs ก่อน ───────────────────────────────────────────────
    if name_lower in HLTV_KNOWN_IDS:
        pid, url_name = HLTV_KNOWN_IDS[name_lower]
        result = get_hltv_pro_by_id(pid, url_name)
        if "error" not in result or "blocked" not in result.get("error", ""):
            return result

    # ── ลองค้นหาผ่าน HLTV search ─────────────────────────────────────────────
    search_url = f"https://www.hltv.org/search#query={requests.utils.quote(player_name)}"
    resp = _safe_get(search_url, extra_headers={"Referer": "https://www.hltv.org/"})

    if resp:
        soup = BeautifulSoup(resp.text, "lxml")
        # หา player links ใน search results
        player_links = soup.find_all("a", href=re.compile(r"/stats/players/\d+/"))
        if player_links:
            href = player_links[0]["href"]
            # Parse /stats/players/{id}/{name}
            match = re.search(r"/stats/players/(\d+)/(.+?)(?:\?|$)", href)
            if match:
                found_id = int(match.group(1))
                found_name = match.group(2)
                return get_hltv_pro_by_id(found_id, found_name)

    return {
        "error": f"ไม่พบ '{player_name}' บน HLTV",
        "source": "hltv",
        "player_name": player_name,
    }


# ══════════════════════════════════════════════════════════════════════════════
# FACEIT Public Page Scraper (ไม่ต้องใช้ API key)
# ══════════════════════════════════════════════════════════════════════════════

def get_public_faceit_stats(nickname: str) -> dict:
    """
    ดึง stats จาก FACEIT public profile page โดยไม่ต้อง API key
    URL: https://www.faceit.com/en/players/{nickname}/stats/cs2

    Args:
        nickname: FACEIT nickname

    Returns:
        dict ที่มี stats หรือ error message
    """
    url = f"https://www.faceit.com/en/players/{nickname}/stats/cs2"
    extra_headers = {
        "Referer": "https://www.faceit.com/",
        "Host": "www.faceit.com",
    }

    resp = _safe_get(url, extra_headers=extra_headers)
    if resp is None:
        return {"error": f"ไม่สามารถเข้าถึง FACEIT profile ของ {nickname}", "source": "faceit_public"}

    soup = BeautifulSoup(resp.text, "lxml")
    stats: dict = {"source": "faceit_public", "nickname": nickname}

    # ── ดึง stats จาก JSON-LD หรือ __NEXT_DATA__ ─────────────────────────────
    # FACEIT เป็น Next.js app — ข้อมูลมักฝังใน script tag
    next_data_script = soup.find("script", id="__NEXT_DATA__")
    if next_data_script:
        try:
            import json
            data = json.loads(next_data_script.string)
            # Navigate the Next.js page props structure
            page_props = (
                data.get("props", {})
                    .get("pageProps", {})
            )
            # ลองหา player stats ใน props
            player_stats = (
                page_props.get("playerStats", {}) or
                page_props.get("stats", {}) or
                page_props.get("lifetimeStats", {})
            )
            if player_stats:
                stats.update(_extract_faceit_next_stats(player_stats))
                return stats
        except Exception as e:
            logger.debug("Failed to parse __NEXT_DATA__: %s", e)

    # ── Fallback: ดึงจาก rendered HTML ──────────────────────────────────────
    # หา stat cards ที่ FACEIT render ใน HTML
    stat_containers = soup.find_all(
        class_=re.compile(r"(stat|statistic|metric|kpi)", re.I)
    )

    for container in stat_containers:
        label_el = container.find(class_=re.compile(r"(label|title|name)", re.I))
        value_el = container.find(class_=re.compile(r"(value|number|count)", re.I))
        if not (label_el and value_el):
            continue
        label = label_el.get_text(strip=True).lower()
        value_text = value_el.get_text(strip=True)

        if "k/d" in label or "kd" in label:
            stats["kd_ratio"] = _parse_float(value_text)
        elif "headshot" in label or "hs" in label:
            stats["hs_pct"] = _parse_pct(value_text)
        elif "win rate" in label or "win %" in label:
            stats["win_rate"] = _parse_pct(value_text)
        elif "avg kills" in label or "kills" in label:
            stats["avg_kills"] = _parse_float(value_text)
        elif "adr" in label:
            stats["adr"] = _parse_float(value_text)
        elif "matches" in label:
            stats["matches"] = _parse_float(value_text)

    # ── ดึง ELO / Level จาก profile header ──────────────────────────────────
    elo_el = soup.find(string=re.compile(r"\d{3,5}\s*ELO", re.I))
    if elo_el:
        elo_match = re.search(r"(\d{3,5})", str(elo_el))
        if elo_match:
            stats["elo"] = int(elo_match.group(1))

    level_el = soup.find(alt=re.compile(r"level\s*\d+", re.I))
    if level_el:
        level_match = re.search(r"(\d+)", level_el.get("alt", ""))
        if level_match:
            stats["level"] = int(level_match.group(1))

    # ── ถ้าไม่ได้ stats เลย ────────────────────────────────────────────────
    meaningful = {"kd_ratio", "hs_pct", "win_rate", "avg_kills"}
    if not any(k in stats for k in meaningful):
        stats["warning"] = (
            "FACEIT อาจ render ด้วย JavaScript — stats อาจไม่ครบถ้วน "
            "ลองใช้ FACEIT API แทน"
        )

    return stats


def _extract_faceit_next_stats(raw: dict) -> dict:
    """
    แปลง Next.js props structure ของ FACEIT เป็น normalized stats dict
    """
    result = {}
    # ลอง keys ที่เป็นไปได้หลายแบบ
    kd = raw.get("KD Ratio") or raw.get("kd_ratio") or raw.get("Average K/D Ratio")
    if kd:
        result["kd_ratio"] = _parse_float(str(kd))

    hs = raw.get("Headshots %") or raw.get("hs_pct") or raw.get("Average Headshots %")
    if hs:
        result["hs_pct"] = _parse_pct(str(hs))

    wins = raw.get("Win Rate %") or raw.get("win_rate")
    if wins:
        result["win_rate"] = _parse_pct(str(wins))

    kills = raw.get("Average Kills") or raw.get("avg_kills")
    if kills:
        result["avg_kills"] = _parse_float(str(kills))

    matches = raw.get("Matches") or raw.get("matches")
    if matches:
        result["matches"] = _parse_float(str(matches))

    return result


# ══════════════════════════════════════════════════════════════════════════════
# csstats.gg Scraper
# ══════════════════════════════════════════════════════════════════════════════

def get_csstats_stats(identifier: str) -> dict:
    """
    ดึง stats จาก csstats.gg
    รองรับ Steam ID หรือ username

    Args:
        identifier: Steam64 ID หรือ username

    Returns:
        dict stats หรือ error
    """
    stats: dict = {"source": "csstats_gg", "identifier": identifier}

    # ── ลอง API endpoint ก่อน ────────────────────────────────────────────────
    api_url = f"https://api.csstats.gg/api/players/{identifier}"
    api_resp = _safe_get(api_url, extra_headers={"Referer": "https://csstats.gg/"})

    if api_resp:
        try:
            import json as _json
            data = _json.loads(api_resp.text)
            if isinstance(data, dict) and not data.get("error"):
                # csstats.gg API response structure
                player_data = data.get("player", data)
                if player_data:
                    stats.update({
                        "kd_ratio":   _parse_float(str(player_data.get("kd", 0))),
                        "hs_pct":     _parse_pct(str(player_data.get("hs_pct", 0))),
                        "win_rate":   _parse_pct(str(player_data.get("win_rate", 0))),
                        "avg_kills":  _parse_float(str(player_data.get("kills_per_round", 0))),
                        "adr":        _parse_float(str(player_data.get("adr", 0))),
                        "matches":    _parse_float(str(player_data.get("matches", 0))),
                    })
                    return stats
        except Exception as e:
            logger.debug("csstats API parse error: %s", e)

    # ── Fallback: scrape HTML page ────────────────────────────────────────────
    html_url = f"https://csstats.gg/player/{identifier}"
    html_resp = _safe_get(html_url, extra_headers={"Referer": "https://csstats.gg/"})

    if html_resp is None:
        return {**stats, "error": "ไม่สามารถเข้าถึง csstats.gg"}

    soup = BeautifulSoup(html_resp.text, "lxml")

    # หา stat values — csstats.gg มักใช้ div ที่มี class 'value' และ 'label'
    stat_blocks = soup.find_all(class_=re.compile(r"(stat-block|stat_block|player-stat)", re.I))
    for block in stat_blocks:
        val_el = block.find(class_=re.compile(r"value", re.I))
        lab_el = block.find(class_=re.compile(r"(label|title)", re.I))
        if not (val_el and lab_el):
            continue
        label = lab_el.get_text(strip=True).lower()
        value = val_el.get_text(strip=True)
        if "k/d" in label:
            stats["kd_ratio"] = _parse_float(value)
        elif "headshot" in label:
            stats["hs_pct"] = _parse_pct(value)
        elif "win" in label:
            stats["win_rate"] = _parse_pct(value)
        elif "adr" in label:
            stats["adr"] = _parse_float(value)
        elif "kills" in label:
            stats["avg_kills"] = _parse_float(value)

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# Multi-source search
# ══════════════════════════════════════════════════════════════════════════════

def search_pro_player(name: str) -> dict:
    """
    ค้นหา pro player จากหลาย sources และ merge ข้อมูลที่ได้

    ลำดับการลอง:
    1. HLTV (ข้อมูล pro level ดีที่สุด)
    2. FACEIT public page
    3. csstats.gg

    Args:
        name: ชื่อ in-game ของ pro player

    Returns:
        dict ที่รวม stats จากหลาย sources พร้อม 'sources_tried' key
    """
    merged: dict = {
        "player_name": name,
        "sources_tried": [],
        "sources_success": [],
    }

    # ── 1. ลอง HLTV ────────────────────────────────────────────────────────
    print(f"  [WebScraper] กำลังดึงข้อมูล {name} จาก HLTV...")
    hltv_stats = get_hltv_pro_stats(name)
    merged["sources_tried"].append("hltv")

    if "error" not in hltv_stats:
        # HLTV สำเร็จ — ใส่ข้อมูลลงใน merged
        _merge_stats(merged, hltv_stats, priority=3)
        merged["sources_success"].append("hltv")
        merged["hltv_data"] = hltv_stats
        print(f"  [WebScraper] HLTV สำเร็จ: {list(hltv_stats.keys())}")
    else:
        print(f"  [WebScraper] HLTV ล้มเหลว: {hltv_stats.get('error', 'unknown')}")

    # ── 2. ลอง FACEIT public page ────────────────────────────────────────────
    # เฉพาะ pro players บางคนมี FACEIT account สาธารณะ
    # ใช้ชื่อ in-game เดิมเป็น FACEIT nickname (มักตรงกัน)
    print(f"  [WebScraper] กำลังดึงข้อมูล {name} จาก FACEIT public...")
    faceit_stats = get_public_faceit_stats(name)
    merged["sources_tried"].append("faceit_public")

    if "error" not in faceit_stats and any(
        k in faceit_stats for k in ("kd_ratio", "hs_pct", "win_rate")
    ):
        _merge_stats(merged, faceit_stats, priority=2)
        merged["sources_success"].append("faceit_public")
        merged["faceit_data"] = faceit_stats
        print(f"  [WebScraper] FACEIT สำเร็จ: {list(faceit_stats.keys())}")
    else:
        print(f"  [WebScraper] FACEIT ข้อมูลไม่ครบ (อาจต้อง API key)")

    # ── 3. ลอง csstats.gg ────────────────────────────────────────────────────
    # csstats ต้องการ Steam ID ซึ่งเราอาจไม่มี — ลองใช้ชื่อก่อน
    print(f"  [WebScraper] กำลังดึงข้อมูล {name} จาก csstats.gg...")
    cs_stats = get_csstats_stats(name)
    merged["sources_tried"].append("csstats_gg")

    if "error" not in cs_stats and any(
        k in cs_stats for k in ("kd_ratio", "hs_pct", "adr")
    ):
        _merge_stats(merged, cs_stats, priority=1)
        merged["sources_success"].append("csstats_gg")
        merged["csstats_data"] = cs_stats
        print(f"  [WebScraper] csstats.gg สำเร็จ")
    else:
        print(f"  [WebScraper] csstats.gg ล้มเหลว")

    # ── สรุปผล ───────────────────────────────────────────────────────────────
    if not merged["sources_success"]:
        merged["error"] = f"ไม่สามารถดึงข้อมูล '{name}' จาก source ใดเลย"

    return merged


def _merge_stats(base: dict, new_stats: dict, priority: int = 1):
    """
    Merge stats จาก new_stats เข้า base dict
    ใช้ priority เพื่อตัดสินว่า source ไหนน่าเชื่อถือกว่า
    Stats ที่มีค่า > 0 และ priority สูงกว่าจะ override
    """
    stat_keys = {
        "rating", "kd_ratio", "kast_pct", "impact", "adr", "dpr",
        "hs_pct", "maps_played", "avg_kills", "win_rate", "matches",
        "opening_duel_rating", "elo", "level",
    }

    for key in stat_keys:
        if key in new_stats and new_stats[key]:
            val = new_stats[key]
            if isinstance(val, (int, float)) and val > 0:
                existing_priority = base.get(f"_{key}_priority", 0)
                if priority >= existing_priority:
                    base[key] = val
                    base[f"_{key}_priority"] = priority
