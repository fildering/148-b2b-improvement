# 🎮 CS2 Multi-Agent Performance Analyst

วิเคราะห์ performance CS2 ด้วย multi-agent AI — เปรียบเทียบ stats กับ pro player และรับ training plan เฉพาะบุคคล

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              Orchestrator Agent                  │
│         (ประสานงาน pipeline ทั้งหมด)             │
└──────┬──────────────┬──────────────┬─────────────┘
       │              │              │
  ┌────▼────┐   ┌─────▼────┐  ┌─────▼──────┐
  │  Data   │   │ Analysis │  │Comparison  │
  │  Agent  │   │  Agent   │  │   Agent    │
  │         │   │          │  │            │
  │• Demo   │   │• K/D     │  │• vs Bench  │
  │  Parser │   │• HS%     │  │• vs Pro    │
  │• FACEIT │   │• Weapons │  │• Ratings   │
  │  API    │   │• Rounds  │  │  S/A/B/C/D │
  └────┬────┘   └─────┬────┘  └─────┬──────┘
       │              │              │
       └──────────────▼──────────────┘
                      │
               ┌──────▼──────┐
               │    Coach    │
               │    Agent    │
               │             │
               │• Training   │
               │  Plan       │
               │• Daily      │
               │  Warm-up    │
               │• Weekly     │
               │  Goals      │
               └─────────────┘
```

## 📦 Data Sources

| แหล่งข้อมูล | ข้อมูลที่ได้ | วิธีเข้าถึง |
|------------|------------|------------|
| **CS2 Demo (.dem)** | Kills, positions, utility, rounds | `demoparser2` library |
| **FACEIT API** | Lifetime stats, match history, ELO | Official API (ฟรี) |
| **Benchmark DB** | Stats เฉลี่ยแต่ละ level | Built-in database |

## 🚀 การติดตั้ง

```bash
cd cs2_analyst

# สร้าง virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# หรือ venv\Scripts\activate  # Windows

# ติดตั้ง dependencies
pip install -r requirements.txt

# ตั้งค่า API keys
cp .env.example .env
# แก้ไข .env ใส่ keys ของคุณ
```

## ⚙️ การตั้งค่า

แก้ไขไฟล์ `.env`:
```env
ANTHROPIC_API_KEY=your_key  # จำเป็น
FACEIT_API_KEY=your_key     # optional
```

- **Anthropic API Key**: สมัครที่ [console.anthropic.com](https://console.anthropic.com/)
- **FACEIT API Key**: สมัครฟรีที่ [developers.faceit.com](https://developers.faceit.com/)

## 🎯 การใช้งาน

### วิเคราะห์จาก FACEIT nickname
```bash
python main.py --nickname yourFaceitNick
```

### วิเคราะห์จาก demo file
```bash
python main.py --demo /path/to/match.dem
```

### วิเคราะห์ทั้งคู่พร้อมกัน
```bash
python main.py --nickname yourNick --demo /path/to/match.dem
```

### เปรียบเทียบกับ pro level
```bash
python main.py --nickname yourNick --level pro
```

### ทดสอบด้วย mock data
```bash
python main.py --demo mock --current-level 7 --goal-level 10
```

### บันทึก report
```bash
python main.py --nickname yourNick --save-report
# ผลลัพธ์: output/report.md
```

## 📊 ตัวอย่าง Output

```
╭─────────────────────────────────────────╮
│     🎮 CS2 Performance Analyst          │
│     Player: s1mple | Target: faceit_10  │
╰─────────────────────────────────────────╯

📡 Data Collection
• FACEIT ELO: 1850 (Level 8)
• K/D Ratio: 1.12 | HS%: 44.2%
• Win Rate: 55.3% (342 matches)

🔬 Performance Analysis
• Impact Score: 1.24 (Above average)
• Best weapon: AK-47 (68% of kills)
• Strongest map: de_mirage (K/D 1.25)

📊 Comparison vs Faceit Level 10
Metric        Yours    Target   Rating
K/D           1.12     1.35     C
HS%           44.2%    52.0%    C
Win Rate      55.3%    55.0%    B
ADR           82.0     95.0     C
Overall: C+

🎓 Training Plan
[Weekly schedule + daily warmup + goals]
```

## 🗂️ Project Structure

```
cs2_analyst/
├── agents/
│   ├── base_agent.py         # Base class สำหรับทุก agent
│   ├── orchestrator.py       # ประสานงาน pipeline
│   ├── data_agent.py         # ดึงข้อมูล
│   ├── analysis_agent.py     # วิเคราะห์ stats
│   ├── comparison_agent.py   # เปรียบเทียบ
│   └── coach_agent.py        # สร้าง training plan
├── tools/
│   ├── demo_tools.py         # Parse .dem files
│   ├── faceit_tools.py       # FACEIT API client
│   └── stats_tools.py        # คำนวณ metrics
├── data/                     # เก็บ demo files
├── output/                   # report output
├── main.py                   # Entry point
├── requirements.txt
└── .env.example
```

## 🔧 Customization

### เพิ่ม benchmark level
แก้ไข `tools/stats_tools.py` ใน function `get_benchmark_stats()`

### เพิ่ม data source ใหม่
1. สร้าง tool function ใน `tools/`
2. Register ใน agent ที่เกี่ยวข้อง
3. เพิ่ม tool schema ใน `TOOLS` list

---

*Built with Claude API + demoparser2 + FACEIT API*
