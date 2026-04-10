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

WEEKDAY_INDEX = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
TIME_KEYWORDS = {
    "今天", "明天", "后天", "本周", "这周", "下周", "周一", "周二", "周三", "周四", "周五", "周六", "周日", "周天",
    "上午", "下午", "晚上", "晚间", "中午", "凌晨", "工作日", "周末", "全天", "线下", "线上", "开始", "结束", "到",
    "至", "日期", "时间", "活动", "会议", "聚餐", "评审", "讨论", "复盘", "团建", "约饭", "参加", "参与", "安排", "创建",
}


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


def _make_date(year: int, month: int, day: int):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _next_weekday(base_date: date, weekday: int, offset_weeks: int = 0) -> date:
    week_start = base_date - timedelta(days=base_date.weekday())
    target = week_start + timedelta(days=weekday, weeks=offset_weeks)
    if offset_weeks == 0 and target < base_date:
        target += timedelta(days=7)
    return target


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


def _parse_date_fragment(text: str, base_date: date):
    normalized = str(text or "").replace("周天", "周日").replace("礼拜天", "周日")
    if "今天" in normalized:
        return base_date
    if "明天" in normalized:
        return base_date + timedelta(days=1)
    if "后天" in normalized:
        return base_date + timedelta(days=2)

    full = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", normalized)
    if full:
        return _make_date(int(full.group(1)), int(full.group(2)), int(full.group(3)))

    md = re.search(r"(\d{1,2})月(\d{1,2})日?", normalized)
    if md:
        candidate = _make_date(base_date.year, int(md.group(1)), int(md.group(2)))
        if candidate and candidate < base_date - timedelta(days=30):
            next_year = _make_date(base_date.year + 1, int(md.group(1)), int(md.group(2)))
            return next_year or candidate
        return candidate

    wd = re.search(r"(本周|这周|下周)?周([一二三四五六日天])", normalized)
    if wd:
        prefix = wd.group(1) or ""
        offset_weeks = 1 if prefix == "下周" else 0
        return _next_weekday(base_date, WEEKDAY_INDEX[wd.group(2)], offset_weeks=offset_weeks)

    return None


def _parse_date_range(text: str, base_date: date):
    normalized = str(text or "").replace("周天", "周日").replace("礼拜天", "周日")

    full_range = re.search(
        r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*(?:到|至|[-~—])\s*(?:(\d{4})[/-])?(\d{1,2})[/-](\d{1,2})",
        normalized,
    )
    if full_range:
        start = _make_date(int(full_range.group(1)), int(full_range.group(2)), int(full_range.group(3)))
        end_year = int(full_range.group(4) or full_range.group(1))
        end = _make_date(end_year, int(full_range.group(5)), int(full_range.group(6)))
        if start and end:
            return start, end

    md_range = re.search(
        r"(\d{1,2})月(\d{1,2})日?\s*(?:到|至|[-~—])\s*(?:(\d{1,2})月)?(\d{1,2})日",
        normalized,
    )
    if md_range:
        start_month = int(md_range.group(1))
        start_day = int(md_range.group(2))
        end_month = int(md_range.group(3) or start_month)
        end_day = int(md_range.group(4))
        start = _make_date(base_date.year, start_month, start_day)
        end_year = base_date.year + (1 if end_month < start_month else 0)
        end = _make_date(end_year, end_month, end_day)
        if start and end:
            return start, end

    wd_range = re.search(
        r"(本周|这周|下周)?周([一二三四五六日天])\s*(?:到|至|[-~—])\s*(?:(本周|这周|下周)?周)?([一二三四五六日天])",
        normalized,
    )
    if wd_range:
        start_prefix = wd_range.group(1) or ""
        end_prefix = wd_range.group(3) if wd_range.group(3) is not None else start_prefix
        start = _next_weekday(base_date, WEEKDAY_INDEX[wd_range.group(2)], 1 if start_prefix == "下周" else 0)
        end = _next_weekday(base_date, WEEKDAY_INDEX[wd_range.group(4)], 1 if end_prefix == "下周" else 0)
        if end < start:
            end += timedelta(days=7)
        return start, end

    single = _parse_date_fragment(normalized, base_date)
    if single:
        return single, single

    return None, None


