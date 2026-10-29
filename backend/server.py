#!/usr/bin/env python3
"""群约小助手 - Flask + SQLite 服务端。"""
from __future__ import annotations

from datetime import date, timedelta
from flask import Flask, g, jsonify, request, send_from_directory
import hashlib
import json
import logging
import os
import re
import secrets
import time

import requests
from werkzeug.exceptions import HTTPException

from .create_draft import AI_DRAFT_TEXT_MAX, generate_ai_create_draft, normalize_create_draft_defaults
from . import storage

app = Flask(__name__, static_folder=None)
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(MODULE_DIR)
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
DB_PATH = storage.DB_PATH
DB_USES_URI = storage.DB_USES_URI
KEEPALIVE_DB = storage.KEEPALIVE_DB
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"

SESSION_NAME_MAX = 20
PERSON_NAME_MAX = 10
PROMPT_MAX = 200
REMARK_MAX = 200
INTERVAL_NOTE_MAX = 200
MAX_INTERVALS_PER_PARTICIPANT = 500
EXPECTED_NAMES_MAX = 12
MAX_PARTICIPANTS = 24
MAX_RANGE_DAYS = 14
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
SCHEMA_VERSION = 4

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("meetup")


def get_db():
    return storage.get_db()


def init_db():
    storage.init_db()
    global KEEPALIVE_DB
    KEEPALIVE_DB = storage.KEEPALIVE_DB


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
    payload = storage.load_session(sid)
    return _normalize_session_data(payload) if payload else None


def _save(sid: str, payload: dict) -> None:
    sid = _sanitize_sid(sid)
    normalized = _normalize_session_data(payload) or payload
    normalized["id"] = sid
    storage.save_session(sid, normalized)


def _clean_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _new_participant_id() -> str:
    return secrets.token_hex(6)


def _stable_participant_id(name: str) -> str:
    digest = hashlib.sha1(str(name or "").encode("utf-8")).hexdigest()[:10]
    return f"participant_{digest}"


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _safe_color(value: str | None, fallback: str = "#FF6B35") -> str:
    text = str(value or "").strip()
    return text if COLOR_RE.fullmatch(text) else fallback


def _delete(sid: str) -> None:
    sid = _sanitize_sid(sid)
    storage.delete_session(sid)


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


def _normalize_required_names(values):
    names = []
    seen = set()
    for value in values or []:
        name = _clean_text(value, PERSON_NAME_MAX)
        if not name or name in seen:
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
        participant_id = raw_id or (existing.get("id") if existing else "") or _stable_participant_id(name)
        if participant_id in seen_ids:
            participant_id = _new_participant_id()

        fallback_color = (existing or {}).get("color") or "#FF6B35"
        participant = {
            "id": participant_id,
            "name": name,
            "color": _safe_color(raw.get("color"), fallback_color),
            "intervals": _normalize_intervals(
                session_data,
                raw.get("intervals") if "intervals" in raw else (existing or {}).get("intervals", []),
            ),
            "remark": _clean_text(raw.get("remark") if "remark" in raw else (existing or {}).get("remark"), REMARK_MAX),
            "isRequired": _parse_bool(raw.get("isRequired") if "isRequired" in raw else (existing or {}).get("isRequired"), False),
        }

        token_hash = _clean_text(raw.get("tokenHash") if "tokenHash" in raw else (existing or {}).get("tokenHash"), 128)
        if token_hash:
            participant["tokenHash"] = token_hash

        seen_ids.add(participant_id)
        seen_names.add(name)
        participants.append(participant)

    return participants


def _merge_required_names(raw_data: dict, participants):
    required = []
    if isinstance(raw_data, dict):
        required.extend(raw_data.get("requiredNames", []))
    required.extend(participant.get("name") for participant in participants if participant.get("isRequired"))
    return _normalize_required_names(required)


