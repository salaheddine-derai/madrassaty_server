# main.py
import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from database import (
    init_db,
    create_account,
    get_account_by_username,
    get_account_by_id,
    get_all_accounts,
    activate_account,
    deactivate_account,
    unbind_device,
    bind_device,
    delete_account,
    hash_password,
)
from licence_manager import generate_activation_code

from contextlib import asynccontextmanager

# مفتاح الدخول للوحة تحكم الإدارة (يمكنك تغييره لكلمة مرور خاصة بك)
ADMIN_SECRET_KEY = "admin_madrassaty_2026"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # تهيئة قاعدة البيانات عند بدء تشغيل السيرفر
    init_db()
    yield

app = FastAPI(title="Madrassaty Central Server & Web Platform", lifespan=lifespan)

# إعداد قوالب HTML
templates = Jinja2Templates(directory="templates")

# =========================================================
# 1. صفحات الويب (Web Pages)
# =========================================================

@app.get("/", response_class=HTMLResponse)
@app.get("/register", response_class=HTMLResponse)
def page_register(request: Request):
    """صفحة إنشاء الحسابات للمدارس والأساتذة"""
    return templates.TemplateResponse(request=request, name="register.html")

@app.get("/status", response_class=HTMLResponse)
def page_status(request: Request):
    """صفحة فحص حالة التفعيل والصلاحية"""
    return templates.TemplateResponse(request=request, name="status.html")

@app.get("/admin", response_class=HTMLResponse)
def page_admin(request: Request):
    """لوحة تحكم الإدارة المركزية والتراخيص"""
    return templates.TemplateResponse(request=request, name="admin.html")


# =========================================================
# 2. واجهات برمجة التطبيقات العامة للموقع (Public Web APIs)
# =========================================================

class RegisterPayload(BaseModel):
    account_type: str
    full_name: str
    username: str
    password: str
    contact_info: str

@app.post("/api/register")
def api_register(payload: RegisterPayload):
    """تسجيل حساب جديد من الموقع"""
    if payload.account_type not in ['school', 'teacher']:
        return {"success": False, "message": "نوع الحساب غير صالح"}
    
    if len(payload.username.strip()) < 3:
        return {"success": False, "message": "اسم المستخدم يجب أن يكون 3 أحرف على الأقل"}

    if len(payload.password) < 4:
        return {"success": False, "message": "كلمة المرور قصيرة جداً (4 خانات كحد أدنى)"}

    ok, msg, acc_id = create_account(
        account_type=payload.account_type,
        full_name=payload.full_name,
        username=payload.username,
        password=payload.password,
        contact_info=payload.contact_info,
    )
    return {"success": ok, "message": msg, "account_id": acc_id}

@app.get("/api/status/{username}")
def api_check_status(username: str):
    """فحص حالة حساب معين"""
    acc = get_account_by_username(username)
    if not acc:
        return {"found": False}
    
    is_expired = False
    if acc.get('expires_at'):
        try:
            exp_dt = datetime.strptime(acc['expires_at'], "%Y-%m-%d")
            is_expired = (exp_dt < datetime.now())
        except:
            pass

    return {
        "found": True,
        "username": acc['username'],
        "full_name": acc['full_name'],
        "account_type": acc['account_type'],
        "is_active": bool(acc['is_active']),
        "expires_at": acc.get('expires_at'),
        "is_expired": is_expired,
        "is_bound": bool(acc.get('bound_device_id')),
    }


# =========================================================
# 3. واجهات لوحة تحكم الإدارة (Admin APIs)
# =========================================================

def verify_admin(admin_key: str):
    if admin_key != ADMIN_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized admin key")

@app.get("/api/admin/accounts")
def admin_get_accounts(admin_key: str):
    verify_admin(admin_key)
    accounts = get_all_accounts()
    # نحذف كلمات المرور من النتائج للأمان
    for a in accounts:
        a.pop('password_hash', None)
    return {"accounts": accounts}

class AdminActivatePayload(BaseModel):
    admin_key: str
    account_id: int
    duration_days: Optional[int] = 365

@app.post("/api/admin/activate")
def admin_activate(payload: AdminActivatePayload):
    verify_admin(payload.admin_key)
    ok = activate_account(payload.account_id, payload.duration_days)
    return {"success": ok, "message": "تم تفعيل الحساب بنجاح" if ok else "تعذر التفعيل"}

class AdminGenericPayload(BaseModel):
    admin_key: str
    account_id: int

@app.post("/api/admin/deactivate")
def admin_deactivate(payload: AdminGenericPayload):
    verify_admin(payload.admin_key)
    ok = deactivate_account(payload.account_id)
    return {"success": ok, "message": "تم تعطيل الحساب" if ok else "تعذر التعطيل"}

