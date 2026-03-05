#!/usr/bin/env python3
"""群约小助手 - 服务器（SQLite 存储，本地/云部署均可）"""
from flask import Flask, request, jsonify, send_from_directory
import json, os, time, sqlite3, contextlib

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))

# 数据库路径：优先用环境变量（云部署挂载目录），否则本地
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE, 'sessions.db'))

# ── 数据库初始化 ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id   TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            ts   INTEGER NOT NULL
        )''')
        db.commit()

init_db()

# ── 辅助函数 ─────────────────────────────────────────────
def _sanitize(sid):
    return ''.join(c for c in sid if c.isalnum())[:20]

def _load(sid):
    sid = _sanitize(sid)
    with get_db() as db:
        row = db.execute('SELECT data FROM sessions WHERE id=?', (sid,)).fetchone()
        return json.loads(row['data']) if row else None

def _save(sid, d):
    sid = _sanitize(sid)
    js  = json.dumps(d, ensure_ascii=False)
    with get_db() as db:
        db.execute('INSERT OR REPLACE INTO sessions(id,data,ts) VALUES(?,?,?)',
                   (sid, js, int(time.time())))
        db.commit()

# ── 路由 ─────────────────────────────────────────────────
@app.route('/')
def root():
    return send_from_directory(BASE, 'index.html')

@app.route('/api/session', methods=['POST'])
def create():
    b   = request.get_json(force=True)
    sid = f"{int(time.time()*1000) % (16**8):08x}"
    _save(sid, {
        'id': sid,
        'name':          (b.get('name') or '').strip()[:20],
        'dateS':         b.get('dateS'),
        'dateE':         b.get('dateE'),
        'hourS':         int(b.get('hourS', 9)),
        'hourE':         int(b.get('hourE', 21)),
        'expectedNames': b.get('expectedNames', []),
        'participants':  []
    })
    return jsonify({'id': sid})

@app.route('/api/session/<sid>')
def read(sid):
    s = _load(sid)
    return jsonify(s) if s else (jsonify({'error': 'not found'}), 404)

@app.route('/api/session/<sid>/join', methods=['POST'])
def join(sid):
    s = _load(sid)
    if not s: return jsonify({'error': 'not found'}), 404
    b     = request.get_json(force=True)
    name  = (b.get('name') or '').strip()[:10]
    if not name: return jsonify({'error': 'name required'}), 400
    plist = s.setdefault('participants', [])
    if not any(p['name'] == name for p in plist):
        plist.append({'name': name, 'color': b.get('color', '#FF6B35'), 'avail': {}})
        _save(sid, s)
    return jsonify(s)

@app.route('/api/session/<sid>/avail', methods=['PUT'])
def avail(sid):
    s = _load(sid)
    if not s: return jsonify({'error': 'not found'}), 404
    b    = request.get_json(force=True)
    name = (b.get('name') or '').strip()
    p    = next((x for x in s.get('participants', []) if x['name'] == name), None)
    if not p: return jsonify({'error': 'participant not found'}), 404
    p['avail'] = b.get('avail', {})
    _save(sid, s)
    return jsonify({'ok': True})

if __name__ == '__main__':
    import socket
    try: ip = socket.gethostbyname(socket.gethostname())
    except: ip = '127.0.0.1'
    print(f'\n{"="*52}\n  📅  群约小助手已启动！\n{"="*52}')
    print(f'  🖥   本机访问：   http://localhost:5000')
    print(f'  📱   局域网访问： http://{ip}:5000')
    print(f'\n  Ctrl+C 停止服务\n{"="*52}\n')
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
