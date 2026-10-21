import os
import sys
from datetime import date, timedelta
import flet as ft
from license_core import generate_activation_token, verify_activation_token, LicenseDB

def main(page: ft.Page):
    page.title = "سيرفر مدرستي - إدارة وتوليد تراخيص التفعيل"
    page.theme_mode = ft.ThemeMode.DARK
    page.rtl = True
    page.padding = ft.Padding.symmetric(horizontal=12, vertical=16)
    page.scroll = ft.ScrollMode.AUTO

    # ضبط أبعاد النافذة في بيئة الديسكتوب فقط دون التأثير على الهواتف
    try:
        if page.platform in [ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX]:
            page.window.width = 460
            page.window.height = 840
            page.window.min_width = 340
            page.window.min_height = 400
    except Exception:
        pass

    db = LicenseDB()

    # عناصر الإدخال مع دعم الشاشات الصغيرة والكبيرة Responsive
    username_input = ft.TextField(
        label="اسم المستخدم (Username) *",
        hint_text="مثال: ecole_najah أو admin",
        prefix_icon=ft.Icons.PERSON_ROUNDED,
        autofocus=True,
        border=ft.OutlineInputBorder(border_radius=10),
        col={"xs": 12, "sm": 12, "md": 6},
    )

    device_id_input = ft.TextField(
        label="معرّف الجهاز (Device ID) *",
        hint_text="مثال: MAD-4E2A-9B10",
        prefix_icon=ft.Icons.PHONE_ANDROID_ROUNDED,
        border=ft.OutlineInputBorder(border_radius=10),
        col={"xs": 12, "sm": 12, "md": 6},
    )

    school_name_input = ft.TextField(
        label="اسم المدرسة / المؤسسة (اختياري)",
        hint_text="مثال: مدرسة النجاح النموذجية",
        prefix_icon=ft.Icons.SCHOOL_ROUNDED,
        border=ft.OutlineInputBorder(border_radius=10),
        col={"xs": 12, "sm": 12, "md": 6},
    )

    phone_input = ft.TextField(
        label="رقم هاتف المدير / المسير (اختياري)",
        hint_text="مثال: 0550123456",
        prefix_icon=ft.Icons.PHONE_ROUNDED,
        border=ft.OutlineInputBorder(border_radius=10),
        col={"xs": 12, "sm": 12, "md": 6},
    )

    notes_input = ft.TextField(
        label="ملاحظات إضافية (اختياري)",
        hint_text="مثال: اشتراك سنوي مدفوع عبر بريدي موب",
        prefix_icon=ft.Icons.NOTE_ALT_ROUNDED,
        border=ft.OutlineInputBorder(border_radius=10),
        col={"xs": 12},
    )

    # حساب التواريخ المسبقة
    def calculate_expiry(choice: str) -> str:
        today = date.today()
        if choice == "1_month":
            return (today + timedelta(days=30)).strftime("%Y-%m-%d")
        elif choice == "3_months":
            return (today + timedelta(days=90)).strftime("%Y-%m-%d")
        elif choice == "6_months":
            return (today + timedelta(days=180)).strftime("%Y-%m-%d")
        elif choice == "1_year":
            return (today + timedelta(days=365)).strftime("%Y-%m-%d")
        elif choice == "2_years":
            return (today + timedelta(days=730)).strftime("%Y-%m-%d")
        elif choice == "lifetime":
            return "2099-12-31"
        return (today + timedelta(days=365)).strftime("%Y-%m-%d")

    duration_labels = {
        "1_month": "شهر واحد (30 يوم)",
        "3_months": "3 أشهر",
        "6_months": "6 أشهر",
        "1_year": "سنة كاملة (365 يوم)",
        "2_years": "سنتين",
        "lifetime": "تفعيل دائم مدى الحياة (2099)",
        "custom": "تاريخ مخصص...",
    }

    expiry_date_input = ft.TextField(
        label="تاريخ انتهاء الصلاحية (YYYY-MM-DD) *",
        value=calculate_expiry("1_year"),
        prefix_icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
        border=ft.OutlineInputBorder(border_radius=10),
        read_only=True,
        col={"xs": 12, "sm": 12, "md": 5},
    )

    def on_duration_changed(e):
        selected = duration_dropdown.value
        if selected == "custom":
            expiry_date_input.read_only = False
            expiry_date_input.focus()
        else:
            expiry_date_input.read_only = True
            expiry_date_input.value = calculate_expiry(selected)
        page.update()

    duration_dropdown = ft.Dropdown(
        label="مدة الترخيص والتفعيل",
        value="1_year",
        border=ft.OutlineInputBorder(border_radius=10),
        col={"xs": 12, "sm": 12, "md": 7},
        options=[
            ft.dropdown.Option("1_year", "سنة كاملة (365 يوم) - الافتراضي"),
            ft.dropdown.Option("6_months", "6 أشهر"),
            ft.dropdown.Option("3_months", "3 أشهر"),
            ft.dropdown.Option("1_month", "شهر واحد (30 يوم)"),
            ft.dropdown.Option("2_years", "سنتين"),
            ft.dropdown.Option("lifetime", "تفعيل دائم مدى الحياة (2099)"),
            ft.dropdown.Option("custom", "تحديد تاريخ انتهاء مخصص"),
        ],
        on_select=on_duration_changed,
    )

    # كارت إظهار النتيجة
    result_token_input = ft.TextField(
        label="كود التفعيل الموقّع رقمياً (جاهز للإرسال للعميل)",
        value="",
        read_only=True,
        border=ft.OutlineInputBorder(border_radius=10),
        multiline=True,
        min_lines=2,
        max_lines=3,
        text_size=12.5,
        prefix_icon=ft.Icons.VPN_KEY_ROUNDED,
    )

    result_info_text = ft.Text(
        value="",
        color=ft.Colors.GREEN_400,
        size=12.5,
        weight=ft.FontWeight.BOLD,
    )

    copy_btn = ft.FilledButton(
        content="نسخ كود التفعيل",
        icon=ft.Icons.CONTENT_COPY_ROUNDED,
        visible=False,
    )

    def show_snack(message: str, is_error: bool = False):
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.TEAL_700,
            duration=3000,
        )
        page.show_dialog(snack)

    def generate_code_click(e):
        username = username_input.value.strip()
        device_id = device_id_input.value.strip().upper()
        school_name = school_name_input.value.strip()
        phone = phone_input.value.strip()
        notes = notes_input.value.strip()
        exp_date = expiry_date_input.value.strip()
        dur_key = duration_dropdown.value
        dur_label = duration_labels.get(dur_key, dur_key)

        if not username:
            show_snack("خطأ: يرجى إدخال اسم المستخدم (Username).", is_error=True)
            username_input.focus()
            return

        if not device_id:
            show_snack("خطأ: يرجى إدخال معرّف الجهاز (Device ID).", is_error=True)
            device_id_input.focus()
            return

        if not exp_date:
            show_snack("خطأ: يرجى تحديد تاريخ انتهاء الصلاحية.", is_error=True)
            return

        try:
            token = generate_activation_token(username, device_id, exp_date)
            # حفظ بالسجل
            db.add_license(username, device_id, school_name, phone, dur_label, exp_date, token, notes)

            result_token_input.value = token
            result_info_text.value = f"✓ تم التوليد بنجاح! المستخدم: {username.lower()} • الجهاز: {device_id} • الصلاحية: {exp_date}"
            copy_btn.visible = True
            copy_btn.action = ft.CopyToClipboard(token)

            load_history()
            show_snack("تم إنشاء وتوقيع كود التفعيل بنجاح!")
        except Exception as ex:
            show_snack(f"حدث خطأ: {ex}", is_error=True)

    # جدول السجل
    history_column = ft.Column(spacing=10)

    def delete_single_license(lic_id):
        db.delete_license(lic_id)
        load_history()
        show_snack("تم حذف الترخيص من السجل.")

    def load_history(search_query: str = ""):
        history_column.controls.clear()
        if search_query.strip():
            licenses = db.search_licenses(search_query)
        else:
            licenses = db.get_all_licenses()

        if not licenses:
            history_column.controls.append(
                ft.Container(
                    content=ft.Text(
                        "لا توجد تراخيص مسجلة حتى الآن." if not search_query else "لا توجد نتائج مطابقة للبحث.",
                        color=ft.Colors.GREY_500,
                        size=13,
                    ),
                    alignment=ft.Alignment(0, 0),
                    padding=25,
                )
            )
        else:
            for lic in licenses:
                token_val = lic['token']
                dev_id_display = lic.get('device_id') or 'عام'
                history_column.controls.append(
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(
                                    controls=[
                                        ft.Row([
                                            ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=ft.Colors.TEAL_400, size=20),
                                            ft.Text(f"المستخدم: {lic['username']}", weight=ft.FontWeight.BOLD, size=13.5),
                                        ], spacing=6),
                                        ft.Row([
                                            ft.IconButton(
                                                icon=ft.Icons.CONTENT_COPY_ROUNDED,
                                                tooltip="نسخ الكود",
                                                icon_color=ft.Colors.AMBER_400,
                                                action=ft.CopyToClipboard(token_val),
                                                on_click=lambda e: show_snack("تم نسخ الكود بنجاح!"),
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                                tooltip="حذف",
                                                icon_color=ft.Colors.RED_400,
                                                on_click=lambda e, lid=lic['id']: delete_single_license(lid),
                                            ),
                                        ], spacing=0),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Container(
                                    content=ft.Row([
                                        const_icon := ft.Icon(ft.Icons.PHONE_ANDROID_ROUNDED, size=15, color=ft.Colors.TEAL_300),
                                        ft.Text(f"معرّف الجهاز: {dev_id_display}", color=ft.Colors.TEAL_300, weight=ft.FontWeight.BOLD, size=12.5),
                                    ], spacing=6),
                                    padding=ft.Padding.only(top=1, bottom=3),
                                ),
                                ft.Row([
                                    ft.Text(f"المدرسة: {lic['school_name'] or 'غير محدد'}", color=ft.Colors.GREY_400, size=12),
                                    ft.Text(f"• الهاتف: {lic['phone'] or '-'}", color=ft.Colors.GREY_400, size=12),
                                ], wrap=True),
                                ft.Text(
                                    f"تاريخ الإنشاء: {lic['created_at']} | ينتهي في: {lic['expiry_date']} ({lic['duration_label']})",
                                    color=ft.Colors.GREY_500,
                                    size=11,
                                ),
                            ],
                            spacing=3,
                        ),
                        padding=12,
                        border_radius=10,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                    )
                )
        page.update()

    search_input = ft.TextField(
        hint_text="بحث باسم المستخدم، معرف الجهاز، المدرسة، أو الهاتف...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        border=ft.OutlineInputBorder(border_radius=10),
        dense=True,
        on_change=lambda e: load_history(search_input.value),
        expand=True,
    )

    # بناء واجهة التطبيق المتجاوبة بالكامل ResponsiveRow
    page.add(
        # الهيدر
        ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, color=ft.Colors.TEAL_400, size=30),
                    ft.Column(
                        controls=[
                            ft.Text("سيرفر تراخيص مدرستي", weight=ft.FontWeight.BOLD, size=17),
                            ft.Text("توليد وتوقيع أكواد تفعيل الحسابات المربوطة بالجهاز", color=ft.Colors.GREY_400, size=11),
                        ],
                        spacing=2,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=ft.Padding.only(bottom=8),
        ),

        # كارت نموذج التوليد
        ft.Card(
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.ResponsiveRow(
                            controls=[
                                username_input,
                                device_id_input,
                                school_name_input,
                                phone_input,
                                duration_dropdown,
                                expiry_date_input,
                                notes_input,
                            ],
                            spacing=12,
                            run_spacing=12,
                        ),
                        ft.Container(
                            content=ft.FilledButton(
                                content="توليد وتوقيع كود التفعيل المربوط بالجهاز الآن",
                                icon=ft.Icons.KEY_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.TEAL_600,
                                    color=ft.Colors.WHITE,
                                    padding=14,
                                ),
                                on_click=generate_code_click,
                            ),
                            alignment=ft.Alignment(0, 0),
                            padding=ft.Padding.only(top=6),
                        ),
                        ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
                        result_token_input,
                        ft.Row(
                            controls=[
                                result_info_text,
                                copy_btn,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            wrap=True,
                        ),
                    ],
                    spacing=12,
                ),
                padding=14,
            ),
            elevation=2,
        ),

        ft.Container(height=10),

        # هيدر السجل والبحث متجاوب مع شاشات الهواتف
        ft.ResponsiveRow(
            controls=[
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.HISTORY_ROUNDED, color=ft.Colors.AMBER_400, size=20),
                        ft.Text("سجل التراخيص الصادرة", weight=ft.FontWeight.BOLD, size=15),
                    ]),
                    col={"xs": 12, "sm": 12, "md": 4},
                    alignment=ft.Alignment(-1, 0),
                ),
                ft.Container(
                    content=search_input,
                    col={"xs": 12, "sm": 12, "md": 8},
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            run_spacing=8,
        ),

        ft.Container(height=4),

        # قائمة السجل
        ft.Container(
            content=history_column,
            padding=ft.Padding.only(bottom=30),
        ),
    )

    load_history()

if __name__ == "__main__":
    ft.run(main)
