"""SQLite persistence for web-intel runs and monitors, in the orchestrator's flood_app.db."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from app.intel.evidence import FailedSource, FailureReason, RunState, WebIntelRun

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ACTIVE = (RunState.queued.value, RunState.running.value)
_USABLE = (RunState.succeeded.value, RunState.partial.value)


def default_db_path() -> str:
    return os.getenv("AEGIS_APP_DB") or os.path.join(_BACKEND_ROOT, "flood_app.db")


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class IntelStore:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or default_db_path()
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with closing(self._connect()) as conn, conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS web_intel_runs (
                    run_id TEXT PRIMARY KEY,
                    request_key TEXT,
                    status TEXT NOT NULL,
                    location TEXT,
                    district TEXT,
                    state TEXT,
                    lat REAL,
                    lon REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    run_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_web_intel_runs_district ON web_intel_runs (district);
                CREATE INDEX IF NOT EXISTS idx_web_intel_runs_state ON web_intel_runs (state);
                CREATE INDEX IF NOT EXISTS idx_web_intel_runs_created ON web_intel_runs (created_at);
                CREATE INDEX IF NOT EXISTS idx_web_intel_runs_status ON web_intel_runs (status);
                CREATE TABLE IF NOT EXISTS web_intel_monitors (
                    monitor_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    source_id TEXT,
                    district TEXT,
                    state TEXT,
                    latitude REAL,
                    longitude REAL,
                    products TEXT NOT NULL,
                    baseline_hash TEXT,
                    created_at TEXT NOT NULL,
                    monitor_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS web_intel_webhook_events (
                    event_key TEXT PRIMARY KEY,
                    received_at TEXT NOT NULL
                );
                """
            )

    # runs

    def save_run(self, run: WebIntelRun, request_key: str | None = None) -> None:
        stored = run.model_copy(update={"live_view": None})
        loc = stored.location
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT INTO web_intel_runs (run_id, request_key, status, location, district, state, lat, lon,
                                            created_at, updated_at, run_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET status=excluded.status, updated_at=excluded.updated_at,
                    run_json=excluded.run_json
                """,
                (
                    stored.run_id, request_key, stored.state.value, loc.query,
                    (loc.district or "").lower() or None, loc.jurisdiction, loc.latitude, loc.longitude,
                    _utc(stored.created_at), _utc(datetime.now(timezone.utc)), stored.model_dump_json(),
                ),
            )

    def get_run(self, run_id: str) -> WebIntelRun | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT run_json FROM web_intel_runs WHERE run_id = ?", (run_id,)).fetchone()
        return WebIntelRun.model_validate_json(row["run_json"]) if row else None

    def mark_interrupted(self) -> int:
        """Runs left queued/running by a previous process cannot resume: fail them."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"SELECT run_json FROM web_intel_runs WHERE status IN ({','.join('?' * len(_ACTIVE))})", _ACTIVE
            ).fetchall()
        now = datetime.now(timezone.utc)
        for row in rows:
            run = WebIntelRun.model_validate_json(row["run_json"])
            failed = run.model_copy(update={
                "state": RunState.failed,
                "finished_at": now,
                "error": "interrupted: the server restarted while this run was in flight",
                "failed_sources": run.failed_sources + [FailedSource(
                    source_id="aegis_runner", reason=FailureReason.interrupted,
                    detail="process restarted before completion")],
                "sources_failed": run.sources_failed + 1,
            })
            self.save_run(failed)
        return len(rows)

    def latest_for(
        self,
        *,
        district: str | None = None,
        state: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        max_age: timedelta = timedelta(hours=6),
        include_stale: bool = False,
    ) -> WebIntelRun | None:
        """Most recent usable run for a place. With include_stale, ignores max_age."""
        clauses = [f"status IN ({','.join('?' * len(_USABLE))})"]
        params: list = list(_USABLE)
        if not include_stale:
            clauses.append("created_at >= ?")
            params.append(_utc(datetime.now(timezone.utc) - max_age))
        if district:
            clauses.append("district = ?")
            params.append(district.strip().lower())
        elif state:
            clauses.append("state = ?")
            params.append(state)
        elif lat is not None and lon is not None:
            clauses.append("ABS(lat - ?) <= 0.5 AND ABS(lon - ?) <= 0.5")
            params.extend([lat, lon])
        else:
            return None
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"SELECT run_json FROM web_intel_runs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT 1",
                params,
            ).fetchone()
        return WebIntelRun.model_validate_json(row["run_json"]) if row else None

    # monitors

    def save_monitor(self, record: dict) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO web_intel_monitors (monitor_id, kind, target, source_id, district, state,
                    latitude, longitude, products, baseline_hash, created_at, monitor_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["monitor_id"], record["kind"], record["target"], record.get("source_id"),
                    record.get("district"), record.get("state"), record["latitude"], record["longitude"],
                    json.dumps(record["products"]), record.get("baseline_hash"), record["created_at"],
                    json.dumps(record),
                ),
            )

    def get_monitor(self, monitor_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT monitor_json, baseline_hash FROM web_intel_monitors WHERE monitor_id = ?",
                               (monitor_id,)).fetchone()
        if not row:
            return None
        record = json.loads(row["monitor_json"])
        record["baseline_hash"] = row["baseline_hash"]
        return record

    def list_monitors(self) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT monitor_json, baseline_hash FROM web_intel_monitors ORDER BY created_at DESC").fetchall()
        return [{**json.loads(r["monitor_json"]), "baseline_hash": r["baseline_hash"]} for r in rows]

    def set_monitor_baseline(self, monitor_id: str, baseline_hash: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("UPDATE web_intel_monitors SET baseline_hash = ? WHERE monitor_id = ?",
                         (baseline_hash, monitor_id))

    def delete_monitor(self, monitor_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cur = conn.execute("DELETE FROM web_intel_monitors WHERE monitor_id = ?", (monitor_id,))
        return cur.rowcount > 0

    def record_webhook_event(self, event_key: str) -> bool:
        """True the first time an event key is seen; False for a duplicate delivery."""
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO web_intel_webhook_events (event_key, received_at) VALUES (?, ?)",
                (event_key, _utc(datetime.now(timezone.utc))),
            )
        return cur.rowcount == 1

    def forget_webhook_event(self, event_key: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM web_intel_webhook_events WHERE event_key = ?", (event_key,))
