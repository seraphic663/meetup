import os
import sys
import tempfile
import unittest
from pathlib import Path
import importlib


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TMP_DIR = tempfile.mkdtemp(prefix="meetup_test_")
os.environ["DB_PATH"] = str(Path(TMP_DIR) / "sessions_test.db")

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
        participants = data.get("participants", [])
        self.assertEqual(len(participants), 1)
        self.assertEqual(participants[0].get("name"), "Alice")
        self.assertEqual(participants[0].get("remark"), "仅上午可参与")
        self.assertEqual(participants[0].get("avail", {}).get("2026-03-20", {}).get("9"), 1)


if __name__ == "__main__":
    unittest.main()