def _parse_hour_value(hour_text: str, meridiem: str | None = None, minute_text: str | None = None):
    hour = _parse_int(hour_text, -1)
    minute = _parse_int(minute_text, 0)
    if hour < 0:
        return None

    meridiem = meridiem or ""
    if meridiem in {"下午", "晚上", "晚间"} and hour < 12:
        hour += 12
    elif meridiem == "中午":
        if hour < 11:
            hour += 12
        elif hour == 12:
            hour = 12
    elif meridiem in {"上午", "早上"} and hour == 12:
        hour = 0
    elif meridiem == "凌晨" and hour == 12:
        hour = 0

    if hour > 24:
        return None
    if minute > 0 and hour < 24:
        hour += 1
    return min(hour, 24)


def _parse_time_range(text: str, defaults: dict):
    normalized = str(text or "")
    simple_hours = []
    digits = ""
    for ch in normalized:
        if ch.isdigit():
            digits += ch
            continue
        if ch == "点" and digits:
            simple_hours.append(digits[-2:])
        digits = ""
    if len(simple_hours) >= 2 and any(separator in normalized for separator in ("到", "至", "-", "~", "—")):
        meridiem = next((keyword for keyword in ("凌晨", "早上", "上午", "中午", "下午", "晚上", "晚间") if keyword in normalized), None)
        start_hour = _parse_hour_value(simple_hours[0], meridiem)
        end_hour = _parse_hour_value(simple_hours[1], meridiem)
        if start_hour is not None and end_hour is not None and start_hour < end_hour:
            return {
                "hourS": start_hour,
                "hourE": end_hour,
                "firstHourS": start_hour,
                "lastHourE": end_hour,
            }

    after_match = re.search(
        r"(凌晨|早上|上午|中午|下午|晚上|晚间)?\s*(\d{1,2})(?:[:：](\d{1,2}))?\s*点(?:后|以后|开始)",
        normalized,
    )
    before_match = re.search(
        r"(凌晨|早上|上午|中午|下午|晚上|晚间)?\s*(\d{1,2})(?:[:：](\d{1,2}))?\s*点(?:前|以前|结束)",
        normalized,
    )
    if after_match or before_match:
        hour_s = defaults["hourS"]
        hour_e = defaults["hourE"]
        if after_match:
            parsed = _parse_hour_value(after_match.group(2), after_match.group(1), after_match.group(3))
            if parsed is not None:
                hour_s = min(parsed, 23)
                hour_e = max(hour_e, min(hour_s + 3, 24))
        if before_match:
            parsed = _parse_hour_value(before_match.group(2), before_match.group(1), before_match.group(3))
            if parsed is not None:
                hour_e = max(min(parsed, 24), hour_s + 1)
        if hour_s < hour_e:
            return {
                "hourS": hour_s,
                "hourE": hour_e,
                "firstHourS": hour_s,
                "lastHourE": hour_e,
            }

    descriptor_map = {
        "上午": (9, 12),
        "早上": (8, 12),
        "中午": (11, 14),
        "下午": (13, 18),
        "晚上": (18, 22),
        "晚间": (18, 22),
        "全天": (9, 21),
    }
    for keyword, (hour_s, hour_e) in descriptor_map.items():
        if keyword in normalized:
            return {
                "hourS": hour_s,
                "hourE": hour_e,
                "firstHourS": hour_s,
                "lastHourE": hour_e,
            }
    return {}


def _clean_name_token(token: str):
    value = str(token or "").strip().strip("，。；;:：()（）[]【】\"'“”‘’")
    if not value or len(value) > PERSON_NAME_MAX:
        return ""
    if value in TIME_KEYWORDS or re.fullmatch(r"\d+", value):
        return ""
    if any(keyword in value for keyword in ("尽量", "优先", "线下", "线上", "最好", "可以", "参加", "到场", "必须")):
        return ""
    if re.fullmatch(r"周[一二三四五六日天]", value):
        return ""
    if any(word in value for word in ("月", "日", "点", "时", "工作日", "周末")):
        return ""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,15}|[\u4e00-\u9fff]{2,10}", value):
        return ""
    return value


def _extract_names(fragment: str):
    replaced = re.sub(r"[和及与跟/]+", "、", str(fragment or ""))
    names = []
    seen = set()
    for token in re.split(r"[、,，\s]+", replaced):
        name = _clean_name_token(token)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names[:EXPECTED_NAMES_MAX]


