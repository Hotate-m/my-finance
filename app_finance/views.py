import csv, calendar
from decimal import Decimal

from django.db.models import Sum, Q
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import logout
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date
from django.template.loader import get_template

try:
    from weasyprint import HTML
except Exception:
    HTML = None

from .models import Account, Transaction, Category, RecurringTransaction, DashboardPreference, Goal, CategoryBudget, TransactionTemplate, Tag, DebtPlanSetting
from .forms import TransactionForm, AccountForm, CategoryForm, RecurringTransactionForm, GoalForm

@login_required
def home(request):
    """หน้าเริ่มต้น แนะนำขั้นตอนใช้งาน"""
    accounts_count = Account.objects.count()
    categories_count = Category.objects.count()
    tx_count = Transaction.objects.count()

    context = {
        "accounts_count": accounts_count,
        "categories_count": categories_count,
        "tx_count": tx_count,
    }
    return render(request, "app_finance/home.html", context)
@login_required
def _get_filtered_transactions(request):
    """
    ใช้ร่วมกันระหว่างหน้า list + export CSV
    รองรับการกรอง: ปี, เดือน, ประเภท (IN/OUT), คำค้นหา
    """
    qs = Transaction.objects.select_related("account", "category").order_by("-date", "-id")

    filter_type = (request.GET.get("type") or "").strip()   # IN / OUT / ""
    year = (request.GET.get("year") or "").strip()          # "2025" / ""
    month = (request.GET.get("month") or "").strip()        # "1".."12" / ""
    q = (request.GET.get("q") or "").strip()                # keyword

    # ประเภท รายรับ/รายจ่าย
    if filter_type in ["IN", "OUT"]:
        qs = qs.filter(direction=filter_type)

    # ปี
    if year.isdigit():
        qs = qs.filter(date__year=int(year))

    # เดือน
    if month.isdigit():
        qs = qs.filter(date__month=int(month))

    # ค้นหา note / ชื่อบัญชี / ชื่อหมวด
    if q:
        qs = qs.filter(
            Q(note__icontains=q) |
            Q(account__name__icontains=q) |
            Q(category__name__icontains=q)
        )

    income_sum = qs.filter(direction="IN").aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expense_sum = qs.filter(direction="OUT").aggregate(total=Sum("amount"))["total"] or Decimal("0")
    net_sum = income_sum - expense_sum

    return qs, {
        "filter_type": filter_type,
        "year": year,
        "month": month,
        "q": q,
        "income_sum": income_sum,
        "expense_sum": expense_sum,
        "net_sum": net_sum,
    }

from datetime import datetime   # ถ้ายังไม่ได้ import ด้านบนไฟล์ ให้เพิ่มบรรทัดนี้
from decimal import Decimal
from django.db.models import Sum
...

@login_required
def transactions_list(request):
    """หน้าแสดงประวัติรายการทั้งหมด + filter + summary"""
    qs, filter_ctx = _get_filtered_transactions(request)

    # ===== filter ตามวันที่จากปฏิทิน (?date=YYYY-MM-DD) =====
    selected_date = None
    selected_date_str = (request.GET.get("date") or "").strip()
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
            qs = qs.filter(date=selected_date)

            # ถ้าอยากให้ summary ด้านบนอัปเดตตามวันที่นี้ด้วย
            income_sum = qs.filter(direction="IN").aggregate(total=Sum("amount"))["total"] or Decimal("0")
            expense_sum = qs.filter(direction="OUT").aggregate(total=Sum("amount"))["total"] or Decimal("0")
            net_sum = income_sum - expense_sum
            filter_ctx.update({
                "income_sum": income_sum,
                "expense_sum": expense_sum,
                "net_sum": net_sum,
            })
        except ValueError:
            selected_date = None  # ถ้า parse ไม่ได้ก็ไม่กรองอะไรเพิ่ม

    # เตรียมตัวเลือกปีจากข้อมูลจริงในฐานข้อมูล
    years_qs = Transaction.objects.dates("date", "year", order="DESC")
    years = [str(d.year) for d in years_qs]

    # ตัวเลือกเดือน (ใช้ string เพื่อเทียบใน template ง่าย)
    months = [
        ("1", "ม.ค."),
        ("2", "ก.พ."),
        ("3", "มี.ค."),
        ("4", "เม.ย."),
        ("5", "พ.ค."),
        ("6", "มิ.ย."),
        ("7", "ก.ค."),
        ("8", "ส.ค."),
        ("9", "ก.ย."),
        ("10", "ต.ค."),
        ("11", "พ.ย."),
        ("12", "ธ.ค."),
    ]

    query_string = request.GET.urlencode()  # เอาไว้ใช้กับปุ่ม Export CSV

    context = {
        "transactions": qs,
        "years": years,
        "months": months,
        "query_string": query_string,
        "selected_date": selected_date,
        "selected_date_str": selected_date_str,
        **filter_ctx,  # มี filter_type, year, month, q, income_sum, expense_sum, net_sum
    }
    return render(request, "app_finance/transactions_list.html", context)

@login_required
def transactions_export_csv(request):
    """Export รายการตาม filter ปัจจุบันเป็น CSV (เอาไปเปิดใน Excel ได้)"""
    qs, filter_ctx = _get_filtered_transactions(request)

    year_label = filter_ctx["year"] or "all"
    month_label = filter_ctx["month"] or "all"

    filename = f"transactions_{year_label}_{month_label}.csv"

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # header
    writer.writerow([
        "วันที่",
        "บัญชี",
        "ประเภท",
        "จำนวนเงิน",
        "หมวดหมู่",
        "ประมาณการ/จริง",
        "หมายเหตุ",
    ])

    for t in qs:
        direction_label = "รายรับ" if t.direction == "IN" else "รายจ่าย"
        status_label = "ประมาณการ" if t.is_estimate else "จริง"
        writer.writerow([
            t.date.strftime("%Y-%m-%d"),
            t.account.name if t.account else "",
            direction_label,
            f"{t.amount:.2f}",
            t.category.name if t.category else "",
            status_label,
            (t.note or "").replace("\n", " "),
        ])

    return response

