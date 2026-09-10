@echo off
chcp 65001 >nul
REM 测试环境(SIT)启动脚本
REM 加载 .env.sit 配置

set ENV=sit
echo ============================================================
echo  工业智能体平台 - 测试环境(SIT)启动
echo  配置文件: .env.sit
echo  ENV: %ENV%
echo ============================================================
echo.

cd /d %~dp0
python main.py
pause
