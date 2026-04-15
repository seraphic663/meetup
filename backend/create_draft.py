from __future__ import annotations

from datetime import date, timedelta
import json
import re

import requests

AI_DRAFT_TEXT_MAX = 300
SESSION_NAME_MAX = 20
PERSON_NAME_MAX = 10
PROMPT_MAX = 200
EXPECTED_NAMES_MAX = 12
MAX_RANGE_DAYS = 14


def _clean_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_date(value):
    try:
        return date.fromisoformat(str(value))
    except Exception:
        return None


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


def default_create_draft():
    today = date.today()
    end = today + timedelta(days=3)
    return {
        "name": "",
        "dateS": today.isoformat(),
        "dateE": end.isoformat(),
        "hourS": 9,
        "hourE": 21,
        "firstHourS": 9,
        "lastHourE": 21,
        "creatorName": "",
        "creatorPrompt": "",
        "expectedNames": [],
        "requiredNames": [],
    }


def normalize_create_draft_defaults(raw_defaults):
    defaults = default_create_draft()
    if not isinstance(raw_defaults, dict):
        return defaults

    date_s = _parse_date(raw_defaults.get("dateS")) or _parse_date(defaults["dateS"])
    date_e = _parse_date(raw_defaults.get("dateE")) or _parse_date(defaults["dateE"])
    if date_s and date_e and date_s > date_e:
        date_s, date_e = date_e, date_s

    hour_s, hour_e, first_hour_s, last_hour_e = _normalize_time_window(
        date_s,
        date_e,
        raw_defaults.get("hourS", defaults["hourS"]),
        raw_defaults.get("hourE", defaults["hourE"]),
        raw_defaults.get("firstHourS", raw_defaults.get("hourS", defaults["firstHourS"])),
        raw_defaults.get("lastHourE", raw_defaults.get("hourE", defaults["lastHourE"])),
    )
    defaults.update(
        {
            "name": _clean_text(raw_defaults.get("name"), SESSION_NAME_MAX),
            "dateS": date_s.isoformat() if date_s else defaults["dateS"],
            "dateE": date_e.isoformat() if date_e else defaults["dateE"],
            "hourS": hour_s,
            "hourE": hour_e,
            "firstHourS": first_hour_s,
            "lastHourE": last_hour_e,
            "creatorName": _clean_text(raw_defaults.get("creatorName"), PERSON_NAME_MAX),
            "creatorPrompt": _clean_text(raw_defaults.get("creatorPrompt"), PROMPT_MAX),
            "expectedNames": _dedupe_names(raw_defaults.get("expectedNames", [])),
            "requiredNames": _normalize_required_names(raw_defaults.get("requiredNames", [])),
        }
    )
    return defaults


def _merge_create_draft(defaults: dict, parsed: dict):
    merged = dict(defaults)

    parsed_name = _clean_text(parsed.get("name"), SESSION_NAME_MAX)
    if parsed_name:
        merged["name"] = parsed_name

    date_s = _parse_date(parsed.get("dateS")) or _parse_date(defaults.get("dateS"))
    date_e = _parse_date(parsed.get("dateE")) or _parse_date(defaults.get("dateE")) or date_s
    if date_s and date_e and date_s <= date_e and (date_e - date_s).days <= MAX_RANGE_DAYS:
        merged["dateS"] = date_s.isoformat()
        merged["dateE"] = date_e.isoformat()

    hour_s = parsed.get("hourS", defaults.get("hourS", 9))
    hour_e = parsed.get("hourE", defaults.get("hourE", 21))
    first_hour_s = parsed.get("firstHourS", hour_s)
    last_hour_e = parsed.get("lastHourE", hour_e)
    hour_s, hour_e, first_hour_s, last_hour_e = _normalize_time_window(
        _parse_date(merged["dateS"]),
        _parse_date(merged["dateE"]),
        hour_s,
        hour_e,
        first_hour_s,
        last_hour_e,
    )
    merged.update(
        {
            "hourS": hour_s,
            "hourE": hour_e,
            "firstHourS": first_hour_s,
            "lastHourE": last_hour_e,
        }
    )

    parsed_prompt = _clean_text(parsed.get("creatorPrompt"), PROMPT_MAX)
    if parsed_prompt:
        merged["creatorPrompt"] = parsed_prompt

    expected_names = _dedupe_names([*defaults.get("expectedNames", []), *(parsed.get("expectedNames") or [])])
    required_names = _normalize_required_names([*defaults.get("requiredNames", []), *(parsed.get("requiredNames") or [])])
    merged["requiredNames"] = required_names
    merged["expectedNames"] = _dedupe_names([*expected_names, *required_names], exclude=defaults.get("creatorName") or None)
    merged["creatorName"] = _clean_text(parsed.get("creatorName") or defaults.get("creatorName"), PERSON_NAME_MAX)
    return merged


