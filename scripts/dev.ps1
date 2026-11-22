# JobCopilot 一键启动（Windows / PowerShell）
# 用法：powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "[x] 未找到 backend/.venv，请先执行：" -ForegroundColor Red
    Write-Host "    cd backend; python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt"
    exit 1
}

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "[x] 未找到 frontend/node_modules，请先执行：cd frontend; npm install" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $backend "jobcopilot.db"))) {
    Write-Host "[!] 尚未初始化数据库，建议先执行：" -ForegroundColor Yellow
    Write-Host "    cd backend"
    Write-Host "    .venv\Scripts\python -m app.seed.generate_seed_data"
    Write-Host "    .venv\Scripts\python -m app.seed.seed"
}

Write-Host "启动后端 http://127.0.0.1:8000/docs ..." -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/k", "`"$python`" -m uvicorn app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $backend

Write-Host "启动前端 http://127.0.0.1:5180 ..." -ForegroundColor Cyan
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/k", "npm run dev" `
    -WorkingDirectory $frontend

Start-Sleep -Seconds 3
Write-Host ""
Write-Host "已拉起两个窗口：" -ForegroundColor Green
Write-Host "  前端  http://127.0.0.1:5180"
Write-Host "  接口  http://127.0.0.1:8000/docs"
Write-Host "  账号  zhangsan / 123456（求职者）、xinglankeji / 123456（招聘方，星澜科技）"
