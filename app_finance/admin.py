from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import (
    Account,
    Category,
    Transaction,
    CategoryBudget,
    TransactionTemplate,
)

User = get_user_model()


class OwnableAdminMixin:
    """
    Mixin สำหรับ model ที่มี field owner:
    - non-superuser จะเห็นเฉพาะของตัวเอง
    - เวลาเพิ่ม record ใหม่ จะเซ็ต owner เป็น request.user อัตโนมัติ (ถ้ายังไม่เซ็ต)
    """

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(owner=request.user)

    def save_model(self, request, obj, form, change):
        # ถ้า object นี้มี field owner และยังไม่ได้กำหนด owner ให้เป็นคนที่กดบันทึก
        if hasattr(obj, "owner") and obj.owner_id is None:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


@admin.register(Account)
class AccountAdmin(OwnableAdminMixin, admin.ModelAdmin):
    list_display = [
        "name",
        "owner",           # ✅ แสดงเจ้าของ
        "account_type",
        "opening_balance",
        "current_balance",
        "credit_limit",
        "is_active",
    ]
    list_filter = ["account_type", "is_active", "owner"]   # ✅ filter ตาม owner ด้วย
    search_fields = ["name", "owner__username", "owner__email"]
    # current_balance เป็น @property ใช้ใน list_display ได้เลย


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # Category เป็นของกลาง ไม่ผูก owner
    list_display = ["name", "kind", "is_debt_related"]
    list_filter = ["kind", "is_debt_related"]
    search_fields = ["name"]


@admin.register(Transaction)
class TransactionAdmin(OwnableAdminMixin, admin.ModelAdmin):
    list_display = [
        "date",
        "owner",        # ✅ เจ้าของ
        "account",
        "direction",
        "amount",
        "category",
        "is_estimate",
        "is_paid",
    ]
    list_filter = [
        "direction",
        "is_estimate",
        "is_paid",
        "account",
        "category",
        "owner",        # ✅ filter owner
    ]
    search_fields = ["note", "owner__username", "owner__email"]
    date_hierarchy = "date"


@admin.register(CategoryBudget)
class CategoryBudgetAdmin(OwnableAdminMixin, admin.ModelAdmin):
    list_display = ("category", "owner", "year", "month", "amount", "note")
    list_filter = ("year", "month", "category", "owner")
    search_fields = ("category__name", "note", "owner__username", "owner__email")
    ordering = ("-year", "-month", "category__name")


@admin.register(TransactionTemplate)
class TransactionTemplateAdmin(OwnableAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "direction",
        "default_amount",
        "account",
        "category",
        "is_active",
    )
    list_filter = ("direction", "is_active", "owner")
    search_fields = ("name", "note", "owner__username", "owner__email")
    filter_horizontal = ("tags",)
