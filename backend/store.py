import hashlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone

DATA = Path(os.environ.get("CCO_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))


def connection():
    DATA.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA / "archive.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS versions (
      id INTEGER PRIMARY KEY, day TEXT NOT NULL, code TEXT NOT NULL,
      family TEXT NOT NULL, filename TEXT NOT NULL, digest TEXT NOT NULL,
      source TEXT NOT NULL, saved_at TEXT NOT NULL, payload TEXT, error TEXT,
      UNIQUE(day, code, family, digest))""")
    return db


def save(day, code, raw, filename, source, payload=None, error=None, family="official"):
    digest = hashlib.sha256(raw).hexdigest()
    originals = DATA / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    target = originals / digest
    if not target.exists():
        target.write_bytes(raw)
    with connection() as db:
        found = db.execute("SELECT id FROM versions WHERE day=? AND code=? AND family=? AND digest=?", (day, code, family, digest)).fetchone()
        if found:
            # Permit re-parsing a previously unsupported original after adding an adapter.
            if payload:
                db.execute("UPDATE versions SET payload=?,error=NULL WHERE id=?", (json.dumps(payload), found[0]))
            return found[0], False
        cursor = db.execute("INSERT INTO versions(day,code,family,filename,digest,source,saved_at,payload,error) VALUES(?,?,?,?,?,?,?,?,?)", (day, code, family, Path(filename).name, digest, source, datetime.now(timezone.utc).isoformat(), json.dumps(payload) if payload else None, error))
        return cursor.lastrowid, True


def all_versions(day=None, family=None):
    where, args = [], []
    for name, value in (("day", day), ("family", family)):
        if value:
            where.append(name + "=?")
            args.append(value)
    with connection() as db:
        rows = db.execute("SELECT * FROM versions" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC", args).fetchall()
    results = []
    latest = set()
    for row in rows:
        item = dict(row)
        payload = json.loads(item.pop("payload")) if row["payload"] else None
        identity = (item["day"], item["family"], item["code"])
        item.update(ready=payload is not None, asset_count=len(payload["assets"]) if payload else 0, warnings=payload["warnings"] if payload else [], current=identity not in latest)
        latest.add(identity)
        results.append(item)
    return results


def get_version(identifier):
    with connection() as db:
        row = db.execute("SELECT * FROM versions WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise ValueError("Versión no encontrada.")
    item = dict(row)
    item["payload"] = json.loads(item["payload"]) if item["payload"] else None
    return item


def latest(day, code, family):
    with connection() as db:
        row = db.execute("SELECT id FROM versions WHERE day=? AND code=? AND family=? ORDER BY id DESC LIMIT 1", (day, code, family)).fetchone()
    return get_version(row[0]) if row else None
