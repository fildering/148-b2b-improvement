@echo off
REM Quick run script — double-click เพื่อรันได้เลย

call venv\Scripts\activate.bat 2>nul

if "%1"=="" (
    echo วิธีใช้:
    echo   run.bat --nickname yourFaceitNick
    echo   run.bat --nickname yourNick --level faceit_10 --save-report
    echo   run.bat --demo mock
    echo.
    set /p NICK="ใส่ FACEIT nickname (หรือ Enter เพื่อใช้ mock): "
    if "%NICK%"=="" (
        python main.py --demo mock --current-level 7 --goal-level 10
    ) else (
        python main.py --nickname %NICK% --save-report
    )
) else (
    python main.py %*
)

pause
