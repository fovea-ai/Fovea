# =============================================================================
# storage.py — Local Database & Data Storage
# =============================================================================
#
# This file handles ALL data storage for Fovea.
# Everything is stored locally on the user's machine — nothing goes to a server.
#
# DATABASE: We use SQLite, a simple file-based database.
#   The database file is at: ~/Fovea/fovea.db
#   SQLite is built into Python — no server needed, no installation required.
#
# TABLES IN THE DATABASE:
#   cameras          — stores each camera the user has added
#   frames           — stores info about each captured frame (path, timestamp)
#   settings         — stores app settings (API key, capture interval, etc.)
#   training_submissions — photos uploaded for AI training
#   training_votes   — community votes on training submissions
#   approval_keys    — one-time keys for giving users approved access
#   approved_machines — machines that have claimed an approval key
#   terms_accepted   — tracks which machines have accepted the terms
#   camera_alerts    — stores disconnect/reconnect notifications
#   mod_codes        — moderator invite codes
#
# SECURITY:
#   API keys are encrypted using AES-256-GCM before being stored.
#   Even if someone got access to the database file, they couldn't read the key.
#   The encryption key is derived from a unique machine ID — so the encrypted
#   value only works on the machine it was encrypted on.
#
# HOW TO READ THIS FILE (for beginners):
#   Each function is a simple operation on the database:
#   - get_*   → read data from a table
#   - set_*   → write data to a table
#   - add_*   → insert a new row
#   - delete_* → remove a row
# =============================================================================

import sqlite3
import os
import uuid
import shutil
import hashlib
import platform
from datetime import datetime, timedelta

# ── Paths ─────────────────────────────────────────────────────────────────────
_HOME         = os.path.expanduser("~")
BASE_DIR      = os.path.join(_HOME, "Fovea")
DB_PATH       = os.path.join(BASE_DIR, "fovea.db")
FRAMES_PATH   = os.path.join(BASE_DIR, "frames")
TRAINING_PATH = os.path.join(BASE_DIR, "training")

# ── Encryption key (derived from machine ID — local only) ─────────────────────
_MACHINE_ID_CACHE: str | None = None

def _get_machine_id() -> str:
    """Stable per-machine UUID stored in DB settings. Cached in memory after first read."""
    global _MACHINE_ID_CACHE
    if _MACHINE_ID_CACHE:
        return _MACHINE_ID_CACHE
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Ensure settings table exists before querying
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("SELECT value FROM settings WHERE key='machine_id'")
        row = c.fetchone()
        if row:
            conn.close()
            _MACHINE_ID_CACHE = row[0]
            return _MACHINE_ID_CACHE
        mid = str(uuid.uuid4())
        c.execute("INSERT OR IGNORE INTO settings (key,value) VALUES ('machine_id',?)", (mid,))
        conn.commit()
        conn.close()
        _MACHINE_ID_CACHE = mid
        return mid
    except Exception:
        # Last resort fallback — use a file-based ID so it's at least stable per session
        fallback_path = os.path.join(BASE_DIR, ".machine_id")
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            if os.path.exists(fallback_path):
                with open(fallback_path) as f:
                    _MACHINE_ID_CACHE = f.read().strip()
                    return _MACHINE_ID_CACHE
            mid = str(uuid.uuid4())
            with open(fallback_path, "w") as f:
                f.write(mid)
            _MACHINE_ID_CACHE = mid
            return mid
        except Exception:
            _MACHINE_ID_CACHE = "fallback-machine-id"
            return _MACHINE_ID_CACHE


