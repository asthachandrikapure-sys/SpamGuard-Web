@echo off
title SPAMGUARD — Real-Time SMS Security
echo ========================================================
echo   SPAMGUARD — AI-Powered SMS Security Platform
echo   Real-Time SMS Security
echo ========================================================
echo.
cd /d "%~dp0backend"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" app.py
) else (
    py -3.13 app.py 2>nul || python app.py
)
pause
