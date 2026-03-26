# 安装本仓库 Git Hooks（Windows PowerShell）
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

git config core.hooksPath .githooks
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 设置 hooksPath 失败" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 已启用 .githooks/pre-commit" -ForegroundColor Green
Write-Host "  之后每次 git commit 前会自动执行安全扫描" -ForegroundColor Green
