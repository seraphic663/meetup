#!/usr/bin/env python3
"""密钥安全扫描：工作区 + Git 历史。"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

KEY_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"DEEPSEEK_API_KEY\s*=\s*['\"][^'\"]{8,}['\"]"),
]

ALLOW_PATTERNS = [
    re.compile(r"<YOUR_DEEPSEEK_API_KEY>"),
    re.compile(r"sk-xxxx"),
]

TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".html", ".css", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".ps1", ".sh", ".env"
}

EXCLUDE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "sessions"}


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {"README", "Dockerfile", ".gitignore"}


def is_allowed(line: str) -> bool:
    return any(p.search(line) for p in ALLOW_PATTERNS)


def scan_workspace(root: Path) -> list[str]:
    findings: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if not is_text_file(p):
            continue

        rel = p.relative_to(root).as_posix()
        try:
            with p.open("r", encoding="utf-8") as f:
                for i, line in enumerate(f, start=1):
                    if is_allowed(line):
                        continue
                    for pat in KEY_PATTERNS:
                        if pat.search(line):
                            findings.append(f"[workspace] {rel}:{i}: {line.strip()}")
                            break
        except Exception:
            continue
    return findings


def scan_history(root: Path) -> list[str]:
    findings: list[str] = []
    try:
        out = subprocess.check_output(
            ["git", "log", "-p", "--all"],
            cwd=str(root),
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    except Exception as e:
        return [f"[history] 扫描失败：{e}"]

    for i, line in enumerate(out.splitlines(), start=1):
        if is_allowed(line):
            continue
        for pat in KEY_PATTERNS:
            if pat.search(line):
                findings.append(f"[history] line {i}: {line.strip()}")
                break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="安全扫描：检测潜在密钥泄露")
    parser.add_argument("--workspace", action="store_true", help="扫描当前工作区文件")
    parser.add_argument("--history", action="store_true", help="扫描 Git 提交历史")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    if not args.workspace and not args.history:
        args.workspace = True

    findings: list[str] = []
    if args.workspace:
        findings.extend(scan_workspace(root))
    if args.history:
        findings.extend(scan_history(root))

    if findings:
        print("❌ 检测到潜在密钥泄露：")
        for f in findings[:200]:
            print(f"- {f}")
        if len(findings) > 200:
            print(f"... 其余 {len(findings) - 200} 条已省略")
        return 1

    print("✅ 未发现潜在密钥泄露")
    return 0


if __name__ == "__main__":
    sys.exit(main())