def _normalize_session_data(raw_data: dict | None):
    if not isinstance(raw_data, dict):
        return None

    date_s = _parse_date(raw_data.get("dateS"))
    date_e = _parse_date(raw_data.get("dateE"))
    hour_s, hour_e, first_hour_s, last_hour_e = _normalize_time_window(
        date_s,
        date_e,
        raw_data.get("hourS", 9),
        raw_data.get("hourE", 21),
        raw_data.get("firstHourS", raw_data.get("hourS", 9)),
        raw_data.get("lastHourE", raw_data.get("hourE", 21)),
    )
    payload = {
        "id": _sanitize_sid(raw_data.get("id")),
        "schemaVersion": int(raw_data.get("schemaVersion") or 1),
        "name": _clean_text(raw_data.get("name"), SESSION_NAME_MAX),
        "dateS": date_s.isoformat() if date_s else "",
        "dateE": date_e.isoformat() if date_e else "",
        "hourS": hour_s,
        "hourE": hour_e,
        "firstHourS": first_hour_s,
        "lastHourE": last_hour_e,
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
    payload["requiredNames"] = _merge_required_names(raw_data, payload["participants"])
    return payload


def _validate_create_payload(body: dict, creator_name: str | None = None):
    name = _clean_text(body.get("name"), SESSION_NAME_MAX)
    creator_prompt = _clean_text(body.get("creatorPrompt"), PROMPT_MAX)
    date_s = _parse_date(body.get("dateS"))
    date_e = _parse_date(body.get("dateE"))
    hour_s = _parse_int(body.get("hourS", 9), -1)
    hour_e = _parse_int(body.get("hourE", 21), -1)
    first_hour_s = _parse_int(body.get("firstHourS", hour_s), -1)
    last_hour_e = _parse_int(body.get("lastHourE", hour_e), -1)

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
    if first_hour_s < hour_s or first_hour_s >= hour_e:
        errors.append("首日开始时间不正确")
    if last_hour_e <= hour_s or last_hour_e > hour_e:
        errors.append("末日结束时间不正确")
    if date_s and date_e and date_s == date_e and first_hour_s >= last_hour_e:
        errors.append("同一天的首尾截断时间不正确")

    hour_s, hour_e, first_hour_s, last_hour_e = _normalize_time_window(
        date_s,
        date_e,
        hour_s,
        hour_e,
        first_hour_s,
        last_hour_e,
    )

    payload = {
        "name": name,
        "dateS": date_s.isoformat() if date_s else "",
        "dateE": date_e.isoformat() if date_e else "",
        "hourS": hour_s,
        "hourE": hour_e,
        "firstHourS": first_hour_s,
        "lastHourE": last_hour_e,
        "creatorPrompt": creator_prompt,
        "expectedNames": _dedupe_names(body.get("expectedNames", []), exclude=creator_name),
        "requiredNames": _normalize_required_names(body.get("requiredNames", [])),
        "participants": [],
    }
    return payload, errors


def _normalize_time_window(date_s, date_e, hour_s, hour_e, first_hour_s, last_hour_e):
    hour_s = _parse_int(hour_s, 9)
    hour_e = _parse_int(hour_e, 21)
    if hour_s < 0 or hour_s > 23 or hour_e < 1 or hour_e > 24 or hour_s >= hour_e:
        hour_s, hour_e = 9, 21

    first_hour_s = _parse_int(first_hour_s, hour_s)
    last_hour_e = _parse_int(last_hour_e, hour_e)
    first_hour_s = min(max(first_hour_s, hour_s), hour_e - 1)
    last_hour_e = max(min(last_hour_e, hour_e), hour_s + 1)

    if date_s and date_e and date_s == date_e and first_hour_s >= last_hour_e:
        first_hour_s, last_hour_e = hour_s, hour_e

    return hour_s, hour_e, first_hour_s, last_hour_e


def _time_bounds(session_data: dict, session_date: str):
    hour_s = _parse_int(session_data.get("hourS", 9), 9)
    hour_e = _parse_int(session_data.get("hourE", 21), 21)
    start = hour_s * 60
    end = hour_e * 60
    if session_date == session_data.get("dateS"):
        start = _parse_int(session_data.get("firstHourS", hour_s), hour_s) * 60
    if session_date == session_data.get("dateE"):
        end = _parse_int(session_data.get("lastHourE", hour_e), hour_e) * 60
    return start, end


def _normalize_intervals(session_data: dict, raw_intervals):
    if not isinstance(raw_intervals, list):
        return []
    valid_dates = set(_iter_dates(session_data))
    intervals = []
    for raw in raw_intervals[:MAX_INTERVALS_PER_PARTICIPANT]:
        if not isinstance(raw, dict):
            continue
        session_date = str(raw.get("date") or "")
        kind = str(raw.get("type") or "")
        start = _parse_int(raw.get("startMinute"), -1)
        end = _parse_int(raw.get("endMinute"), -1)
        if session_date not in valid_dates or kind not in {"busy", "preferred"}:
            continue
        bounds = _time_bounds(session_data, session_date)
        if start < bounds[0] or end > bounds[1] or start >= end:
            continue
        intervals.append(
            {
                "id": _clean_text(raw.get("id"), 64) or secrets.token_hex(12),
                "date": session_date,
                "startMinute": start,
                "endMinute": end,
                "type": kind,
                "note": _clean_text(raw.get("note"), INTERVAL_NOTE_MAX),
            }
        )
    return sorted(intervals, key=lambda item: (item["date"], item["startMinute"], item["endMinute"]))


def _validate_interval_payload(session_data: dict, raw_intervals):
    if not isinstance(raw_intervals, list):
        return None, ["intervals 必须是数组"]
    if len(raw_intervals) > MAX_INTERVALS_PER_PARTICIPANT:
        return None, [f"每人最多保存 {MAX_INTERVALS_PER_PARTICIPANT} 段时间"]
    valid_dates = set(_iter_dates(session_data))
    intervals = []
    errors = []
    seen_ids = set()
    for index, raw in enumerate(raw_intervals):
        if not isinstance(raw, dict):
            errors.append(f"第 {index + 1} 段格式不正确")
            continue
        session_date = str(raw.get("date") or "")
        if session_date not in valid_dates:
            errors.append(f"第 {index + 1} 段日期不在活动范围内")
            continue
        start_raw = raw.get("startMinute")
        end_raw = raw.get("endMinute")
        if any(isinstance(value, (bool, float)) for value in (start_raw, end_raw)):
            errors.append(f"第 {index + 1} 段时间格式不正确")
            continue
        try:
            start = int(start_raw)
            end = int(end_raw)
        except (TypeError, ValueError):
            errors.append(f"第 {index + 1} 段时间格式不正确")
            continue
        bounds = _time_bounds(session_data, session_date)
        if start < bounds[0] or end > bounds[1] or start >= end:
            errors.append(f"第 {index + 1} 段时间超出当天活动范围")
            continue
        kind = str(raw.get("type") or "")
        if kind not in {"busy", "preferred"}:
            errors.append(f"第 {index + 1} 段类型不正确")
            continue
        interval_id = _clean_text(raw.get("id"), 64) or secrets.token_hex(12)
        if interval_id in seen_ids:
            errors.append(f"第 {index + 1} 段 ID 重复")
            continue
        seen_ids.add(interval_id)
        intervals.append(
            {
                "id": interval_id,
                "date": session_date,
                "startMinute": start,
                "endMinute": end,
                "type": kind,
                "note": _clean_text(raw.get("note"), INTERVAL_NOTE_MAX),
            }
        )
    intervals.sort(key=lambda item: (item["date"], item["startMinute"], item["endMinute"]))
    previous = None
    for item in intervals:
        if previous and previous["date"] == item["date"] and item["startMinute"] < previous["endMinute"]:
            errors.append(f"{item['date']} 的时间条不能互相重叠")
            break
        previous = item
    return (None, errors) if errors else (intervals, [])


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
    return {
        "id": session_data.get("id"),
        "schemaVersion": session_data.get("schemaVersion", 1),
        "name": session_data.get("name", ""),
        "dateS": session_data.get("dateS", ""),
        "dateE": session_data.get("dateE", ""),
        "hourS": session_data.get("hourS", 9),
        "hourE": session_data.get("hourE", 21),
        "firstHourS": session_data.get("firstHourS", session_data.get("hourS", 9)),
        "lastHourE": session_data.get("lastHourE", session_data.get("hourE", 21)),
        "creatorPrompt": session_data.get("creatorPrompt", ""),
        "creatorName": creator.get("name", ""),
        "expectedNames": session_data.get("expectedNames", []),
        "requiredNames": session_data.get("requiredNames", []),
        "participants": [
            {
                "id": participant.get("id"),
                "name": participant.get("name"),
                "color": participant.get("color"),
                "intervals": participant.get("intervals", []),
                "remark": participant.get("remark", ""),
                "isRequired": bool(participant.get("isRequired")),
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
            "canDeleteSession": viewer["is_creator"],
            "canManageParticipants": viewer["is_creator"],
            "canLeaveSession": bool(viewer["participant"]),
            "canEditOwnIntervals": bool(viewer["participant"]),
        },
    }


def _creator_required(session_data: dict):
    viewer = _viewer_context(session_data)
    if viewer["is_creator"]:
        return viewer
    return None


def _participant_for_write(session_data: dict):
    viewer = _viewer_context(session_data)
    if viewer["participant"]:
        return viewer["participant"]
    return None


def _required_participants(participants):
    return [participant for participant in participants if participant.get("isRequired")]


def _minute_label(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


def _interval_label(item: dict) -> str:
    start = item.get("start", item.get("startMinute", 0))
    end = item.get("end", item.get("endMinute", 0))
    return f"{item['date'][5:]} {_minute_label(start)}-{_minute_label(end)}"


def _interval_summary_segments(session_data: dict):
    participants = session_data.get("participants", [])
    required_names = {person.get("name", "未知") for person in _required_participants(participants)}
    result = []
    for session_date in _iter_dates(session_data):
        window_start, window_end = _time_bounds(session_data, session_date)
        boundaries = {window_start, window_end}
        participant_intervals = []
        for participant in participants:
            intervals = []
            for interval in participant.get("intervals", []):
                if interval.get("date") != session_date:
                    continue
                start = max(window_start, _parse_int(interval.get("startMinute"), window_start))
                end = min(window_end, _parse_int(interval.get("endMinute"), window_end))
                if start >= end or interval.get("type") not in {"busy", "preferred"}:
                    continue
                boundaries.update((start, end))
                intervals.append({"start": start, "end": end, "type": interval["type"]})
            participant_intervals.append((participant, intervals))

        points = sorted(boundaries)
        for index in range(len(points) - 1):
            start, end = points[index], points[index + 1]
            busy = []
            preferred = []
            for participant, intervals in participant_intervals:
                if any(item["start"] <= start and item["end"] >= end and item["type"] == "busy" for item in intervals):
                    busy.append(participant.get("name", "未知"))
                if any(item["start"] <= start and item["end"] >= end and item["type"] == "preferred" for item in intervals):
                    preferred.append(participant.get("name", "未知"))
            if not busy and not preferred:
                continue
            required_preferred = [name for name in preferred if name in required_names]
            required_busy = [name for name in busy if name in required_names]
            item = {
                "date": session_date,
                "start": start,
                "end": end,
                "busy": busy,
                "preferred": preferred,
                "busy_count": len(busy),
                "preferred_count": len(preferred),
                "required_preferred": required_preferred,
                "required_preferred_count": len(required_preferred),
                "required_busy": required_busy,
            }
            previous = result[-1] if result else None
            same_members = previous and (
                previous["date"] == session_date
                and previous["end"] == start
                and previous["busy"] == busy
                and previous["preferred"] == preferred
            )
            if same_members:
                previous["end"] = end
            else:
                result.append(item)
    return result


def _build_local_summary(session_data: dict) -> str:
    participants = session_data.get("participants", [])
    interval_segments = _interval_summary_segments(session_data)
    participant_total = len(participants)
    required_people = _required_participants(participants)
    required_total = len(required_people)
    recommended = sorted(
        [item for item in interval_segments if item["busy_count"] == 0 and item["preferred_count"] > 0],
        key=lambda item: (-item["required_preferred_count"], -item["preferred_count"], -(item["end"] - item["start"]), item["date"], item["start"]),
    )[:3]
    busy_segments = [item for item in interval_segments if item["busy_count"] > 0]
    pending_names = [participant.get("name", "未知") for participant in participants if not participant.get("intervals")]
    remarks = [(participant.get("name", "未知"), _clean_text(participant.get("remark"), REMARK_MAX)) for participant in participants if (participant.get("remark") or "").strip()]

    lines = ["## 推荐时段"]
    if recommended:
        for item in recommended:
            pref_names = "、".join(item["preferred"])
            lines.append(
                f"- {_interval_label(item)}：{item['preferred_count']}/{participant_total} 人偏好，"
                f"不方便 {item['busy_count']} 人；偏好成员：{pref_names}。"
            )
    else:
        lines.append("- 目前还没有同时避开不方便区间且存在明确偏好的时段。")

    lines.append("")
    lines.append("## 协调建议")
    if recommended:
        best = recommended[0]
        lines.append(f"- 可优先沟通 {_interval_label(best)}，有 {best['preferred_count']}/{participant_total} 人明确偏好，且没有人标记不方便。")
    else:
        lines.append("- 暂无无冲突的明确偏好重叠区间，可协商调整已有区间或补充填写。")
    if busy_segments:
        conflicts = "; ".join(
            f"{_interval_label(item)}（{', '.join(item['busy'])}）"
            for item in sorted(busy_segments, key=lambda item: (item["date"], item["start"]))[:3]
        )
        lines.append(f"- 明确不方便区间：{conflicts}。")
    if pending_names:
        lines.append(f"- 尚未填写时间条：{'、'.join(pending_names)}。")

    if required_total:
        lines.append("")
        lines.append("## 关键成员约束")
        lines.append(f"- 当前共标记 {required_total} 位关键成员：{', '.join(participant.get('name', '未知') for participant in required_people)}。")
        clean_intervals = [item for item in recommended if not item["required_busy"]]
        if clean_intervals:
            lines.append(f"- 没有关键成员标记不方便的偏好区间，例如 {_interval_label(clean_intervals[0])}。")
        else:
            lines.append("- 当前尚无避开关键成员不方便区间的明确偏好时段。")

    if remarks:
        lines.append("")
        lines.append("## 参与者整体说明")
        for name, note in remarks:
            lines.append(f"- {name}：{note}")

    interval_notes = [
        (participant.get("name", "未知"), interval)
        for participant in participants
        for interval in participant.get("intervals", [])
        if interval.get("note")
    ]
    if interval_notes:
        lines.extend(["", "## 时间条备注"])
        for name, interval in interval_notes[:20]:
            lines.append(f"- {name} · {_interval_label(interval)}：{interval['note']}")

    if participants:
        lines.append("")
        lines.append("## 填写进度")
        lines.append(f"- 当前共 {participant_total} 人参与，已填写 {participant_total - len(pending_names)} 人，待填写 {len(pending_names)} 人。")
    return "\n".join(lines)


def _build_ai_prompt(session_data: dict, fallback_summary: str) -> str:
    intervals = _interval_summary_segments(session_data)
    required_people = _required_participants(session_data.get("participants", []))
    participant_count = len(session_data.get("participants", []))
    highlights = sorted(
        [item for item in intervals if item["busy_count"] == 0 and item["preferred_count"] > 0],
        key=lambda item: (-item["required_preferred_count"], -item["preferred_count"], -(item["end"] - item["start"]), item["date"], item["start"]),
    )[:5]
    highlight_lines = [
        f"- {_interval_label(item)}：偏好 {item['preferred_count']}/{participant_count} 人，"
        f"不方便 {item['busy_count']} 人，偏好成员 {', '.join(item['preferred'])}"
        + (
            f"；关键成员偏好 {len(item['required_preferred'])} 人，关键成员不方便 {', '.join(item['required_busy'])}"
            if required_people else ""
        )
        for item in highlights
    ] or ["- 暂无有效高亮时段"]
    time_label = f"{session_data.get('hourS', 9)}:00 - {session_data.get('hourE', 21)}:00"
    first_hour_s = session_data.get("firstHourS", session_data.get("hourS", 9))
    last_hour_e = session_data.get("lastHourE", session_data.get("hourE", 21))
    if first_hour_s != session_data.get("hourS", 9) or last_hour_e != session_data.get("hourE", 21):
        time_label = (
            f"每日 {time_label}；首日 {first_hour_s}:00 起；"
            f"末日 {last_hour_e}:00 止"
        )

    return (
        "请只依据参与者明确保存的时间区间进行总结，用简洁中文输出 markdown。\n\n"
        f"活动名称：{session_data.get('name', '时间调查')}\n"
        f"日期范围：{session_data.get('dateS', '')} 至 {session_data.get('dateE', '')}\n"
        f"时间范围：{time_label}\n"
        f"发起人提示：{session_data.get('creatorPrompt', '') or '无'}\n\n"
        f"参与人数：{participant_count}\n"
        f"关键成员：{', '.join(participant.get('name', '未知') for participant in required_people) or '无'}\n"
        "红色不方便区间表示明确冲突并集；绿色偏好以明确标记偏好的人数统计。没有区间记录不等于有空。\n\n"
        "本地预分析：\n"
        f"{fallback_summary}\n\n"
        "高亮时段：\n"
        f"{'\n'.join(highlight_lines)}\n\n"
        "请按以下结构回答：\n"
        "## 推荐时段\n"
        "- 优先考虑没有人标记不方便、且明确偏好人数较多的连续区间\n"
        "## 协调建议\n"
        "- 给出备选与沟通建议，若关键成员冲突请明确指出\n"
        "## 关键成员约束\n"
        "- 概括关键成员的偏好与不方便区间\n"
        "## 参与者整体说明\n"
        "- 只在确实有备注或限制时输出\n"
    )


def _deepseek_chat(user_prompt: str, *, temperature: float, max_tokens: int):
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("missing_api_key")

    response = requests.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": user_prompt}],
            "thinking": {"type": "disabled"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"upstream_status_{response.status_code}")

    data = response.json()
    choices = data.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else ""
    if not content:
        raise RuntimeError("empty_choice")
    return content


def generate_ai_summary(session_data: dict) -> str:
    fallback_summary = _build_local_summary(session_data)
    if not DEEPSEEK_API_KEY:
        return fallback_summary

    try:
        return _deepseek_chat(_build_ai_prompt(session_data, fallback_summary), temperature=0.4, max_tokens=500)
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
    return jsonify(
        {
            "ok": True,
            "service": "meetup",
            "ai_configured": bool(DEEPSEEK_API_KEY),
            "ai_model": DEEPSEEK_MODEL,
        }
    )


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
        required_count=len(payload.get("requiredNames", [])),
    )
    return jsonify({"id": sid, "creatorToken": creator_token})


@app.route("/api/session/draft", methods=["POST"])
def create_draft():
    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))

    text = _clean_text(body.get("text"), AI_DRAFT_TEXT_MAX)
    if not text:
        return _api_error("invalid_payload", 400, "请求参数不合法", ["活动描述不能为空"])

    defaults = normalize_create_draft_defaults(body.get("defaults"))
    draft, notes, warnings, source = generate_ai_create_draft(
        text,
        defaults,
        api_key=DEEPSEEK_API_KEY,
        api_url=DEEPSEEK_API_URL,
        model=DEEPSEEK_MODEL,
        request_id=_request_id(),
        log_event=_log_event,
    )
    _log_event(
        "info",
        "session_draft_generated",
        request_id=_request_id(),
        source=source,
        expected_count=len(draft.get("expectedNames", [])),
        required_count=len(draft.get("requiredNames", [])),
    )
    return jsonify(
        {
            "draft": draft,
            "notes": notes,
            "warnings": warnings,
            "source": source,
        }
    )


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
                "intervals": [],
                "remark": "",
                "isRequired": name in set(session_data.get("requiredNames", [])),
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
    public_session["capabilities"]["canEditOwnIntervals"] = True

    return jsonify(
        {
            "session": public_session,
            "participantToken": participant_token,
            "participantId": existing.get("id"),
            "participantName": existing.get("name"),
        }
    )