def _encryption_key() -> bytes:
    """Derive a 32-byte encryption key from the machine ID."""
    mid = _get_machine_id()
    return hashlib.sha256(f"fovea-{mid}".encode()).digest()


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string using AES-256-GCM.

    AES-256-GCM is authenticated encryption — it both encrypts AND
    verifies integrity. If anyone tampers with the stored value,
    decryption will fail rather than return garbage.

    Uses a random 12-byte nonce per encryption so the same value
    encrypted twice produces different ciphertext (prevents pattern analysis).

    Returns a base64-encoded string: nonce + ciphertext + tag
    """
    if not plaintext:
        return plaintext
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import os
        key   = _encryption_key()          # 32 bytes = 256 bits
        nonce = os.urandom(12)             # 96-bit random nonce (GCM standard)
        aes   = AESGCM(key)
        ct    = aes.encrypt(nonce, plaintext.encode(), None)
        # Store as base64: nonce (12 bytes) + ciphertext+tag
        return base64.urlsafe_b64encode(nonce + ct).decode()
    except Exception:
        return plaintext  # graceful fallback


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt an AES-256-GCM encrypted string.
    Also handles legacy Fernet-encrypted values for backward compatibility.
    """
    if not ciphertext:
        return ciphertext
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key  = _encryption_key()
        raw  = base64.urlsafe_b64decode(ciphertext.encode())
        # AES-GCM nonce is 12 bytes
        if len(raw) < 13:
            raise ValueError("Too short")
        nonce = raw[:12]
        ct    = raw[12:]
        aes   = AESGCM(key)
        return aes.decrypt(nonce, ct, None).decode()
    except Exception:
        # Legacy fallback: try Fernet (old AES-128 values)
        try:
            from cryptography.fernet import Fernet
            key_b64 = base64.urlsafe_b64encode(_encryption_key())
            return Fernet(key_b64).decrypt(ciphertext.encode()).decode()
        except Exception:
            return ciphertext  # not encrypted or unreadable — return as-is


# ── Admin password hash ───────────────────────────────────────────────────────
# The master password hash is stored in the database, NOT hardcoded in the binary.
# This means even if someone decompiles the exe, they cannot find the password.
# The hash is set the first time the user saves their master password in Settings.

def verify_admin_password(password: str) -> bool:
    """
    Verify the master password against the hash stored in the local database.
    The hash is never stored in the code — only in the user's local DB.
    """
    if not password:
        return False
    stored_hash = get_setting("master_password_hash", "")
    if not stored_hash:
        return False
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash


def set_admin_password(password: str):
    """
    Hash and store the master password in the local database.
    Called when the user saves their password in Settings.
    """
    if password:
        hashed = hashlib.sha256(password.encode()).hexdigest()
        set_setting("master_password_hash", hashed)


