# 一键启动管理端独立实例（5174，只开后台）：npm run dev:admin
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\web")

if (-not (Test-Path ".\node_modules")) { throw "未找到 web/node_modules，请先在 web/ 下执行 npm install" }
Write-Host "管理端 dev server → http://localhost:5174/admin/dashboard" -ForegroundColor Green
npm run dev:admin
