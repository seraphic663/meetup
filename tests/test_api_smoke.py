import os
import sys
import unittest
from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["DB_PATH"] = "file:meetup_test?mode=memory&cache=shared"

server = importlib.import_module("server")


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
            "creatorPrompt": "请尽量优先选择线下可参加时段",
            "expectedNames": ["Alice", "Bob"],
        }
        resp = self.client.post("/api/session", json=payload)
        self.assertEqual(resp.status_code, 200)
        sid = resp.get_json().get("id")
        self.assertTrue(sid)
        return sid

    def test_01_create_session(self):
        sid = self._create_session()
        self.assertEqual(len(sid), 8)

    def test_02_join_session(self):
        sid = self._create_session()
        resp = self.client.post(f"/api/session/{sid}/join", json={"name": "Alice", "color": "#00AAFF"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        names = [p["name"] for p in data.get("participants", [])]
        self.assertIn("Alice", names)

    def test_03_update_avail_and_remark(self):
        sid = self._create_session()
        self.client.post(f"/api/session/{sid}/join", json={"name": "Alice", "color": "#00AAFF"})
        resp = self.client.put(
            f"/api/session/{sid}/avail",
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1, "10": 2}},
                "remark": "10点后可参会",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json().get("ok"), True)

    def test_04_read_session(self):
        sid = self._create_session()
        self.client.post(f"/api/session/{sid}/join", json={"name": "Alice", "color": "#00AAFF"})
        self.client.put(
            f"/api/session/{sid}/avail",
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1}},
                "remark": "仅上午可参与",
            },
        )

        resp = self.client.get(f"/api/session/{sid}")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("id"), sid)
        self.assertEqual(data.get("creatorPrompt"), "请尽量优先选择线下可参加时段")
        participants = data.get("participants", [])
        self.assertEqual(len(participants), 1)
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
        self.assertEqual(data.get("error"), "invalid payload")
        self.assertTrue(data.get("details"))

    def test_06_summary_falls_back_without_api_key(self):
        sid = self._create_session()
        self.client.post(f"/api/session/{sid}/join", json={"name": "Alice", "color": "#00AAFF"})
        self.client.post(f"/api/session/{sid}/join", json={"name": "Bob", "color": "#22CC88"})
        self.client.put(
            f"/api/session/{sid}/avail",
            json={
                "name": "Alice",
                "avail": {"2026-03-20": {"9": 1, "10": 1}},
                "remark": "上午优先",
            },
        )
        self.client.put(
            f"/api/session/{sid}/avail",
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


if __name__ == "__main__":
    unittest.main()
