"""Tiny persistent store (SQLite) that backs the mock enterprise systems."""
import json, sqlite3, threading
from contextlib import closing
from core.common import RUNTIME

DB = RUNTIME / "systems.db"
_lock = threading.Lock()


def _c():
    c = sqlite3.connect(DB, timeout=15)
    c.execute("CREATE TABLE IF NOT EXISTS records(col TEXT, key TEXT, body TEXT, PRIMARY KEY(col,key))")
    return c


def put(col, key, obj):
    with _lock, closing(_c()) as c:
        c.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (col, key, json.dumps(obj, ensure_ascii=False)))
        c.commit()


def get(col, key):
    with _lock, closing(_c()) as c:
        r = c.execute("SELECT body FROM records WHERE col=? AND key=?", (col, key)).fetchone()
    return json.loads(r[0]) if r else None


def rows(col):
    with _lock, closing(_c()) as c:
        return [json.loads(b) for (b,) in c.execute("SELECT body FROM records WHERE col=? ORDER BY key", (col,))]


def count(col):
    with _lock, closing(_c()) as c:
        return c.execute("SELECT COUNT(*) FROM records WHERE col=?", (col,)).fetchone()[0]


def clear_all():
    with _lock, closing(_c()) as c:
        c.execute("DELETE FROM records")
        c.commit()
