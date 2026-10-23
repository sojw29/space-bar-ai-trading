@echo off
setlocal
cd /d "%~dp0"
echo SPACE BAR AI TRADING - LOCAL HISTORICAL RESEARCH ONLY
echo No real orders or exchange account access.
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 space_bar_launcher.py
) else (
    python space_bar_launcher.py
)
if errorlevel 1 (
    echo.
    echo Launcher could not start. Install Python 3 with tkinter enabled.
    pause
)
endlocal
