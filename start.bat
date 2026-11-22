@echo off
chcp 936 >nul
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%backend\.venv\Scripts\python.exe"

echo ==========================================
echo   JobCopilot 一键启动
echo ==========================================
echo.

if not exist "%PY%" (
    echo [x] 未找到 backend\.venv，请先执行：
    echo     cd backend
    echo     python -m venv .venv
    echo     .venv\Scripts\python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
    echo [x] 未找到 frontend\node_modules，请先执行：
    echo     cd frontend ^&^& npm install
    echo.
    pause
    exit /b 1
)

if not exist "%ROOT%backend\jobcopilot.db" (
    echo [!] 尚未初始化数据库，首次启动前请执行：
    echo     cd backend
    echo     .venv\Scripts\python -m app.seed.generate_seed_data
    echo     .venv\Scripts\python -m app.seed.seed
    echo.
)

netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [1/2] 启动后端 http://127.0.0.1:8000 ...
    start "JobCopilot Backend" /D "%ROOT%backend" "%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) else (
    echo [1/2] 端口 8000 已在运行，跳过后端启动
)

netstat -ano | findstr ":5180" | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [2/2] 启动前端 http://127.0.0.1:5180 ...
    start "JobCopilot Frontend" /D "%ROOT%frontend" cmd /k "npm run dev"
) else (
    echo [2/2] 端口 5180 已在运行，跳过前端启动
)

echo.
echo 等待服务启动...
timeout /t 4 /nobreak >nul
start "" http://127.0.0.1:5180

echo.
echo 启动完成：
echo   前端  http://127.0.0.1:5180
echo   接口  http://127.0.0.1:8000/docs
echo   账号  zhangsan / 123456（求职者）  xinglankeji / 123456（招聘方）
echo.
echo 关闭本窗口不会停止服务，请手动关闭服务窗口
pause
