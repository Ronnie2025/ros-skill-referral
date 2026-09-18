#!/usr/bin/env python3
"""Minimal skill-referral collector. Python 3 stdlib only."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(os.environ.get("REFERRAL_ROOT", Path(__file__).resolve().parent))
DB_PATH = Path(os.environ.get("REFERRAL_DB", ROOT / "events.db"))
SALT_FILE = Path(os.environ.get("REFERRAL_SALT_FILE", ROOT / "salt"))
HOST = os.environ.get("REFERRAL_HOST", "127.0.0.1")
PORT = int(os.environ.get("REFERRAL_PORT", "8788"))
PUBLIC_DIR = Path(os.environ.get("REFERRAL_PUBLIC", ROOT / "public"))
MAX_BODY = 8192
RATE_LIMIT = 30
RATE_WINDOW = 60
TOKEN_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
ALLOWED_EVENTS = {
    "install_attempt",
    "install_success",
    "setup_success",
    "first_use_success",
}
SUCCESS_EVENTS = {"install_success", "setup_success"}

_lock = threading.Lock()
_db_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_salt() -> str:
    SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SALT_FILE.exists():
        SALT_FILE.write_text(os.urandom(16).hex(), encoding="utf-8")
        try:
            os.chmod(SALT_FILE, 0o600)
        except OSError:
            pass
    return SALT_FILE.read_text(encoding="utf-8").strip() or "referral"


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{load_salt()}|{ip}".encode("utf-8")).hexdigest()[:16]


def db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
          event_id TEXT PRIMARY KEY,
          installation_id TEXT NOT NULL,
          event TEXT NOT NULL,
          referrer TEXT NOT NULL DEFAULT '',
          source_skill TEXT NOT NULL DEFAULT '',
          target_skill TEXT NOT NULL DEFAULT '',
          campaign TEXT NOT NULL DEFAULT '',
          ts TEXT NOT NULL,
          ip_hash TEXT NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_events_install_target ON events(installation_id, target_skill, ts)"
    )
    conn.commit()
    return conn


CONN = db()


def rate_ok(ip: str) -> bool:
    now = time.time()
    with _lock:
        bucket = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(bucket) >= RATE_LIMIT:
            _hits[ip] = bucket
            return False
        bucket.append(now)
        _hits[ip] = bucket
        if len(_hits) > 4000:
            stale = [key for key, times in _hits.items() if not times or now - times[-1] > RATE_WINDOW]
            for key in stale:
                _hits.pop(key, None)
        return True


def clean_token(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not TOKEN_RE.match(value):
        return ""
    return value


def parse_event(raw: bytes) -> dict[str, str]:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("object required")
    event = clean_token(data.get("event"))
    if event not in ALLOWED_EVENTS:
        raise ValueError("unsupported event")
    payload = {
        "event": event,
        "referrer": clean_token(data.get("referrer")),
        "source_skill": clean_token(data.get("source_skill")),
        "target_skill": clean_token(data.get("target_skill")),
        "campaign": clean_token(data.get("campaign")),
        "installation_id": clean_token(data.get("installation_id")),
        "event_id": clean_token(data.get("event_id")),
    }
    if not payload["installation_id"] or not payload["event_id"]:
        raise ValueError("installation_id and event_id required")
    if not payload["target_skill"]:
        raise ValueError("target_skill required")
    return payload


def insert_event(payload: dict[str, str], ip_hash: str) -> None:
    with _db_lock:
        CONN.execute(
            """
            INSERT OR IGNORE INTO events (
              event_id, installation_id, event, referrer, source_skill,
              target_skill, campaign, ts, ip_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["event_id"],
                payload["installation_id"],
                payload["event"],
                payload["referrer"],
                payload["source_skill"],
                payload["target_skill"],
                payload["campaign"],
                utc_now(),
                ip_hash,
            ),
        )
        CONN.commit()


