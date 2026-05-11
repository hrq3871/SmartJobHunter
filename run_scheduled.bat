@echo off
REM SmartJobHunter 定时任务启动脚本 (Windows)
REM 每天晚上8点执行

cd /d %~dp0

echo ============================================
echo SmartJobHunter 定时任务
echo 时间: %date% %time%
echo ============================================

python -m src.scheduler --schedule

echo.
echo 任务完成
