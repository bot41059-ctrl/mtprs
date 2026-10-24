@echo off
title Ultimate Telegram Video Downloader Bot
echo ====================================================
echo  Starting Ultimate Telegram Video Downloader Bot...
echo ====================================================
cd /d "%~dp0"
python modules\main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot stopped with error code %ERRORLEVEL%.
    pause
)
