@echo off
title CSTCloud-RAG Environment Check
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -CheckOnly
echo.
echo Press any key to start CSTCloud-RAG now...
pause >nul
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
