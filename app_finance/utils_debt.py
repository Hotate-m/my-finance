from decimal import Decimal

def calculate_debt_plan(debts, monthly_budget, strategy="AVALANCHE", max_months=120):
    """
    debts: list ของ dict
      [
        {
          "name": "...",
          "balance": Decimal(),
          "interest_rate": Decimal(),  # ต่อปี เช่น 18
          "min_payment": Decimal(),
        },
        ...
      ]
    monthly_budget: Decimal
    strategy: "AVALANCHE" หรือ "SNOWBALL"
    return: list ของเดือน
    """
    # copy ข้อมูลก่อน กัน side effect
    items = []
    for d in debts:
        items.append({
            "name": d["name"],
            "interest_rate": Decimal(d["interest_rate"]),
            "min_payment": Decimal(d["min_payment"]),
            "balance": Decimal(d["balance"]),
        })

    plan = []

    month = 0
    while month < max_months and any(i["balance"] > 0 for i in items):
        month += 1

        # 1) คิดดอกเบี้ยรายเดือน (สมมติ interest_rate เป็น % ต่อปี)
        for i in items:
            if i["balance"] <= 0:
                continue
            monthly_rate = (i["interest_rate"] / Decimal("100")) / Decimal("12")
            i["balance"] = i["balance"] * (Decimal("1") + monthly_rate)

        # 2) จ่ายขั้นต่ำทุกใบ
        payments = []
        total_min = Decimal("0")
        for i in items:
            if i["balance"] <= 0:
                pay_min = Decimal("0")
            else:
                pay_min = min(i["min_payment"], i["balance"])
            payments.append({
                "name": i["name"],
                "pay_min": pay_min,
                "extra": Decimal("0"),
            })
            total_min += pay_min

        if monthly_budget < total_min:
            # งบไม่พอจ่ายขั้นต่ำ -> แจ้งเตือนให้รู้ใน plan
            plan.append({
                "month": month,
                "warning": "งบไม่พอจ่ายขั้นต่ำทุกใบ",
                "details": payments,
                "total_payment": monthly_budget,
                "total_balance": sum(i["balance"] for i in items),
            })
            break

        extra = monthly_budget - total_min

        # 3) เรียงลำดับหนี้ตาม strategy
        if strategy == "SNOWBALL":
            ordered = sorted(
                range(len(items)),
                key=lambda idx: items[idx]["balance"],
            )
        else:  # AVA
            ordered = sorted(
                range(len(items)),
                key=lambda idx: items[idx]["interest_rate"],
                reverse=True,
            )

        # 4) ยิง extra ไปใบที่ควรจัดการก่อน
        for idx in ordered:
            if extra <= 0:
                break
            i = items[idx]
            if i["balance"] <= 0:
                continue

            # หนี้คงเหลือหลังจ่ายขั้นต่ำ
            p = payments[idx]
            remaining_after_min = i["balance"] - p["pay_min"]
            if remaining_after_min <= 0:
                continue

            pay_extra = min(extra, remaining_after_min)
            p["extra"] = pay_extra
            extra -= pay_extra

        # 5) หักยอดหนี้จริง
        for idx, i in enumerate(items):
            total_pay = payments[idx]["pay_min"] + payments[idx]["extra"]
            i["balance"] = max(i["balance"] - total_pay, Decimal("0"))

        plan.append({
            "month": month,
            "details": payments,
            "total_payment": monthly_budget,
            "total_balance": sum(i["balance"] for i in items),
        })

    return plan
