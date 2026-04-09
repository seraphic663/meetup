#!/usr/bin/env python3
"""群约小助手 - Flask + SQLite 服务端。"""
from __future__ import annotations

from datetime import date, timedelta
from flask import Flask, g, jsonify, request, send_from_directory
import hashlib
import logging
import json
import os
import re
import secrets
import sqlite3
import time

import requests
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(MODULE_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
DB_PATH = os.environ.get("DB_PATH", os.path.join(ROOT_DIR, "sessions", "sessions.db"))
DB_USES_URI = DB_PATH.startswith("file:")
KEEPALIVE_DB = None
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

SESSION_NAME_MAX = 20
PERSON_NAME_MAX = 10
PROMPT_MAX = 200
REMARK_MAX = 200
EXPECTED_NAMES_MAX = 12
MAX_PARTICIPANTS = 24
MAX_RANGE_DAYS = 14
VALID_STATES = {0, 1, 2}
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
SCHEMA_VERSION = 2

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("meetup")


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


def _request_id() -> str | None:
    return getattr(g, "request_id", None)


def _log_event(level: str, event: str, **fields) -> None:
    payload = {
        "event": event,
        "ts": int(time.time()),
        **fields,
    }
    getattr(logger, level, logger.info)(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _api_error(code: str, status: int, message: str, details=None):
    payload = {
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": _request_id(),
    }
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def _json_body():
    body = request.get_json(force=True, silent=True)
    if body is None:
        raise ValueError("请求体必须是合法 JSON")
    return body


def _sanitize_sid(sid: str) -> str:
    return "".join(ch for ch in str(sid or "") if ch.isalnum())[:20]


def _load(sid: str):
    sid = _sanitize_sid(sid)
    with get_db() as db:
        row = db.execute("SELECT data FROM sessions WHERE id=?", (sid,)).fetchone()
        return _normalize_session_data(json.loads(row["data"])) if row else None


def _save(sid: str, payload: dict) -> None:
    sid = _sanitize_sid(sid)
    normalized = _normalize_session_data(payload) or payload
    normalized["id"] = sid
    with get_db() as db:
        db.execute(
            "INSERT OR REPLACE INTO sessions(id,data,ts) VALUES(?,?,?)",
            (sid, json.dumps(normalized, ensure_ascii=False), int(time.time())),
        )
        db.commit()


def _clean_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _new_participant_id() -> str:
    return secrets.token_hex(6)


def _legacy_participant_id(name: str) -> str:
    digest = hashlib.sha1(str(name or "").encode("utf-8")).hexdigest()[:10]
    return f"legacy_{digest}"


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _safe_color(value: str | None, fallback: str = "#FF6B35") -> str:
    text = str(value or "").strip()
    return text if COLOR_RE.fullmatch(text) else fallback


def _delete(sid: str) -> None:
    sid = _sanitize_sid(sid)
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        db.commit()


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


def _normalize_participants(session_data: dict, raw_participants, existing_by_id: dict | None = None):
    participants = []
    seen_names = set()
    seen_ids = set()
    existing_by_id = existing_by_id or {}

    for raw in raw_participants or []:
        if not isinstance(raw, dict):
            continue

        name = _clean_text(raw.get("name"), PERSON_NAME_MAX)
        if not name or name in seen_names:
            continue

        raw_id = _clean_text(raw.get("id"), 32)
        existing = existing_by_id.get(raw_id) if raw_id else None
        participant_id = raw_id or (existing.get("id") if existing else "") or _legacy_participant_id(name)
        if participant_id in seen_ids:
            participant_id = _new_participant_id()

        fallback_color = (existing or {}).get("color") or "#FF6B35"
        participant = {
            "id": participant_id,
            "name": name,
            "color": _safe_color(raw.get("color"), fallback_color),
            "avail": _normalize_avail(session_data, raw.get("avail") if "avail" in raw else (existing or {}).get("avail", {})),
            "remark": _clean_text(raw.get("remark") if "remark" in raw else (existing or {}).get("remark"), REMARK_MAX),
        }

        token_hash = _clean_text(raw.get("tokenHash") if "tokenHash" in raw else (existing or {}).get("tokenHash"), 128)
        if token_hash:
            participant["tokenHash"] = token_hash

        seen_ids.add(participant_id)
        seen_names.add(name)
        participants.append(participant)

    return participants


def _normalize_session_data(raw_data: dict | None):
    if not isinstance(raw_data, dict):
        return None

    payload = {
        "id": _sanitize_sid(raw_data.get("id")),
        "schemaVersion": int(raw_data.get("schemaVersion") or 1),
        "name": _clean_text(raw_data.get("name"), SESSION_NAME_MAX),
        "dateS": _parse_date(raw_data.get("dateS")).isoformat() if _parse_date(raw_data.get("dateS")) else "",
        "dateE": _parse_date(raw_data.get("dateE")).isoformat() if _parse_date(raw_data.get("dateE")) else "",
        "hourS": int(raw_data.get("hourS", 9)) if str(raw_data.get("hourS", 9)).isdigit() else 9,
        "hourE": int(raw_data.get("hourE", 21)) if str(raw_data.get("hourE", 21)).isdigit() else 21,
        "creatorPrompt": _clean_text(raw_data.get("creatorPrompt"), PROMPT_MAX),
    }

    creator = raw_data.get("creator")
    if isinstance(creator, dict):
        creator_name = _clean_text(creator.get("name"), PERSON_NAME_MAX)
        creator_token_hash = _clean_text(creator.get("tokenHash"), 128)
        if creator_name or creator_token_hash:
            payload["creator"] = {}
            if creator_name:
                payload["creator"]["name"] = creator_name
            if creator_token_hash:
                payload["creator"]["tokenHash"] = creator_token_hash

    exclude_name = payload.get("creator", {}).get("name")
    payload["expectedNames"] = _dedupe_names(raw_data.get("expectedNames", []), exclude=exclude_name)
    payload["participants"] = _normalize_participants(payload, raw_data.get("participants", []))
    return payload


def _validate_create_payload(body: dict, creator_name: str | None = None):
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
        "expectedNames": _dedupe_names(body.get("expectedNames", []), exclude=creator_name),
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


def _viewer_context(session_data: dict):
    creator = session_data.get("creator", {})
    creator_token = _clean_text(request.headers.get("X-Creator-Token"), 256)
    participant_token = _clean_text(request.headers.get("X-Participant-Token"), 256)

    is_creator = bool(creator.get("tokenHash") and creator_token and _hash_token(creator_token) == creator.get("tokenHash"))
    participant = None
    if participant_token:
        participant_hash = _hash_token(participant_token)
        participant = next(
            (item for item in session_data.get("participants", []) if item.get("tokenHash") == participant_hash),
            None,
        )
    return {
        "is_creator": is_creator,
        "creator_token": creator_token,
        "participant": participant,
        "participant_token": participant_token,
    }


def _public_session(session_data: dict):
    viewer = _viewer_context(session_data)
    creator = session_data.get("creator", {})
    legacy_delete = not creator.get("tokenHash")
    return {
        "id": session_data.get("id"),
        "schemaVersion": session_data.get("schemaVersion", 1),
        "name": session_data.get("name", ""),
        "dateS": session_data.get("dateS", ""),
        "dateE": session_data.get("dateE", ""),
        "hourS": session_data.get("hourS", 9),
        "hourE": session_data.get("hourE", 21),
        "creatorPrompt": session_data.get("creatorPrompt", ""),
        "creatorName": creator.get("name", ""),
        "expectedNames": session_data.get("expectedNames", []),
        "participants": [
            {
                "id": participant.get("id"),
                "name": participant.get("name"),
                "color": participant.get("color"),
                "avail": participant.get("avail", {}),
                "remark": participant.get("remark", ""),
            }
            for participant in session_data.get("participants", [])
        ],
        "viewer": {
            "isCreator": viewer["is_creator"],
            "participantId": viewer["participant"].get("id") if viewer["participant"] else None,
            "participantName": viewer["participant"].get("name") if viewer["participant"] else "",
        },
        "capabilities": {
            "canManageSession": viewer["is_creator"],
            "canDeleteSession": viewer["is_creator"] or legacy_delete,
            "canManageParticipants": viewer["is_creator"],
            "canLeaveSession": bool(viewer["participant"]),
            "canEditOwnAvailability": bool(viewer["participant"]),
        },
    }


def _creator_required(session_data: dict):
    viewer = _viewer_context(session_data)
    if viewer["is_creator"]:
        return viewer
    return None


def _participant_for_write(session_data: dict, body_name: str | None = None):
    viewer = _viewer_context(session_data)
    if viewer["participant"]:
        return viewer["participant"]

    name = _clean_text(body_name, PERSON_NAME_MAX)
    if not name:
        return None

    participant = next((item for item in session_data.get("participants", []) if item.get("name") == name), None)
    if participant and not participant.get("tokenHash") and not session_data.get("creator", {}).get("tokenHash"):
        return participant
    return None


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
        _log_event(
            "warning",
            "ai_summary_failed",
            request_id=_request_id(),
            reason="upstream_error",
            status_code=response.status_code,
        )
        return f"{fallback_summary}\n\n## 说明\n- AI 服务暂时不可用，已返回本地总结。"
    except requests.exceptions.Timeout:
        _log_event("warning", "ai_summary_failed", request_id=_request_id(), reason="timeout")
        return f"{fallback_summary}\n\n## 说明\n- AI 请求超时，已返回本地总结。"
    except Exception as exc:
        _log_event(
            "error",
            "ai_summary_failed",
            request_id=_request_id(),
            reason="exception",
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        return f"{fallback_summary}\n\n## 说明\n- AI 生成失败，已返回本地总结。"


@app.before_request
def before_request():
    g.request_id = request.headers.get("X-Request-Id") or secrets.token_hex(8)
    g.request_started_at = time.perf_counter()


@app.after_request
def after_request(response):
    request_id = _request_id() or secrets.token_hex(8)
    response.headers["X-Request-Id"] = request_id
    duration_ms = int((time.perf_counter() - getattr(g, "request_started_at", time.perf_counter())) * 1000)
    _log_event(
        "info",
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.path,
        status=response.status_code,
        duration_ms=duration_ms,
        remote_addr=request.headers.get("X-Forwarded-For", request.remote_addr),
    )
    return response


@app.errorhandler(HTTPException)
def handle_http_exception(exc: HTTPException):
    _log_event(
        "warning",
        "http_exception",
        request_id=_request_id(),
        method=request.method,
        path=request.path,
        status=exc.code,
        error=exc.name,
    )
    if request.path.startswith("/api/"):
        return _api_error("http_error", exc.code or 500, exc.description)
    return exc


@app.errorhandler(Exception)
def handle_unexpected_exception(exc: Exception):
    _log_event(
        "error",
        "unhandled_exception",
        request_id=_request_id(),
        method=request.method,
        path=request.path,
        exception_type=type(exc).__name__,
        message=str(exc),
    )
    if request.path.startswith("/api/"):
        return _api_error("internal_server_error", 500, "服务器内部错误，请稍后重试")
    return "Internal Server Error", 500


@app.route("/")
def root():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/styles.css")
def styles():
    return send_from_directory(FRONTEND_DIR, "styles.css")


@app.route("/static/<path:filename>")
def assets(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "service": "meetup", "ai_configured": bool(DEEPSEEK_API_KEY)})


@app.route("/api/session", methods=["POST"])
def create():
    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))
    creator_name = _clean_text(body.get("creatorName"), PERSON_NAME_MAX)
    payload, errors = _validate_create_payload(body, creator_name=creator_name)
    if not creator_name:
        errors.append("创建者昵称不能为空")
    if errors:
        return _api_error("invalid_payload", 400, "请求参数不合法", errors)

    sid = secrets.token_hex(4)
    creator_token = _new_token()
    payload["id"] = sid
    payload["schemaVersion"] = SCHEMA_VERSION
    payload["creator"] = {
        "name": creator_name,
        "tokenHash": _hash_token(creator_token),
    }
    _save(sid, payload)
    _log_event(
        "info",
        "session_created",
        request_id=_request_id(),
        session_id=sid,
        name=payload["name"],
        creator=creator_name,
        expected_count=len(payload["expectedNames"]),
    )
    return jsonify({"id": sid, "creatorToken": creator_token})


