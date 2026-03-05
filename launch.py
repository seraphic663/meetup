#!/usr/bin/env python3
"""群约小助手 - 一键启动（本地服务 + 公网穿透）"""
import subprocess, sys, os, time, re, threading, urllib.request, signal

BASE = os.path.dirname(os.path.abspath(__file__))
CF   = os.path.join(BASE, 'cloudflared.exe')
CF_URL = ('https://github.com/cloudflare/cloudflared/releases/latest/download/'
          'cloudflared-windows-amd64.exe')

flask_proc = None
cf_proc    = None

def log(msg): print(msg, flush=True)

# ── 1. 安装依赖 ──────────────────────────────────────
def install_deps():
    log('📦 检查 Flask 依赖...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'flask', '-q'],
                   check=True)

# ── 2. 释放端口 5000 ─────────────────────────────────
def free_port():
    try:
        r = subprocess.check_output('netstat -ano | findstr ":5000 "',
                                    shell=True, text=True, stderr=subprocess.DEVNULL)
        for line in r.strip().splitlines():
            pid = line.strip().split()[-1]
            subprocess.run(f'taskkill /PID {pid} /F', shell=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    except Exception:
        pass

# ── 3. 启动 Flask ─────────────────────────────────────
def start_flask():
    global flask_proc
    log('🚀 启动本地服务器...')
    flask_proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE, 'server.py')],
        cwd=BASE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    # 等待服务就绪
    for _ in range(20):
        time.sleep(0.5)
        try:
            urllib.request.urlopen('http://localhost:5000', timeout=1)
            log('✅ 本地服务就绪 → http://localhost:5000')
            return True
        except Exception:
            pass
    log('❌ 本地服务启动超时')
    return False

# ── 4. 下载 cloudflared ───────────────────────────────
def ensure_cloudflared():
    if os.path.exists(CF):
        return True
    log('⬇  首次运行，下载公网穿透工具 cloudflared（约30MB）...')
    log('   网络慢时请耐心等待，下载完成后以后不再重复下载。')
    try:
        def reporthook(count, block, total):
            pct = min(count * block * 100 // total, 100) if total > 0 else 0
            print(f'\r   进度: {pct}%', end='', flush=True)
        urllib.request.urlretrieve(CF_URL, CF, reporthook=reporthook)
        print()
        log('✅ cloudflared 下载完成')
        return True
    except Exception as e:
        print()
        log(f'❌ 下载失败: {e}')
        log('   请手动下载 cloudflared-windows-amd64.exe 放到当前目录：')
        log(f'   {CF_URL}')
        return False

# ── 5. 启动 cloudflared 穿透 ──────────────────────────
def start_tunnel():
    global cf_proc
    log('🌏 正在创建公网链接（10~30秒）...')
    cf_proc = subprocess.Popen(
        [CF, 'tunnel', '--url', 'http://localhost:5000'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='ignore'
    )
    url_re = re.compile(r'https://[a-z0-9\-]+\.trycloudflare\.com')
    found_url = None

    # 在找到 URL 之前逐行扫描
    for line in cf_proc.stdout:
        m = url_re.search(line)
        if m:
            found_url = m.group(0)
            break

    # 关键：用 daemon 线程持续消耗 stdout，防止管道关闭导致 cloudflared 退出
    def _drain():
        if cf_proc and cf_proc.stdout:
            for _ in cf_proc.stdout:
                pass
    threading.Thread(target=_drain, daemon=True).start()

    return found_url

# ── 6. 优雅退出 ───────────────────────────────────────
def shutdown(sig=None, frame=None):
    log('\n\n⏹  正在停止所有服务...')
    for p in (cf_proc, flask_proc):
        if p:
            try: p.terminate()
            except: pass
    sys.exit(0)

signal.signal(signal.SIGINT,  shutdown)
signal.signal(signal.SIGTERM, shutdown)

# ── 主流程 ────────────────────────────────────────────
if __name__ == '__main__':
    print('\n' + '='*54)
    print('  📅  群约小助手')
    print('='*54)

    install_deps()
    free_port()

    if not start_flask():
        input('按回车退出...')
        sys.exit(1)

    if not ensure_cloudflared():
        log('\n仅本机可用，局域网地址请查看上方输出')
        input('按回车退出...')
        shutdown()

    public_url = start_tunnel()

    if public_url:
        print('\n' + '='*54)
        print('  ✅  公网链接已就绪！')
        print('='*54)
        print(f'\n  🔗  {public_url}')
        print(f'\n  👉  把上面这条链接发到微信群！')
        print(f'  📱  群友点开链接，选自己名字，填有空时段')
        print(f'  🔄  数据实时同步，所有人共享同一份结果')
        print(f'\n  本机访问:  http://localhost:5000')
        print(f'  Ctrl+C 停止所有服务')
        print('='*54 + '\n')
    else:
        log('⚠️  未能获取公网链接，仅本机可用: http://localhost:5000')

    # 保持进程存活：等待 cloudflared，如果它退出则用 flask 和轮询补充
    try:
        if cf_proc:
            cf_proc.wait()
        if flask_proc:
            flask_proc.wait()
    except KeyboardInterrupt:
        shutdown()
