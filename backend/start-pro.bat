@echo off
chcp 65001 >nul
REM 生产环境启动脚本
REM 加载 .env.pro 配置

set ENV=production
echo ============================================================
echo  工业智能体平台 - 生产环境启动
echo  配置文件: .env.pro
echo  ENV: %ENV%
echo ============================================================
echo.

cd /d %~dp0
python main.py
pause