@app.route("/api/session/<sid>")
def read(sid):
    session_data = _load(sid)
    return jsonify(_public_session(session_data)) if session_data else _api_error("not_found", 404, "会话不存在")


@app.route("/api/session/<sid>/join", methods=["POST"])
def join(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))
    name = _clean_text(body.get("name"), PERSON_NAME_MAX)
    if not name:
        return _api_error("name_required", 400, "昵称不能为空")

    participants = session_data.setdefault("participants", [])
    existing = next((item for item in participants if item.get("name") == name), None)
    participant_token = None
    if existing is None:
        participant_token = _new_token()
        participants.append(
            {
                "id": _new_participant_id(),
                "name": name,
                "color": _safe_color(body.get("color")),
                "avail": {},
                "remark": "",
                "tokenHash": _hash_token(participant_token),
            }
        )
        _save(sid, session_data)
        _log_event(
            "info",
            "participant_joined",
            request_id=_request_id(),
            session_id=sid,
            participant=name,
            participant_count=len(participants),
        )
        existing = participants[-1]
    else:
        viewer = _viewer_context(session_data)
        if existing.get("tokenHash"):
            if not viewer["participant"] or viewer["participant"].get("id") != existing.get("id"):
                return _api_error("name_taken", 409, "这个昵称已在其他设备使用，请换个昵称或在原设备继续")
            participant_token = viewer["participant_token"]
        else:
            participant_token = _new_token()
            existing["tokenHash"] = _hash_token(participant_token)
            _save(sid, session_data)

    public_session = _public_session(session_data)
    public_session["viewer"]["participantId"] = existing.get("id")
    public_session["viewer"]["participantName"] = existing.get("name")
    public_session["capabilities"]["canLeaveSession"] = True
    public_session["capabilities"]["canEditOwnAvailability"] = True

    return jsonify(
        {
            "session": public_session,
            "participantToken": participant_token,
            "participantId": existing.get("id"),
            "participantName": existing.get("name"),
        }
    )


