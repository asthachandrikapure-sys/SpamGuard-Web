@echo off
title SPAMGUARD — ML Model Training
echo ========================================================
echo   SPAMGUARD — Training Support Vector Machine Model
echo ========================================================
echo.
cd /d "%~dp0backend"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" train_model.py
) else (
    py -3.13 train_model.py 2>nul || python train_model.py
)
echo.
echo Model training completed successfully!
pause
