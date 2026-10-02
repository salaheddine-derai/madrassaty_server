# database.py
import sqlite3
import os

DB_PATH = "data/server.db"

def init_db():
    """إنشاء الجداول إذا لم تكن موجودة"""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            school_name TEXT NOT NULL,
            username TEXT NOT NULL,
            contact_info TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_activation_request(school_name, username, contact_info):
    """إضافة طلب تفعيل جديد يجينا من التطبيق"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO activation_requests (school_name, username, contact_info)
        VALUES (?, ?, ?)
    """, (school_name, username, contact_info))
    conn.commit()
    conn.close()
    return True

def get_pending_requests():
    """نجيبو كل الطلبات اللي مازال ماردينالهمش باش تشوفهم أنت"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    requests = cursor.execute("SELECT * FROM activation_requests WHERE status = 'pending'").fetchall()
    conn.close()
    return [dict(r) for r in requests]