@app.route("/api/session/<sid>/avail", methods=["PUT"])
def avail(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))
    participant = _participant_for_write(session_data, body.get("name"))
    if participant is None:
        return _api_error("participant_auth_required", 403, "需要先以参与者身份进入后才能填写")

    participant["avail"] = _normalize_avail(session_data, body.get("avail", {}))
    if "remark" in body:
        participant["remark"] = _clean_text(body.get("remark"), REMARK_MAX)
    _save(sid, session_data)
    _log_event(
        "info",
        "availability_saved",
        request_id=_request_id(),
        session_id=sid,
        participant=participant.get("name"),
        date_count=len(participant["avail"]),
        remark_len=len(participant.get("remark", "")),
    )
    return jsonify({"ok": True, "participantId": participant.get("id")})


@app.route("/api/session/<sid>", methods=["PATCH"])
def update_session(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    if not _creator_required(session_data):
        return _api_error("creator_auth_required", 403, "只有创建者可以修改整张表")

    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))

    merged_payload, errors = _validate_create_payload(
        {
            "name": body.get("name", session_data.get("name")),
            "dateS": body.get("dateS", session_data.get("dateS")),
            "dateE": body.get("dateE", session_data.get("dateE")),
            "hourS": body.get("hourS", session_data.get("hourS")),
            "hourE": body.get("hourE", session_data.get("hourE")),
            "creatorPrompt": body.get("creatorPrompt", session_data.get("creatorPrompt")),
            "expectedNames": body.get("expectedNames", session_data.get("expectedNames", [])),
        },
        creator_name=session_data.get("creator", {}).get("name"),
    )

    raw_participants = body.get("participants", session_data.get("participants", []))
    if not isinstance(raw_participants, list):
        errors.append("参与者名单格式不正确")
        raw_participants = session_data.get("participants", [])

    existing_by_id = {participant.get("id"): participant for participant in session_data.get("participants", [])}
    normalized_participants = _normalize_participants(merged_payload, raw_participants, existing_by_id=existing_by_id)

    if len(normalized_participants) != len(raw_participants):
        errors.append("参与者名单存在空昵称或重复昵称")
    if len(normalized_participants) > MAX_PARTICIPANTS:
        errors.append(f"参与者最多 {MAX_PARTICIPANTS} 人")

    if errors:
        return _api_error("invalid_payload", 400, "请求参数不合法", errors)

    session_data.update(merged_payload)
    session_data["participants"] = normalized_participants
    session_data["schemaVersion"] = SCHEMA_VERSION
    _save(sid, session_data)
    _log_event(
        "info",
        "session_updated",
        request_id=_request_id(),
        session_id=sid,
        participant_count=len(session_data.get("participants", [])),
        expected_count=len(session_data.get("expectedNames", [])),
    )
    return jsonify({"session": _public_session(session_data)})


