import os
import json
import base64
import hmac
import hashlib
import sqlite3
from datetime import datetime, date

# المفتاح السري المطابق للتطبيق في فلاتر (LicenseService.secretKey)
SECRET_KEY = "madrassaty_super_secret_key_2026_xyz"

def generate_activation_token(username: str, device_id: str, expiry_date: str) -> str:
    """
    توليد كود تفعيل موقّع ومشفّر رقمياً (HMAC-SHA256 Token)
    مرتبط باسم المستخدم ومعرّف الجهاز (Device ID) وصالح لغاية تاريخ محدد.
    متوافق 100% مع LicenseService في تطبيق مدرستي فلاتر.
    """
    clean_user = username.strip().lower()
    clean_device = device_id.strip().upper()
    clean_exp = expiry_date.strip()

    if not clean_user:
        raise ValueError("اسم المستخدم مطلوب ولا يمكن أن يكون فارغاً.")
    if not clean_device:
        raise ValueError("معرّف الجهاز (Device ID) مطلوب ولا يمكن أن يكون فارغاً.")
    
    try:
        datetime.strptime(clean_exp, "%Y-%m-%d")
    except ValueError:
        raise ValueError("تنسيق التاريخ غير صالح. يجب أن يكون YYYY-MM-DD")

    payload = {
        "username": clean_user,
        "device_id": clean_device,
        "exp": clean_exp,
    }

    # تسلسل JSON بدون مسافات لمطابقة Dart json.encode
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip('=')

    # التوقيع الرقمي HMAC-SHA256
    digest = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

    return f"{payload_b64}.{sig_b64}"

def verify_activation_token(token: str, username: str, device_id: str = "") -> dict:
    """
    التحقق من صحة كود التفعيل ومطابقته لاسم المستخدم ومعرّف الجهاز وتاريخ الصلاحية
    """
    clean_token = token.strip().replace('"', '').replace("'", "")
    clean_user = username.strip().lower()
    clean_device = device_id.strip().upper()

    parts = clean_token.split('.')
    if len(parts) != 2:
        return {"is_valid": False, "message": "تنسيق الكود خاطئ."}

    payload_b64, sig_b64 = parts[0], parts[1]

    # التحقق من التوقيع
    expected_digest = hmac.new(SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).digest()
    expected_sig_b64 = base64.urlsafe_b64encode(expected_digest).decode('utf-8').rstrip('=')

    if not hmac.compare_digest(sig_b64, expected_sig_b64):
        return {"is_valid": False, "message": "التوقيع الرقمي غير صالح (كود مزوّر أو تم التلاعب به)."}

    # فك تشفير البيانات
    normalized_b64 = payload_b64 + '=' * ((4 - len(payload_b64) % 4) % 4)
    try:
        payload_data = json.loads(base64.urlsafe_b64decode(normalized_b64).decode('utf-8'))
    except Exception as e:
        return {"is_valid": False, "message": f"خطأ في فك البيانات: {e}"}

    target_user = payload_data.get("username", "").strip().lower()
    if target_user != clean_user:
        return {
            "is_valid": False,
            "message": f"الكود مخصص للمستخدم ({target_user}) ولا يطابق ({clean_user})."
        }

    target_device = payload_data.get("device_id", "").strip().upper()
    if clean_device and target_device and target_device != clean_device:
        return {
            "is_valid": False,
            "message": f"الكود مخصص لجهاز ({target_device}) ولا يطابق ({clean_device})."
        }

    exp_str = payload_data.get("exp", "")
    try:
        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
    except ValueError:
        return {"is_valid": False, "message": "تاريخ الصلاحية غير صالح."}

    today = date.today()
    if today > exp_date:
        return {
            "is_valid": False,
            "expiry_date": exp_str,
            "message": f"انتهت صلاحية هذا الكود في {exp_str}."
        }

    return {
        "is_valid": True,
        "expiry_date": exp_str,
        "username": target_user,
        "device_id": target_device,
        "message": f"الكود صالح لغاية {exp_str} ✓"
    }

class LicenseDB:
    def __init__(self, db_path=None):
        if db_path is None:
            storage_dir = os.environ.get("FLET_APP_STORAGE_DATA")
            if not storage_dir:
                storage_dir = os.path.dirname(os.path.abspath(__file__))
            try:
                os.makedirs(storage_dir, exist_ok=True)
            except Exception:
                pass
            db_path = os.path.join(storage_dir, "licenses.db")
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS licenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    device_id TEXT,
                    school_name TEXT,
                    phone TEXT,
                    duration_label TEXT,
                    expiry_date TEXT NOT NULL,
                    token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    notes TEXT
                )
            ''')
            # فحص إذا كان حقل device_id موجوداً في الجداول القديمة
            cursor = conn.execute("PRAGMA table_info(licenses)")
            columns = [row[1] for row in cursor.fetchall()]
            if "device_id" not in columns:
                conn.execute("ALTER TABLE licenses ADD COLUMN device_id TEXT")
            conn.commit()

    def add_license(self, username, device_id, school_name, phone, duration_label, expiry_date, token, notes=""):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO licenses (username, device_id, school_name, phone, duration_label, expiry_date, token, created_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username.strip().lower(), device_id.strip().upper(), school_name.strip(), phone.strip(), duration_label, expiry_date.strip(), token.strip(), now_str, notes.strip()))
            conn.commit()
            return cursor.lastrowid

    def get_all_licenses(self):
        with self.get_connection() as conn:
            cursor = conn.execute('SELECT * FROM licenses ORDER BY id DESC')
            return [dict(row) for row in cursor.fetchall()]

    def search_licenses(self, query):
        q = f"%{query.strip().lower()}%"
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM licenses 
                WHERE LOWER(username) LIKE ? OR LOWER(school_name) LIKE ? OR phone LIKE ? OR LOWER(device_id) LIKE ?
                ORDER BY id DESC
            ''', (q, q, q, q))
            return [dict(row) for row in cursor.fetchall()]

    def delete_license(self, license_id):
        with self.get_connection() as conn:
            conn.execute('DELETE FROM licenses WHERE id = ?', (license_id,))
            conn.commit()
