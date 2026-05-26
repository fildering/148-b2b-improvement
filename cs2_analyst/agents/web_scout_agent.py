"""
Web Scout Agent — Agent ที่ตัดสินใจเองว่าจะไปดึงข้อมูลจากเว็บไซต์ไหน
ทำงานแบบ agentic loop: วิเคราะห์ → เลือก tool → รวมผล

หน้าที่หลัก:
- รับชื่อ player → หาข้อมูลจากหลาย source อัตโนมัติ
- Retry อัตโนมัติถ้า source หนึ่งล้มเหลว
- Return structured stats dict ที่พร้อมใช้งาน
"""

import json
import os
import logging
from typing import Optional

from agents.base_agent import BaseAgent, ToolExecutor
from tools import web_scraper
from tools import faceit_tools

logger = logging.getLogger(__name__)

# ── System prompt สำหรับ Web Scout Agent ─────────────────────────────────────
WEB_SCOUT_SYSTEM_PROMPT = """You are a CS2 data scout agent. Your job is to find accurate statistics for CS2 players from the web.

You have access to scraping tools for HLTV, FACEIT, and csstats. Always try multiple sources to get the most complete picture.

Your goal for each player:
- Rating 2.0 (HLTV) — most important pro metric
- K/D Ratio — kills per death
- HS% — headshot percentage
- ADR — average damage per round
- KAST% — rounds with Kill/Assist/Survived/Traded
- Impact score
- Opening duel stats (first kills per round)
- Matches played

Strategy:
1. Start with HLTV for pro players — most reliable source for Rating 2.0 and KAST
2. Try FACEIT for ELO, level, and ranked match stats
3. Use csstats.gg as additional verification
4. If a source fails, always try the next one — never give up after one failure
5. When you have data from multiple sources, prefer HLTV Rating/KAST, FACEIT for ELO/Level

Always return a summary with ALL stats you found, clearly labeled with which source they came from.
Report in both English and Thai (ภาษาไทย) for key findings.
"""

# ── Tool definitions สำหรับ Groq function calling ────────────────────────────
WEB_SCOUT_TOOLS = [
    {
        "name": "scrape_hltv_pro",
        "description": (
            "ดึง stats ของ pro player จาก HLTV.org "
            "ได้ Rating 2.0, K/D, KAST%, Impact, ADR, DPR, HS%, maps played "
            "เหมาะสำหรับ pro players ที่มีชื่อเสียงระดับสากล"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "player_name": {
                    "type": "string",
                    "description": "ชื่อ in-game ของ pro player เช่น 's1mple', 'ZywOo', 'NiKo'",
                }
            },
            "required": ["player_name"],
        },
    },
    {
        "name": "scrape_hltv_by_id",
        "description": (
            "ดึง stats จาก HLTV โดยระบุ player ID โดยตรง "
            "เร็วกว่า scrape_hltv_pro เพราะข้ามขั้นตอน search "
            "ใช้เมื่อรู้ HLTV ID ของผู้เล่น"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "player_id": {
                    "type": "integer",
                    "description": "HLTV numeric player ID เช่น 7998 สำหรับ s1mple",
                },
                "player_name": {
                    "type": "string",
                    "description": "ชื่อที่ใช้ใน HLTV URL เช่น 's1mple', 'ZywOo'",
                },
            },
            "required": ["player_id", "player_name"],
        },
    },
    {
        "name": "scrape_faceit_profile",
        "description": (
            "ดึง stats จาก FACEIT public profile page "
            "ไม่ต้องใช้ API key แต่อาจได้ข้อมูลไม่ครบ "
            "ได้: ELO, Level, K/D, HS%, Win Rate"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nickname": {
                    "type": "string",
                    "description": "FACEIT nickname ของผู้เล่น",
                }
            },
            "required": ["nickname"],
        },
    },
    {
        "name": "get_faceit_api_stats",
        "description": (
            "ดึง stats จาก FACEIT Official API "
            "ต้องการ FACEIT_API_KEY ใน environment variables "
            "ถ้าไม่มี key จะ return mock data "
            "ข้อมูลแม่นยำที่สุดสำหรับ FACEIT players"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nickname": {
                    "type": "string",
                    "description": "FACEIT nickname ของผู้เล่น",
                }
            },
            "required": ["nickname"],
        },
    },
    {
        "name": "scrape_csstats",
        "description": (
            "ดึง stats จาก csstats.gg "
            "รองรับ Steam ID หรือ username "
            "ข้อมูลครอบคลุมทั้ง matchmaking และ third-party platforms"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "Steam64 ID หรือ username ของผู้เล่น",
                }
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "search_all_sources",
        "description": (
            "ค้นหาข้อมูลผู้เล่นจากทุก source พร้อมกัน และ merge ผลลัพธ์ "
            "เป็น tool หลักที่ควรใช้ก่อนเพื่อประหยัดเวลา "
            "เหมาะสำหรับ pro players ที่มีชื่อเสียง"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "ชื่อ in-game ของผู้เล่น",
                }
            },
            "required": ["name"],
        },
    },
]


