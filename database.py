# database.py
import sqlite3
import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

DB_PATH = "data/server.db"

def get_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """تهيئة جداول السيرفر"""
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. جدول الحسابات الموحد (مدارس وأساتذة)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_type TEXT NOT NULL CHECK(account_type IN ('school', 'teacher')),
            school_name TEXT,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            contact_info TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            bound_device_id TEXT,
            expires_at TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. جدول سجلات العمليات والتفعيل
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(id)
        )
    """)

    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """تشفير كلمة المرور بـ SHA256 مع Salt ثابت"""
    salt = "madrassaty_salt_2026_secure"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def create_account(
    account_type: str,
    full_name: str,
    username: str,
    password: str,
    contact_info: str,
    school_name: str = None
) -> Tuple[bool, str, Optional[int]]:
    """إنشاء حساب جديد غير مفعل"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM accounts WHERE username = ?", (username.strip().lower(),))
    if cursor.fetchone():
        conn.close()
        return False, "اسم المستخدم محجوز مسبقاً، يرجى اختيار اسم آخر", None

    pwd_hash = hash_password(password)
    # حساب الأستاذ مفعل تلقائياً ومباشرة، أما المدرسة فتنتظر تفعيل الإدارة
    is_teacher = (account_type == 'teacher')
    is_active_initial = 1 if is_teacher else 0
    expires_at_initial = "2099-12-31" if is_teacher else None

    try:
        cursor.execute("""
            INSERT INTO accounts (account_type, full_name, school_name, username, password_hash, contact_info, is_active, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_type,
            full_name.strip(),
            school_name.strip() if school_name else full_name.strip(),
            username.strip().lower(),
            pwd_hash,
            contact_info.strip(),
            is_active_initial,
            expires_at_initial
        ))
        acc_id = cursor.lastrowid

        if is_teacher:
            cursor.execute("""
                INSERT INTO activation_logs (account_id, action, details)
                VALUES (?, 'auto_activate', 'Auto-activated teacher account (Free Tier)')
            """, (acc_id,))

        conn.commit()
        msg = "تم إنشاء وتفعيل حساب الأستاذ بنجاح! يمكنك الآن تسجيل الدخول مباشرة من التطبيق." if is_teacher else "تم إنشاء الحساب بنجاح وهو الآن بانتظار التفعيل من الإدارة."
        return True, msg, acc_id
    except Exception as e:
        conn.rollback()
        return False, f"حدث خطأ أثناء إنشاء الحساب: {e}", None
    finally:
        conn.close()

def get_account_by_username(username: str) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE username = ?", (username.strip().lower(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_account_by_id(account_id: int) -> Optional[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_accounts(account_type: str = None) -> List[Dict]:
    """جلب كل الحسابات للوحة تحكم الأدمن"""
    conn = get_db()
    cursor = conn.cursor()
    if account_type:
        cursor.execute("SELECT * FROM accounts WHERE account_type = ? ORDER BY id DESC", (account_type,))
    else:
        cursor.execute("SELECT * FROM accounts ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def activate_account(account_id: int, duration_days: Optional[int] = 365) -> bool:
    """تفعيل الحساب وتحديد مدة الصلاحية"""
    conn = get_db()
    cursor = conn.cursor()
    
    if duration_days is None: # تفعيل دائم
        expires_at = "2099-12-31"
    else:
        expires_date = datetime.now() + timedelta(days=duration_days)
        expires_at = expires_date.strftime("%Y-%m-%d")

    cursor.execute("""
        UPDATE accounts 
        SET is_active = 1, expires_at = ? 
        WHERE id = ?
    """, (expires_at, account_id))

    cursor.execute("""
        INSERT INTO activation_logs (account_id, action, details)
        VALUES (?, 'activate', ?)
    """, (account_id, f"Activated for {duration_days} days (Expires: {expires_at})"))

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def deactivate_account(account_id: int) -> bool:
    """تعطيل الحساب"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET is_active = 0 WHERE id = ?", (account_id,))
    cursor.execute("INSERT INTO activation_logs (account_id, action, details) VALUES (?, 'deactivate', 'Manual deactivation')", (account_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def unbind_device(account_id: int) -> bool:
    """فك ارتباط الحساب بالجهاز للسماح بربط جهاز جديد"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET bound_device_id = NULL WHERE id = ?", (account_id,))
    cursor.execute("INSERT INTO activation_logs (account_id, action, details) VALUES (?, 'unbind_device', 'Device unbound by admin')", (account_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def bind_device(account_id: int, device_id: str) -> bool:
    """ربط الحساب بجهاز معين"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET bound_device_id = ? WHERE id = ?", (device_id, account_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def delete_account(account_id: int) -> bool:
    """حذف الحساب نهائياً من السيرفر"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM activation_logs WHERE account_id = ?", (account_id,))
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0