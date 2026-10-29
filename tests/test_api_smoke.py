import os
import sqlite3
import sys
import unittest
from pathlib import Path
import importlib
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DB_PATH"] = "file:meetup_test?mode=memory&cache=shared"

server = importlib.import_module("backend.server")
create_draft = importlib.import_module("backend.create_draft")


class TestApiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = server.app.test_client()

    def setUp(self):
        with server.get_db() as db:
            db.execute("DELETE FROM sessions")
            db.commit()

    def _create_session(self):
        payload = {
            "name": "周会",
            "dateS": "2026-03-20",
            "dateE": "2026-03-21",
            "hourS": 9,
            "hourE": 12,
            "creatorName": "Host",
            "creatorPrompt": "请尽量优先选择线下可参加时段",
            "expectedNames": ["Alice", "Bob"],
        }
        resp = self.client.post("/api/session", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        sid = data.get("id")
        self.assertTrue(sid)
        self.assertTrue(data.get("creatorToken"))
        return sid, data.get("creatorToken")

    def _join_session(self, sid, name, color, headers=None):
        resp = self.client.post(
            f"/api/session/{sid}/join",
            json={"name": name, "color": color},
            headers=headers or {},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("participantId"))
        self.assertTrue(data.get("participantToken"))
        return data

    def _save_intervals(self, sid, participant, intervals):
        return self.client.put(
            f"/api/session/{sid}/intervals",
            headers={"X-Participant-Token": participant["participantToken"]},
            json={"intervals": intervals},
        )

    def _save_remark(self, sid, participant, remark):
        return self.client.put(
            f"/api/session/{sid}/remark",
            headers={"X-Participant-Token": participant["participantToken"]},
            json={"remark": remark},
        )

    def test_01_create_session(self):
        sid, creator_token = self._create_session()
        self.assertEqual(len(sid), 8)
        self.assertTrue(creator_token)

    def test_02_join_session(self):
        sid, _ = self._create_session()
        data = self._join_session(sid, "Alice", "#00AAFF")
        names = [p["name"] for p in data.get("session", {}).get("participants", [])]
        self.assertIn("Alice", names)

    def test_03_update_intervals_and_remark(self):
        sid, _ = self._create_session()
        joined = self._join_session(sid, "Alice", "#00AAFF")
        unauthenticated = self.client.put(
            f"/api/session/{sid}/intervals", json={"intervals": []}
        )
        self.assertEqual(unauthenticated.status_code, 403)

        overlapping = self._save_intervals(sid, joined, [
            {"id": "busy", "date": "2026-03-20", "startMinute": 540, "endMinute": 630, "type": "busy"},
            {"id": "preferred", "date": "2026-03-20", "startMinute": 600, "endMinute": 660, "type": "preferred"},
        ])
        self.assertEqual(overlapping.status_code, 400)

        saved = self._save_intervals(sid, joined, [
            {"id": "busy", "date": "2026-03-20", "startMinute": 540, "endMinute": 600, "type": "busy"},
            {"id": "preferred", "date": "2026-03-20", "startMinute": 600, "endMinute": 660, "type": "preferred", "note": "10点后方便"},
        ])
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json().get("ok"), True)
        remark = self._save_remark(sid, joined, "通常上午不便")
        self.assertEqual(remark.status_code, 200)
        self.assertEqual(remark.get_json().get("remark"), "通常上午不便")

    def test_04_read_session(self):
        sid, creator_token = self._create_session()
        joined = self._join_session(sid, "Alice", "#00AAFF")
        self._save_intervals(sid, joined, [
            {"id": "morning", "date": "2026-03-20", "startMinute": 540, "endMinute": 600, "type": "preferred"},
        ])
        self._save_remark(sid, joined, "通常上午比较方便")

        resp = self.client.get(
            f"/api/session/{sid}",
            headers={
                "X-Creator-Token": creator_token,
                "X-Participant-Token": joined["participantToken"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("id"), sid)
        self.assertEqual(data.get("creatorPrompt"), "请尽量优先选择线下可参加时段")
        self.assertEqual(data.get("creatorName"), "Host")
        self.assertEqual(data.get("firstHourS"), 9)
        self.assertEqual(data.get("lastHourE"), 12)
        self.assertEqual(data.get("viewer", {}).get("isCreator"), True)
        participants = data.get("participants", [])
        self.assertEqual(len(participants), 1)
        self.assertTrue(participants[0].get("id"))
        self.assertEqual(participants[0].get("name"), "Alice")
        self.assertEqual(participants[0].get("remark"), "通常上午比较方便")
        self.assertEqual(participants[0].get("intervals"), [
            {"id": "morning", "date": "2026-03-20", "startMinute": 540, "endMinute": 600, "type": "preferred", "note": ""},
        ])

    def test_05_invalid_create_payload(self):
        resp = self.client.post(
            "/api/session",
            json={
                "name": "",
                "dateS": "2026-03-23",
                "dateE": "2026-03-20",
                "hourS": 18,
                "hourE": 10,
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error", {}).get("code"), "invalid_payload")
        self.assertEqual(data.get("error", {}).get("message"), "请求参数不合法")
        self.assertTrue(data.get("error", {}).get("details"))
        self.assertTrue(data.get("request_id"))

    def test_06_summary_falls_back_without_api_key(self):
        sid, _ = self._create_session()
        alice = self._join_session(sid, "Alice", "#00AAFF")
        bob = self._join_session(sid, "Bob", "#22CC88")
        self._save_intervals(sid, alice, [
            {"id": "alice-pref", "date": "2026-03-20", "startMinute": 540, "endMinute": 660, "type": "preferred"},
        ])
        self._save_remark(sid, alice, "上午优先")
        self._save_intervals(sid, bob, [
            {"id": "bob-busy", "date": "2026-03-20", "startMinute": 540, "endMinute": 600, "type": "busy"},
            {"id": "bob-pref", "date": "2026-03-20", "startMinute": 600, "endMinute": 660, "type": "preferred"},
        ])

        previous_key = server.DEEPSEEK_API_KEY
        setattr(server, "DEEPSEEK_API_KEY", "")
        try:
            resp = self.client.get(f"/api/session/{sid}/summary")
        finally:
            setattr(server, "DEEPSEEK_API_KEY", previous_key)
        self.assertEqual(resp.status_code, 200)
        summary = resp.get_json().get("summary", "")
        self.assertIn("## 推荐时段", summary)
        self.assertIn("## 协调建议", summary)
        self.assertIn("Alice", summary)

    def test_07_request_id_header_present(self):
        resp = self.client.get("/healthz", headers={"X-Request-Id": "test-request-id"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Request-Id"), "test-request-id")

    def test_08_creator_can_update_session(self):
        sid, creator_token = self._create_session()
        alice = self._join_session(sid, "Alice", "#00AAFF")
        self._save_intervals(sid, alice, [
            {"id": "outside-new-window", "date": "2026-03-20", "startMinute": 600, "endMinute": 630, "type": "busy"},
            {"id": "alice-pref", "date": "2026-03-20", "startMinute": 660, "endMinute": 720, "type": "preferred"},
        ])
        self._save_remark(sid, alice, "上午都行")

        resp = self.client.patch(
            f"/api/session/{sid}",
            headers={"X-Creator-Token": creator_token},
            json={
                "name": "改后周会",
                "dateS": "2026-03-20",
                "dateE": "2026-03-20",
                "hourS": 10,
                "hourE": 12,
                "firstHourS": 11,
                "lastHourE": 12,
                "creatorPrompt": "只看周五上午",
                "expectedNames": ["Alice", "Carol"],
                "participants": [
                    {"id": alice["participantId"], "name": "Alice-改名", "color": "#00AAFF", "isRequired": True},
                    {"name": "Carol", "color": "#22CC88"},
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        session = resp.get_json().get("session", {})
        self.assertEqual(session.get("name"), "改后周会")
        self.assertEqual(session.get("dateE"), "2026-03-20")
        self.assertEqual(session.get("hourS"), 10)
        self.assertEqual(session.get("firstHourS"), 11)
        self.assertEqual(session.get("lastHourE"), 12)
        self.assertEqual(session.get("expectedNames"), ["Alice", "Carol"])
        participants = session.get("participants", [])
        self.assertEqual(len(participants), 2)
        renamed = next(item for item in participants if item["id"] == alice["participantId"])
        self.assertEqual(renamed["name"], "Alice-改名")
        self.assertEqual(renamed["isRequired"], True)
        self.assertEqual(renamed["remark"], "上午都行")
        self.assertEqual(renamed["intervals"], [
            {"id": "alice-pref", "date": "2026-03-20", "startMinute": 660, "endMinute": 720, "type": "preferred", "note": ""},
        ])

    def test_09_participant_can_leave_but_cannot_delete_session(self):
        sid, creator_token = self._create_session()
        alice = self._join_session(sid, "Alice", "#00AAFF")

        leave_resp = self.client.delete(
            f"/api/session/{sid}/participants/{alice['participantId']}",
            headers={"X-Participant-Token": alice["participantToken"]},
        )
        self.assertEqual(leave_resp.status_code, 200)
        self.assertEqual(leave_resp.get_json().get("ok"), True)

        delete_resp = self.client.delete(
            f"/api/session/{sid}",
            headers={"X-Participant-Token": alice["participantToken"]},
        )
        self.assertEqual(delete_resp.status_code, 403)

        creator_delete_resp = self.client.delete(
            f"/api/session/{sid}",
            headers={"X-Creator-Token": creator_token},
        )
        self.assertEqual(creator_delete_resp.status_code, 200)
        self.assertEqual(creator_delete_resp.get_json().get("ok"), True)

    def test_10_session_without_creator_token_cannot_delete_openly(self):
        sid = "oldopen01"
        server._save(
            sid,
            {
                "id": sid,
                "name": "无创建者令牌会话",
                "dateS": "2026-03-20",
                "dateE": "2026-03-20",
                "hourS": 9,
                "hourE": 12,
                "creatorPrompt": "",
                "expectedNames": [],
                "participants": [],
            },
        )

        resp = self.client.delete(f"/api/session/{sid}")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.get_json().get("error", {}).get("code"), "creator_auth_required")
        self.assertIsNotNone(server._load(sid))

    def test_11_truncated_range_validates_intervals(self):
        resp = self.client.post(
            "/api/session",
            json={
                "name": "跨天讨论",
                "dateS": "2026-03-20",
                "dateE": "2026-03-22",
                "hourS": 10,
                "hourE": 22,
                "firstHourS": 14,
                "lastHourE": 20,
                "creatorName": "Host",
                "creatorPrompt": "",
                "expectedNames": [],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        sid = data["id"]
        alice = self._join_session(sid, "Alice", "#00AAFF")

        outside_window = self._save_intervals(sid, alice, [
            {"id": "day-1-outside-start", "date": "2026-03-20", "startMinute": 600, "endMinute": 630, "type": "preferred"},
        ])
        self.assertEqual(outside_window.status_code, 400)
        outside_last_day = self._save_intervals(sid, alice, [
            {"id": "day-3-outside-end", "date": "2026-03-22", "startMinute": 1200, "endMinute": 1260, "type": "preferred"},
        ])
        self.assertEqual(outside_last_day.status_code, 400)

        save_resp = self._save_intervals(sid, alice, [
            {"id": "day-1-valid", "date": "2026-03-20", "startMinute": 840, "endMinute": 900, "type": "preferred"},
            {"id": "day-2-start", "date": "2026-03-21", "startMinute": 600, "endMinute": 660, "type": "preferred"},
            {"id": "day-2-end", "date": "2026-03-21", "startMinute": 1260, "endMinute": 1320, "type": "busy"},
            {"id": "day-3-valid", "date": "2026-03-22", "startMinute": 600, "endMinute": 660, "type": "preferred"},
            {"id": "day-3-end", "date": "2026-03-22", "startMinute": 1140, "endMinute": 1200, "type": "busy"},
        ])
        self.assertEqual(save_resp.status_code, 200)

        read_resp = self.client.get(
            f"/api/session/{sid}",
            headers={"X-Participant-Token": alice["participantToken"]},
        )
        self.assertEqual(read_resp.status_code, 200)
        session = read_resp.get_json()
        self.assertEqual(session.get("firstHourS"), 14)
        self.assertEqual(session.get("lastHourE"), 20)
        participant = session.get("participants", [])[0]
        self.assertEqual(participant.get("intervals"), [
            {"id": "day-1-valid", "date": "2026-03-20", "startMinute": 840, "endMinute": 900, "type": "preferred", "note": ""},
            {"id": "day-2-start", "date": "2026-03-21", "startMinute": 600, "endMinute": 660, "type": "preferred", "note": ""},
            {"id": "day-2-end", "date": "2026-03-21", "startMinute": 1260, "endMinute": 1320, "type": "busy", "note": ""},
            {"id": "day-3-valid", "date": "2026-03-22", "startMinute": 600, "endMinute": 660, "type": "preferred", "note": ""},
            {"id": "day-3-end", "date": "2026-03-22", "startMinute": 1140, "endMinute": 1200, "type": "busy", "note": ""},
        ])

    def test_12_invalid_same_day_truncation_rejected(self):
        resp = self.client.post(
            "/api/session",
            json={
                "name": "同日无效",
                "dateS": "2026-03-20",
                "dateE": "2026-03-20",
                "hourS": 10,
                "hourE": 22,
                "firstHourS": 18,
                "lastHourE": 18,
                "creatorName": "Host",
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data.get("error", {}).get("code"), "invalid_payload")
        self.assertTrue(any("同一天" in item for item in data.get("error", {}).get("details", [])))

    def test_13_required_participants_affect_summary(self):
        sid, creator_token = self._create_session()
        alice = self._join_session(sid, "Alice", "#00AAFF")
        bob = self._join_session(sid, "Bob", "#22CC88")

        patch_resp = self.client.patch(
            f"/api/session/{sid}",
            headers={"X-Creator-Token": creator_token},
            json={
                "participants": [
                    {"id": alice["participantId"], "name": "Alice", "color": "#00AAFF", "isRequired": True},
                    {"id": bob["participantId"], "name": "Bob", "color": "#22CC88", "isRequired": False},
                ],
            },
        )
        self.assertEqual(patch_resp.status_code, 200)

        self._save_intervals(sid, alice, [
            {"id": "alice-busy", "date": "2026-03-20", "startMinute": 540, "endMinute": 600, "type": "busy"},
            {"id": "alice-pref", "date": "2026-03-20", "startMinute": 600, "endMinute": 660, "type": "preferred"},
        ])
        self._save_intervals(sid, bob, [
            {"id": "bob-pref", "date": "2026-03-20", "startMinute": 540, "endMinute": 660, "type": "preferred"},
        ])

        previous_key = server.DEEPSEEK_API_KEY
        setattr(server, "DEEPSEEK_API_KEY", "")
        try:
            summary_resp = self.client.get(f"/api/session/{sid}/summary")
        finally:
            setattr(server, "DEEPSEEK_API_KEY", previous_key)

        self.assertEqual(summary_resp.status_code, 200)
        summary = summary_resp.get_json().get("summary", "")
        self.assertIn("## 关键成员约束", summary)
        self.assertIn("Alice", summary)
        self.assertIn("不方便", summary)

    def test_14_create_draft_fallback_returns_defaults_without_local_nlp(self):
        previous_key = server.DEEPSEEK_API_KEY
        setattr(server, "DEEPSEEK_API_KEY", "")
        try:
            resp = self.client.post(
                "/api/session/draft",
                json={
                    "text": "2026-04-14到2026-04-16晚上7点到9点约产品评审，Alice和Bob必须到场，参与者包括Alice、Bob、Carol，尽量线下。",
                    "defaults": {
                        "name": "当前活动",
                        "dateS": "2026-04-20",
                        "dateE": "2026-04-21",
                        "hourS": 10,
                        "hourE": 18,
                        "creatorName": "Host",
                        "expectedNames": ["Alice"],
                        "requiredNames": ["Alice"],
                    },
                },
            )
        finally:
            setattr(server, "DEEPSEEK_API_KEY", previous_key)

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        draft = data.get("draft", {})
        self.assertEqual(data.get("source"), "local")
        self.assertEqual(draft.get("name"), "当前活动")
        self.assertEqual(draft.get("dateS"), "2026-04-20")
        self.assertEqual(draft.get("dateE"), "2026-04-21")
        self.assertEqual(draft.get("hourS"), 10)
        self.assertEqual(draft.get("hourE"), 18)
        self.assertEqual(draft.get("requiredNames"), ["Alice"])
        self.assertEqual(draft.get("expectedNames"), ["Alice"])
        self.assertTrue(data.get("warnings"))

    def test_15_required_names_auto_apply_when_participant_joins(self):
        previous_key = server.DEEPSEEK_API_KEY
        setattr(server, "DEEPSEEK_API_KEY", "")
        try:
            draft_resp = self.client.post(
                "/api/session/draft",
                json={
                    "text": "Alice和Bob必须到场。",
                    "defaults": {
                        "name": "产品评审",
                        "dateS": "2026-04-14",
                        "dateE": "2026-04-16",
                        "hourS": 19,
                        "hourE": 21,
                        "creatorName": "Host",
                        "expectedNames": ["Alice", "Bob", "Carol"],
                        "requiredNames": ["Alice", "Bob"],
                    },
                },
            )
        finally:
            setattr(server, "DEEPSEEK_API_KEY", previous_key)
        self.assertEqual(draft_resp.status_code, 200)
        draft = draft_resp.get_json().get("draft", {})

        create_resp = self.client.post(
            "/api/session",
            json={
                **draft,
                "creatorName": "Host",
            },
        )
        self.assertEqual(create_resp.status_code, 200)
        sid = create_resp.get_json()["id"]

        alice = self._join_session(sid, "Alice", "#00AAFF")
        session = alice.get("session", {})
        participant = next(item for item in session.get("participants", []) if item["name"] == "Alice")
        self.assertEqual(session.get("requiredNames"), ["Alice", "Bob"])
        self.assertEqual(participant.get("isRequired"), True)

    def test_16_delete_session_cascades_storage_rows(self):
        sid, creator_token = self._create_session()
        alice = self._join_session(sid, "Alice", "#00AAFF")
        self._save_intervals(sid, alice, [
            {"id": "busy", "date": "2026-03-20", "startMinute": 540, "endMinute": 600, "type": "busy"},
            {"id": "pref", "date": "2026-03-20", "startMinute": 600, "endMinute": 660, "type": "preferred", "note": "刚好接上"},
        ])
        self._save_remark(sid, alice, "早上不便")

        with server.get_db() as db:
            session_count = db.execute("SELECT COUNT(*) AS c FROM sessions WHERE id=?", (sid,)).fetchone()["c"]
            participant_count = db.execute("SELECT COUNT(*) AS c FROM participants WHERE session_id=?", (sid,)).fetchone()["c"]
            interval_count = db.execute("SELECT COUNT(*) AS c FROM time_intervals WHERE session_id=?", (sid,)).fetchone()["c"]

        self.assertEqual(session_count, 1)
        self.assertEqual(participant_count, 1)
        self.assertEqual(interval_count, 2)

        delete_resp = self.client.delete(
            f"/api/session/{sid}",
            headers={"X-Creator-Token": creator_token},
        )
        self.assertEqual(delete_resp.status_code, 200)

        with server.get_db() as db:
            session_count = db.execute("SELECT COUNT(*) AS c FROM sessions WHERE id=?", (sid,)).fetchone()["c"]
            expected_count = db.execute("SELECT COUNT(*) AS c FROM session_expected_names WHERE session_id=?", (sid,)).fetchone()["c"]
            participant_count = db.execute("SELECT COUNT(*) AS c FROM participants WHERE session_id=?", (sid,)).fetchone()["c"]
            interval_count = db.execute("SELECT COUNT(*) AS c FROM time_intervals WHERE session_id=?", (sid,)).fetchone()["c"]

        self.assertEqual(session_count, 0)
        self.assertEqual(expected_count, 0)
        self.assertEqual(participant_count, 0)
        self.assertEqual(interval_count, 0)

    def test_17_summary_request_disables_thinking_mode(self):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
        previous_key = server.DEEPSEEK_API_KEY
        try:
            server.DEEPSEEK_API_KEY = "x" * 8
            with patch.object(server.requests, "post", return_value=response) as request:
                result = server._deepseek_chat("测试", temperature=0.4, max_tokens=500)
        finally:
            server.DEEPSEEK_API_KEY = previous_key

        self.assertEqual(result, "OK")
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload.get("model"), server.DEEPSEEK_MODEL)
        self.assertEqual(payload.get("thinking"), {"type": "disabled"})

    def test_18_create_draft_request_disables_thinking_mode(self):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
        with patch.object(create_draft.requests, "post", return_value=response) as request:
            result = create_draft._call_deepseek(
                "测试",
                "x" * 8,
                "https://api.deepseek.com/v1/chat/completions",
                "deepseek-v4-flash",
            )

        self.assertEqual(result, "{}")
        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload.get("model"), "deepseek-v4-flash")
        self.assertEqual(payload.get("thinking"), {"type": "disabled"})

    def test_19_legacy_server_module_exports_app(self):
        legacy_server = importlib.import_module("server")
        self.assertIs(legacy_server.app, server.app)

    def test_20_storage_migration_resets_old_data_once(self):
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        for table in ("sessions", "participants", "session_expected_names", "session_required_names", "availability", "time_intervals"):
            db.execute(f"CREATE TABLE {table}(id TEXT PRIMARY KEY)")
            db.execute(f"INSERT INTO {table}(id) VALUES(?)", (table,))

        server.storage._migrate_reset_old_scheduling_data(db)
        server.storage._create_tables(db)
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], server.storage.STORAGE_FORMAT_VERSION)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn("availability", tables)
        self.assertIn("time_intervals", tables)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)

        now = 1
        db.execute(
            """INSERT INTO sessions(
                id, schema_version, name, date_s, date_e, hour_s, hour_e,
                first_hour_s, last_hour_e, creator_name, creator_token_hash,
                creator_prompt, created_ts, updated_ts
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("new-session", 4, "新表", "2026-03-20", "2026-03-20", 9, 12, 9, 12, "", "", "", now, now),
        )
        server.storage._migrate_reset_old_scheduling_data(db)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions WHERE id='new-session'").fetchone()[0], 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