class WebScoutAgent(BaseAgent):
    """
    Agent ที่ค้นหาข้อมูล CS2 players จากเว็บโดยอัตโนมัติ

    ทำงานแบบ agentic loop:
    1. รับชื่อ player จาก user
    2. เลือก tool ที่เหมาะสม (HLTV/FACEIT/csstats)
    3. วิเคราะห์ผลลัพธ์
    4. ถ้าไม่ครบ → เลือก tool อื่น retry
    5. Return structured summary
    """

    def __init__(self):
        super().__init__(
            name="WebScoutAgent",
            system_prompt=WEB_SCOUT_SYSTEM_PROMPT,
            tools=WEB_SCOUT_TOOLS,
        )

        # ── ลงทะเบียน tool functions ─────────────────────────────────────────
        self.executor = ToolExecutor()
        self.executor.register("scrape_hltv_pro", self._tool_scrape_hltv_pro)
        self.executor.register("scrape_hltv_by_id", self._tool_scrape_hltv_by_id)
        self.executor.register("scrape_faceit_profile", self._tool_scrape_faceit_profile)
        self.executor.register("get_faceit_api_stats", self._tool_get_faceit_api_stats)
        self.executor.register("scrape_csstats", self._tool_scrape_csstats)
        self.executor.register("search_all_sources", self._tool_search_all_sources)

        # Cache เก็บผลลัพธ์ที่ดึงมาแล้ว ป้องกัน duplicate requests
        self._cache: dict[str, dict] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def scout_player(self, player_name: str,
                     prefer_sources: Optional[list[str]] = None) -> dict:
        """
        ค้นหาข้อมูล player อย่างอัตโนมัติ

        Args:
            player_name: ชื่อผู้เล่น (pro IGN หรือ FACEIT nickname)
            prefer_sources: ลำดับ sources ที่ต้องการ เช่น ["hltv", "faceit_api"]

        Returns:
            dict ที่มี:
                - stats: ข้อมูล stats ที่รวบรวมได้
                - narrative: คำอธิบายเป็น text
                - sources_used: list ของ sources ที่สำเร็จ
                - raw_data: ข้อมูลดิบจากแต่ละ source
        """
        # ── Reset messages เพื่อเริ่ม conversation ใหม่ ──────────────────────
        self.reset()

        # ── Build user message ───────────────────────────────────────────────
        source_hint = ""
        if prefer_sources:
            source_hint = f" Please prioritize these sources: {', '.join(prefer_sources)}."

        user_msg = (
            f"Find all available CS2 stats for player: '{player_name}'.{source_hint}\n"
            f"Try multiple sources. Start with search_all_sources tool, then fill gaps with other tools.\n"
            f"I need: K/D, HS%, ADR, Rating 2.0 (if pro), KAST%, Win Rate, matches played, ELO (if FACEIT).\n"
            f"Return a complete summary at the end."
        )

        # ── รัน agentic loop ─────────────────────────────────────────────────
        narrative = self.run(user_msg, tool_executor=self.executor)

        # ── ดึง structured stats จาก cache ──────────────────────────────────
        # ข้อมูล raw จะถูกเก็บใน self._cache ระหว่าง tool calls
        collected_stats = self._cache.get(player_name.lower(), {})

        # ── สร้าง normalized output ──────────────────────────────────────────
        return {
            "player_name": player_name,
            "stats": _normalize_stats(collected_stats),
            "narrative": narrative,
            "sources_used": collected_stats.get("sources_success", []),
            "raw_data": collected_stats,
        }

    def scout_player_fast(self, player_name: str) -> dict:
        """
        ดึงข้อมูลเร็ว (ไม่ผ่าน LLM) — ใช้เมื่อต้องการความเร็วมากกว่าความฉลาด
        เหมาะสำหรับ known pro players ที่อยู่ใน HLTV_KNOWN_IDS

        Args:
            player_name: ชื่อผู้เล่น

        Returns:
            dict stats
        """
        result = web_scraper.search_pro_player(player_name)
        self._cache[player_name.lower()] = result
        return {
            "player_name": player_name,
            "stats": _normalize_stats(result),
            "sources_used": result.get("sources_success", []),
            "raw_data": result,
        }

    # ── Tool implementations ──────────────────────────────────────────────────

    def _tool_scrape_hltv_pro(self, player_name: str) -> dict:
        """Tool: ดึงจาก HLTV ด้วยชื่อ"""
        result = web_scraper.get_hltv_pro_stats(player_name)
        self._update_cache(player_name, result)
        return result

    def _tool_scrape_hltv_by_id(self, player_id: int, player_name: str) -> dict:
        """Tool: ดึงจาก HLTV ด้วย ID"""
        result = web_scraper.get_hltv_pro_by_id(player_id, player_name)
        self._update_cache(player_name, result)
        return result

    def _tool_scrape_faceit_profile(self, nickname: str) -> dict:
        """Tool: ดึงจาก FACEIT public page"""
        result = web_scraper.get_public_faceit_stats(nickname)
        self._update_cache(nickname, result)
        return result

    def _tool_get_faceit_api_stats(self, nickname: str) -> dict:
        """Tool: ดึงจาก FACEIT API (ถ้ามี key)"""
        player = faceit_tools.get_player_by_nickname(nickname)
        if "error" in player:
            return player

        stats = faceit_tools.get_player_stats(player.get("player_id", ""))
        combined = {
            "source": "faceit_api",
            "nickname": nickname,
            "elo": player.get("elo", 0),
            "level": player.get("level", 0),
            "country": player.get("country", ""),
            **stats,
        }
        self._update_cache(nickname, combined)
        return combined

    def _tool_scrape_csstats(self, identifier: str) -> dict:
        """Tool: ดึงจาก csstats.gg"""
        result = web_scraper.get_csstats_stats(identifier)
        self._update_cache(identifier, result)
        return result

    def _tool_search_all_sources(self, name: str) -> dict:
        """Tool: ค้นหาจากทุก source และ merge"""
        result = web_scraper.search_pro_player(name)
        self._cache[name.lower()] = result
        return result

    # ── Cache helpers ─────────────────────────────────────────────────────────

    def _update_cache(self, player_name: str, new_data: dict):
        """อัพเดต cache ด้วยข้อมูลใหม่ — merge เข้ากับข้อมูลที่มีอยู่"""
        key = player_name.lower()
        if key not in self._cache:
            self._cache[key] = {}
        # Merge: ข้อมูลใหม่ override เฉพาะ keys ที่ยังไม่มี หรือ source ดีกว่า
        existing = self._cache[key]
        for k, v in new_data.items():
            if k not in existing or (v and not existing[k]):
                existing[k] = v

        # Track sources
        if "source" in new_data and "error" not in new_data:
            sources = existing.setdefault("sources_success", [])
            if new_data["source"] not in sources:
                sources.append(new_data["source"])