def stats_payload(target_skill: str = "", source_skill: str = "",
                  referrer: str = "", campaign: str = "") -> dict:
    selected = {"target_skill": target_skill, "source_skill": source_skill,
                "referrer": referrer, "campaign": campaign}
    with _db_lock:
        # Attribute globally before applying filters. rowid breaks second-resolution
        # timestamp ties in receipt order, preserving the first successful referral.
        rows = CONN.execute(
            """
            SELECT installation_id, target_skill, event, referrer, source_skill, campaign, ts
            FROM events ORDER BY ts ASC, rowid ASC
            """
        ).fetchall()
    fields = {"target_skill": 1, "referrer": 3, "source_skill": 4, "campaign": 5}

    def matches(row: tuple) -> bool:
        return all(not value or row[fields[field]] == value
                   for field, value in selected.items())

    first: dict[tuple[str, str], tuple] = {}
    used: set[tuple[str, str]] = set()
    last_seen: dict[tuple[str, str], str] = {}
    for row in rows:
        key = (row[0], row[1])
        last_seen[key] = row[6]
        if row[2] in SUCCESS_EVENTS:
            first.setdefault(key, row)
        elif row[2] == "first_use_success":
            used.add(key)
    installs = {key: row for key, row in first.items() if matches(row)}
    by_key: dict[tuple[str, str, str, str], dict] = {}
    for installation, row in installs.items():
        # Group raw values to avoid merging a missing source with a named source.
        key = (row[3], row[4], row[1], row[5])
        entry = by_key.setdefault(key, {
            "referrer": row[3] or "(none)",
            "source_skill": row[4] or "(none)",
            "target_skill": row[1],
            "campaign": row[5],
            "environments": 0,
            "first_use_environments": 0,
            "last_seen": "",
        })
        entry["environments"] += 1
        entry["first_use_environments"] += int(installation in used)
        entry["last_seen"] = max(entry["last_seen"], last_seen[installation])
    breakdown = [entry for key, entry in sorted(
        by_key.items(), key=lambda item: (-item[1]["environments"], item[0])
    )]
    return {
        "metric": "deduped_install_environments",
        "filters": selected,
        "options": {field: sorted({row[index] for row in rows if row[index]})
                    for field, index in fields.items()},
        "note": "收到的安装成功上报，按安装环境标识和目标 Skill 去重，并归于首次成功上报的推荐来源。一人多台电脑或清除本地标识会算多次；无法据此推算独立人数。数据由客户端自行上报，可能漏报或被伪造。",
        "updated_at": utc_now(),
        "totals": {
            "install_environments": len(installs),
            "first_use_environments": len(installs.keys() & used),
            "events": sum(matches(row) for row in rows),
        },
        "by_referrer": breakdown,
    }


def public_file(rel: str) -> Path | None:
    candidate = (PUBLIC_DIR / rel).resolve()
    if PUBLIC_DIR.resolve() not in candidate.parents and candidate != PUBLIC_DIR.resolve():
        return None
    if candidate.is_file():
        return candidate
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "dbskill-referral/0.1"

    def log_message(self, fmt: str, *args) -> None:
        sys_stderr = __import__("sys").stderr
        sys_stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _ip(self) -> str:
        if self.client_address[0] in {"127.0.0.1", "::1"}:
            return self.headers.get("X-Real-IP", "").strip() or self.client_address[0]
        return self.client_address[0]

    def _send(self, status: int, body: bytes, content_type: str, extra: list[tuple[str, str]] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        for key, value in extra or []:
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send(204, b"", "text/plain")

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path in {"/health", "/referral/health"}:
            self._send(200, b'{"ok":true}\n', "application/json; charset=utf-8")
            return
        if path in {"/stats.json", "/referral/stats.json"}:
            query = parse_qs(parsed.query, keep_blank_values=True)
            selected = {}
            for key in ("target_skill", "source_skill", "referrer", "campaign"):
                values = query.get(key, [])
                if len(values) > 1 or (values and not clean_token(values[0])):
                    self._send(400, b'{"error":"invalid filter"}\n', "application/json; charset=utf-8")
                    return
                selected[key] = clean_token(values[0]) if values else ""
            body = json.dumps(stats_payload(**selected), ensure_ascii=False, indent=2).encode("utf-8")
            self._send(200, body + b"\n", "application/json; charset=utf-8")
            return
        if path in {"/", "/referral", "/referral/index.html", "/index.html"}:
            page = public_file("index.html")
            if page is None:
                self._send(500, b'{"error":"dashboard missing"}\n', "application/json; charset=utf-8")
                return
            self._send(200, page.read_bytes(), "text/html; charset=utf-8")
            return
        self._send(404, b'{"error":"not found"}\n', "application/json; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path not in {"/e", "/referral/e"}:
            self._send(404, b'{"error":"not found"}\n', "application/json; charset=utf-8")
            return
        ip = self._ip()
        if not rate_ok(ip):
            self._send(429, b'{"error":"rate limited"}\n', "application/json; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send(413, b'{"error":"payload too large"}\n', "application/json; charset=utf-8")
            return
        raw = self.rfile.read(length)
        try:
            payload = parse_event(raw)
        except (ValueError, json.JSONDecodeError):
            self._send(400, b'{"error":"invalid event"}\n', "application/json; charset=utf-8")
            return
        insert_event(payload, hash_ip(ip))
        self._send(204, b"", "text/plain")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"referral api listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
