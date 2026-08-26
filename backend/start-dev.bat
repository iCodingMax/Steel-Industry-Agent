@echo off
chcp 65001 >nul
REM 开发环境启动脚本
REM 加载 .env.dev 配置

set ENV=development
echo ============================================================
echo  工业智能助手平台 - 开发环境启动
echo  配置文件: .env.dev
echo  ENV: %ENV%
echo ============================================================
echo.

cd /d %~dp0
python main.py
pause
