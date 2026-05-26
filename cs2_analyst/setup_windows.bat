@echo off
echo ============================================
echo   CS2 Multi-Agent Performance Analyst
echo   Windows Setup Script
echo ============================================
echo.

REM ตรวจสอบ Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ไม่พบ Python! กรุณาติดตั้งจาก https://python.org
    pause
    exit /b 1
)
echo [OK] Python พร้อมใช้งาน

REM สร้าง virtual environment
if not exist "venv" (
    echo [*] กำลังสร้าง virtual environment...
    python -m venv venv
)
echo [OK] Virtual environment พร้อม

REM Activate venv
call venv\Scripts\activate.bat

REM ติดตั้ง dependencies
echo [*] กำลังติดตั้ง packages...
pip install -r requirements.txt --quiet

REM สร้างโฟลเดอร์ที่จำเป็น
if not exist "data\demos" mkdir data\demos
if not exist "output" mkdir output
echo [OK] สร้างโฟลเดอร์เรียบร้อย

REM ตรวจสอบ .env
if not exist ".env" (
    echo.
    echo [!] ยังไม่มีไฟล์ .env
    copy .env.example .env >nul
    echo [*] สร้าง .env จาก template แล้ว
    echo.
    echo ===== ต้องใส่ API Keys ก่อนใช้งาน =====
    echo เปิดไฟล์ .env แล้วแก้ไข:
    echo   GROQ_API_KEY=your_key_here     (ฟรี! จาก console.groq.com)
    echo   FACEIT_API_KEY=your_key_here   (ฟรี! จาก developers.faceit.com)
    echo =========================================
    notepad .env
) else (
    echo [OK] พบ .env แล้ว
)

echo.
echo ============================================
echo   Setup เสร็จแล้ว! วิธีรัน:
echo.
echo   1. เปิด Command Prompt ใน C:\Claude\cs
echo   2. รัน: venv\Scripts\activate
echo   3. รัน: python main.py --demo mock
echo ============================================
echo.
pause