@app.route("/api/session/<sid>/intervals", methods=["GET", "PUT"])
def participant_intervals(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    participant = _participant_for_write(session_data)
    if participant is None:
        return _api_error("participant_auth_required", 403, "需要参与者令牌才能读取或保存自己的时间条")

    if request.method == "GET":
        return jsonify({"participantId": participant.get("id"), "intervals": participant.get("intervals", [])})

    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))
    if not isinstance(body, dict):
        return _api_error("invalid_payload", 400, "请求体必须是 JSON 对象")
    intervals, errors = _validate_interval_payload(session_data, body.get("intervals"))
    if errors:
        return _api_error("invalid_payload", 400, "时间条数据不合法", errors)

    storage.replace_participant_intervals(session_data["id"], participant["id"], intervals)
    participant["intervals"] = intervals
    _log_event(
        "info",
        "participant_intervals_saved",
        request_id=_request_id(),
        session_id=session_data["id"],
        participant=participant.get("name"),
        interval_count=len(intervals),
    )
    return jsonify({"ok": True, "participantId": participant.get("id"), "intervals": intervals})


@app.route("/api/session/<sid>/remark", methods=["PUT"])
def participant_remark(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    try:
        body = _json_body()
    except ValueError as exc:
        return _api_error("invalid_json", 400, str(exc))
    if not isinstance(body, dict):
        return _api_error("invalid_payload", 400, "请求体必须是 JSON 对象")

    participant = _participant_for_write(session_data)
    if participant is None:
        return _api_error("participant_auth_required", 403, "需要参与者令牌才能修改整体说明")

    remark = _clean_text(body.get("remark"), REMARK_MAX)
    storage.update_participant_remark(session_data["id"], participant["id"], remark)
    participant["remark"] = remark
    _log_event(
        "info",
        "participant_remark_saved",
        request_id=_request_id(),
        session_id=session_data["id"],
        participant=participant.get("name"),
        remark_len=len(remark),
    )
    return jsonify({"ok": True, "participantId": participant.get("id"), "remark": remark})


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
            "firstHourS": body.get("firstHourS", session_data.get("firstHourS", session_data.get("hourS"))),
            "lastHourE": body.get("lastHourE", session_data.get("lastHourE", session_data.get("hourE"))),
            "creatorPrompt": body.get("creatorPrompt", session_data.get("creatorPrompt")),
            "expectedNames": body.get("expectedNames", session_data.get("expectedNames", [])),
            "requiredNames": body.get("requiredNames", session_data.get("requiredNames", [])),
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
    session_data["requiredNames"] = _merge_required_names(
        {
            "requiredNames": body.get("requiredNames", session_data.get("requiredNames", [])),
        },
        normalized_participants,
    )
    session_data["schemaVersion"] = SCHEMA_VERSION
    _save(sid, session_data)
    interval_windows = {
        session_date: _time_bounds(session_data, session_date)
        for session_date in _iter_dates(session_data)
    }
    storage.prune_intervals_to_session_windows(sid, interval_windows)
    _log_event(
        "info",
        "session_updated",
        request_id=_request_id(),
        session_id=sid,
        participant_count=len(session_data.get("participants", [])),
        expected_count=len(session_data.get("expectedNames", [])),
        required_count=len(session_data.get("requiredNames", [])),
    )
    return jsonify({"session": _public_session(session_data)})


@app.route("/api/session/<sid>", methods=["DELETE"])
def delete_session(sid):
    session_data = _load(sid)
    if not session_data:
        return _api_error("not_found", 404, "会话不存在")

    if not _creator_required(session_data):
        return _api_error("creator_auth_required", 403, "只有创建者可以删除整张表")

    _delete(sid)
    _log_event(
        "info",
        "session_deleted",
        request_id=_request_id(),
        session_id=sid,
        mode="creator_only",
    )
    return jsonify({"ok": True})


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
