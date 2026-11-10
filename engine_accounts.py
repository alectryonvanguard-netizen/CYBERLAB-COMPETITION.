"""
.engine accounts and reporting store (SQLite, standard library only).

Mother server: customers, their small servers ("nodes"), daily usage, storage,
uptime, private messages and an audit log.
Any engine also keeps its own local daily usage here (node id "local").
"""
import os
import re
import json
import time
import math
import hmac
import hashlib
import secrets
import sqlite3
import threading
import datetime

from engine_infra import password_checks, hash_password, ITERATIONS

HEARTBEAT_SECONDS = 60
BEATS_PER_DAY = 86400 // HEARTBEAT_SECONDS
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SITE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,38}$")
MB = 1024 * 1024


def day_str(ts=None):
    return time.strftime("%Y-%m-%d", time.localtime(ts if ts is not None else time.time()))


def _days_back(n):
    today = datetime.date.today()
    return [(today - datetime.timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _months_back(n):
    today = datetime.date.today().replace(day=1)
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self._pending = {}
        self._schema()
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # ------------------------------------------------------------ plumbing
    def q(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def x(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def _schema(self):
        stmts = [
            """CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL, hash TEXT NOT NULL, iterations INTEGER NOT NULL,
                email TEXT DEFAULT '', quota_mb INTEGER DEFAULT 1024, max_nodes INTEGER DEFAULT 1,
                status TEXT DEFAULT 'active', created REAL, last_login REAL)""",
            """CREATE TABLE IF NOT EXISTS nodes(
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT, token_hash TEXT UNIQUE,
                created REAL, last_seen REAL, version TEXT, remote_ip TEXT, entries INTEGER DEFAULT 0,
                storage_bytes INTEGER DEFAULT 0, cpu REAL, mem REAL, disk REAL, sites_json TEXT DEFAULT '[]')""",
            """CREATE TABLE IF NOT EXISTS usage_daily(
                day TEXT, node_id TEXT, site TEXT, requests INTEGER DEFAULT 0, bytes INTEGER DEFAULT 0,
                PRIMARY KEY(day, node_id, site))""",
            """CREATE TABLE IF NOT EXISTS storage_daily(
                day TEXT, node_id TEXT, bytes INTEGER, PRIMARY KEY(day, node_id))""",
            """CREATE TABLE IF NOT EXISTS beats_daily(
                day TEXT, node_id TEXT, beats INTEGER, PRIMARY KEY(day, node_id))""",
            """CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, subject TEXT, body TEXT,
                kind TEXT DEFAULT 'info', created REAL, read INTEGER DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS audit(
                id INTEGER PRIMARY KEY, ts REAL, actor TEXT, action TEXT, detail TEXT, ip TEXT)""",
            """CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)""",
        ]
        for s in stmts:
            self.x(s)

    # ------------------------------------------------------------ settings
    def get_setting(self, key, default=None):
        rows = self.q("SELECT v FROM settings WHERE k=?", (key,))
        if not rows:
            return default
        try:
            return json.loads(rows[0][0])
        except Exception:
            return default

    def set_setting(self, key, value):
        self.x("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
               (key, json.dumps(value)))

    # --------------------------------------------------------------- audit
    def audit(self, actor, action, detail="", ip=""):
        self.x("INSERT INTO audit(ts,actor,action,detail,ip) VALUES(?,?,?,?,?)",
               (time.time(), actor, action, str(detail)[:500], ip))
        self.x("DELETE FROM audit WHERE id <= (SELECT MAX(id) FROM audit) - 20000")

    def audit_tail(self, limit=200):
        rows = self.q("SELECT ts,actor,action,detail,ip FROM audit ORDER BY id DESC LIMIT ?", (limit,))
        return [{"ts": r[0], "actor": r[1], "action": r[2], "detail": r[3], "ip": r[4]} for r in rows]

    # --------------------------------------------------------------- users
    def create_user(self, username, password, email="", quota_mb=1024, max_nodes=1):
        username = (username or "").strip().lower()
        if not USERNAME_RE.match(username):
            return None, "Username: 3-32 characters, letters, numbers, . _ -"
        missing = [t for t, ok in password_checks(password or "") if not ok]
        if missing:
            return None, "Password still needs: " + "; ".join(missing)
        salt = secrets.token_hex(16)
        try:
            cur = self.x("INSERT INTO users(username,salt,hash,iterations,email,quota_mb,max_nodes,created)"
                         " VALUES(?,?,?,?,?,?,?,?)",
                         (username, salt, hash_password(password, salt, ITERATIONS), ITERATIONS,
                          (email or "")[:120], int(quota_mb), int(max_nodes), time.time()))
        except sqlite3.IntegrityError:
            return None, "That username is already taken."
        return cur.lastrowid, ""

    def _user_row(self, row):
        keys = ("id", "username", "email", "quota_mb", "max_nodes", "status", "created", "last_login")
        return dict(zip(keys, row)) if row else None

    _USER_COLS = "id,username,email,quota_mb,max_nodes,status,created,last_login"

    def get_user(self, uid):
        rows = self.q(f"SELECT {self._USER_COLS} FROM users WHERE id=?", (uid,))
        return self._user_row(rows[0]) if rows else None

    def verify_user(self, username, password):
        rows = self.q("SELECT id,salt,hash,iterations,status FROM users WHERE username=?",
                      ((username or "").strip().lower(),))
        if not rows:
            hash_password(password or "", "00" * 16)  # keep timing similar
            return None, "Wrong username or password."
        uid, salt, h, iters, status = rows[0]
        if not hmac.compare_digest(hash_password(password or "", salt, iters), h):
            return None, "Wrong username or password."
        if status != "active":
            return None, "This account is suspended. Contact your provider."
        self.x("UPDATE users SET last_login=? WHERE id=?", (time.time(), uid))
        return self.get_user(uid), ""

    def set_password(self, uid, new_password):
        missing = [t for t, ok in password_checks(new_password or "") if not ok]
        if missing:
            return False, "Password still needs: " + "; ".join(missing)
        salt = secrets.token_hex(16)
        self.x("UPDATE users SET salt=?, hash=?, iterations=? WHERE id=?",
               (salt, hash_password(new_password, salt, ITERATIONS), ITERATIONS, uid))
        return True, ""

    def update_user(self, uid, **fields):
        allowed = {"email", "quota_mb", "max_nodes", "status"}
        sets, args = [], []
        for k, v in fields.items():
            if k not in allowed:
                continue
            if k == "status" and v not in ("active", "suspended"):
                continue
            if k in ("quota_mb", "max_nodes"):
                v = max(0, int(v))
            sets.append(f"{k}=?")
            args.append(v)
        if sets:
            self.x(f"UPDATE users SET {', '.join(sets)} WHERE id=?", (*args, uid))

    def delete_user(self, uid):
        for (nid,) in self.q("SELECT id FROM nodes WHERE user_id=?", (uid,)):
            self.delete_node(nid)
        self.x("DELETE FROM messages WHERE user_id=?", (uid,))
        self.x("DELETE FROM users WHERE id=?", (uid,))

    def user_storage(self, uid):
        rows = self.q("SELECT COALESCE(SUM(storage_bytes),0) FROM nodes WHERE user_id=?", (uid,))
        return int(rows[0][0])

    def list_users(self):
        out = []
        for r in self.q(f"SELECT {self._USER_COLS} FROM users ORDER BY username"):
            u = self._user_row(r)
            nodes = self.q("SELECT COUNT(*), MAX(last_seen) FROM nodes WHERE user_id=?", (u["id"],))[0]
            u["nodes"], u["last_seen"] = nodes[0], nodes[1]
            u["storage_bytes"] = self.user_storage(u["id"])
            u["unread"] = self.unread_count(u["id"])
            out.append(u)
        return out

    # --------------------------------------------------------------- nodes
    def create_node(self, user_id, name):
        user = self.get_user(user_id)
        if not user:
            return None, None, "No such customer."
        count = self.q("SELECT COUNT(*) FROM nodes WHERE user_id=?", (user_id,))[0][0]
        if count >= user["max_nodes"]:
            return None, None, f"This customer may have {user['max_nodes']} server(s) at most."
        node_id = secrets.token_hex(8)
        token = "eng_" + secrets.token_urlsafe(24)
        self.x("INSERT INTO nodes(id,user_id,name,token_hash,created) VALUES(?,?,?,?,?)",
               (node_id, user_id, (name or "server")[:60], token_hash(token), time.time()))
        return node_id, token, ""

    def reset_node_token(self, node_id):
        token = "eng_" + secrets.token_urlsafe(24)
        cur = self.x("UPDATE nodes SET token_hash=? WHERE id=?", (token_hash(token), node_id))
        return token if cur.rowcount else None

    def delete_node(self, node_id):
        for t in ("usage_daily", "storage_daily", "beats_daily"):
            self.x(f"DELETE FROM {t} WHERE node_id=?", (node_id,))
        self.x("DELETE FROM nodes WHERE id=?", (node_id,))

    _NODE_COLS = ("id,user_id,name,created,last_seen,version,remote_ip,entries,"
                  "storage_bytes,cpu,mem,disk,sites_json")

    def _node_row(self, r):
        keys = self._NODE_COLS.split(",")
        n = dict(zip(keys, r))
        try:
            n["sites"] = json.loads(n.pop("sites_json") or "[]")
        except Exception:
            n["sites"] = []
        n["online"] = bool(n["last_seen"] and time.time() - n["last_seen"] < HEARTBEAT_SECONDS * 3)
        return n

    def list_nodes(self, user_id=None):
        if user_id is None:
            rows = self.q(f"SELECT {self._NODE_COLS} FROM nodes ORDER BY name")
        else:
            rows = self.q(f"SELECT {self._NODE_COLS} FROM nodes WHERE user_id=? ORDER BY name", (user_id,))
        return [self._node_row(r) for r in rows]

    def get_node(self, node_id):
        rows = self.q(f"SELECT {self._NODE_COLS} FROM nodes WHERE id=?", (node_id,))
        return self._node_row(rows[0]) if rows else None

    def node_by_token(self, token):
        if not token:
            return None
        rows = self.q(f"SELECT {self._NODE_COLS} FROM nodes WHERE token_hash=?", (token_hash(token),))
        return self._node_row(rows[0]) if rows else None

    # ----------------------------------------------------------- heartbeat
    def heartbeat(self, node, payload, ip=""):
        now = time.time()
        today = day_str(now)
        metrics = payload.get("metrics") or {}
        sites = payload.get("sites") or []
        storage = int(payload.get("storage_bytes") or 0)
        self.x("UPDATE nodes SET last_seen=?, version=?, remote_ip=?, entries=?, storage_bytes=?,"
               " cpu=?, mem=?, disk=?, sites_json=? WHERE id=?",
               (now, str(payload.get("version", ""))[:20], ip, int(payload.get("entries") or len(sites)),
                storage, metrics.get("cpu"), metrics.get("mem"), metrics.get("disk"),
                json.dumps(sites[:300]), node["id"]))
        with self.lock:
            for r in (payload.get("usage") or [])[:3000]:
                day, site = str(r.get("day", "")), str(r.get("site", ""))
                if not DAY_RE.match(day) or not SITE_RE.match(site):
                    continue
                self.x("INSERT INTO usage_daily(day,node_id,site,requests,bytes) VALUES(?,?,?,?,?)"
                       " ON CONFLICT(day,node_id,site) DO UPDATE SET requests=excluded.requests,"
                       " bytes=excluded.bytes",
                       (day, node["id"], site, max(0, int(r.get("requests", 0))),
                        max(0, int(r.get("bytes", 0)))))
            self.x("INSERT INTO storage_daily(day,node_id,bytes) VALUES(?,?,?)"
                   " ON CONFLICT(day,node_id) DO UPDATE SET bytes=excluded.bytes",
                   (today, node["id"], storage))
            self.x("INSERT INTO beats_daily(day,node_id,beats) VALUES(?,?,1)"
                   " ON CONFLICT(day,node_id) DO UPDATE SET beats=beats+1", (today, node["id"]))

        user = self.get_user(node["user_id"]) or {}
        used = self.user_storage(node["user_id"])
        quota = int(user.get("quota_mb", 0)) * MB
        after = int(payload.get("last_message_id") or 0)
        msgs = self.inbox(node["user_id"], limit=30, after_id=after)
        return {"ok": True, "quota_bytes": quota, "storage_bytes": used,
                "over_quota": bool(quota and used > quota),
                "suspended": user.get("status") != "active",
                "messages": msgs, "server_time": now}

    # --------------------------------------------------------- local usage
    def add_usage(self, site, requests=1, nbytes=0):
        """Counts traffic in memory; flush_usage() writes it out."""
        key = (day_str(), site)
        with self.lock:
            cur = self._pending.setdefault(key, [0, 0])
            cur[0] += requests
            cur[1] += nbytes

    def flush_usage(self):
        with self.lock:
            pending, self._pending = self._pending, {}
            for (day, site), (req, nbytes) in pending.items():
                self.x("INSERT INTO usage_daily(day,node_id,site,requests,bytes) VALUES(?,'local',?,?,?)"
                       " ON CONFLICT(day,node_id,site) DO UPDATE SET requests=requests+excluded.requests,"
                       " bytes=bytes+excluded.bytes", (day, site, req, nbytes))

    def local_rows(self, days=2):
        start = _days_back(days)[0]
        rows = self.q("SELECT day,site,requests,bytes FROM usage_daily WHERE node_id='local' AND day>=?",
                      (start,))
        return [{"day": r[0], "site": r[1], "requests": r[2], "bytes": r[3]} for r in rows]

    # ------------------------------------------------------------ reports
    def _scope(self, user_id, node_id):
        """(sql fragment, args) limiting rows to a node, a customer's nodes, or all remote nodes."""
        if node_id is not None:
            return "node_id=?", [node_id]
        if user_id is not None:
            ids = [r[0] for r in self.q("SELECT id FROM nodes WHERE user_id=?", (user_id,))]
            if not ids:
                return "0", []
            return "node_id IN (%s)" % ",".join("?" * len(ids)), ids
        return "node_id!='local'", []

    def usage_series(self, period, user_id=None, node_id=None):
        where, args = self._scope(user_id, node_id)
        if period == "year":
            labels = _months_back(12)
            rows = self.q(f"SELECT substr(day,1,7), SUM(requests), SUM(bytes) FROM usage_daily"
                          f" WHERE {where} AND substr(day,1,7)>=? GROUP BY 1", (*args, labels[0]))
        else:
            labels = _days_back(30 if period == "month" else 7)
            rows = self.q(f"SELECT day, SUM(requests), SUM(bytes) FROM usage_daily"
                          f" WHERE {where} AND day>=? GROUP BY 1", (*args, labels[0]))
        data = {r[0]: (r[1] or 0, r[2] or 0) for r in rows}
        return {"labels": labels,
                "requests": [data.get(l, (0, 0))[0] for l in labels],
                "bytes": [data.get(l, (0, 0))[1] for l in labels]}

    def report(self, period="week", user_id=None, node_id=None):
        period = period if period in ("week", "month", "year") else "week"
        series = self.usage_series(period, user_id, node_id)
        where, args = self._scope(user_id, node_id)
        today = datetime.date.today()
        span = {"week": 7, "month": 30, "year": 365}[period]
        start = (today - datetime.timedelta(days=span - 1)).isoformat()
        prev_start = (today - datetime.timedelta(days=2 * span - 1)).isoformat()
        prev = self.q(f"SELECT COALESCE(SUM(requests),0), COALESCE(SUM(bytes),0) FROM usage_daily"
                      f" WHERE {where} AND day>=? AND day<?", (*args, prev_start, start))[0]
        total_req, total_bytes = sum(series["requests"]), sum(series["bytes"])
        change = None
        if prev[0] > 0:
            change = round(100.0 * (total_req - prev[0]) / prev[0], 1)
        top = self.q(f"SELECT site, SUM(requests), SUM(bytes) FROM usage_daily WHERE {where} AND day>=?"
                     f" GROUP BY site ORDER BY SUM(requests) DESC LIMIT 10", (*args, start))

        # storage + uptime
        if node_id is not None:
            node_list = [self.get_node(node_id)]
        elif user_id is not None:
            node_list = self.list_nodes(user_id)
        else:
            node_list = [n for n in self.list_nodes()]
        node_list = [n for n in node_list if n]
        storage_now = sum(n["storage_bytes"] or 0 for n in node_list)
        uptimes = []
        for n in node_list:
            active_days = min(span, max(1, math.ceil((time.time() - (n["created"] or time.time())) / 86400)))
            beats = self.q("SELECT COALESCE(SUM(beats),0) FROM beats_daily WHERE node_id=? AND day>=?",
                           (n["id"], start))[0][0]
            uptimes.append(min(100.0, 100.0 * beats / (active_days * BEATS_PER_DAY)))
        sdays = _days_back(30)
        if node_list:
            ids = [n["id"] for n in node_list]
            srows = self.q("SELECT day, SUM(bytes) FROM storage_daily WHERE node_id IN (%s) AND day>=?"
                           " GROUP BY day" % ",".join("?" * len(ids)), (*ids, sdays[0]))
        else:
            srows = []
        sdata = {r[0]: r[1] for r in srows}
        quota = None
        if user_id is not None:
            u = self.get_user(user_id)
            quota = (u["quota_mb"] * MB) if u else None
        return {
            "period": period,
            "series": series,
            "totals": {"requests": total_req, "bytes": total_bytes, "change_pct": change},
            "top_sites": [{"site": r[0], "requests": r[1] or 0, "bytes": r[2] or 0} for r in top],
            "storage": {"used": storage_now, "quota": quota,
                        "history": {"labels": sdays, "bytes": [sdata.get(d, 0) for d in sdays]}},
            "uptime_pct": round(sum(uptimes) / len(uptimes), 2) if uptimes else None,
            "nodes": len(node_list),
            "nodes_online": sum(1 for n in node_list if n["online"]),
        }

    def heat(self, user_id=None, node_id=None, days=140):
        where, args = self._scope(user_id, node_id)
        start = _days_back(days)[0]
        rows = self.q(f"SELECT day, SUM(requests) FROM usage_daily WHERE {where} AND day>=? GROUP BY day",
                      (*args, start))
        return {"days": _days_back(days), "requests": {r[0]: r[1] or 0 for r in rows}}

    def local_report(self, period="week"):
        return self.report(period, node_id="local")

    def local_heat(self, days=140):
        return self.heat(node_id="local", days=days)

    # ------------------------------------------------------------ messages
    def send_message(self, user_id, subject, body, kind="info"):
        if not self.get_user(user_id):
            return None
        cur = self.x("INSERT INTO messages(user_id,subject,body,kind,created) VALUES(?,?,?,?,?)",
                     (user_id, (subject or "")[:120], (body or "")[:4000],
                      kind if kind in ("info", "warning", "billing") else "info", time.time()))
        return cur.lastrowid

    def broadcast(self, subject, body, kind="info"):
        n = 0
        for (uid,) in self.q("SELECT id FROM users WHERE status='active'"):
            if self.send_message(uid, subject, body, kind):
                n += 1
        return n

    def inbox(self, user_id, limit=50, after_id=0):
        rows = self.q("SELECT id,subject,body,kind,created,read FROM messages"
                      " WHERE user_id=? AND id>? ORDER BY id DESC LIMIT ?", (user_id, after_id, limit))
        return [{"id": r[0], "subject": r[1], "body": r[2], "kind": r[3], "created": r[4],
                 "read": bool(r[5])} for r in rows]

    def unread_count(self, user_id):
        return self.q("SELECT COUNT(*) FROM messages WHERE user_id=? AND read=0", (user_id,))[0][0]

    def mark_read(self, user_id, ids):
        for i in ids[:200]:
            self.x("UPDATE messages SET read=1 WHERE id=? AND user_id=?", (int(i), user_id))

    def sent_messages(self, limit=100):
        rows = self.q("SELECT m.id,u.username,m.subject,m.body,m.kind,m.created,m.read FROM messages m"
                      " JOIN users u ON u.id=m.user_id ORDER BY m.id DESC LIMIT ?", (limit,))
        return [{"id": r[0], "to": r[1], "subject": r[2], "body": r[3], "kind": r[4],
                 "created": r[5], "read": bool(r[6])} for r in rows]