@login_required
def dashboard(request):
    """หน้า Dashboard หลัก + สรุปวันนี้/เดือนนี้ + กราฟ + goals + recurring + budgets"""
    today = timezone.now().date()
    year = today.year
    month = today.month

    # ===== บัญชี & Net Worth =====
    accounts = Account.objects.filter(is_active=True)

    total_assets = Decimal("0")
    total_debt = Decimal("0")

    for acc in accounts:
        bal = acc.current_balance or Decimal("0")   # ใช้ property current_balance
        bal = Decimal(bal)
        if bal >= 0:
            total_assets += bal
        else:
            total_debt += abs(bal)

    net_worth = total_assets - total_debt

    # ===== รายรับ/รายจ่าย "จริง" ของเดือนนี้ =====
    month_tx = Transaction.objects.filter(
        date__year=year,
        date__month=month,
        is_estimate=False,
    )

    income_month = month_tx.filter(direction="IN").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    expense_month = month_tx.filter(direction="OUT").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    net_month = income_month - expense_month

    # ===== รายรับ/รายจ่าย "ประมาณการ" ของเดือนนี้ =====
    est_tx = Transaction.objects.filter(
        date__year=year,
        date__month=month,
        is_estimate=True,
    )
    est_income = est_tx.filter(direction="IN").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    est_expense = est_tx.filter(direction="OUT").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    est_net = est_income - est_expense

    # ===== รายรับ/รายจ่าย "วันนี้" =====
    today_tx = Transaction.objects.filter(
        date=today,
        is_estimate=False,
    )
    today_income = today_tx.filter(direction="IN").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    today_expense = today_tx.filter(direction="OUT").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    today_net = today_income - today_expense

    # ฟังก์ชัน format 0.00
    def fmt(amount):
        a = amount or Decimal("0")
        return f"{a:.2f}"

    today_income_str = fmt(today_income)
    today_expense_str = fmt(today_expense)
    today_net_str = fmt(today_net)

    # ===== รายการล่าสุด 10 รายการ =====
    recent_tx = Transaction.objects.select_related("account", "category").order_by(
        "-date", "-id"
    )[:10]

    # ===== ข้อมูลกราฟ 6 เดือนล่าสุด (รายการจริง) =====
    labels = []
    income_data = []
    expense_data = []

    months_back = []
    for i in range(5, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        months_back.append((y, m))

    month_names_short = {
        1: "ม.ค.",
        2: "ก.พ.",
        3: "มี.ค.",
        4: "เม.ย.",
        5: "พ.ค.",
        6: "มิ.ย.",
        7: "ก.ค.",
        8: "ส.ค.",
        9: "ก.ย.",
        10: "ต.ค.",
        11: "พ.ย.",
        12: "ธ.ค.",
    }

    for y2, m2 in months_back:
        label = f"{month_names_short.get(m2, m2)} {str(y2)[2:]}"
        labels.append(label)

        base_qs = Transaction.objects.filter(
            date__year=y2,
            date__month=m2,
            is_estimate=False,
        )
        inc = base_qs.filter(direction="IN").aggregate(s=Sum("amount"))["s"] or Decimal("0")
        exp = base_qs.filter(direction="OUT").aggregate(s=Sum("amount"))["s"] or Decimal("0")

        income_data.append(float(inc))
        expense_data.append(float(exp))

    # ===== รายจ่ายต่อหมวดในเดือนนี้ (สำหรับกราฟวงกลม + ใช้เทียบงบ) =====
    expense_by_cat_qs = (
        Transaction.objects.filter(
            date__year=year,
            date__month=month,
            direction="OUT",
            is_estimate=False,
        )
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    cat_labels = []
    cat_values = []
    expense_map_by_cat = {}
    for row in expense_by_cat_qs:
        cid = row["category_id"]
        name = row["category__name"] or "ไม่ระบุหมวด"
        total = row["total"] or Decimal("0")
        expense_map_by_cat[cid] = total
        cat_labels.append(name)
        cat_values.append(float(total))

    # ===== Smart Insights =====
    insight_top_category_name = None
    insight_top_category_amount = None

    if expense_by_cat_qs:
        top = expense_by_cat_qs[0]
        insight_top_category_name = top["category__name"] or "ไม่ระบุหมวด"
        insight_top_category_amount = top["total"] or Decimal("0")

    # เปรียบเทียบรายจ่ายเดือนนี้ vs ค่าเฉลี่ย 3 เดือนก่อนหน้า
    last3_months = []
    for i in range(1, 4):  # 1,2,3 เดือนก่อนหน้า
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        last3_months.append((y, m))

    total_exp_prev = Decimal("0")
    count_prev = 0
    for y3, m3 in last3_months:
        prev_qs = Transaction.objects.filter(
            date__year=y3,
            date__month=m3,
            is_estimate=False,
            direction="OUT",
        )
        val = prev_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        total_exp_prev += val
        count_prev += 1

    avg_exp_prev = total_exp_prev / count_prev if count_prev > 0 else None

    insight_expense_vs_avg = None
    insight_expense_vs_avg_percent = None
    insight_expense_higher = None

    if avg_exp_prev is not None and avg_exp_prev > 0:
        diff = expense_month - avg_exp_prev
        insight_expense_vs_avg = diff
        insight_expense_higher = diff > 0
        insight_expense_vs_avg_percent = float((diff / avg_exp_prev) * 100)

    # ===== งบประมาณรายจ่ายเดือนนี้ (Budget signals) =====
    budget_items = []
    budgets_qs = (
        CategoryBudget.objects
        .filter(year=year, month=month)
        .select_related("category")
    )

    budget_over_count = 0
    for b in budgets_qs:
        budget_amount = b.amount or Decimal("0")
        spent = expense_map_by_cat.get(b.category_id, Decimal("0"))
        diff_b = budget_amount - spent  # เหลือเท่าไหร่ (ติดลบ = เกินงบ)
        if budget_amount > 0:
            percent_b = float(spent / budget_amount * 100)
        else:
            percent_b = None

        over = spent > budget_amount
        if over:
            budget_over_count += 1

        budget_items.append({
            "obj": b,
            "category_name": b.category.name,
            "budget_amount": budget_amount,
            "spent": spent,
            "diff": diff_b,
            "percent": percent_b,
            "over": over,
        })

    budget_items_sorted = sorted(
        budget_items,
        key=lambda x: (x["percent"] if x["percent"] is not None else -1),
        reverse=True,
    )
    budget_items_dashboard = budget_items_sorted[:3]
    budget_total_count = len(budget_items)

    # ===== เป้าหมาย (preview 3 เป้าหมาย) =====
    goals_preview = []
    for g in Goal.objects.filter(is_active=True).select_related("account").order_by("target_date", "name")[:3]:
        qs_goal = Transaction.objects.filter(
            goal=g,
            is_estimate=False,
            direction=g.direction,
        )
        done_g = qs_goal.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        target_g = g.target_amount or Decimal("0")
        percent_g = float(done_g / target_g * 100) if target_g > 0 else None
        remaining_g = target_g - done_g

        goals_preview.append({
            "obj": g,
            "done": done_g,
            "target": target_g,
            "percent": percent_g,
            "remaining": remaining_g,
        })

    # ===== รายการประจำที่กำลังจะถึง (ในเดือนนี้) =====
    upcoming_recurring = []
    last_day = calendar.monthrange(year, month)[1]

    for r in RecurringTransaction.objects.filter(is_active=True).select_related("account", "category"):
        d = min(r.day_of_month, last_day)
        next_date = today.replace(day=d)

        if next_date < today:
            continue

        upcoming_recurring.append({
            "obj": r,
            "next_date": next_date,
        })

    upcoming_recurring.sort(key=lambda x: x["next_date"])
    upcoming_recurring = upcoming_recurring[:5]

    # ===== ตั้งค่า Dashboard + แผนปลดหนี้ =====
    dashboard_pref, _ = DashboardPreference.objects.get_or_create(user=request.user)
    debt_plan = DebtPlanSetting.objects.first()  # อันเดียวใช้ทั้งหน้า

    context = {
        "today": today,

        # Net worth
        "total_assets": total_assets,
        "total_liabilities": total_debt,
        "net_worth": net_worth,

        "accounts": accounts,

        # เดือนนี้จริง
        "income_month": income_month,
        "expense_month": expense_month,
        "net_month": net_month,

        # เดือนนี้ประมาณการ
        "est_income": est_income,
        "est_expense": est_expense,
        "est_net": est_net,

        # วันนี้
        "today_income": today_income,
        "today_expense": today_expense,
        "today_net": today_net,
        "today_income_str": today_income_str,
        "today_expense_str": today_expense_str,
        "today_net_str": today_net_str,

        # รายการล่าสุด
        "recent_tx": recent_tx,

        # กราฟเส้น 6 เดือน
        "chart_labels": labels,
        "chart_income": income_data,
        "chart_expense": expense_data,

        # กราฟวงกลมหมวดรายจ่าย
        "cat_labels": cat_labels,
        "cat_values": cat_values,

        # Smart Insight
        "insight_top_category_name": insight_top_category_name,
        "insight_top_category_amount": insight_top_category_amount,
        "insight_expense_vs_avg": insight_expense_vs_avg,
        "insight_expense_vs_avg_percent": insight_expense_vs_avg_percent,
        "insight_expense_higher": insight_expense_higher,
        "avg_exp_prev": avg_exp_prev,

        # งบประมาณเดือนนี้
        "budget_items_dashboard": budget_items_dashboard,
        "budget_total_count": budget_total_count,
        "budget_over_count": budget_over_count,

        # goals + recurring preview
        "goals_preview": goals_preview,
        "upcoming_recurring": upcoming_recurring,
    }

    # ===== แผนปลดหนี้ที่เลือกใช้ (ใช้บนการ์ด “แผนปลดหนี้ที่ใช้อยู่ตอนนี้”) =====
    debt_plan = DebtPlanSetting.objects.first()

    # ===== ตั้งค่าหน้า Dashboard ของ user คนนี้ =====
    dash_pref, _ = DashboardPreference.objects.get_or_create(user=request.user)

    context.update({
        "dash_pref": dash_pref,
        "debt_plan": debt_plan,
    })

    return render(request, "app_finance/dashboard.html", context)


@login_required
def dashboard_preferences(request):
    """
    ตั้งค่าว่าหน้า Dashboard จะแสดงการ์ดไหนบ้าง
    """
    pref, _ = DashboardPreference.objects.get_or_create(user=request.user)

    if request.method == "POST":
        fields = [
            "show_smart_insights",
            "show_budget_box",
            "show_goals",
            "show_recurring",
            "show_today_summary",
            "show_trend_chart",
            "show_expense_pie",
            "show_estimate_box",
            "show_accounts",
            "show_recent_transactions",
            "show_debt_plan_card",
        ]

        for field in fields:
            setattr(pref, field, field in request.POST)

        pref.save()
        messages.success(request, "บันทึกการตั้งค่าหน้า Dashboard แล้วคับ")
        return redirect("app_finance:dashboard")

    return render(request, "app_finance/dashboard_preferences.html", {
        "pref": pref,
    })

@login_required
def tools_home(request):
    """
    หน้า Tools / เครื่องมือ: รวมลิงก์สำรองข้อมูล / export ต่าง ๆ
    """
    now = timezone.now()
    return render(request, "app_finance/tools.html", {
        "now": now,
    })

@login_required
def export_full_json(request):
    """
    Export ข้อมูลหลักทั้งหมดเป็นไฟล์ JSON
    เอาไว้ backup เก็บเอง หรือย้ายเครื่องในอนาคต
    """
    now = timezone.now()

    data = {
        "generated_at": now,
        "user": request.user.username,

        # ข้อมูลหลัก
        "accounts": list(Account.objects.all().values()),
        "categories": list(Category.objects.all().values()),
        "tags": list(Tag.objects.all().values()),
        "goals": list(Goal.objects.all().values()),
        "category_budgets": list(CategoryBudget.objects.all().values()),
        "recurring_transactions": list(RecurringTransaction.objects.all().values()),
        "transaction_templates": list(TransactionTemplate.objects.all().values()),
        "transactions": list(Transaction.objects.all().values()),

        # ความสัมพันธ์ ManyToMany
        "transaction_tags": list(Transaction.tags.through.objects.all().values()),
        "transaction_template_tags": list(TransactionTemplate.tags.through.objects.all().values()),
    }

    filename = now.strftime("myfinance_backup_%Y%m%d_%H%M%S.json")

    response = JsonResponse(
        data,
        json_dumps_params={"ensure_ascii": False, "indent": 2},
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

@login_required
def debts_overview(request):
    """
    หน้าแผนปลดหนี้:
    - รวมหนี้จากบัญชีประเภท CREDIT / LOAN (ยอดปัจจุบันติดลบ)
    - จำลองงบจ่ายหนี้ต่อเดือนแบบง่าย ๆ
    - ให้เลือกแผน Snowball / Avalanche / ยังไม่เลือก แล้วเอาไปโชว์บน Dashboard
    """

    today = timezone.now().date()

    # ===== ดึงบัญชีหนี้ =====
    base_qs = (
        Account.objects
        .filter(
            is_active=True,
            account_type__in=["CREDIT", "LOAN"],
        )
        .order_by("name")
    )

    debts = []
    total_debt = Decimal("0")

    for acc in base_qs:
        # ถ้ามี current_balance ให้ใช้เลย, ถ้าไม่มีก็คำนวณจาก opening + tx
        if hasattr(acc, "current_balance"):
            bal = acc.current_balance or Decimal("0")
        else:
            opening = acc.opening_balance or Decimal("0")
            total_tx = acc.transactions.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            bal = opening + total_tx

        if bal >= 0:
            continue  # ไม่ใช่หนี้

        debt_amount = abs(Decimal(bal))
        total_debt += debt_amount

        interest_rate = acc.interest_rate or Decimal("0")         # % ต่อปี
        min_percent = acc.min_payment_percent or Decimal("0")     # % ของยอดหนี้

        min_payment = None
        if min_percent > 0:
            min_payment = (debt_amount * min_percent / Decimal("100")).quantize(
                Decimal("0.01")
            )

        months_to_payoff = None
        if min_payment and min_payment > 0:
            months_to_payoff = ceil(float(debt_amount / min_payment))

        debts.append({
            "account": acc,
            "debt_amount": debt_amount,
            "interest_rate": interest_rate,
            "min_percent": min_percent,
            "min_payment": min_payment,
            "months_to_payoff": months_to_payoff,
        })

    # แผน Snowball / Avalanche
    snowball_plan = sorted(
        debts,
        key=lambda x: x["debt_amount"]
    )
    avalanche_plan = sorted(
        debts,
        key=lambda x: x["interest_rate"],
        reverse=True,
    )

    # ===== Simulator: งบจ่ายหนี้ต่อเดือน =====
    monthly_budget_raw = (request.GET.get("monthly_budget") or "").replace(",", "").strip()
    monthly_budget = None
    sim_months = None

    if monthly_budget_raw:
        try:
            monthly_budget = Decimal(monthly_budget_raw)
            if monthly_budget > 0 and total_debt > 0:
                sim_months = ceil(float(total_debt / monthly_budget))
        except Exception:
            monthly_budget = None
            sim_months = None

    # ===== แผนปลดหนี้ที่เลือกใช้ (DebtPlanSetting – singleton) =====
    plan, _ = DebtPlanSetting.objects.get_or_create(pk=1)

    if request.method == "POST":
        strategy = (request.POST.get("strategy") or "NONE").upper()
        allowed = dict(DebtPlanSetting.STRATEGY_CHOICES).keys()
        if strategy not in allowed:
            strategy = "NONE"

        plan.strategy = strategy
        plan.save()
        messages.success(request, "บันทึกแผนปลดหนี้ที่ใช้อยู่เรียบร้อยแล้วคับ")
        return redirect("app_finance:debts_overview")

    context = {
        "today": today,
        "debts": debts,
        "total_debt": total_debt,
        "debt_count": len(debts),
        "snowball_plan": snowball_plan,
        "avalanche_plan": avalanche_plan,

        "monthly_budget_raw": monthly_budget_raw,
        "monthly_budget": monthly_budget,
        "sim_months": sim_months,

        "plan": plan,
    }
    return render(request, "app_finance/debts_overview.html", context)

@login_required
def transaction_create(request):
    """สร้าง Transaction ใหม่ (รองรับ ?type=IN/OUT, ?goal=<id>, ?next=/path)"""
    from decimal import Decimal

    # รับ next จาก query string หรือจาก POST (เผื่อส่งซ้ำเป็น hidden field)
    next_url = (request.GET.get("next") or request.POST.get("next") or "").strip()

    initial = {}

    # ตั้งค่า direction จาก query string ?type=IN/OUT
    direction_default = (request.GET.get("type") or "").upper()
    if direction_default in ("IN", "OUT"):
        initial["direction"] = direction_default

    # ถ้ามี ?goal=<id> ให้ผูกกับเป้าหมายนั้น
    goal_id = request.GET.get("goal")
    if goal_id:
        try:
            goal_obj = Goal.objects.get(pk=goal_id)
            initial["goal"] = goal_obj
        except Goal.DoesNotExist:
            goal_obj = None
    else:
        goal_obj = None

    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES)
        if form.is_valid():
            tx = form.save()
            messages.success(request, "บันทึกรายการเรียบร้อยแล้ว")

            # ถ้ามี next และเป็น path ในเว็บเรา ให้เด้งกลับไป path นั้น (ใช้กับ Quick Add บน Dashboard)
            if next_url and next_url.startswith("/"):
                return redirect(next_url)

            # ถ้าเป็นรายการของ goal และไม่มี next ให้เด้งกลับไปหน้า goal_detail
            if tx.goal_id:
                return redirect("app_finance:goal_detail", pk=tx.goal_id)

            # default เด้งไปหน้ารายการทั้งหมด
            return redirect("app_finance:transactions_list")
    else:
        form = TransactionForm(initial=initial)

    return render(request, "app_finance/transaction_form.html", {
        "form": form,
        "goal": goal_obj,
        "next": next_url,  # เผื่ออยากใส่เป็น hidden field ในฟอร์มปกติด้วย
    })

@login_required
def transaction_edit(request, pk):
    """แก้ไข Transaction ที่มีอยู่แล้ว"""
    tx = get_object_or_404(Transaction, pk=pk)

    if request.method == "POST":
        form = TransactionForm(request.POST, request.FILES, instance=tx)
        if form.is_valid():
            form.save()
            messages.success(request, "แก้ไขรายการเรียบร้อยแล้ว")
            return redirect("app_finance:transactions_list")
    else:
        form = TransactionForm(instance=tx)

    return render(request, "app_finance/transaction_form.html", {
        "form": form,
        "transaction": tx,
    })

@login_required
def transactions_list(request):
    """หน้าแสดงประวัติรายการทั้งหมด + filter แบบง่าย (รายรับ/รายจ่าย)"""
    qs = Transaction.objects.select_related("account", "category").order_by("-date", "-id")

    # filter แบบง่าย: ?type=IN หรือ ?type=OUT
    filter_type = request.GET.get("type")
    if filter_type in ["IN", "OUT"]:
        qs = qs.filter(direction=filter_type)

    income_sum = qs.filter(direction="IN").aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expense_sum = qs.filter(direction="OUT").aggregate(total=Sum("amount"))["total"] or Decimal("0")
    net_sum = income_sum - expense_sum

    context = {
        "transactions": qs,
        "filter_type": filter_type,
        "income_sum": income_sum,
        "expense_sum": expense_sum,
        "net_sum": net_sum,
    }
    return render(request, "app_finance/transactions_list.html", context)

@login_required
def accounts_manage(request):
    """หน้า HTML สำหรับดู + เพิ่มบัญชี/กระเป๋า"""
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("app_finance:accounts_manage")
    else:
        form = AccountForm()

    accounts = Account.objects.all().order_by("name")

    return render(request, "app_finance/accounts.html", {
        "form": form,
        "accounts": accounts,
    })

@login_required
def account_edit(request, pk):
    """
    แก้ไขบัญชีที่มีอยู่ (ชื่อ, ประเภท, ดอกเบี้ย, % ขั้นต่ำ ฯลฯ)
    """
    account = get_object_or_404(Account, pk=pk)

    if request.method == "POST":
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, "อัปเดตข้อมูลบัญชีเรียบร้อยแล้ว")
            return redirect("app_finance:accounts_manage")
    else:
        form = AccountForm(instance=account)

    return render(request, "app_finance/account_form.html", {
        "form": form,
        "account": account,
        "edit_mode": True,
    })

@login_required
def categories_manage(request):
    """หน้า HTML สำหรับดู + เพิ่มหมวดหมู่รายรับ/รายจ่าย + งบประมาณต่อเดือน"""
    today = timezone.now().date()
    year = today.year
    month = today.month

    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("app_finance:categories_manage")
    else:
        form = CategoryForm()

    categories = Category.objects.all().order_by("kind", "name")

    # ===== ใส่ยอดใช้จริงเดือนนี้แต่ละหมวด (เฉพาะรายจ่าย) =====
    for c in categories:
        # อันนี้คือ snippet ที่โอ็ตถามว่าใส่ตรงไหน → เราใส่ใน loop นี้เลย
        this_month_expense = Transaction.objects.filter(
            date__year=year,
            date__month=month,
            direction="OUT",
            category=c,
            is_estimate=False,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        # attach เป็น attribute ให้ template ใช้ได้เลย
        c.expense_this_month = this_month_expense

        # คิดเปอร์เซ็นต์ใช้ไปของงบ (ถ้ามีงบ)
        if c.monthly_budget:
            if c.monthly_budget > 0:
                c.budget_percent = float(this_month_expense / c.monthly_budget * 100)
            else:
                c.budget_percent = None
        else:
            c.budget_percent = None

    month_label = today.strftime("%B %Y")  # ไว้โชว์ "November 2025" หรือใส่ logic แปลไทยเองได้ทีหลัง

    return render(request, "app_finance/categories.html", {
        "form": form,
        "categories": categories,
        "month_label": month_label,
    })

@login_required
def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]

@login_required
def recurring_list(request):
    """หน้าแสดง/เพิ่มรายการประจำทุกเดือน"""
    today = timezone.now().date()
    recurrings = RecurringTransaction.objects.filter(
        is_active=True
    ).select_related("account", "category").order_by("day_of_month", "name")

    if request.method == "POST":
        form = RecurringTransactionForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกรายการประจำเรียบร้อยแล้ว")
            return redirect("app_finance:recurring_list")
    else:
        form = RecurringTransactionForm()

    context = {
        "today": today,
        "recurrings": recurrings,
        "form": form,
    }
    return render(request, "app_finance/recurring_list.html", {
        "recurrings": recurrings,
        "today": today,
    })

@login_required
def recurring_apply_month(request):
    """
    สร้าง Transaction จริงจาก RecurringTransaction สำหรับเดือนที่เลือก
    default = เดือนปัจจุบัน
    """
    if request.method != "POST":
        return redirect("app_finance:recurring_list")

    today = timezone.now().date()
    year = int(request.POST.get("year", today.year))
    month = int(request.POST.get("month", today.month))

    last_day = calendar.monthrange(year, month)[1]

    created_count = 0

    recurrings = RecurringTransaction.objects.filter(
        is_active=True
    ).select_related("account", "category")

    for r in recurrings:
        d = min(r.day_of_month, last_day)
        tx_date = date(year, month, d)

        # ถ้ามีรายการของ recurring นี้ในเดือนนี้แล้ว ไม่ต้องสร้างซ้ำ
        exists = Transaction.objects.filter(
            source_recurring=r,
            date=tx_date,
        ).exists()
        if exists:
            continue

        note_text = r.name or (r.category.name if r.category else "")

        Transaction.objects.create(
            account=r.account,
            category=r.category,
            direction=r.direction,
            amount=r.amount,
            date=tx_date,
            note=note_text,
            is_estimate=True,   # ให้เป็น "ประมาณการ" ก่อน ค่อยไปแก้ทีหลังได้
            is_paid=False,
            source_recurring=r,
        )
        created_count += 1

    messages.success(
        request,
        f"สร้างรายการ recurring สำหรับ {month}/{year} จำนวน {created_count} รายการแล้ว"
    )
    return redirect("app_finance:transactions_list")

@login_required
def recurring_generate_for_month(request):
    """สร้าง Transaction จาก recurring สำหรับเดือนปัจจุบัน"""
    today = timezone.now().date()
    year = today.year
    month = today.month
    last_day = _last_day_of_month(year, month)

    recurrings = RecurringTransaction.objects.filter(is_active=True)
    created = 0

    for r in recurrings:
        # เคารพ start_date / end_date
        if r.start_date and r.start_date > today:
            continue
        if r.end_date and r.end_date < today:
            continue

        # วันที่จะใช้ในเดือนนี้
        d = min(r.day_of_month, last_day)
        tx_date = date(year, month, d)

        # เช็คว่ามีอยู่แล้วหรือยัง (กันซ้ำ)
        exists = Transaction.objects.filter(
            source_recurring=r,
            date=tx_date,
            amount=r.amount,
            direction=r.direction,
            account=r.account,
            category=r.category,
        ).exists()
        if exists:
            continue

        Transaction.objects.create(
            account=r.account,
            category=r.category,
            date=tx_date,
            direction=r.direction,
            amount=r.amount,
            is_estimate=False,
            is_paid=True,
            note=r.name or "รายการประจำ",
            source_recurring=r,
        )
        created += 1

    if created:
        messages.success(request, f"สร้างรายการประจำสำหรับเดือนนี้แล้ว {created} รายการ")
    else:
        messages.info(request, "ไม่มีรายการใหม่ที่ต้องสร้างสำหรับเดือนนี้")

    return redirect("app_finance:recurring_list")

@login_required
def summary_month(request):
    """สรุปรายจ่ายต่อหมวดสำหรับเดือนที่เลือก (เน้นหมวดค่าใช้จ่าย)"""
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    from decimal import Decimal

    expense_categories = Category.objects.filter(kind="EXPENSE").order_by("name")

    rows = []
    total_budget = Decimal("0")
    total_used = Decimal("0")

    month_names = {
        1: "ม.ค.",
        2: "ก.พ.",
        3: "มี.ค.",
        4: "เม.ย.",
        5: "พ.ค.",
        6: "มิ.ย.",
        7: "ก.ค.",
        8: "ส.ค.",
        9: "ก.ย.",
        10: "ต.ค.",
        11: "พ.ย.",
        12: "ธ.ค.",
    }

    for c in expense_categories:
        used = Transaction.objects.filter(
            date__year=year,
            date__month=month,
            direction="OUT",
            category=c,
            is_estimate=False,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        budget = c.monthly_budget or Decimal("0")
        remaining = None
        percent = None
        over = False

        if budget > 0:
            remaining = budget - used
            percent = float(used / budget * 100) if budget > 0 else None
            if used > budget:
                over = True
            total_budget += budget

        total_used += used

        rows.append({
            "category": c,
            "used": used,
            "budget": budget,
            "remaining": remaining,
            "percent": percent,
            "over": over,
        })

    net_remaining = total_budget - total_used

    years_qs = Transaction.objects.dates("date", "year")
    year_options = [d.year for d in years_qs] or [today.year]

    months = [
        (1, "ม.ค."),
        (2, "ก.พ."),
        (3, "มี.ค."),
        (4, "เม.ย."),
        (5, "พ.ค."),
        (6, "มิ.ย."),
        (7, "ก.ค."),
        (8, "ส.ค."),
        (9, "ก.ย."),
        (10, "ต.ค."),
        (11, "พ.ย."),
        (12, "ธ.ค."),
    ]

    month_label = f"{month_names.get(month, month)} {year}"

    context = {
        "rows": rows,
        "total_budget": total_budget,
        "total_used": total_used,
        "net_remaining": net_remaining,
        "year": year,
        "month": month,
        "years": year_options,
        "months": months,
        "month_label": month_label,
    }
    return render(request, "app_finance/summary_month.html", context)

@login_required
def monthly_report(request):
    """หน้ารีพอร์ตสรุปรายเดือน (เหมาะสำหรับพิมพ์/Export PDF)"""
    now = timezone.now()
    today = now.date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # ===== ตัวเลือกปี/เดือน =====
    months = [
        (1, "ม.ค."), (2, "ก.พ."), (3, "มี.ค."), (4, "เม.ย."),
        (5, "มิ.ย."), (6, "มิ.ย."), (7, "ก.ค."), (8, "ส.ค."),
        (9, "ก.ย."), (10, "ต.ค."), (11, "พ.ย."), (12, "ธ.ค."),
    ]
    years_qs = Transaction.objects.dates("date", "year")
    years = sorted({d.year for d in years_qs} | {today.year}, reverse=True)
    month_label = next((label for m, label in months if m == month), str(month))
    month_label_full = f"{month_label} {year}"

    # ===== ดึงรายการเดือนนี้ (เฉพาะรายการจริง) =====
    tx_qs = Transaction.objects.filter(
        date__year=year,
        date__month=month,
        is_estimate=False,
    ).select_related("account", "category").prefetch_related("tags")

    income_sum = tx_qs.filter(direction="IN").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    expense_sum = tx_qs.filter(direction="OUT").aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    net_sum = income_sum - expense_sum

    # ===== รายจ่ายตามหมวด (top 7) =====
    expense_by_cat = (
        tx_qs.filter(direction="OUT")
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    cat_items = []
    for row in expense_by_cat:
        name = row["category__name"] or "ไม่ระบุหมวด"
        total = row["total"] or Decimal("0")
        cat_items.append({
            "name": name,
            "total": total,
        })
    cat_items_top = cat_items[:7]

    # ===== รายจ่ายตาม Tag (top 7) =====
    expense_by_tag = (
        tx_qs.filter(direction="OUT", tags__isnull=False)
        .values("tags__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    tag_items = []
    for row in expense_by_tag:
        name = row["tags__name"] or "ไม่ระบุแท็ก"
        total = row["total"] or Decimal("0")
        tag_items.append({
            "name": name,
            "total": total,
        })
    tag_items_top = tag_items[:7]

    # ===== งบประมาณเดือนนี้ =====
    budgets_qs = (
        CategoryBudget.objects
        .filter(year=year, month=month)
        .select_related("category")
    )

    expense_by_cat_id = (
        tx_qs.filter(direction="OUT")
        .values("category_id")
        .annotate(total=Sum("amount"))
    )
    expense_map = {row["category_id"]: row["total"] or Decimal("0") for row in expense_by_cat_id}

    budget_rows = []
    total_budget = Decimal("0")
    total_spent_vs_budget = Decimal("0")
    for b in budgets_qs:
        budget_amount = b.amount or Decimal("0")
        spent = expense_map.get(b.category_id, Decimal("0"))
        diff = budget_amount - spent
        percent = float(spent / budget_amount * 100) if budget_amount > 0 else None
        over = spent > budget_amount

        budget_rows.append({
            "budget": b,
            "budget_amount": budget_amount,
            "spent": spent,
            "diff": diff,
            "percent": percent,
            "over": over,
        })
        total_budget += budget_amount
        total_spent_vs_budget += spent

    total_budget_diff = total_budget - total_spent_vs_budget
    total_budget_percent = float(total_spent_vs_budget / total_budget * 100) if total_budget > 0 else None

    # ===== เป้าหมาย (goals) ที่มีการเคลื่อนไหวในเดือนนี้ =====
    goals_rows = []
    goals_qs = Goal.objects.filter(is_active=True).select_related("account")
    for g in goals_qs:
        g_tx = tx_qs.filter(goal=g, direction=g.direction)
        if not g_tx.exists():
            continue
        done = g_tx.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        target = g.target_amount or Decimal("0")
        percent = float(done / target * 100) if target > 0 else None
        goals_rows.append({
            "goal": g,
            "done": done,
            "target": target,
            "percent": percent,
        })

    # ===== Top 10 รายการใหญ่ (ใช้สำหรับเล่าเรื่อง) =====
    big_tx = tx_qs.order_by("-amount")[:10]

    # ===== สร้างข้อความสรุป Insight แบบอ่านง่าย =====
    insights = []

    # 1) เทียบรายจ่ายกับเดือนที่แล้ว
    prev_year, prev_month = year, month - 1
    if prev_month <= 0:
        prev_month += 12
        prev_year -= 1

    prev_tx_qs = Transaction.objects.filter(
        date__year=prev_year,
        date__month=prev_month,
        is_estimate=False,
        direction="OUT",
    )
    prev_expense = prev_tx_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    if prev_tx_qs.exists():
        diff_prev = expense_sum - prev_expense
        diff_percent_prev = None
        if prev_expense > 0:
            diff_percent_prev = float(diff_prev / prev_expense * 100)

        if diff_prev > 0 and diff_percent_prev is not None:
            insights.append(
                f"รายจ่ายเดือนนี้มากกว่าเดือนที่แล้วประมาณ {diff_percent_prev:.0f}% "
                f"(เพิ่มขึ้นราว ๆ ฿{abs(diff_prev):,.0f})"
            )
        elif diff_prev < 0 and diff_percent_prev is not None:
            insights.append(
                f"รายจ่ายเดือนนี้น้อยกว่าเดือนที่แล้วประมาณ {abs(diff_percent_prev):.0f}% "
                f"(ลดลงราว ๆ ฿{abs(diff_prev):,.0f})"
            )
        else:
            insights.append("รายจ่ายเดือนนี้ใกล้เคียงกับเดือนที่แล้ว")

    # 2) หมวดที่ใช้เยอะที่สุด
    if cat_items_top:
        top_cat = cat_items_top[0]
        total_exp = expense_sum if expense_sum > 0 else sum(c["total"] for c in cat_items_top)
        share = float(top_cat["total"] / total_exp * 100) if total_exp > 0 else 0
        insights.append(
            f"หมวดที่ใช้เงินมากที่สุดคือ \"{top_cat['name']}\" "
            f"คิดเป็นประมาณ {share:.0f}% ของรายจ่ายทั้งเดือน (ประมาณ ฿{top_cat['total']:,.0f})"
        )

    # 3) Tag ที่เด่นที่สุด (ถ้ามี Tag)
    if tag_items_top:
        top_tag = tag_items_top[0]
        insights.append(
            f"รายการที่ติด Tag มากที่สุดคือ \"{top_tag['name']}\" "
            f"รวมแล้วราว ๆ ฿{top_tag['total']:,.0f} ในเดือนนี้"
        )

    # 4) งบประมาณรวม ใช้เกิน/ไม่เกิน
    if total_budget > 0:
        if total_budget_diff < 0:
            insights.append(
                f"ใช้เกินงบรวมประมาณ ฿{abs(total_budget_diff):,.0f} "
                f"(ใช้ไป {total_budget_percent:.0f}% ของงบที่ตั้งไว้)"
            )
        else:
            insights.append(
                f"ยังใช้งบไม่หมด เหลืองบรวมประมาณ ฿{total_budget_diff:,.0f} "
                f"(ใช้ไป {total_budget_percent:.0f}% ของงบทั้งหมด)"
            )

    # 5) เป้าหมายที่ขยับมากที่สุดในเดือนนี้
    if goals_rows:
        goals_sorted = sorted(goals_rows, key=lambda g: g["done"], reverse=True)
        top_goal = goals_sorted[0]
        name = top_goal["goal"].name
        done = top_goal["done"]
        percent = top_goal["percent"]
        if percent:
            insights.append(
                f"เป้าหมาย \"{name}\" มีการขยับมากสุดในเดือนนี้ ประมาณ ฿{done:,.0f} "
                f"(คิดเป็น {percent:.0f}% ของเป้าหมายทั้งหมด)"
            )
        else:
            insights.append(
                f"เป้าหมาย \"{name}\" มีการขยับในเดือนนี้ประมาณ ฿{done:,.0f}"
            )

    if not insights:
        insights.append("ยังไม่มีข้อมูลมากพอสำหรับสรุปเป็น Insight ในเดือนนี้")

    context = {
        "today": today,
        "now": now,
        "year": year,
        "month": month,
        "years": years,
        "months": months,
        "month_label_full": month_label_full,

        "income_sum": income_sum,
        "expense_sum": expense_sum,
        "net_sum": net_sum,

        "cat_items_top": cat_items_top,
        "tag_items_top": tag_items_top,

        "budget_rows": budget_rows,
        "total_budget": total_budget,
        "total_spent_vs_budget": total_spent_vs_budget,
        "total_budget_diff": total_budget_diff,
        "total_budget_percent": total_budget_percent,

        "goals_rows": goals_rows,
        "big_tx": big_tx,

        "insights": insights,
    }
    return render(request, "app_finance/monthly_report.html", context)

@login_required
def cash_calendar(request):
    """ปฏิทินเงินเข้า–ออกของเดือนที่เลือก"""
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # จำนวนวันในเดือน
    days_in_month = calendar.monthrange(year, month)[1]

    days = []
    for d in range(1, days_in_month + 1):
        current = date(year, month, d)
        qs = Transaction.objects.filter(date=current, is_estimate=False)

        total_in = qs.filter(direction="IN").aggregate(s=Sum("amount"))["s"] or Decimal("0")
        total_out = qs.filter(direction="OUT").aggregate(s=Sum("amount"))["s"] or Decimal("0")
        net = total_in - total_out

        # recurring ที่ผูก day_of_month วันนี้
        rec_today = RecurringTransaction.objects.filter(
            is_active=True,
            day_of_month=d,
        ).select_related("account", "category")

        days.append({
            "date": current,
            "day": d,
            "weekday": current.weekday(),  # Monday=0 ... Sunday=6
            "total_in": total_in,
            "total_out": total_out,
            "net": net,
            "recurring": list(rec_today),
        })

    first_weekday = days[0]["weekday"] if days else 0
    empty_start = list(range(first_weekday))

    # สำหรับ dropdown เลือกเดือน/ปี
    months = [
        (1, "ม.ค."), (2, "ก.พ."), (3, "มี.ค."), (4, "เม.ย."),
        (5, "พ.ค."), (6, "มิ.ย."), (7, "ก.ค."), (8, "ส.ค."),
        (9, "ก.ย."), (10, "ต.ค."), (11, "พ.ย."), (12, "ธ.ค."),
    ]
    years_qs = Transaction.objects.dates("date", "year")
    year_options = sorted({d.year for d in years_qs} | {today.year})

    month_label = f"{dict(months).get(month, month)} {year}"

    context = {
        "today": today,
        "year": year,
        "month": month,
        "month_label": month_label,
        "days": days,
        "empty_start": empty_start,
        "months": months,
        "years": year_options,
    }
    return render(request, "app_finance/cash_calendar.html", context)

@login_required
def goals_list(request):
    """หน้าดู + เพิ่มเป้าหมายเก็บเงิน พร้อม progress bar"""
    today = timezone.now().date()
    goals = Goal.objects.filter(is_active=True).select_related("account").order_by("target_date", "name")

    from decimal import Decimal
    for g in goals:
        qs = Transaction.objects.filter(
            goal=g,
            is_estimate=False,
            direction=g.direction,
        )
        done = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        g.done_amount = done

        # เป้าทั้งก้อน
        target = g.target_amount or Decimal("0")
        # 👇 เพิ่ม: ยอดคงเหลือ (อาจเป็นติดลบ ถ้าเกินเป้า)
        g.remaining_amount = target - done

        if target > 0:
            g.percent = float(done / target * 100)
        else:
            g.percent = None

        if g.target_date:
            delta = g.target_date - today
            g.days_left = delta.days
        else:
            g.days_left = None

    if request.method == "POST":
        form = GoalForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "บันทึกเป้าหมายเรียบร้อยแล้ว")
            return redirect("app_finance:goals_list")
    else:
        form = GoalForm()

    return render(request, "app_finance/goals_list.html", {
        "today": today,
        "goals": goals,
        "form": form,
    })

@login_required
def goal_detail(request, pk):
    """หน้าเป้าหมายแบบละเอียด + รายการที่เกี่ยวข้อง"""
    today = timezone.now().date()
    from decimal import Decimal

    goal = get_object_or_404(Goal.objects.select_related("account"), pk=pk)

    # ดึงรายการที่ผูกกับ goal นี้ (เฉพาะรายการจริง)
    tx_qs = Transaction.objects.filter(
        goal=goal,
        is_estimate=False,
        direction=goal.direction,
    ).select_related("account", "category").order_by("-date", "-id")

    done = tx_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    target = goal.target_amount or Decimal("0")
    remaining = target - done
    percent = float(done / target * 100) if target > 0 else None

    if goal.target_date:
        delta = goal.target_date - today
        days_left = delta.days
    else:
        days_left = None

    context = {
        "today": today,
        "goal": goal,
        "transactions": tx_qs,
        "done": done,
        "target": target,
        "remaining": remaining,
        "percent": percent,
        "days_left": days_left,
    }
    return render(request, "app_finance/goal_detail.html", context)

@login_required
def monthly_report_pdf(request):
    """สร้าง PDF รายงานรายรับ-รายจ่าย + หมวด สำหรับเดือนที่เลือก"""
    if HTML is None:
        messages.error(
            request,
            "เครื่องนี้ยังไม่พร้อมใช้ระบบสร้าง PDF (WeasyPrint) ตอนนี้ใช้ปุ่ม Print → Save as PDF จาก browser แทนก่อนนะคับ"
        )
        return redirect("app_finance:summary_month")
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    from decimal import Decimal

    # รายจ่ายตามหมวด
    expense_categories = Category.objects.filter(kind="EXPENSE").order_by("name")

    rows = []
    total_budget = Decimal("0")
    total_used = Decimal("0")

    for c in expense_categories:
        used = Transaction.objects.filter(
            date__year=year,
            date__month=month,
            direction="OUT",
            category=c,
            is_estimate=False,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        budget = c.monthly_budget or Decimal("0")
        remaining = None
        percent = None
        over = False

        if budget > 0:
            remaining = budget - used
            percent = float(used / budget * 100) if budget > 0 else None
            if used > budget:
                over = True
            total_budget += budget

        total_used += used

        rows.append({
            "category": c,
            "used": used,
            "budget": budget,
            "remaining": remaining,
            "percent": percent,
            "over": over,
        })

    net_remaining = total_budget - total_used

    # รายรับ/รายจ่ายรวมของเดือน
    month_tx = Transaction.objects.filter(
        date__year=year,
        date__month=month,
        is_estimate=False,
    )
    income_month = month_tx.filter(direction="IN").aggregate(s=Sum("amount"))["s"] or Decimal("0")
    expense_month = month_tx.filter(direction="OUT").aggregate(s=Sum("amount"))["s"] or Decimal("0")
    net_month = income_month - expense_month

    month_names = {
        1: "มกราคม",
        2: "กุมภาพันธ์",
        3: "มีนาคม",
        4: "เมษายน",
        5: "พฤษภาคม",
        6: "มิถุนายน",
        7: "กรกฎาคม",
        8: "สิงหาคม",
        9: "กันยายน",
        10: "ตุลาคม",
        11: "พฤศจิกายน",
        12: "ธันวาคม",
    }
    month_label = f"{month_names.get(month, month)} {year}"

    context = {
        "month_label": month_label,
        "year": year,
        "month": month,
        "rows": rows,
        "total_budget": total_budget,
        "total_used": total_used,
        "net_remaining": net_remaining,
        "income_month": income_month,
        "expense_month": expense_month,
        "net_month": net_month,
    }

    template = get_template("app_finance/monthly_report_pdf.html")
    html_string = template.render(context)

    html = HTML(string=html_string, base_url=request.build_absolute_uri("/"))
    pdf_bytes = html.write_pdf()

    filename = f"finance_report_{year}_{month:02d}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    return response

@login_required
def budgets_overview(request):
    """หน้าดูงบประมาณรายจ่ายต่อหมวด เทียบกับใช้จริงในเดือนที่เลือก"""
    today = timezone.now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # ตัวเลือกปี ใช้จาก CategoryBudget + ปีปัจจุบัน
    years_from_budget = CategoryBudget.objects.values_list("year", flat=True).distinct()
    years = sorted(set(years_from_budget) | {today.year}, reverse=True)

    months = [
        (1, "ม.ค."), (2, "ก.พ."), (3, "มี.ค."), (4, "เม.ย."),
        (5, "พ.ค."), (6, "มิ.ย."), (7, "ก.ค."), (8, "ส.ค."),
        (9, "ก.ย."), (10, "ต.ค."), (11, "พ.ย."), (12, "ธ.ค."),
    ]

    # ดึงงบของเดือนนั้น
    budgets = (
        CategoryBudget.objects
        .filter(year=year, month=month)
        .select_related("category")
        .order_by("category__name")
    )

    # ดึงรายจ่ายจริงต่อหมวดของเดือนนั้น
    expense_qs = (
        Transaction.objects.filter(
            date__year=year,
            date__month=month,
            direction="OUT",
            is_estimate=False,
        )
        .values("category_id")
        .annotate(total=Sum("amount"))
    )
    expense_map = {row["category_id"]: row["total"] or Decimal("0") for row in expense_qs}

    items = []
    total_budget = Decimal("0")
    total_spent = Decimal("0")

    for b in budgets:
        budget_amount = b.amount or Decimal("0")
        spent = expense_map.get(b.category_id, Decimal("0"))
        diff = budget_amount - spent
        percent = float(spent / budget_amount * 100) if budget_amount > 0 else None
        over = spent > budget_amount

        items.append({
            "budget": b,
            "budget_amount": budget_amount,
            "spent": spent,
            "diff": diff,
            "percent": percent,
            "over": over,
        })

        total_budget += budget_amount
        total_spent += spent

    total_diff = total_budget - total_spent
    total_percent = float(total_spent / total_budget * 100) if total_budget > 0 else None

    month_label = next((label for m, label in months if m == month), str(month))
    month_label = f"{month_label} {year}"

    context = {
        "today": today,
        "year": year,
        "month": month,
        "years": years,
        "months": months,
        "month_label": month_label,
        "items": items,
        "total_budget": total_budget,
        "total_spent": total_spent,
        "total_diff": total_diff,
        "total_percent": total_percent,
    }
    return render(request, "app_finance/budgets_overview.html", context)

@login_required
def howto_view(request):
    """หน้าคู่มือการใช้งานแบบย่อ"""
    return render(request, "app_finance/howto.html")

def logout_view(request):
    """ออกจากระบบแล้วเด้งกลับไปหน้า login ทันที"""
    logout(request)
    return redirect("login")