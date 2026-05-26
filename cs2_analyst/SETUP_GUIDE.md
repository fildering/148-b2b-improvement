# 🛠️ Setup Guide (Windows)

## ขั้นตอนที่ 1 — โคลน repo ลงเครื่อง

เปิด **Command Prompt** หรือ **PowerShell** แล้วรัน:

```bat
mkdir C:\Claude\cs
cd C:\Claude\cs
git clone https://github.com/fildering/148-b2b-improvement.git .
cd cs2_analyst
```

หรือถ้าไม่มี git → ดาวน์โหลด ZIP จาก GitHub แล้วแตกไฟล์ไปที่ `C:\Claude\cs\cs2_analyst`

---

## ขั้นตอนที่ 2 — ติดตั้ง Python

ดาวน์โหลด Python 3.11+ จาก [python.org](https://www.python.org/downloads/)

> ⚠️ ติ๊ก **"Add Python to PATH"** ตอนติดตั้ง!

---

## ขั้นตอนที่ 3 — รัน Setup Script

```bat
cd C:\Claude\cs\cs2_analyst
setup_windows.bat
```

Script จะ:
- สร้าง virtual environment
- ติดตั้ง packages ทั้งหมด
- เปิด `.env` ให้แก้ไข API keys

---

## ขั้นตอนที่ 4 — ตั้งค่า API Keys

### 🔑 Google Gemini API Key (จำเป็น — ฟรี!)

1. ไปที่ **[aistudio.google.com](https://aistudio.google.com/)**
2. Login ด้วย Google account
3. คลิก **"Get API key"** (มุมบนขวา)
4. คลิก **"Create API key"** → เลือก Project (หรือสร้างใหม่)
5. Copy key (ขึ้นต้นด้วย `AIza...`)
6. ใส่ใน `.env`:
   ```
   GEMINI_API_KEY=AIzaxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

> ✅ **ฟรีทั้งหมด!** Free tier ของ Gemini 2.0 Flash:
> - 1,500 requests/วัน
> - 1 ล้าน tokens/วัน
> - ไม่ต้องใส่บัตรเครดิต

---

### 🔑 FACEIT API Key (ฟรี — สำหรับ auto-download demos)

1. ไปที่ [developers.faceit.com](https://developers.faceit.com/)
2. Login ด้วย FACEIT account
3. คลิก **"My Apps"** → **"Create App"**
4. ตั้งชื่อ App เช่น `CS2 Analyst`
5. เลือก **"Server-side API key"**
6. Copy API key
7. ใส่ใน `.env`:
   ```
   FACEIT_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```

> ✅ FACEIT API ฟรี 100% ไม่มีค่าใช้จ่าย
> 📥 API นี้จะให้ demo download URL อัตโนมัติ ไม่ต้องโหลดเองเลย!

---

## ขั้นตอนที่ 5 — รันโปรแกรม

### ทดสอบก่อน (ไม่ต้องมี API key)
```bat
python main.py --demo mock
```

### วิเคราะห์ด้วย FACEIT nickname
```bat
python main.py --nickname yourFaceitNick
```

### วิเคราะห์และบันทึก report
```bat
python main.py --nickname yourFaceitNick --save-report
# report อยู่ที่: output\report.md
```

### Double-click สะดวกๆ
```bat
run.bat
```
แล้วพิมพ์ nickname ได้เลย!

---

## 📁 โครงสร้างโฟลเดอร์หลังติดตั้ง

```
C:\Claude\cs\cs2_analyst\
├── .env                  ← API keys (อย่า share ให้ใคร!)
├── main.py
├── run.bat               ← double-click รันได้เลย
├── agents\
├── tools\
├── data\
│   └── demos\            ← demo files ดาวน์โหลดอัตโนมัติมาเก็บที่นี่
└── output\
    └── report.md         ← รายงานผล
```

---

## ❓ FAQ

**Q: ต้องมี CS2 ติดตั้งไหม?**
A: ไม่ต้องครับ! parse demo ได้โดยตรงโดยไม่ต้องเปิดเกม

**Q: demo ดาวน์โหลดอัตโนมัติยังไง?**
A: FACEIT API ให้ download URL มาตรงๆ โปรแกรมจะ download → extract → parse ให้เองอัตโนมัติ

**Q: ถ้าเล่น Valve Matchmaking (Premier) ได้ไหม?**
A: ได้ครับ แต่ต้องเพิ่ม Steam API Key และดาวน์โหลด demo จาก CS2 client ก่อน (รองรับใน roadmap)

**Q: ไม่มี FACEIT account ล่ะ?**
A: ยังใช้งานได้ครับ ส่ง `--demo mock` เพื่อทดสอบ หรือ download demo file มาเองจาก CS2 แล้วส่ง `--demo path\to\file.dem`
