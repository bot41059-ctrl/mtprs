import os
import sqlite3
import logging
from datetime import datetime, timedelta
from vars import FREE_LIMIT, is_admin

logger = logging.getLogger("database")

# Local SQLite database path inside bot root
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "users.db")


def get_connection():
    """Returns a SQLite connection with timeout."""
    return sqlite3.connect(DB_PATH, timeout=10)


def init_db():
    """Initializes local SQLite database and migrates schema if needed."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_paid INTEGER DEFAULT 0,
                downloads_used INTEGER DEFAULT 0,
                first_name TEXT DEFAULT '',
                username TEXT DEFAULT '',
                expiry_date TEXT DEFAULT '',
                updated_at TEXT
            )
        """)
        conn.commit()

        # Check if expiry_date column exists (schema migration)
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "expiry_date" not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN expiry_date TEXT DEFAULT ''")
            conn.commit()

        conn.close()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")


# Initialize DB on load
init_db()


def get_expiry_info(expiry_str: str) -> tuple[bool, str, int]:
    """
    Returns (is_active: bool, formatted_string: str, days_left: int).
    """
    if not expiry_str:
        return True, "Permanent (Lifetime)", 99999
    try:
        exp_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        diff = exp_dt - datetime.utcnow()
        if diff.total_seconds() <= 0:
            return False, "Expired", 0
        days = diff.days
        hours = int(diff.seconds / 3600)
        return True, f"`{days} days, {hours} hours left` (Till `{expiry_str}` UTC)", days
    except Exception:
        return True, expiry_str, 0


