#!/usr/bin/env python3
"""本地启动脚本 - 通过环境变量 DEEPSEEK_API_KEY 配置 AI 功能"""
import os, socket

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 提示 API Key 状态
key = os.environ.get('DEEPSEEK_API_KEY', '')
if not key:
    print('\n⚠  DEEPSEEK_API_KEY 未设置，AI 总结功能将不可用')
    print('   启动前请运行：$env:DEEPSEEK_API_KEY = "sk-xxxx"\n')
else:
    print('\n✓  DEEPSEEK_API_KEY 已配置，AI 总结功能已启用\n')

from server import app

if __name__ == '__main__':
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = '127.0.0.1'
    print('=' * 52)
    print('  📅  群约小助手已启动！')
    print('=' * 52)
    print(f'  🖥   本机访问：   http://localhost:5000')
    print(f'  📱   局域网访问： http://{ip}:5000')
    print('\n  Ctrl+C 停止服务')
    print('=' * 52 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
