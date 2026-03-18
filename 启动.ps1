# 群约小助手 - PowerShell 启动脚本

Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  📅 群约小助手 - 快速启动脚本" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
Write-Host "🔍 检查 Python..." -ForegroundColor Yellow
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Host "✗ 错误：未找到 Python" -ForegroundColor Red
    Write-Host "   请先安装 Python 3.10+ 并添加到 PATH" -ForegroundColor Red
    Read-Host "按 Enter 关闭"
    exit 1
}
Write-Host "✓ Python 已安装：$pythonPath" -ForegroundColor Green

# 进入项目目录
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectDir
Write-Host "✓ 进入目录：$(Get-Location)" -ForegroundColor Green

# 检查依赖
Write-Host ""
Write-Host "📦 检查依赖..." -ForegroundColor Yellow
$pipList = pip list 2>$null | Out-String
if ($pipList -notlike "*Flask*") {
    Write-Host "✗ Flask 未安装，正在安装..." -ForegroundColor Yellow
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 安装失败" -ForegroundColor Red
        Read-Host "按 Enter 关闭"
        exit 1
    }
    Write-Host "✓ 依赖安装成功" -ForegroundColor Green
} else {
    Write-Host "✓ 依赖已安装" -ForegroundColor Green
}

# 检查 API Key（只读，不在脚本中采集）
Write-Host ""
Write-Host "🔑 API 配置" -ForegroundColor Yellow
if ([string]::IsNullOrWhiteSpace($env:DEEPSEEK_API_KEY)) {
    Write-Host "⊘ 未检测到 DEEPSEEK_API_KEY，AI 总结功能将不可用" -ForegroundColor Gray
    Write-Host "  请在当前终端先执行：`$env:DEEPSEEK_API_KEY = \"sk-xxxx\"" -ForegroundColor Gray
    Write-Host "  安全建议：仅使用环境变量，不要把密钥写进项目文件" -ForegroundColor Gray
} else {
    Write-Host "✓ 已检测到 DEEPSEEK_API_KEY（来源：环境变量）" -ForegroundColor Green
}

# 启动服务器
Write-Host ""
Write-Host "🚀 启动服务器..." -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

python run.py

Write-Host ""
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "✓ 服务器已停止" -ForegroundColor Green
Write-Host "════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
