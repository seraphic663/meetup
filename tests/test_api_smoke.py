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

        resp = self.client.get(f"/api/session/{sid}/summary")
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
                "creatorPrompt": "只看周五上午",
                "expectedNames": ["Alice", "Carol"],
                "participants": [
                    {"id": alice["participantId"], "name": "Alice-改名", "color": "#00AAFF"},
                    {"name": "Carol", "color": "#22CC88"},
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        session = resp.get_json().get("session", {})
        self.assertEqual(session.get("name"), "改后周会")
        self.assertEqual(session.get("dateE"), "2026-03-20")
        self.assertEqual(session.get("hourS"), 10)
        self.assertEqual(session.get("expectedNames"), ["Alice", "Carol"])
        participants = session.get("participants", [])
        self.assertEqual(len(participants), 2)
        renamed = next(item for item in participants if item["id"] == alice["participantId"])
        self.assertEqual(renamed["name"], "Alice-改名")
        self.assertEqual(renamed["remark"], "上午都行")
        self.assertEqual(renamed["avail"], {"2026-03-20": {"10": 1, "11": 1}})

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

    def test_10_legacy_session_can_delete_without_creator_token(self):
        sid = "legacy01"
        server._save(
            sid,
            {
                "id": sid,
                "name": "旧会话",
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
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get("ok"), True)
        self.assertEqual(resp.get_json().get("legacy"), True)
        self.assertIsNone(server._load(sid))


if __name__ == "__main__":
    unittest.main()
