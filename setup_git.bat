@echo off
REM SmartJobHunter Git 初始化脚本

echo ============================================
echo SmartJobHunter Git 初始化
echo ============================================

REM 检查是否已安装 git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未安装 Git，请先安装: https://git-scm.com/downloads
    pause
    exit /b 1
)

REM 检查是否已配置用户信息
git config user.name >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [配置] 请设置 Git 用户信息
    echo.
    set /p GIT_NAME="请输入你的名字: "
    set /p GIT_EMAIL="请输入你的邮箱: "

    git config user.name "%GIT_NAME%"
    git config user.email "%GIT_EMAIL%"
    echo [OK] Git 用户信息已设置
)

REM 检查是否已是 git 仓库
if exist .git (
    echo [OK] 已经是 Git 仓库
) else (
    echo [Git] 初始化仓库...
    git init
    git add -A
    git commit -m "init: SmartJobHunter 初始化"
    echo [OK] 初始提交完成
)

echo.
echo ============================================
echo 下一步操作
echo ============================================
echo.
echo 1. 在 GitHub 创建新仓库:
echo    https://github.com/new
echo    - 仓库名: SmartJobHunter
echo    - 不要勾选 README
echo    - 选择 Private (私有) 保护你的配置
echo.
echo 2. 运行以下命令连接远程仓库:
echo    git remote add origin https://github.com/你的用户名/SmartJobHunter.git
echo    git branch -M main
echo    git push -u origin main
echo.
echo 3. 设置定时任务:
echo    setup_schedule.bat
echo.
echo 4. 之后每次巡检成功会自动推送
echo.

pause
