@echo off
title Spam SMS Classifier - Flask Server
echo ===================================================
echo   Spam SMS Classifier - Starting Flask Server
echo ===================================================
echo.
cd /d "%~dp0backend"
python app.py
pause
