@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title SUPRA-Tex Workbench

if not exist ".venv314\Scripts\python.exe" goto NO_SETUP

rem Hugging Face: never use stored login info. Precision: fp16 on RTX 20, bf16 on RTX 30+.
set HF_HUB_DISABLE_IMPLICIT_TOKEN=1
set SUPRATEX_COMPLETION_DTYPE=auto

".venv314\Scripts\python.exe" -m workbench --open
echo.
pause
exit /b 0

:NO_SETUP
echo Setup has not been run. Run Setup-SUPRA-Tex.cmd first.
echo 아직 설치하지 않았습니다. Setup-SUPRA-Tex.cmd 를 먼저 실행하세요.
pause
exit /b 1
