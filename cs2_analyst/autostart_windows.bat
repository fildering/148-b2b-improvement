@echo off
REM ลงทะเบียน CS2 Analyst ให้รันอัตโนมัติตอน Windows เปิด
REM รันไฟล์นี้ครั้งเดียวเท่านั้น (ต้องเปิด Admin)

set TASK_NAME=CS2_Auto_Analyst
set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe

REM ถามว่าใช้ nickname อะไร
set /p NICK="FACEIT nickname ของคุณ: "
set /p PRO="เปรียบเทียบกับ pro (ว่างไว้ถ้าไม่ต้องการ, เช่น s1mple): "

REM สร้าง run_scheduler.bat
(
echo @echo off
echo cd /d "%SCRIPT_DIR%"
echo call venv\Scripts\activate.bat
if "%PRO%"=="" (
echo python scheduler.py --nickname %NICK% --interval 30
) else (
echo python scheduler.py --nickname %NICK% --compare-with %PRO% --interval 30
)
) > "%SCRIPT_DIR%run_scheduler.bat"

REM ลงทะเบียน Windows Task Scheduler
schtasks /create /tn "%TASK_NAME%" /tr "%SCRIPT_DIR%run_scheduler.bat" /sc ONLOGON /delay 0001:00 /f

if errorlevel 1 (
    echo [ERROR] ต้องรันในฐานะ Administrator!
    echo คลิกขวาที่ไฟล์นี้ แล้วเลือก "Run as administrator"
) else (
    echo.
    echo ============================================
    echo  ✅ ติดตั้งสำเร็จ!
    echo  CS2 Analyst จะรันอัตโนมัติทุกครั้งที่เปิด Windows
    echo  ตรวจสอบ matches ใหม่ทุก 30 นาที
    echo  รายงานอยู่ที่: %SCRIPT_DIR%output\reports\
    echo ============================================
)
pause
