from django.urls import path
from . import views

app_name = "app_finance"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("transactions/", views.transactions_list, name="transactions_list"),
    path("transactions/<int:pk>/edit/", views.transaction_edit, name="transaction_edit"),
    path("transactions/export/", views.transactions_export_csv, name="transactions_export_csv"),
    path("transactions/add/", views.transaction_create, name="transaction_create"),
    path("accounts/", views.accounts_manage, name="accounts_manage"),
    path("categories/", views.categories_manage, name="categories_manage"),
    path("recurring/", views.recurring_list, name="recurring_list"),
    path("recurring/generate/", views.recurring_generate_for_month, name="recurring_generate_for_month"),
    path("summary/month/", views.summary_month, name="summary_month"),
    path("goals/", views.goals_list, name="goals_list"),
    path("goals/<int:pk>/", views.goal_detail, name="goal_detail"), 
    path("report/month/pdf/", views.monthly_report_pdf, name="monthly_report_pdf"),
    path("calendar/", views.cash_calendar, name="cash_calendar"),
    path("budgets/", views.budgets_overview, name="budgets_overview"),
    path("report/monthly/", views.monthly_report, name="monthly_report"),
    path("debts/", views.debts_overview, name="debts_overview"),
    path("tools/", views.tools_home, name="tools_home"),
    path("tools/export/json/", views.export_full_json, name="export_full_json"),
    path("recurring/", views.recurring_list, name="recurring_list"),
    path("recurring/apply-month/", views.recurring_apply_month, name="recurring_apply_month"),
    path("howto/", views.howto_view, name="howto"),

]