def get_user(user_id: int, first_name: str = "", username: str = "") -> dict:
    """Retrieves user data, automatically checks expiry, or creates a new entry."""
    user_id = int(user_id)
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_paid, downloads_used, first_name, username, expiry_date, updated_at FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()

        if row:
            is_paid_val = bool(row[0])
            downloads_used = int(row[1])
            f_name = row[2] or first_name
            u_name = row[3] or username
            expiry_str = row[4] or ""
            updated_at = row[5]

            # Check if membership has expired
            if is_paid_val and expiry_str:
                try:
                    exp_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                    if datetime.utcnow() > exp_dt:
                        is_paid_val = False
                        cursor.execute("UPDATE users SET is_paid = 0 WHERE user_id = ?", (user_id,))
                        conn.commit()
                except Exception:
                    pass

            # Update names if passed
            if first_name or username:
                cursor.execute(
                    "UPDATE users SET first_name = COALESCE(NULLIF(?, ''), first_name), username = COALESCE(NULLIF(?, ''), username) WHERE user_id = ?",
                    (first_name, username, user_id)
                )
                conn.commit()

            conn.close()
            return {
                "user_id": user_id,
                "is_paid": is_paid_val,
                "downloads_used": downloads_used,
                "first_name": f_name,
                "username": u_name,
                "expiry_date": expiry_str,
                "updated_at": updated_at
            }

        # New user
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO users (user_id, is_paid, downloads_used, first_name, username, expiry_date, updated_at)
            VALUES (?, 0, 0, ?, ?, '', ?)
        """, (user_id, first_name, username, now_str))
        conn.commit()
        conn.close()

        return {
            "user_id": user_id,
            "is_paid": False,
            "downloads_used": 0,
            "first_name": first_name,
            "username": username,
            "expiry_date": "",
            "updated_at": now_str
        }
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return {
            "user_id": user_id,
            "is_paid": False,
            "downloads_used": 0,
            "first_name": first_name,
            "username": username,
            "expiry_date": "",
            "updated_at": ""
        }


def is_paid(user_id: int) -> bool:
    """Checks if a user is admin or has an active unexpired paid membership."""
    user_id = int(user_id)
    if is_admin(user_id):
        return True
    u = get_user(user_id)
    return bool(u.get("is_paid", False))


def get_downloads(user_id: int) -> int:
    """Returns number of downloads used by user."""
    u = get_user(user_id)
    return int(u.get("downloads_used", 0))


def increment_downloads(user_id: int, count: int = 1) -> int:
    """Increments downloads used counter."""
    user_id = int(user_id)
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, is_paid, downloads_used, updated_at)
            VALUES (?, 0, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                downloads_used = downloads_used + ?,
                updated_at = excluded.updated_at
        """, (user_id, count, now_str, count))
        conn.commit()
        cursor.execute("SELECT downloads_used FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else count
    except Exception as e:
        logger.error(f"Error incrementing downloads for {user_id}: {e}")
        return count


def add_paid_user(user_id: int, days: int = 30) -> tuple[bool, str]:
    """
    Grants paid/premium membership to a user for specified number of days.
    If user already has active time remaining, the days are stacked onto current expiry.
    Returns (success: bool, expiry_date_str: str).
    """
    user_id = int(user_id)
    days = int(days) if days > 0 else 30
    now = datetime.utcnow()

    base_dt = now
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_paid, expiry_date FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row[0] and row[1]:
            try:
                curr_exp = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")
                if curr_exp > now:
                    base_dt = curr_exp
            except Exception:
                pass

        expiry = base_dt + timedelta(days=days)
        expiry_str = expiry.strftime("%Y-%m-%d %H:%M:%S")
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO users (user_id, is_paid, downloads_used, expiry_date, updated_at)
            VALUES (?, 1, 0, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                is_paid = 1,
                expiry_date = excluded.expiry_date,
                updated_at = excluded.updated_at
        """, (user_id, expiry_str, now_str))
        conn.commit()
        conn.close()
        return True, expiry_str
    except Exception as e:
        logger.error(f"Error adding paid user {user_id}: {e}")
        return False, ""


def remove_paid_user(user_id: int) -> bool:
    """Removes paid/premium membership from a user."""
    user_id = int(user_id)
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET is_paid = 0, expiry_date = '', updated_at = ? WHERE user_id = ?
        """, (now_str, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error removing paid user {user_id}: {e}")
        return False


def reset_user_limit(user_id: int) -> bool:
    """Resets user download counter back to 0."""
    user_id = int(user_id)
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users SET downloads_used = 0, updated_at = ? WHERE user_id = ?
        """, (now_str, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error resetting limit for {user_id}: {e}")
        return False


def get_all_paid_users() -> list[dict]:
    """Returns list of all active paid users."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, first_name, username, downloads_used, expiry_date, updated_at FROM users WHERE is_paid = 1"
        )
        rows = cursor.fetchall()
        conn.close()
        
        now = datetime.utcnow()
        active_paid = []
        for r in rows:
            expiry_str = r[4] or ""
            # Filter out expired
            if expiry_str:
                try:
                    exp_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                    if now > exp_dt:
                        continue
                except Exception:
                    pass
            active_paid.append({
                "user_id": r[0],
                "first_name": r[1],
                "username": r[2],
                "downloads_used": r[3],
                "expiry_date": expiry_str,
                "updated_at": r[5]
            })
        return active_paid
    except Exception as e:
        logger.error(f"Error fetching paid users: {e}")
        return []


def check_access(user_id: int, count: int = 1) -> tuple[bool, int, str]:
    """
    Checks if user is allowed to download.
    Returns: (is_allowed: bool, remaining_downloads: int, message: str)
    """
    user_id = int(user_id)

    # 1. Admin bypass
    if is_admin(user_id):
        return True, 999999, "Admin Access (Unlimited)"

    # 2. Paid Member bypass
    u = get_user(user_id)
    if u.get("is_paid", False):
        return True, 999999, "Paid Member (Unlimited)"

    # 3. Free User calculation
    used = int(u.get("downloads_used", 0))
    remaining = FREE_LIMIT - used

    if remaining <= 0:
        return (
            False,
            0,
            f"🚫 **You are not a paid user!**\n\n"
            f"⚠️ Your free limit of **{FREE_LIMIT} videos** has been reached.\n"
            f"💳 **Please purchase a paid membership to continue downloading.**\n\n"
            f"📩 Contact Admin to buy membership."
        )

    return True, remaining, f"Free user: {used}/{FREE_LIMIT} used ({remaining} remaining)"
