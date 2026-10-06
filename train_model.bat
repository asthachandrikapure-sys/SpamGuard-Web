@echo off
title Spam SMS Classifier - Model Training
echo ===================================================
echo   Spam SMS Classifier - Training ML Models
echo ===================================================
echo.
cd /d "%~dp0backend"
python train_model.py
echo.
echo Model training completed!
pause
