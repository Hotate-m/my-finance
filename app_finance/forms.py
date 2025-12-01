from django import forms
from .models import Transaction, Account, Category, RecurringTransaction, Goal, DebtPlanSetting


class TransactionForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Transaction
        fields = [
            "account",
            "date",
            "direction",
            "amount",
            "category",
            "goal",
            "is_estimate",
            "note",
            "proof_file",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "form-select"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "goal": forms.Select(attrs={"class": "form-select"}),
            "is_estimate": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["name", 
                  "account_type", 
                  "opening_balance", 
                  "credit_limit", 
                  "is_active",
                  "interest_rate",
                  "min_payment_percent",
                  ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-select"}),
            "opening_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "kind", "is_debt_related", "monthly_budget"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "kind": forms.Select(attrs={"class": "form-select"}),
            "is_debt_related": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "monthly_budget": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "placeholder": "เช่น 5000.00 ถ้าไม่ตั้งให้เว้นว่าง",
            }),
        }


class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = [
            "name",
            "account",
            "category",
            "direction",
            "amount",
            "day_of_month",
            "is_active",
            "start_date",
            "end_date",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "เช่น ค่าเช่าห้อง, ผ่อนรถ"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "day_of_month": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 31}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "end_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

class GoalForm(forms.ModelForm):
    target_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = Goal
        fields = [
            "name",
            "account",
            "target_amount",
            "target_date",
            "direction",
            "is_active",
            "note",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "เช่น ทริปญี่ปุ่น, กองทุนสำรองเลี้ยงชีพ"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "target_amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
class DebtPlanSettingForm(forms.ModelForm):
    class Meta:
        model = DebtPlanSetting
        fields = ["monthly_budget", "strategy"]
        widgets = {
            "monthly_budget": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
            }),
            "strategy": forms.Select(attrs={"class": "form-select"}),
        }