def _extract_required_names(text: str):
    required = []
    patterns = [
        r"([A-Za-z\u4e00-\u9fff0-9、，,\s和及与跟/]{1,60})(?:必须到场|必须参加|一定到场|一定参加|务必参加|必须在场|关键成员)",
        r"(?:关键成员|必须到场人员|必须参加的人)[：:\s]*([A-Za-z\u4e00-\u9fff0-9、，,\s和及与跟/]{1,60})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, str(text or "")):
            required.extend(_extract_names(match.group(1)))
    return _normalize_required_names(required)


def _extract_expected_names(text: str, required_names):
    names = list(required_names)
    patterns = [
        r"(?:参与者|参与人|参加人员|名单|邀请|叫上|包括|参会人)[：:\s]*([A-Za-z\u4e00-\u9fff0-9、，,\s和及与跟/]{1,80})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, str(text or "")):
            names.extend(_extract_names(match.group(1)))
    return _dedupe_names(names)


def _extract_event_name(text: str):
    explicit = re.search(r"(?:活动|会议|主题|名称)(?:叫|是|为)?[：:\s\"“”']*([^，。；\n]{2,20})", str(text or ""))
    if explicit:
        return _clean_text(explicit.group(1), SESSION_NAME_MAX)

    action = re.search(r"(?:约|开|安排|组织|发起)([^，。；\n]{2,20})", str(text or ""))
    if action:
        name = re.sub(
            r"^(今天|明天|后天|本周|这周|下周|周[一二三四五六日天]|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\d{1,2}月\d{1,2}日|上午|下午|晚上|晚间|中午|\d{1,2}点(?:到\d{1,2}点)?)+" ,
            "",
            action.group(1),
        )
        return _clean_text(name, SESSION_NAME_MAX)

    candidate = re.search(
        r"([\u4e00-\u9fffA-Za-z0-9]{2,20}(?:聚餐|周会|评审|复盘|讨论|会议|约饭|活动|团建|球赛|培训|课程|面试|见面|出游))",
        str(text or ""),
    )
    if candidate:
        name = re.sub(r"^(今天|明天|后天|本周|这周|下周|周[一二三四五六日天]|上午|下午|晚上|晚间|中午)+", "", candidate.group(1))
        return _clean_text(name, SESSION_NAME_MAX)
    return ""


def _extract_creator_prompt(text: str, required_names):
    clauses = []
    for piece in re.split(r"[，,。；;\n]", str(text or "")):
        clause = piece.strip()
        if not clause:
            continue
        if any(keyword in clause for keyword in ("优先", "尽量", "最好", "允许", "可", "不能", "必须", "务必", "线下", "线上", "迟到", "早退", "连续")):
            clauses.append(clause)
    if not clauses and required_names:
        clauses.append(f"请优先满足关键成员：{'、'.join(required_names)}。")
    return _clean_text("；".join(dict.fromkeys(clauses)), PROMPT_MAX)


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


def _local_session_draft(text: str, defaults: dict):
    base_date = date.today()
    notes = ["当前使用本地规则生成草稿，建议再确认日期和时间。"]
    warnings = []

    required_names = _extract_required_names(text)
    expected_names = _extract_expected_names(text, required_names)
    date_s, date_e = _parse_date_range(text, base_date)
    time_window = _parse_time_range(text, defaults)
    name = _extract_event_name(text)
    creator_prompt = _extract_creator_prompt(text, required_names)

    parsed = {
        "name": name,
        "dateS": date_s.isoformat() if date_s else "",
        "dateE": date_e.isoformat() if date_e else "",
        "creatorPrompt": creator_prompt,
        "expectedNames": expected_names,
        "requiredNames": required_names,
        **time_window,
    }

    if not name:
        warnings.append("活动名称未明确识别，已保留当前输入。")
    if not date_s or not date_e:
        warnings.append("日期未明确识别，已保留当前日期范围。")
    if not time_window:
        warnings.append("时间未明确识别，已保留当前时间范围。")
    if expected_names:
        notes.append(f"已识别 {len(expected_names)} 位参与者：{'、'.join(expected_names)}。")
    if required_names:
        notes.append(f"检测到关键成员：{'、'.join(required_names)}。创建后这些名字会自动按关键成员预设。")

    return _merge_create_draft(defaults, parsed), notes, warnings, "local"


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
        return _local_session_draft(user_text, defaults)

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

    draft, notes, warnings, source = _local_session_draft(user_text, defaults)
    notes.insert(0, "AI 草稿生成暂时不可用，已回退到本地规则。")
    return draft, notes, warnings, source
