# licence_manager.py
import json
import base64
import hmac
import hashlib

# نفس المفتاح السري اللي في التطبيق! لازم يكونو متطابقين 100%
SECRET_KEY = b"madrassaty_super_secret_key_2026_xyz"


def generate_activation_code(username: str, expiration_date: str) -> str:
    """
    توليد كود تفعيل مشفر
    """
    payload = {
        "username": username,
        "exp": expiration_date
    }

    payload_json = json.dumps(payload).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode('utf-8').rstrip("=")

    signature = hmac.new(SECRET_KEY, payload_b64.encode('utf-8'), hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode('utf-8').rstrip("=")

    return f"{payload_b64}.{signature_b64}"