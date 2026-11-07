"""SQLite account store with invite licenses and encrypted per-user settings."""
import base64, hashlib, json, os, secrets, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from cryptography.fernet import Fernet
from werkzeug.security import check_password_hash, generate_password_hash

DATA_DIR = Path(os.environ.get("TERMSENDER_DATA_DIR", "data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "termsender.sqlite3"

def _db():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    return c

def _fernet():
    secret = os.environ.get("TERMSENDER_ENCRYPTION_SECRET")
    path = DATA_DIR / ".encryption-key"
    if secret:
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))
    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError("TERMSENDER_ENCRYPTION_SECRET is required in production")
    if not path.exists(): path.write_bytes(Fernet.generate_key())
    return Fernet(path.read_bytes())

FERNET = _fernet()

class AccountStore:
    def __init__(self):
        with _db() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE COLLATE NOCASE,name TEXT NOT NULL,password_hash TEXT NOT NULL,is_admin INTEGER NOT NULL DEFAULT 0,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,last_login TEXT);
            CREATE TABLE IF NOT EXISTS licenses(id INTEGER PRIMARY KEY,key_hash TEXT UNIQUE,email TEXT NOT NULL COLLATE NOCASE,name TEXT NOT NULL,created_at TEXT NOT NULL,expires_at TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,redeemed_by INTEGER REFERENCES users(id),redeemed_at TEXT);
            CREATE TABLE IF NOT EXISTS user_configs(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,value BLOB NOT NULL,encrypted INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(user_id,name));
            """)
        self.bootstrap_admin()

    def bootstrap_admin(self):
        with _db() as c:
            if c.execute("SELECT 1 FROM users WHERE is_admin=1 LIMIT 1").fetchone(): return
            email=os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@localhost").strip().lower()
            password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
            if os.getenv("APP_ENV")=="production" and not password: raise RuntimeError("Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD before first start")
            local=not password
            password=password or secrets.token_urlsafe(24)
            c.execute("INSERT INTO users(email,name,password_hash,is_admin,created_at) VALUES(?,?,?,?,?)",(email,"Administrator",generate_password_hash(password),1,datetime.now(timezone.utc).isoformat()))
            if local:
                f=DATA_DIR/"local-admin-credentials.txt"; f.write_text(f"Email: {email}\nPassword: {password}\n",encoding="utf-8"); print(f"TermSender admin credentials saved to {f}")

    @staticmethod
    def hash_key(key): return hashlib.sha256(key.strip().encode()).hexdigest()

    def user(self, uid):
        if not uid: return None
        with _db() as c:
            r=c.execute("SELECT id,email,name,is_admin,active FROM users WHERE id=? AND active=1",(uid,)).fetchone()
        return dict(r) if r else None

    def login(self,email,password):
        with _db() as c:
            r=c.execute("SELECT * FROM users WHERE email=? COLLATE NOCASE AND active=1",(email.strip(),)).fetchone()
            if not r or not check_password_hash(r["password_hash"],password): return None
            c.execute("UPDATE users SET last_login=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),r["id"]))
        return self.user(r["id"])

    def activate(self,email,name,password,key):
        now=datetime.now(timezone.utc)
        with _db() as c:
            lic=c.execute("SELECT * FROM licenses WHERE key_hash=? AND email=? COLLATE NOCASE AND active=1",(self.hash_key(key),email.strip())).fetchone()
            if not lic: return None,"License invalid, inactive, or issued to another email."
            if lic["redeemed_by"]: return None,"This license was already used."
            if datetime.fromisoformat(lic["expires_at"])<now: return None,"This license expired."
            try: cur=c.execute("INSERT INTO users(email,name,password_hash,created_at) VALUES(?,?,?,?)",(email.strip().lower(),name.strip(),generate_password_hash(password),now.isoformat()))
            except sqlite3.IntegrityError: return None,"An account with this email already exists."
            c.execute("UPDATE licenses SET redeemed_by=?,redeemed_at=? WHERE id=?",(cur.lastrowid,now.isoformat(),lic["id"]))
        return self.user(cur.lastrowid),None

    def issue(self,email,name,days=365):
        key=secrets.token_urlsafe(32); now=datetime.now(timezone.utc); expiry=now+timedelta(days=max(1,min(int(days),3650)))
        with _db() as c: c.execute("INSERT INTO licenses(key_hash,email,name,created_at,expires_at) VALUES(?,?,?,?,?)",(self.hash_key(key),email.strip().lower(),name.strip(),now.isoformat(),expiry.isoformat()))
        return key

    def licenses(self):
        with _db() as c: rows=c.execute("SELECT l.email AS user_email,l.name AS user_name,substr(l.created_at,1,10) created_date,substr(l.expires_at,1,10) expiry_date,l.active AS is_active,l.redeemed_at,u.last_login FROM licenses l LEFT JOIN users u ON u.id=l.redeemed_by ORDER BY l.id DESC").fetchall()
        return [dict(x) for x in rows]

    def revoke(self,email):
        with _db() as c:
            c.execute("UPDATE licenses SET active=0 WHERE email=? COLLATE NOCASE",(email.strip(),)); c.execute("UPDATE users SET active=0 WHERE email=? COLLATE NOCASE AND is_admin=0",(email.strip(),))

    def save_config(self,uid,name,value,secret=False):
        raw=json.dumps(value,ensure_ascii=False).encode(); raw=FERNET.encrypt(raw) if secret else raw
        with _db() as c: c.execute("INSERT INTO user_configs VALUES(?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET value=excluded.value,encrypted=excluded.encrypted",(uid,name,raw,int(secret)))

    def get_config(self,uid,name,default):
        with _db() as c: row=c.execute("SELECT value,encrypted FROM user_configs WHERE user_id=? AND name=?",(uid,name)).fetchone()
        if not row:return default
        raw=FERNET.decrypt(bytes(row["value"])) if row["encrypted"] else bytes(row["value"])
        return json.loads(raw.decode())

store=AccountStore()
