import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "safety_monitor.db"


def ensure_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                email TEXT,
                company_name TEXT,
                email_verified INTEGER NOT NULL DEFAULT 0,
                email_verified_at TEXT
            );
            """
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source_label TEXT NOT NULL,
                file_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                helmet_detected INTEGER NOT NULL,
                shoes_detected INTEGER NOT NULL,
                alert_reason TEXT NOT NULL,
                helmet_ratio REAL NOT NULL,
                shoe_dark_ratio REAL NOT NULL,
                detector_summary TEXT NOT NULL
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at DESC);")

        # 과거 users 테이블이 일부 컬럼만 있었던 경우를 위한 보강.
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(users);").fetchall()}
        if "email" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT;")
        if "company_name" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN company_name TEXT;")
        if "email_verified" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0;")
        if "email_verified_at" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT;")

        # 컬럼 보강 후에 이메일 관련 인덱스를 생성합니다.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_email_tokens_user_id ON email_verification_tokens(user_id);")


def user_count() -> int:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT COUNT(*) FROM users;").fetchone()
    return int(row[0] if row else 0)


def ensure_default_admin(username: str, password_hash: str) -> None:
    ensure_db()
    if user_count() > 0:
        return
    if not username or not password_hash:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO users (created_at, username, password_hash, email_verified) VALUES (?, ?, ?, 1);",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(username), str(password_hash)),
        )


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, created_at, username, password_hash, email, company_name, email_verified, email_verified_at
            FROM users
            WHERE username = ?;
            """,
            (str(username or "").strip(),),
        ).fetchone()
    return dict(row) if row else None


def verify_user_password(user_row: Dict[str, Any], plain_password: str) -> bool:
    try:
        return check_password_hash(str(user_row.get("password_hash", "")), str(plain_password or ""))
    except Exception:
        return False


def is_email_verified(user_row: Dict[str, Any]) -> bool:
    try:
        return bool(int(user_row.get("email_verified") or 0))
    except Exception:
        return False


def create_user_pending_verification(username: str, plain_password: str, email: str, company_name: str) -> tuple[Optional[str], Optional[str]]:
    ensure_db()
    username = (username or "").strip()
    plain_password = (plain_password or "").strip()
    email = (email or "").strip()
    company_name = (company_name or "").strip()

    if not username or not plain_password or not email:
        return "아이디/비밀번호/이메일을 모두 입력하세요.", None

    if get_user_by_username(username) is not None:
        return "이미 존재하는 아이디입니다.", None

    password_hash = generate_password_hash(plain_password)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO users (created_at, username, password_hash, email, company_name, email_verified) VALUES (?, ?, ?, ?, ?, 0);",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username, password_hash, email, company_name),
        )
        user_id = int(conn.execute("SELECT last_insert_rowid();").fetchone()[0])

    token = create_email_verification_token(user_id=user_id, ttl_minutes=60)
    return None, token


def create_email_verification_token(user_id: int, ttl_minutes: int = 60) -> str:
    ensure_db()
    now = datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (now + timedelta(minutes=int(ttl_minutes))).strftime("%Y-%m-%d %H:%M:%S")
    token = secrets.token_urlsafe(32)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO email_verification_tokens (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?);",
            (token, int(user_id), created_at, expires_at),
        )
    return token


def verify_email_with_token(token: str) -> Optional[str]:
    ensure_db()
    token = (token or "").strip()
    if not token:
        return "토큰이 없습니다."

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT token, user_id, expires_at, used_at FROM email_verification_tokens WHERE token = ?;",
            (token,),
        ).fetchone()
        if not row:
            return "유효하지 않은 토큰입니다."
        if row["used_at"]:
            return "이미 사용된 토큰입니다."

        try:
            expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return "토큰 만료 정보가 올바르지 않습니다."
        if datetime.now() > expires_at:
            return "토큰이 만료되었습니다. 다시 인증을 진행하세요."

        used_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE email_verification_tokens SET used_at = ? WHERE token = ?;", (used_at, token))
        conn.execute("UPDATE users SET email_verified = 1, email_verified_at = ? WHERE id = ?;", (used_at, int(row["user_id"])))

    return None


def insert_alert(alert_item: Dict[str, Any]) -> None:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO alerts (
                created_at,
                source_label,
                file_name,
                relative_path,
                helmet_detected,
                shoes_detected,
                alert_reason,
                helmet_ratio,
                shoe_dark_ratio,
                detector_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                str(alert_item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                str(alert_item.get("source_label") or ""),
                str(alert_item.get("file_name") or ""),
                str(alert_item.get("relative_path") or ""),
                1 if bool(alert_item.get("helmet_detected")) else 0,
                1 if bool(alert_item.get("shoes_detected")) else 0,
                str(alert_item.get("alert_reason") or ""),
                float(alert_item.get("helmet_ratio") or 0.0),
                float(alert_item.get("shoe_dark_ratio") or 0.0),
                str(alert_item.get("detector_summary") or ""),
            ),
        )


def list_alerts(limit: int = 30) -> List[Dict[str, Any]]:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                id,
                created_at AS timestamp,
                source_label,
                file_name,
                relative_path,
                helmet_detected,
                shoes_detected,
                alert_reason,
                helmet_ratio,
                shoe_dark_ratio,
                detector_summary
            FROM alerts
            ORDER BY id DESC
            LIMIT ?;
            """,
            (int(limit),),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["helmet_detected"] = bool(item.get("helmet_detected"))
        item["shoes_detected"] = bool(item.get("shoes_detected"))
        items.append(item)
    return items


def import_alerts_from_jsonl(jsonl_path: Path, max_lines: Optional[int] = None) -> int:
    if not jsonl_path.exists():
        return 0

    ensure_db()
    lines = jsonl_path.read_text(encoding="utf-8").splitlines()
    if max_lines is not None:
        lines = lines[: int(max_lines)]

    imported = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            import json

            item = json.loads(line)
        except Exception:
            continue
        insert_alert(item)
        imported += 1
    return imported