@app.post("/api/admin/unbind-device")
def admin_unbind_device(payload: AdminGenericPayload):
    verify_admin(payload.admin_key)
    ok = unbind_device(payload.account_id)
    return {"success": ok, "message": "تم فك ارتباط الجهاز بنجاح" if ok else "تعذر فك الارتباط"}

@app.post("/api/admin/delete-account")
def admin_delete_account(payload: AdminGenericPayload):
    verify_admin(payload.admin_key)
    ok = delete_account(payload.account_id)
    return {"success": ok, "message": "تم حذف الحساب نهائياً" if ok else "تعذر الحذف"}


# =========================================================
# 4. الـ API المخصص لتطبيق مدرستي (Mobile / Desktop Client API)
# =========================================================

class AppLoginPayload(BaseModel):
    username: str
    password: str
    device_id: str
    account_type: Optional[str] = None

@app.post("/api/app-login")
def api_app_login(payload: AppLoginPayload):
    """
    تسجيل الدخول من داخل تطبيق الهاتف أو الحاسوب:
    يتحقق من:
    1. صحة اسم المستخدم وكلمة المرور
    2. حالة التفعيل (مفعل / غير مفعل)
    3. الصلاحية (سارية / منتهية)
    4. ربط الجهاز (Device Binding لمنع فتح الحساب في جهازين مختلفين)
    """
    username = payload.username.strip().lower()
    acc = get_account_by_username(username)

    if not acc:
        return {
            "success": False,
            "error": "user_not_found",
            "message": "اسم المستخدم غير موجود، يرجى إنشاء حساب أولاً عبر موقعنا."
        }

    # التحقق من نوع الحساب إذا تم تحديده
    if payload.account_type and acc['account_type'] != payload.account_type:
        return {
            "success": False,
            "error": "account_type_mismatch",
            "message": f"هذا الحساب مسجل كـ ({acc['account_type']}) وليس ({payload.account_type})."
        }

    # التحقق من كلمة المرور
    pwd_hash = hash_password(payload.password)
    if pwd_hash != acc['password_hash']:
        return {
            "success": False,
            "error": "wrong_password",
            "message": "كلمة المرور غير صحيحة."
        }

    # التحقق من التفعيل
    if not acc['is_active']:
        return {
            "success": False,
            "error": "not_active",
            "message": "حسابك غير مفعّل بعد! يرجى الدخول للموقع والتواصل مع الإدارة لتفعيل اشتراكك.",
            "status_url": f"/status"
        }

    # التحقق من تاريخ الصلاحية
    expires_at = acc.get('expires_at')
    if expires_at:
        try:
            exp_date = datetime.strptime(expires_at, "%Y-%m-%d")
            if exp_date < datetime.now():
                return {
                    "success": False,
                    "error": "subscription_expired",
                    "message": f"انتهت صلاحية اشتراكك بتاريخ ({expires_at}). يرجى تجديد الاشتراك عبر الموقع."
                }
        except:
            pass

    # التحقق من ربط الجهاز (Single Device Policy)
    current_bound_device = acc.get('bound_device_id')
    device_id = payload.device_id.strip()

    if not current_bound_device:
        # ربط الحساب بهذا الجهاز لأول مرة
        bind_device(acc['id'], device_id)
    elif current_bound_device != device_id:
        return {
            "success": False,
            "error": "device_mismatch",
            "message": "هذا الحساب مرتبط بجهاز آخر بالفعل! للأمان لا يمكن تشغيل الحساب في جهازين في نفس الوقت. اتصل بالإدارة لفك ربط الجهاز القديم."
        }

    # توليد توكن ترخيص مشفر (License Token)
    license_token = generate_activation_code(acc['username'], expires_at or "2099-12-31")

    return {
        "success": True,
        "message": "تم تسجيل الدخول بنجاح",
        "user": {
            "id": acc['id'],
            "username": acc['username'],
            "full_name": acc['full_name'],
            "school_name": acc.get('school_name', acc['full_name']),
            "account_type": acc['account_type'],
            "expires_at": expires_at,
        },
        "license_token": license_token
    }

class LicenseCheckPayload(BaseModel):
    username: str
    device_id: str

@app.post("/api/app-check-license")
def api_app_check_license(payload: LicenseCheckPayload):
    """تحقق دوري من استمرار صلاحية الترخيص وربط الجهاز"""
    acc = get_account_by_username(payload.username.strip().lower())
    if not acc or not acc['is_active']:
        return {"valid": False, "reason": "not_active"}

    if acc.get('bound_device_id') and acc['bound_device_id'] != payload.device_id.strip():
        return {"valid": False, "reason": "device_mismatch"}

    expires_at = acc.get('expires_at')
    if expires_at:
        try:
            if datetime.strptime(expires_at, "%Y-%m-%d") < datetime.now():
                return {"valid": False, "reason": "expired"}
        except:
            pass

    return {"valid": True, "expires_at": expires_at}