@echo off
REM 设置Windows定时任务 - 每天晚上8点执行
REM 需要以管理员身份运行

set TASK_NAME=SmartJobHunter
set SCRIPT_PATH=%~dp0run_scheduled.bat

echo 正在创建定时任务...
echo 任务名称: %TASK_NAME%
echo 执行时间: 每天 20:00
echo 脚本路径: %SCRIPT_PATH%

REM 删除已存在的任务
schtasks /delete /tn "%TASK_NAME%" /f 2>nul

REM 创建新任务
schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%SCRIPT_PATH%\"" ^
    /sc daily ^
    /st 20:00 ^
    /rl HIGHEST ^
    /f

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo ✅ 定时任务创建成功！
    echo ============================================
    echo.
    echo 任务名称: %TASK_NAME%
    echo 执行时间: 每天 20:00
    echo.
    echo 管理命令:
    echo   查看任务: schtasks /query /tn "%TASK_NAME%"
    echo   立即运行: schtasks /run /tn "%TASK_NAME%"
    echo   删除任务: schtasks /delete /tn "%TASK_NAME%"
    echo.
) else (
    echo.
    echo ❌ 创建失败，请以管理员身份运行此脚本
)

pause
