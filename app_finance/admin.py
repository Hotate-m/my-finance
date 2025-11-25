from django.contrib import admin
from .models import Account, Category, Transaction, CategoryBudget, TransactionTemplate

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'opening_balance', 'current_balance', 'credit_limit', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['name']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'kind', 'is_debt_related']
    list_filter = ['kind', 'is_debt_related']
    search_fields = ['name']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'account', 'direction', 'amount', 'category', 'is_estimate', 'is_paid']
    list_filter = ['direction', 'is_estimate', 'is_paid', 'account', 'category']
    search_fields = ['note']
    date_hierarchy = 'date'

@admin.register(CategoryBudget)
class CategoryBudgetAdmin(admin.ModelAdmin):
    list_display = ("category", "year", "month", "amount", "note")
    list_filter = ("year", "month", "category")
    search_fields = ("category__name", "note")
    ordering = ("-year", "-month", "category__name")

@admin.register(TransactionTemplate)
class TransactionTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "direction", "default_amount", "account", "category", "is_active")
    list_filter = ("direction", "is_active")
    search_fields = ("name", "note")
    filter_horizontal = ("tags",)
