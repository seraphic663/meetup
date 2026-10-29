"""SQLite storage helpers for meetup sessions."""
from __future__ import annotations

import os
import sqlite3
import time


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(MODULE_DIR)
DB_PATH = os.environ.get("DB_PATH", os.path.join(ROOT_DIR, "sessions", "sessions.db"))
DB_USES_URI = DB_PATH.startswith("file:")
KEEPALIVE_DB = None
STORAGE_FORMAT_VERSION = 1


def _prepare_connection(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    return _prepare_connection(sqlite3.connect(DB_PATH, uri=DB_USES_URI))


def _create_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            name TEXT NOT NULL,
            date_s TEXT NOT NULL,
            date_e TEXT NOT NULL,
            hour_s INTEGER NOT NULL,
            hour_e INTEGER NOT NULL,
            first_hour_s INTEGER NOT NULL,
            last_hour_e INTEGER NOT NULL,
            creator_name TEXT NOT NULL DEFAULT '',
            creator_token_hash TEXT NOT NULL DEFAULT '',
            creator_prompt TEXT NOT NULL DEFAULT '',
            created_ts INTEGER NOT NULL,
            updated_ts INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS session_expected_names (
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (session_id, name),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS session_required_names (
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            position INTEGER NOT NULL,
            PRIMARY KEY (session_id, name),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            remark TEXT NOT NULL DEFAULT '',
            is_required INTEGER NOT NULL DEFAULT 0,
            token_hash TEXT NOT NULL DEFAULT '',
            created_ts INTEGER NOT NULL,
            updated_ts INTEGER NOT NULL,
            UNIQUE (session_id, name),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS time_intervals (
            session_id TEXT NOT NULL,
            participant_id TEXT NOT NULL,
            id TEXT NOT NULL,
            slot_date TEXT NOT NULL,
            start_minute INTEGER NOT NULL,
            end_minute INTEGER NOT NULL,
            type TEXT NOT NULL CHECK (type IN ('busy', 'preferred')),
            note TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (participant_id) REFERENCES participants(id) ON DELETE CASCADE,
            PRIMARY KEY (participant_id, id),
            CHECK (start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute)
        );

        CREATE INDEX IF NOT EXISTS idx_expected_names_session
            ON session_expected_names(session_id, position);
        CREATE INDEX IF NOT EXISTS idx_required_names_session
            ON session_required_names(session_id, position);
        CREATE INDEX IF NOT EXISTS idx_participants_session
            ON participants(session_id);
        CREATE INDEX IF NOT EXISTS idx_time_intervals_session
            ON time_intervals(session_id, participant_id, slot_date, start_minute);
        """
    )


def _migrate_reset_old_scheduling_data(db: sqlite3.Connection) -> None:
    """Reset old schedule data once before the interval model becomes authoritative."""
    version = int(db.execute("PRAGMA user_version").fetchone()[0])
    if version >= STORAGE_FORMAT_VERSION:
        return

    for table in (
        "time_intervals",
        "availability",
        "participants",
        "session_required_names",
        "session_expected_names",
        "sessions",
    ):
        db.execute(f"DROP TABLE IF EXISTS {table}")
    db.execute(f"PRAGMA user_version = {STORAGE_FORMAT_VERSION}")


def init_db():
    global KEEPALIVE_DB

    if DB_USES_URI and "mode=memory" in DB_PATH:
        if KEEPALIVE_DB is None:
            KEEPALIVE_DB = _prepare_connection(sqlite3.connect(DB_PATH, uri=True))
        db = KEEPALIVE_DB
    else:
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        db = get_db()

    _migrate_reset_old_scheduling_data(db)
    _create_tables(db)
    db.commit()

    if db is not KEEPALIVE_DB:
        db.close()


def _read_names(db: sqlite3.Connection, table: str, sid: str):
    rows = db.execute(
        f"SELECT name FROM {table} WHERE session_id=? ORDER BY position ASC, name ASC",
        (sid,),
    ).fetchall()
    return [row["name"] for row in rows]


def load_session(sid: str):
    with get_db() as db:
        session_row = db.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not session_row:
            return None
        expected_names = _read_names(db, "session_expected_names", sid)
        stored_required_names = _read_names(db, "session_required_names", sid)

        participants_rows = db.execute(
            """
            SELECT id, name, color, remark, is_required, token_hash
            FROM participants
            WHERE session_id=?
            ORDER BY created_ts ASC, name ASC
            """,
            (sid,),
        ).fetchall()
        interval_rows = db.execute(
            """
            SELECT id, participant_id, slot_date, start_minute, end_minute, type, note
            FROM time_intervals
            WHERE session_id=?
            ORDER BY participant_id ASC, slot_date ASC, start_minute ASC, end_minute ASC
            """,
            (sid,),
        ).fetchall()
        intervals_by_participant = {}
        for row in interval_rows:
            intervals_by_participant.setdefault(row["participant_id"], []).append(
                {
                    "id": row["id"],
                    "date": row["slot_date"],
                    "startMinute": int(row["start_minute"]),
                    "endMinute": int(row["end_minute"]),
                    "type": row["type"],
                    "note": row["note"] or "",
                }
            )

        participants = []
        joined_required_names = []
        for row in participants_rows:
            participant = {
                "id": row["id"],
                "name": row["name"],
                "color": row["color"],
                "intervals": intervals_by_participant.get(row["id"], []),
                "remark": row["remark"] or "",
                "isRequired": bool(row["is_required"]),
            }
            token_hash = row["token_hash"] or ""
            if token_hash:
                participant["tokenHash"] = token_hash
            if participant["isRequired"]:
                joined_required_names.append(participant["name"])
            participants.append(participant)

    merged_required_names = []
    seen_required = set()
    for name in [*stored_required_names, *joined_required_names]:
        if not name or name in seen_required:
            continue
        seen_required.add(name)
        merged_required_names.append(name)

    payload = {
        "id": session_row["id"],
        "schemaVersion": int(session_row["schema_version"]),
        "name": session_row["name"],
        "dateS": session_row["date_s"],
        "dateE": session_row["date_e"],
        "hourS": int(session_row["hour_s"]),
        "hourE": int(session_row["hour_e"]),
        "firstHourS": int(session_row["first_hour_s"]),
        "lastHourE": int(session_row["last_hour_e"]),
        "creatorPrompt": session_row["creator_prompt"] or "",
        "expectedNames": expected_names,
        "requiredNames": merged_required_names,
        "participants": participants,
    }

    if session_row["creator_name"] or session_row["creator_token_hash"]:
        payload["creator"] = {}
        if session_row["creator_name"]:
            payload["creator"]["name"] = session_row["creator_name"]
        if session_row["creator_token_hash"]:
            payload["creator"]["tokenHash"] = session_row["creator_token_hash"]

    return payload


def save_session(sid: str, payload: dict) -> None:
    now = int(time.time())
    creator = payload.get("creator")
    if not isinstance(creator, dict):
        creator = {}
    with get_db() as db:
        existing_session = db.execute(
            "SELECT created_ts FROM sessions WHERE id=?",
            (sid,),
        ).fetchone()
        existing_participants = {
            row["id"]: row["created_ts"]
            for row in db.execute(
                "SELECT id, created_ts FROM participants WHERE session_id=?",
                (sid,),
            ).fetchall()
        }

        db.execute(
            """
            INSERT INTO sessions (
                id, schema_version, name, date_s, date_e, hour_s, hour_e,
                first_hour_s, last_hour_e, creator_name, creator_token_hash,
                creator_prompt, created_ts, updated_ts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                schema_version=excluded.schema_version,
                name=excluded.name,
                date_s=excluded.date_s,
                date_e=excluded.date_e,
                hour_s=excluded.hour_s,
                hour_e=excluded.hour_e,
                first_hour_s=excluded.first_hour_s,
                last_hour_e=excluded.last_hour_e,
                creator_name=excluded.creator_name,
                creator_token_hash=excluded.creator_token_hash,
                creator_prompt=excluded.creator_prompt,
                updated_ts=excluded.updated_ts
            """,
            (
                sid,
                int(payload.get("schemaVersion") or 1),
                payload.get("name", ""),
                payload.get("dateS", ""),
                payload.get("dateE", ""),
                int(payload.get("hourS", 9)),
                int(payload.get("hourE", 21)),
                int(payload.get("firstHourS", payload.get("hourS", 9))),
                int(payload.get("lastHourE", payload.get("hourE", 21))),
                creator.get("name", ""),
                creator.get("tokenHash", ""),
                payload.get("creatorPrompt", ""),
                int(existing_session["created_ts"]) if existing_session else now,
                now,
            ),
        )

        db.execute("DELETE FROM session_expected_names WHERE session_id=?", (sid,))
        db.executemany(
            "INSERT INTO session_expected_names(session_id, name, position) VALUES(?,?,?)",
            [
                (sid, name, index)
                for index, name in enumerate(payload.get("expectedNames", []))
            ],
        )

        db.execute("DELETE FROM session_required_names WHERE session_id=?", (sid,))
        db.executemany(
            "INSERT INTO session_required_names(session_id, name, position) VALUES(?,?,?)",
            [
                (sid, name, index)
                for index, name in enumerate(payload.get("requiredNames", []))
            ],
        )

        participant_rows = []
        participant_ids = set()
        for participant in payload.get("participants", []):
            participant_id = participant.get("id", "")
            participant_ids.add(participant_id)
            participant_created_ts = existing_participants.get(participant_id, now)
            participant_rows.append(
                (
                    participant_id,
                    sid,
                    participant.get("name", ""),
                    participant.get("color", "#FF6B35"),
                    participant.get("remark", ""),
                    1 if participant.get("isRequired") else 0,
                    participant.get("tokenHash", ""),
                    participant_created_ts,
                    now,
                )
            )
        removed_ids = set(existing_participants) - participant_ids
        if removed_ids:
            db.executemany("DELETE FROM participants WHERE id=? AND session_id=?", [(pid, sid) for pid in removed_ids])

        if participant_rows:
            db.execute(
                "UPDATE participants SET name='__sync__' || id WHERE session_id=?",
                (sid,),
            )

        for row in participant_rows:
            db.execute(
                """
                INSERT INTO participants(
                    id, session_id, name, color, remark, is_required,
                    token_hash, created_ts, updated_ts
                ) VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    session_id=excluded.session_id,
                    name=excluded.name,
                    color=excluded.color,
                    remark=excluded.remark,
                    is_required=excluded.is_required,
                    token_hash=excluded.token_hash,
                    updated_ts=excluded.updated_ts
                """,
                row,
            )
        db.commit()


def replace_participant_intervals(sid: str, participant_id: str, intervals: list[dict]) -> None:
    with get_db() as db:
        db.execute("DELETE FROM time_intervals WHERE session_id=? AND participant_id=?", (sid, participant_id))
        if intervals:
            db.executemany(
                """
                INSERT INTO time_intervals(
                    session_id, participant_id, id, slot_date, start_minute, end_minute, type, note
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                [
                    (
                        sid, participant_id, item["id"], item["date"], item["startMinute"],
                        item["endMinute"], item["type"], item.get("note", ""),
                    )
                    for item in intervals
                ],
            )
        db.commit()


def prune_intervals_to_session_windows(sid: str, windows: dict[str, tuple[int, int]]) -> None:
    with get_db() as db:
        if windows:
            placeholders = ",".join("?" for _ in windows)
            db.execute(
                f"DELETE FROM time_intervals WHERE session_id=? AND slot_date NOT IN ({placeholders})",
                (sid, *windows.keys()),
            )
            db.executemany(
                """DELETE FROM time_intervals
                   WHERE session_id=? AND slot_date=? AND (start_minute<? OR end_minute>?)""",
                [(sid, date, start, end) for date, (start, end) in windows.items()],
            )
        else:
            db.execute("DELETE FROM time_intervals WHERE session_id=?", (sid,))
        db.commit()


def update_participant_remark(sid: str, participant_id: str, remark: str) -> None:
    with get_db() as db:
        db.execute(
            "UPDATE participants SET remark=?, updated_ts=? WHERE session_id=? AND id=?",
            (remark, int(time.time()), sid, participant_id),
        )
        db.commit()


def delete_session(sid: str) -> None:
    with get_db() as db:
        db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        db.commit()


init_db()
