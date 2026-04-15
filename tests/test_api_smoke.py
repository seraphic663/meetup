import os
import sys
import unittest
from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DB_PATH"] = "file:meetup_test?mode=memory&cache=shared"

server = importlib.import_module("backend.server")


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

    def test_01_create_session(self):
        sid, creator_token = self._create_session()
        self.assertEqual(len(sid), 8)
        self.assertTrue(creator_token)

    def test_02_join_session(self):
        sid, _ = self._create_session()
        data = self._join_session(sid, "Alice", "#00AAFF")
        names = [p["name"] for p in data.get("session", {}).get("participants", [])]
        self.assertIn("Alice", names)

    def test_03_update_avail_and_remark(self):
        sid, _ = self._create_session()
        joined = self._join_session(sid, "Alice", "#00AAFF")
        resp = self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": joined["participantToken"]},
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1, "10": 2}},
                "remark": "10点后可参会",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get("ok"), True)

    def test_04_read_session(self):
        sid, creator_token = self._create_session()
        joined = self._join_session(sid, "Alice", "#00AAFF")
        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": joined["participantToken"]},
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1}},
                "remark": "仅上午可参与",
            },
        )

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
        self.assertEqual(participants[0].get("remark"), "仅上午可参与")
        self.assertEqual(participants[0].get("avail", {}).get("2026-03-20", {}).get("9"), 1)

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
        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": alice["participantToken"]},
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1, "10": 1}},
                "remark": "上午优先",
            },
        )
        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": bob["participantToken"]},
            json={
                "name": "Bob",
                "avail": {"2026-03-20": {"9": 2, "10": 1}},
                "remark": "",
            },
        )

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
        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": alice["participantToken"]},
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1, "10": 1, "11": 1}},
                "remark": "上午都行",
            },
        )

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
        self.assertEqual(renamed["avail"], {"2026-03-20": {"11": 1}})

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

    def test_11_truncated_range_blocks_invalid_slots(self):
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

        save_resp = self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": alice["participantToken"]},
            json={
                "name": "Alice",
                "avail": {
                    "2026-03-20": {"10": 1, "14": 1, "21": 2},
                    "2026-03-21": {"10": 1, "21": 1},
                    "2026-03-22": {"10": 1, "19": 2, "20": 1},
                },
            },
        )
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
        self.assertEqual(
            participant.get("avail"),
            {
                "2026-03-20": {"14": 1, "21": 2},
                "2026-03-21": {"10": 1, "21": 1},
                "2026-03-22": {"10": 1, "19": 2},
            },
        )

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

        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": alice["participantToken"]},
            json={"name": "Alice", "avail": {"2026-03-20": {"9": 2, "10": 1}}},
        )
        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": bob["participantToken"]},
            json={"name": "Bob", "avail": {"2026-03-20": {"9": 1, "10": 1}}},
        )

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
        self.assertIn("关键成员冲突", summary)

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
        self.client.put(
            f"/api/session/{sid}/avail",
            headers={"X-Participant-Token": alice["participantToken"]},
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1, "10": 2}},
                "remark": "测试级联删除",
            },
        )

        with server.get_db() as db:
            session_count = db.execute("SELECT COUNT(*) AS c FROM sessions WHERE id=?", (sid,)).fetchone()["c"]
            participant_count = db.execute("SELECT COUNT(*) AS c FROM participants WHERE session_id=?", (sid,)).fetchone()["c"]
            availability_count = db.execute("SELECT COUNT(*) AS c FROM availability WHERE session_id=?", (sid,)).fetchone()["c"]

        self.assertEqual(session_count, 1)
        self.assertEqual(participant_count, 1)
        self.assertEqual(availability_count, 2)

        delete_resp = self.client.delete(
            f"/api/session/{sid}",
            headers={"X-Creator-Token": creator_token},
        )
        self.assertEqual(delete_resp.status_code, 200)

        with server.get_db() as db:
            session_count = db.execute("SELECT COUNT(*) AS c FROM sessions WHERE id=?", (sid,)).fetchone()["c"]
            expected_count = db.execute("SELECT COUNT(*) AS c FROM session_expected_names WHERE session_id=?", (sid,)).fetchone()["c"]
            participant_count = db.execute("SELECT COUNT(*) AS c FROM participants WHERE session_id=?", (sid,)).fetchone()["c"]
            availability_count = db.execute("SELECT COUNT(*) AS c FROM availability WHERE session_id=?", (sid,)).fetchone()["c"]

        self.assertEqual(session_count, 0)
        self.assertEqual(expected_count, 0)
        self.assertEqual(participant_count, 0)
        self.assertEqual(availability_count, 0)


if __name__ == "__main__":
    unittest.main()
