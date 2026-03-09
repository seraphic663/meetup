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
    pip install flask>=3.0.0 requests>=2.31.0
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ 安装失败" -ForegroundColor Red
        Read-Host "按 Enter 关闭"
        exit 1
    }
    Write-Host "✓ 依赖安装成功" -ForegroundColor Green
} else {
    Write-Host "✓ 依赖已安装" -ForegroundColor Green
}

# 配置 API Key
Write-Host ""
Write-Host "🔑 API 配置" -ForegroundColor Yellow
Write-Host "若要启用 AI 总结功能，需要配置 DeepSeek API Key" -ForegroundColor Gray
Write-Host ""

$choice = Read-Host "是否现在配置 API Key？(y/n，默认 n)"
if ($choice -eq 'y' -or $choice -eq 'Y') {
    $apiKey = Read-Host "输入 API Key"
    if ($apiKey) {
        $env:DEEPSEEK_API_KEY = $apiKey
        Write-Host "✓ API Key 已设置（仅本次会话有效）" -ForegroundColor Green
        Write-Host ""
        Write-Host "💡 提示：要永久保存，请在系统环境变量中设置 DEEPSEEK_API_KEY" -ForegroundColor Cyan
    }
} else {
    Write-Host "⊘ 跳过 API Key 配置（可稍后通过环境变量设置）" -ForegroundColor Gray
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
