@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 群约小助手

:: 优先查找 Anaconda/Miniconda Python
set PY=
for %%P in (
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "D:\application\anaconda\python.exe"
    "C:\ProgramData\anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
) do (
    if exist %%P (
        if "!PY!"=="" set PY=%%P
    )
)

:: 其次查找系统 Python
if "%PY%"=="" (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if "!PY!"=="" set PY=%%P
    )
)

if "%PY%"=="" (
    echo.
    echo  ❌  未找到 Python，请先安装 Anaconda 或 Python 3.8+
    echo      下载地址: https://www.anaconda.com/download
    echo.
    pause
    exit /b 1
)

echo.
echo  使用 Python: %PY%
echo.
"%PY%" launch.py
pause
