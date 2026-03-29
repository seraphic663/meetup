#!/usr/bin/env python3
"""群约小助手 - Flask + SQLite 服务端。"""
from __future__ import annotations

from datetime import date, timedelta
from flask import Flask, jsonify, request, send_from_directory
import json
import os
import re
import secrets
import sqlite3
import time

import requests

app = Flask(__name__)
BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE, "sessions", "sessions.db"))
DB_USES_URI = DB_PATH.startswith("file:")
KEEPALIVE_DB = None

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

SESSION_NAME_MAX = 20
PERSON_NAME_MAX = 10
PROMPT_MAX = 200
REMARK_MAX = 200
EXPECTED_NAMES_MAX = 12
MAX_RANGE_DAYS = 14
VALID_STATES = {0, 1, 2}
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def get_db():
    conn = sqlite3.connect(DB_PATH, uri=DB_USES_URI)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    global KEEPALIVE_DB

    if DB_USES_URI and "mode=memory" in DB_PATH:
        KEEPALIVE_DB = sqlite3.connect(DB_PATH, uri=True)
        KEEPALIVE_DB.row_factory = sqlite3.Row
        db = KEEPALIVE_DB
    else:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        db = get_db()

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id   TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            ts   INTEGER NOT NULL
        )
        """
    )
    db.commit()
    if db is not KEEPALIVE_DB:
        db.close()


init_db()


def _sanitize_sid(sid: str) -> str:
    return "".join(ch for ch in str(sid or "") if ch.isalnum())[:20]


def _load(sid: str):
    sid = _sanitize_sid(sid)
    with get_db() as db:
        row = db.execute("SELECT data FROM sessions WHERE id=?", (sid,)).fetchone()
        return json.loads(row["data"]) if row else None


def _save(sid: str, payload: dict) -> None:
    sid = _sanitize_sid(sid)
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO sessions(id,data,ts) VALUES(?,?,?)",
            (sid, json.dumps(payload, ensure_ascii=False), int(time.time())),
        )
        db.commit()


def _clean_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _safe_color(value: str | None, fallback: str = "#FF6B35") -> str:
    text = str(value or "").strip()
    return text if COLOR_RE.fullmatch(text) else fallback


def _iter_dates(session_data: dict):
    current = _parse_date(session_data.get("dateS"))
    end = _parse_date(session_data.get("dateE"))
    if not current or not end or current > end:
        return []
    out = []
    while current <= end:
        out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def _dedupe_names(values, exclude: str | None = None):
    names = []
    seen = set()
    exclude = exclude or None
    for value in values or []:
        name = _clean_text(value, PERSON_NAME_MAX)
        if not name or name == exclude or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= EXPECTED_NAMES_MAX:
            break
    return names


def _validate_create_payload(body: dict):
    name = _clean_text(body.get("name"), SESSION_NAME_MAX)
    creator_prompt = _clean_text(body.get("creatorPrompt"), PROMPT_MAX)
    date_s = _parse_date(body.get("dateS"))
    date_e = _parse_date(body.get("dateE"))
    try:
        hour_s = int(body.get("hourS", 9))
        hour_e = int(body.get("hourE", 21))
    except (TypeError, ValueError):
        hour_s = hour_e = -1

    errors = []
    if not name:
        errors.append("活动名称不能为空")
    if not date_s or not date_e:
        errors.append("日期格式不正确")
    elif date_s > date_e:
        errors.append("开始日期不能晚于结束日期")
    elif (date_e - date_s).days > MAX_RANGE_DAYS:
        errors.append("日期范围最多14天")
    if hour_s < 0 or hour_s > 23 or hour_e < 1 or hour_e > 24 or hour_s >= hour_e:
        errors.append("时间范围不正确")

    payload = {
        "name": name,
        "dateS": date_s.isoformat() if date_s else "",
        "dateE": date_e.isoformat() if date_e else "",
        "hourS": hour_s,
        "hourE": hour_e,
        "creatorPrompt": creator_prompt,
        "expectedNames": _dedupe_names(body.get("expectedNames", [])),
        "participants": [],
    }
    return payload, errors


def _normalize_avail(session_data: dict, raw_avail):
    if not isinstance(raw_avail, dict):
        return {}

    valid_dates = set(_iter_dates(session_data))
    valid_hours = {str(hour) for hour in range(int(session_data.get("hourS", 9)), int(session_data.get("hourE", 21)))}
    normalized = {}

    for raw_date, raw_hours in raw_avail.items():
        session_date = str(raw_date)
        if session_date not in valid_dates or not isinstance(raw_hours, dict):
            continue
        day_payload = {}
        for raw_hour, raw_state in raw_hours.items():
            hour = str(raw_hour)
            try:
                state = int(raw_state)
            except (TypeError, ValueError):
                continue
            if hour not in valid_hours or state not in VALID_STATES or state == 0:
                continue
            day_payload[hour] = state
        if day_payload:
            normalized[session_date] = day_payload
    return normalized


def _participant_has_input(participant: dict) -> bool:
    return bool(participant.get("avail") or (participant.get("remark") or "").strip())


def _slot_stats(session_data: dict):
    participants = session_data.get("participants", [])
    stats = []
    for session_date in _iter_dates(session_data):
        for hour in range(int(session_data.get("hourS", 9)), int(session_data.get("hourE", 21))):
            available = []
            busy = []
            unknown = []
            for participant in participants:
                day_avail = participant.get("avail", {}).get(session_date, {})
                state = int(day_avail.get(str(hour), 0)) if isinstance(day_avail, dict) else 0
                if state == 1:
                    available.append(participant.get("name", "未知"))
                elif state == 2:
                    busy.append(participant.get("name", "未知"))
                else:
                    unknown.append(participant.get("name", "未知"))
            stats.append(
                {
                    "date": session_date,
                    "hour": hour,
                    "available": available,
                    "busy": busy,
                    "unknown": unknown,
                    "avail_count": len(available),
                    "busy_count": len(busy),
                    "unknown_count": len(unknown),
                }
            )
    return stats


def _slot_label(slot: dict) -> str:
    return f"{slot['date'][5:]} {slot['hour']:02d}:00-{slot['hour'] + 1:02d}:00"


def _build_local_summary(session_data: dict) -> str:
    participants = session_data.get("participants", [])
    participant_total = len(participants)
    slots = _slot_stats(session_data)
    ranked_slots = sorted(
        slots,
        key=lambda item: (-item["avail_count"], item["busy_count"], item["unknown_count"], item["date"], item["hour"]),
    )
    top_slots = [slot for slot in ranked_slots if slot["avail_count"] > 0][:3]
    pending_names = [participant.get("name", "未知") for participant in participants if not _participant_has_input(participant)]
    remarks = [(participant.get("name", "未知"), _clean_text(participant.get("remark"), REMARK_MAX)) for participant in participants if (participant.get("remark") or "").strip()]

    lines = ["## 推荐时段"]
    if top_slots:
        for slot in top_slots:
            parts = [f"{slot['avail_count']}/{participant_total} 人有空"]
            if slot["busy_count"]:
                parts.append(f"{slot['busy_count']} 人明确没空")
            if slot["unknown_count"]:
                parts.append(f"{slot['unknown_count']} 人尚未填写")
            lines.append(f"- {_slot_label(slot)}：{'，'.join(parts)}")
    else:
        lines.append("- 目前还没有明确的可用时段，建议先提醒大家填写。")

    lines.append("")
    lines.append("## 协调建议")
    if top_slots:
        best = top_slots[0]
        lines.append(f"- 优先从 {_slot_label(best)} 开始沟通，这个时段当前重合度最高。")
        if best["busy"]:
            lines.append(f"- 这个时段和 {', '.join(best['busy'])} 有冲突，如需全员参与可继续看备选时段。")
        if pending_names:
            lines.append(f"- 还有 {', '.join(pending_names)} 未完成填写，最终敲定前建议先补齐信息。")
    else:
        lines.append("- 大家还没有形成明显重合，建议缩小日期范围或先明确优先级。")

    if remarks:
        lines.append("")
        lines.append("## 参与者备注")
        for name, note in remarks:
            lines.append(f"- {name}：{note}")

    if participants:
        lines.append("")
        lines.append("## 填写进度")
        lines.append(f"- 当前共 {participant_total} 人参与，已填写 {participant_total - len(pending_names)} 人，待填写 {len(pending_names)} 人。")
    return "\n".join(lines)


def _build_ai_prompt(session_data: dict, fallback_summary: str) -> str:
    slots = _slot_stats(session_data)
    highlights = sorted(
        [slot for slot in slots if slot["avail_count"] > 0],
        key=lambda item: (-item["avail_count"], item["busy_count"], item["unknown_count"], item["date"], item["hour"]),
    )[:5]
    highlight_lines = [
        f"- {_slot_label(slot)}：有空 {slot['avail_count']} 人，没空 {slot['busy_count']} 人，未填 {slot['unknown_count']} 人"
        for slot in highlights
    ] or ["- 暂无有效高亮时段"]

    return (
        "请基于以下时间调查信息，用简洁中文输出 markdown 总结。\n\n"
        f"活动名称：{session_data.get('name', '时间调查')}\n"
        f"日期范围：{session_data.get('dateS', '')} 至 {session_data.get('dateE', '')}\n"
        f"时间范围：{session_data.get('hourS', 9)}:00 - {session_data.get('hourE', 21)}:00\n"
        f"发起人提示：{session_data.get('creatorPrompt', '') or '无'}\n\n"
        "本地预分析：\n"
        f"{fallback_summary}\n\n"
        "高亮时段：\n"
        f"{'\n'.join(highlight_lines)}\n\n"
        "请按以下结构回答：\n"
        "## 推荐时段\n"
        "- 给出最值得先讨论的时段和理由\n"
        "## 协调建议\n"
        "- 给出备选与沟通建议\n"
        "## 参与者备注\n"
        "- 只在确实有备注或限制时输出\n"
    )


def generate_ai_summary(session_data: dict) -> str:
    fallback_summary = _build_local_summary(session_data)
    if not DEEPSEEK_API_KEY:
        return fallback_summary

    try:
        response = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": _build_ai_prompt(session_data, fallback_summary)}],
                "temperature": 0.4,
                "max_tokens": 500,
            },
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            choices = data.get("choices") or []
            if choices and choices[0].get("message", {}).get("content"):
                return choices[0]["message"]["content"]
        return f"{fallback_summary}\n\n## 说明\n- AI 服务暂时不可用，已返回本地总结。"
    except requests.exceptions.Timeout:
        return f"{fallback_summary}\n\n## 说明\n- AI 请求超时，已返回本地总结。"
    except Exception:
        return f"{fallback_summary}\n\n## 说明\n- AI 生成失败，已返回本地总结。"


@app.route("/")
def root():
    return send_from_directory(BASE, "index.html")


@app.route("/styles.css")
def styles():
    return send_from_directory(BASE, "styles.css")


@app.route("/app.js")
def app_js():
    return send_from_directory(BASE, "app.js")


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "meetup", "ai_configured": bool(DEEPSEEK_API_KEY)})


@app.route("/api/session", methods=["POST"])
def create():
    body = request.get_json(force=True) or {}
    payload, errors = _validate_create_payload(body)
    if errors:
        return jsonify({"error": "invalid payload", "details": errors}), 400

    sid = secrets.token_hex(4)
    payload["id"] = sid
    _save(sid, payload)
    return jsonify({"id": sid})


@app.route("/api/session/<sid>")
def read(sid):
    session_data = _load(sid)
    return jsonify(session_data) if session_data else (jsonify({"error": "not found"}), 404)


@app.route("/api/session/<sid>/join", methods=["POST"])
def join(sid):
    session_data = _load(sid)
    if not session_data:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True) or {}
    name = _clean_text(body.get("name"), PERSON_NAME_MAX)
    if not name:
        return jsonify({"error": "name required"}), 400

    participants = session_data.setdefault("participants", [])
    existing = next((item for item in participants if item.get("name") == name), None)
    if existing is None:
        participants.append(
            {
                "name": name,
                "color": _safe_color(body.get("color")),
                "avail": {},
                "remark": "",
            }
        )
        _save(sid, session_data)
    return jsonify(session_data)


@app.route("/api/session/<sid>/avail", methods=["PUT"])
def avail(sid):
    session_data = _load(sid)
    if not session_data:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(force=True) or {}
    name = _clean_text(body.get("name"), PERSON_NAME_MAX)
    participant = next((item for item in session_data.get("participants", []) if item.get("name") == name), None)
    if participant is None:
        return jsonify({"error": "participant not found"}), 404

    participant["avail"] = _normalize_avail(session_data, body.get("avail", {}))
    if "remark" in body:
        participant["remark"] = _clean_text(body.get("remark"), REMARK_MAX)
    _save(sid, session_data)
    return jsonify({"ok": True})


@app.route("/api/session/<sid>/summary", methods=["GET"])
def summary(sid):
    session_data = _load(sid)
    if not session_data:
        return jsonify({"error": "not found"}), 404
    return jsonify({"summary": generate_ai_summary(session_data)})


if __name__ == "__main__":
    import socket

    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "127.0.0.1"

    print(f"\n{'=' * 52}\n  📅  群约小助手已启动！\n{'=' * 52}")
    print("  🖥   本机访问：   http://localhost:5000")
    print(f"  📱   局域网访问： http://{ip}:5000")
    print(f"\n  Ctrl+C 停止服务\n{'=' * 52}\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
