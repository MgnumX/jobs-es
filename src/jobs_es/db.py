import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "jobs.db"

_COLS = ("id source title company city province sector url salary_text hourly "
         "housing food direct urgent posted_at first_seen last_seen hourly_est est_src "
         "active canonical_url dedupe_key hourly_low hourly_high eff_hourly score score_src est_conf hours_to_rent").split()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, source TEXT, title TEXT, company TEXT,
    city TEXT DEFAULT '', province TEXT DEFAULT '', sector TEXT DEFAULT '',
    url TEXT UNIQUE, salary_text TEXT DEFAULT '', hourly REAL,
    housing INTEGER DEFAULT 0, food INTEGER DEFAULT 0, direct INTEGER DEFAULT 0,
    urgent INTEGER DEFAULT 0,
    posted_at TEXT DEFAULT '', first_seen TEXT DEFAULT '', last_seen TEXT DEFAULT '',
    hourly_est REAL, est_src TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    canonical_url TEXT,
    dedupe_key TEXT,
    hourly_low REAL, hourly_high REAL,
    eff_hourly REAL, score REAL, score_src TEXT, est_conf REAL, hours_to_rent REAL
);
CREATE INDEX IF NOT EXISTS idx_jobs_sector ON jobs(sector);
"""


def _migrate(con: sqlite3.Connection):
    stmts = [
        "ALTER TABLE jobs ADD COLUMN active INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE jobs ADD COLUMN canonical_url TEXT",
        "ALTER TABLE jobs ADD COLUMN dedupe_key TEXT",
        "ALTER TABLE jobs ADD COLUMN hourly_low REAL",
        "ALTER TABLE jobs ADD COLUMN hourly_high REAL",
        "ALTER TABLE jobs ADD COLUMN eff_hourly REAL",
        "ALTER TABLE jobs ADD COLUMN score REAL",
        "ALTER TABLE jobs ADD COLUMN score_src TEXT",
        "ALTER TABLE jobs ADD COLUMN est_conf REAL",
        "ALTER TABLE jobs ADD COLUMN hours_to_rent REAL",
        # legacy est columns for compat
        "ALTER TABLE jobs ADD COLUMN hourly_est REAL",
        "ALTER TABLE jobs ADD COLUMN est_src TEXT DEFAULT ''",
        "ALTER TABLE jobs ADD COLUMN urgent INTEGER DEFAULT 0",
    ]
    for stmt in stmts:
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise
    try:
        con.executescript("CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(active); CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score);")
    except sqlite3.OperationalError:
        pass
    con.commit()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    _migrate(con)
    return con


def refresh_active(con: sqlite3.Connection, days: int = 14):
    con.execute(
        """
        UPDATE jobs
        SET active = CASE
            WHEN last_seen >= date('now', ?)
            THEN 1 ELSE 0
        END
        """,
        (f"-{days} days",),
    )
    con.commit()


def upsert(con: sqlite3.Connection, row: dict) -> bool:
    """True si es nueva. Actualiza last_seen y enriquece campos vacíos, mantiene active=1."""
    cur = con.execute("SELECT * FROM jobs WHERE id=?", (row["id"],))
    old = cur.fetchone()
    now = __import__("datetime").datetime.now().isoformat(timespec="seconds")
    if not old:
        row = {**row, "first_seen": now, "last_seen": now, "active": 1}
        # ensure all cols present
        con.execute(
            f"INSERT INTO jobs ({','.join(_COLS)}) VALUES ({','.join('?' * len(_COLS))})",
            [row.get(c) for c in _COLS])
        return True
    # merge: rellena huecos que la primera pasada no tuvo (p.ej. salario)
    updates = {}
    for c in _COLS:
        nv = row.get(c)
        if nv and c not in ("id", "first_seen") and not old[c]:
            updates[c] = nv
    updates["last_seen"] = now
    updates["active"] = 1
    if updates:
        sets = ",".join(f"{c}=?" for c in updates)
        con.execute(f"UPDATE jobs SET {sets} WHERE id=?",
                    [*updates.values(), row["id"]])
    return False


def score_rows(con: sqlite3.Connection):
    """Calcula buckets y persiste eff_hourly/score en DB (solo vista, no fuentes)."""
    from .normalize import build_salary_buckets, eff_score
    rows = all_rows(con, only_active=True)
    buckets = build_salary_buckets(rows)
    for r in rows:
        s = eff_score(r, buckets)
        con.execute(
            """
            UPDATE jobs SET eff_hourly=?, score=?, score_src=?, est_conf=?, hours_to_rent=?, hourly_est=?, hourly_low=?, hourly_high=?
            WHERE id=?
            """,
            (s["eff_hourly"], s["score"], s["est_src"], s["est_conf"], s["hours_to_rent"], s["hourly_est"], s.get("hourly_low"), s.get("hourly_high"), r["id"]),
        )
    con.commit()


def all_rows(con: sqlite3.Connection, only_active: bool = False) -> list[dict]:
    if only_active:
        cur = con.execute("SELECT * FROM jobs WHERE active = 1 ORDER BY first_seen DESC")
    else:
        cur = con.execute("SELECT * FROM jobs ORDER BY first_seen DESC")
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def known_ids(con: sqlite3.Connection, ids: set[str]) -> set[str]:
    out = set()
    ids = list(ids)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" * len(chunk))
        out |= {r["id"] for r in con.execute(
            f"SELECT id FROM jobs WHERE id IN ({q})", chunk)}
    return out


def dump_json(rows: list[dict]) -> str:
    return json.dumps(rows, ensure_ascii=False)