# ══════════════════════════════════════════════════════════════════════════════
# Standalone functions (ใช้ได้โดยไม่ต้อง instantiate WebScoutAgent)
# ══════════════════════════════════════════════════════════════════════════════

def quick_scout(player_name: str) -> dict:
    """
    Convenience function: ดึงข้อมูล player แบบ direct (ไม่ผ่าน LLM)
    เร็วที่สุด เหมาะสำหรับ known pro players

    Args:
        player_name: ชื่อผู้เล่น

    Returns:
        dict ที่มี stats, sources_used, raw_data
    """
    agent = WebScoutAgent()
    return agent.scout_player_fast(player_name)


def _normalize_stats(raw: dict) -> dict:
    """
    แปลง raw data จาก scraper เป็น normalized stats dict
    ที่ compatible กับ comparison_agent และ orchestrator

    Args:
        raw: dict ที่ได้จาก scraper (อาจมี format แตกต่างกัน)

    Returns:
        Normalized dict ที่มี keys มาตรฐาน
    """
    def _f(val, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    normalized = {}

    # K/D Ratio
    kd = raw.get("kd_ratio") or raw.get("kd") or raw.get("Average K/D Ratio") or 0
    normalized["kd_ratio"] = _f(kd)

    # HS%
    hs = (raw.get("hs_pct") or raw.get("headshots_pct") or
          raw.get("Average Headshots %") or 0)
    normalized["headshots_pct"] = _f(hs)

    # Win Rate
    wr = raw.get("win_rate") or raw.get("Win Rate %") or 0
    normalized["win_rate"] = _f(wr)

    # ADR
    adr = raw.get("adr") or raw.get("ADR") or 0
    normalized["adr"] = _f(adr)

    # Avg Kills
    kills = raw.get("avg_kills") or raw.get("Average Kills") or 0
    normalized["avg_kills"] = _f(kills)

    # Rating 2.0 (HLTV-specific)
    rating = raw.get("rating") or 0
    if rating:
        normalized["rating"] = _f(rating)

    # KAST%
    kast = raw.get("kast_pct") or raw.get("kast") or 0
    if kast:
        normalized["kast_pct"] = _f(kast)

    # Impact
    impact = raw.get("impact") or 0
    if impact:
        normalized["impact"] = _f(impact)

    # DPR
    dpr = raw.get("dpr") or 0
    if dpr:
        normalized["dpr"] = _f(dpr)

    # ELO & Level
    elo = raw.get("elo") or 0
    if elo:
        normalized["elo"] = int(_f(elo))

    level = raw.get("level") or 0
    if level:
        normalized["level"] = int(_f(level))

    # Matches
    matches = raw.get("maps_played") or raw.get("matches") or raw.get("Matches") or 0
    if matches:
        normalized["matches"] = int(_f(matches))

    # Source tracking
    normalized["_source"] = raw.get("source") or "web_scraper"
    normalized["_sources_success"] = raw.get("sources_success", [])

    return normalized