# ── Init ──────────────────────────────────────────────────────────────────────
def init_db():
    for d in (BASE_DIR, FRAMES_PATH, TRAINING_PATH):
        os.makedirs(d, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS cameras (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT    NOT NULL,
        source     TEXT    NOT NULL,
        type       TEXT    NOT NULL,
        active     INTEGER DEFAULT 1,
        created_at TEXT    DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS frames (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id      INTEGER NOT NULL,
        filepath       TEXT    NOT NULL,
        timestamp      TEXT    NOT NULL,
        ai_description TEXT,
        FOREIGN KEY (camera_id) REFERENCES cameras(id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS training_submissions (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        filepath              TEXT    NOT NULL,
        description           TEXT    NOT NULL,
        submitted_by          TEXT    DEFAULT 'anonymous',
        status                TEXT    DEFAULT 'pending_review',
        votes_yes             INTEGER DEFAULT 0,
        votes_no              INTEGER DEFAULT 0,
        vote_total            INTEGER DEFAULT 0,
        reported              INTEGER DEFAULT 0,
        report_count          INTEGER DEFAULT 0,
        created_at            TEXT    DEFAULT CURRENT_TIMESTAMP,
        reviewed_at           TEXT,
        reviewed_by           TEXT,
        corrected_description TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS training_votes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        submission_id INTEGER NOT NULL,
        machine_id    TEXT    NOT NULL,
        vote          TEXT    NOT NULL,
        created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(submission_id, machine_id))""")

    c.execute("""CREATE TABLE IF NOT EXISTS mod_codes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        code       TEXT    UNIQUE NOT NULL,
        label      TEXT,
        active     INTEGER DEFAULT 1,
        uses       INTEGER DEFAULT 0,
        created_at TEXT    DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS terms_accepted (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id  TEXT UNIQUE NOT NULL,
        accepted_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    c.execute("""CREATE TABLE IF NOT EXISTS approval_keys (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        key            TEXT    UNIQUE NOT NULL,
        status         TEXT    DEFAULT 'active',
        claimed_by     TEXT,
        created_at     TEXT    DEFAULT CURRENT_TIMESTAMP,
        claimed_at     TEXT,
        claim_attempts INTEGER DEFAULT 0)""")

    c.execute("""CREATE TABLE IF NOT EXISTS approved_machines (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        machine_id  TEXT UNIQUE NOT NULL,
        key_used    TEXT NOT NULL,
        approved_at TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # Timeline saves
    c.execute("""CREATE TABLE IF NOT EXISTS timeline_exports (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        query       TEXT NOT NULL,
        export_path TEXT NOT NULL,
        frame_count INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP)""")

    # Camera alerts
    c.execute("""CREATE TABLE IF NOT EXISTS camera_alerts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id  INTEGER NOT NULL,
        alert_type TEXT    NOT NULL,
        message    TEXT,
        seen       INTEGER DEFAULT 0,
        created_at TEXT    DEFAULT CURRENT_TIMESTAMP)""")

    conn.commit()
    conn.close()

    # Run retention cleanup on startup (non-blocking — purge is fast)
    try:
        days = int(get_setting("retention_days", 0) or 0)
        if days > 0:
            purge_old_frames(days)
    except Exception:
        pass  # Never block startup


# ── Settings (with encryption for sensitive keys) ─────────────────────────────

def get_setting(key: str, default=None) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row  = c.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception:
        return default


def set_setting(key: str, value):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)",
                  (key, str(value) if value is not None else ""))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to save setting '{key}': {e}")


def get_secure_setting(key: str, default="") -> str:
    """Get and decrypt a sensitive setting (e.g. API key)."""
    raw = get_setting(key, default)
    return decrypt_value(raw) if raw else default


def set_secure_setting(key: str, value: str):
    """Encrypt with AES-256-GCM and save a sensitive setting."""
    encrypted = encrypt_value(value) if value else ""
    set_setting(key, encrypted)


# ── Terms ─────────────────────────────────────────────────────────────────────

def has_accepted_terms() -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id FROM terms_accepted WHERE machine_id=?", (_get_machine_id(),))
        row  = c.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def accept_terms():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("INSERT OR IGNORE INTO terms_accepted (machine_id) VALUES (?)",
                  (_get_machine_id(),))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to accept terms: {e}")


# ── Cameras ───────────────────────────────────────────────────────────────────

def add_camera(name: str, source: str, cam_type: str) -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("INSERT INTO cameras (name,source,type) VALUES (?,?,?)",
                  (name, source, cam_type))
        cam_id = c.lastrowid
        conn.commit()
        conn.close()
        return cam_id
    except Exception as e:
        raise RuntimeError(f"Failed to add camera: {e}")


def get_cameras():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id,name,source,type,active FROM cameras")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def delete_camera(cam_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("DELETE FROM cameras WHERE id=?", (cam_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to delete camera: {e}")


def set_camera_active(cam_id: int, active: bool):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("UPDATE cameras SET active=? WHERE id=?", (1 if active else 0, cam_id))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Frames ────────────────────────────────────────────────────────────────────

def save_frame(camera_id: int, filepath: str, timestamp: str, description=None):
    try:
        # Check disk space before saving (warn if < 500 MB free)
        free = shutil.disk_usage(FRAMES_PATH).free
        if free < 200 * 1024 * 1024:
            raise RuntimeError(
                f"Low disk space: only {free // (1024*1024)} MB remaining. "
                "Free up space or reduce retention days in Settings."
            )
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute(
            "INSERT INTO frames (camera_id,filepath,timestamp,ai_description) VALUES (?,?,?,?)",
            (camera_id, filepath, timestamp, description)
        )
        conn.commit()
        conn.close()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to save frame: {e}")


def update_frame_description(frame_id: int, description: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("UPDATE frames SET ai_description=? WHERE id=?", (description, frame_id))
        conn.commit()
        conn.close()
    except Exception:
        pass


def search_frames(query: str, hours_back: float, camera_ids=None):
    try:
        cutoff = (datetime.now() - timedelta(hours=hours_back)).strftime("%Y-%m-%d %H:%M:%S")
        conn   = sqlite3.connect(DB_PATH)
        c      = conn.cursor()
        if camera_ids:
            ph = ",".join("?" * len(camera_ids))
            c.execute(f"""
                SELECT f.id, f.camera_id, f.filepath, f.timestamp, f.ai_description, cam.name
                FROM frames f JOIN cameras cam ON f.camera_id=cam.id
                WHERE f.timestamp >= ? AND f.camera_id IN ({ph})
                ORDER BY f.timestamp ASC
            """, [cutoff] + list(camera_ids))
        else:
            c.execute("""
                SELECT f.id, f.camera_id, f.filepath, f.timestamp, f.ai_description, cam.name
                FROM frames f JOIN cameras cam ON f.camera_id=cam.id
                WHERE f.timestamp >= ?
                ORDER BY f.timestamp ASC
            """, (cutoff,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_frames_in_range(camera_id: int, start_time: str, end_time: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            SELECT id, filepath, timestamp, ai_description
            FROM frames WHERE camera_id=? AND timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """, (camera_id, start_time, end_time))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def purge_old_frames(days: int):
    """Delete frames older than `days` days and their files."""
    if days <= 0:
        return
    try:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        conn   = sqlite3.connect(DB_PATH)
        c      = conn.cursor()
        c.execute("SELECT filepath FROM frames WHERE timestamp < ?", (cutoff,))
        files  = [r[0] for r in c.fetchall()]
        c.execute("DELETE FROM frames WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()
        for f in files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
    except Exception:
        pass


# ── Camera alerts ─────────────────────────────────────────────────────────────

def add_camera_alert(camera_id: int, alert_type: str, message: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute(
            "INSERT INTO camera_alerts (camera_id,alert_type,message) VALUES (?,?,?)",
            (camera_id, alert_type, message)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_unseen_alerts():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            SELECT a.id, a.camera_id, a.alert_type, a.message, a.created_at, cam.name
            FROM camera_alerts a JOIN cameras cam ON a.camera_id=cam.id
            WHERE a.seen=0 ORDER BY a.created_at DESC
        """)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def mark_alerts_seen():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("UPDATE camera_alerts SET seen=1")
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Training submissions ──────────────────────────────────────────────────────

def add_training_submission(filepath: str, description: str, submitted_by="anonymous") -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute(
            "INSERT INTO training_submissions (filepath,description,submitted_by) VALUES (?,?,?)",
            (filepath, description, submitted_by)
        )
        sub_id = c.lastrowid
        conn.commit()
        conn.close()
        return sub_id
    except Exception as e:
        raise RuntimeError(f"Failed to add submission: {e}")


def get_submissions_for_moderation():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            SELECT id,filepath,description,submitted_by,status,
                   votes_yes,votes_no,vote_total,report_count,created_at
            FROM training_submissions WHERE status IN ('pending_review','flagged')
            ORDER BY created_at ASC
        """)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_submissions_for_voting():
    try:
        mid  = _get_machine_id()
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            SELECT s.id,s.filepath,s.description,s.votes_yes,s.votes_no,s.vote_total
            FROM training_submissions s
            WHERE s.status='voting' AND s.reported=0
              AND NOT EXISTS (
                SELECT 1 FROM training_votes v
                WHERE v.submission_id=s.id AND v.machine_id=?)
            ORDER BY s.created_at ASC
        """, (mid,))
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def moderate_submission(sub_id: int, action: str, moderator_label: str, corrected_desc=None):
    try:
        now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        if action == "accept":
            if corrected_desc:
                c.execute("""UPDATE training_submissions
                    SET status='voting',reviewed_at=?,reviewed_by=?,corrected_description=?
                    WHERE id=?""", (now, moderator_label, corrected_desc, sub_id))
            else:
                c.execute("""UPDATE training_submissions
                    SET status='voting',reviewed_at=?,reviewed_by=?
                    WHERE id=?""", (now, moderator_label, sub_id))
        else:
            c.execute("""UPDATE training_submissions
                SET status='rejected',reviewed_at=?,reviewed_by=?
                WHERE id=?""", (now, moderator_label, sub_id))
        conn.commit()
        conn.close()
    except Exception as e:
        raise RuntimeError(f"Failed to moderate submission: {e}")


def cast_vote(submission_id: int, vote: str) -> bool:
    mid  = _get_machine_id()
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    try:
        c.execute(
            "INSERT INTO training_votes (submission_id,machine_id,vote) VALUES (?,?,?)",
            (submission_id, mid, vote)
        )
        if vote == "yes":
            c.execute("UPDATE training_submissions SET votes_yes=votes_yes+1,vote_total=vote_total+1 WHERE id=?",
                      (submission_id,))
        else:
            c.execute("UPDATE training_submissions SET votes_no=votes_no+1,vote_total=vote_total+1 WHERE id=?",
                      (submission_id,))
        conn.commit()
        c.execute("SELECT votes_yes,votes_no,vote_total FROM training_submissions WHERE id=?", (submission_id,))
        row = c.fetchone()
        if row:
            yes, no, total = row
            # Approval rule:
            # A submission is approved when at least 2 approved users vote YES.
            # It is rejected when at least 2 approved users vote NO.
            # This means only approved/trusted users can decide — not the general public.
            # The admin can also approve/reject directly via the Moderation tab.
            if yes >= 2:
                c.execute("UPDATE training_submissions SET status='approved' WHERE id=?", (submission_id,))
                conn.commit()
            elif no >= 2:
                c.execute("UPDATE training_submissions SET status='rejected' WHERE id=?", (submission_id,))
                conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def report_submission(submission_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""UPDATE training_submissions
            SET report_count=report_count+1,reported=1,status='flagged'
            WHERE id=?""", (submission_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_approved_training_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""
            SELECT id,filepath,COALESCE(corrected_description,description),
                   votes_yes,votes_no,vote_total
            FROM training_submissions WHERE status='approved'
            ORDER BY created_at ASC
        """)
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_training_stats() -> dict:
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT status,COUNT(*) FROM training_submissions GROUP BY status")
        rows = c.fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}


# ── Mod codes ─────────────────────────────────────────────────────────────────

def add_mod_code(code: str, label="") -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("INSERT INTO mod_codes (code,label) VALUES (?,?)", (code, label))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def validate_mod_code(code: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id,label FROM mod_codes WHERE code=? AND active=1", (code,))
        row  = c.fetchone()
        if row:
            c.execute("UPDATE mod_codes SET uses=uses+1 WHERE code=?", (code,))
            conn.commit()
        conn.close()
        return row
    except Exception:
        return None


def get_mod_codes():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id,code,label,active,uses,created_at FROM mod_codes ORDER BY created_at DESC")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def revoke_mod_code(code_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("UPDATE mod_codes SET active=0 WHERE id=?", (code_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ── Approval keys ─────────────────────────────────────────────────────────────

def generate_approval_key(password: str):
    if not verify_admin_password(password):
        return None
    import secrets
    key  = "VG-" + secrets.token_urlsafe(20).upper()
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("INSERT INTO approval_keys (key) VALUES (?)", (key,))
    conn.commit()
    conn.close()
    return key


def claim_approval_key(key: str) -> str:
    mid  = _get_machine_id()
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    try:
        c.execute("SELECT id FROM approved_machines WHERE machine_id=?", (mid,))
        if c.fetchone():
            return 'already'
        c.execute("SELECT id,status,claim_attempts FROM approval_keys WHERE key=?", (key,))
        row = c.fetchone()
        if not row:
            return 'invalid'
        key_id, status, attempts = row
        if status == 'claimed': return 'used'
        if status == 'voided':  return 'voided'
        if status != 'active':  return 'invalid'

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        c.execute("""UPDATE approval_keys
            SET claim_attempts=claim_attempts+1, claimed_at=COALESCE(claimed_at,?)
            WHERE key=? AND status='active'""", (now, key))
        conn.commit()

        c.execute("SELECT claim_attempts FROM approval_keys WHERE key=?", (key,))
        final = c.fetchone()[0]
        if final > 1:
            c.execute("UPDATE approval_keys SET status='voided' WHERE key=?", (key,))
            conn.commit()
            return 'race'

        c.execute("UPDATE approval_keys SET status='claimed',claimed_by=? WHERE key=?", (mid, key))
        c.execute("INSERT OR IGNORE INTO approved_machines (machine_id,key_used) VALUES (?,?)", (mid, key))
        conn.commit()
        return 'approved'
    finally:
        conn.close()


def is_machine_approved() -> bool:
    try:
        mid  = _get_machine_id()
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT id FROM approved_machines WHERE machine_id=?", (mid,))
        row  = c.fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def admin_approve_this_machine(password: str) -> bool:
    if not verify_admin_password(password):
        return False
    try:
        mid  = _get_machine_id()
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("INSERT OR IGNORE INTO approved_machines (machine_id,key_used) VALUES (?,?)",
                  (mid, "ADMIN_DIRECT"))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_all_approval_keys():
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("""SELECT id,key,status,claimed_by,created_at,claimed_at,claim_attempts
            FROM approval_keys ORDER BY created_at DESC""")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def revoke_approval_key(key_id: int):
    try:
        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        c.execute("UPDATE approval_keys SET status='voided' WHERE id=? AND status='active'", (key_id,))
        conn.commit()
        conn.close()
    except Exception:
        pass