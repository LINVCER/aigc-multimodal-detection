# 一键启动推理服务（首次需先完成 START.md §1 环境准备与 §2 配置 .env）
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py))    { throw "未找到 .venv，请先执行 START.md §1 环境准备" }
if (-not (Test-Path ".env")) { throw "未找到 .env，请先 Copy-Item .env.example .env 并配置" }

& $py -m uvicorn main:app --host 0.0.0.0 --port 8000 --env-file .env