@app.route("/api/session/<sid>", methods=["DELETE"])
def delete_session(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    legacy_session = not session_data.get("creator", {}).get("tokenHash")
    if not legacy_session and not _creator_required(session_data):
        return _api_error("creator_auth_required", 403, "只有创建者可以删除整张表")

    _delete(sid)
    _log_event(
        "info",
        "session_deleted",
        request_id=_request_id(),
        session_id=sid,
        mode="legacy_open_delete" if legacy_session else "creator_only",
    )
    return jsonify({"ok": True, "legacy": legacy_session})


@app.route("/api/session/<sid>/participants/<pid>", methods=["DELETE"])
def delete_participant(sid, pid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    participants = session_data.get("participants", [])
    target = next((item for item in participants if item.get("id") == _clean_text(pid, 32)), None)
    if target is None:
        return _api_error("participant_not_found", 404, "参与者不存在")

    viewer = _viewer_context(session_data)
    can_delete = viewer["is_creator"] or (viewer["participant"] and viewer["participant"].get("id") == target.get("id"))
    if not can_delete:
        return _api_error("participant_auth_required", 403, "只有创建者或参与者本人可以执行此操作")

    session_data["participants"] = [item for item in participants if item.get("id") != target.get("id")]
    _save(sid, session_data)
    _log_event(
        "info",
        "participant_deleted",
        request_id=_request_id(),
        session_id=sid,
        participant=target.get("name"),
        actor="creator" if viewer["is_creator"] else "self",
    )
    return jsonify({"ok": True, "participantId": target.get("id")})


@app.route("/api/session/<sid>/summary", methods=["GET"])
def summary(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")
    summary_text = generate_ai_summary(session_data)
    _log_event(
        "info",
        "summary_generated",
        request_id=_request_id(),
        session_id=sid,
        participant_count=len(session_data.get("participants", [])),
    )
    return jsonify({"summary": summary_text})


def main():
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


if __name__ == "__main__":
    main()
