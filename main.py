# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from database import init_db, add_activation_request, get_pending_requests
from licence_manager import generate_activation_code

# إنشاء تطبيق السيرفر
app = FastAPI(title="Madrassaty License Server")

# تشغيل قاعدة البيانات مع انطلاق السيرفر
@app.on_event("startup")
def startup_event():
    init_db()

# ---------------------------------------------------------
# 1. الواجهة الخاصة بالتطبيق (Desktop App)
# ---------------------------------------------------------

# النموذج اللي راح يبعثو التطبيق
class ActivationRequest(BaseModel):
    school_name: str
    username: str
    contact_info: str

@app.post("/api/request-activation")
def request_activation(req: ActivationRequest):
    """المسار اللي يعيطلوله التطبيق باش يبعث طلب تفعيل"""
    add_activation_request(req.school_name, req.username, req.contact_info)
    return {"status": "success", "message": "تم استلام الطلب بنجاح"}


# ---------------------------------------------------------
# 2. الواجهة الخاصة بك أنت (المدير / المطور)
# ---------------------------------------------------------

@app.get("/api/admin/requests")
def view_requests():
    """تشوف بيها شكون طلب تفعيل"""
    return {"pending_requests": get_pending_requests()}

class GenerateKeyRequest(BaseModel):
    username: str
    expiration_date: str

@app.post("/api/admin/generate-key")
def generate_key(req: GenerateKeyRequest):
    """تستعملها باش تولد كود التفعيل للمدرسة بعد ما يخلصوك"""
    key = generate_activation_code(req.username, req.expiration_date)
    return {"activation_key": key, "message": "تم توليد الكود بنجاح، أرسله للعميل"}