def _extract_json_object(text: str):
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _local_session_draft(defaults: dict, reason: str):
    notes = ["已保留当前表单内容，请手动调整后再创建。"]
    warnings = [reason]
    return dict(defaults), notes, warnings, "local"


def _build_ai_create_prompt(user_text: str, defaults: dict):
    today = date.today().isoformat()
    return (
        "你是时间调查表草稿助手。请把用户的一句话需求解析成 JSON，不要输出 JSON 以外的内容。\n"
        f"今天日期：{today}\n"
        "字段说明：\n"
        "- name: 活动名称，20 字以内\n"
        "- dateS/dateE: ISO 日期，如 2026-04-12\n"
        "- hourS/hourE: 每日总体时间范围，整数小时，hourE 取结束小时\n"
        "- firstHourS/lastHourE: 首日/末日截断时间，整数小时\n"
        "- creatorPrompt: 给参与者看的约束说明，200 字以内\n"
        "- expectedNames: 预设参与者昵称数组\n"
        "- requiredNames: 必须到场或优先满足的人名数组\n"
        "- notes: 成功识别到的信息\n"
        "- warnings: 存在歧义或没有识别到的部分\n"
        "规则：\n"
        "- 不要臆造没有提到的名字、日期或时间\n"
        "- 如果信息不明确，请用 null 或空数组，并写入 warnings\n"
        "- 如果用户提到“必须到场”“关键成员”，把这些名字放入 requiredNames\n"
        "- 如果只识别到单日，dateS 和 dateE 用同一天\n"
        "- 如果只识别到时间段关键词，如“晚上”，可推成合理小时段\n"
        f"当前默认草稿：{json.dumps(defaults, ensure_ascii=False)}\n"
        f"用户输入：{user_text}\n"
        '请返回 JSON，例如 {"name":"","dateS":null,"dateE":null,"hourS":null,"hourE":null,"firstHourS":null,"lastHourE":null,"creatorPrompt":"","expectedNames":[],"requiredNames":[],"notes":[],"warnings":[]}'
    )


def _call_deepseek(user_prompt: str, api_key: str, api_url: str):
    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": 0.2,
            "max_tokens": 500,
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(f"upstream_status_{response.status_code}")

    data = response.json()
    choices = data.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else ""
    if not content:
        raise RuntimeError("empty_choice")
    return content


def generate_ai_create_draft(user_text: str, defaults: dict, *, api_key: str, api_url: str, request_id: str | None = None, log_event=None):
    if not api_key:
        return _local_session_draft(defaults, "AI 草稿生成不可用：未配置 API Key。")

    try:
        raw_content = _call_deepseek(_build_ai_create_prompt(user_text, defaults), api_key, api_url)
        payload = _extract_json_object(raw_content)
        if not isinstance(payload, dict):
            raise RuntimeError("invalid_json")
        notes = [str(item).strip() for item in payload.get("notes", []) if str(item).strip()]
        warnings = [str(item).strip() for item in payload.get("warnings", []) if str(item).strip()]
        merged = _merge_create_draft(defaults, payload)
        if payload.get("requiredNames"):
            detected = "、".join(_normalize_required_names(payload.get("requiredNames", [])))
            notes.append(f"检测到关键成员：{detected}。创建后这些名字会自动按关键成员预设。")
        return merged, list(dict.fromkeys(notes)), list(dict.fromkeys(warnings)), "ai"
    except requests.exceptions.Timeout:
        if callable(log_event):
            log_event("warning", "ai_create_draft_failed", request_id=request_id, reason="timeout")
    except Exception as exc:
        if callable(log_event):
            log_event(
                "warning",
                "ai_create_draft_failed",
                request_id=request_id,
                reason=type(exc).__name__,
                message=str(exc),
            )

    return _local_session_draft(defaults, "AI 草稿生成暂时不可用，请手动调整表单。")
