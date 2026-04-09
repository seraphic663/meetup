#!/usr/bin/env python3
"""本地启动脚本 - 通过环境变量 DEEPSEEK_API_KEY 配置 AI 功能"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 提示 API Key 状态
key = os.environ.get('DEEPSEEK_API_KEY', '')
if not key:
    print('\n⚠  DEEPSEEK_API_KEY 未设置，AI 总结功能将不可用')
    print('   启动前请运行：$env:DEEPSEEK_API_KEY = "<YOUR_DEEPSEEK_API_KEY>"\n')
else:
    print('\n✓  DEEPSEEK_API_KEY 已配置，AI 总结功能已启用\n')

from backend.server import main

if __name__ == '__main__':
    main()
