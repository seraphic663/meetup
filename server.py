#!/usr/bin/env python3
"""群约小助手 - 服务器（SQLite 存储，本地/云部署均可）"""
from flask import Flask, request, jsonify, send_from_directory
import json, os, time, sqlite3, contextlib, requests

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))

# 数据库路径：优先用环境变量（云部署挂载目录），否则本地
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE, 'sessions', 'sessions.db'))

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'

# ── 数据库初始化 ─────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
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

# ── AI 总结生成 ─────────────────────────────────────────
def generate_ai_summary(session_data):
    """调用 DeepSeek API 生成智能总结"""
    if not DEEPSEEK_API_KEY:
        return "未配置 DeepSeek API 密钥"
    
    # 准备数据
    name = session_data.get('name', '时间调查')
    participants = session_data.get('participants', [])
    creator_prompt = (session_data.get('creatorPrompt') or '').strip()
    dateS = session_data.get('dateS', '')
    dateE = session_data.get('dateE', '')
    hourS = session_data.get('hourS', 9)
    hourE = session_data.get('hourE', 21)
    
    # 统计数据
    stats_lines = [f"## 📊 调查信息\n"]
    stats_lines.append(f"- 活动：{name}")
    stats_lines.append(f"- 日期：{dateS} 至 {dateE}")
    stats_lines.append(f"- 时段：{hourS}:00 - {hourE}:00")
    stats_lines.append(f"- 参与人数：{len(participants)} 人\n")
    if creator_prompt:
        stats_lines.append(f"- 发起人提示：{creator_prompt}\n")
    
    # 时段统计
    time_slots = {}
    for hour in range(hourS, hourE):
        avail_count = 0
        busy_count = 0
        for p in participants:
            avail = p.get('avail', {})
            for date, hours in avail.items():
                if str(hour) in hours:
                    state = hours[str(hour)]
                    if state == 1:
                        avail_count += 1
                    elif state == 2:
                        busy_count += 1
        if avail_count > 0 or busy_count > 0:
            time_slots[f"{hour:02d}:00"] = (avail_count, busy_count)
    
    if time_slots:
        stats_lines.append("## ⏰ 时段分析")
        best_slot = max(time_slots.items(), key=lambda x: x[1][0])
        stats_lines.append(f"- 最优时段：{best_slot[0]}（{best_slot[1][0]} 人有空，{best_slot[1][1]} 人没空）")
        
        # 列举其他热门时段
        hot_slots = sorted(time_slots.items(), key=lambda x: x[1][0], reverse=True)[:3]
        if len(hot_slots) > 1:
            stats_lines.append("- 备选时段：")
            for slot, (avail, busy) in hot_slots[1:]:
                stats_lines.append(f"  - {slot}（{avail} 人有空）")
    
    # 人员统计
    stats_lines.append("\n## 👥 人员统计")
    for p in participants:
        avail = p.get('avail', {})
        avail_hours = 0
        for date, hours in avail.items():
            for h, state in hours.items():
                if state == 1:
                    avail_hours += 1
        pname = p.get('name', '未知')
        if avail_hours > 0:
            stats_lines.append(f"- {pname}：{avail_hours} 个时段有空")
        else:
            stats_lines.append(f"- {pname}：未填写")

    # 参与者备注
    remarks = []
    for p in participants:
        note = (p.get('remark') or '').strip()
        if note:
            remarks.append((p.get('name', '未知'), note[:200]))
    if remarks:
        stats_lines.append("\n## 📝 参与者备注")
        for n, note in remarks:
            stats_lines.append(f"- {n}：{note}")
    
    # 提示词
    prompt = f"""基于以下调查统计，用 markdown 格式生成简洁的时间选择建议。
    
{chr(10).join(stats_lines)}

请提供：
1. 最优时间选择及理由（2-3 句）
2. 如果最优时段有人冲突，给出备选方案
3. 参与者建议（如哪些人时间冲突，可能需要另外协商）
4. 若有备注信息，请在建议中纳入约束（如线上参加、晚到、临时不确定）

要求简洁、actionable，用中文回复。"""
    
    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'deepseek-chat',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens': 500
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('choices'):
                return data['choices'][0]['message']['content']
        return f"API 返回错误：{resp.status_code}"
    except requests.exceptions.Timeout:
        return "⏱️ 请求超时，请稍后重试"
    except Exception as e:
        return f"🚫 生成失败：{str(e)}"

# ── 路由 ─────────────────────────────────────────────────
@app.route('/')
def root():
    return send_from_directory(BASE, 'index.html')

@app.route('/styles.css')
def styles():
    return send_from_directory(BASE, 'styles.css')

@app.route('/app.js')
def app_js():
    return send_from_directory(BASE, 'app.js')

@app.route('/healthz')
def healthz():
    return jsonify({'ok': True, 'service': 'meetup'})

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
        'creatorPrompt': (b.get('creatorPrompt') or '').strip()[:200],
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
        plist.append({'name': name, 'color': b.get('color', '#FF6B35'), 'avail': {}, 'remark': ''})
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
    if 'remark' in b:
        p['remark'] = (b.get('remark') or '').strip()[:200]
    _save(sid, s)
    return jsonify({'ok': True})

@app.route('/api/session/<sid>/summary', methods=['GET'])
def summary(sid):
    """生成 AI 智能总结"""
    s = _load(sid)
    if not s: return jsonify({'error': 'not found'}), 404
    summary_text = generate_ai_summary(s)
    return jsonify({'summary': summary_text})

if __name__ == '__main__':
    import socket
    try: ip = socket.gethostbyname(socket.gethostname())
    except: ip = '127.0.0.1'
    print(f'\n{"="*52}\n  📅  群约小助手已启动！\n{"="*52}')
    print(f'  🖥   本机访问：   http://localhost:5000')
    print(f'  📱   局域网访问： http://{ip}:5000')
    print(f'\n  Ctrl+C 停止服务\n{"="*52}\n')
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
