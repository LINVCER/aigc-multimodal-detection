# 一键启动 C 端（5173）：npm run dev
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\web")

if (-not (Test-Path ".\node_modules")) { throw "未找到 web/node_modules，请先在 web/ 下执行 npm install" }
Write-Host "C 端 dev server → http://localhost:5173" -ForegroundColor Green
npm run dev
